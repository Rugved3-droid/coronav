"""
D:\steve\pilot\run_asoca.py
VLM operator -- coronary navigation on ASOCA anatomies, monoplane.

Identical run pipeline to run_coronary.py (VMR 0066) with these differences:
  - ANATOMY: ASOCA Normal_12 or Normal_5 (--anatomy flag)
  - BRANCHES: asoca_left_coronary_branches() instead of left_coronary_branches()
  - MESH: clipped_asoca_normal{12|5}.{vtp|obj}
  - SYSTEM_PROMPT: per-anatomy geometry (LM length, LAD/LCX directions, distances)
                   NO early-phase distance increase section (absent in ASOCA)
  - PROXIMITY_GATE_DIST_MM: 15mm (Normal_12) / 25mm (Normal_5) -- geometry-derived
                             (gate must fire AFTER bifurcation, not AT it)
  - SEEDS: 3001+i*11 (Normal_12), 4001+i*11 (Normal_5) -- distinct from VMR 0066

Everything else IDENTICAL to run_coronary.py:
  MODEL, IMAGE_ROT_ZX, IMAGE_SIZE, RETRACTION_BUDGET, PROXIMITY_GATE_ADV_DEFAULT,
  TRANS_LIMIT, ROT_LIMIT, XTIP_HEALTHY_MAX, MAX_RESET_TRIES,
  PillowTracking, precompute_binary_mask, render_frame, parse_action,
  safe_reset, run_arm, write_summary.

Geometry parameters are DERIVED from each anatomy -- not tuned to outcomes.

Usage:
    . D:\\steve\\activate_steve.ps1
    $env:ANTHROPIC_API_KEY = "sk-..."
    $env:SOFA_ROOT = "D:\\steve\\deps\\SOFA_v23.06.00_Win64"
    $env:PYTHONPATH = "D:\\steve\\deps\\SOFA_v23.06.00_Win64\\plugins\\SofaPython3\\lib\\python3\\site-packages"
    $env:PATH = "D:\\steve\\deps\\SOFA_v23.06.00_Win64\\bin;" + $env:PATH

Smoke test (3 eps x 10 steps):
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal12 --mode wire_only --episodes 3 --steps 10 --out D:\\steve\\pilot\\smoke_normal12
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal5  --mode wire_only --episodes 3 --steps 10 --out D:\\steve\\pilot\\smoke_normal5

Full run (per-anatomy budget from ANATOMY_PARAMS: normal12=120 steps, normal5=150 steps):
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal12 --mode wire_only
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal12 --mode overlay
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal5  --mode wire_only
    D:\\conda\\envs\\steve\\python.exe D:\\steve\\pilot\\run_asoca.py --anatomy normal5  --mode overlay
"""

import argparse
import base64
import datetime
import json
import math
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageChops
import pyvista as pv
from scipy.spatial import cKDTree

# ── Paths ──────────────────────────────────────────────────────────────────────
PILOT_ROOT = Path(r"D:\steve\pilot")
STEVE_ROOT = Path(r"D:\steve\stEVE")

sys.path.insert(0, str(STEVE_ROOT))
sys.path.insert(0, str(PILOT_ROOT))

import eve
from eve.intervention.fluoroscopy.pillow import Pillow
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from eve.util.coordtransform import vessel_cs_to_tracking3d, tracking3d_to_2d

from coronary_fixture.coronary_sim import CoronaryBeamAdapter
from asoca_adapter import asoca_left_coronary_branches

# ── Constants (IDENTICAL to run_coronary.py unless noted) ─────────────────────
MODEL                      = "claude-sonnet-4-6"
TRANS_LIMIT                = 50.0
ROT_LIMIT                  = 3.14159
RETRACTION_BUDGET          = 2
MAX_RESET_TRIES            = 3
XTIP_HEALTHY_MAX           = 10.0
PROXIMITY_GATE_ADV_DEFAULT = 35.0

IMAGE_ROT_ZX = [0, -40]    # AP Cranial 40° -- same as VMR 0066
IMAGE_SIZE   = (512, 512)

VESSEL_FILL  = {"overlay": 90, "contrast": 108, "overlay_bright": 90}
WIRE_FILL_BY_MODE = {"wire_only": 40, "overlay": 40, "contrast": 40, "overlay_bright": 20}
BG_FILL      = 255

VALID_INTENTS = {"advance", "retract", "rotate_cw", "rotate_ccw", "hold"}

HALLUCINATION_KEYWORDS = [
    "aneurysm", "stenosis", "plaque", "thrombus", "clot",
    "occlusion", "dissection", "embolism",
    "subclavian", "carotid", "aortic arch", "femoral", "descending aorta",
    "ascending aorta",
]


# ── Per-anatomy configuration ──────────────────────────────────────────────────
#
# All values are GEOMETRY-DERIVED from asoca_geom_report.py.
# Neither proximity gate nor system-prompt distances have been tuned to outcomes.
#
# Normal_12 proximity gate: 15mm  (bif_to_mid=24.7mm; gate fires at 0.61 × bif_to_mid,
#   i.e. ~10mm PAST the bifurcation. At 25mm the gate would fire AT the bifurcation,
#   preventing rotation before the fork decision. 15mm fires after the fork.)
# Normal_5  proximity gate: 25mm  (bif_to_mid=39.1mm; gate fires at 0.64 × bif_to_mid,
#   ~14mm past the bifurcation. Same fractional depth as VMR 0066.)

