"""Phase 7j — re-measure the always-advance floor at the OPERATOR ARMS' timestep. NO API CALLS.

WHY THIS EXISTS. Every Phase-7 baseline ran at dt_simulation = 0.006 while every operator arm ran
at 0.001 (CORRECTIONS.md C21). Net commanded displacement per environment step is the same either
way, because `MonoPlaneStatic` advances by `action x duration` with duration = 1/image_frequency.
What differs is how often contact is resolved inside that step: `SofaBeamAdapter.step` runs
`int(duration/dt)` sub-steps, so 133 at 0.001 against 22 at 0.006.

That distinction is not cosmetic for THIS baseline. An always-advance policy drives a wire into
walls; whether it catches, buckles or slides past is decided by contact resolution, not by net
commanded displacement. So the headline floor — the figure that answers the reviewer's request for
a baseline — is re-measured here under the arms' own physics.

WHAT IT DOES NOT CHANGE. The policy, speed, seeds, budgets and success criterion are identical to
Phase 7g. Only dt_simulation differs. Anything that moves is attributable to contact resolution.

The dt is written into the output JSON. Phases 7c, 7d, 7e and 7g did not record theirs, which is
why reconstructing which artifact ran at which timestep required reading source rather than
artifacts. Recording it is the fix.

RUN WITH THE SOFA ENV PYTHON:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7j_floor_dt001.py [a1|a2|all] [reps] [dt]

Writes results/baselines/floor_dt001_<anat>.json and phase7j_report.txt. Raw study logs are never
touched.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

import numpy as np

STEVE_ROOT = r"D:\steve\stEVE"
PILOT_ROOT = r"D:\steve\pilot"
sys.path.insert(0, STEVE_ROOT)
sys.path.insert(0, PILOT_ROOT)

import eve  # noqa: E402
from eve.intervention.fluoroscopy.trackingonly import TrackingOnly  # noqa: E402
from eve.intervention.target.branchindex import BranchIndex  # noqa: E402
from eve.intervention.vesseltree.frommesh import FromMesh  # noqa: E402
from coronary_fixture.coronary_sim import CoronaryBeamAdapter  # noqa: E402

OUT_DIR = r"D:\coronav\results\baselines"

# Identical to Phase 7g. Do not vary these: the whole point is that dt is the only difference.
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

DT_ARMS = 0.001          # the operator arms' timestep (run_ablation.py:628, run_asoca.py:431)
DT_BASELINES = 0.006     # what every previous Phase-7 baseline used
MAX_IT = 2000
FRICTION = 0.001
IMAGE_ROT_ZX = [0, -40]
ADVANCE_MM_S = 35.0
ROTATION = 0.0
MAX_RESET = 3
XTIP_HEALTHY = 10.0
DEFAULT_REPS = 3

# Pooled rates at dt = 0.006, for the comparison this script exists to make.
# Source: results/phase7c_pooled_default.csv via results/manifest.csv.
POOLED_006 = {"a1": 56.6, "a2": 70.9}
# Run-to-run range of a fixed policy at dt = 0.006, from Phase 7g. A shift inside this band is
# not evidence of a timestep effect.
NOISE_BAND_PP = {"a1": 20.0, "a2": 28.0}


def get_branches(cfg):
    if cfg["source"] == "vmr":
        from coronary_fixture.pth_centerlines import left_coronary_branches
        return left_coronary_branches(cfg["paths"], junction_radius_mm=3.0)
    from asoca_adapter import asoca_left_coronary_branches
    return asoca_left_coronary_branches(cfg["case"])


def build_env(cfg, dt):
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
    sim = CoronaryBeamAdapter(friction=FRICTION, dt_simulation=dt, max_it=MAX_IT)
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
    for _ in range(MAX_RESET):
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


def run_pass(cfg, dt):
    env, sim, mid_lad = build_env(cfg, dt)
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


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * p, 100 * max(0.0, c - h), 100 * min(1.0, c + h)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_REPS
    dt = float(sys.argv[3]) if len(sys.argv) > 3 else DT_ARMS
    keys = ["a1", "a2"] if which == "all" else [which]

    lines = []
    def emit(s=""):
        print(s, flush=True)
        lines.append(s)

    emit("=" * 88)
    emit("PHASE 7j — ALWAYS-ADVANCE FLOOR AT THE OPERATOR ARMS' TIMESTEP (simulator only)")
    emit(f"dt_simulation = {dt}  (arms {DT_ARMS}; previous baselines {DT_BASELINES})")
    emit(f"policy: {ADVANCE_MM_S} mm/s advance, rotation {ROTATION}; R={reps} repetitions")
    emit("seeds, budgets, policy and success criterion identical to Phase 7g")
    emit("=" * 88)

    for key in keys:
        cfg = ANATOMIES[key]
        emit("")
        emit(f"### {cfg['label']}  budget={cfg['budget']}  seeds={len(cfg['seeds'])}")
        passes, rates, timings = [], [], []
        for r in range(1, reps + 1):
            t0 = time.time()
            p = run_pass(cfg, dt)
            mins = (time.time() - t0) / 60.0
            timings.append(mins)
            passes.append(p)
            run = [e for e in p if not e["reset_failed"]]
            s = sum(1 for e in run if e["success"])
            rates.append(s / len(run) if run else float("nan"))
            emit(f"  rep {r}/{reps}: success {s}/{len(run)} = {100*rates[-1]:.1f}%  "
                 f"({mins:.1f} min)")

        k = sum(1 for p in passes for e in p if not e["reset_failed"] and e["success"])
        n = sum(1 for p in passes for e in p if not e["reset_failed"])
        pct, lo, hi = wilson(k, n)
        prev = POOLED_006[key]
        delta = pct - prev
        band = NOISE_BAND_PP[key]
        emit("")
        emit(f"  POOLED at dt={dt}: {k}/{n} = {pct:.1f}%  Wilson 95% CI [{lo:.1f}, {hi:.1f}]")
        emit(f"  Pooled at dt={DT_BASELINES} (committed): {prev:.1f}%")
        emit(f"  Shift: {delta:+.1f} pp against a measured run-to-run range of {band:.1f} pp "
             f"for a fixed policy at dt={DT_BASELINES} (Phase 7g)")
        if abs(delta) > band:
            emit("  *** SHIFT EXCEEDS THE MEASURED NOISE BAND. The timestep changes the floor, "
                 "and every calibration figure that uses it must be re-derived. ***")
        else:
            emit("  Shift is within the noise band. The floor is not distinguishable from the "
                 "dt=0.006 value at this sample size; it is NOT thereby shown to be equal.")

        by_seed = defaultdict(list)
        for p in passes:
            for e in p:
                by_seed[e["seed"]].append(e)
        conc = sum(1 for es in by_seed.values() if len({e["success"] for e in es}) == 1)
        emit(f"  per-seed concordance across the {reps} reps: {conc}/{len(by_seed)}")
        starts = Counter(tuple(round(v, 6) for v in e["first_tip"])
                         for p in passes for e in p
                         if not e["reset_failed"] and e.get("first_tip"))
        emit(f"  distinct post-reset tip positions: {len(starts)}")

        with open(os.path.join(OUT_DIR, f"floor_dt001_{key}.json"), "w", encoding="utf-8") as fh:
            json.dump({"anatomy": key, "label": cfg["label"],
                       "dt_simulation": dt, "dt_arms": DT_ARMS,
                       "dt_previous_baselines": DT_BASELINES,
                       "max_it": MAX_IT, "friction": FRICTION,
                       "advance_mm_s": ADVANCE_MM_S, "rotation": ROTATION,
                       "reps": reps, "budget": cfg["budget"], "seeds": cfg["seeds"],
                       "pooled_k": k, "pooled_n": n, "pooled_pct": pct,
                       "wilson_lo": lo, "wilson_hi": hi,
                       "pooled_pct_dt006": prev, "shift_pp": delta,
                       "noise_band_pp": band, "minutes_per_rep": timings,
                       "passes": passes}, fh, indent=2)
        emit(f"  wrote floor_dt001_{key}.json")

    with open(os.path.join(OUT_DIR, "phase7j_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    emit("")
    emit(f"wrote {os.path.join(OUT_DIR, 'phase7j_report.txt')}")


if __name__ == "__main__":
    main()
