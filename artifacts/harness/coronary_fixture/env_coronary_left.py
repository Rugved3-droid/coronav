"""
Left coronary fixture environment — Step 3.

Vessel tree  : FromMesh over clipped_left.obj (left main + LAD + LCX + sub-branches)
Insertion    : left main ostium, point + direction from centerline (source-agnostic)
Target       : BranchIndex at mid-LAD-proper (halfway along LAD after the LM bifurcation)
Device/Sim   : unchanged from function_check.py template
Reward/Obs   : unchanged from function_check.py template

No aortic-root assumptions; insertion is a bare (point, direction) pair so ASOCA
(coronary stub, no aortic root) drops into the same slots.

Plausibility assertion: mesh bbox must be in the 15-200 mm coronary range.
"""

import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh

from coronary_fixture.pth_centerlines import left_coronary_branches
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

# ── Paths ────────────────────────────────────────────────────────────────────
MODEL_DIR  = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR   = os.path.join(MODEL_DIR, "Paths")
MESH_PATH  = os.path.join(HERE, "clipped_left.obj")

# Approximate coronary branch radius used by calc_branching for junction detection.
# Must be >= max junction-start distance (~1.5 mm observed in this dataset).
APPROX_BRANCH_RADIUS_MM = 2.5

# mid-LAD target threshold (success radius, mm)
TARGET_THRESHOLD_MM = 5.0


def _assert_coronary_bbox(vessel_tree: FromMesh) -> None:
    """Loud assertion: bbox must look like a coronary tree in mm."""
    cs = vessel_tree.coordinate_space
    extents = cs.high - cs.low
    max_ext = float(extents.max())
    assert 15 < max_ext < 200, (
        f"UNITS ERROR: coordinate_space max extent = {max_ext:.1f} mm. "
        f"Expected 15-200 mm for a coronary tree. Check mesh scale."
    )


def build_coronary_env(seed: int = 42, max_it: int = 2000):
    """
    Build and return the full Eve environment for the left coronary fixture.

    Parameters
    ----------
    seed   : RNG seed for device insertion rotation.
    max_it : LCPConstraintSolver maxIt (see step4_sweep.py for empirical floor).

    Returns
    -------
    env        : eve.Env
    vessel_tree: FromMesh  (for inspection)
    mid_lad_3d : (3,) float32  target coordinates in vessel-CS mm
    """
    import time as _t, sys as _s
    def _ts(msg): print(f"  [build {_t.strftime('%H:%M:%S')}] {msg}", flush=True); _s.stdout.flush()

    # ── 1. Load centerline and reconstruct topology ──────────────────────────
    _ts("left_coronary_branches ...")
    branches, insertion_pt, insertion_dir = left_coronary_branches(
        PATH_DIR, junction_radius_mm=3.0
    )
    _ts(f"  -> {len(branches)} branches")
    # lad branch is always index 1 (trunk=0, lad-proper=1 per build_branch_tree)
    lad_branch = next(b for b in branches if b.name == "lad")
    mid_lad_idx = len(lad_branch.coordinates) // 2
    mid_lad_3d  = lad_branch.coordinates[mid_lad_idx]

    # ── 2. Vessel tree (FromMesh, no scaling — mesh is already in mm) ────────
    assert os.path.isfile(MESH_PATH), f"Clipped mesh not found: {MESH_PATH}\nRun: python coronary_fixture/clip_left_coronary.py"

    _ts("FromMesh() ...")
    vessel_tree = FromMesh(
        mesh=MESH_PATH,
        insertion_position=tuple(insertion_pt.tolist()),
        insertion_direction=tuple(insertion_dir.tolist()),
        branch_list=branches,
        approx_branch_radii=APPROX_BRANCH_RADIUS_MM,
        # No scaling — mesh is already in mm. VMR's x10 was applied during clip.
        scaling_xyz=None,
        rotation_yzx_deg=None,
        rotate_branches=False,
        rotate_ip=False,
    )
    _ts("FromMesh() done")
    _assert_coronary_bbox(vessel_tree)

    # ── 3. Device / Simulation ────────────────────────────────────────────────
    # Straight wire for bring-up: no J-tip curl, cleanest probe of collision.
    # JShaped(tip_radius~1.5mm) is Step 5 — only once straight-wire containment is proven.
    _ts("Straight() + CoronaryBeamAdapter() ...")
    device = eve.intervention.device.Straight()
    simulation = CoronaryBeamAdapter(friction=0.001, max_it=max_it)
    _ts("device+sim done")

    # ── 4. Fluoroscopy — same angles as function_check template ──────────────
    _ts("TrackingOnly() ...")
    fluoroscopy = TrackingOnly(
        simulation=simulation,
        vessel_tree=vessel_tree,
        image_frequency=7.5,
        image_rot_zx=[20, 5],
    )
    _ts("fluoroscopy done")

    # ── 5. Target: mid-LAD-proper (fixed, not random) ────────────────────────
    _ts("BranchIndex() ...")
    target = BranchIndex(
        vessel_tree=vessel_tree,
        fluoroscopy=fluoroscopy,
        threshold=TARGET_THRESHOLD_MM,
        branch="lad",
        idx=mid_lad_idx,
    )
    _ts("target done")

    # ── 6. Intervention ───────────────────────────────────────────────────────
    _ts("MonoPlaneStatic() ...")
    intervention = eve.intervention.MonoPlaneStatic(
        vessel_tree=vessel_tree,
        devices=[device],
        simulation=simulation,
        fluoroscopy=fluoroscopy,
        target=target,
    )
    _ts("intervention done")

    # ── 7. Start / Pathfinder — unchanged from template ──────────────────────
    _ts("MaxDeviceLength+BruteForceBFS() ...")
    start      = eve.start.MaxDeviceLength(intervention=intervention, max_length=500)
    pathfinder = eve.pathfinder.BruteForceBFS(intervention=intervention)
    _ts("start+pathfinder done")

    # ── 8. Observation — unchanged from template ──────────────────────────────
    _ts("observations() ...")
    position = eve.observation.Tracking2D(intervention=intervention, n_points=5)
    position = eve.observation.wrapper.NormalizeTracking2DEpisode(position, intervention)
    target_obs = eve.observation.Target2D(intervention=intervention)
    target_obs = eve.observation.wrapper.NormalizeTracking2DEpisode(target_obs, intervention)
    rotation = eve.observation.Rotations(intervention=intervention)
    state = eve.observation.ObsDict(
        {"position": position, "target": target_obs, "rotation": rotation}
    )
    _ts("observations done")

    # ── 9. Reward / Terminal / Truncation — unchanged from template ───────────
    target_reward = eve.reward.TargetReached(intervention=intervention, factor=1.0)
    path_delta    = eve.reward.PathLengthDelta(pathfinder=pathfinder, factor=0.01)
    reward        = eve.reward.Combination([target_reward, path_delta])

    target_reached = eve.terminal.TargetReached(intervention=intervention)
    max_steps      = eve.truncation.MaxSteps(200)

    # ── 10. Env ───────────────────────────────────────────────────────────────
    _ts("eve.Env() ...")
    env = eve.Env(
        intervention=intervention,
        observation=state,
        reward=reward,
        terminal=target_reached,
        truncation=max_steps,
        visualisation=None,
        start=start,
        pathfinder=pathfinder,
    )
    _ts("eve.Env() done — build_coronary_env returning")

    return env, vessel_tree, mid_lad_3d