ANATOMY_PARAMS = {
    "normal12": dict(
        case_n              = 12,
        lm_mm               = 16.6,
        init_dist_mm        = 35.2,
        bif_to_mid_mm       = 24.7,
        retract_thr_mm      = 27.2,
        lad_dir_text        = "rightward",
        lcx_dir_text        = "leftward-downward",
        proximity_gate_mm   = 15.0,
        max_it              = 2000,
        n_steps             = 120,    # scripted: target at step 11; 120 is ample
        vtp_path            = PILOT_ROOT / "clipped_asoca_normal12.vtp",
        mesh_path           = PILOT_ROOT / "clipped_asoca_normal12.obj",
        seeds               = [3001 + i * 11 for i in range(25)],
    ),
    "normal5": dict(
        case_n              = 5,
        lm_mm               = 30.3,
        init_dist_mm        = 56.7,
        bif_to_mid_mm       = 39.1,
        retract_thr_mm      = 43.0,
        lad_dir_text        = "downward-leftward",
        lcx_dir_text        = "upward-rightward",
        proximity_gate_mm   = 25.0,
        max_it              = 2000,   # passes stability at 2000; consistent with Normal_12 and VMR0066
        n_steps             = 150,    # VLM reaches 14.9mm at step 120 (budget check ep1); +30 margin
        vtp_path            = PILOT_ROOT / "clipped_asoca_normal5.vtp",
        mesh_path           = PILOT_ROOT / "clipped_asoca_normal5.obj",
        seeds               = [4001 + i * 11 for i in range(25)],
    ),
}


# ── System prompt (geometry-derived, NOT tuned to outcomes) ───────────────────
#
# Strategic content is IDENTICAL to run_coronary.py:
#   - "advance/retract/rotate" rules
#   - retraction budget rule
#   - proximity gate rule
#   - action format
#
# Anatomy-specific sections (differ from VMR 0066 and between ASOCA cases):
#   - LM length
#   - LAD/LCX direction in AP Cranial 40 deg
#   - Distance values (init, bifurcation, retract threshold)
#   - NO "early-phase distance increase" section (not present in ASOCA anatomies)
#   - Instead: "distance decreases from step 1" with per-anatomy values

def make_system_prompt(params: dict) -> str:
    p = params
    lm_mm      = p["lm_mm"]
    init_d     = p["init_dist_mm"]
    bif_d      = p["bif_to_mid_mm"]
    ret_thr    = p["retract_thr_mm"]
    lad_dir    = p["lad_dir_text"]
    lcx_dir    = p["lcx_dir_text"]
    gate_mm    = p["proximity_gate_mm"]

    return (
        "You are operating a guidewire inside a coronary artery. "
        "You receive ONE fluoroscopy image per step: a monoplane AP Cranial 40 deg view "
        "(anterior-posterior projection, cranially angulated 40 degrees).\n\n"

        "WHAT YOU SEE:\n"
        "  - The guidewire appears as a dark curved line.\n"
        "  - Depending on the imaging condition, the coronary vessel anatomy may "
        "appear as gray banding (explicit vessel map) or a faint shadow (angiographic). "
        "Navigate toward the mid-LAD target regardless of which condition is active.\n"
        "  - There is no visible target marker in the image. "
        "Use the distance and trend values in the user message to track progress.\n\n"

        "CRITICAL VASCULAR TOPOLOGY -- read this before every decision:\n\n"

        "ROUTE:\n"
        "  The wire enters the coronary circulation at the LEFT coronary ostium -- "
        "a small opening on the anterior surface of the aortic root. "
        "From the ostium, the wire must traverse:\n"
        f"    1. LEFT MAIN (LM) trunk -- a short (~{lm_mm:.0f}mm) artery; divides at its "
        "distal end into LAD and LCX.\n"
        f"    2. LAD (Left Anterior Descending) -- continues from the LM bifurcation in the "
        f"{lad_dir.upper()} direction in this AP Cranial 40 deg view, "
        "descending toward the cardiac apex.\n"
        f"    3. Mid-LAD target -- approximately the midpoint of the LAD (~{bif_d:.0f}mm "
        "from the bifurcation).\n"
        f"  The LCX (Left Circumflex) is the WRONG branch -- it departs the LM "
        f"bifurcation in the {lcx_dir.upper()} direction in this view "
        f"(opposite direction to the LAD).\n"
        "  The wire is trapped inside the vessel. It can only move FORWARD along "
        "the path (advance) or BACKWARD along the path it came from (retract). "
        "It cannot jump to the target in a straight line.\n\n"

        "DISTANCE BEHAVIOR FOR THIS ANATOMY -- no early-phase increase:\n"
        f"  Starting distance (wire at ostium): approximately {init_d:.0f}mm. "
        "In this anatomy, the 3D distance to the mid-LAD target DECREASES monotonically "
        "once the wire begins advancing -- there is no early-phase distance increase. "
        "Every correct advance step brings the wire closer to the target "
        "(the first few steps may show little movement as the wire seats at the ostium).\n"
        f"  At the LM bifurcation: distance is approximately {bif_d:.0f}mm. "
        "Once into the LAD proper, distance continues decreasing toward 0mm.\n"
        f"  IF the wire enters the LCX instead of the LAD, the distance will STALL or "
        "INCREASE after you have advanced substantially. In this anatomy, increasing "
        f"distance after reaching approximately {ret_thr:.0f}mm is a signal of wrong-branch "
        "entry (NOT a normal traversal artifact). Retract if this occurs.\n\n"

        "BRANCH DECISION AT THE LM BIFURCATION:\n"
        f"  - ADVANCE into the LAD -- it continues in the {lad_dir} direction.\n"
        "  - If the wire mistakenly enters the LCX (the distance stalls or increases "
        "after substantial advance AND the wire appears to curve "
        f"{lcx_dir}), retract to the bifurcation, then use rotation "
        "to redirect the tip toward the LAD before advancing again.\n"
        "  - This is the ONE correct use of retraction. No other situation justifies "
        "consuming the retraction budget.\n\n"

        "ROTATIONAL CONTROL:\n"
        "  - When advancing produces no progress (distance fails to decrease for "
        "2+ consecutive advance steps), ROTATE before advancing again.\n"
        "  - Use translate=0, rotation=+/-1.0 to +/-2.0 rad/s for 30-60 degree "
        "turns. Smaller values for fine adjustment near the target.\n"
        "  - Rotation is NOT retraction and does not consume the retraction budget.\n"
        "  - If THREE advance steps in a row produce no progress, you MUST rotate "
        "on the next step.\n\n"
        "  PROXIMITY GATE: When the user message reports "
        "'Distance trend: decreasing' AND the current distance is under "
        f"{gate_mm:.0f}mm, do NOT rotate. The wire is on final "
        "approach and the trajectory is already working. Rotating at this point "
        "disrupts a stable approach and causes regression. "
        "Output advance.\n\n"

        f"RETRACTION BUDGET -- {RETRACTION_BUDGET} retractions per episode:\n"
        "  - Each step, the user message tells you how many remain.\n"
        "  - Retract ONLY when the wire clearly entered the LCX instead of the LAD.\n"
        "  - In this anatomy, there is NO early-phase distance increase. "
        "If distance is increasing, it likely means wrong branch.\n"
        "  - If budget is 0, advance or rotate instead of retracting.\n\n"

        "Navigate the wire tip to the mid-LAD target.\n\n"
        "Output ONLY a single JSON object -- no text before or after it:\n"
        '{"tip_location_statement": "<which vessel/branch the wire appears to be in>", '
        '"target_location_statement": "<where the target is, inferred from anatomy and distance>", '
        '"intended_direction": "<advance|retract|rotate_cw|rotate_ccw|hold>", '
        '"safety_rationale": "<safety concern or none>", '
        '"action": {"translation": <float>, "rotation": <float>}}\n\n'
        "Action semantics:\n"
        "  translation : positive = advance wire forward, negative = retract.\n"
        "                Range [-50.0, 50.0] mm/s.\n"
        "  rotation    : steers the tip. Positive = clockwise, negative = counter-clockwise.\n"
        "                Range [-3.14, 3.14] rad/s.\n"
        "  For a pure rotation step: set translation=0, rotation=+/-1.0 to +/-2.0.\n"
        "REQUIRED -- intended_direction MUST be consistent with the action:\n"
        "  advance    -> translation > 0\n"
        "  retract    -> translation < 0\n"
        "  rotate_cw  -> rotation > 0  (translation near 0)\n"
        "  rotate_ccw -> rotation < 0  (translation near 0)\n"
        "  hold       -> translation and rotation both near zero"
    )


