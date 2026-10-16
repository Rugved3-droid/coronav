"""Phase 7i addendum — within-pair correlation on the PROMOTED PRIMARY endpoint.

Phase 7i measured the within-pair correlation for f_rot_LM and for steps-to-target among
both-succeed seeds. It did not measure it for the endpoint actually promoted to primary: the
worst-rank imputation over all 50 A1 episodes, tested with a paired Wilcoxon.

That matters because the conclusion could be mixed. If the worst-rank ranks ARE correlated
between arms at the same seed, pairing stays justified for navigation even though it fails for
rotation, and the two endpoints would take different primary tests.

The win ratio and the log-rank are unpaired by construction and are unaffected either way.

Ranks are built exactly as in Phase 3: every failure ranks below every success; successes are
ordered by steps, failures among themselves by final distance; ties take average ranks.

READ-ONLY. No API calls.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The paired test comes from phase5's helper, NOT a bare scipy call. PRESPEC fixes the normal
# approximation WITH continuity correction and forces it whenever zeros or ties are present;
# scipy's default is correction=False with its own auto method selection. Worst-ranks are built
# jointly across both arms with average ranks for ties, so ties are the norm here and the two
# implementations will not agree. See the note at the head of phase7i_pairing.py.
from phase5_multiplicity import paired_wilcoxon

RESULTS = Path(__file__).resolve().parent.parent / "results"
R = r"D:\steve\pilot\runs"
ARMS = {
    "wire_only": rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    "overlay":   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
}


def load_episodes(path, arm):
    by = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by[r["episode"]].append(r)
    eps = []
    for ep, rows in sorted(by.items()):
        rows.sort(key=lambda r: r["step"])
        last = rows[-1]
        success = bool(last.get("terminal")) and not bool(last.get("truncation", True))
        eps.append({"arm": arm, "seed": last["seed"], "success": success,
                    "steps": len(rows) if success else None,
                    "final_dist": float(last["tip_target_dist"])})
    return eps


def worst_rank(all_eps):
    def key(e):
        return (0, float(e["steps"])) if e["success"] else (1, e["final_dist"])
    ordered = sorted(all_eps, key=key)
    ranks, i = {}, 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and key(ordered[j + 1]) == key(ordered[i]):
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[(ordered[k]["arm"], ordered[k]["seed"])] = avg
        i = j + 1
    return ranks


def fisher_ci(r, n, kind="pearson"):
    if not np.isfinite(r) or n < 5 or abs(r) >= 1.0:
        return (float("nan"), float("nan"))
    z = np.arctanh(r)
    se = (1.0 / np.sqrt(n - 3)) if kind == "pearson" else np.sqrt(1.06 / (n - 3))
    return float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))


def main() -> None:
    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    wo = load_episodes(ARMS["wire_only"], "wire_only")
    ov = load_episodes(ARMS["overlay"], "overlay")
    ranks = worst_rank(wo + ov)
    seeds = sorted(e["seed"] for e in wo)
    x = np.array([ranks[("wire_only", s)] for s in seeds], float)
    y = np.array([ranks[("overlay", s)] for s in seeds], float)

    emit("=" * 88)
    emit("PHASE 7i ADDENDUM — within-pair correlation on the WORST-RANK endpoint (A1)")
    emit("=" * 88)
    emit("")
    emit("This is the promoted PRIMARY navigation endpoint. The win ratio and log-rank are")
    emit("unpaired by construction; only this one is tested paired.")
    emit("")
    emit(f"  n = {len(seeds)} seed pairs, ranks over all {len(wo) + len(ov)} episodes")

    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    plo, phi = fisher_ci(pr, len(seeds), "pearson")
    slo, shi = fisher_ci(sr, len(seeds), "spearman")
    emit(f"  Pearson  r = {pr:+.3f}  95% CI [{plo:+.3f}, {phi:+.3f}]  p = {pp:.3g}")
    emit(f"  Spearman r = {sr:+.3f}  95% CI [{slo:+.3f}, {shi:+.3f}]  p = {sp:.3g}")

    vx, vy = float(np.var(x, ddof=1)), float(np.var(y, ddof=1))
    v_unp = vx + vy
    v_pai = vx + vy - 2.0 * pr * np.sqrt(vx) * np.sqrt(vy)
    ratio = v_unp / v_pai if v_pai > 0 else float("nan")
    emit("")
    emit(f"  Var(unpaired contrast) = {v_unp:.4f}")
    emit(f"  Var(paired difference) = {v_pai:.4f}")
    emit(f"  variance ratio         = {ratio:.4f}  -> pairing removes "
         f"{100.0 * (1 - 1 / ratio):+.1f}% of the contrast variance")
    emit(f"  degrees of freedom: paired n-1 = {len(seeds)-1}, unpaired 2n-2 = {2*len(seeds)-2}")

    w = paired_wilcoxon(x, y)
    m = stats.mannwhitneyu(y, x, alternative="two-sided")
    emit("")
    emit(f"  paired Wilcoxon on ranks      W = {w['W']:.1f}  p = {w['p']:.4g}  "
         f"({w['method']}, {w['n_nonzero']}/{w['n']} informative)")
    emit(f"  unpaired Mann-Whitney on ranks U = {m.statistic:.1f}  p = {m.pvalue:.4g}")
    emit("")
    emit("  NOTE: the unpaired test on worst-ranks is reported for completeness only. Ranks")
    emit("  are constructed JOINTLY across both arms, so an unpaired test on them is not the")
    emit("  same object as an unpaired test on a raw endpoint; the win ratio and log-rank are")
    emit("  the proper unpaired analyses of this endpoint and already exist.")

    emit("")
    emit("=" * 88)
    emit("VERDICT FOR THIS ENDPOINT")
    emit("=" * 88)
    near_zero = abs(pr) < 0.2 and (plo < 0 < phi)
    if near_zero:
        emit("  Correlation is near zero and its CI spans zero: seed-matching removes no shared")
        emit("  variance on this endpoint either. The paired worst-rank Wilcoxon is not")
        emit("  justified by blocking, and the unpaired win ratio and log-rank - which were")
        emit("  always part of this analysis - carry it.")
    else:
        emit("  Correlation is NOT near zero on this endpoint. Pairing does real work here even")
        emit("  though it fails for f_rot_LM, so the two endpoints take DIFFERENT primary")
        emit("  tests, and that must be stated explicitly rather than harmonised away.")

    with open(RESULTS / "phase7i_worstrank_corr.csv", "w", newline="", encoding="utf-8") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["anatomy", "endpoint", "n_pairs", "pearson_r", "pearson_ci_lo",
                       "pearson_ci_hi", "pearson_p", "spearman_r", "spearman_p",
                       "var_unpaired", "var_paired", "efficiency_ratio",
                       "paired_wilcoxon_p", "unpaired_mw_p"])
        wcsv.writerow(["A1", "worst_rank", len(seeds), f"{pr:.4f}", f"{plo:.4f}",
                       f"{phi:.4f}", f"{pp:.4g}", f"{sr:.4f}", f"{sp:.4g}",
                       f"{v_unp:.4f}", f"{v_pai:.4f}", f"{ratio:.4f}",
                       f"{w['p']:.4g}", f"{m.pvalue:.4g}"])

    (RESULTS / "phase7i_worstrank_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase7i_worstrank_report.txt'}")
    emit(f"wrote {RESULTS/'phase7i_worstrank_corr.csv'}")


if __name__ == "__main__":
    main()
