"""Phase 7a — always-advance on A2 and A3. SIMULATOR ONLY, NO API CALLS.

A 68% open-loop floor on A1 says nothing about whether that is a property of A1 or of the
environment. This runs the same trivial policy on the other two geometries.

  - If always-advance also clears A2 and A3, the environment's task is largely solvable
    without vision and the paper cannot claim a difficult navigation environment.
  - If it fails on A3, where VLM wire-only reaches 10/25, then A1 is the easy anatomy and the
    environment does discriminate.

CONFIG matches each anatomy's own WIRE-ONLY study arm (benchmarks/protocol.json):
    A2  ASOCA Normal_12  seeds 3001-3265  budget 45
    A3  ASOCA Normal_5   seeds 4001-4265  budget 150
Same harness default advance speed (PROXIMITY_GATE_ADV_DEFAULT = 35 mm/s), rotation 0.
Same simulator settings as the VLM arms: dt=0.006, max_it=2000, friction=0.001,
image_rot_zx=[0,-40], BranchIndex(branch='lad', idx=len(lad)//2, threshold=5.0).

A3 uses clipped_asoca_normal5.obj — the synthetic constant-radius tube — because that is the
surface the VLM arms actually ran on (Phase 6f-rev / CORRECTIONS C8). Centrelines for both
come from asoca_adapter, which reads D:\\ASOCADataAccess.zip.

TRACE SCHEMA matches the mono study traces (tip_branch_obs from the PRE-action tip;
tip_target_dist POST-action; dist_delta = post - pre).

RUN WITH THE SOFA ENV PYTHON:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7a_always_advance_a2a3.py [a2|a3|all]

Writes to results/baselines/. Raw study logs are never touched.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

STEVE_ROOT = r"D:\steve\stEVE"
PILOT_ROOT = r"D:\steve\pilot"
sys.path.insert(0, STEVE_ROOT)
sys.path.insert(0, PILOT_ROOT)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from coronary_fixture.coronary_sim import CoronaryBeamAdapter
from asoca_adapter import asoca_left_coronary_branches

OUT_DIR = r"D:\coronav\results\baselines"

ANATOMIES = {
    "a2": {
        "label": "A2 ASOCA Normal_12",
        "case": 12,
        "mesh": os.path.join(PILOT_ROOT, "clipped_asoca_normal12.obj"),
        "budget": 45,
        "seeds": [3001 + 11 * i for i in range(25)],
        "vlm_wire_only": "25/25",
    },
    "a3": {
        "label": "A3 ASOCA Normal_5 (synthetic tube)",
        "case": 5,
        "mesh": os.path.join(PILOT_ROOT, "clipped_asoca_normal5.obj"),
        "budget": 150,
        "seeds": [4001 + 11 * i for i in range(25)],
        "vlm_wire_only": "10/25",
    },
}

DT_SIMULATION = 0.006
MAX_IT = 2000
FRICTION = 0.001
IMAGE_ROT_ZX = [0, -40]
ADVANCE_MM_S = 35.0
ROTATION = 0.0
MAX_RESET = 3
XTIP_HEALTHY = 10.0


def build_env(cfg):
    branches, ins_pt, ins_dir = asoca_left_coronary_branches(cfg["case"])
    lad = next(b for b in branches if b.name == "lad")
    mid_idx = len(lad.coordinates) // 2
    mid_lad = lad.coordinates[mid_idx].copy()

    vt = FromMesh(
        mesh=cfg["mesh"],
        insertion_position=tuple(ins_pt.tolist()),
        insertion_direction=tuple(ins_dir.tolist()),
        branch_list=branches, approx_branch_radii=2.5,
        scaling_xyz=None, rotation_yzx_deg=None,
        rotate_branches=False, rotate_ip=False,
    )
    device = eve.intervention.device.JShaped(tip_radius=1.5, tip_angle=0.2 * math.pi)
    sim = CoronaryBeamAdapter(friction=FRICTION, dt_simulation=DT_SIMULATION, max_it=MAX_IT)
    fluoro = TrackingOnly(simulation=sim, vessel_tree=vt,
                          image_frequency=7.5, image_rot_zx=IMAGE_ROT_ZX)
    target = BranchIndex(vessel_tree=vt, fluoroscopy=fluoro,
                         threshold=5.0, branch="lad", idx=mid_idx)
    intvn = eve.intervention.MonoPlaneStatic(
        vessel_tree=vt, devices=[device], simulation=sim,
        fluoroscopy=fluoro, target=target)
    start = eve.start.MaxDeviceLength(intervention=intvn, max_length=500)
    pf = eve.pathfinder.BruteForceBFS(intervention=intvn)
    pos = eve.observation.wrapper.NormalizeTracking2DEpisode(
        eve.observation.Tracking2D(intervention=intvn, n_points=5), intvn)
    obs = eve.observation.ObsDict({"pos": pos})
    env = eve.Env(
        intervention=intvn, observation=obs,
        reward=eve.reward.TargetReached(intervention=intvn, factor=1.0),
        terminal=eve.terminal.TargetReached(intervention=intvn),
        truncation=eve.truncation.MaxSteps(cfg["budget"]),
        visualisation=None, start=start, pathfinder=pf)
    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return env, sim, branch_kds, mid_lad


def classify(tip, branch_kds):
    best, bd = "unknown", float("inf")
    for name, kd in branch_kds.items():
        d, _ = kd.query(tip)
        if d < bd:
            bd, best = d, name
    return best


def safe_reset(env, sim, ep, seed):
    for attempt in range(1, MAX_RESET + 1):
        if hasattr(sim, "reset_devices") and getattr(sim, "_instruments_combined", None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        tip = np.array(sim.dof_positions[0], dtype=float)
        xtip = float(sim.inserted_lengths[0])
        if np.any(np.isnan(tip)) or xtip > XTIP_HEALTHY:
            continue
        env.step(np.array([[0.0, 0.0]]))
        if np.any(np.isnan(np.array(sim.dof_positions[0], dtype=float))):
            continue
        if hasattr(sim, "reset_devices") and getattr(sim, "_instruments_combined", None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        return True, attempt
    return False, MAX_RESET


def run_anatomy(key):
    cfg = ANATOMIES[key]
    trace_path = os.path.join(OUT_DIR, f"always_advance_{key}_trace.jsonl")
    print("=" * 84)
    print(f"PHASE 7a — ALWAYS-ADVANCE on {cfg['label']} (simulator only, no API calls)")
    print(f"policy: translation={ADVANCE_MM_S} mm/s, rotation={ROTATION} every step")
    print(f"seeds={len(cfg['seeds'])}  budget={cfg['budget']}  dt={DT_SIMULATION}  "
          f"max_it={MAX_IT}")
    print(f"VLM wire_only on this anatomy: {cfg['vlm_wire_only']}")
    print("=" * 84, flush=True)

    env, sim, branch_kds, mid_lad = build_env(cfg)
    action = np.array([[ADVANCE_MM_S, ROTATION]])

    n_success = 0
    summary = []
    t0 = time.time()
    with open(trace_path, "w", encoding="utf-8") as tf:
        for ep, seed in enumerate(cfg["seeds"], start=1):
            ok, attempts = safe_reset(env, sim, ep, seed)
            if not ok:
                print(f"  ep{ep:02d} seed={seed}: RESET FAILED, skipped", flush=True)
                summary.append({"episode": ep, "seed": seed, "reset_failed": True})
                continue

            terminal = truncation = False
            steps = 0
            final_dist = float("nan")
            for step in range(1, cfg["budget"] + 1):
                tip_obs = np.array(sim.dof_positions[0], dtype=float)
                dist_obs = float(np.linalg.norm(tip_obs - mid_lad))
                branch_pre = classify(tip_obs, branch_kds)

                _, reward, terminal, truncation, _ = env.step(action)

                tip_post = np.array(sim.dof_positions[0], dtype=float)
                if np.any(np.isnan(tip_post)):
                    print(f"  ep{ep:02d} s{step:02d}: NaN tip, ending episode", flush=True)
                    break
                dist_post = float(np.linalg.norm(tip_post - mid_lad))

                tf.write(json.dumps({
                    "episode": ep, "step": step, "seed": seed,
                    "arm": f"baseline_always_advance_{key}",
                    "fluoro_mode": "wire_only", "policy": "always_advance",
                    "anatomy": key,
                    "api_ok": True, "parse_ok": True,
                    "intended_direction": "advance",
                    "translation": ADVANCE_MM_S, "rotation": ROTATION,
                    "dist_obs_at_call": dist_obs,
                    "tip_target_dist": dist_post,
                    "dist_delta": dist_post - dist_obs,
                    "tip_branch_obs": branch_pre,
                    "gt_tip_obs": tip_obs.tolist(), "gt_tip_pos": tip_post.tolist(),
                    "gt_target_pos": mid_lad.tolist(),
                    "raw_reward": float(reward),
                    "terminal": bool(terminal), "truncation": bool(truncation),
                    "reset_attempts": attempts,
                }) + "\n")
                tf.flush()

                steps = step
                final_dist = dist_post
                if terminal or truncation:
                    break

            success = bool(terminal) and not bool(truncation)
            n_success += int(success)
            summary.append({"episode": ep, "seed": seed, "success": success,
                            "steps": steps if success else None,
                            "final_dist": final_dist, "reset_failed": False})
            print(f"  ep{ep:02d} seed={seed}: success={success}  steps={steps}  "
                  f"final_dist={final_dist:.1f} mm", flush=True)

    dur = time.time() - t0
    n_run = sum(1 for s in summary if not s.get("reset_failed"))
    succ_steps = [s["steps"] for s in summary if s.get("success")]
    finals = [s["final_dist"] for s in summary if not s.get("reset_failed")]

    print("")
    print("=" * 84)
    print(f"ALWAYS-ADVANCE on {cfg['label']}: success {n_success}/{n_run}  "
          f"({100.0 * n_success / n_run if n_run else float('nan'):.1f}%)")
    print(f"  VLM wire_only reference: {cfg['vlm_wire_only']}")
    if succ_steps:
        print(f"  steps to target: median {np.median(succ_steps):.1f}  "
              f"range [{min(succ_steps)}, {max(succ_steps)}]  "
              f"distinct={sorted(set(succ_steps))}")
    else:
        print("  steps to target: no successes")
    if finals:
        print(f"  final distance : median {np.median(finals):.1f} mm  "
              f"range [{min(finals):.1f}, {max(finals):.1f}]")
        fails = sorted(round(s["final_dist"], 1) for s in summary
                       if not s.get("reset_failed") and not s.get("success"))
        print(f"  failure termini: {fails}")
    print(f"  rotate intents : 0 by construction -> f_rot_LM = 0.0000 exactly")
    print(f"  wall time      : {dur / 60.0:.1f} min")
    print("=" * 84, flush=True)

    with open(os.path.join(OUT_DIR, f"always_advance_{key}_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"policy": "always_advance", "anatomy": key, "label": cfg["label"],
                   "advance_mm_s": ADVANCE_MM_S, "budget": cfg["budget"],
                   "dt_simulation": DT_SIMULATION, "seeds": cfg["seeds"],
                   "mesh": cfg["mesh"], "vlm_wire_only": cfg["vlm_wire_only"],
                   "n_success": n_success, "n_run": n_run,
                   "episodes": summary}, fh, indent=2)
    print(f"wrote {trace_path}")
    return {"key": key, "label": cfg["label"], "n_success": n_success, "n_run": n_run,
            "vlm": cfg["vlm_wire_only"]}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    which = (sys.argv[1].lower() if len(sys.argv) > 1 else "all")
    keys = ["a2", "a3"] if which == "all" else [which]
    results = [run_anatomy(k) for k in keys]
    print("")
    print("=" * 84)
    print("PHASE 7a SUMMARY — always-advance vs VLM wire_only")
    print("=" * 84)
    print(f"  A1 (reference, already run)      17/25 = 68.0%   VLM wire_only 20/25 = 80%")
    for r in results:
        pct = 100.0 * r["n_success"] / r["n_run"] if r["n_run"] else float("nan")
        print(f"  {r['label']:<32} {r['n_success']}/{r['n_run']} = {pct:.1f}%   "
              f"VLM wire_only {r['vlm']}")


if __name__ == "__main__":
    main()
