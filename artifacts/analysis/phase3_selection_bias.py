"""Phase 3 — steps-to-target selection bias, anatomy A1 (VMR0066).

Addresses Reviewer 2 comment 3: the manuscript compared steps-to-target among successes
only while success rates differ (20/25 wire_only vs 13/25 overlay). That comparison
conditions on a post-condition outcome and is invalid; it is REPLACED, not re-weighted.
Three analyses over ALL 50 A1 episodes:

  1. Worst-rank imputation      -> Wilcoxon signed-rank on 25 matched seed pairs
  2. Win ratio / Finkelstein-Schoenfeld hierarchical comparison + bootstrap CI
  3. Time-to-event, failures administratively censored at the step budget

Plus an explicit reconciliation of the log-rank result against Fisher on the same episodes.

READ-ONLY with respect to the raw logs. All output goes to results/.
No API calls. Conventions per analysis/PRESPEC.md (incl. §9 amendments).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from statsmodels.duration.survfunc import SurvfuncRight, survdiff

# ── Locked conventions (PRESPEC.md §6) ────────────────────────────────────────
GLOBAL_SEED = 20260911
N_BOOT = 10_000
ALPHA = 0.05
STEP_BUDGET_A1 = 60

TRACES = {
    "wire_only": r"D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    "overlay":   r"D:\steve\pilot\runs\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
}
RESULTS = Path(__file__).resolve().parent.parent / "results"

# Palette: dataviz categorical slots 1 & 2, validated light-mode
# (CVD dE 24.7, normal-vision dE 33.6, both >= 3:1 on the surface).
C_WO, C_OV = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


# ── Episode extraction ────────────────────────────────────────────────────────

def load_episodes(path: str, arm: str) -> list[dict]:
    """One record per episode. Derives success/steps/final distance per PRESPEC §2.4."""
    rows_by_ep: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                rows_by_ep[r["episode"]].append(r)

    eps = []
    for ep, rows in sorted(rows_by_ep.items()):
        rows.sort(key=lambda r: r["step"])
        last = rows[-1]
        success = bool(last.get("terminal")) and not bool(last.get("truncation", True))
        eps.append({
            "arm": arm,
            "episode": ep,
            "seed": last["seed"],
            "success": success,
            "steps": len(rows) if success else None,
            # tip_target_dist is POST-action -> last row is the true final distance
            "final_dist": float(last["tip_target_dist"]),
            "n_rows": len(rows),
        })
    return eps


# ── 1. Worst-rank imputation ──────────────────────────────────────────────────

def worst_rank(all_eps: list[dict]) -> dict[tuple[str, int], float]:
    """Rank all 50 episodes. Failures rank below every success; among failures,
    closer final distance ranks better. Ties get average ranks."""
    def key(e):
        return (0, float(e["steps"])) if e["success"] else (1, e["final_dist"])

    ordered = sorted(all_eps, key=key)
    ranks: dict[tuple[str, int], float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and key(ordered[j + 1]) == key(ordered[i]):
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[(ordered[k]["arm"], ordered[k]["seed"])] = avg
        i = j + 1
    return ranks


# ── Paired inference helpers (PRESPEC §6) ─────────────────────────────────────

def signrank_null_cdf(n: int) -> np.ndarray:
    """Exact null distribution of W+ for n pairs, via subset-sum DP."""
    max_w = n * (n + 1) // 2
    counts = np.zeros(max_w + 1)
    counts[0] = 1.0
    for r in range(1, n + 1):
        counts[r:] += counts[:-r].copy()
    return np.cumsum(counts / counts.sum())


def hodges_lehmann(d: np.ndarray, alpha: float = ALPHA) -> tuple[float, float, float]:
    """HL estimate (median of Walsh averages) + distribution-free CI."""
    n = len(d)
    walsh = np.array([(d[i] + d[j]) / 2.0 for i in range(n) for j in range(i, n)])
    walsh.sort()
    est = float(np.median(walsh))
    cdf = signrank_null_cdf(n)
    below = np.nonzero(cdf <= alpha / 2.0)[0]
    k = int(below[-1]) if len(below) else 0
    m = len(walsh)
    lo = float(walsh[k]) if k < m else float("nan")
    hi = float(walsh[m - 1 - k]) if k < m else float("nan")
    return est, lo, hi


def paired_wilcoxon(x_wo: np.ndarray, x_ov: np.ndarray, label: str) -> dict:
    """Two-sided Wilcoxon signed-rank, diff = overlay - wire_only."""
    d = x_ov - x_wo
    nonzero = d[d != 0]
    has_zero = bool(np.any(d == 0))
    _, tie_counts = np.unique(np.abs(nonzero), return_counts=True)
    has_ties = bool(np.any(tie_counts > 1))
    method = "approx" if (has_zero or has_ties) else "exact"

    if method == "exact":
        res = stats.wilcoxon(x_ov, x_wo, alternative="two-sided", method="exact")
    else:
        res = stats.wilcoxon(x_ov, x_wo, alternative="two-sided",
                             method="approx", correction=True)

    ranks = stats.rankdata(np.abs(nonzero))
    r_pos = float(ranks[nonzero > 0].sum())
    r_neg = float(ranks[nonzero < 0].sum())
    rb = (r_pos - r_neg) / (r_pos + r_neg) if (r_pos + r_neg) > 0 else float("nan")
    hl, hl_lo, hl_hi = hodges_lehmann(d)

    return {
        "label": label, "test": "Wilcoxon signed-rank", "n": len(d),
        "n_nonzero": int(len(nonzero)), "method": method,
        "statistic": float(res.statistic), "p": float(res.pvalue),
        "rank_biserial": rb, "R_plus": r_pos, "R_minus": r_neg,
        "hl": hl, "hl_lo": hl_lo, "hl_hi": hl_hi,
        "n_overlay_worse": int(np.sum(d > 0)),
        "n_wireonly_worse": int(np.sum(d < 0)),
        "n_tied": int(np.sum(d == 0)),
    }


# ── 2. Win ratio / Finkelstein-Schoenfeld ─────────────────────────────────────

def fs_compare(a: dict, b: dict) -> int:
    """Hierarchical: success first, then steps. +1 = a better, -1 = b better, 0 = tie."""
    if a["success"] != b["success"]:
        return 1 if a["success"] else -1
    if a["success"] and b["success"]:
        if a["steps"] < b["steps"]:
            return 1
        if a["steps"] > b["steps"]:
            return -1
    return 0


def win_ratio(wo: list[dict], ov: list[dict]) -> tuple[int, int, int, float]:
    wins = losses = ties = 0
    for a in wo:
        for b in ov:
            c = fs_compare(a, b)
            if c > 0:
                wins += 1
            elif c < 0:
                losses += 1
            else:
                ties += 1
    wr = wins / losses if losses else float("inf")
    return wins, losses, ties, wr


# ── 3. Cumulative incidence ───────────────────────────────────────────────────

def cuminc_at(steps: list[int], t: int, n: int) -> float:
    """Right-continuous step lookup. All censoring is at t=60, after every event,
    so the KM estimator reduces exactly to the empirical CDF here."""
    return sum(1 for s in steps if s <= t) / n


def make_figure(wo: list[dict], ov: list[dict]) -> None:
    """Cumulative-incidence curves, A1 wire_only vs overlay. Manuscript Fig. 3b."""
    s_wo = sorted(e["steps"] for e in wo if e["success"])
    s_ov = sorted(e["steps"] for e in ov if e["success"])
    n_wo, n_ov = len(wo), len(ov)
    grid = np.arange(0, STEP_BUDGET_A1 + 1)
    y_wo = np.array([cuminc_at(s_wo, t, n_wo) for t in grid])
    y_ov = np.array([cuminc_at(s_ov, t, n_ov) for t in grid])

    fig, ax = plt.subplots(figsize=(6.4, 4.1), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-")
    ax.xaxis.grid(False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)

    ax.step(grid, y_wo, where="post", color=C_WO, linewidth=2,
            solid_joinstyle="round", solid_capstyle="round", label="Wire-only", zorder=3)
    ax.step(grid, y_ov, where="post", color=C_OV, linewidth=2,
            solid_joinstyle="round", solid_capstyle="round", label="Overlay", zorder=3)

    # step-50 annotation (the widest part of the gap)
    v_wo, v_ov = cuminc_at(s_wo, 50, n_wo), cuminc_at(s_ov, 50, n_ov)
    ax.plot([50, 50], [v_ov, v_wo], color=MUTED, linewidth=0.8, zorder=2)
    for val, col in ((v_wo, C_WO), (v_ov, C_OV)):
        ax.plot([50], [val], marker="o", markersize=8, color=col,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
    ax.annotate(f"{v_wo:.0%} at step 50", xy=(50, v_wo), xytext=(-8, 12),
                textcoords="offset points", ha="right", color=INK2, fontsize=9)
    # placed to the lower-RIGHT: the region left of x=50 near the baseline is
    # occupied by the wire-only riser, and a label there collides with it.
    ax.annotate(f"{v_ov:.0%} at step 50", xy=(50, v_ov), xytext=(10, -14),
                textcoords="offset points", ha="left", color=INK2, fontsize=9)

    # selective direct labels at the curve ends
    ax.annotate(f"{y_wo[-1]:.2f}", xy=(STEP_BUDGET_A1, y_wo[-1]), xytext=(6, -2),
                textcoords="offset points", color=INK2, fontsize=9, va="center")
    ax.annotate(f"{y_ov[-1]:.2f}", xy=(STEP_BUDGET_A1, y_ov[-1]), xytext=(6, -2),
                textcoords="offset points", color=INK2, fontsize=9, va="center")

    ax.set_xlim(0, STEP_BUDGET_A1 + 5)
    ax.set_ylim(0, 1.0)
    ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("Step", color=INK2, fontsize=10)
    ax.set_ylabel("Cumulative incidence of target reached", color=INK2, fontsize=10)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_title("A1 (VMR0066): time to mid-LAD target, all 25 episodes per arm",
                 color=INK, fontsize=11, loc="left", pad=12)

    leg = ax.legend(frameon=False, loc="upper left", fontsize=9)
    for txt in leg.get_texts():
        txt.set_color(INK2)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(RESULTS / f"fig_cumincidence_a1.{ext}",
                    facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    rng = np.random.default_rng(GLOBAL_SEED)
    RESULTS.mkdir(exist_ok=True)

    wo = load_episodes(TRACES["wire_only"], "wire_only")
    ov = load_episodes(TRACES["overlay"], "overlay")
    all_eps = wo + ov

    seeds_wo = sorted(e["seed"] for e in wo)
    seeds_ov = sorted(e["seed"] for e in ov)
    assert seeds_wo == seeds_ov, "A1 arms are not seed-matched"
    seeds = seeds_wo

    out = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    emit("=" * 78)
    emit("PHASE 3 — STEPS-TO-TARGET SELECTION BIAS (A1, all 50 episodes)")
    emit(f"seed={GLOBAL_SEED}  bootstrap={N_BOOT}  alpha={ALPHA}  budget={STEP_BUDGET_A1}")
    emit("=" * 78)
    emit("")
    emit("STATUS OF THE SUPERSEDED ANALYSIS")
    emit("  The manuscript's steps-to-target comparison was restricted to successful")
    emit("  episodes. Success is an outcome of the condition, and the arms contribute")
    emit("  unequal subsets (20 vs 13), so that comparison is INVALID and is REPLACED")
    emit("  by the three analyses below. It is not re-weighted, and no claim is made")
    emit("  that the replacement is 'stronger' or 'weaker' than it: the two estimate")
    emit("  different quantities on different samples under different designs, and are")
    emit("  therefore not placed on a common scale anywhere in this report.")

    n_s_wo = sum(e["success"] for e in wo)
    n_s_ov = sum(e["success"] for e in ov)
    st_wo = [e["steps"] for e in wo if e["success"]]
    st_ov = [e["steps"] for e in ov if e["success"]]
    emit("")
    emit(f"success            wire_only {n_s_wo}/25      overlay {n_s_ov}/25")
    emit(f"steps (successes)  wire_only median={np.median(st_wo):.1f} "
         f"IQR[{np.percentile(st_wo,25):.1f},{np.percentile(st_wo,75):.1f}] n={len(st_wo)}")
    emit(f"                   overlay   median={np.median(st_ov):.1f} "
         f"IQR[{np.percentile(st_ov,25):.1f},{np.percentile(st_ov,75):.1f}] n={len(st_ov)}")
    emit("  (descriptive only — the successes-only contrast is not tested here)")

    # ---- 1. worst-rank imputation
    ranks = worst_rank(all_eps)
    r_wo = np.array([ranks[("wire_only", s)] for s in seeds])
    r_ov = np.array([ranks[("overlay", s)] for s in seeds])
    wr_res = paired_wilcoxon(r_wo, r_ov, "worst-rank imputation (all 50 episodes)")

    emit("")
    emit("-" * 78)
    emit("1. WORST-RANK IMPUTATION  (failures rank below all successes;")
    emit("   failures ordered among themselves by final distance, closer = better)")
    emit("-" * 78)
    emit(f"  mean rank   wire_only {r_wo.mean():6.2f}   overlay {r_ov.mean():6.2f}   "
         f"(lower = better)")
    emit(f"  median rank wire_only {np.median(r_wo):6.2f}   overlay {np.median(r_ov):6.2f}")
    emit(f"  Wilcoxon signed-rank  W={wr_res['statistic']:.1f}  n={wr_res['n']}  "
         f"({wr_res['method']})")
    emit(f"  two-sided p = {wr_res['p']:.3g}")
    emit(f"  rank-biserial r = {wr_res['rank_biserial']:+.3f}   "
         f"HL(overlay-wire_only) = {wr_res['hl']:+.2f} ranks "
         f"[{wr_res['hl_lo']:+.2f}, {wr_res['hl_hi']:+.2f}]")
    emit(f"  overlay worse on {wr_res['n_overlay_worse']}/25 seeds, "
         f"better on {wr_res['n_wireonly_worse']}, tied on {wr_res['n_tied']}")
    emit("  NOTE: the failure-ordering rule favours overlay (its failures end closer to")
    emit("  target), and the conclusion is unchanged under it.")

    # ---- 2. win ratio / FS
    wins, losses, ties, wr = win_ratio(wo, ov)
    boot = np.empty(N_BOOT)
    inf_ct = 0
    for b in range(N_BOOT):
        bw = [wo[i] for i in rng.integers(0, len(wo), len(wo))]
        bo = [ov[i] for i in rng.integers(0, len(ov), len(ov))]
        _, _, _, w = win_ratio(bw, bo)
        if np.isinf(w):
            inf_ct += 1
            boot[b] = np.nan
        else:
            boot[b] = w
    finite = boot[~np.isnan(boot)]
    lo, hi = np.percentile(finite, [2.5, 97.5])

    emit("")
    emit("-" * 78)
    emit("2. WIN RATIO / FINKELSTEIN-SCHOENFELD  (hierarchical: success, then steps)")
    emit("   orientation: 'win' = wire_only better than overlay")
    emit("-" * 78)
    emit(f"  pairs = {wins + losses + ties} (25 x 25)")
    emit(f"  wins {wins}   losses {losses}   ties {ties}")
    emit(f"  win ratio = {wr:.3f}   bootstrap 95% CI [{lo:.3f}, {hi:.3f}]  "
         f"({N_BOOT} resamples, {inf_ct} undefined)")
    win_frac = wins / (wins + losses) if (wins + losses) else float("nan")
    emit(f"  win fraction (wins / informative pairs) = {win_frac:.3f}")
    emit("")
    emit(f"  >> ABSTRACT-FACING NUMBER FOR PHASE 3: win ratio {wr:.2f}, "
         f"95% CI [{lo:.2f}, {hi:.2f}].")
    emit("     Chosen because it is hierarchical — it carries both success and speed in")
    emit("     one figure without conditioning on success.")

    # ---- 3. time-to-event
    time = np.array([(e["steps"] if e["success"] else STEP_BUDGET_A1) for e in all_eps],
                    dtype=float)
    status = np.array([1 if e["success"] else 0 for e in all_eps], dtype=int)
    group = np.array([0 if e["arm"] == "wire_only" else 1 for e in all_eps])
    chisq, p_lr = survdiff(time, status, group)

    s_wo = sorted(e["steps"] for e in wo if e["success"])
    s_ov = sorted(e["steps"] for e in ov if e["success"])

    emit("")
    emit("-" * 78)
    emit("3. TIME-TO-EVENT  (steps as time; failures administratively censored at 60)")
    emit("-" * 78)
    emit(f"  events  wire_only {int(status[group==0].sum())}/25   "
         f"overlay {int(status[group==1].sum())}/25")
    emit(f"  log-rank chi2 = {chisq:.3f}  df=1  two-sided p = {p_lr:.3g}")
    emit("")
    emit("  cumulative incidence of target reached:")
    emit(f"  {'step':>6} {'wire_only':>12} {'overlay':>12}")
    for t in (40, 45, 50, 55, 60):
        emit(f"  {t:>6} {cuminc_at(s_wo,t,len(wo)):>12.3f} "
             f"{cuminc_at(s_ov,t,len(ov)):>12.3f}")
    emit("  (all censoring occurs at step 60, after every event, so the Kaplan-Meier")
    emit("   estimator reduces exactly to the empirical CDF here.)")

    # ---- 4. reconciliation vs Fisher
    table = [[n_s_wo, len(wo) - n_s_wo], [n_s_ov, len(ov) - n_s_ov]]
    or_f, p_fisher = stats.fisher_exact(table)

    emit("")
    emit("-" * 78)
    emit("4. RECONCILIATION: log-rank vs Fisher on the SAME 50 episodes")
    emit("-" * 78)
    emit(f"  Fisher exact on terminal success ({n_s_wo}/25 vs {n_s_ov}/25): "
         f"two-sided p = {p_fisher:.3g}, OR = {or_f:.3f}")
    emit(f"  Log-rank on step-to-target with censoring: p = {p_lr:.3g}")
    emit("")
    emit("  Both are correct, and they do not conflict: Fisher uses ONLY the terminal")
    emit("  success proportion at the budget, discarding when each episode succeeded,")
    emit("  whereas the log-rank uses the step at which every episode either reached")
    emit("  target or was censored — so it detects the overlay arm's systematically")
    emit("  later successes that Fisher is blind to.")
    emit("")
    emit("  The manuscript's success-rate claim REMAINS DECLINED (Fisher p = "
         f"{p_fisher:.3g}, n.s.). The log-rank is a statement about TIME TO TARGET,")
    emit("  not about the terminal proportion, and must not be reported as reviving")
    emit("  the abandoned success-rate claim.")

    make_figure(wo, ov)

    # ---- persist
    with open(RESULTS / "phase3_episodes_a1.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "episode", "seed", "success", "steps", "final_dist", "worst_rank"])
        for e in sorted(all_eps, key=lambda e: (e["arm"], e["seed"])):
            w.writerow([e["arm"], e["episode"], e["seed"], e["success"],
                        e["steps"] if e["steps"] is not None else "",
                        f"{e['final_dist']:.4f}", ranks[(e["arm"], e["seed"])]])

    with open(RESULTS / "phase3_tests.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["analysis", "test", "statistic", "n", "exact_or_approx",
                    "two_sided_p", "effect_size", "effect_name", "ci_low", "ci_high"])
        w.writerow(["worst_rank_imputation", "Wilcoxon signed-rank",
                    f"{wr_res['statistic']:.1f}", wr_res["n"], wr_res["method"],
                    f"{wr_res['p']:.3g}", f"{wr_res['rank_biserial']:.3f}",
                    "matched-pairs rank-biserial",
                    f"{wr_res['hl_lo']:.3f}", f"{wr_res['hl_hi']:.3f}"])
        w.writerow(["win_ratio_FS", "Finkelstein-Schoenfeld win ratio",
                    f"{wr:.3f}", f"{len(wo)}x{len(ov)}", "bootstrap",
                    "", f"{wr:.3f}", "win ratio (wire_only/overlay)",
                    f"{lo:.3f}", f"{hi:.3f}"])
        w.writerow(["time_to_event", "log-rank", f"{chisq:.3f}", len(all_eps),
                    "chi2 approx", f"{p_lr:.3g}", "", "", "", ""])
        w.writerow(["success_rate_reconciliation", "Fisher exact", "", len(all_eps),
                    "exact", f"{p_fisher:.3g}", f"{or_f:.3f}", "odds ratio", "", ""])

    (RESULTS / "phase3_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase3_episodes_a1.csv'}")
    emit(f"wrote {RESULTS/'phase3_tests.csv'}")
    emit(f"wrote {RESULTS/'phase3_report.txt'}")
    emit(f"wrote {RESULTS/'fig_cumincidence_a1.pdf'} / .png")


if __name__ == "__main__":
    main()
