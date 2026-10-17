"""Phase 7 baseline 1 — ALWAYS-ADVANCE policy on A1. SIMULATOR ONLY, NO API CALLS.

Reviewer 1: "the reader cannot judge whether the VLM's 80% success rate is good or bad.
If a random policy achieves 0% and an RL policy achieves 90%, then the VLM is poor."

This is the baseline that matters most for the framing. The policy advances every step and
NEVER rotates and NEVER retracts. If a policy that never rotates reaches mid-LAD at a
meaningful rate, the task is easier than the paper implies and the rotation endpoint reads
very differently.

CONFIG MATCHES THE STUDY ARMS, NOT scripted_stability_check.py. That script uses
dt_simulation=0.001; the VLM arms used dt_simulation=0.006 (PAPER_DATA section 6c). Matching
the study is the whole point of a baseline, so the study value is used here. Likewise
max_it=2000, friction=0.001, JShaped(tip_radius=1.5, tip_angle=0.2*pi), image_rot_zx=[0,-40],
target BranchIndex(branch='lad', idx=len(lad)//2, threshold=5.0), MaxSteps(60),
MaxDeviceLength(max_length=500) — all as in run_coronary.py build_env().

TRACE SCHEMA matches the mono study traces, including their conventions, so the existing
Phase 3/4 machinery can consume the output unchanged:
  - tip_branch_obs is classified from the PRE-action tip (run_coronary.py:663)
  - tip_target_dist is the POST-action distance; dist_obs_at_call is the PRE-action distance
  - dist_delta = post - pre  (the movement caused by THIS step's action)

RUN WITH THE SOFA ENV PYTHON:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7_always_advance.py

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
sys.path.insert(0, STEVE_ROOT)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from coronary_fixture.coronary_sim import CoronaryBeamAdapter
from coronary_fixture.pth_centerlines import left_coronary_branches

OUT_DIR = r"D:\coronav\results\baselines"
TRACE = os.path.join(OUT_DIR, "always_advance_a1_trace.jsonl")

PATH_DIR = os.path.join(STEVE_ROOT, ".data", "vmr", "0066_H_CORO_H", "Paths")
MESH_PATH = os.path.join(STEVE_ROOT, "coronary_fixture", "clipped_left.obj")

# A1 study seeds and budget (benchmarks/protocol.json)
SEEDS = [5001, 5012, 5023, 5034, 5045, 5056, 5067, 5078, 5089, 5100,
         5111, 5122, 5133, 5144, 5155, 5166, 5177, 5188, 5199, 5210,
         5221, 5232, 5243, 5254, 5265]
N_STEPS = 60

# Study simulator config
DT_SIMULATION = 0.006
MAX_IT = 2000
FRICTION = 0.001
IMAGE_ROT_ZX = [0, -40]

# The policy: the harness's own default advance speed, zero rotation.
ADVANCE_MM_S = 35.0     # PROXIMITY_GATE_ADV_DEFAULT in run_coronary.py
ROTATION = 0.0

MAX_RESET = 3
XTIP_HEALTHY = 10.0


def build_env():
    branches, ins_pt, ins_dir = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
    lad = next(b for b in branches if b.name == "lad")
    mid_idx = len(lad.coordinates) // 2
    mid_lad = lad.coordinates[mid_idx].copy()

    vt = FromMesh(
        mesh=MESH_PATH,
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
        truncation=eve.truncation.MaxSteps(N_STEPS),
        visualisation=None, start=start, pathfinder=pf)
    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return env, sim, fluoro, branch_kds, mid_lad


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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 84)
    print("PHASE 7 BASELINE — ALWAYS-ADVANCE on A1 (simulator only, no API calls)")
    print(f"policy: translation={ADVANCE_MM_S} mm/s, rotation={ROTATION} every step")
    print(f"seeds={len(SEEDS)}  budget={N_STEPS}  dt={DT_SIMULATION}  max_it={MAX_IT}")
    print("=" * 84, flush=True)

    env, sim, fluoro, branch_kds, mid_lad = build_env()
    action = np.array([[ADVANCE_MM_S, ROTATION]])

    n_success = 0
    summary = []
    t0 = time.time()
    with open(TRACE, "w", encoding="utf-8") as tf:
        for ep, seed in enumerate(SEEDS, start=1):
            ok, attempts = safe_reset(env, sim, ep, seed)
            if not ok:
                print(f"  ep{ep:02d} seed={seed}: RESET FAILED, skipped", flush=True)
                summary.append({"episode": ep, "seed": seed, "reset_failed": True})
                continue

            terminal = truncation = False
            steps = 0
            final_dist = float("nan")
            for step in range(1, N_STEPS + 1):
                tip_obs = np.array(sim.dof_positions[0], dtype=float)
                dist_obs = float(np.linalg.norm(tip_obs - mid_lad))
                branch_pre = classify(tip_obs, branch_kds)     # PRE-action, as in the study

                _, reward, terminal, truncation, _ = env.step(action)

                tip_post = np.array(sim.dof_positions[0], dtype=float)
                if np.any(np.isnan(tip_post)):
                    print(f"  ep{ep:02d} s{step:02d}: NaN tip, ending episode", flush=True)
                    break
                dist_post = float(np.linalg.norm(tip_post - mid_lad))

                tf.write(json.dumps({
                    "episode": ep, "step": step, "seed": seed,
                    "arm": "baseline_always_advance", "fluoro_mode": "wire_only",
                    "policy": "always_advance",
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
    print("")
    print("=" * 84)
    print(f"ALWAYS-ADVANCE on A1: success {n_success}/{n_run}  "
          f"({100.0 * n_success / n_run if n_run else float('nan'):.1f}%)")
    succ_steps = [s["steps"] for s in summary if s.get("success")]
    if succ_steps:
        print(f"  steps to target: median {np.median(succ_steps):.1f}  "
              f"range [{min(succ_steps)}, {max(succ_steps)}]")
    finals = [s["final_dist"] for s in summary if not s.get("reset_failed")]
    print(f"  final distance : median {np.median(finals):.1f} mm  "
          f"range [{min(finals):.1f}, {max(finals):.1f}]")
    print(f"  rotate intents : 0 by construction -> f_rot_LM = 0.0000 exactly")
    print(f"  wall time      : {dur / 60.0:.1f} min")
    print("=" * 84)

    with open(os.path.join(OUT_DIR, "always_advance_a1_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"policy": "always_advance", "anatomy": "A1",
                   "advance_mm_s": ADVANCE_MM_S, "budget": N_STEPS,
                   "dt_simulation": DT_SIMULATION, "seeds": SEEDS,
                   "n_success": n_success, "n_run": n_run,
                   "episodes": summary}, fh, indent=2)
    print(f"wrote {TRACE}")
    print(f"wrote {os.path.join(OUT_DIR, 'always_advance_a1_summary.json')}")


if __name__ == "__main__":
    main()
