"""What advance speed did the operator actually use? READ-ONLY on the logged traces. No API calls.

WHY THIS EXISTS. Every open-loop baseline (Phases 7, 7a, 7c, 7d, 7g) runs at 35 mm/s, described in
PRESPEC and the drafts as "the harness's own default advance speed". That description is wrong.
In run_coronary.py, PROXIMITY_GATE_ADV_DEFAULT = 35.0 is used in exactly one place: it is the
translation SUBSTITUTED when the proximity gate suppresses a rotate intent (run_coronary.py:708).
On every other step the operator chooses its own translation, clipped to TRANS_LIMIT.

The distinction matters because Phase 7c showed blind success varies with advance speed, so a
floor measured at 35 mm/s is not a calibration for an operator that navigated at a different speed.
This script measures the speed the operator used, per arm, so that statement rests on an artifact.

OUTPUTS
  results/phase7_operator_speed.csv               per-arm summary
  results/phase7_operator_speed_distribution.csv  share of steps at EACH translation value, per arm
  results/phase7_operator_speed_report.txt

Scope: the four confirmatory arms (A1, A2 x wire_only, overlay). A3 absent (C11).
"""
from __future__ import annotations

import csv
import json
import os
import statistics
from collections import Counter

R = r"D:\steve\pilot\runs"
ARMS = {
    ("A1", "wire_only"): rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    ("A1", "overlay"):   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
    ("A2", "wire_only"): rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    ("A2", "overlay"):   rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
}
RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
GATE_VALUE = 35.0


def main() -> int:
    lines, rows, dist_rows = [], [], []
    def emit(s=""):
        print(s, flush=True)
        lines.append(s)

    emit("=" * 84)
    emit("OPERATOR ADVANCE SPEED, per arm, from the logged traces")
    emit("=" * 84)
    emit("35 mm/s is the proximity-gate SUBSTITUTE translation (run_coronary.py:708), not a")
    emit("default operating speed. Everything else is chosen by the operator.")
    emit("Translation 0 = a step on which the operator did not advance (rotate, hold, retract).")
    emit("")
    for (anat, arm), path in ARMS.items():
        allt, adv, n = Counter(), [], 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                n += 1
                pa = r.get("parsed_action") or {}
                t = pa.get("translation", r.get("translation"))
                if t is None:
                    continue
                t = float(t)
                allt[t] += 1
                if t > 0:
                    adv.append(t)
        at_gate = allt.get(GATE_VALUE, 0)
        med, mean = statistics.median(adv), statistics.mean(adv)
        emit(f"  {anat} {arm:<9}  steps={n:4d}  advancing={len(adv):4d}  "
             f"median advance {med:5.1f} mm/s  mean {mean:5.1f}  "
             f"at exactly {GATE_VALUE:g}: {at_gate} ({100*at_gate/n:.1f}%)")
        for val, cnt in sorted(allt.items()):
            emit(f"      {val:6g} mm/s : {cnt:5d} steps  {100.0*cnt/n:5.1f}%")
            dist_rows.append([anat, arm, f"{val:g}", cnt, n, f"{100.0*cnt/n:.1f}"])
        rows.append([anat, arm, n, len(adv), f"{med:.1f}", f"{mean:.1f}", at_gate,
                     f"{100*at_gate/n:.1f}"])

    with open(os.path.join(RESULTS, "phase7_operator_speed.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "arm", "steps", "advancing_steps", "median_advance_mm_s",
                    "mean_advance_mm_s", "steps_at_35", "pct_steps_at_35"])
        w.writerows(rows)
    with open(os.path.join(RESULTS, "phase7_operator_speed_distribution.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "arm", "translation_mm_s", "steps", "arm_steps", "pct_of_steps"])
        w.writerows(dist_rows)
    with open(os.path.join(RESULTS, "phase7_operator_speed_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    emit("")
    emit(f"wrote {os.path.join(RESULTS, 'phase7_operator_speed.csv')}")
    emit(f"wrote {os.path.join(RESULTS, 'phase7_operator_speed_distribution.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
