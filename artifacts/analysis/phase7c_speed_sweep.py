"""Phase 7c — advance-speed sensitivity curve for the open-loop baseline. NO API CALLS.

WHAT THIS IS FOR, AND WHAT IT IS NOT FOR.

The always-advance baseline runs at the harness's own default advance speed,
PROXIMITY_GATE_ADV_DEFAULT = 35.0 mm/s (run_coronary.py). **That value, and only that value, is
the open-loop baseline reported in the manuscript.** This sweep exists to show how the floor
varies with speed, so a reader can see the headline figure is not an artefact of one arbitrary
choice. It is a SENSITIVITY CURVE. It is **not** a set of candidate numbers from which a
baseline is selected.

That rule was recorded in analysis/PRESPEC.md BEFORE this sweep was written or run, precisely so
the default-is-primary choice cannot be read as a selection made after seeing which speed
flatters the manuscript. If the sweep shows a higher floor at some other speed, that appears in
the curve and **the headline baseline stays at 35 mm/s**.

WHY REPETITIONS, AND WHY A SINGLE RUN PER SPEED WOULD BE WORTHLESS.

Phase 7g measured this environment's intrinsic run-to-run noise floor: repeating a FIXED policy
over the same seed list moved the success rate by 20.0 pp on A1 and 28.0 pp on A2. Phase 7h then
showed that spread is consistent with independent binomial draws at n = 25.

So one run per speed cannot distinguish a real speed effect from ordinary sampling noise. A
curve built that way would invite the reader to interpret differences that are not there, which
is a worse outcome than not running the sweep. Each speed therefore gets R repetitions, pooled
into a rate over R x 25 episodes with a Wilson interval, and:

  **A difference between two speeds is reportable only if their intervals separate.**

The script applies that test itself rather than leaving it to prose, and says so per pair.

SCOPE. A1 and A2 only. A3 is excluded from Results on physical-validity grounds (CORRECTIONS
C11) and is absent here, as it is absent from every other retained analysis.

ARTIFACTS. Writes phase7c_* only. The committed 35 mm/s baselines
(always_advance_a{1,2}_summary.json) are NOT touched: this sweep re-measures that speed under
its own repetition design, and conflating the two would silently replace a single logged draw
with a pooled estimate.

RUN WITH THE SOFA ENV PYTHON:
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7c_speed_sweep.py [a1|a2|all] [reps]
"""
from __future__ import annotations

import csv
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

OUT_DIR = r"D:\coronav\results\baselines"
RESULTS_DIR = r"D:\coronav\results"

# The pre-committed headline. Not a sweep member that happens to win.
HEADLINE_SPEED = 35.0

# Sensitivity curve. Bracketed around the default rather than centred on a favourable value.
SPEEDS = [15.0, 25.0, 35.0, 45.0, 55.0]

ANATOMIES = {
    "a1": {
        "label": "A1 VMR0066",
        "source": "vmr",
        "mesh": os.path.join(STEVE_ROOT, "coronary_fixture", "clipped_left.obj"),
        "paths": os.path.join(STEVE_ROOT, ".data", "vmr", "0066_H_CORO_H", "Paths"),
        "budget": 60,
        "seeds": [5001 + 11 * i for i in range(25)],
        "floor_pp": 20.0,          # measured in Phase 7g at the default speed
    },
    "a2": {
        "label": "A2 ASOCA Normal_12",
        "source": "asoca",
        "case": 12,
        "mesh": os.path.join(PILOT_ROOT, "clipped_asoca_normal12.obj"),
        "budget": 45,
        "seeds": [3001 + 11 * i for i in range(25)],
        "floor_pp": 28.0,
    },
}

DT_SIMULATION = 0.006
MAX_IT = 2000
FRICTION = 0.001
IMAGE_ROT_ZX = [0, -40]
ROTATION = 0.0
MAX_RESET = 3
XTIP_HEALTHY = 10.0
DEFAULT_REPS = 3


def get_branches(cfg):
    if cfg["source"] == "vmr":
        from coronary_fixture.pth_centerlines import left_coronary_branches
        return left_coronary_branches(cfg["paths"], junction_radius_mm=3.0)
    from asoca_adapter import asoca_left_coronary_branches
    return asoca_left_coronary_branches(cfg["case"])


