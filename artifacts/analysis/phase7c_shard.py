"""Phase 7c, sharded execution. One process per single pass. NO API CALLS.

WHY THIS EXISTS. The single-process sweep (phase7c_speed_sweep.py) was killed by the OS for
low memory on its SECOND pass: one completed A1 repetition, then a scene rebuild, then dead.
SOFA scene teardown does not reliably return memory, so peak usage is set by how many scenes a
process builds - and for A1 that ceiling is roughly one scene plus another under construction.
Batching more passes per process does not help; it just postpones the same failure.

So each pass gets its own process. Peak memory becomes one scene no matter how large the sweep,
the run is RESUMABLE because completed shards are skipped, and an interruption costs one pass
rather than everything. The cost is SOFA plugin load per process, which is seconds against
minutes of simulation.

The single-process script is left intact and still works for small runs; this module imports its
primitives rather than duplicating them, so there is exactly one definition of the environment,
the policy loop and the interval arithmetic.

ARTIFACT SAFETY. Shards are written per pass to results/baselines/phase7c_shards/. The report,
CSV and JSON are written ONLY by `aggregate`, and only from shards actually on disk - so a
partial sweep produces a partial report that says how partial it is, rather than an
authoritative-looking file built from whatever happened to finish.

USAGE (SOFA env python):
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7c_shard.py run a1 35.0 1
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7c_shard.py aggregate
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase7c_speed_sweep import (ANATOMIES, HEADLINE_SPEED, OUT_DIR, RESULTS_DIR, ROTATION,
                                 SPEEDS, build_env, run_pass, wilson)

SHARD_DIR = os.path.join(OUT_DIR, "phase7c_shards")

# The sweep was CLOSED at 12 shards by author direction (2026-09-14): a bracketing design of
# low / default / high speed on both anatomies, not the five-speed grid first planned. Aggregating
# against the original grid would label the closed design "incomplete", which misdescribes a
# deliberate scope decision as a missing measurement. 25 and 45 mm/s were never part of it.
DESIGN_SPEEDS = [15.0, 35.0, 55.0]


def shard_path(anat: str, speed: float, rep: int) -> str:
    return os.path.join(SHARD_DIR, f"phase7c_{anat}_{speed:g}_r{rep}.json")


def cmd_run(anat: str, speed: float, rep: int) -> int:
    os.makedirs(SHARD_DIR, exist_ok=True)
    path = shard_path(anat, speed, rep)
    if os.path.exists(path):
        print(f"SKIP (exists): {os.path.basename(path)}", flush=True)
        return 0
    cfg = ANATOMIES[anat]
    print(f"RUN {cfg['label']}  speed={speed} mm/s  rep={rep}  budget={cfg['budget']}",
          flush=True)
    t0 = time.time()
    episodes = run_pass(cfg, speed)
    mins = (time.time() - t0) / 60.0
    run = [e for e in episodes if not e["reset_failed"]]
    k = sum(1 for e in run if e["success"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"anatomy": anat, "label": cfg["label"], "speed": speed, "rep": rep,
                   "budget": cfg["budget"], "rotation": ROTATION,
                   "n_run": len(run), "n_success": k, "minutes": mins,
                   "episodes": episodes}, fh, indent=2)
    print(f"  {k}/{len(run)} = {100.0*k/len(run) if run else float('nan'):.1f}%  "
          f"in {mins:.1f} min  -> {os.path.basename(path)}", flush=True)
    return 0


def load_shards() -> dict:
    out: dict = {}
    if not os.path.isdir(SHARD_DIR):
        return out
    for fn in sorted(os.listdir(SHARD_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(SHARD_DIR, fn), encoding="utf-8") as fh:
            s = json.load(fh)
        out.setdefault(s["anatomy"], {}).setdefault(s["speed"], []).append(s)
    return out


def cmd_aggregate() -> int:
    shards = load_shards()
    lines: list[str] = []
    def emit(s: str = "") -> None:
        print(s, flush=True)
        lines.append(s)

    emit("=" * 88)
    emit("PHASE 7c — ADVANCE-SPEED SENSITIVITY CURVE (simulator only, no API calls)")
    emit("=" * 88)
    emit(f"HEADLINE, PRE-COMMITTED IN PRESPEC BEFORE THIS RAN: {HEADLINE_SPEED} mm/s")
    emit("  Other speeds are a sensitivity curve, NOT candidate baselines. The reported")
    emit("  open-loop floor stays at the harness default whatever this shows.")
    emit("")
    emit("A between-speed difference counts ONLY if the pooled Wilson intervals separate.")
    emit("Phase 7g measured a run-to-run floor of 20.0 pp (A1) and 28.0 pp (A2) for a FIXED")
    emit("policy, so a single run per speed could not tell a speed effect from sampling noise.")
    emit("A3 is absent: excluded from Results on physical-validity grounds (C11).")

    # Completeness is stated up front. A partial sweep must never read as a finished one.
    expected = [(a, s) for a in ANATOMIES for s in DESIGN_SPEEDS]
    have = {(a, s): len(shards.get(a, {}).get(s, [])) for a, s in expected}
    missing = [(a, s) for a, s in expected if have[(a, s)] == 0]
    emit("")
    emit("COMPLETENESS")
    for a in ANATOMIES:
        counts = ", ".join(f"{s:g}:{have[(a, s)]}" for s in DESIGN_SPEEDS)
        emit(f"  {ANATOMIES[a]['label']:<24} reps per speed -> {counts}")
    if missing:
        emit(f"  *** INCOMPLETE: {len(missing)} (anatomy, speed) cell(s) have NO data: "
             f"{', '.join(f'{a}@{s:g}' for a, s in missing)}")
        emit("  Everything below is computed from what exists. Do not read it as a full sweep.")
    else:
        emit("  all cells populated")

    rows = []
    payload = {}
    for anat in ANATOMIES:
        if anat not in shards:
            continue
        cfg = ANATOMIES[anat]
        emit("")
        emit("=" * 88)
        emit(f"{cfg['label']}   budget={cfg['budget']}  seeds={len(cfg['seeds'])}  "
             f"floor from 7g = {cfg['floor_pp']:.1f} pp")
        emit("=" * 88)
        per_speed = {}
        for speed in DESIGN_SPEEDS:
            ss = shards[anat].get(speed, [])
            if not ss:
                emit(f"  {speed:5.1f} mm/s : no data")
                continue
            run = [e for s in ss for e in s["episodes"] if not e["reset_failed"]]
            k = sum(1 for e in run if e["success"])
            n = len(run)
            lo, hi = wilson(k, n)
            per_rep = [s["n_success"] / s["n_run"] if s["n_run"] else float("nan") for s in ss]
            steps = [e["steps"] for e in run if e["success"]]
            fails = [e for e in run if not e["success"]]
            at_cap = sum(1 for e in fails if e["steps"] >= cfg["budget"])
            fd = sorted(e["final_dist"] for e in fails
                        if e["final_dist"] is not None and np.isfinite(e["final_dist"]))
            fmed = float(np.median(fd)) if fd else None
            near = sum(1 for d in fd if d <= 20.0)
            med_steps = float(np.median(steps)) if steps else None
            per_speed[speed] = {"k": k, "n": n, "rate": k / n if n else float("nan"),
                                "lo": lo, "hi": hi, "per_rep": per_rep, "reps": len(ss),
                                "median_steps": med_steps, "fail_at_cap": at_cap,
                                "fail_near": near, "fail_dist_median": fmed,
                                "fail_dist_min": float(fd[0]) if fd else None,
                                "fail_dist_max": float(fd[-1]) if fd else None}
            tag = "  <-- HEADLINE (pre-committed)" if speed == HEADLINE_SPEED else ""
            emit(f"  {speed:5.1f} mm/s : {k:3d}/{n:3d} = {100.0*k/n:5.1f}%  "
                 f"95% CI [{100*lo:5.1f}, {100*hi:5.1f}]  reps={len(ss)}  "
                 f"per-rep {['%.0f%%' % (100*x) for x in per_rep]}  "
                 f"median steps {med_steps}{tag}")
            if fails:
                emit(f"                {len(fails)} failures: {at_cap} hit the "
                     f"{cfg['budget']}-step cap, {near} ended within 20 mm of target; "
                     f"final distance median {fmed:.1f} mm "
                     f"[{fd[0]:.1f}, {fd[-1]:.1f}]")
                if at_cap and fmed is not None and fmed > 20.0:
                    emit("                -> these hit the cap far from target: they went the "
                         "wrong way, they did not run out of budget.")

        if not per_speed:
            continue

        emit("")
        emit("  BUDGET-LIMITATION CHECK (steps scale roughly as 1/speed):")
        ref = per_speed.get(HEADLINE_SPEED, {}).get("median_steps")
        if ref:
            for s in sorted(per_speed):
                need = ref * HEADLINE_SPEED / s
                flag = "  BUDGET-LIMITED BY CONSTRUCTION" if need > cfg["budget"] else ""
                emit(f"    {s:5.1f} mm/s  expected ~{need:5.1f} steps vs budget "
                     f"{cfg['budget']}{flag}")
            emit("    A speed flagged above cannot reach target within its budget no matter how")
            emit("    well it navigates. Its rate measures the budget, not the geometry.")
        else:
            emit("    no successes at the headline speed; cannot estimate step scaling")

        n_pooled = max(v["n"] for v in per_speed.values())
        w_lo, w_hi = wilson(int(round(0.7 * n_pooled)), n_pooled)
        emit("")
        emit(f"  RESOLUTION: pooled n up to {n_pooled} per speed gives a Wilson interval "
             f"{100*(w_hi-w_lo):.0f} pp")
        emit("  wide at p = 0.7. Two speeds separate only if their rates differ by roughly that")
        emit("  much. A flat curve means FLAT WITHIN THIS RESOLUTION, not that speed has no")
        emit("  effect.")

        emit("")
        emit("  SEPARATION TEST — pairs whose pooled 95% intervals do not overlap:")
        sp = sorted(per_speed)
        separated = []
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
            emit("    none. No pair separates at the pooled sample size.")
            emit("    -> FLAT within the resolution this design achieves. Do not read an")
            emit("       ordering into overlapping intervals.")

        head = per_speed.get(HEADLINE_SPEED)
        if head:
            emit("")
            emit(f"  HEADLINE {HEADLINE_SPEED:.1f} mm/s pooled over {head['reps']} rep(s): "
                 f"{head['k']}/{head['n']} = {100*head['rate']:.1f}% "
                 f"[{100*head['lo']:.1f}, {100*head['hi']:.1f}]")
            best = max(per_speed, key=lambda s: per_speed[s]["rate"])
            beaten = [s for s in sorted(per_speed) if per_speed[s]["lo"] > head["hi"]]
            if beaten:
                emit("")
                emit("  *** THE PRE-COMMITTED HEADLINE SPEED IS NOT THE BEST PERFORMER ***")
                for s in beaten:
                    v = per_speed[s]
                    emit(f"      {s:5.1f} mm/s reaches {100*v['rate']:.1f}% "
                         f"[{100*v['lo']:.1f}, {100*v['hi']:.1f}] and SEPARATES from the "
                         f"headline's {100*head['rate']:.1f}%")
                emit(f"      Best in sweep: {best:g} mm/s at "
                     f"{100*per_speed[best]['rate']:.1f}%.")
                emit("      The open-loop floor for this anatomy is therefore HIGHER than the")
                emit("      headline implies, and the manuscript must say so. The headline still")
                emit("      stays at the harness default per the PRESPEC pre-commitment: that")
                emit("      rule exists precisely for the case where honouring it costs us.")
            elif best != HEADLINE_SPEED:
                emit(f"  Best rate is {best:g} mm/s ({100*per_speed[best]['rate']:.1f}%), but it")
                emit("  does not separate from the headline at this resolution.")

        for speed, v in per_speed.items():
            rows.append([cfg["label"], f"{speed:.1f}", v["k"], v["n"], v["reps"],
                         f"{v['rate']:.4f}", f"{v['lo']:.4f}", f"{v['hi']:.4f}",
                         " ".join(f"{x:.4f}" for x in v["per_rep"]),
                         v["median_steps"] if v["median_steps"] is not None else "",
                         v["fail_at_cap"], v["fail_near"],
                         f"{v['fail_dist_median']:.1f}" if v["fail_dist_median"] else ""])
        payload[anat] = {"label": cfg["label"], "budget": cfg["budget"],
                         "floor_pp": cfg["floor_pp"], "separated_pairs": separated,
                         "speeds": {str(s): v for s, v in per_speed.items()}}

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "phase7c_speed_sweep.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "advance_mm_s", "successes", "episodes", "reps", "rate",
                    "wilson_lo", "wilson_hi", "per_rep_rates", "median_steps_success",
                    "failures_at_step_cap", "failures_within_20mm",
                    "failure_final_dist_median_mm"])
        w.writerows(rows)
    with open(os.path.join(OUT_DIR, "phase7c_speed_sweep.json"), "w", encoding="utf-8") as fh:
        json.dump({"headline_speed": HEADLINE_SPEED, "speeds": DESIGN_SPEEDS,
                   "complete": not missing, "missing_cells": missing,
                   "anatomies": payload}, fh, indent=2)
    with open(os.path.join(RESULTS_DIR, "phase7c_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    emit("")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7c_speed_sweep.csv')}")
    emit(f"wrote {os.path.join(OUT_DIR, 'phase7c_speed_sweep.json')}")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7c_report.txt')}")
    return 1 if missing else 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1].lower()
    if cmd == "run":
        return cmd_run(sys.argv[2].lower(), float(sys.argv[3]), int(sys.argv[4]))
    if cmd == "aggregate":
        return cmd_aggregate()
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
