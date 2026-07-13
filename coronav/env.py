"""CoroNavEnv: the benchmark environment wrapping stEVE + coronary simulation.

This module provides ``build_env()`` and ``run_episode()`` — the two functions
a benchmark script needs to run a VLM operator on the coronary anatomy.
"""
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw
import pyvista as pv
from scipy.spatial import cKDTree

import eve
from eve.intervention.fluoroscopy.pillow import Pillow
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from eve.util.coordtransform import vessel_cs_to_tracking3d, tracking3d_to_2d

from .sim.coronary_sim import CoronaryBeamAdapter
from .sim.pth_centerlines import left_coronary_branches
from .operator.base import VLMOperator
from .prompts import _PROXIMITY_GATE_MM, _PROXIMITY_GATE_ADV_DEFAULT, _RETRACTION_BUDGET

# ── Defaults ───────────────────────────────────────────────────────────────────
IMAGE_ROT_ZX = [0, -40]   # AP Cranial 40 deg
IMAGE_SIZE   = (512, 512)
TRANS_LIMIT  = 50.0
ROT_LIMIT    = math.pi
XTIP_HEALTHY = 10.0
MAX_RESET    = 3

VESSEL_FILL: Dict[str, int] = {"overlay": 90, "contrast": 108}
WIRE_FILL:   Dict[str, int] = {"wire_only": 40, "overlay": 40, "contrast": 40}

VALID_INTENTS = {"advance", "retract", "rotate_cw", "rotate_ccw", "hold"}

# ── PillowTracking ─────────────────────────────────────────────────────────────

class PillowTracking(Pillow, TrackingOnly):
    """Renders the guidewire onto a grayscale fluoroscopy image."""

    def __init__(self, image_size, simulation, vessel_tree,
                 wire_diameter=0.89, image_frequency=7.5,
                 image_rot_zx=(0.0, 0.0), image_center=None, field_of_view=None):
        TrackingOnly.__init__(self, simulation=simulation, vessel_tree=vessel_tree,
                              image_frequency=image_frequency, image_rot_zx=image_rot_zx,
                              image_center=image_center, field_of_view=field_of_view)
        if isinstance(image_size, int):
            image_size = (image_size, image_size)
        self.image_size = image_size
        self._wire_diameter = wire_diameter
        self._image_mode = "L"
        self.low = 0; self.high = 255
        self._tracking_to_image_factor = 0
        self._tracking_offset = [0, 0]
        self._image_offset = [0, 0]
        self._image = None

    def reset(self, episode_nr=0):
        TrackingOnly.reset(self, episode_nr)
        Pillow.reset(self, episode_nr)
        self.step()

    def step(self):
        trackings = self.device_trackings2d
        noise = Image.effect_noise(size=self.image_size, sigma=5)
        wire  = self._render(trackings, [self._wire_diameter])
        self._image = np.asarray(ImageChops.darker(wire, noise), dtype=np.uint8)

    @property
    def image(self): return self._image

    @property
    def image_space(self):
        import gymnasium as gym
        return gym.spaces.Box(0, 255, self.image_size, dtype=np.uint8)

    @property
    def tracking3d_space(self):
        import gymnasium as gym
        lo = vessel_cs_to_tracking3d(self.vessel_tree.coordinate_space.low,
                                     self.image_rot_zx, self.image_center, self.field_of_view)
        hi = vessel_cs_to_tracking3d(self.vessel_tree.coordinate_space.high,
                                     self.image_rot_zx, self.image_center, self.field_of_view)
        return gym.spaces.Box(low=np.minimum(lo, hi), high=np.maximum(lo, hi))


# ── Environment builder ───────────────────────────────────────────────────────