# ── Proximity gate helpers (parameterized by per-anatomy gate distance) ────────

def _dist_trend(dist_history: list, dist_obs: float) -> str:
    if len(dist_history) < 2:
        return "unknown"
    change = dist_obs - dist_history[-2]
    if change < -1.0: return "decreasing"
    if change >  1.0: return "increasing"
    return "stable"


def _gate_active(dist_obs: float, trend: str, gate_mm: float) -> bool:
    return dist_obs < gate_mm and trend == "decreasing"


def user_msg(retractions_remaining: int, no_progress_advances: int,
             current_dist: float, dist_trend: str, gate_mm: float) -> str:
    parts = [
        "Monoplane AP Cranial 40 deg view.",
        f"Retractions remaining: {retractions_remaining} of {RETRACTION_BUDGET}.",
        f"Consecutive no-progress advance steps: {no_progress_advances}.",
        f"Current distance to mid-LAD target: {current_dist:.1f} mm.",
        f"Distance trend (last 3 steps): {dist_trend}.",
    ]
    if no_progress_advances >= 3:
        parts.append("You MUST rotate on this step.")
    if _gate_active(current_dist, dist_trend, gate_mm):
        parts.append(
            f"PROXIMITY GATE ACTIVE: distance is decreasing and under "
            f"{gate_mm:.0f}mm -- do NOT rotate, output advance."
        )
    parts.append("Navigate the wire tip to the mid-LAD target.")
    return " ".join(parts)


# ── PillowTracking (IDENTICAL to run_coronary.py) ─────────────────────────────

class PillowTracking(Pillow, TrackingOnly):
    def __init__(self, image_size, simulation, vessel_tree,
                 wire_diameter=0.89, image_frequency=7.5,
                 image_rot_zx=(0.0, 0.0), image_center=None, field_of_view=None):
        TrackingOnly.__init__(self, simulation=simulation, vessel_tree=vessel_tree,
                              image_frequency=image_frequency, image_rot_zx=image_rot_zx,
                              image_center=image_center, field_of_view=field_of_view)
        if isinstance(image_size, int):
            image_size = (image_size, image_size)
        self.image_size         = image_size
        self._wire_diameter     = wire_diameter
        self._image_mode        = "L"
        self.low = 0; self.high = 255
        self._tracking_to_image_factor = 0
        self._tracking_offset   = [0, 0]
        self._image_offset      = [0, 0]
        self._image             = None

    def reset(self, episode_nr=0):
        TrackingOnly.reset(self, episode_nr)
        Pillow.reset(self, episode_nr)
        self.step()

    def step(self):
        trackings = self.device_trackings2d
        noise_img = Image.effect_noise(size=self.image_size, sigma=5)
        phys_img  = self._render(trackings, [self._wire_diameter])
        self._image = np.asarray(ImageChops.darker(phys_img, noise_img), dtype=np.uint8)

    @property
    def image(self): return self._image
    @property
    def image_space(self):
        import gymnasium as gym
        return gym.spaces.Box(0, 255, self.image_size, dtype=np.uint8)

    @property
    def tracking3d_space(self):
        # After cranial rotation the bounding-box corners can swap in one axis
        # (Normal_5: Y-extent inverts by ~1.7mm). Recompute without calling the
        # base property (it constructs the failing Box before we can sort).
        import gymnasium as gym
        low  = self.vessel_tree.coordinate_space.low
        high = self.vessel_tree.coordinate_space.high
        low_t  = vessel_cs_to_tracking3d(low,  self.image_rot_zx, self.image_center, self.field_of_view)
        high_t = vessel_cs_to_tracking3d(high, self.image_rot_zx, self.image_center, self.field_of_view)
        return gym.spaces.Box(low=np.minimum(low_t, high_t), high=np.maximum(low_t, high_t))


