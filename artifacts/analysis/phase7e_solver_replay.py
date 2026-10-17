"""Phase 7e — solver-fidelity audit of the VLM study arms, A1 and A2 only. NO API CALLS.

WHY A REPLAY IS NECESSARY. Solver non-convergence is reported by SOFA to stdout, not into
trace.jsonl. The surviving run logs (batch_overlay, overlay_bright, haiku_equiv_check,
run_120_*) belong to OTHER arms — the canonical A1 v1_current and A2 arms had no stdout
captured. So the rates cannot be read off disk; they have to be re-measured.

The traces do record the action actually taken at every step (translation, rotation). Replaying
those recorded action sequences through the simulator reproduces the same action distribution on
the same mesh with the same seed, and requires no model call. That is what this does.

CAVEAT, STATED NOT BURIED: the environment does not reproduce trajectories exactly (Phase 7a),
so a replay is not a re-execution of that specific episode. It measures how often the solver
fails to converge UNDER THIS ARM'S ACTION DISTRIBUTION ON THIS ANATOMY — which is the quantity
Section V needs. The replay also records whether it reproduced the original episode's outcome,
which is a direct reproducibility probe on the VLM arms.

A3 is out of scope: excluded from Results on physical-validity grounds (CORRECTIONS C11).

OUTPUT. Per-step marker lines "#MARK arm=.. seed=.. step=.." are printed to stdout so SOFA's
warnings can be attributed to a step by the companion parser. Per-episode replay outcomes go to
results/baselines/phase7e_replay_<arm>.json.

RUN WITH THE SOFA ENV PYTHON, CAPTURING STDOUT:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7e_solver_replay.py [a1|a2|all]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np

STEVE_ROOT = r"D:\steve\stEVE"
PILOT_ROOT = r"D:\steve\pilot"
sys.path.insert(0, STEVE_ROOT)
sys.path.insert(0, PILOT_ROOT)

import eve
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly
from eve.intervention.target.branchindex import BranchIndex
from eve.intervention.vesseltree.frommesh import FromMesh
from coronary_fixture.coronary_sim import CoronaryBeamAdapter

OUT_DIR = r"D:\coronav\results\baselines"
R = r"D:\steve\pilot\runs"

ARMS = {
    "a1_wire_only": {
        "anatomy": "a1", "label": "A1 wire_only",
        "trace": rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
        "budget": 60,
    },
    "a1_overlay": {
        "anatomy": "a1", "label": "A1 overlay",
        "trace": rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
        "budget": 60,
    },
    "a2_wire_only": {
        "anatomy": "a2", "label": "A2 wire_only",
        "trace": rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
        "budget": 45,
    },
    "a2_overlay": {
        "anatomy": "a2", "label": "A2 overlay",
        "trace": rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
        "budget": 62,
    },
}

ANATOMY = {
    "a1": {"source": "vmr",
           "mesh": os.path.join(STEVE_ROOT, "coronary_fixture", "clipped_left.obj"),
           "paths": os.path.join(STEVE_ROOT, ".data", "vmr", "0066_H_CORO_H", "Paths")},
    "a2": {"source": "asoca", "case": 12,
           "mesh": os.path.join(PILOT_ROOT, "clipped_asoca_normal12.obj")},
}

DT_SIMULATION = 0.006
MAX_IT = 2000
FRICTION = 0.001
IMAGE_ROT_ZX = [0, -40]
MAX_RESET = 3
XTIP_HEALTHY = 10.0


def get_branches(cfg):
    if cfg["source"] == "vmr":
        from coronary_fixture.pth_centerlines import left_coronary_branches
        return left_coronary_branches(cfg["paths"], junction_radius_mm=3.0)
    from asoca_adapter import asoca_left_coronary_branches
    return asoca_left_coronary_branches(cfg["case"])


def build_env(anat_key, budget):
    cfg = ANATOMY[anat_key]
    branches, ins_pt, ins_dir = get_branches(cfg)
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
        truncation=eve.truncation.MaxSteps(budget),
        visualisation=None, start=start, pathfinder=pf)
    return env, sim, mid_lad


def load_actions(path):
    """seed -> ordered list of (translation, rotation), plus the original outcome."""
    by_ep = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by_ep[r["episode"]].append(r)
    out = {}
    for ep, rows in sorted(by_ep.items()):
        rows.sort(key=lambda r: r["step"])
        last = rows[-1]
        n_valid = sum(1 for r in rows if r.get("api_ok", True) and r.get("parse_ok", True))
        if n_valid == 0:
            continue                      # excluded per the 6d rule
        acts = []
        for r in rows:
            if r.get("parse_ok") is False:
                acts.append((0.0, 0.0))   # the harness executed a null hold
            else:
                # The canonical mono traces (run_coronary.py / run_asoca.py) store the action
                # NESTED as parsed_action; only the repo port (coronav/env.py) and the biplane
                # traces carry top-level translation/rotation. Reading the top level first
                # silently yielded (0,0) on every mono row and made an entire replay run
                # meaningless, so parsed_action is tried FIRST and the top level is the
                # fallback.
                pa = r.get("parsed_action") or {}
                if "translation" in pa or "rotation" in pa:
                    acts.append((float(pa.get("translation", 0.0)),
                                 float(pa.get("rotation", 0.0))))
                else:
                    acts.append((float(r.get("translation", 0.0)),
                                 float(r.get("rotation", 0.0))))

        # Guard: a replay of all-zero actions is the failure mode above. Refuse to run one
        # silently rather than emit plausible-looking zeros again.
        if not any(t != 0.0 or ro != 0.0 for t, ro in acts):
            raise SystemExit(
                f"ABORT: every action parsed as (0,0) for seed {last['seed']} in {path}. "
                "The action field is not where this loader expects it.")

        # parsed_action is what the MODEL asked for. run_coronary.py may then override it via
        # the retraction budget or the proximity gate before env.step(), so the executed action
        # can differ. The recorded distance change brackets what actually happened, so we keep
        # it for a post-hoc fidelity check of the replay rather than assuming equality.
        recorded_delta = [float(r.get("dist_delta", 0.0)) for r in rows]
        out[last["seed"]] = {
            "actions": acts,
            "recorded_delta": recorded_delta,
            "orig_success": bool(last.get("terminal")) and not bool(last.get("truncation", True)),
            "orig_steps": len(rows),
            "orig_final_dist": float(last["tip_target_dist"]),
        }
    return out


def safe_reset(env, sim, ep, seed):
    for attempt in range(1, MAX_RESET + 1):
        if hasattr(sim, "reset_devices") and getattr(sim, "_instruments_combined", None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        tip = np.array(sim.dof_positions[0], dtype=float)
        if np.any(np.isnan(tip)) or float(sim.inserted_lengths[0]) > XTIP_HEALTHY:
            continue
        env.step(np.array([[0.0, 0.0]]))
        if np.any(np.isnan(np.array(sim.dof_positions[0], dtype=float))):
            continue
        if hasattr(sim, "reset_devices") and getattr(sim, "_instruments_combined", None):
            sim.reset_devices()
        env.episode_number = ep - 1
        env.reset(seed=seed)
        return True
    return False


def replay_arm(arm_key):
    cfg = ARMS[arm_key]
    eps = load_actions(cfg["trace"])
    print(f"#ARM {arm_key} episodes={len(eps)} budget={cfg['budget']}", flush=True)
    env, sim, mid_lad = build_env(cfg["anatomy"], cfg["budget"])

    records = []
    for i, (seed, info) in enumerate(sorted(eps.items()), start=1):
        if not safe_reset(env, sim, i, seed):
            records.append({"seed": seed, "reset_failed": True})
            continue
        terminal = truncation = False
        steps = 0
        final_dist = float("nan")
        prev_dist = float(np.linalg.norm(
            np.array(sim.dof_positions[0], dtype=float) - mid_lad))
        replay_delta = []
        for step, (tr, ro) in enumerate(info["actions"], start=1):
            # marker consumed by the companion parser to attribute SOFA warnings to a step
            print(f"#MARK arm={arm_key} seed={seed} step={step}", flush=True)
            _, _, terminal, truncation, _ = env.step(np.array([[tr, ro]]))
            tip = np.array(sim.dof_positions[0], dtype=float)
            if np.any(np.isnan(tip)):
                break
            steps = step
            final_dist = float(np.linalg.norm(tip - mid_lad))
            replay_delta.append(final_dist - prev_dist)
            prev_dist = final_dist
            if terminal or truncation:
                break

        # Fidelity of the replay against what the harness actually executed. parsed_action is
        # what the model ASKED for; the retraction budget and proximity gate could override it,
        # and the environment is non-deterministic (Phase 7g), so exact agreement is not
        # expected. What matters is that the wire MOVED as recorded rather than sitting still -
        # the failure mode that voided the first run.
        n_cmp = min(len(replay_delta), len(info["recorded_delta"]))
        moved = sum(1 for d in replay_delta if abs(d) > 1e-9)
        if n_cmp >= 2:
            a = np.asarray(replay_delta[:n_cmp], dtype=float)
            b = np.asarray(info["recorded_delta"][:n_cmp], dtype=float)
            corr = (float(np.corrcoef(a, b)[0, 1])
                    if a.std() > 1e-12 and b.std() > 1e-12 else float("nan"))
            mad = float(np.mean(np.abs(a - b)))
        else:
            corr, mad = float("nan"), float("nan")
        print(f"#FIDELITY arm={arm_key} seed={seed} steps_moved={moved}/{len(replay_delta)} "
              f"delta_corr={corr:.3f} mean_abs_diff_mm={mad:.3f}", flush=True)
        replay_success = bool(terminal) and not bool(truncation)
        records.append({
            "seed": seed, "reset_failed": False,
            "replay_success": replay_success, "replay_steps": steps,
            "replay_final_dist": final_dist,
            "orig_success": info["orig_success"], "orig_steps": info["orig_steps"],
            "orig_final_dist": info["orig_final_dist"],
            "outcome_reproduced": replay_success == info["orig_success"],
            "n_actions": len(info["actions"]),
        })
        print(f"#EPDONE arm={arm_key} seed={seed} replay_success={replay_success} "
              f"orig_success={info['orig_success']} steps={steps}/{info['orig_steps']}",
              flush=True)

    with open(os.path.join(OUT_DIR, f"phase7e_replay_{arm_key}.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"arm": arm_key, "label": cfg["label"], "budget": cfg["budget"],
                   "episodes": records}, fh, indent=2)

    run = [r for r in records if not r.get("reset_failed")]
    repro = sum(1 for r in run if r["outcome_reproduced"])
    print(f"#ARMDONE {arm_key} outcome_reproduced={repro}/{len(run)}", flush=True)
    del env, sim
    return {"arm": arm_key, "label": cfg["label"], "n": len(run), "reproduced": repro}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    keys = list(ARMS) if which == "all" else [k for k in ARMS if k.startswith(which)]
    print("=" * 84, flush=True)
    print("PHASE 7e — SOLVER-FIDELITY REPLAY of the VLM arms (A1, A2). No API calls.", flush=True)
    print(f"arms: {keys}", flush=True)
    print("=" * 84, flush=True)
    t0 = time.time()
    summary = [replay_arm(k) for k in keys]
    print("")
    print("=" * 84, flush=True)
    print("REPLAY OUTCOME REPRODUCTION (same seed, same recorded actions)", flush=True)
    for s in summary:
        print(f"  {s['label']:<16} outcome reproduced {s['reproduced']}/{s['n']}", flush=True)
    print(f"  wall time {(time.time()-t0)/60.0:.1f} min", flush=True)
    print("Solver non-convergence counts come from the companion parser over this stdout.",
          flush=True)


if __name__ == "__main__":
    main()