def build_env(
    anatomy_dir: str,
    n_steps: int = 60,
    image_rot_zx: List[int] = IMAGE_ROT_ZX,
) -> Tuple:
    """Build the stEVE environment for the A1 (VMR0066) coronary anatomy.

    Parameters
    ----------
    anatomy_dir : path to ``data/anatomy/a1_vmr0066`` (or equivalent for A2/A3)
    n_steps     : step budget per episode
    image_rot_zx : fluoroscopy projection angles [rot_z, rot_x] in degrees

    Returns
    -------
    (env, sim, fluoro, branch_kds, mid_lad_world)
        env         : stEVE Env
        sim         : CoronaryBeamAdapter (for safe_reset and tip position)
        fluoro      : PillowTracking (for image retrieval)
        branch_kds  : {branch_name: cKDTree}  for tip-branch classification
        mid_lad_world : (3,) float64  SOFA world-space target coordinates
    """
    adir = Path(anatomy_dir)
    paths_dir = adir / "paths"
    mesh_path = adir / "clipped_left.obj"
    vtp_path  = adir / "clipped_left.vtp"

    branches, ins_pt, ins_dir = left_coronary_branches(
        str(paths_dir), junction_radius_mm=3.0
    )
    lad = next(b for b in branches if b.name == "lad")
    mid_idx = len(lad.coordinates) // 2
    mid_lad = lad.coordinates[mid_idx].copy()

    vt = FromMesh(
        mesh=str(mesh_path),
        insertion_position=tuple(ins_pt.tolist()),
        insertion_direction=tuple(ins_dir.tolist()),
        branch_list=branches, approx_branch_radii=2.5,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )

    device = eve.intervention.device.JShaped(tip_radius=1.5, tip_angle=0.2 * math.pi)
    sim    = CoronaryBeamAdapter(friction=0.001, dt_simulation=0.006, max_it=2000)
    fluoro = PillowTracking(
        image_size=IMAGE_SIZE, simulation=sim, vessel_tree=vt,
        wire_diameter=0.89, image_frequency=7.5,
        image_rot_zx=image_rot_zx,
    )
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=5.0, branch="lad", idx=mid_idx)
    intvn  = eve.intervention.MonoPlaneStatic(
        vessel_tree=vt, devices=[device], simulation=sim,
        fluoroscopy=fluoro, target=target)
    start  = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf     = eve.pathfinder.BruteForceBFS(intervention=intvn)
    pos    = eve.observation.wrapper.NormalizeTracking2DEpisode(
        eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)
    obs    = eve.observation.ObsDict({"pos": pos})
    env    = eve.Env(
        intervention=intvn, observation=obs,
        reward=eve.reward.TargetReached(intervention=intvn, factor=1.0),
        terminal=eve.terminal.TargetReached(intervention=intvn),
        truncation=eve.truncation.MaxSteps(n_steps),
        visualisation=None, start=start, pathfinder=pf,
    )

    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}

    # Warmup reset to initialise pixel transform (required before mask precomputation)
    env.reset()
    binary_mask = _precompute_mask(fluoro, vtp_path)

    return env, sim, fluoro, branch_kds, mid_lad, binary_mask


def _precompute_mask(fluoro: PillowTracking, vtp_path: Path) -> np.ndarray:
    """Project clipped_left.vtp triangles onto the image plane (once per run)."""
    mesh  = pv.read(str(vtp_path)).triangulate()
    verts = np.asarray(mesh.points, dtype=np.float64)
    v3d   = vessel_cs_to_tracking3d(verts, fluoro.image_rot_zx,
                                    fluoro.image_center, fluoro.field_of_view)
    v2d   = tracking3d_to_2d(v3d)
    offset     = np.asarray(fluoro._tracking_offset, dtype=np.float64)
    img_offset = np.asarray(fluoro._image_offset, dtype=np.float64)
    H = fluoro.image_size[1]
    px = (v2d + offset) * fluoro._tracking_to_image_factor + img_offset
    px = px.copy(); px[:, 1] = -px[:, 1] + H
    px = np.round(px).astype(np.int32)

    raw   = np.asarray(mesh.faces, dtype=np.int32)
    faces = raw.reshape(-1, 4)[:, 1:]
    mask  = Image.new("L", fluoro.image_size, 255)
    draw  = ImageDraw.Draw(mask)
    for tri in faces:
        pts = [(int(px[i, 0]), int(px[i, 1])) for i in tri]
        draw.polygon(pts, fill=0)
    return np.asarray(mask, dtype=np.uint8)