# ── Mesh-raster (IDENTICAL to run_coronary.py) ────────────────────────────────

def _coords_to_px(coords_2d: np.ndarray, fluoro: PillowTracking) -> np.ndarray:
    offset     = np.asarray(fluoro._tracking_offset, dtype=np.float64)
    img_offset = np.asarray(fluoro._image_offset,    dtype=np.float64)
    H          = fluoro.image_size[1]
    px = (coords_2d + offset) * fluoro._tracking_to_image_factor + img_offset
    px = px.copy()
    px[:, 1] = -px[:, 1] + H
    return np.round(px).astype(np.int32)


def precompute_binary_mask(fluoro: PillowTracking, vtp_path: Path) -> np.ndarray:
    t0   = time.perf_counter()
    mesh = pv.read(str(vtp_path)).triangulate()
    verts  = np.asarray(mesh.points, dtype=np.float64)
    v3d    = vessel_cs_to_tracking3d(verts, fluoro.image_rot_zx,
                                     fluoro.image_center, fluoro.field_of_view)
    v2d    = tracking3d_to_2d(v3d)
    vpx    = _coords_to_px(v2d, fluoro)
    raw    = np.asarray(mesh.faces, dtype=np.int32)
    faces  = raw.reshape(-1, 4)[:, 1:]

    mask = Image.new("L", fluoro.image_size, 255)
    draw = ImageDraw.Draw(mask)
    for tri in faces:
        pts = [(int(vpx[i, 0]), int(vpx[i, 1])) for i in tri]
        draw.polygon(pts, fill=0)

    arr      = np.asarray(mask, dtype=np.uint8)
    n_vessel = int(np.sum(arr == 0))
    print(f"  Vessel mask: {len(faces)} triangles -> {n_vessel} px "
          f"({100*n_vessel/arr.size:.1f}%)  {time.perf_counter()-t0:.2f}s")
    return arr


def render_frame(fluoro: PillowTracking, binary_mask: np.ndarray, mode: str) -> np.ndarray:
    if mode == "wire_only":
        return fluoro.image
    fill = VESSEL_FILL[mode]
    vessel_arr = np.where(binary_mask == 0, fill, BG_FILL).astype(np.uint8)
    base = Image.fromarray(vessel_arr)
    draw = ImageDraw.Draw(base)
    for tracking_2d in fluoro.device_trackings2d:
        if len(tracking_2d) < 2:
            continue
        wire_px = fluoro._coord_transform_tracking_to_image(tracking_2d)
        w = max(2, int(fluoro._wire_diameter * fluoro._tracking_to_image_factor))
        draw.line(wire_px, fill=WIRE_FILL_BY_MODE.get(mode, 40), width=w)
    noise = Image.effect_noise(size=fluoro.image_size, sigma=5)
    return np.asarray(ImageChops.darker(base, noise), dtype=np.uint8)


# ── Environment builder (ASOCA-specific anatomy loading) ──────────────────────

def build_env(case_n: int, mesh_path: Path, n_steps: int, max_it: int = 2000):
    """
    Build SOFA env for ASOCA Normal_{case_n}.
    Returns (env, sim, fluoro, branch_kds, mid_lad).
    mid_lad is in SOFA world-space (same as sim.dof_positions[0]).
    """
    branches, ins_pt, ins_dir = asoca_left_coronary_branches(case_n)
    lad     = next(b for b in branches if b.name == "lad")
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
    sim    = CoronaryBeamAdapter(friction=0.001, dt_simulation=0.001, max_it=max_it)
    fluoro = PillowTracking(image_size=IMAGE_SIZE, simulation=sim, vessel_tree=vt,
                            wire_diameter=0.89, image_frequency=7.5,
                            image_rot_zx=IMAGE_ROT_ZX)
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
    rew    = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env    = eve.Env(
        intervention=intvn, observation=obs, reward=rew,
        terminal=eve.terminal.TargetReached(intervention=intvn),
        truncation=eve.truncation.MaxSteps(n_steps),
        visualisation=None, start=start, pathfinder=pf)

    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return env, sim, fluoro, branch_kds, mid_lad


# ── Safe reset (IDENTICAL to run_coronary.py) ─────────────────────────────────

def safe_reset(env, sim: CoronaryBeamAdapter, ep: int, seed: int):
    for attempt in range(1, MAX_RESET_TRIES + 1):
        if (hasattr(sim, 'reset_devices') and
                getattr(sim, '_instruments_combined', None) is not None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)

        xtip = float(sim.inserted_lengths[0])
        tip  = np.array(sim.dof_positions[0], dtype=float)
        if np.any(np.isnan(tip)) or np.any(np.isinf(tip)):
            print(f"    [RESET] attempt {attempt}: NaN/Inf tip -- retrying"); continue
        if xtip > XTIP_HEALTHY_MAX:
            print(f"    [RESET] attempt {attempt}: xtip={xtip:.2f}mm too high -- retrying"); continue

        env.step(np.array([[0.0, 0.0]]))
        if np.any(np.isnan(np.array(sim.dof_positions[0], dtype=float))):
            print(f"    [RESET] attempt {attempt}: zero-action NaN -- retrying"); continue

        if (hasattr(sim, 'reset_devices') and
                getattr(sim, '_instruments_combined', None) is not None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        tip_f  = np.array(sim.dof_positions[0], dtype=float)
        xtip_f = float(sim.inserted_lengths[0])
        print(f"    [RESET] OK (attempt {attempt}): xtip={xtip_f:.2f}mm  "
              f"tip={[round(x,1) for x in tip_f]}")
        return True, tip_f, xtip_f, attempt

    print(f"    [RESET] FAILED after {MAX_RESET_TRIES} attempts")
    return False, None, None, MAX_RESET_TRIES


# ── Frame utilities (IDENTICAL to run_coronary.py) ────────────────────────────

def frame_to_png_b64(frame: np.ndarray) -> str:
    img = Image.fromarray(frame, mode="L") if frame.ndim == 2 else \
          Image.fromarray(np.flipud(frame), mode="RGB")
    buf = BytesIO(); img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def save_frame_png(frame: np.ndarray, path: Path) -> None:
    img = Image.fromarray(frame, mode="L") if frame.ndim == 2 else \
          Image.fromarray(np.flipud(frame), mode="RGB")
    img.save(str(path))


# ── VLM call ──────────────────────────────────────────────────────────────────

def call_vlm(client, b64_frame: str, retractions_remaining: int,
             no_progress: int, current_dist: float, dist_trend: str,
             system_prompt: str, gate_mm: float) -> str:
    response = client.messages.create(
        model=MODEL, max_tokens=600, system=system_prompt,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/png",
                                         "data": b64_frame}},
            {"type": "text", "text": user_msg(retractions_remaining, no_progress,
                                              current_dist, dist_trend, gate_mm)},
        ]}],
    )
    return response.content[0].text


