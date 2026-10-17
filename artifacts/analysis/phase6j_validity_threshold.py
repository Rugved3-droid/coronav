"""Phase 6j — minimum-validity threshold sensitivity.

The Phase 6d exclusion rule removes only episodes with ZERO valid operator actions. That
admits a borderline case: V3 overlay seed 5034 is retained on 7 valid actions out of 60,
i.e. 88% of its calls failed.

This adds a minimum-validity threshold as a SENSITIVITY (not a change to the rule):
exclude any retained episode in which more than 50% of calls failed, and check what moves.
The affected episodes should be exploratory-arm only, so the confirmatory family should be
untouched — that is the claim being confirmed, not assumed.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase5_multiplicity import (ALPHA, TRACES, holm, load, n_label, paired_wilcoxon,
                                 pair_arms)

RESULTS = Path(__file__).resolve().parent.parent / "results"
FAIL_FRACTION_LIMIT = 0.50


def failed_fraction(rec: dict) -> float:
    return 1.0 - (rec["n_valid"] / rec["n_rows"]) if rec["n_rows"] else 1.0


def apply_threshold(d: dict[int, dict]) -> tuple[dict[int, dict], list[tuple[int, float]]]:
    kept, dropped = {}, []
    for seed, rec in d.items():
        if not rec["analysed"]:
            continue                      # already excluded by the 6d rule
        f = failed_fraction(rec)
        if f > FAIL_FRACTION_LIMIT:
            dropped.append((seed, f))
        else:
            kept[seed] = rec
    return kept, dropped


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    data = {k: load(p) for k, p in TRACES.items()}

    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 88)
    emit("PHASE 6j — MINIMUM-VALIDITY THRESHOLD SENSITIVITY")
    emit(f"threshold: exclude retained episodes with more than "
         f"{FAIL_FRACTION_LIMIT:.0%} failed calls")
    emit("=" * 88)

    emit("")
    emit("EPISODES CAUGHT BY THE THRESHOLD (retained under the 6d rule, dropped here)")
    caught_any = False
    rows_csv = []
    for (an, arm), d in data.items():
        _, dropped = apply_threshold(d)
        for seed, f in dropped:
            caught_any = True
            rec = d[seed]
            emit(f"  {an:<9} {arm:<10} seed {seed}: {rec['n_rows'] - rec['n_valid']}"
                 f"/{rec['n_rows']} calls failed ({f:.1%}) -> dropped in sensitivity")
            rows_csv.append([an, arm, seed, rec["n_rows"],
                             rec["n_rows"] - rec["n_valid"], f"{f:.4f}"])
    if not caught_any:
        emit("  none")

    # ---- confirmatory family under the threshold
    emit("")
    emit("-" * 88)
    emit("CONFIRMATORY FAMILY (A1 + A2) UNDER THE THRESHOLD")
    emit("-" * 88)
    conf_rows = []
    for an in ("A1", "A2"):
        wo_k, wo_d = apply_threshold(data[(an, "wire_only")])
        ov_k, ov_d = apply_threshold(data[(an, "overlay")])
        seeds, x_wo, x_ov = pair_arms(wo_k, ov_k)
        r = paired_wilcoxon(x_wo, x_ov)
        conf_rows.append((an, r, len(wo_d) + len(ov_d)))
    hp = holm([r["p"] for _, r, _ in conf_rows])
    for (an, r, n_drop), h in zip(conf_rows, hp):
        emit(f"  {an}: W={r['W']:.1f}  n={n_label(r['n'], r['n_nonzero'])} pairs  "
             f"{r['method']}  raw p={r['p']:.3g}  Holm p={h:.3g}   "
             f"(episodes dropped by threshold: {n_drop})")

    emit("")
    emit("  Reference, as committed in Phase 5 / the A1+A2 family:")
    emit("    A1  W=73.0  n=25  exact   raw p=0.0147     Holm p=0.0147")
    emit("    A2  W=0.0   n=25 (16 informative)  approx  raw p=0.000482  Holm p=0.000965")

    unchanged = (abs(conf_rows[0][1]["p"] - 0.0147) < 5e-4
                 and abs(conf_rows[1][1]["p"] - 0.000482) < 5e-5)
    emit("")
    emit(f"  CONFIRMATORY FAMILY UNCHANGED BY THE THRESHOLD: {unchanged}")

    # ---- exploratory arms that do move
    emit("")
    emit("-" * 88)
    emit("EXPLORATORY ARMS AFFECTED")
    emit("-" * 88)
    for v in ("V2", "V3", "V4"):
        wo_k, wo_d = apply_threshold(data[(v, "wire_only")])
        ov_k, ov_d = apply_threshold(data[(v, "overlay")])
        if not (wo_d or ov_d):
            emit(f"  {v}: no episodes caught; unchanged")
            continue
        seeds, x_wo, x_ov = pair_arms(wo_k, ov_k)
        before_seeds, bx_wo, bx_ov = pair_arms(
            {s: r for s, r in data[(v, "wire_only")].items() if r["analysed"]},
            {s: r for s, r in data[(v, "overlay")].items() if r["analysed"]})
        rb = paired_wilcoxon(bx_wo, bx_ov)
        if len(seeds) >= 2:
            ra = paired_wilcoxon(x_wo, x_ov)
            emit(f"  {v}: dropped {[s for s, _ in wo_d + ov_d]}")
            emit(f"      before threshold: W={rb['W']:.1f}  n={rb['n']}  p={rb['p']:.3g}")
            emit(f"      after  threshold: W={ra['W']:.1f}  n={ra['n']}  p={ra['p']:.3g}")
            rows_csv.append([v, "paired", "", "", "",
                             f"before p={rb['p']:.3g}; after p={ra['p']:.3g}"])
        else:
            emit(f"  {v}: dropped {[s for s, _ in wo_d + ov_d]}; fewer than 2 pairs remain, "
                 f"test not defined")

    with open(RESULTS / "phase6j_threshold.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy_or_variant", "arm", "seed", "n_rows", "n_failed",
                    "failed_fraction_or_note"])
        w.writerows(rows_csv)

    (RESULTS / "phase6j_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6j_report.txt'}")
    emit(f"wrote {RESULTS/'phase6j_threshold.csv'}")


if __name__ == "__main__":
    main()
