"""Phase 7i — is seed-matching doing any work? This decides the primary test.

Pairing only buys something if the two arms are CORRELATED at the same seed. If the seed
carries no information (Phase 7h), the within-pair correlation is ~0, seed-matching removes no
shared variance, and the paired test is not the appropriate primary analysis - it is simply a
test with fewer degrees of freedom.

This bears directly on the A1 rotation endpoint, which fell from unpaired p = 0.0004 to paired
p = 0.0147 when we adopted Reviewer 2's matched analysis.

PROCEDURE, IN THIS ORDER, so the data select the test rather than the test selecting the data:
  1. compute the within-pair correlation (Pearson and Spearman, with CIs);
  2. compute the paired test's efficiency relative to unpaired given that correlation;
  3. only then state which test is primary.

Both tests are reported in the paper regardless of which is primary, with the correlation as
the stated justification.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase5_multiplicity import TRACES, load, pair_arms, paired_wilcoxon

# The paired test MUST come from phase5's helper, not from a bare scipy call. PRESPEC fixes the
# normal approximation WITH continuity correction; scipy's default is correction=False, and an
# earlier version of this file called stats.wilcoxon directly and so reported A2 f_rot_LM as
# p=0.000438 where phase5 reported 0.000482 (and A2 steps as 1.175e-05 where 6h reported
# 1.25e-05). Same data, same statistic, two answers. One implementation, imported.

RESULTS = Path(__file__).resolve().parent.parent / "results"
ALPHA = 0.05


def fisher_ci(r, n, kind="pearson"):
    """Fisher z CI. The Spearman variant uses the standard 1.06/(n-3) inflation."""
    if not np.isfinite(r) or n < 5 or abs(r) >= 1.0:
        return (float("nan"), float("nan"))
    z = np.arctanh(r)
    se = (1.0 / np.sqrt(n - 3)) if kind == "pearson" else np.sqrt(1.06 / (n - 3))
    lo, hi = z - 1.96 * se, z + 1.96 * se
    return float(np.tanh(lo)), float(np.tanh(hi))


def corr_block(x, y, label, emit):
    """Correlation between arms at the same seed, with degeneracy handled explicitly."""
    n = len(x)
    sx, sy = float(np.std(x)), float(np.std(y))
    if sx < 1e-12 or sy < 1e-12:
        which = "wire_only" if sx < 1e-12 else "overlay"
        emit(f"    {label}: UNDEFINED — the {which} arm is CONSTANT across all {n} seeds")
        emit(f"      (sd_wire_only={sx:.3e}, sd_overlay={sy:.3e}). A constant variable has no")
        emit("      shared variance to remove, so pairing is definitionally useless here.")
        return {"n": n, "pearson": float("nan"), "spearman": float("nan"),
                "p_p": float("nan"), "p_s": float("nan"),
                "pearson_lo": float("nan"), "pearson_hi": float("nan"),
                "degenerate": True}
    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    plo, phi = fisher_ci(pr, n, "pearson")
    slo, shi = fisher_ci(sr, n, "spearman")
    emit(f"    {label}: n={n}")
    emit(f"      Pearson  r = {pr:+.3f}  95% CI [{plo:+.3f}, {phi:+.3f}]  p = {pp:.3g}")
    emit(f"      Spearman r = {sr:+.3f}  95% CI [{slo:+.3f}, {shi:+.3f}]  p = {sp:.3g}")
    return {"n": n, "pearson": float(pr), "spearman": float(sr),
            "p_p": float(pp), "p_s": float(sp),
            "pearson_lo": plo, "pearson_hi": phi, "degenerate": False}


def efficiency(x, y, r, emit):
    """Variance of the paired difference vs the unpaired contrast, given the correlation."""
    vx, vy = float(np.var(x, ddof=1)), float(np.var(y, ddof=1))
    sx, sy = np.sqrt(vx), np.sqrt(vy)
    v_unpaired = vx + vy
    v_paired = vx + vy - 2.0 * r * sx * sy if np.isfinite(r) else float("nan")
    ratio = (v_unpaired / v_paired) if (np.isfinite(v_paired) and v_paired > 0) else float("nan")
    emit(f"      Var(unpaired contrast) = {v_unpaired:.6g}")
    emit(f"      Var(paired difference) = {v_paired:.6g}")
    if np.isfinite(ratio):
        emit(f"      variance ratio (unpaired/paired) = {ratio:.4f}   "
             f"-> pairing removes {100.0 * (1 - 1 / ratio):+.1f}% of the contrast variance")
        emit(f"      NOTE: pairing also costs degrees of freedom (n-1 = {len(x)-1} vs "
             f"2n-2 = {2*len(x)-2}).")
        if ratio < 1.02:
            emit("      -> pairing removes essentially NO shared variance while costing df:")
            emit("         the paired test is the LESS efficient choice here.")
    return {"var_unpaired": v_unpaired, "var_paired": v_paired, "eff_ratio": ratio}


def main() -> None:
    data = {k: load(p) for k, p in TRACES.items()}
    out, rows = [], []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 88)
    emit("PHASE 7i — IS SEED-MATCHING DOING ANY WORK?")
    emit("=" * 88)
    emit("")
    emit("Correlation is computed FIRST and recorded, then it selects the test. The primary")
    emit("test is not chosen by which p-value is smaller.")

    for an in ("A1", "A2"):
        wo_all, ov_all = data[(an, "wire_only")], data[(an, "overlay")]
        wo = {s: v for s, v in wo_all.items() if v["analysed"]}
        ov = {s: v for s, v in ov_all.items() if v["analysed"]}

        emit("")
        emit("=" * 88)
        emit(f"{an}")
        emit("=" * 88)

        # --- endpoint 1: f_rot_LM
        seeds, x, y = pair_arms(wo, ov)
        emit("")
        emit("  ENDPOINT: f_rot_LM (LM-phase rotation-movement fraction)")
        c = corr_block(x, y, "within-pair correlation", emit)
        if not c["degenerate"]:
            e = efficiency(x, y, c["pearson"], emit)
        else:
            e = {"var_unpaired": float("nan"), "var_paired": float("nan"),
                 "eff_ratio": float("nan")}
        wil = paired_wilcoxon(x, y)
        mw = stats.mannwhitneyu(y, x, alternative="two-sided")
        emit(f"      paired Wilcoxon   W={wil['W']:.1f}  p={wil['p']:.4g}  ({wil['method']}, "
             f"{wil['n_nonzero']}/{wil['n']} informative)")
        emit(f"      unpaired Mann-Whitney U={mw.statistic:.1f}  p={mw.pvalue:.4g}")
        rows.append([an, "f_rot_LM", c["n"], f"{c['pearson']:.4f}", f"{c['pearson_lo']:.4f}",
                     f"{c['pearson_hi']:.4f}", f"{c['spearman']:.4f}", f"{c['p_s']:.4g}",
                     f"{e['eff_ratio']:.4f}", f"{wil['p']:.4g}", f"{mw.pvalue:.4g}",
                     "degenerate" if c["degenerate"] else "ok"])

        # --- endpoint 2: steps-to-target, on seeds where BOTH arms succeeded
        both = sorted(s for s in set(wo) & set(ov)
                      if wo[s]["success"] and ov[s]["success"])
        emit("")
        emit(f"  ENDPOINT: steps-to-target (seeds where BOTH arms succeeded, n={len(both)})")
        if len(both) >= 5:
            sx = np.array([wo[s]["n_rows"] for s in both], float)
            sy = np.array([ov[s]["n_rows"] for s in both], float)
            c2 = corr_block(sx, sy, "within-pair correlation", emit)
            if not c2["degenerate"]:
                e2 = efficiency(sx, sy, c2["pearson"], emit)
            else:
                e2 = {"eff_ratio": float("nan")}
            w2 = paired_wilcoxon(sx, sy)
            m2 = stats.mannwhitneyu(sy, sx, alternative="two-sided")
            emit(f"      paired Wilcoxon   W={w2['W']:.1f}  p={w2['p']:.4g}  ({w2['method']}, "
                 f"{w2['n_nonzero']}/{w2['n']} informative)")
            emit(f"      unpaired Mann-Whitney U={m2.statistic:.1f}  p={m2.pvalue:.4g}")
            emit("      CAVEAT: conditioning on both arms succeeding is the very selection")
            emit("      Reviewer 2 flagged (C1). Reported here only to characterise the")
            emit("      correlation, not as an endpoint.")
            rows.append([an, "steps_both_succeed", c2["n"], f"{c2['pearson']:.4f}",
                         f"{c2['pearson_lo']:.4f}", f"{c2['pearson_hi']:.4f}",
                         f"{c2['spearman']:.4f}", f"{c2['p_s']:.4g}",
                         f"{e2['eff_ratio']:.4f}", f"{w2['p']:.4g}", f"{m2.pvalue:.4g}",
                         "degenerate" if c2["degenerate"] else "ok"])
        else:
            emit(f"      too few both-succeed seeds (n={len(both)}) to estimate a correlation")

    emit("")
    emit("=" * 88)
    emit("DECISION RULE, STATED BEFORE THE NUMBERS WERE SEEN")
    emit("=" * 88)
    emit("  correlation near zero  -> seed-matching removes no shared variance; pairing is")
    emit("                            unjustified; the unpaired Mann-Whitney is primary.")
    emit("  correlation positive   -> pairing does real work; the paired result stays primary.")
    emit("  Both tests are reported in the paper either way, with the correlation given as the")
    emit("  justification for the choice.")

    with open(RESULTS / "phase7i_pairing.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "endpoint", "n_pairs", "pearson_r", "pearson_ci_lo",
                    "pearson_ci_hi", "spearman_r", "spearman_p", "efficiency_ratio",
                    "paired_wilcoxon_p", "unpaired_mannwhitney_p", "status"])
        w.writerows(rows)

    (RESULTS / "phase7i_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase7i_report.txt'}")
    emit(f"wrote {RESULTS/'phase7i_pairing.csv'}")


if __name__ == "__main__":
    main()
