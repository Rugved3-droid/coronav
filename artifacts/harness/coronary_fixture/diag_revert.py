"""
Revert diagnostic — three questions, one run:
  Q1. Does the scene NaN WITHOUT _fix_tip_dof?
  Q2. Does the wire tip ACTUALLY ADVANCE without the fix (or is it stuck)?
  Q3. What is firstSimulatedNode / FixedConstraint size in each case?

Run from your own terminal (needs display context for VTK):
  ! D:\conda\envs\steve\python.exe D:\steve\stEVE\coronary_fixture\diag_revert.py
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from eve.intervention.simulation.sofabeamadapter import SofaBeamAdapter

from coronary_fixture.pth_centerlines import left_coronary_branches
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

MODEL_DIR = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR  = os.path.join(MODEL_DIR, "Paths")
MESH_PATH = os.path.join(HERE, "clipped_left.obj")


class CoronaryNoFix(CoronaryBeamAdapter):
    """Identical to CoronaryBeamAdapter but reset() does NOT call _fix_tip_dof."""
    def reset(self, *args, **kwargs):
        SofaBeamAdapter.reset(self, *args, **kwargs)   # skip _fix_tip_dof


def _build_env(sim_cls):
    branches, ins_pt, ins_dir = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
    lad_branch  = next(b for b in branches if b.name == "lad")
    mid_lad_idx = len(lad_branch.coordinates) // 2
    vt = FromMesh(
        mesh=MESH_PATH,
        insertion_position=tuple(ins_pt.tolist()),
        insertion_direction=tuple(ins_dir.tolist()),
        branch_list=branches, approx_branch_radii=2.5,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )
    device = eve.intervention.device.Straight()
    sim    = sim_cls(friction=0.001, max_it=2000)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=[20, 5])
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=5.0, branch="lad", idx=mid_lad_idx)
    intervention = eve.intervention.MonoPlaneStatic(
        vessel_tree=vt, devices=[device],
        simulation=sim, fluoroscopy=fluoro, target=target)
    start      = eve.start.MaxDeviceLength(intervention=intervention, max_length=500)
    pathfinder = eve.pathfinder.BruteForceBFS(intervention=intervention)
    pos_obs    = eve.observation.wrapper.NormalizeTracking2DEpisode(
                    eve.observation.Tracking2D(intervention=intervention, n_points=5),
                    intervention)
    tgt_obs    = eve.observation.wrapper.NormalizeTracking2DEpisode(
                    eve.observation.Target2D(intervention=intervention),
                    intervention)
    rot_obs    = eve.observation.Rotations(intervention=intervention)
    state      = eve.observation.ObsDict({"position": pos_obs, "target": tgt_obs,
                                          "rotation": rot_obs})
    reward     = eve.reward.Combination([
        eve.reward.TargetReached(intervention=intervention, factor=1.0),
        eve.reward.PathLengthDelta(pathfinder=pathfinder, factor=0.01)])
    env = eve.Env(
        intervention=intervention, observation=state, reward=reward,
        terminal=eve.terminal.TargetReached(intervention=intervention),
        truncation=eve.truncation.MaxSteps(200),
        visualisation=None, start=start, pathfinder=pathfinder)
    return env, sim


def _probe(label, sim, n_steps=3, xtip_advance=0.21):
    import sofa
    ic   = sim._instruments_combined
    root = sim.root

    print(f"\n{'='*60}", flush=True)
    print(f"PROBE: {label}", flush=True)
    print(f"{'='*60}", flush=True)

    pos0 = ic.DOFs.position.value[:, 0:3].copy()
    ip   = pos0[0].copy()

    xtip0 = float(ic.m_ircontroller.xtip.value[0])
    fsn0  = int(ic.m_ircontroller.indexFirstNode.value[0])
    fc    = ic.getObject("FixedConstraint")
    fc0   = list(fc.indices.value)
    tip0  = pos0[-1].copy()
    h0    = pos0[-2].copy()
    d0    = float(np.linalg.norm(tip0 - h0))

    print(f"  after reset:", flush=True)
    print(f"    xtip         = {xtip0:.4f} mm", flush=True)
    print(f"    indexFirstNode = {fsn0}", flush=True)
    print(f"    FixedConstraint = {len(fc0)} DOFs (first: {fc0[:3]}, last: {fc0[-3:] if len(fc0)>=3 else fc0})", flush=True)
    print(f"    DOF[-2]      = {h0}", flush=True)
    print(f"    DOF[-1]      = {tip0}", flush=True)
    print(f"    dist[-1,-2]  = {d0:.6f} mm", flush=True)

    nan_any = False
    for s in range(n_steps):
        x     = ic.m_ircontroller.xtip.value.copy()
        x[0] += xtip_advance
        ic.m_ircontroller.xtip.value = x

        sofa.Simulation.animate(root, root.dt.value)

        pos   = ic.DOFs.position.value[:, 0:3]
        n_nan = int(np.sum(np.isnan(pos)))
        xtip_a = float(ic.m_ircontroller.xtip.value[0])
        fsn_a  = int(ic.m_ircontroller.indexFirstNode.value[0])
        fc_a   = len(list(fc.indices.value))

        if n_nan == 0:
            tip_a = pos[-1].copy()
            d_ip  = float(np.linalg.norm(tip_a - ip))
            d_12  = float(np.linalg.norm(pos[-1] - pos[-2]))
            print(f"  step {s+1}: nan=0   xtip={xtip_a:.4f}  fsn={fsn_a}  fc_n={fc_a}  "
                  f"tip_from_ip={d_ip:.4f}mm  dist[-1,-2]={d_12:.4f}mm", flush=True)
        else:
            first = int(np.where(np.any(np.isnan(pos), axis=1))[0][0])
            print(f"  step {s+1}: nan={n_nan}/189  first_nan_row={first}  "
                  f"xtip={xtip_a:.4f}  fsn={fsn_a}  fc_n={fc_a}  <<< NaN!", flush=True)
            nan_any = True

    return nan_any


if __name__ == "__main__":
    print("Building env A — REVERTED (no _fix_tip_dof) ...", flush=True)
    env_a, sim_a = _build_env(CoronaryNoFix)

    print("\nBuilding env B — CURRENT (with _fix_tip_dof) ...", flush=True)
    env_b, sim_b = _build_env(CoronaryBeamAdapter)

    env_a.reset()
    nan_a = _probe("REVERTED — no _fix_tip_dof", sim_a)

    env_b.reset()
    nan_b = _probe("CURRENT — with _fix_tip_dof", sim_b)

    print(f"\n{'='*60}", flush=True)
    print(f"REVERTED (no fix): {'NaN appeared' if nan_a else 'clean (0 NaN)'}", flush=True)
    print(f"CURRENT  (fix on): {'NaN appeared' if nan_b else 'clean (0 NaN)'}", flush=True)
    print(f"{'='*60}", flush=True)

    env_a.close()
    env_b.close()
