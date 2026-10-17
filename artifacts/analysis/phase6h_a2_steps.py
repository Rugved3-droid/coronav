"""Phase 6h — steps-to-target on A2 (ASOCA Normal_12).

A2 reaches 25/25 success in BOTH arms, so there is no selection bias and the
steps-to-target comparison is clean — unlike A1, where it required the Phase 3
worst-rank machinery.

This decides whether the promoted primary endpoint (navigation degradation) replicates
on a second genuinely patient-derived anatomy, or rests on A1 alone.

TWO THINGS THIS SCRIPT HANDLES EXPLICITLY:

  1. COMPLETE SEPARATION. If every wire_only episode is faster than every overlay
     episode, losses = 0 and the win ratio is infinite; a percentile CI on it does not
     exist. That is a property of the data, not an error. The raw value is reported as
     infinite, alongside a Haldane-Anscombe corrected stand-in (0.5 added to each cell)
     and the win FRACTION, which is always defined.

  2. THE STEP LIMIT, AND WHAT IS ACTUALLY KNOWN ABOUT IT. An earlier version of this
     script hardcoded per-arm budgets of 45 and 62 and reported a "budget asymmetry"
     counterfactual. That was wrong (CORRECTIONS.md C20): no artifact records the limit,
     no A2 episode was truncated, and 45 and 62 are simply the longest episode in each
     arm. Both arms ran under the documented common limit. This script now reports
     observed episode lengths and censoring, and asserts no per-arm budget.

READ-ONLY with respect to raw logs. No API calls.
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

GLOBAL_SEED = 20260911
N_BOOT = 10_000
ALPHA = 0.05
ROT_INTENTS = {"rotate_cw", "rotate_ccw"}

R = r"D:\steve\pilot\runs"
TRACES = {
    "wire_only": rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    "overlay":   rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
}
# Step limit passed to MaxSteps for BOTH arms: run_asoca.py ANATOMY_PARAMS["normal12"] sets
# n_steps = 120, and the script's documented full-run invocation passes no --steps override for
# either mode. It is NOT recoverable from the traces, because no A2 episode was truncated, so it
# is recorded here as the documented value rather than a measured one (CORRECTIONS.md C20).
STEP_LIMIT_DOCUMENTED = 120
RESULTS = Path(__file__).resolve().parent.parent / "results"

C_WO, C_OV = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def load(path: str) -> dict[int, dict]:
    by: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by[r["episode"]].append(r)
    out = {}
    for ep, rows in sorted(by.items()):
        rows.sort(key=lambda r: r["step"])
        last = rows[-1]
        n_valid = sum(1 for r in rows if r.get("api_ok", True) and r.get("parse_ok", True))
        success = bool(last.get("terminal")) and not bool(last.get("truncation", True))
        rot_all = sum(1 for r in rows if r.get("intended_direction", "") in ROT_INTENTS)
        rot_lm = sum(1 for r in rows
                     if r.get("tip_branch_obs", "") == "left_main"
                     and r.get("intended_direction", "") in ROT_INTENTS)
        out[last["seed"]] = {
            "episode": ep, "success": success, "steps": len(rows) if success else None,
            "n_rows": len(rows), "n_valid": n_valid, "analysed": n_valid > 0,
            "rot_all": rot_all, "rot_lm": rot_lm,
            "final_dist": float(last["tip_target_dist"]),
        }
    return out


def signrank_null_cdf(n: int) -> np.ndarray:
    counts = np.zeros(n * (n + 1) // 2 + 1)
    counts[0] = 1.0
    for r in range(1, n + 1):
        counts[r:] += counts[:-r].copy()
    return np.cumsum(counts / counts.sum())


def hodges_lehmann(d: np.ndarray):
    n = len(d)
    walsh = np.array([(d[i] + d[j]) / 2.0 for i in range(n) for j in range(i, n)])
    walsh.sort()
    cdf = signrank_null_cdf(n)
    below = np.nonzero(cdf <= ALPHA / 2.0)[0]
    k = int(below[-1]) if len(below) else 0
    return float(np.median(walsh)), float(walsh[k]), float(walsh[len(walsh) - 1 - k])


def paired(a: np.ndarray, b: np.ndarray) -> dict:
    """diff = b - a (overlay - wire_only)."""
    d = b - a
    nz = d[d != 0]
    if len(nz) == 0:
        return {"n": len(d), "n_nonzero": 0, "method": "undefined", "W": float("nan"),
                "p": float("nan"), "rb": float("nan"), "hl": 0.0,
                "hl_lo": float("nan"), "hl_hi": float("nan"), "d": d}
    _, tc = np.unique(np.abs(nz), return_counts=True)
    method = "approx" if (np.any(d == 0) or np.any(tc > 1)) else "exact"
    res = (stats.wilcoxon(b, a, alternative="two-sided", method="exact")
           if method == "exact" else
           stats.wilcoxon(b, a, alternative="two-sided", method="approx", correction=True))
    ranks = stats.rankdata(np.abs(nz))
    rp, rn = float(ranks[nz > 0].sum()), float(ranks[nz < 0].sum())
    hl, lo, hi = hodges_lehmann(d)
    return {"n": len(d), "n_nonzero": int(len(nz)), "method": method,
            "W": float(res.statistic), "p": float(res.pvalue),
            "rb": (rp - rn) / (rp + rn), "hl": hl, "hl_lo": lo, "hl_hi": hi, "d": d}


def win_ratio(wo: list[dict], ov: list[dict]):
    wins = losses = ties = 0
    for a in wo:
        for b in ov:
            if a["success"] != b["success"]:
                if a["success"]:
                    wins += 1
                else:
                    losses += 1
            elif a["success"] and b["success"]:
                if a["steps"] < b["steps"]:
                    wins += 1
                elif a["steps"] > b["steps"]:
                    losses += 1
                else:
                    ties += 1
            else:
                ties += 1
    return wins, losses, ties, (wins / losses if losses else float("inf"))


def cuminc(steps: list[int], t: int, n: int) -> float:
    return sum(1 for s in steps if s <= t) / n


def make_figure(s_wo, s_ov, n_wo, n_ov):
    grid = np.arange(0, 66)
    y_wo = np.array([cuminc(s_wo, t, n_wo) for t in grid])
    y_ov = np.array([cuminc(s_ov, t, n_ov) for t in grid])

    fig, ax = plt.subplots(figsize=(6.4, 4.1), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(0.8)

    ax.step(grid, y_wo, where="post", color=C_WO, linewidth=2, label="Wire-only", zorder=3)
    ax.step(grid, y_ov, where="post", color=C_OV, linewidth=2, label="Overlay", zorder=3)

    # The two vertical "budget" markers that used to sit at 45 and 62 are removed: they drew a
    # design parameter that does not exist. Those are the longest episode in each arm, which the
    # curves already show by reaching 1.0 there (CORRECTIONS.md C20).

    # No end labels here. Both arms reach 1.00, so the two labels land at the same y and
    # collide into an unreadable smudge — and they restate what the y-axis already shows.
    # (On the A1 figure the arms end at 0.80 vs 0.52, so there the end labels do work.)

    ax.set_xlim(0, 70)
    ax.set_ylim(0, 1.0)
    ax.set_xticks([0, 10, 20, 30, 40, 50, 60])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel("Step", color=INK2, fontsize=10)
    ax.set_ylabel("Cumulative incidence of target reached", color=INK2, fontsize=10)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_title("A2 (ASOCA Normal_12): time to mid-LAD target, 25 episodes per arm",
                 color=INK, fontsize=11, loc="left", pad=12)
    leg = ax.legend(frameon=False, loc="upper left", fontsize=9)
    for t in leg.get_texts():
        t.set_color(INK2)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(RESULTS / f"fig_cumincidence_a2.{ext}", facecolor=SURFACE,
                    bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    rng = np.random.default_rng(GLOBAL_SEED)
    RESULTS.mkdir(exist_ok=True)
    wo_all, ov_all = load(TRACES["wire_only"]), load(TRACES["overlay"])
    wo = {s: v for s, v in wo_all.items() if v["analysed"]}
    ov = {s: v for s, v in ov_all.items() if v["analysed"]}
    seeds = sorted(set(wo) & set(ov))

    out = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    emit("=" * 80)
    emit("PHASE 6h — STEPS-TO-TARGET ON A2 (ASOCA Normal_12), patient-derived")
    emit(f"seed={GLOBAL_SEED}  bootstrap={N_BOOT}  alpha={ALPHA}")
    emit("=" * 80)
    emit("")
    emit(f"analysed: wire_only {len(wo)}/{len(wo_all)}   overlay {len(ov)}/{len(ov_all)}   "
         f"complete pairs {len(seeds)}")
    n_s_wo = sum(1 for s in wo if wo[s]["success"])
    n_s_ov = sum(1 for s in ov if ov[s]["success"])
    emit(f"success : wire_only {n_s_wo}/{len(wo)}   overlay {n_s_ov}/{len(ov)}   "
         f"-> no selection bias; every episode contributes a step count")

    st_wo = np.array([wo[s]["steps"] for s in seeds], dtype=float)
    st_ov = np.array([ov[s]["steps"] for s in seeds], dtype=float)

    emit("")
    emit("STEPS TO TARGET")
    emit(f"  wire_only median {np.median(st_wo):.1f}  "
         f"IQR[{np.percentile(st_wo,25):.1f},{np.percentile(st_wo,75):.1f}]  "
         f"range [{st_wo.min():.0f}, {st_wo.max():.0f}]")
    emit(f"  overlay   median {np.median(st_ov):.1f}  "
         f"IQR[{np.percentile(st_ov,25):.1f},{np.percentile(st_ov,75):.1f}]  "
         f"range [{st_ov.min():.0f}, {st_ov.max():.0f}]")

    pr = paired(st_wo, st_ov)
    emit("")
    emit("-" * 80)
    emit("PAIRED TEST — Wilcoxon signed-rank, two-sided")
    emit("-" * 80)
    emit(f"  W = {pr['W']:.1f}   n = {pr['n']} pairs "
         f"({pr['n_nonzero']} informative)   method = {pr['method']}")
    emit(f"  two-sided p = {pr['p']:.3g}")
    emit(f"  matched-pairs rank-biserial r = {pr['rb']:+.3f}")
    emit(f"  Hodges-Lehmann (overlay - wire_only) = {pr['hl']:+.2f} steps  "
         f"95% CI [{pr['hl_lo']:+.2f}, {pr['hl_hi']:+.2f}]")
    d = pr["d"]
    emit(f"  overlay slower on {int(np.sum(d>0))}/{pr['n']} seeds, faster on "
         f"{int(np.sum(d<0))}, tied on {int(np.sum(d==0))}")

    # ---- win ratio, tolerant of complete separation
    lw, lo_ = [wo[s] for s in seeds], [ov[s] for s in seeds]
    wins, losses, ties, wr = win_ratio(lw, lo_)
    separated = (losses == 0)
    wr_hald = (wins + 0.5) / (losses + 0.5)

    boot_wr = np.empty(N_BOOT)
    boot_wf = np.empty(N_BOOT)
    sep_ct = 0
    for b in range(N_BOOT):
        bw = [lw[i] for i in rng.integers(0, len(lw), len(lw))]
        bo = [lo_[i] for i in rng.integers(0, len(lo_), len(lo_))]
        w_, l_, t_, raw = win_ratio(bw, bo)
        if np.isinf(raw):
            sep_ct += 1
        boot_wr[b] = (w_ + 0.5) / (l_ + 0.5)
        boot_wf[b] = (w_ / (w_ + l_)) if (w_ + l_) else np.nan
    ci_lo, ci_hi = np.percentile(boot_wr, [2.5, 97.5])
    wf = wins / (wins + losses) if (wins + losses) else float("nan")
    wf_fin = boot_wf[~np.isnan(boot_wf)]
    wf_lo, wf_hi = (np.percentile(wf_fin, [2.5, 97.5]) if len(wf_fin)
                    else (float("nan"), float("nan")))

    emit("")
    emit("WIN RATIO (hierarchical: success, then steps; 'win' = wire_only better)")
    emit(f"  wins {wins}  losses {losses}  ties {ties}  of {wins+losses+ties} pairs")
    if separated:
        emit("")
        emit("  *** COMPLETE SEPARATION ***")
        emit(f"      wire_only's slowest episode ({st_wo.max():.0f} steps) is faster than")
        emit(f"      overlay's fastest ({st_ov.min():.0f} steps). Every cross-arm pair is a")
        emit("      wire_only win, so losses = 0 and the raw win ratio is INFINITE.")
        emit("      A percentile CI on the raw ratio does not exist. This is a property of")
        emit("      the data, not a computational failure.")
    emit(f"  raw win ratio = {'inf' if np.isinf(wr) else format(wr, '.3f')}")
    emit(f"  Haldane-corrected win ratio = {wr_hald:.1f}   bootstrap 95% CI "
         f"[{ci_lo:.1f}, {ci_hi:.1f}]")
    emit(f"    (0.5 added to each cell; the MAGNITUDE is an artefact of that correction,")
    emit(f"     not an effect-size estimate. {sep_ct}/{N_BOOT} replicates were separated.)")
    emit(f"  win fraction = {wf:.4f}   bootstrap 95% CI [{wf_lo:.4f}, {wf_hi:.4f}]")

    emit("")
    emit("EPISODE LENGTH AND ROTATION")
    for lbl, d_ in (("wire_only", wo), ("overlay", ov)):
        tot_len = sum(d_[s]["n_rows"] for s in d_)
        tot_rot = sum(d_[s]["rot_all"] for s in d_)
        tot_rot_lm = sum(d_[s]["rot_lm"] for s in d_)
        eps_rot = sum(1 for s in d_ if d_[s]["rot_all"] > 0)
        emit(f"  {lbl:<10} total steps {tot_len:>5}   total rotate intents {tot_rot:>5} "
             f"(LM phase {tot_rot_lm:>4})   episodes with any rotation {eps_rot}/{len(d_)}")

    # ---- step limit and censoring
    n_trunc_wo = sum(1 for s in seeds if not wo[s]["success"])
    n_trunc_ov = sum(1 for s in seeds if not ov[s]["success"])
    emit("")
    emit("=" * 80)
    emit("STEP LIMIT AND CENSORING")
    emit("=" * 80)
    emit(f"  documented step limit, BOTH arms: {STEP_LIMIT_DOCUMENTED} steps")
    emit("    (run_asoca.py ANATOMY_PARAMS['normal12']; the documented full-run invocation")
    emit("     passes no --steps override for either mode)")
    emit(f"  episodes not reaching target (i.e. truncated): wire_only {n_trunc_wo}/{len(st_wo)}   "
         f"overlay {n_trunc_ov}/{len(st_ov)}")
    emit(f"  longest episode observed: wire_only {st_wo.max():.0f}   overlay {st_ov.max():.0f}")
    emit("")
    emit("  Both arms ran under the same limit and nothing was truncated, so no step count is")
    emit("  censored and the success counts are directly comparable. An earlier version of this")
    emit("  script hardcoded per-arm budgets of 45 and 62 and called the A2 success parity an")
    emit("  artefact of unequal budgets. Those two numbers are the longest episode in each arm;")
    emit("  the claim is withdrawn (CORRECTIONS.md C20). The limit itself was never persisted by")
    emit("  the harness, which is a reproducibility gap recorded rather than papered over.")

    make_figure(sorted(int(x) for x in st_wo), sorted(int(x) for x in st_ov),
                len(st_wo), len(st_ov))

    with open(RESULTS / "phase6h_pairs_a2.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "steps_wire_only", "steps_overlay", "diff_ov_minus_wo",
                    "rot_intents_wo", "rot_intents_ov", "rot_lm_wo", "rot_lm_ov"])
        for s in seeds:
            w.writerow([s, wo[s]["steps"], ov[s]["steps"],
                        ov[s]["steps"] - wo[s]["steps"],
                        wo[s]["rot_all"], ov[s]["rot_all"],
                        wo[s]["rot_lm"], ov[s]["rot_lm"]])

    with open(RESULTS / "phase6h_tests.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["analysis", "test", "statistic", "n", "exact_or_approx",
                    "two_sided_p", "effect_size", "effect_name", "ci_low", "ci_high"])
        w.writerow(["A2_steps_to_target", "Wilcoxon signed-rank", f"{pr['W']:.1f}",
                    pr["n"], pr["method"], f"{pr['p']:.3g}", f"{pr['rb']:.3f}",
                    "matched-pairs rank-biserial", f"{pr['hl_lo']:.3f}", f"{pr['hl_hi']:.3f}"])
        w.writerow(["A2_win_ratio",
                    "Finkelstein-Schoenfeld win ratio",
                    "inf (complete separation)" if separated else f"{wr:.3f}",
                    f"{len(seeds)}x{len(seeds)}", "bootstrap", "",
                    f"{wr_hald:.1f} (Haldane-corrected)",
                    "win ratio (wire_only/overlay)", f"{ci_lo:.1f}", f"{ci_hi:.1f}"])
        w.writerow(["A2_win_fraction", "bootstrap percentile", f"{wf:.4f}",
                    f"{len(seeds)}x{len(seeds)}", "bootstrap", "", f"{wf:.4f}",
                    "wins / informative pairs", f"{wf_lo:.4f}", f"{wf_hi:.4f}"])
        w.writerow(["A2_step_limit_and_censoring", "descriptive",
                    f"truncated {n_trunc_wo}/{len(st_wo)} vs {n_trunc_ov}/{len(st_ov)}",
                    len(seeds), "n/a", "",
                    f"documented limit {STEP_LIMIT_DOCUMENTED} steps, both arms",
                    "episodes truncated at the step limit (none; nothing censored)", "", ""])

    (RESULTS / "phase6h_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6h_report.txt'}")
    emit(f"wrote {RESULTS/'phase6h_pairs_a2.csv'}")
    emit(f"wrote {RESULTS/'phase6h_tests.csv'}")
    emit(f"wrote {RESULTS/'fig_cumincidence_a2.pdf'} / .png")


if __name__ == "__main__":
    main()
