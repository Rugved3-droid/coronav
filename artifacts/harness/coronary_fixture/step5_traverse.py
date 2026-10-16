"""
Step 5 — Full coronary traverse with JShaped device.

Straight was confirmed (RUN 6) as the sole NaN cause: zero initial curvature
gives 0/0 in the controller's direction normalization. JShaped's built-in curve
always provides a well-defined tangent direction.

Device: JShaped(tip_radius=1.5mm, tip_angle=0.2*pi)
  tip_radius=1.5mm fits a 3-4mm lumen without jamming at the ostium.
  Everything else (mesh, solver, IncrSAP, insertion, target) unchanged.

Reports:
  - NaN / segfault status
  - Velocity profile: jump per step vs 4.67mm free-space baseline
  - Per-step containment: tip-to-CL vs local vessel radius
  - Path length vs pathfinder optimal

Run:
    python coronary_fixture/step5_traverse.py [--max-steps N]
"""

import os
import sys
import math
import argparse
from collections import Counter

import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh

from coronary_fixture.pth_centerlines import left_coronary_branches
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

MODEL_DIR = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR  = os.path.join(MODEL_DIR, "Paths")
MESH_PATH = os.path.join(HERE, "clipped_left.obj")
VTP_PATH  = os.path.join(HERE, "clipped_left.vtp")

APPROX_BRANCH_RADIUS_MM = 2.5
TARGET_THRESHOLD_MM     = 5.0
TUNNEL_THRESH_MM        = 3.5
JUMP_THRESH_MM          = 5.0
NEG_REWARD_THRESH       = -0.1
FREE_SPACE_JUMP_MM      = 35.0 / 7.5   # 4.667 mm/step at 35mm/s, 7.5Hz

BRANCH_RADII = {
    "left_main": 3.0, "lad": 2.0, "lcx": 1.8,
    "lad_b1": 1.4, "lad_b2": 1.0, "lad_b3": 1.2, "lad_b3_b1": 0.8,
    "lad_b4": 0.9, "lad_b5": 0.9, "lad_b6": 0.8, "lad_b7": 0.7,
    "lad_b8": 0.8, "lad_b9": 0.7,
    "lcx_b1": 1.2, "lcx_b2": 1.2, "lcx_b3": 1.0, "lcx_b4": 1.0,
    "lcx_b4_b1": 0.7, "lcx_b4_b2": 0.7,
    "lcx_b5": 0.9, "lcx_b6": 0.9, "lcx_b7": 0.8,
}


def build_env(seed=42, max_it=2000, dt_simulation=0.006):
    import time as _t
    def _ts(msg): print(f"  [{_t.strftime('%H:%M:%S')}] {msg}", flush=True)

    _ts("left_coronary_branches ...")
    branches, insertion_pt, insertion_dir = left_coronary_branches(
        PATH_DIR, junction_radius_mm=3.0)
    lad_branch  = next(b for b in branches if b.name == "lad")
    mid_lad_idx = len(lad_branch.coordinates) // 2
    mid_lad_3d  = lad_branch.coordinates[mid_lad_idx]

    _ts("FromMesh ...")
    vessel_tree = FromMesh(
        mesh=MESH_PATH,
        insertion_position=tuple(insertion_pt.tolist()),
        insertion_direction=tuple(insertion_dir.tolist()),
        branch_list=branches,
        approx_branch_radii=APPROX_BRANCH_RADIUS_MM,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )

    # Loud bbox assertion — units error fails immediately
    cs = vessel_tree.coordinate_space
    max_ext = float((cs.high - cs.low).max())
    assert 15 < max_ext < 200, (
        f"UNITS ERROR: max_ext={max_ext:.1f}mm, expected 15-200mm for coronary")

    # JShaped: tip_radius=1.5mm, tip_angle=0.2*pi  (~0.94mm arc length tip)
    # Fits 3-4mm lumen; curved enough to give a well-defined tangent at DOF[-1].
    tip_r = 1.5
    tip_a = 0.2 * math.pi
    _ts(f"JShaped(tip_radius={tip_r}mm, tip_angle={tip_a:.3f}rad "
        f"= {math.degrees(tip_a):.1f}deg, arc={tip_r*tip_a:.2f}mm) ...")
    device     = eve.intervention.device.JShaped(tip_radius=tip_r, tip_angle=tip_a)
    simulation = CoronaryBeamAdapter(friction=0.001, dt_simulation=dt_simulation, max_it=max_it)

    _ts("TrackingOnly ...")
    fluoroscopy = TrackingOnly(simulation=simulation, vessel_tree=vessel_tree,
                               image_frequency=7.5, image_rot_zx=[20, 5])

    _ts("BranchIndex (mid-LAD) ...")
    target = BranchIndex(vessel_tree=vessel_tree, fluoroscopy=fluoroscopy,
                         threshold=TARGET_THRESHOLD_MM, branch="lad",
                         idx=mid_lad_idx)

    _ts("MonoPlaneStatic ...")
    intervention = eve.intervention.MonoPlaneStatic(
        vessel_tree=vessel_tree, devices=[device],
        simulation=simulation, fluoroscopy=fluoroscopy, target=target)

    start      = eve.start.MaxDeviceLength(intervention=intervention, max_length=500)
    pathfinder = eve.pathfinder.BruteForceBFS(intervention=intervention)

    pos_obs = eve.observation.wrapper.NormalizeTracking2DEpisode(
        eve.observation.Tracking2D(intervention=intervention, n_points=5), intervention)
    tgt_obs = eve.observation.wrapper.NormalizeTracking2DEpisode(
        eve.observation.Target2D(intervention=intervention), intervention)
    rot_obs = eve.observation.Rotations(intervention=intervention)
    state   = eve.observation.ObsDict(
        {"position": pos_obs, "target": tgt_obs, "rotation": rot_obs})

    reward = eve.reward.Combination([
        eve.reward.TargetReached(intervention=intervention, factor=1.0),
        eve.reward.PathLengthDelta(pathfinder=pathfinder, factor=0.01),
    ])

    _ts("eve.Env ...")
    env = eve.Env(
        intervention=intervention, observation=state, reward=reward,
        terminal=eve.terminal.TargetReached(intervention=intervention),
        truncation=eve.truncation.MaxSteps(200),
        visualisation=None, start=start, pathfinder=pathfinder)

    _ts("build done")
    return env, vessel_tree, mid_lad_3d