# ── Action parsing (IDENTICAL to run_coronary.py) ─────────────────────────────

def parse_action(raw_text: str):
    last_close = raw_text.rfind("}")
    if last_close == -1: return None, False
    depth = 0; first_open = -1
    for i in range(last_close, -1, -1):
        if raw_text[i] == "}": depth += 1
        elif raw_text[i] == "{":
            depth -= 1
            if depth == 0: first_open = i; break
    if first_open == -1: return None, False
    try:
        data   = json.loads(raw_text[first_open : last_close + 1])
        act    = data.get("action", {})
        trans  = float(np.clip(float(act.get("translation", 0.0)), -TRANS_LIMIT, TRANS_LIMIT))
        rot    = float(np.clip(float(act.get("rotation",    0.0)), -ROT_LIMIT,   ROT_LIMIT))
        intent = str(data.get("intended_direction", "")).lower().strip()
        if intent not in VALID_INTENTS: intent = "unknown"
        return {
            "tip_location_statement":    str(data.get("tip_location_statement",    "")),
            "target_location_statement": str(data.get("target_location_statement", "")),
            "intended_direction":        intent,
            "safety_rationale":          str(data.get("safety_rationale",          "")),
            "translation": trans, "rotation": rot,
        }, True
    except Exception:
        return None, False


# ── Ground-truth helpers (IDENTICAL) ─────────────────────────────────────────

def gt_tip(sim):    return np.array(sim.dof_positions[0], dtype=float)
def dist3d(a, b):   return float(np.linalg.norm(np.array(a) - np.array(b)))


# ── Scoring (IDENTICAL to run_coronary.py) ────────────────────────────────────

def score_action_consistent(intended, translation, rotation):
    if intended == "advance":    return bool(translation > 0)
    if intended == "retract":    return bool(translation < 0)
    if intended == "rotate_cw":  return bool(rotation > 0)
    if intended == "rotate_ccw": return bool(rotation < 0)
    if intended == "hold":       return bool(abs(translation) < 1.0 and abs(rotation) < 0.1)
    return None


def score_intent_appropriate(intended, tip_obs, tip_post, target_pos):
    if intended in ("rotate_cw", "rotate_ccw"): return None
    if intended == "hold": return True
    movement  = np.array(tip_post)   - np.array(tip_obs)
    to_target = np.array(target_pos) - np.array(tip_obs)
    d = float(np.linalg.norm(to_target))
    if d < 1e-6 or float(np.linalg.norm(movement)) < 0.01: return None
    return bool(float(np.dot(movement, to_target / d)) > 0)


def score_perception_tip(stmt, tip_obs, target_pos):
    text = stmt.lower(); to_t = np.array(target_pos) - np.array(tip_obs)
    d = float(np.linalg.norm(to_t))
    if any(p in text for p in ("at target", "reached target", "on target")):      return bool(d < 5.0)
    if any(p in text for p in ("very close to target", "almost at target")):      return bool(d < 15.0)
    if any(p in text for p in ("far from target", "long way from target")):       return bool(d > 50.0)
    dx, dy = float(to_t[0]), float(to_t[1])
    if "above the target" in text:    return bool(dy < 0)
    if "below the target" in text:    return bool(dy > 0)
    if "left of the target"  in text: return bool(dx > 0)
    if "right of the target" in text: return bool(dx < 0)
    return None


def score_perception_target(stmt, tip_obs, target_pos):
    text = stmt.lower(); to_t = np.array(target_pos) - np.array(tip_obs)
    d = float(np.linalg.norm(to_t))
    if any(p in text for p in ("near tip", "near the wire", "close to wire")): return bool(d < 15.0)
    if any(p in text for p in ("far from tip", "far from the wire")):          return bool(d > 50.0)
    dx, dy = float(to_t[0]), float(to_t[1])
    if any(p in text for p in ("above the wire", "above the tip")): return bool(dy > 0)
    if any(p in text for p in ("below the wire", "below the tip")): return bool(dy < 0)
    if "to the left"  in text: return bool(dx < 0)
    if "to the right" in text: return bool(dx > 0)
    return None


def check_hallucination(tip_stmt, target_stmt, safety):
    combined = (tip_stmt + " " + target_stmt + " " + safety).lower()
    return any(kw in combined for kw in HALLUCINATION_KEYWORDS)


def _blank():
    return {"tip_location_statement":    "[PARSE FAIL]",
            "target_location_statement": "[PARSE FAIL]",
            "intended_direction": "unknown", "safety_rationale": "",
            "translation": 0.0, "rotation": 0.0}


# ── Run arm ────────────────────────────────────────────────────────────────────

