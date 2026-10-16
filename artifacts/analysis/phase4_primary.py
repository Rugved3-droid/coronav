"""Phase 4 — primary endpoint, matched design. Anatomy A1 (VMR0066).

Primary: f_rot_LM (LM-phase rotation-movement fraction), wire_only vs overlay,
Wilcoxon signed-rank on 25 seed-matched pairs, two-sided, alpha 0.05.

Also: matched-pairs rank-biserial, Hodges-Lehmann with distribution-free CI,
Mann-Whitney as a clearly-labelled secondary sensitivity line, sensitivity with and
without the 0.371 outlier episode, and design sensitivity (smallest detectable
paired effect at n=25, 80% power).

READ-ONLY with respect to raw logs. No API calls. Conventions per analysis/PRESPEC.md.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from statsmodels.stats.power import TTestPower

GLOBAL_SEED = 20260911
ALPHA = 0.05
N_POWER_SIM = 4000

TRACES = {
    "wire_only": r"D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    "overlay":   r"D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
}
RESULTS = Path(__file__).resolve().parent.parent / "results"
ROT_INTENTS = {"rotate_cw", "rotate_ccw"}


# ── Primary metric (PRESPEC §2.3) ─────────────────────────────────────────────

def f_rot_lm(rows: list[dict]) -> float | None:
    """LM-phase rotation-movement fraction for one episode.

    sum(|dist_delta|) over LM rotation rows / sum(|dist_delta|) over all LM rows.
    Valid rows only (api_ok AND parse_ok). Returns None if undefined.
    """
    valid = [r for r in rows if r.get("api_ok", True) and r.get("parse_ok", True)]
    if not valid:
        return None
    rot_sum = tot_sum = 0.0
    for r in valid:
        if r.get("tip_branch_obs", "") != "left_main":
            continue
        if "tip_target_dist_after" in r:
            dc = abs(r["tip_target_dist_after"] - r["tip_target_dist"])
        else:
            dc = abs(r.get("dist_delta", 0.0))
        is_rot = (bool(r["is_rotate_step"]) if "is_rotate_step" in r
                  else r.get("intended_direction", "") in ROT_INTENTS)
        if is_rot:
            rot_sum += dc
        tot_sum += dc
    if tot_sum == 0.0:
        return None
    return rot_sum / tot_sum


def load_arm(path: str) -> dict[int, float]:
    """seed -> f_rot_LM, one entry per episode with a defined metric."""
    by_ep: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by_ep[r["episode"]].append(r)
    out = {}
    for ep, rows in sorted(by_ep.items()):
        rows.sort(key=lambda r: r["step"])
        v = f_rot_lm(rows)
        if v is not None:
            out[rows[-1]["seed"]] = v
    return out


# ── Paired inference (shared conventions) ─────────────────────────────────────

def signrank_null_cdf(n: int) -> np.ndarray:
    max_w = n * (n + 1) // 2
    counts = np.zeros(max_w + 1)
    counts[0] = 1.0
    for r in range(1, n + 1):
        counts[r:] += counts[:-r].copy()
    return np.cumsum(counts / counts.sum())


def hodges_lehmann(d: np.ndarray, alpha: float = ALPHA):
    n = len(d)
    walsh = np.array([(d[i] + d[j]) / 2.0 for i in range(n) for j in range(i, n)])
    walsh.sort()
    est = float(np.median(walsh))
    cdf = signrank_null_cdf(n)
    below = np.nonzero(cdf <= alpha / 2.0)[0]
    k = int(below[-1]) if len(below) else 0
    m = len(walsh)
    return est, float(walsh[k]), float(walsh[m - 1 - k])


def paired_test(x_wo: np.ndarray, x_ov: np.ndarray) -> dict:
    d = x_ov - x_wo
    nonzero = d[d != 0]
    has_zero = bool(np.any(d == 0))
    _, tc = np.unique(np.abs(nonzero), return_counts=True)
    has_ties = bool(np.any(tc > 1))
    method = "approx" if (has_zero or has_ties) else "exact"
    if method == "exact":
        res = stats.wilcoxon(x_ov, x_wo, alternative="two-sided", method="exact")
    else:
        res = stats.wilcoxon(x_ov, x_wo, alternative="two-sided",
                             method="approx", correction=True)
    ranks = stats.rankdata(np.abs(nonzero))
    r_pos = float(ranks[nonzero > 0].sum())
    r_neg = float(ranks[nonzero < 0].sum())
    rb = (r_pos - r_neg) / (r_pos + r_neg)
    hl, lo, hi = hodges_lehmann(d)
    return {"n": len(d), "method": method, "W": float(res.statistic),
            "p": float(res.pvalue), "rb": rb, "hl": hl, "hl_lo": lo, "hl_hi": hi,
            "n_pos": int(np.sum(d > 0)), "n_neg": int(np.sum(d < 0)),
            "n_zero": int(np.sum(d == 0)), "d": d}


def wilcoxon_1samp_prespec(d: np.ndarray):
    """One-sample signed-rank under the PRESPEC convention.

    Exact ONLY when there are no zero differences and no tied absolute differences; otherwise
    the normal approximation WITH continuity correction. This mirrors `paired_test` above and
    `phase5_multiplicity.paired_wilcoxon` exactly.

    This function exists because this simulation previously called
    `stats.wilcoxon(row, alternative="two-sided")` bare, taking scipy's method='auto' and
    correction=False - NOT the convention the analysis it calibrates actually uses. See
    results/LOG.md 2026-09-13 on two scripts disagreeing on the same statistic. Returns None
    when the sample carries no information.
    """
    nz = d[d != 0]
    if len(nz) == 0:
        return None
    _, tc = np.unique(np.abs(nz), return_counts=True)
    if np.any(d == 0) or np.any(tc > 1):
        return stats.wilcoxon(d, alternative="two-sided", method="approx", correction=True)
    return stats.wilcoxon(d, alternative="two-sided", method="exact")


def mde_wilcoxon(d_obs: np.ndarray, rng, target_power: float = 0.80):
    """Smallest detectable paired shift for the Wilcoxon signed-rank test at this n,
    simulated from the observed difference distribution centred at zero.

    Returns (mde, frac_approx) where frac_approx is the share of simulated samples that fell to
    the normal approximation at the returned delta. That number matters: resampling WITH
    REPLACEMENT from 25 observed differences induces tied absolute values that the observed
    sample may not have, so the simulated test can take the approximate branch even when the
    test actually run on the real data was exact. Reported rather than hidden.
    """
    n = len(d_obs)
    centred = d_obs - np.median(d_obs)

    def power_at(delta: float) -> tuple[float, float]:
        idx = rng.integers(0, n, (N_POWER_SIM, n))
        samples = centred[idx] + delta
        hits = evaluated = approx = 0
        for row in samples:
            try:
                res = wilcoxon_1samp_prespec(row)
            except ValueError:
                continue
            if res is None:
                continue
            evaluated += 1
            nz = row[row != 0]
            _, tc = np.unique(np.abs(nz), return_counts=True)
            if np.any(row == 0) or np.any(tc > 1):
                approx += 1
            if res.pvalue < ALPHA:
                hits += 1
        return hits / N_POWER_SIM, (approx / evaluated if evaluated else float("nan"))

    lo, hi = 0.0, float(np.max(np.abs(centred)) * 2 + 1e-9)
    for _ in range(18):
        mid = (lo + hi) / 2
        if power_at(mid)[0] < target_power:
            lo = mid
        else:
            hi = mid
    mde = (lo + hi) / 2
    return mde, power_at(mde)[1]


def main() -> None:
    rng = np.random.default_rng(GLOBAL_SEED)
    RESULTS.mkdir(exist_ok=True)

    wo = load_arm(TRACES["wire_only"])
    ov = load_arm(TRACES["overlay"])

    out = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    emit("=" * 78)
    emit("PHASE 4 — PRIMARY ENDPOINT f_rot_LM, MATCHED DESIGN (A1)")
    emit(f"seed={GLOBAL_SEED}  alpha={ALPHA}  two-sided")
    emit("=" * 78)

    # ---- pairing audit (mandatory pre-check)
    s_wo, s_ov = set(wo), set(ov)
    paired = sorted(s_wo & s_ov)
    emit("")
    emit("PAIRING AUDIT")
    emit(f"  wire_only episodes with defined metric : {len(s_wo)}")
    emit(f"  overlay   episodes with defined metric : {len(s_ov)}")
    emit(f"  seeds identical across arms            : {sorted(s_wo) == sorted(s_ov)}")
    emit(f"  COMPLETE PAIRS                         : {len(paired)}")
    only_wo, only_ov = sorted(s_wo - s_ov), sorted(s_ov - s_wo)
    emit(f"  seeds only in wire_only                : {only_wo if only_wo else 'none'}")
    emit(f"  seeds only in overlay                  : {only_ov if only_ov else 'none'}")
    if only_wo or only_ov:
        emit("  *** PAIRING INCOMPLETE — unpaired seeds listed above, none dropped silently")
    else:
        emit("  -> pairing complete; no seed dropped")

    x_wo = np.array([wo[s] for s in paired])
    x_ov = np.array([ov[s] for s in paired])

    emit("")
    emit("DESCRIPTIVE (per-episode f_rot_LM)")
    emit(f"  wire_only  median={np.median(x_wo):.4f}  "
         f"IQR[{np.percentile(x_wo,25):.4f},{np.percentile(x_wo,75):.4f}]  "
         f"mean={x_wo.mean():.4f}  n={len(x_wo)}")
    emit(f"  overlay    median={np.median(x_ov):.4f}  "
         f"IQR[{np.percentile(x_ov,25):.4f},{np.percentile(x_ov,75):.4f}]  "
         f"mean={x_ov.mean():.4f}  n={len(x_ov)}")
    emit(f"  median difference (overlay - wire_only) = "
         f"{np.median(x_ov) - np.median(x_wo):+.4f}")

    # ---- PRIMARY
    pr = paired_test(x_wo, x_ov)
    emit("")
    emit("-" * 78)
    emit("PRIMARY — Wilcoxon signed-rank, 25 seed-matched pairs, two-sided")
    emit("-" * 78)
    emit(f"  W = {pr['W']:.1f}   n = {pr['n']} pairs   method = {pr['method']}")
    emit(f"  two-sided p = {pr['p']:.3g}")
    emit(f"  matched-pairs rank-biserial r = {pr['rb']:+.3f}")
    emit(f"  Hodges-Lehmann (overlay - wire_only) = {pr['hl']:+.4f}  "
         f"95% CI [{pr['hl_lo']:+.4f}, {pr['hl_hi']:+.4f}]")
    emit(f"  overlay higher on {pr['n_pos']}/{pr['n']} seeds, lower on {pr['n_neg']}, "
         f"tied on {pr['n_zero']}")
    direction = "overlay > wire_only" if pr["hl"] > 0 else "overlay < wire_only"
    emit(f"  DIRECTION: {direction}   "
         f"{'SIGNIFICANT' if pr['p'] < ALPHA else 'NOT SIGNIFICANT'} at alpha={ALPHA}")

    # ---- SECONDARY sensitivity: Mann-Whitney
    mw = stats.mannwhitneyu(x_ov, x_wo, alternative="two-sided")
    n1, n2 = len(x_ov), len(x_wo)
    r_mw = 1.0 - (2.0 * mw.statistic) / (n1 * n2)
    emit("")
    emit("SECONDARY SENSITIVITY ONLY — Mann-Whitney U (unmatched; NOT the primary test)")
    emit(f"  U = {mw.statistic:.1f}  two-sided p = {mw.pvalue:.3g}  "
         f"rank-biserial = {abs(r_mw):.3f}")
    emit("  Reported because the manuscript used it. It ignores the matched structure")
    emit("  and is not comparable to the primary effect size above.")

    # ---- sensitivity: drop the outlier episode
    i_max = int(np.argmax(x_wo))
    emit("")
    emit("SENSITIVITY — excluding the extreme wire_only episode")
    emit(f"  excluded seed {paired[i_max]} (f_rot_LM = {x_wo[i_max]:.4f})")
    keep = np.arange(len(paired)) != i_max
    sr = paired_test(x_wo[keep], x_ov[keep])
    emit(f"  W = {sr['W']:.1f}  n = {sr['n']} pairs  method = {sr['method']}  "
         f"two-sided p = {sr['p']:.3g}")
    emit(f"  rank-biserial r = {sr['rb']:+.3f}   HL = {sr['hl']:+.4f} "
         f"[{sr['hl_lo']:+.4f}, {sr['hl_hi']:+.4f}]")
    emit("  NOTE: the paired test ranks within-seed differences, so a single extreme")
    emit("  VALUE has bounded influence by construction. Full sample stays primary.")

    # ---- design sensitivity
    d = pr["d"]
    sd_d = float(np.std(d, ddof=1))
    d_param = TTestPower().solve_power(effect_size=None, nobs=len(d), alpha=ALPHA,
                                       power=0.80, alternative="two-sided")
    mde_sim, frac_approx = mde_wilcoxon(d, rng)
    emit("")
    emit("-" * 78)
    emit("DESIGN SENSITIVITY  (n = 25 pairs, 80% power, alpha 0.05 two-sided)")
    emit("-" * 78)
    emit(f"  SD of paired differences = {sd_d:.4f}")
    emit(f"  parametric reference (paired t): smallest detectable d = {d_param:.4f}")
    emit(f"    -> raw units: {d_param * sd_d:+.4f} f_rot_LM")
    emit(f"  simulated for the Wilcoxon signed-rank actually used, resampling the")
    emit(f"    observed difference distribution centred at zero ({N_POWER_SIM} sims/step):")
    emit(f"    -> smallest detectable paired shift = {mde_sim:.4f} f_rot_LM")
    emit(f"  observed HL shift = {pr['hl']:+.4f}, i.e. "
         f"{abs(pr['hl']) / mde_sim:.2f}x the smallest detectable shift")
    emit("")
    emit(f"  METHOD MIX: {100.0 * frac_approx:.1f}% of simulated samples fell to the normal")
    emit("    approximation with continuity correction; the rest used the exact test. The test")
    emit(f"    actually run on the observed data used the {pr['method'].upper()} method.")
    emit("    Resampling with replacement induces tied absolute differences that the observed")
    emit("    sample need not have, so a mix is expected. This simulation now applies the SAME")
    emit("    exact/approx rule as the analysis (PRESPEC); it previously called scipy bare with")
    emit("    correction=False, which understated p and so understated the detectable shift.")

    with open(RESULTS / "phase4_pairs_a1.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "f_rot_LM_wire_only", "f_rot_LM_overlay", "diff_ov_minus_wo"])
        for s, a, b in zip(paired, x_wo, x_ov):
            w.writerow([s, f"{a:.6f}", f"{b:.6f}", f"{b - a:+.6f}"])

    with open(RESULTS / "phase4_tests.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["analysis", "test", "statistic", "n", "exact_or_approx",
                    "two_sided_p", "effect_size", "effect_name", "ci_low", "ci_high"])
        w.writerow(["primary_f_rot_LM_A1", "Wilcoxon signed-rank", f"{pr['W']:.1f}",
                    pr["n"], pr["method"], f"{pr['p']:.3g}", f"{pr['rb']:.3f}",
                    "matched-pairs rank-biserial", f"{pr['hl_lo']:.4f}", f"{pr['hl_hi']:.4f}"])
        w.writerow(["secondary_sensitivity_MW", "Mann-Whitney U", f"{mw.statistic:.1f}",
                    f"{n1}v{n2}", "approx", f"{mw.pvalue:.3g}", f"{abs(r_mw):.3f}",
                    "rank-biserial (unmatched)", "", ""])
        w.writerow(["sensitivity_excl_outlier", "Wilcoxon signed-rank", f"{sr['W']:.1f}",
                    sr["n"], sr["method"], f"{sr['p']:.3g}", f"{sr['rb']:.3f}",
                    "matched-pairs rank-biserial", f"{sr['hl_lo']:.4f}", f"{sr['hl_hi']:.4f}"])

    (RESULTS / "phase4_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase4_pairs_a1.csv'}")
    emit(f"wrote {RESULTS/'phase4_tests.csv'}")
    emit(f"wrote {RESULTS/'phase4_report.txt'}")


if __name__ == "__main__":
    main()
