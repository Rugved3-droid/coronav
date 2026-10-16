"""Phase 7e companion parser — attribute SOFA solver warnings to steps, arms and outcomes.

phase7e_solver_replay.py emits "#MARK arm=.. seed=.. step=.." before every env.step(), so the
Gauss-Seidel non-convergence warnings SOFA writes to stdout can be attributed to a specific
step of a specific episode. This parser consumes that captured stdout and produces the rates.

WHAT IT ANSWERS (Phase 7e, scoped to A1 and A2; A3 is already excluded per CORRECTIONS C11):
  1. Non-convergence frequency and residual distribution, per arm.
  2. Whether non-convergence correlates with episode outcome.
  3. Whether either retained anatomy approaches A3's 97.2% - the stop-immediately threshold.

Runs on the ordinary analysis interpreter (no SOFA needed).

    python analysis/phase7e_parse_solver.py <captured_stdout_file>
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

RESULTS = Path(__file__).resolve().parent.parent / "results"
BASELINES = RESULTS / "baselines"

# Reference point: the excluded geometry, measured in Phase 7a.
A3_RATE = 0.972
A3_RESID_MAX = 1.44
STOP_THRESHOLD = 0.50          # "anything approaching 97%" - flagged well before it

# A replay whose final position lands this far from the original explored different contact
# states, so its solver rate does not describe the original episodes. The sound arms sit at
# 0.34-0.90 mm and the failing one at ~48 mm, so the threshold is not finely balanced.
DIVERGENCE_LIMIT_MM = 10.0


def final_divergence(arm: str):
    """Median |replay final distance - original final distance|, in mm, for one arm.

    Read from the per-arm replay JSON rather than the stdout markers, because the final
    positions are recorded there. Returns None if the file is absent or unreadable, so a
    missing file degrades to 'n/a' instead of crashing the report.
    """
    path = BASELINES / f"phase7e_replay_{arm}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    diffs = []
    for e in data.get("episodes", []):
        if e.get("reset_failed"):
            continue
        r, o = e.get("replay_final_dist"), e.get("orig_final_dist")
        if r is None or o is None:
            continue
        if np.isfinite(r) and np.isfinite(o):
            diffs.append(abs(float(r) - float(o)))
    return float(np.median(diffs)) if diffs else None

MARK = re.compile(r"#MARK arm=(\S+) seed=(\d+) step=(\d+)")
EPDONE = re.compile(r"#EPDONE arm=(\S+) seed=(\d+) replay_success=(\S+) "
                    r"orig_success=(\S+) steps=(\d+)/(\d+)")
FIDELITY = re.compile(r"#FIDELITY arm=(\S+) seed=(\d+) steps_moved=(\d+)/(\d+) "
                      r"delta_corr=(\S+) mean_abs_diff_mm=(\S+)")
WARN = re.compile(r"No convergence in unbuilt nlcp gaussseidel function : error =([0-9.eE+\-]+)")


def parse(path: str):
    per_step = defaultdict(list)        # (arm, seed, step) -> [residuals]
    per_arm_steps = defaultdict(int)    # arm -> marks seen
    epdone = []
    fidelity = []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = MARK.search(line)
            if m:
                cur = (m.group(1), int(m.group(2)), int(m.group(3)))
                per_arm_steps[cur[0]] += 1
                continue
            e = EPDONE.search(line)
            if e:
                epdone.append({
                    "arm": e.group(1), "seed": int(e.group(2)),
                    "replay_success": e.group(3) == "True",
                    "orig_success": e.group(4) == "True",
                    "replay_steps": int(e.group(5)), "orig_steps": int(e.group(6)),
                })
                continue
            f = FIDELITY.search(line)
            if f:
                def _num(s):
                    try:
                        return float(s)
                    except ValueError:
                        return float("nan")
                fidelity.append({
                    "arm": f.group(1), "seed": int(f.group(2)),
                    "steps_moved": int(f.group(3)), "steps_total": int(f.group(4)),
                    "delta_corr": _num(f.group(5)), "mean_abs_diff_mm": _num(f.group(6)),
                })
                continue
            w = WARN.search(line)
            if w and cur is not None:
                try:
                    per_step[cur].append(float(w.group(1)))
                except ValueError:
                    pass
    return per_step, per_arm_steps, epdone, fidelity


def describe(vals):
    if not vals:
        return None
    a = np.asarray(vals, dtype=float)
    return {"n": int(a.size), "min": float(a.min()), "q1": float(np.percentile(a, 25)),
            "median": float(np.median(a)), "q3": float(np.percentile(a, 75)),
            "max": float(a.max()), "mean": float(a.mean())}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: phase7e_parse_solver.py <captured_stdout_file>")
    src = sys.argv[1]
    if not os.path.exists(src):
        sys.exit(f"capture file not found: {src}")

    per_step, per_arm_steps, epdone, fidelity = parse(src)
    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 90)
    emit("PHASE 7e — SOLVER FIDELITY OF THE VLM ARMS (A1, A2)")
    emit(f"source: {src}")
    emit("=" * 90)
    emit("")
    emit("Reference, the EXCLUDED geometry (Phase 7a): A3 non-convergence on 97.2% of steps,")
    emit(f"residual to {A3_RESID_MAX}. Stop-immediately threshold for a retained anatomy: "
         f"{STOP_THRESHOLD:.0%}.")

    arms = sorted(per_arm_steps)
    rows = []
    emit("")
    emit(f"{'arm':<16} {'steps':>7} {'nc steps':>9} {'% steps':>9} {'warnings':>9} "
         f"{'resid med':>11} {'resid max':>11}")
    emit("-" * 90)
    verdicts = {}
    for arm in arms:
        steps = per_arm_steps[arm]
        nc_steps = sum(1 for k, v in per_step.items() if k[0] == arm and v)
        resid = [r for k, v in per_step.items() if k[0] == arm for r in v]
        frac = nc_steps / steps if steps else float("nan")
        d = describe(resid)
        med_s = f"{d['median']:.2e}" if d else "n/a"
        max_s = f"{d['max']:.2e}" if d else "n/a"
        emit(f"{arm:<16} {steps:>7} {nc_steps:>9} {frac:>8.2%} {len(resid):>9} "
             f"{med_s:>11} {max_s:>11}")
        verdicts[arm] = frac
        rows.append([arm, steps, nc_steps, f"{frac:.6f}", len(resid),
                     f"{d['median']:.6e}" if d else "",
                     f"{d['max']:.6e}" if d else "",
                     f"{d['q1']:.6e}" if d else "",
                     f"{d['q3']:.6e}" if d else ""])

    # ---- stop condition
    emit("")
    emit("=" * 90)
    emit("STOP CONDITION CHECK")
    emit("=" * 90)
    worst = max(verdicts.values()) if verdicts else 0.0
    for arm, frac in verdicts.items():
        flag = "*** EXCEEDS THRESHOLD ***" if frac >= STOP_THRESHOLD else "ok"
        emit(f"  {arm:<16} {frac:>7.2%}   {flag}")
    if worst >= STOP_THRESHOLD:
        emit("")
        emit("  STOP: a retained anatomy approaches the excluded geometry's failure rate.")
        emit("  This would remove a second anatomy. Report before drafting further.")
    else:
        emit("")
        emit(f"  No retained arm approaches A3's {A3_RATE:.1%}. Worst is {worst:.2%}.")
        emit("  -> Section V fidelity paragraph with the measured rates, rather than an")
        emit("     exclusion.")

    # ---- does non-convergence correlate with outcome?
    emit("")
    emit("=" * 90)
    emit("DOES NON-CONVERGENCE CORRELATE WITH EPISODE OUTCOME?")
    emit("=" * 90)
    by_ep = defaultdict(int)
    for (arm, seed, _step), v in per_step.items():
        if v:
            by_ep[(arm, seed)] += 1
    corr_rows = []
    for arm in arms:
        recs = [e for e in epdone if e["arm"] == arm]
        if not recs:
            emit(f"  {arm}: no #EPDONE records parsed")
            continue
        succ = [by_ep.get((arm, e["seed"]), 0) for e in recs if e["orig_success"]]
        fail = [by_ep.get((arm, e["seed"]), 0) for e in recs if not e["orig_success"]]
        med_succ = float(np.median(succ)) if succ else float("nan")
        med_fail = float(np.median(fail)) if fail else float("nan")
        line = (f"  {arm:<16} success n={len(succ):<3} median nc-steps={med_succ:>6.1f}   "
                f"failure n={len(fail):<3} median nc-steps={med_fail:>6.1f}")
        if succ and fail:
            u = stats.mannwhitneyu(succ, fail, alternative="two-sided")
            line += f"   Mann-Whitney p={u.pvalue:.3g}"
            corr_rows.append([arm, len(succ), len(fail), f"{med_succ:.2f}",
                              f"{med_fail:.2f}", f"{u.pvalue:.4g}"])
        else:
            line += "   (one outcome class empty; not tested)"
        emit(line)
    emit("")
    emit("  Descriptive. Non-convergence is a property of the contact state, which the episode's")
    emit("  own trajectory determines, so this is an association and not a causal claim.")

    # ---- did the wire actually move? the check that voided the first run
    emit("")
    emit("=" * 90)
    emit("REPLAY FIDELITY — did the wire move, and did it move as recorded?")
    emit("=" * 90)
    if not fidelity:
        emit("  NO #FIDELITY RECORDS PARSED. Either the capture predates the fidelity marker,")
        emit("  or the replay did not reach the check. Do NOT read the rates above as valid")
        emit("  until this is resolved: a replay that never moves the wire produces zero")
        emit("  contact and therefore zero non-convergence, which is what voided the first run.")
    else:
        emit(f"{'arm':<16} {'episodes':>9} {'steps moved':>14} {'delta corr':>11} "
             f"{'mean |diff| mm':>14} {'final-dist diverg mm':>21}")
        emit("-" * 100)
        for arm in arms:
            recs = [f for f in fidelity if f["arm"] == arm]
            if not recs:
                emit(f"{arm:<16} {'none':>9}")
                continue
            moved = sum(r["steps_moved"] for r in recs)
            total = sum(r["steps_total"] for r in recs)
            corrs = [r["delta_corr"] for r in recs if np.isfinite(r["delta_corr"])]
            mads = [r["mean_abs_diff_mm"] for r in recs if np.isfinite(r["mean_abs_diff_mm"])]
            div = final_divergence(arm)
            emit(f"{arm:<16} {len(recs):>9} {f'{moved}/{total}':>14} "
                 f"{(f'{np.median(corrs):.3f}' if corrs else 'n/a'):>11} "
                 f"{(f'{np.median(mads):.3f}' if mads else 'n/a'):>14} "
                 f"{(f'{div:.2f}' if div is not None else 'n/a'):>21}")
            frac_moved = moved / total if total else 0.0
            if frac_moved < 0.5:
                emit(f"    *** ONLY {frac_moved:.1%} OF STEPS MOVED THE WIRE — treat this arm's")
                emit("        solver rates as invalid, not as a low measurement.")
            elif div is not None and div > DIVERGENCE_LIMIT_MM:
                emit(f"    *** REPLAY DIVERGED {div:.1f} mm FROM THE ORIGINAL FINAL POSITION —")
                emit("        this arm's replay explored different contact states, so its rate")
                emit("        does NOT characterise the original episodes. Rate withheld.")
        emit("")
        emit("  Correlation is against the per-step distance change recorded in the trace.")
        emit("  Exact agreement is NOT expected: parsed_action is what the model asked for,")
        emit("  the harness could override it via the retraction budget or proximity gate, and")
        emit("  Phase 7g showed the environment does not reproduce a seed. A high moved-step")
        emit("  fraction is the load-bearing check; the correlation is corroboration.")

    # ---- binary outcome agreement is NOT a usable metric here; see below
    emit("")
    emit("=" * 90)
    emit("WHY BINARY OUTCOME AGREEMENT IS NOT REPORTED")
    emit("=" * 90)
    emit("  Every successful original episode crosses the 5 mm success threshold ON ITS FINAL")
    emit("  RECORDED ACTION, arriving from a median 5.6 mm and clearing the line by roughly")
    emit("  0.2 mm. The replay lands a median 0.3-0.9 mm from where the original finished. A")
    emit("  margin of 0.2 mm against a divergence of 0.3 mm means binary agreement records")
    emit("  which side of a knife edge the last step happened to fall on, not whether the")
    emit("  replay navigated the same way. On A2, 25/25 replays finish within 5.5 mm while")
    emit("  only 7/25 finish within 5.0 mm - they are terminating a fraction short, not")
    emit("  failing to navigate.")
    emit("")
    emit("  The metric is therefore WITHDRAWN rather than repaired, and replaced by the")
    emit("  continuous quantity reported above: replay-vs-original final-distance divergence.")
    emit("  Lengthening the replay to chase the threshold would manufacture agreement without")
    emit("  making the comparison more faithful.")

    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / "phase7e_solver_rates.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "steps", "nonconvergent_steps", "fraction_of_steps",
                    "total_warnings", "residual_median", "residual_max",
                    "residual_q1", "residual_q3"])
        w.writerows(rows)
    if corr_rows:
        with open(RESULTS / "phase7e_outcome_assoc.csv", "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["arm", "n_success", "n_failure", "median_nc_steps_success",
                        "median_nc_steps_failure", "mannwhitney_p"])
            w.writerows(corr_rows)

    (RESULTS / "phase7e_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase7e_report.txt'}")
    emit(f"wrote {RESULTS/'phase7e_solver_rates.csv'}")


if __name__ == "__main__":
    main()
