"""Phase 7g — measure the environment's intrinsic run-to-run variability. NO API CALLS.

THE QUESTION THIS ACTUALLY SETTLES. Phase 7a showed that DIFFERENT seeds, under an identical
start state and an identical fixed action sequence, produce divergent trajectories. That alone
does NOT prove the environment is irreproducible — different seeds giving different results is
what a seed is for. The real question is whether the SAME seed reproduces.

So: R repetitions of the full seed list, each in a FRESHLY BUILT environment, same order, same
policy. If every seed gives the same outcome in all R repetitions, the environment is
reproducible given a seed and the Phase 7a framing (and the PRESPEC section 7 correction) was an
over-claim that must be withdrawn. If outcomes differ across repetitions for the same seed,
there is a genuine noise floor, and it is measured here.

Scoped to A1 and A2. A3 is excluded from Results on physical-validity grounds (CORRECTIONS C11).

RESIDUAL CAVEAT, STATED NOT HIDDEN: repetitions run in one process with a fresh env per
repetition. That resets the SOFA scene but not the process. Pass-to-pass differences therefore
conflate run-to-run non-determinism with any inter-episode state that survives a scene rebuild.

RUN WITH THE SOFA ENV PYTHON:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7g_nondeterminism_floor.py [a1|a2|all] [reps]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

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

OUT_DIR = r"D:\coronav\results\baselines"

ANATOMIES = {
    "a1": {
        "label": "A1 VMR0066",
        "source": "vmr",
        "mesh": os.path.join(STEVE_ROOT, "coronary_fixture", "clipped_left.obj"),
        "paths": os.path.join(STEVE_ROOT, ".data", "vmr", "0066_H_CORO_H", "Paths"),
        "budget": 60,
        "seeds": [5001 + 11 * i for i in range(25)],
    },
    "a2": {
        "label": "A2 ASOCA Normal_12",
        "source": "asoca",
        "case": 12,
        "mesh": os.path.join(PILOT_ROOT, "clipped_asoca_normal12.obj"),
        "budget": 45,
        "seeds": [3001 + 11 * i for i in range(25)],
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
DEFAULT_REPS = 5


def get_branches(cfg):
    if cfg["source"] == "vmr":
        from coronary_fixture.pth_centerlines import left_coronary_branches
        return left_coronary_branches(cfg["paths"], junction_radius_mm=3.0)
    from asoca_adapter import asoca_left_coronary_branches
    return asoca_left_coronary_branches(cfg["case"])


def build_env(cfg):
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
        truncation=eve.truncation.MaxSteps(cfg["budget"]),
        visualisation=None, start=start, pathfinder=pf)
    return env, sim, mid_lad


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


def run_pass(cfg, rep):
    env, sim, mid_lad = build_env(cfg)
    action = np.array([[ADVANCE_MM_S, ROTATION]])
    out = []
    for ep, seed in enumerate(cfg["seeds"], start=1):
        if not safe_reset(env, sim, ep, seed):
            out.append({"seed": seed, "success": None, "steps": None,
                        "final_dist": None, "reset_failed": True})
            continue
        terminal = truncation = False
        steps, final_dist = 0, float("nan")
        first_tip = np.array(sim.dof_positions[0], dtype=float).tolist()
        for step in range(1, cfg["budget"] + 1):
            _, _, terminal, truncation, _ = env.step(action)
            tip = np.array(sim.dof_positions[0], dtype=float)
            if np.any(np.isnan(tip)):
                break
            steps = step
            final_dist = float(np.linalg.norm(tip - mid_lad))
            if terminal or truncation:
                break
        out.append({"seed": seed,
                    "success": bool(terminal) and not bool(truncation),
                    "steps": steps, "final_dist": final_dist,
                    "first_tip": first_tip, "reset_failed": False})
    del env, sim
    return out


def analyse(label, reps, emit):
    R = len(reps)
    n = len(reps[0])
    emit("")
    emit("=" * 84)
    emit(f"{label} — non-determinism floor over R={R} repetitions")
    emit("=" * 84)

    rates = []
    for r, ep_list in enumerate(reps, start=1):
        run = [e for e in ep_list if not e["reset_failed"]]
        s = sum(1 for e in run if e["success"])
        rates.append(s / len(run) if run else float("nan"))
        emit(f"  rep {r}: success {s}/{len(run)} = {100.0*rates[-1]:.1f}%")
    emit(f"  success rate across repetitions: min {100*min(rates):.1f}%  "
         f"max {100*max(rates):.1f}%  range {100*(max(rates)-min(rates)):.1f} pp")

    by_seed = defaultdict(list)
    for ep_list in reps:
        for e in ep_list:
            by_seed[e["seed"]].append(e)

    concordant = 0
    discordant_seeds = []
    step_spreads = []
    for seed, es in sorted(by_seed.items()):
        outs = {e["success"] for e in es}
        if len(outs) == 1:
            concordant += 1
        else:
            discordant_seeds.append(seed)
        st = [e["steps"] for e in es if e["success"]]
        if len(st) > 1:
            step_spreads.append(max(st) - min(st))
    emit("")
    emit(f"  PER-SEED OUTCOME CONCORDANCE: {concordant}/{len(by_seed)} seeds gave the SAME "
         f"outcome in all {R} repetitions")
    if discordant_seeds:
        emit(f"    discordant seeds: {discordant_seeds}")
        for seed in discordant_seeds:
            es = by_seed[seed]
            emit(f"      seed {seed}: outcomes={[e['success'] for e in es]}  "
                 f"steps={[e['steps'] for e in es]}  "
                 f"final={[round(e['final_dist'], 1) if e['final_dist'] else None for e in es]}")
    else:
        emit("    -> every seed reproduced its outcome in every repetition")

    if step_spreads:
        a = np.array(step_spreads)
        emit(f"  steps-to-target spread within a seed (max-min over reps): "
             f"median {np.median(a):.1f}  max {a.max():.0f}")
    starts = Counter(tuple(round(v, 6) for v in e["first_tip"])
                     for ep_list in reps for e in ep_list
                     if not e["reset_failed"] and e.get("first_tip"))
    emit(f"  distinct post-reset tip positions across all reps x seeds: {len(starts)}")

    return {"rates": rates, "concordant": concordant, "n_seeds": len(by_seed),
            "discordant_seeds": discordant_seeds,
            "range_pp": 100.0 * (max(rates) - min(rates))}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    R = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_REPS
    keys = ["a1", "a2"] if which == "all" else [which]

    out_lines = []
    def emit(s=""):
        print(s, flush=True)
        out_lines.append(s)

    emit("=" * 84)
    emit("PHASE 7g — ENVIRONMENT NON-DETERMINISM FLOOR (simulator only, no API calls)")
    emit(f"policy: {ADVANCE_MM_S} mm/s advance, rotation 0; R={R} repetitions per seed")
    emit("fresh environment built per repetition; same seed list, same order")
    emit("=" * 84)

    summary = {}
    for key in keys:
        cfg = ANATOMIES[key]
        emit("")
        emit(f"### {cfg['label']}  budget={cfg['budget']}  seeds={len(cfg['seeds'])}")
        reps = []
        for r in range(1, R + 1):
            t0 = time.time()
            reps.append(run_pass(cfg, r))
            emit(f"  rep {r}/{R} done in {(time.time()-t0)/60.0:.1f} min")
        summary[key] = analyse(cfg["label"], reps, emit)
        with open(os.path.join(OUT_DIR, f"nondeterminism_floor_{key}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"anatomy": key, "label": cfg["label"], "reps": R,
                       "budget": cfg["budget"], "seeds": cfg["seeds"],
                       "advance_mm_s": ADVANCE_MM_S, "passes": reps}, fh, indent=2)

    emit("")
    emit("=" * 84)
    emit("REPORTABLE STATEMENT")
    emit("=" * 84)
    for key, s in summary.items():
        lab = ANATOMIES[key]["label"]
        if s["concordant"] == s["n_seeds"]:
            emit(f"  {lab}: every seed reproduced its outcome in all {len(s['rates'])} "
                 f"repetitions. The environment is REPRODUCIBLE given a seed; the noise "
                 f"floor on the success rate is 0.0 pp.")
        else:
            emit(f"  {lab}: {s['n_seeds'] - s['concordant']}/{s['n_seeds']} seeds changed "
                 f"outcome across repetitions; success rate varied over "
                 f"{s['range_pp']:.1f} percentage points. That is the environment's "
                 f"intrinsic run-to-run noise floor.")

    with open(os.path.join(OUT_DIR, "phase7g_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out_lines))
    emit("")
    emit(f"wrote {os.path.join(OUT_DIR, 'phase7g_report.txt')}")


if __name__ == "__main__":
    main()