def run_arm(client, env, sim: CoronaryBeamAdapter, fluoro: PillowTracking,
            binary_mask: np.ndarray, mode: str, branch_kds: dict,
            mid_lad: np.ndarray, system_prompt: str, gate_mm: float,
            anatomy_name: str,
            arm_dir: Path, n_episodes: int, n_steps: int, seeds) -> dict:
    arm_dir.mkdir(parents=True, exist_ok=True)
    tf_path = arm_dir / "trace.jsonl"

    stats = dict(
        arm=f"coronary_{mode}", mode=mode,
        episodes=n_episodes, n_steps_limit=n_steps,
        steps_per_episode=[], target_reached_count=0, parse_failures=0,
        api_errors=0, retraction_steps=0, budget_enforcements=0,
        rotation_steps=0, gate_suppressions=0, hallucination_count=0,
        ep_mean_dists=[], failed_resets=0, total_steps=0, scored_steps=0,
        action_consistent_count=0, action_consistent_scored=0,
        intent_appropriate_count=0, intent_appropriate_scored=0,
        perception_tip_ok_count=0, perception_tip_scored=0,
        perception_target_ok_count=0, perception_target_scored=0,
        outcome_reduced_count=0,
    )

    with open(tf_path, "w", encoding="utf-8") as tf:
        for ep in range(1, n_episodes + 1):
            seed = seeds[ep - 1]
            print(f"\n  [{mode.upper()}] Ep {ep}/{n_episodes}  seed={seed}")

            try:
                reset_ok, _, xtip_start, reset_attempts = safe_reset(env, sim, ep, seed)
            except Exception as reset_exc:
                stats["failed_resets"] += 1
                stats["steps_per_episode"].append(0)
                stats["ep_mean_dists"].append(float("nan"))
                print(f"  [{mode.upper()}] Ep {ep} SKIPPED -- reset raised: {reset_exc}"); continue
            if not reset_ok:
                stats["failed_resets"] += 1
                stats["steps_per_episode"].append(0)
                stats["ep_mean_dists"].append(float("nan"))
                print(f"  [{mode.upper()}] Ep {ep} SKIPPED -- reset failed"); continue

            ep_steps = 0; ep_success = False; ep_dists = []
            ep_target = mid_lad
            retractions_used = 0
            consecutive_no_progress = 0
            dist_history = []

            for step in range(1, n_steps + 1):
                tip_obs        = gt_tip(sim)
                dist_obs       = dist3d(tip_obs, ep_target)
                tip_branch_obs = min(branch_kds,
                                     key=lambda n: branch_kds[n].query(tip_obs)[0])

                trend      = _dist_trend(dist_history, dist_obs)
                gate_active = _gate_active(dist_obs, trend, gate_mm)

                frame    = render_frame(fluoro, binary_mask, mode)
                path_img = arm_dir / f"ep{ep:02d}_step{step:02d}.png"
                save_frame_png(frame, path_img)

                b64_frame = frame_to_png_b64(frame)
                retractions_remaining = RETRACTION_BUDGET - retractions_used

                api_ok = True; raw_text = ""
                try:
                    raw_text = call_vlm(client, b64_frame,
                                        retractions_remaining, consecutive_no_progress,
                                        dist_obs, trend, system_prompt, gate_mm)
                except Exception as exc:
                    raw_text = f"[API ERROR] {exc}"; api_ok = False
                    stats["api_errors"] += 1
                    print(f"    ep{ep:02d} s{step:02d} | API ERROR: {exc}")

                parsed, parse_ok = parse_action(raw_text)
                budget_enforced     = False
                gate_suppressed_rot = False

                if not parse_ok:
                    stats["parse_failures"] += 1
                    action_arr = np.array([[0.0, 0.0]]); parsed = _blank()
                    if api_ok:
                        print(f"    ep{ep:02d} s{step:02d} | PARSE FAIL  {raw_text[:60]!r}")
                else:
                    if parsed["translation"] < 0 and retractions_remaining <= 0:
                        parsed["translation"] = 0.0
                        if abs(parsed["rotation"]) < 0.05: parsed["rotation"] = 0.0
                        parsed["intended_direction"] = "hold"
                        budget_enforced = True; stats["budget_enforcements"] += 1
                        print(f"    ep{ep:02d} s{step:02d} | BUDGET ENFORCED (retract->hold)")

                    elif gate_active and parsed["intended_direction"] in ("rotate_cw", "rotate_ccw"):
                        parsed["rotation"]            = 0.0
                        parsed["translation"]         = PROXIMITY_GATE_ADV_DEFAULT
                        parsed["intended_direction"]  = "advance"
                        gate_suppressed_rot = True; stats["gate_suppressions"] += 1
                        print(f"    ep{ep:02d} s{step:02d} | GATE FIRED "
                              f"(rot->+{PROXIMITY_GATE_ADV_DEFAULT:.0f}mm)  "
                              f"dist={dist_obs:.1f}mm trend={trend}")

                    action_arr = np.array([[parsed["translation"], parsed["rotation"]]])
                    if parsed["translation"] < 0:
                        retractions_used += 1; stats["retraction_steps"] += 1
                    if parsed["intended_direction"] in ("rotate_cw", "rotate_ccw"):
                        stats["rotation_steps"] += 1

                _, reward, terminal, truncation, _ = env.step(action_arr)

                tip_post = gt_tip(sim)
                if np.any(np.isnan(tip_post)):
                    print(f"    ep{ep:02d} s{step:02d} | NaN TIP -- ending episode"); break

                dist_post  = dist3d(tip_post, ep_target)
                dist_delta = dist_post - dist_obs
                dist_history.append(dist_post)
                ep_dists.append(dist_post)
                stats["total_steps"] += 1
                if dist_delta < 0: stats["outcome_reduced_count"] += 1

                if parse_ok and parsed["intended_direction"] == "advance":
                    consecutive_no_progress = (consecutive_no_progress + 1) if dist_delta >= 0 else 0
                else:
                    consecutive_no_progress = 0

                ac = ia = pt = pg = hall = None
                if parse_ok:
                    stats["scored_steps"] += 1
                    intended = parsed["intended_direction"]
                    trans = parsed["translation"]; rot = parsed["rotation"]
                    ac   = score_action_consistent(intended, trans, rot)
                    ia   = score_intent_appropriate(intended, tip_obs, tip_post, ep_target)
                    pt   = score_perception_tip(parsed["tip_location_statement"],
                                                tip_obs, ep_target)
                    pg   = score_perception_target(parsed["target_location_statement"],
                                                   tip_obs, ep_target)
                    hall = check_hallucination(parsed["tip_location_statement"],
                                               parsed["target_location_statement"],
                                               parsed["safety_rationale"])
                    if ac is not None:
                        stats["action_consistent_scored"] += 1
                        if ac: stats["action_consistent_count"] += 1
                    if ia is not None:
                        stats["intent_appropriate_scored"] += 1
                        if ia: stats["intent_appropriate_count"] += 1
                    if pt is not None:
                        stats["perception_tip_scored"] += 1
                        if pt: stats["perception_tip_ok_count"] += 1
                    if pg is not None:
                        stats["perception_target_scored"] += 1
                        if pg: stats["perception_target_ok_count"] += 1
                    if hall: stats["hallucination_count"] += 1

                    ac_tag   = "OK" if ac else ("INCON" if ac is False else "?")
                    gate_tag = " [GATE]" if gate_suppressed_rot else ""
                    rot_tag  = (f" [ROT np={consecutive_no_progress}]"
                                if intended in ("rotate_cw", "rotate_ccw") else "")
                    ret_tag  = (f" [RET {retractions_used}/{RETRACTION_BUDGET}]"
                                if parsed["translation"] < 0 else "")
                    print(f"    ep{ep:02d} s{step:02d} | T={trans:+6.1f} R={rot:+5.2f} | "
                          f"intent={intended:10s} | ac={ac_tag} | "
                          f"d={dist_post:6.1f}mm D={dist_delta:+5.1f} "
                          f"trend={trend:11s}{gate_tag}{ret_tag}{rot_tag}")

                row = dict(
                    arm=f"coronary_{mode}", fluoro_mode=mode,
                    anatomy=anatomy_name,
                    episode=ep, step=step, seed=seed,
                    raw_vlm_text=raw_text,
                    tip_location_statement=parsed["tip_location_statement"],
                    target_location_statement=parsed["target_location_statement"],
                    intended_direction=parsed["intended_direction"],
                    safety_rationale=parsed["safety_rationale"],
                    parsed_action={"translation": parsed["translation"],
                                   "rotation":    parsed["rotation"]},
                    gt_tip_obs=tip_obs.tolist(), gt_tip_pos=tip_post.tolist(),
                    gt_target_pos=ep_target.tolist(),
                    tip_branch_obs=tip_branch_obs,
                    tip_target_dist=dist_post, dist_delta=dist_delta,
                    dist_obs_at_call=dist_obs, dist_trend=trend,
                    gate_active=gate_active, gate_suppressed_rotation=gate_suppressed_rot,
                    retractions_used_so_far=retractions_used,
                    consecutive_no_progress_advances=consecutive_no_progress,
                    budget_enforced=budget_enforced,
                    perception_tip_ok=pt, perception_target_ok=pg,
                    intent_appropriate=ia, action_consistent=ac,
                    outcome_reduced_dist=bool(dist_delta < 0),
                    hallucination_flag=hall,
                    raw_reward=float(reward), terminal=bool(terminal),
                    truncation=bool(truncation), parse_ok=parse_ok, api_ok=api_ok,
                    xtip_at_reset=xtip_start, reset_attempts=reset_attempts,
                    frame_path=str(path_img),
                )
                tf.write(json.dumps(row) + "\n"); tf.flush()

                ep_steps = step
                if terminal:
                    ep_success = True; stats["target_reached_count"] += 1
                    print(f"    >>> TARGET REACHED  step={step}  dist={dist_post:.1f}mm"); break
                if truncation:
                    print(f"    >>> Truncated  final_dist={dist_post:.1f}mm"); break

            stats["steps_per_episode"].append(ep_steps)
            ep_mean = float(np.mean(ep_dists)) if ep_dists else float("nan")
            stats["ep_mean_dists"].append(ep_mean)
            print(f"  [{mode.upper()}] Ep {ep} done: {ep_steps} steps | "
                  f"success={ep_success} | mean_dist={ep_mean:.1f}mm | "
                  f"ret={retractions_used}/{RETRACTION_BUDGET} | "
                  f"gate_fires={stats['gate_suppressions']}")

    return stats


