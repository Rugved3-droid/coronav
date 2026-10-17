"""
Three-run diagnostic — raw evidence, no interpretation.

RUN 1: Coronary, REVERTED (no _fix_tip_dof)
RUN 2: Aortic arch, UNMODIFIED (SofaBeamAdapter + AorticArch + JShaped)
RUN 3: Coronary, CURRENT (with _fix_tip_dof)

Each run reports:
  - nan count / 189 after step 1 (and 2)
  - first_nan_row
  - xtip AFTER each step (0.0000 = IRC masked; ~0.31 = no reset)
  - FixedConstraint size (n_fixed DOFs)
  - indexFirstNode (firstSimulatedNode)
  - dist[-1,-2] before animate (separation of tip and handle DOFs)

SOFA's "Tracking is NAN, resetting devices" prints to C stdout;
visible in terminal output between probe lines.

Run:
  D:\\conda\\envs\\steve\\python.exe D:\\steve\\stEVE\\coronary_fixture\\diag_three_runs.py
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import eve
from eve.intervention.simulation.sofabeamadapter import SofaBeamAdapter
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.target.centerlinerandom import CenterlineRandom
from eve.intervention.vesseltree.frommesh import FromMesh
from eve.intervention.vesseltree.aorticarch import AorticArch

from coronary_fixture.pth_centerlines import left_coronary_branches
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

MODEL_DIR = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR  = os.path.join(MODEL_DIR, "Paths")
MESH_PATH = os.path.join(HERE, "clipped_left.obj")

XTIP_ADVANCE = 0.21   # same advance used in all tests (= 35*0.006 from step3 verify)
N_STEPS      = 2


# ── No-fix variant ─────────────────────────────────────────────────────────────
class CoronaryNoFix(CoronaryBeamAdapter):
    def reset(self, *args, **kwargs):
        SofaBeamAdapter.reset(self, *args, **kwargs)   # skip _fix_tip_dof


class AorticIncrSAP(SofaBeamAdapter):
    """Stock SofaBeamAdapter but with IncrSAP instead of BruteForceBroadPhase."""
    def _basic_setup(self, friction: float):
        self.root.addObject("FreeMotionAnimationLoop")
        self.root.addObject("DefaultPipeline", draw="0", depth="6", verbose="1")
        self.root.addObject("IncrSAP")
        self.root.addObject("LocalMinDistance", contactDistance=0.3, alarmDistance=0.5,
                            angleCone=0.02, name="localmindistance")
        self.root.addObject("DefaultContactManager", response="FrictionContactConstraint")
        self.root.addObject("LCPConstraintSolver", mu=friction, tolerance=1e-4,
                            maxIt=2000, name="LCP", build_lcp=False)


# Offset chosen to match coronary insertion-point magnitude: ~(-16, 177, -149).
# Aortic native ip is ~(-0.066, -0.004, 2.0), so offset lands ip at ~230mm from origin.
_FAR_OFFSET = np.array([-16.0, 177.0, -151.0], dtype=np.float64)

class AorticFarIP(SofaBeamAdapter):
    """Aortic scene with insertion point translated ~230mm from origin (coronary magnitude).
    Everything else identical to stock aortic: same mesh, device, solver."""
    def reset(self, insertion_point, insertion_direction, *args, **kwargs):
        ip_far = np.asarray(insertion_point, dtype=np.float64) + _FAR_OFFSET
        print(f"  [AorticFarIP] original ip={np.array(insertion_point).round(4)}  "
              f"moved ip={ip_far.round(4)}  "
              f"dist_from_origin={np.linalg.norm(ip_far):.2f}mm", flush=True)
        super().reset(tuple(ip_far.tolist()), insertion_direction, *args, **kwargs)


# ── Build helpers ──────────────────────────────────────────────────────────────
def _build_coronary(sim_cls):
    branches, ins_pt, ins_dir = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
    lad      = next(b for b in branches if b.name == "lad")
    mid_idx  = len(lad.coordinates) // 2
    vt = FromMesh(mesh=MESH_PATH,
                  insertion_position=tuple(ins_pt.tolist()),
                  insertion_direction=tuple(ins_dir.tolist()),
                  branch_list=branches, approx_branch_radii=2.5,
                  scaling_xyz=None, rotation_yzx_deg=None,
                  rotate_branches=False, rotate_ip=False)
    device = eve.intervention.device.Straight()
    sim    = sim_cls(friction=0.001, max_it=2000)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=[20, 5])
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=5.0, branch="lad", idx=mid_idx)
    intvn  = eve.intervention.MonoPlaneStatic(vessel_tree=vt, devices=[device],
                                               simulation=sim, fluoroscopy=fluoro,
                                               target=target)
    start  = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf     = eve.pathfinder.BruteForceBFS(intervention=intvn)
    obs    = eve.observation.ObsDict({"pos": eve.observation.wrapper.NormalizeTracking2DEpisode(
                 eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)})
    rew    = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env    = eve.Env(intervention=intvn, observation=obs, reward=rew,
                     terminal=eve.terminal.TargetReached(intervention=intvn),
                     truncation=eve.truncation.MaxSteps(200),
                     visualisation=None, start=start, pathfinder=pf)
    return env, sim


def _build_aortic_straight(sim_cls=SofaBeamAdapter):
    vt     = AorticArch(seed=30, scaling_xyzd=[1.0, 1.0, 1.0, 0.75])
    device = eve.intervention.device.Straight()
    sim    = sim_cls(friction=0.001)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=[20, 5])
    target = CenterlineRandom(vessel_tree=vt, fluoroscopy=fluoro, threshold=5,
                               branches=["lcca", "rcca", "lsa", "rsa", "bct", "co"])
    intvn  = eve.intervention.MonoPlaneStatic(vessel_tree=vt, devices=[device],
                                               simulation=sim, fluoroscopy=fluoro,
                                               target=target)
    start  = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf     = eve.pathfinder.BruteForceBFS(intervention=intvn)
    obs    = eve.observation.ObsDict({"pos": eve.observation.wrapper.NormalizeTracking2DEpisode(
                 eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)})
    rew    = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env    = eve.Env(intervention=intvn, observation=obs, reward=rew,
                     terminal=eve.terminal.TargetReached(intervention=intvn),
                     truncation=eve.truncation.MaxSteps(200),
                     visualisation=None, start=start, pathfinder=pf)
    return env, sim


def _build_aortic(sim_cls=SofaBeamAdapter):
    vt     = AorticArch(seed=30, scaling_xyzd=[1.0, 1.0, 1.0, 0.75])
    device = eve.intervention.device.JShaped()
    sim    = sim_cls(friction=0.001)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=[20, 5])
    target = CenterlineRandom(vessel_tree=vt, fluoroscopy=fluoro, threshold=5,
                               branches=["lcca", "rcca", "lsa", "rsa", "bct", "co"])
    intvn  = eve.intervention.MonoPlaneStatic(vessel_tree=vt, devices=[device],
                                               simulation=sim, fluoroscopy=fluoro,
                                               target=target)
    start  = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf     = eve.pathfinder.BruteForceBFS(intervention=intvn)
    obs    = eve.observation.ObsDict({"pos": eve.observation.wrapper.NormalizeTracking2DEpisode(
                 eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)})
    rew    = eve.reward.TargetReached(intervention=intvn, factor=1.0)
    env    = eve.Env(intervention=intvn, observation=obs, reward=rew,
                     terminal=eve.terminal.TargetReached(intervention=intvn),
                     truncation=eve.truncation.MaxSteps(200),
                     visualisation=None, start=start, pathfinder=pf)
    return env, sim


# ── Probe ──────────────────────────────────────────────────────────────────────
def _probe(label, sim, n_steps=N_STEPS, xtip_advance=XTIP_ADVANCE):
    sofa = sim._sofa          # SofaPython3 module obtained from the sim object
    ic   = sim._instruments_combined
    root = sim.root
    fc   = ic.getObject("FixedConstraint")

    pos0 = ic.DOFs.position.value[:, 0:3].copy()
    ip   = pos0[0].copy()
    n_dof = pos0.shape[0]

    xtip0 = float(ic.m_ircontroller.xtip.value[0])
    fsn0  = int(ic.m_ircontroller.indexFirstNode.value)
    fc0   = list(fc.indices.value)
    tip0  = pos0[-1].copy()
    h0    = pos0[-2].copy()
    d0    = float(np.linalg.norm(tip0 - h0))

    sys.stdout.flush()
    print(f"\n{'='*65}", flush=True)
    print(f"PROBE: {label}", flush=True)
    print(f"  n_dof={n_dof}  xtip={xtip0:.4f}mm  fsn={fsn0}  "
          f"fc_n={len(fc0)}  fc=[{fc0[:2]}..{fc0[-2:] if len(fc0)>2 else ''}]", flush=True)
    print(f"  DOF[-2]={h0}  DOF[-1]={tip0}  dist[-1,-2]={d0:.6f}mm", flush=True)
    print(f"{'='*65}", flush=True)

    nan_any = False
    for s in range(n_steps):
        x     = ic.m_ircontroller.xtip.value.copy()
        x[0] += xtip_advance
        ic.m_ircontroller.xtip.value = x
        xtip_set = x[0]

        sys.stdout.flush()   # flush before animate so SOFA log appears in order
        sofa.Simulation.animate(root, root.dt.value)
        sys.stdout.flush()   # flush after so SOFA log appears before our next print

        pos    = ic.DOFs.position.value[:, 0:3]
        n_nan  = int(np.sum(np.isnan(pos)))
        xtip_a = float(ic.m_ircontroller.xtip.value[0])
        fsn_a  = int(ic.m_ircontroller.indexFirstNode.value)
        fc_n   = len(list(fc.indices.value))

        if n_nan == 0:
            tip_a = pos[-1].copy()
            d_ip  = float(np.linalg.norm(tip_a - ip))
            d_12  = float(np.linalg.norm(pos[-1] - pos[-2]))
            print(f"  step{s+1}: nan=0/{n_dof*3}  xtip_set={xtip_set:.4f}->after={xtip_a:.4f}"
                  f"  fsn={fsn_a}  fc={fc_n}"
                  f"  tip_from_ip={d_ip:.4f}mm  d[-1,-2]={d_12:.4f}mm  OK",
                  flush=True)
        else:
            rows = np.where(np.any(np.isnan(pos), axis=1))[0]
            first = int(rows[0])
            print(f"  step{s+1}: nan={n_nan}/{n_dof*3}  first_nan_row={first}"
                  f"  xtip_set={xtip_set:.4f}->after={xtip_a:.4f}"
                  f"  fsn={fsn_a}  fc={fc_n}  <<< NaN!",
                  flush=True)
            nan_any = True

    return nan_any


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── RUN 1: Coronary reverted (no _fix_tip_dof) ────────────────────────────
    print("\n" + "#"*65, flush=True)
    print("RUN 1 — Coronary REVERTED (no _fix_tip_dof)", flush=True)
    print("#"*65, flush=True)
    env1, sim1 = _build_coronary(CoronaryNoFix)
    env1.reset()
    nan1 = _probe("Coronary REVERTED", sim1)

    # ── RUN 2: Aortic arch, unmodified ────────────────────────────────────────
    print("\n" + "#"*65, flush=True)
    print("RUN 2 — Aortic arch UNMODIFIED (SofaBeamAdapter + JShaped)", flush=True)
    print("#"*65, flush=True)
    env2, sim2 = _build_aortic()
    env2.reset()
    nan2 = _probe("Aortic UNMODIFIED", sim2)

    # ── RUN 3: Coronary current (with _fix_tip_dof) ───────────────────────────
    print("\n" + "#"*65, flush=True)
    print("RUN 3 — Coronary CURRENT (with _fix_tip_dof)", flush=True)
    print("#"*65, flush=True)
    env3, sim3 = _build_coronary(CoronaryBeamAdapter)
    env3.reset()
    nan3 = _probe("Coronary CURRENT", sim3)

    # ── Summary table ──────────────────────────────────────────────────────────
    env1.close()
    env2.close()
    env3.close()
    # ── RUN 4: Aortic with IncrSAP (swap in coronary broad phase) ────────────────
    print("\n" + "#"*65, flush=True)
    print("RUN 4 — Aortic with IncrSAP (same broad phase as coronary)", flush=True)
    print("#"*65, flush=True)
    env4, sim4 = _build_aortic(AorticIncrSAP)
    env4.reset()
    nan4 = _probe("Aortic IncrSAP", sim4)

    # ── RUN 5: Aortic mesh + device, insertion point moved ~230mm from origin ─────
    print("\n" + "#"*65, flush=True)
    print("RUN 5 — Aortic scene, ip translated to coronary-magnitude coords", flush=True)
    print("#"*65, flush=True)
    env5, sim5 = _build_aortic(AorticFarIP)
    env5.reset()
    nan5 = _probe("Aortic FAR-IP (~230mm from origin)", sim5)

    print("\n" + "="*65, flush=True)
    print("SUMMARY", flush=True)
    print(f"  RUN 1 (coronary, IncrSAP, no fix)   : {'NaN' if nan1 else 'clean'}", flush=True)
    print(f"  RUN 2 (aortic, BruteForce)          : {'NaN' if nan2 else 'clean'}", flush=True)
    print(f"  RUN 3 (coronary, IncrSAP, fix)      : {'NaN' if nan3 else 'clean'}", flush=True)
    print(f"  RUN 4 (aortic, IncrSAP)             : {'NaN' if nan4 else 'clean'}", flush=True)
    print(f"  RUN 5 (aortic, far ip ~230mm)       : {'NaN' if nan5 else 'clean'}", flush=True)
    print("="*65, flush=True)

    # ── RUN 6: Aortic mesh + solver, STRAIGHT device (only change from RUN 2) ──────
    print("\n" + "#"*65, flush=True)
    print("RUN 6 — Aortic scene, Straight device (JShaped → Straight)", flush=True)
    print("#"*65, flush=True)
    env6, sim6 = _build_aortic_straight()
    env6.reset()
    nan6 = _probe("Aortic STRAIGHT device", sim6)

    print("\n" + "="*65, flush=True)
    print("SUMMARY", flush=True)
    print(f"  RUN 2 (aortic, JShaped)             : {'NaN' if nan2 else 'clean'}", flush=True)
    print(f"  RUN 6 (aortic, Straight)            : {'NaN' if nan6 else 'clean'}", flush=True)
    print("="*65, flush=True)

    env4.close()
    env5.close()
    env6.close()

    print("\nDone.", flush=True)
