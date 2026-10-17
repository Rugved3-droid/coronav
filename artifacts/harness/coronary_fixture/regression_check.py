"""
Regression check — coronary nav milestone canary.

Working config (locked 2026-06-28):
  Device    : JShaped(tip_radius=1.5mm, tip_angle=0.2*pi)
  dt        : 0.001 s  (133 substeps/env.step, 0.035mm/substep = 7% of 0.5mm wall)
  Solver    : IncrSAP + LCPConstraintSolver(maxIt=2000)
  Contact   : contactDistance=0.3mm, alarmDistance=0.5mm  (UNCHANGED)
  Mesh      : clipped_left.obj  (world coords, no recenter)
  Action    : (35.0 mm/s, 1.0 rad/s) pure push
  Frequency : 7.5 Hz

Pass criteria (all must hold):
  REACH  — target reached within MAX_STEPS
  NO_NAN — zero NaN tip positions
  CONT   — zero steps with d_CL > TUNNEL_THRESH_MM

Exit 0 on pass, exit 1 on any failure.
"""
import os, sys, math
import numpy as np
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

MAX_STEPS       = 60       # target reached at step 26; 60 gives 2× margin
TUNNEL_THRESH   = 3.5      # mm — same as step5_traverse
TARGET_THRESH   = 5.0      # mm — BranchIndex success radius


def build():
    branches, ins_pt, ins_dir = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
    lad     = next(b for b in branches if b.name == "lad")
    mid_idx = len(lad.coordinates) // 2

    vt = FromMesh(
        mesh=MESH_PATH,
        insertion_position=tuple(ins_pt.tolist()),
        insertion_direction=tuple(ins_dir.tolist()),
        branch_list=branches, approx_branch_radii=2.5,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )
    device = eve.intervention.device.JShaped(
        tip_radius=1.5, tip_angle=0.2 * math.pi)
    sim = CoronaryBeamAdapter(friction=0.001, dt_simulation=0.001, max_it=2000)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=[20, 5])
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=TARGET_THRESH, branch="lad", idx=mid_idx)
    intvn = eve.intervention.MonoPlaneStatic(
        vessel_tree=vt, devices=[device],
        simulation=sim, fluoroscopy=fluoro, target=target)
    start = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf    = eve.pathfinder.BruteForceBFS(intervention=intvn)
    obs   = eve.observation.ObsDict({"pos": eve.observation.wrapper.NormalizeTracking2DEpisode(
                eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)})
    rew   = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env   = eve.Env(intervention=intvn, observation=obs, reward=rew,
                    terminal=eve.terminal.TargetReached(intervention=intvn),
                    truncation=eve.truncation.MaxSteps(MAX_STEPS),
                    visualisation=None, start=start, pathfinder=pf)
    cl_pts = vt.centerline_coordinates.copy()
    return env, sim, cKDTree(cl_pts)


def run():
    print("coronary regression check ...", flush=True)
    env, sim, kd_cl = build()
    env.reset()

    nan_steps     = []
    tunnel_steps  = []
    terminal = truncation = False
    step_n = 0

    while not (terminal or truncation) and step_n < MAX_STEPS:
        step_n += 1
        _, _, terminal, truncation, _ = env.step((35.0, 1.0))
        tip   = np.array(sim.dof_positions[0], dtype=float)
        d_cl  = float(kd_cl.query(tip)[0])
        if np.any(np.isnan(tip)):
            nan_steps.append(step_n)
        if d_cl > TUNNEL_THRESH:
            tunnel_steps.append(step_n)

    env.close()

    reached = terminal and not truncation
    passed  = reached and not nan_steps and not tunnel_steps

    print(f"  steps taken  : {step_n}")
    print(f"  target reached : {reached}")
    print(f"  NaN steps    : {len(nan_steps)}")
    print(f"  tunnel steps : {len(tunnel_steps)}")

    if passed:
        print("\nRESULT: PASS")
        sys.exit(0)
    else:
        failures = []
        if not reached:
            failures.append(f"target NOT reached within {MAX_STEPS} steps")
        if nan_steps:
            failures.append(f"NaN at steps {nan_steps}")
        if tunnel_steps:
            failures.append(f"tunneling at steps {tunnel_steps} (d_CL > {TUNNEL_THRESH}mm)")
        print("\nRESULT: FAIL")
        for f in failures:
            print(f"  >> {f}")
        sys.exit(1)


if __name__ == "__main__":
    run()