# ── Step-3 verification (run this before Step 4) ─────────────────────────────
if __name__ == "__main__":
    print("Building coronary left env ...")
    env, vt, mid_lad = build_coronary_env(seed=42)

    print("\n=== VesselTree ===")
    ip  = vt.insertion.position
    idir = vt.insertion.direction
    print(f"  Insertion point     : ({ip[0]:.2f}, {ip[1]:.2f}, {ip[2]:.2f}) mm")
    print(f"  Insertion direction : ({idir[0]:.3f}, {idir[1]:.3f}, {idir[2]:.3f})")
    cs = vt.coordinate_space
    ext = cs.high - cs.low
    print(f"  Coord-space extents : {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm")

    print(f"\n  Branches ({len(vt.branches)}):")
    for b in vt.branches:
        l = float(np.sum(np.linalg.norm(np.diff(b.coordinates, axis=0), axis=1)))
        print(f"    {b.name:<20} {len(b.coordinates):>4} pts  {l:>8.1f} mm")

    print(f"\n  Branching points: {len(vt.branching_points)}")
    for bp in vt.branching_points:
        names = [b.name for b in bp.connections]
        print(f"    r={bp.radius:.1f}mm @ ({bp.coordinates[0]:.1f},{bp.coordinates[1]:.1f},{bp.coordinates[2]:.1f})  connects={names}")

    print(f"\n=== Target ===")
    print(f"  Mid-LAD-proper : ({mid_lad[0]:.2f}, {mid_lad[1]:.2f}, {mid_lad[2]:.2f}) mm")
    print(f"  (lad branch index {len(vt['lad'].coordinates)//2} of {len(vt['lad'].coordinates)})")

    print("\n=== env.reset() ===")
    obs = env.reset()
    print("  Reset OK")
    print(f"  Pathfinder path length (reset): "
          f"{env.pathfinder.path_length:.1f} mm")

    print("\n=== Step x3 ===")
    for i in range(3):
        obs, r, terminal, truncation, info = env.step((35.0, 1.0))
        print(f"  step {i+1}: reward={r:.4f}  terminal={terminal}  truncation={truncation}")

    env.close()
    print("\nStep 3 PASS -- ready for Step 4.")