# ── Summary ────────────────────────────────────────────────────────────────────

def pct(n, d): return f"{100*n/d:.1f}%" if d else "N/A"


def write_summary(stats: dict, run_dir: Path, mode: str,
                  anatomy_name: str, gate_mm: float) -> Path:
    ts = stats["total_steps"]; ss = stats["scored_steps"]
    lines = [
        "=" * 68,
        f"CORONARY VLM OPERATOR -- anatomy: {anatomy_name}  mode: {mode.upper()}",
        f"Run dir  : {run_dir}",
        f"Model    : {MODEL}",
        f"Scene    : {anatomy_name}, clipped mesh, AP Cranial 40 deg",
        f"Target   : mid-LAD (BranchIndex, threshold=5mm)",
        f"Budget   : {RETRACTION_BUDGET} retractions per episode",
        f"Gate     : suppress rotation when dist < {gate_mm:.0f}mm AND decreasing",
        "=" * 68,
        "FRAMING: Each 'episode' is a repetition of a single fixed coronary scenario.",
        "  Anatomy, target, and start are IDENTICAL across all episodes.",
        "  Observed variance reflects VLM sampling stochasticity, NOT anatomical variation.",
        "  The fixed scenario enables clean causal attribution.",
        "=" * 68, "",
        f"  Episodes run          : {stats['episodes']}",
        f"  Failed resets         : {stats['failed_resets']}",
        f"  Target reached        : {stats['target_reached_count']} / {stats['episodes']}",
        f"  Steps total / scored  : {ts} / {ss}  "
        f"(parse failures: {stats['parse_failures']})",
        f"  API errors            : {stats['api_errors']}",
        f"  Retraction steps      : {stats['retraction_steps']}  "
        f"(budget enforcements: {stats['budget_enforcements']})",
        f"  Rotation steps        : {stats['rotation_steps']}  "
        f"({pct(stats['rotation_steps'], ts)})",
        f"  Gate suppressions     : {stats['gate_suppressions']}",
        f"  Hallucination flags   : {stats['hallucination_count']}",
        "",
        f"  Perception tip OK     : {pct(stats['perception_tip_ok_count'], stats['perception_tip_scored'])}"
        f"  ({stats['perception_tip_ok_count']}/{stats['perception_tip_scored']} verifiable)",
        f"  Perception target OK  : {pct(stats['perception_target_ok_count'], stats['perception_target_scored'])}"
        f"  ({stats['perception_target_ok_count']}/{stats['perception_target_scored']} verifiable)",
        f"  Intent appropriate    : {pct(stats['intent_appropriate_count'], stats['intent_appropriate_scored'])}"
        f"  ({stats['intent_appropriate_count']}/{stats['intent_appropriate_scored']} assessable)",
        f"  Action consistent *** : {pct(stats['action_consistent_count'], stats['action_consistent_scored'])}"
        f"  ({stats['action_consistent_count']}/{stats['action_consistent_scored']} assessable)",
        f"  Outcome reduced dist  : {pct(stats['outcome_reduced_count'], ts)}"
        f"  ({stats['outcome_reduced_count']}/{ts})",
        "",
        "  Per-episode mean tip->target dist (mm):",
    ] + [
        f"    ep{i+1:02d} : {d:6.1f} mm" for i, d in enumerate(stats["ep_mean_dists"])
    ] + ["", "=" * 68]

    path = run_dir / "summary.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anatomy", type=str, required=True,
                        choices=["normal12", "normal5"],
                        help="ASOCA anatomy to use")
    parser.add_argument("--mode",    type=str,
                        choices=["wire_only", "overlay", "contrast", "overlay_bright"],
                        default="wire_only")
    parser.add_argument("--episodes", type=int, default=25)
    parser.add_argument("--steps",    type=int, default=None,
                        help="steps per episode (default: per-anatomy n_steps in ANATOMY_PARAMS)")
    parser.add_argument("--out",      type=str, default=None)
    parser.add_argument("--model",    type=str, default=None)
    parser.add_argument("--episode-offset", type=int, default=0,
                        help="Skip first N seeds (resume after crash)")
    args = parser.parse_args()

    if args.model:
        global MODEL
        MODEL = args.model

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key: sys.exit("ERROR: ANTHROPIC_API_KEY not set.")

    params = ANATOMY_PARAMS[args.anatomy]
    system_prompt = make_system_prompt(params)
    gate_mm = params["proximity_gate_mm"]
    anatomy_name = f"asoca_{args.anatomy}"

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    if args.out:
        run_dir = Path(args.out)
    else:
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = Path(r"D:\steve\pilot\runs") / f"{anatomy_name}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    arm_dir = run_dir / f"arm_{anatomy_name}_{args.mode}"

    n_steps = args.steps if args.steps is not None else params["n_steps"]
    seeds = params["seeds"][args.episode_offset : args.episode_offset + args.episodes]
    print(f"Run dir  : {run_dir}")
    print(f"Anatomy  : {anatomy_name}  (ASOCA Normal_{params['case_n']})")
    print(f"Model    : {MODEL}")
    print(f"Mode     : {args.mode}")
    print(f"Plan     : {args.episodes} episodes x {n_steps} steps")
    print(f"Budget   : {RETRACTION_BUDGET} retractions/episode")
    print(f"Gate     : suppress rotation when dist < {gate_mm:.0f}mm AND decreasing")
    print(f"Seeds    : {seeds}\n")

    print("Building ASOCA environment (first SOFA init ~30s) ...")
    env, sim, fluoro, branch_kds, mid_lad = build_env(
        params["case_n"], params["mesh_path"], n_steps, params["max_it"])

    print("env.reset() to initialise pixel transform ...")
    env.reset()

    print("Precomputing vessel mask ...")
    binary_mask = precompute_binary_mask(fluoro, params["vtp_path"])

    try:
        print("\n" + "=" * 68)
        print(f"CORONARY VLM OPERATOR  anatomy={anatomy_name}  mode={args.mode.upper()}")
        print("=" * 68)
        stats = run_arm(client, env, sim, fluoro, binary_mask, args.mode, branch_kds,
                        mid_lad, system_prompt, gate_mm, anatomy_name,
                        arm_dir, args.episodes, n_steps, seeds)
    except KeyboardInterrupt:
        print("\nInterrupted."); env.close(); sys.exit(1)

    env.close()
    summary_path = write_summary(stats, run_dir, args.mode, anatomy_name, gate_mm)

    print(f"\n{'='*68}\nRun complete.")
    print(f"  summary  : {summary_path}")
    print(f"  trace    : {arm_dir / 'trace.jsonl'}")
    print(f"  Targets  : {stats['target_reached_count']} / {stats['episodes']}")
    print(f"  Ret steps: {stats['retraction_steps']}  "
          f"({stats['budget_enforcements']} enforced)")
    print(f"  Rot steps: {stats['rotation_steps']}")
    print(f"  Gate fires: {stats['gate_suppressions']}")
    print("=" * 68)


if __name__ == "__main__":
    main()