def render_frame(fluoro: PillowTracking, binary_mask: np.ndarray, mode: str) -> np.ndarray:
    """Render one fluoroscopy frame for the VLM.

    mode : "wire_only" | "overlay" | "contrast"
    """
    if mode == "wire_only":
        return fluoro.image

    fill   = VESSEL_FILL[mode]
    base   = Image.fromarray(np.where(binary_mask == 0, fill, 255).astype(np.uint8))
    draw   = ImageDraw.Draw(base)
    for tracking_2d in fluoro.device_trackings2d:
        if len(tracking_2d) < 2:
            continue
        wire_px = fluoro._coord_transform_tracking_to_image(tracking_2d)
        w = max(2, int(fluoro._wire_diameter * fluoro._tracking_to_image_factor))
        draw.line(wire_px, fill=WIRE_FILL.get(mode, 40), width=w)
    noise = Image.effect_noise(size=fluoro.image_size, sigma=5)
    return np.asarray(ImageChops.darker(base, noise), dtype=np.uint8)


# ── Episode runner ─────────────────────────────────────────────────────────────

def run_episode(
    env,
    sim: CoronaryBeamAdapter,
    fluoro: PillowTracking,
    binary_mask: np.ndarray,
    branch_kds: Dict,
    mid_lad: np.ndarray,
    operator: VLMOperator,
    seed: int,
    episode_num: int,
    n_steps: int,
    mode: str = "wire_only",
    verbose: bool = False,
) -> List[Dict]:
    """Run one episode and return a list of trace row dicts.

    Each row is suitable for writing to a trace.jsonl file and for computing
    metrics via ``lm_metrics()``.
    """
    operator.reset()
    ok, tip, xtip, _ = _safe_reset(env, sim, episode_num, seed)
    if not ok:
        return []

    dist_history: List[float] = []
    retract_budget = _RETRACTION_BUDGET
    no_progress    = 0
    trace: List[Dict] = []

    for step in range(1, n_steps + 1):
        tip_now = np.array(sim.dof_positions[0], dtype=float)
        dist    = float(np.linalg.norm(tip_now - mid_lad))
        trend   = _dist_trend(dist_history, dist)
        dist_history.append(dist)

        frame = render_frame(fluoro, binary_mask, mode)

        state_text = (
            f"Monoplane AP Cranial 40 deg view. "
            f"Distance to mid-LAD target: {dist:.1f} mm. "
            f"Distance trend (last 3 steps): {trend}. "
            f"Retractions remaining: {retract_budget} of {_RETRACTION_BUDGET}. "
            f"Consecutive no-progress advance steps: {no_progress}."
        )
        if no_progress >= 3:
            state_text += " You MUST rotate on this step."
        if dist < _PROXIMITY_GATE_MM and trend == "decreasing":
            state_text += (
                f" PROXIMITY GATE ACTIVE: distance is decreasing and under "
                f"{_PROXIMITY_GATE_MM:.0f}mm -- do NOT rotate, output advance."
            )
        state_text += " Navigate the wire tip to the mid-LAD target."

        api_ok = parse_ok = False
        action_dict = {}
        trans = rot = 0.0
        intent = "hold"

        try:
            action_dict = operator.act([frame], state_text)
            api_ok = True
            act    = action_dict.get("action", {})
            trans  = float(np.clip(float(act.get("translation", 0.0)), -TRANS_LIMIT, TRANS_LIMIT))
            rot    = float(np.clip(float(act.get("rotation",    0.0)), -ROT_LIMIT,   ROT_LIMIT))
            intent = str(action_dict.get("intended_direction", "hold")).lower()
            if intent not in VALID_INTENTS:
                intent = "hold"
            parse_ok = True
        except Exception as exc:
            if verbose:
                print(f"    [ep{episode_num} step{step}] operator error: {exc}")

        # Retraction budget
        is_retract = (intent == "retract" and trans < 0)
        if is_retract and retract_budget <= 0:
            trans = 0.0; rot = 0.0; intent = "hold"
            is_retract = False
        elif (dist < _PROXIMITY_GATE_MM and trend == "decreasing"
              and intent in ("rotate_cw", "rotate_ccw")):
            rot = 0.0
            trans = _PROXIMITY_GATE_ADV_DEFAULT
            intent = "advance"
        if is_retract:
            retract_budget -= 1

        # No-progress counter
        is_advance = (intent == "advance" and trans > 0)
        _, _, terminal, truncation, _ = env.step(np.array([[trans, rot]]))
        tip_after = np.array(sim.dof_positions[0], dtype=float)
        dist_after = float(np.linalg.norm(tip_after - mid_lad))

        if is_advance:
            no_progress = no_progress + 1 if dist_after >= dist - 0.5 else 0
        else:
            no_progress = 0

        tip_branch = _classify_branch(tip_after, branch_kds)
        is_rotate  = intent in ("rotate_cw", "rotate_ccw")

        row = {
            "episode": episode_num,
            "step": step,
            "seed": seed,
            "mode": mode,
            "api_ok": api_ok,
            "parse_ok": parse_ok,
            "intended_direction": intent,
            "is_rotate_step": is_rotate,
            "tip_target_dist": dist,
            "tip_target_dist_after": dist_after,
            "tip_branch_obs": tip_branch,
            "translation": trans,
            "rotation": rot,
            "terminal": bool(terminal),
            "truncation": bool(truncation),
            **{k: v for k, v in action_dict.items()
               if k not in ("action", "intended_direction")},
        }
        trace.append(row)

        if verbose:
            print(f"    step {step:2d}  dist={dist:.1f}->{dist_after:.1f}  "
                  f"branch={tip_branch}  {intent}  "
                  f"({'success' if terminal and not truncation else 'truncated' if truncation else '...'})")

        if terminal or truncation:
            break

    return trace


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dist_trend(history: List[float], current: float) -> str:
    if len(history) < 2:
        return "unknown"
    change = current - history[-2]
    if change < -1.0: return "decreasing"
    if change >  1.0: return "increasing"
    return "stable"


