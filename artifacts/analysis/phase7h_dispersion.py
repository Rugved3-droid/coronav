"""Phase 7h — is the 7g variability EXCESS, or is it just binomial?

The hypothesis under test is not "the simulator is unstable". It is the simpler one: the seed
carries no information, and each episode is an independent Bernoulli draw. Those two readings
predict very different things and must not be conflated - the first is a defect, the second is
a property of the design that changes how the paper words its Methods.

Three tests, per anatomy, on the Phase 7g repetition data (A1 and A2; A3 is excluded, C11):

  1. CONCORDANCE UNDER INDEPENDENCE. Under pure independence a seed shows the same outcome in
     all R repetitions with probability p^R + (1-p)^R. Expected count vs observed count.
  2. DISPERSION. Does the across-repetition variance of the success count exceed binomial
     variance n*p*(1-p)? Reported with a chi-square dispersion statistic on R-1 df, and stated
     plainly as over-dispersed, consistent, or under-dispersed.
  3. STEPS-TO-TARGET VARIANCE COMPONENTS. Within-seed spread across repetitions against
     across-seed spread, for the continuous endpoint.

READ-ONLY. No API calls.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import stats

RESULTS = Path(__file__).resolve().parent.parent / "results"
BASE = RESULTS / "baselines"
ANATOMIES = {"a1": "A1 VMR0066", "a2": "A2 ASOCA Normal_12"}


def load(key):
    p = BASE / f"nondeterminism_floor_{key}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    passes = d["passes"]
    seeds = sorted({e["seed"] for pas in passes for e in pas if not e.get("reset_failed")})
    # outcome matrix: rows = repetitions, cols = seeds
    M = np.full((len(passes), len(seeds)), np.nan)
    S = np.full((len(passes), len(seeds)), np.nan)     # steps, successes only
    idx = {s: i for i, s in enumerate(seeds)}
    for r, pas in enumerate(passes):
        for e in pas:
            if e.get("reset_failed"):
                continue
            j = idx[e["seed"]]
            M[r, j] = 1.0 if e["success"] else 0.0
            if e["success"] and e.get("steps") is not None:
                S[r, j] = float(e["steps"])
    return d, seeds, M, S


def main() -> None:
    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 88)
    emit("PHASE 7h — IS THE VARIABILITY EXCESS, OR BINOMIAL?")
    emit("=" * 88)
    emit("")
    emit("H0 under test: the seed carries no information and each episode is an independent")
    emit("Bernoulli draw. If the data are consistent with that, the correct Methods statement")
    emit("is 'the seed does not propagate to outcomes', NOT 'the simulator is unreliable'.")

    rows = []
    for key, label in ANATOMIES.items():
        d, seeds, M, S = load(key)
        R, n = M.shape
        counts = np.nansum(M, axis=1)
        total_succ = int(np.nansum(M))
        total_trials = int(np.sum(~np.isnan(M)))
        p = total_succ / total_trials

        emit("")
        emit("=" * 88)
        emit(f"{label}   R={R} repetitions x n={n} seeds")
        emit("=" * 88)
        emit(f"  success counts per repetition: {[int(c) for c in counts]}")
        emit(f"  pooled success rate p = {total_succ}/{total_trials} = {p:.4f}")

        # ---- 1. concordance under independence
        per_seed = [M[:, j][~np.isnan(M[:, j])] for j in range(n)]
        observed_conc = sum(1 for col in per_seed if len(col) == R and len(set(col)) == 1)
        p_conc = p ** R + (1.0 - p) ** R
        expected_conc = n * p_conc
        # exact binomial test: is the observed concordance count unusual under independence?
        bt = stats.binomtest(observed_conc, n, p_conc)
        emit("")
        emit("  1. CONCORDANCE ACROSS ALL REPETITIONS")
        emit(f"     P(same outcome in all {R} | independence) = p^{R} + (1-p)^{R} = {p_conc:.4f}")
        emit(f"     expected concordant seeds = {expected_conc:.2f} of {n}")
        emit(f"     observed concordant seeds = {observed_conc} of {n}")
        emit(f"     exact binomial test vs independence: p = {bt.pvalue:.3g}")
        direction = ("MORE concordant than independence predicts"
                     if observed_conc > expected_conc else
                     "LESS concordant than independence predicts"
                     if observed_conc < expected_conc else "exactly as predicted")
        emit(f"     -> {direction}")

        # ---- 2. dispersion
        var_obs = float(np.var(counts, ddof=1))
        var_bin = n * p * (1.0 - p)
        chi2 = float(np.sum((counts - n * p) ** 2) / var_bin)
        df = R - 1
        p_over = 1.0 - stats.chi2.cdf(chi2, df)      # over-dispersion
        p_under = stats.chi2.cdf(chi2, df)           # under-dispersion
        ratio = var_obs / var_bin
        emit("")
        emit("  2. DISPERSION OF THE SUCCESS COUNT")
        emit(f"     observed variance across repetitions = {var_obs:.3f}")
        emit(f"     binomial variance n*p*(1-p)          = {var_bin:.3f}")
        emit(f"     variance ratio                       = {ratio:.3f}")
        emit(f"     dispersion statistic X2 = {chi2:.3f} on {df} df")
        emit(f"       P(X2 >= observed) = {p_over:.3g}   (over-dispersion)")
        emit(f"       P(X2 <= observed) = {p_under:.3g}   (under-dispersion)")
        if p_over < 0.05:
            verdict = "OVER-DISPERSED: variability exceeds independent Bernoulli draws"
        elif p_under < 0.05:
            verdict = "UNDER-DISPERSED: less variable than independent Bernoulli draws"
        else:
            verdict = "CONSISTENT WITH BINOMIAL: no evidence of excess variability"
        emit(f"     -> {verdict}")

        # ---- 3. steps-to-target variance components
        emit("")
        emit("  3. STEPS-TO-TARGET VARIANCE COMPONENTS")
        within = []
        for j in range(n):
            col = S[:, j][~np.isnan(S[:, j])]
            if len(col) >= 2:
                within.append(float(np.var(col, ddof=1)))
        seed_means = []
        for j in range(n):
            col = S[:, j][~np.isnan(S[:, j])]
            if len(col) >= 1:
                seed_means.append(float(np.mean(col)))
        allvals = S[~np.isnan(S)]
        if allvals.size == 0:
            emit("     no successful episodes; undefined")
            wmean = bvar = float("nan")
        else:
            wmean = float(np.mean(within)) if within else 0.0
            bvar = float(np.var(seed_means, ddof=1)) if len(seed_means) > 1 else 0.0
            emit(f"     successful episodes: {allvals.size}   distinct step counts: "
                 f"{sorted(set(int(v) for v in allvals))}")
            emit(f"     mean WITHIN-seed variance across repetitions = {wmean:.4f}")
            emit(f"     BETWEEN-seed variance of per-seed means      = {bvar:.4f}")
            if wmean == 0.0 and bvar == 0.0:
                emit("     -> DEGENERATE: every successful episode takes an identical number of")
                emit("        steps, so the continuous endpoint has ZERO variance both within and")
                emit("        across seeds. There is no steps variability to decompose; under a")
                emit("        fixed policy ALL variability lives in the binary outcome.")
            else:
                emit(f"     -> within/between ratio = "
                     f"{(wmean / bvar) if bvar > 0 else float('inf'):.3f}")

        rows.append([label, R, n, total_succ, total_trials, f"{p:.4f}",
                     observed_conc, f"{expected_conc:.2f}", f"{bt.pvalue:.4g}",
                     f"{var_obs:.4f}", f"{var_bin:.4f}", f"{ratio:.4f}",
                     f"{chi2:.4f}", df, f"{p_over:.4g}", f"{p_under:.4g}",
                     verdict.split(":")[0], f"{wmean:.4f}", f"{bvar:.4f}"])

    emit("")
    emit("=" * 88)
    emit("WHAT THIS MEANS FOR METHODS")
    emit("=" * 88)
    emit("  If both anatomies are consistent with binomial, the honest statement is that the")
    emit("  simulator seed does not propagate to episode outcomes - episodes behave as")
    emit("  independent draws - and NOT that the environment is unreliable. The run-to-run")
    emit("  range measured in 7g is then simply sampling variability at n=25, which is what")
    emit("  any n=25 binary endpoint carries, and is not evidence of a defect.")

    with open(RESULTS / "phase7h_dispersion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "repetitions", "seeds", "successes", "trials", "pooled_p",
                    "concordant_observed", "concordant_expected", "binom_p",
                    "var_observed", "var_binomial", "var_ratio",
                    "dispersion_chi2", "df", "p_overdispersion", "p_underdispersion",
                    "verdict", "steps_within_seed_var", "steps_between_seed_var"])
        w.writerows(rows)

    (RESULTS / "phase7h_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase7h_report.txt'}")
    emit(f"wrote {RESULTS/'phase7h_dispersion.csv'}")


if __name__ == "__main__":
    main()