def build_env(cfg):
    """Identical construction to Phase 7a/7g. The speed is an ACTION parameter, not an
    environment parameter, so nothing here varies across the sweep - which is what makes the
    curve a comparison of policies rather than a comparison of environments."""
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


def run_pass(cfg, speed):
    """One full seed list at one speed, in a freshly built environment."""
    env, sim, mid_lad = build_env(cfg)
    action = np.array([[speed, ROTATION]])
    out = []
    for ep, seed in enumerate(cfg["seeds"], start=1):
        if not safe_reset(env, sim, ep, seed):
            out.append({"seed": seed, "success": None, "steps": None,
                        "final_dist": None, "reset_failed": True})
            continue
        terminal = truncation = False
        steps, final_dist = 0, float("nan")
        for step in range(1, cfg["budget"] + 1):
            _, _, terminal, truncation, _ = env.step(action)
            tip = np.array(sim.dof_positions[0], dtype=float)
            if np.any(np.isnan(tip)):
                break
            steps = step
            final_dist = float(np.linalg.norm(tip - mid_lad))
            if terminal or truncation:
                break
        out.append({"seed": seed, "success": bool(terminal) and not bool(truncation),
                    "steps": steps, "final_dist": final_dist, "reset_failed": False})
    del env, sim
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Used rather than the normal approximation because rates here sit
    near 0 and 1 often enough that the naive interval leaves the unit range."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    R = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_REPS
    keys = ["a1", "a2"] if which == "all" else [which]

    lines = []
    def emit(s=""):
        print(s, flush=True)
        lines.append(s)

    emit("=" * 88)
    emit("PHASE 7c — ADVANCE-SPEED SENSITIVITY CURVE (simulator only, no API calls)")
    emit("=" * 88)
    emit(f"speeds: {SPEEDS} mm/s   R={R} repetitions each   rotation {ROTATION} throughout")
    emit(f"HEADLINE, PRE-COMMITTED IN PRESPEC BEFORE THIS RAN: {HEADLINE_SPEED} mm/s")
    emit("  The other speeds form a sensitivity curve. They are NOT candidate baselines, and")
    emit("  the reported open-loop floor stays at the harness default whatever this shows.")
    emit("")
    emit("A between-speed difference counts ONLY if the pooled Wilson intervals separate.")
    emit("Phase 7g measured a run-to-run floor of 20.0 pp (A1) and 28.0 pp (A2) for a FIXED")
    emit("policy, so a single run per speed could not tell a speed effect from sampling noise.")
    emit("A3 is absent: excluded from Results on physical-validity grounds (C11).")

    rows = []
    payload = {}
    for key in keys:
        cfg = ANATOMIES[key]
        emit("")
        emit("=" * 88)
        emit(f"{cfg['label']}   budget={cfg['budget']}  seeds={len(cfg['seeds'])}  "
             f"floor from 7g = {cfg['floor_pp']:.1f} pp")
        emit("=" * 88)
        per_speed = {}
        for speed in SPEEDS:
            passes = []
            t0 = time.time()
            for r in range(1, R + 1):
                passes.append(run_pass(cfg, speed))
                emit(f"  {speed:5.1f} mm/s  rep {r}/{R} done in "
                     f"{(time.time() - t0) / 60.0:.1f} min cumulative")
            run = [e for p in passes for e in p if not e["reset_failed"]]
            k = sum(1 for e in run if e["success"])
            n = len(run)
            lo, hi = wilson(k, n)
            # HOW a speed fails, not just how often. Steps scale roughly as 1/speed, so a slow
            # policy can exhaust its budget while still closing on the target - that is budget
            # exhaustion, not a navigation failure, and the two must not be pooled.
            #
            # But hitting the step cap is NOT sufficient evidence of budget exhaustion. In the
            # A2 smoke run every failure at 35 mm/s hit the 45-step cap against an expected
            # traverse of 11 steps: those episodes had budget to spare and went somewhere wrong.
            # Final distance is what separates the two, so it is reported rather than inferred.
            fails = [e for e in run if not e["success"]]
            at_cap = sum(1 for e in fails if e["steps"] >= cfg["budget"])
            fd = sorted(e["final_dist"] for e in fails
                        if e["final_dist"] is not None and np.isfinite(e["final_dist"]))
            fail_med = float(np.median(fd)) if fd else None
            fail_min = float(fd[0]) if fd else None
            fail_max = float(fd[-1]) if fd else None
            # "Near" = within 4x the 5 mm success threshold: still on the right course.
            near = sum(1 for d in fd if d <= 20.0)
            per_rep = []
            for p in passes:
                pr = [e for e in p if not e["reset_failed"]]
                per_rep.append(sum(1 for e in pr if e["success"]) / len(pr) if pr else float("nan"))
            steps = [e["steps"] for e in run if e["success"]]
            per_speed[speed] = {"k": k, "n": n, "rate": k / n if n else float("nan"),
                                "lo": lo, "hi": hi, "per_rep": per_rep,
                                "median_steps": float(np.median(steps)) if steps else None,
                                "fail_at_cap": at_cap, "fail_near": near,
                                "fail_dist_median": fail_med, "fail_dist_min": fail_min,
                                "fail_dist_max": fail_max,
                                "passes": passes}
            tag = "  <-- HEADLINE (pre-committed)" if speed == HEADLINE_SPEED else ""
            emit(f"  {speed:5.1f} mm/s : {k:3d}/{n:3d} = {100.0*k/n:5.1f}%  "
                 f"95% CI [{100*lo:5.1f}, {100*hi:5.1f}]  "
                 f"per-rep {['%.0f%%' % (100*x) for x in per_rep]}"
                 f"  median steps {per_speed[speed]['median_steps']}{tag}")
            if fails:
                emit(f"                {len(fails)} failures: {at_cap} hit the "
                     f"{cfg['budget']}-step cap, {near} ended within 20 mm of target; "
                     f"final distance median {fail_med:.1f} mm "
                     f"[{fail_min:.1f}, {fail_max:.1f}]")
                if at_cap and fail_med is not None and fail_med > 20.0:
                    emit("                -> these hit the cap far from target: they went the "
                         "wrong way, they did not run out of budget.")
            rows.append([cfg["label"], f"{speed:.1f}", k, n, f"{k/n:.4f}" if n else "",
                         f"{lo:.4f}", f"{hi:.4f}",
                         " ".join(f"{x:.4f}" for x in per_rep),
                         per_speed[speed]["median_steps"] if steps else "",
                         at_cap, near,
                         f"{fail_med:.1f}" if fail_med is not None else ""])

        # Does the curve actually separate anywhere?
        # Budget-limited speeds, predicted from the headline observation rather than discovered.
        emit("")
        emit("  BUDGET-LIMITATION CHECK (steps scale roughly as 1/speed):")
        ref = per_speed[HEADLINE_SPEED]["median_steps"]
        if ref:
            for s in sorted(per_speed):
                need = ref * HEADLINE_SPEED / s
                flag = "  BUDGET-LIMITED BY CONSTRUCTION" if need > cfg["budget"] else ""
                emit(f"    {s:5.1f} mm/s  expected ~{need:5.1f} steps vs budget "
                     f"{cfg['budget']}{flag}")
            emit("    A speed flagged above cannot reach target within its budget no matter how")
            emit("    well it navigates. Its rate measures the budget, not the geometry, and it")
            emit("    must not be read as a navigation result.")
        else:
            emit(f"    no successes at the headline speed; cannot estimate step scaling")

        # Resolution computed from THIS run's own sample size, not asserted. A hardcoded caveat
        # that misstates the precision of the run printing it is worse than no caveat.
        n_pooled = R * len(cfg["seeds"])
        w_lo, w_hi = wilson(int(round(0.7 * n_pooled)), n_pooled)
        emit("")
        emit(f"  RESOLUTION OF THIS DESIGN: pooled n = {n_pooled} per speed gives a Wilson")
        emit(f"  interval {100 * (w_hi - w_lo):.0f} pp wide at p = 0.7. Two speeds separate only")
        emit("  if their rates differ by roughly that much. A flat curve therefore means FLAT")
        emit("  WITHIN THIS RESOLUTION - not that speed has no effect.")
        emit("")
        emit("  SEPARATION TEST — pairs whose pooled 95% intervals do not overlap:")
        separated = []
        sp = sorted(per_speed)
        for i in range(len(sp)):
            for j in range(i + 1, len(sp)):
                a, b = per_speed[sp[i]], per_speed[sp[j]]
                if a["hi"] < b["lo"] or b["hi"] < a["lo"]:
                    separated.append((sp[i], sp[j]))
        if separated:
            for a, b in separated:
                emit(f"    {a:5.1f} vs {b:5.1f} mm/s  SEPARATED")
            emit("    -> speed measurably changes the open-loop floor on this anatomy.")
        else:
            emit("    none. No pair of speeds separates at the pooled sample size.")
            emit("    -> the curve is FLAT within the resolution this design can achieve.")
            emit("    Report it as such; do not read an ordering into overlapping intervals.")

        head = per_speed[HEADLINE_SPEED]
        emit("")
        emit(f"  HEADLINE {HEADLINE_SPEED:.1f} mm/s pooled over {R} reps: "
             f"{head['k']}/{head['n']} = {100*head['rate']:.1f}% "
             f"[{100*head['lo']:.1f}, {100*head['hi']:.1f}]")

        # If the pre-committed speed is not the best performer, say so HERE, in the artifact,
        # so it cannot be quietly softened downstream. The pre-commitment is only worth anything
        # if it is honoured when it costs us, and a sweep where some other speed clears the task
        # more often is exactly that case.
        best = max(per_speed, key=lambda s: per_speed[s]["rate"])
        beaten = [s for s in sorted(per_speed)
                  if per_speed[s]["lo"] > head["hi"]]
        if beaten:
            emit("")
            emit("  *** THE PRE-COMMITTED HEADLINE SPEED IS NOT THE BEST PERFORMER ***")
            for s in beaten:
                v = per_speed[s]
                emit(f"      {s:5.1f} mm/s reaches {100*v['rate']:.1f}% "
                     f"[{100*v['lo']:.1f}, {100*v['hi']:.1f}] and SEPARATES from the headline's "
                     f"{100*head['rate']:.1f}%")
            emit(f"      Best in sweep: {best:.1f} mm/s at {100*per_speed[best]['rate']:.1f}%.")
            emit("      The open-loop floor for this anatomy is therefore HIGHER than the")
            emit("      headline figure implies, and the manuscript must say so. The headline")
            emit("      still stays at the harness default per the PRESPEC pre-commitment: the")
            emit("      rule exists precisely for the case where honouring it costs us.")
        elif best != HEADLINE_SPEED:
            emit(f"  Best rate in sweep is {best:.1f} mm/s "
                 f"({100*per_speed[best]['rate']:.1f}%), but it does not separate from the "
                 f"headline at this resolution.")
        emit("  The manuscript quotes the single-run range from Phases 7/7a/7g, not this pooled")
        emit("  figure. This is stated so the two are never conflated.")
        payload[key] = {"label": cfg["label"], "budget": cfg["budget"],
                        "seeds": cfg["seeds"], "reps": R, "floor_pp": cfg["floor_pp"],
                        "speeds": {str(s): {kk: vv for kk, vv in v.items() if kk != "passes"}
                                   for s, v in per_speed.items()},
                        "separated_pairs": separated,
                        "raw": {str(s): v["passes"] for s, v in per_speed.items()}}

    with open(os.path.join(RESULTS_DIR, "phase7c_speed_sweep.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "advance_mm_s", "successes", "episodes", "rate",
                    "wilson_lo", "wilson_hi", "per_rep_rates", "median_steps_success",
                    "failures_at_step_cap", "failures_within_20mm",
                    "failure_final_dist_median_mm"])
        w.writerows(rows)
    with open(os.path.join(OUT_DIR, "phase7c_speed_sweep.json"), "w", encoding="utf-8") as fh:
        json.dump({"headline_speed": HEADLINE_SPEED, "speeds": SPEEDS, "reps": R,
                   "anatomies": payload}, fh, indent=2)
    with open(os.path.join(RESULTS_DIR, "phase7c_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    emit("")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7c_speed_sweep.csv')}")
    emit(f"wrote {os.path.join(OUT_DIR, 'phase7c_speed_sweep.json')}")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7c_report.txt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