def _classify_branch(tip: np.ndarray, branch_kds: Dict) -> str:
    best_name = "unknown"
    best_dist = float("inf")
    for name, kd in branch_kds.items():
        d, _ = kd.query(tip)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def _safe_reset(env, sim, episode_num: int, seed: int):
    for attempt in range(1, MAX_RESET + 1):
        if hasattr(sim, "reset_devices") and sim._instruments_combined is not None:
            sim.reset_devices()
        env.episode_number = episode_num - 1
        env.reset(seed=seed)
        tip = np.array(sim.dof_positions[0], dtype=float)
        xtip = float(sim.inserted_lengths[0])
        if np.any(np.isnan(tip)) or xtip > XTIP_HEALTHY:
            continue
        env.step(np.array([[0.0, 0.0]]))
        if np.any(np.isnan(np.array(sim.dof_positions[0], dtype=float))):
            continue
        if hasattr(sim, "reset_devices") and sim._instruments_combined is not None:
            sim.reset_devices()
        env.episode_number = episode_num - 1
        env.reset(seed=seed)
        tip_f  = np.array(sim.dof_positions[0], dtype=float)
        xtip_f = float(sim.inserted_lengths[0])
        return True, tip_f, xtip_f, attempt
    return False, None, None, MAX_RESET
