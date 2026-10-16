"""Phase 7d — oracle reachability probe. SIMULATOR ONLY, NO API CALLS.

DEFINITION, fixed in analysis/PRESPEC.md and committed BEFORE this file was written
(commit a837705), so the rule cannot be read as having been chosen to suit the answer.

The oracle is NOT a path-following controller. The action space is (advance speed, rotation) on
a J-tip guidewire, where branch selection is governed by tip orientation rather than by steering
toward a waypoint, so "follow the centreline" has no direct realisation in it. The oracle is a
**reachability probe over a restricted policy class**: a grid of constant rotation values, each
run over the full seed list at the pre-committed advance speed of 35 mm/s. It is described in
those terms and never as "the best achievable policy".

THE ROTATION GRID IS EMPIRICAL, NOT INVENTED. Auditing 1,448 logged overlay steps, the operator's
entire rotation vocabulary was 0.0 (1192 steps), -1.5 (236), +1.5 (14), -1.2 (4), +1.2 (1) and
0.3 (1). So the action space was exercised over roughly +/-1.5, and the grid brackets that. A
grid in the tens - which is what "degrees per second" would have suggested - would have been an
order of magnitude wrong and the run wasted.

THE BIAS THIS DESIGN CARRIES, AND THE RULE THAT CONTAINS IT.

Counting a seed reachable if ANY grid value succeeds is a MAXIMUM OVER NOISY BINARY TRIALS.
Phase 7g measured a run-to-run floor of 20.0 pp (A1) and 28.0 pp (A2) for a fixed policy, and
Phase 7h showed that spread is consistent with independent binomial draws. A maximum over G grid
values therefore drifts upward even when no rotation is genuinely better: with enough grid points
the union approaches 100% by selection alone.

Two figures are therefore reported, always together, neither without the other:

  1. UNION REACHABILITY - a seed counts if any grid value reached target. An UPPER BOUND
     INFLATED BY SELECTION OVER NOISE, labelled as such everywhere. Not a policy anyone could
     run: it requires knowing per seed which rotation to use.
  2. BEST SINGLE ROTATION - the highest rate achieved by one fixed rotation across the whole
     seed list. Deployable, and not inflated by per-seed cherry-picking.

Where the manuscript needs one oracle number it uses (2), not (1). If (1) is far higher, that
gap is reported as a measure of how much apparent ceiling is selection over noise. It is not
promoted to the headline because it is larger.

A FURTHER BIAS, NOT IN THE ORIGINAL RULE, STATED HERE BECAUSE IT IS REAL. At one repetition per
rotation, figure (2) is itself a maximum - over G single draws of n=25 rather than over seeds. It
is far less inflated than the union, but it is not unbiased either. So the FULL DISTRIBUTION of
all G rotation rates is reported, not just its maximum, and the selection is visible rather than
hidden behind one number.

SCOPE. A1 and A2. A3 absent (C11). Speed fixed at the harness default so the oracle and the
open-loop floor are measured at the same speed and stay comparable.

MEMORY. One pass per process, as Phase 7c: SOFA scene teardown does not reliably return memory,
and this machine killed two multi-scene runs. Shards are skipped if present, so the run resumes.

USAGE (SOFA env python):
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7d_oracle.py run a1 -1.5 1
    D:\\conda\\envs\\steve\\python.exe analysis\\phase7d_oracle.py aggregate
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase7c_speed_sweep import (ANATOMIES, HEADLINE_SPEED, OUT_DIR, RESULTS_DIR,
                                 build_env, safe_reset, wilson)

SHARD_DIR = os.path.join(OUT_DIR, "phase7d_shards")
ROTATION_GRID = [-1.5, -1.2, -0.6, 0.0, 0.6, 1.2, 1.5]
SPEED = HEADLINE_SPEED


def shard_path(anat: str, rot: float, rep: int) -> str:
    return os.path.join(SHARD_DIR, f"phase7d_{anat}_rot{rot:+g}_r{rep}.json")


def run_pass_rot(cfg, speed: float, rotation: float):
    """One full seed list at one constant (speed, rotation), fresh environment.

    Mirrors phase7c_speed_sweep.run_pass but with rotation as a parameter rather than the
    module constant 0.0 - that is the whole difference between the open-loop floor and this
    probe.
    """
    env, sim, mid_lad = build_env(cfg)
    action = np.array([[speed, rotation]])
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


def cmd_run(anat: str, rot: float, rep: int) -> int:
    os.makedirs(SHARD_DIR, exist_ok=True)
    path = shard_path(anat, rot, rep)
    if os.path.exists(path):
        print(f"SKIP (exists): {os.path.basename(path)}", flush=True)
        return 0
    cfg = ANATOMIES[anat]
    print(f"RUN {cfg['label']}  speed={SPEED} rot={rot:+g}  rep={rep}", flush=True)
    t0 = time.time()
    episodes = run_pass_rot(cfg, SPEED, rot)
    mins = (time.time() - t0) / 60.0
    run = [e for e in episodes if not e["reset_failed"]]
    k = sum(1 for e in run if e["success"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"anatomy": anat, "label": cfg["label"], "speed": SPEED, "rotation": rot,
                   "rep": rep, "budget": cfg["budget"], "n_run": len(run), "n_success": k,
                   "minutes": mins, "episodes": episodes}, fh, indent=2)
    print(f"  {k}/{len(run)} = {100.0*k/len(run) if run else float('nan'):.1f}%  "
          f"in {mins:.1f} min  -> {os.path.basename(path)}", flush=True)
    return 0


def load_shards() -> dict:
    out: dict = {}
    if not os.path.isdir(SHARD_DIR):
        return out
    for fn in sorted(os.listdir(SHARD_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(SHARD_DIR, fn), encoding="utf-8") as fh:
                s = json.load(fh)
            out.setdefault(s["anatomy"], {}).setdefault(s["rotation"], []).append(s)
    return out


def cmd_aggregate() -> int:
    shards = load_shards()
    lines: list[str] = []
    def emit(s: str = "") -> None:
        print(s, flush=True)
        lines.append(s)

    emit("=" * 88)
    emit("PHASE 7d — ORACLE REACHABILITY PROBE (simulator only, no API calls)")
    emit("=" * 88)
    emit(f"speed fixed at the pre-committed {SPEED} mm/s; rotation grid {ROTATION_GRID}")
    emit("Grid bracketed on the operator's OWN logged rotation vocabulary (+/-1.5, +/-1.2, 0.3)")
    emit("A3 absent (C11).")
    emit("")
    emit("TWO FIGURES, REPORTED TOGETHER (PRESPEC, committed before this ran):")
    emit("  UNION        - seed counts if ANY rotation reached target. Upper bound INFLATED BY")
    emit("                 SELECTION OVER NOISE. Not a runnable policy.")
    emit("  BEST SINGLE  - highest rate from one fixed rotation. Deployable. This is the figure")
    emit("                 the manuscript uses.")

    rows, payload = [], {}
    for anat in ANATOMIES:
        if anat not in shards:
            continue
        cfg = ANATOMIES[anat]
        emit("")
        emit("=" * 88)
        emit(f"{cfg['label']}   budget={cfg['budget']}  seeds={len(cfg['seeds'])}")
        emit("=" * 88)

        per_rot, reached = {}, {}
        for rot in ROTATION_GRID:
            ss = shards[anat].get(rot, [])
            if not ss:
                emit(f"  rot {rot:+5.2f} : no data")
                continue
            run = [e for s in ss for e in s["episodes"] if not e["reset_failed"]]
            k = sum(1 for e in run if e["success"])
            n = len(run)
            lo, hi = wilson(k, n)
            per_rot[rot] = {"k": k, "n": n, "rate": k / n if n else float("nan"),
                            "lo": lo, "hi": hi, "reps": len(ss)}
            for e in run:
                if e["success"]:
                    reached.setdefault(e["seed"], set()).add(rot)
            emit(f"  rot {rot:+5.2f} : {k:3d}/{n:3d} = {100.0*k/n:5.1f}%  "
                 f"95% CI [{100*lo:5.1f}, {100*hi:5.1f}]  reps={len(ss)}")

        if not per_rot:
            continue

        seeds = cfg["seeds"]
        union_k = sum(1 for s in seeds if reached.get(s))
        u_lo, u_hi = wilson(union_k, len(seeds))
        best = max(per_rot, key=lambda r: per_rot[r]["rate"])
        b = per_rot[best]

        emit("")
        emit(f"  BEST SINGLE ROTATION : {best:+g} at {100*b['rate']:.1f}% "
             f"[{100*b['lo']:.1f}, {100*b['hi']:.1f}]   <-- the manuscript figure")
        emit(f"  UNION OVER {len(per_rot)} ROTATIONS : {union_k}/{len(seeds)} = "
             f"{100.0*union_k/len(seeds):.1f}% [{100*u_lo:.1f}, {100*u_hi:.1f}]")
        emit(f"  gap union - best = {100.0*union_k/len(seeds) - 100*b['rate']:+.1f} pp")
        emit("  That gap is the size of the selection effect, not a capability. It is what you")
        emit("  gain by being told, per seed, which rotation to use - which no policy knows.")

        rates = sorted(100 * v["rate"] for v in per_rot.values())
        emit("")
        emit(f"  FULL DISTRIBUTION of the {len(per_rot)} rotation rates: "
             f"{['%.0f%%' % r for r in rates]}")
        emit("  Reported because BEST SINGLE is itself a maximum - over grid values rather than")
        emit("  over seeds. Less inflated than the union, but not unbiased. The spread here is")
        emit("  how much of that maximum could be noise.")
        if len(per_rot) > 1:
            spread = rates[-1] - rates[0]
            floor = cfg["floor_pp"]
            emit(f"  spread across rotations = {spread:.1f} pp against a measured run-to-run "
                 f"floor of {floor:.1f} pp")
            if spread <= floor:
                emit("  *** THE SPREAD DOES NOT EXCEED THE NOISE FLOOR. On this evidence no")
                emit("      rotation is demonstrably better than any other, and BEST SINGLE is")
                emit("      indistinguishable from picking one at random. Report it that way.")

        for rot, v in sorted(per_rot.items()):
            rows.append([cfg["label"], f"{rot:+g}", f"{SPEED:.1f}", v["k"], v["n"], v["reps"],
                         f"{v['rate']:.4f}", f"{v['lo']:.4f}", f"{v['hi']:.4f}",
                         "best" if rot == best else ""])
        rows.append([cfg["label"], "UNION", f"{SPEED:.1f}", union_k, len(seeds), "",
                     f"{union_k/len(seeds):.4f}", f"{u_lo:.4f}", f"{u_hi:.4f}",
                     "selection-inflated upper bound"])
        payload[anat] = {"label": cfg["label"], "best_rotation": best,
                         "best_rate": b["rate"], "best_lo": b["lo"], "best_hi": b["hi"],
                         "union_k": union_k, "union_n": len(seeds),
                         "union_rate": union_k / len(seeds),
                         "rotations": {str(r): v for r, v in per_rot.items()}}

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "phase7d_oracle.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "rotation", "advance_mm_s", "successes", "episodes", "reps",
                    "rate", "wilson_lo", "wilson_hi", "note"])
        w.writerows(rows)
    with open(os.path.join(OUT_DIR, "phase7d_oracle.json"), "w", encoding="utf-8") as fh:
        json.dump({"speed": SPEED, "grid": ROTATION_GRID, "anatomies": payload}, fh, indent=2)
    with open(os.path.join(RESULTS_DIR, "phase7d_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    emit("")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7d_oracle.csv')}")
    emit(f"wrote {os.path.join(OUT_DIR, 'phase7d_oracle.json')}")
    emit(f"wrote {os.path.join(RESULTS_DIR, 'phase7d_report.txt')}")
    return 0


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