def build_geometry(vt):
    cl_pts  = vt.centerline_coordinates.copy()
    kd_cl   = cKDTree(cl_pts)
    mesh    = pv.read(VTP_PATH)
    kd_surf = cKDTree(mesh.points)
    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return kd_cl, kd_surf, branch_kds


def run(max_steps=200, dt_sim=0.006):
    import time as _t
    n_sub_theory = int((1.0 / 7.5) / dt_sim)
    adv_per_sub  = 35.0 * dt_sim
    print(f"\n{'='*80}")
    print(f"STEP 5 — JShaped(tip_radius=1.5mm, tip_angle=0.2pi) traverse")
    print(f"  dt_simulation          : {dt_sim} s  (substeps/env.step ≈ {n_sub_theory})")
    print(f"  per-substep advance    : {adv_per_sub:.4f} mm  ({adv_per_sub/0.5*100:.1f}% of 0.5mm wall)")
    print(f"{'='*80}\n")

    env, vt, mid_lad_cs = build_env(seed=42, dt_simulation=dt_sim)
    kd_cl, kd_surf, branch_kds = build_geometry(vt)

    print(f"\n[{_t.strftime('%H:%M:%S')}] env.reset() ...", flush=True)
    obs = env.reset()
    print(f"[{_t.strftime('%H:%M:%S')}] reset done", flush=True)

    initial_path = env.pathfinder.path_length
    print(f"\nPathfinder optimal path : {initial_path:.1f} mm")
    print(f"Target (vessel CS)      : ({mid_lad_cs[0]:.1f}, "
          f"{mid_lad_cs[1]:.1f}, {mid_lad_cs[2]:.1f}) mm")
    print(f"Action                  : (35.0 mm/s, 1.0 rad/s)  pure push")
    print(f"Free-space baseline     : {FREE_SPACE_JUMP_MM:.2f} mm/step\n")

    header = (f"{'Step':>4}  {'Tip (vessel CS)':>34}"
              f"  {'d_CL':>6}  {'r_loc':>5}  {'CONT':>4}  {'d_surf':>7}"
              f"  {'d_tgt':>6}  {'jump':>6}  {'vs_free':>7}"
              f"  {'path_rem':>8}  {'branch':>12}  flags")
    print(header)
    print("-" * 155)

    prev_tip   = np.array(env.intervention.simulation.dof_positions[0], dtype=float)
    log_rows   = []
    terminal   = truncation = False
    step_n     = 0
    t_steps_start = _t.perf_counter()

    while not (terminal or truncation) and step_n < max_steps:
        step_n += 1
        obs, reward, terminal, truncation, info = env.step((35.0, 1.0))

        tip    = np.array(env.intervention.simulation.dof_positions[0], dtype=float)
        d_cl   = float(kd_cl.query(tip)[0])
        d_surf = float(kd_surf.query(tip)[0])
        d_tgt  = float(np.linalg.norm(tip - mid_lad_cs))
        jump   = float(np.linalg.norm(tip - prev_tip))
        near   = min(branch_kds, key=lambda n: branch_kds[n].query(tip)[0])
        r_loc  = BRANCH_RADII.get(near, 1.5)
        cont   = d_cl <= r_loc
        path_r = env.pathfinder.path_length
        dvf    = jump - FREE_SPACE_JUMP_MM

        flags = []
        if np.any(np.isnan(tip)):        flags.append("NAN")
        if d_cl > TUNNEL_THRESH_MM:      flags.append(f"TUNNEL(d_CL={d_cl:.1f})")
        if jump > JUMP_THRESH_MM:        flags.append(f"JUMP({jump:.1f})")
        if reward < NEG_REWARD_THRESH:   flags.append(f"NEG_R({reward:.3f})")
        if jump > FREE_SPACE_JUMP_MM * 0.95 and step_n > 1:
            flags.append("FREE")

        log_rows.append(dict(step=step_n, tip=tip.copy(), d_cl=d_cl, d_surf=d_surf,
                             d_tgt=d_tgt, jump=jump, dvf=dvf, reward=reward,
                             path_rem=path_r, near=near, r_loc=r_loc,
                             contained=cont, flags=flags,
                             terminal=terminal, truncation=truncation))

        print(f"{step_n:>4}  ({tip[0]:>8.2f},{tip[1]:>8.2f},{tip[2]:>8.2f})"
              f"  {d_cl:>6.2f}  {r_loc:>5.1f}  {'YES' if cont else 'NO ':>4}  {d_surf:>7.2f}"
              f"  {d_tgt:>6.2f}  {jump:>6.2f}  {dvf:>+7.2f}"
              f"  {path_r:>8.1f}  {near:>12}  {' '.join(flags)}")

        prev_tip = tip

    t_steps_total = _t.perf_counter() - t_steps_start
    env.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    reached    = any(r["terminal"]    for r in log_rows)
    truncated  = any(r["truncation"]  for r in log_rows)
    nan_rows   = [r for r in log_rows if np.any(np.isnan(r["tip"]))]
    tunnel_rows= [r for r in log_rows if r["d_cl"] > TUNNEL_THRESH_MM]
    jump_rows  = [r for r in log_rows if r["jump"] > JUMP_THRESH_MM]
    jumps      = [r["jump"]  for r in log_rows]
    d_cls      = [r["d_cl"]  for r in log_rows]

    print(f"\nWall-time")
    print(f"  Total step loop       : {t_steps_total:.1f} s  ({t_steps_total/step_n:.2f} s/env.step)")
    print(f"  dt_simulation used    : {dt_sim} s  (~{n_sub_theory} substeps/env.step)")

    print(f"\nOutcome")
    print(f"  Target reached        : {reached}")
    print(f"  Truncated (maxsteps)  : {truncated}")
    print(f"  Steps taken           : {step_n}")
    print(f"  NaN positions         : {len(nan_rows)}")

    print(f"\nPath length")
    print(f"  Pathfinder optimal    : {initial_path:.1f} mm")
    if log_rows:
        rem  = log_rows[-1]["path_rem"]
        cons = initial_path - rem
        print(f"  Remaining at end      : {rem:.1f} mm")
        print(f"  Consumed              : {cons:.1f} mm")

    print(f"\nVelocity (free-space baseline = {FREE_SPACE_JUMP_MM:.2f} mm/step)")
    if jumps:
        free_ct    = sum(1 for r in log_rows[1:] if r["jump"] > FREE_SPACE_JUMP_MM * 0.95)
        contact_ct = sum(1 for r in log_rows[1:] if r["jump"] < FREE_SPACE_JUMP_MM * 0.90)
        print(f"  Mean jump             : {np.mean(jumps):.2f} mm/step")
        print(f"  Max  jump             : {max(jumps):.2f} mm/step")
        print(f"  Min  jump             : {min(jumps):.2f} mm/step")
        print(f"  Free-space steps      : {free_ct} / {step_n-1}")
        print(f"  Deceleration steps    : {contact_ct} / {step_n-1}  "
              f"({'WALL CONTACT CONFIRMED' if contact_ct > 5 else 'insufficient contact evidence'})")

    print(f"\nContainment (tunnel threshold = {TUNNEL_THRESH_MM} mm)")
    if d_cls:
        print(f"  Mean d_CL             : {np.mean(d_cls):.2f} mm")
        print(f"  Max  d_CL             : {max(d_cls):.2f} mm")
        print(f"  Tunnel-suspect steps  : {len(tunnel_rows)}")

    print(f"\nNearest-branch distribution")
    for bn, cnt in Counter(r["near"] for r in log_rows).most_common():
        pct = 100 * cnt / step_n
        note = "  <-- DIVERSION" if bn not in ("lad", "left_main") and cnt > 3 else ""
        print(f"  {bn:<20}  {cnt:>4} steps  ({pct:4.1f}%){note}")

    print(f"\nInstability")
    print(f"  JUMP > {JUMP_THRESH_MM}mm steps     : {len(jump_rows)}")

    print(f"\n{'='*80}")
    if reached and not nan_rows and not tunnel_rows and not jump_rows:
        print("VERDICT: PASS")
    else:
        issues = []
        if not reached:        issues.append("DID NOT REACH TARGET")
        if nan_rows:           issues.append(f"NAN ({len(nan_rows)} steps)")
        if tunnel_rows:        issues.append(f"TUNNELING ({len(tunnel_rows)} steps)")
        if jump_rows:          issues.append(f"INSTABILITY ({len(jump_rows)} steps)")
        print("VERDICT: NEEDS ATTENTION")
        for i in issues: print(f"  >> {i}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--dt", type=float, default=0.006,
                        help="SOFA dt_simulation (default 0.006 s). "
                             "Use 0.001 for 6x finer substeps (~7%% wall/step).")
    args = parser.parse_args()
    run(max_steps=args.max_steps, dt_sim=args.dt)
