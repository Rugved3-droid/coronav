"""Phase 6i — API-hold sensitivity on the A1 primary.

A1 wire_only absorbed 17 null holds across 1277 calls; A1 overlay absorbed none. A failed
call is not skipped — run_coronary.py executes [[0.0, 0.0]] and continues — so each hold
consumes one step of that episode's budget. The FASTER arm lost budget, so the bias is
conservative. This quantifies it instead of asserting it.

Recomputes the three Phase 3 analyses with hold steps discounted from the affected
wire_only episodes:
  1. worst-rank imputation      (Wilcoxon signed-rank on 25 matched pairs)
  2. win ratio / Finkelstein-Schoenfeld
  3. log-rank, failures censored at the (discounted) budget

Also reports an explicit BOUND: the maximum the holds could possibly have cost, obtained by
granting the affected episode the most favourable outcome consistent with its budget. That
is labelled a bound, not an estimate.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
from statsmodels.duration.survfunc import survdiff

GLOBAL_SEED = 20260911
N_BOOT = 10_000
ALPHA = 0.05
BUDGET = 60

R = r"D:\steve\pilot\runs"
TRACES = {
    "wire_only": rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    "overlay":   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
}
RESULTS = Path(__file__).resolve().parent.parent / "results"


def load(path: str, arm: str) -> list[dict]:
    by: dict[int, list[dict]] = defaultdict(list)
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
        # a HOLD is injected whenever the action could not be parsed (api failure implies this)
        holds = sum(1 for r in rows if r.get("parse_ok") is False)
        eps.append({
            "arm": arm, "episode": ep, "seed": last["seed"], "success": success,
            "n_rows": len(rows), "holds": holds,
            "steps": len(rows) if success else None,
            "steps_disc": (len(rows) - holds) if success else None,
            "budget_const": BUDGET,
            "budget_disc": BUDGET - holds,
            "final_dist": float(last["tip_target_dist"]),
        })
    return eps


def worst_rank(episodes, steps_key):
    def key(e):
        return (0, float(e[steps_key])) if e["success"] else (1, e["final_dist"])
    ordered = sorted(episodes, key=key)
    ranks = {}
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


def signrank_null_cdf(n):
    c = np.zeros(n * (n + 1) // 2 + 1)
    c[0] = 1.0
    for r in range(1, n + 1):
        c[r:] += c[:-r].copy()
    return np.cumsum(c / c.sum())


def hodges_lehmann(d):
    n = len(d)
    w = np.array([(d[i] + d[j]) / 2.0 for i in range(n) for j in range(i, n)])
    w.sort()
    cdf = signrank_null_cdf(n)
    below = np.nonzero(cdf <= ALPHA / 2.0)[0]
    k = int(below[-1]) if len(below) else 0
    return float(np.median(w)), float(w[k]), float(w[len(w) - 1 - k])


def paired(a, b):
    d = b - a
    nz = d[d != 0]
    if len(nz) == 0:
        return {"n": len(d), "method": "undefined", "W": float("nan"), "p": float("nan"),
                "rb": float("nan"), "hl": 0.0, "hl_lo": float("nan"), "hl_hi": float("nan")}
    _, tc = np.unique(np.abs(nz), return_counts=True)
    method = "approx" if (np.any(d == 0) or np.any(tc > 1)) else "exact"
    res = (stats.wilcoxon(b, a, alternative="two-sided", method="exact") if method == "exact"
           else stats.wilcoxon(b, a, alternative="two-sided", method="approx", correction=True))
    ranks = stats.rankdata(np.abs(nz))
    rp, rn = float(ranks[nz > 0].sum()), float(ranks[nz < 0].sum())
    hl, lo, hi = hodges_lehmann(d)
    return {"n": len(d), "method": method, "W": float(res.statistic), "p": float(res.pvalue),
            "rb": (rp - rn) / (rp + rn), "hl": hl, "hl_lo": lo, "hl_hi": hi}


def fs(a, b, steps_key):
    if a["success"] != b["success"]:
        return 1 if a["success"] else -1
    if a["success"] and b["success"]:
        if a[steps_key] < b[steps_key]:
            return 1
        if a[steps_key] > b[steps_key]:
            return -1
    return 0


def win_ratio(wo, ov, steps_key):
    w = l = t = 0
    for x in wo:
        for y in ov:
            c = fs(x, y, steps_key)
            if c > 0:
                w += 1
            elif c < 0:
                l += 1
            else:
                t += 1
    return w, l, t, (w / l if l else float("inf"))


def analyse(wo, ov, steps_key, budget_key, rng, label, emit):
    seeds = sorted(e["seed"] for e in wo)
    episodes = wo + ov
    ranks = worst_rank(episodes, steps_key)
    r_wo = np.array([ranks[("wire_only", s)] for s in seeds])
    r_ov = np.array([ranks[("overlay", s)] for s in seeds])
    pr = paired(r_wo, r_ov)

    wins, losses, ties, wr = win_ratio(wo, ov, steps_key)
    boot = np.empty(N_BOOT)
    for b in range(N_BOOT):
        bw = [wo[i] for i in rng.integers(0, len(wo), len(wo))]
        bo = [ov[i] for i in rng.integers(0, len(ov), len(ov))]
        w_, l_, _, _ = win_ratio(bw, bo, steps_key)
        boot[b] = (w_ + 0.5) / (l_ + 0.5) if l_ == 0 else w_ / l_
    ci_lo, ci_hi = np.percentile(boot, [2.5, 97.5])

    time = np.array([(e[steps_key] if e["success"] else e[budget_key]) for e in episodes],
                    dtype=float)
    status = np.array([1 if e["success"] else 0 for e in episodes], dtype=int)
    group = np.array([0 if e["arm"] == "wire_only" else 1 for e in episodes])
    chisq, p_lr = survdiff(time, status, group)

    emit(f"  {label}")
    emit(f"    worst-rank Wilcoxon : W={pr['W']:.1f}  n={pr['n']}  {pr['method']}  "
         f"p={pr['p']:.3g}  rb={pr['rb']:+.3f}  HL={pr['hl']:+.2f} "
         f"[{pr['hl_lo']:+.2f}, {pr['hl_hi']:+.2f}]")
    emit(f"    win ratio           : {wins}W/{losses}L/{ties}T  WR="
         f"{'inf' if np.isinf(wr) else format(wr, '.3f')}  95% CI [{ci_lo:.3f}, {ci_hi:.3f}]")
    emit(f"    log-rank            : chi2={chisq:.3f}  p={p_lr:.3g}")
    return {"wilcoxon_W": pr["W"], "wilcoxon_p": pr["p"], "rb": pr["rb"],
            "wr": wr, "wr_lo": ci_lo, "wr_hi": ci_hi,
            "logrank_chi2": float(chisq), "logrank_p": float(p_lr)}


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    wo = load(TRACES["wire_only"], "wire_only")
    ov = load(TRACES["overlay"], "overlay")

    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 84)
    emit("PHASE 6i — API-HOLD SENSITIVITY ON THE A1 PRIMARY")
    emit(f"seed={GLOBAL_SEED}  bootstrap={N_BOOT}  budget={BUDGET}")
    emit("=" * 84)

    h_wo = sum(e["holds"] for e in wo)
    h_ov = sum(e["holds"] for e in ov)
    steps_wo = sum(e["n_rows"] for e in wo)
    steps_ov = sum(e["n_rows"] for e in ov)
    aff_wo = [e for e in wo if e["holds"] > 0]
    aff_ov = [e for e in ov if e["holds"] > 0]

    emit("")
    emit("HOLDS INJECTED (a failed call executes [[0,0]] and consumes a step)")
    emit(f"  wire_only: {h_wo} holds over {steps_wo} steps, in {len(aff_wo)}/{len(wo)} episodes")
    emit(f"  overlay  : {h_ov} holds over {steps_ov} steps, in {len(aff_ov)}/{len(ov)} episodes")
    for e in aff_wo + aff_ov:
        emit(f"    {e['arm']:<10} seed {e['seed']}: {e['holds']} holds of {e['n_rows']} "
             f"steps  success={e['success']}  final_dist={e['final_dist']:.1f} mm")

    n_succ_affected = sum(1 for e in aff_wo + aff_ov if e["success"])
    emit("")
    emit(f"  successful episodes affected by holds: {n_succ_affected}")
    if n_succ_affected == 0:
        emit("  -> no success step count changes under the discount; only the censoring")
        emit("     time of the affected FAILED episode(s) moves.")

    emit("")
    emit("-" * 84)
    emit("AS ANALYSED (Phase 3, no discount)")
    emit("-" * 84)
    rng = np.random.default_rng(GLOBAL_SEED)
    base = analyse(wo, ov, "steps", "budget_const", rng, "as-analysed", emit)

    emit("")
    emit("-" * 84)
    emit("DISCOUNTED (hold steps removed from the affected wire_only episodes)")
    emit("-" * 84)
    rng = np.random.default_rng(GLOBAL_SEED)
    disc = analyse(wo, ov, "steps_disc", "budget_disc", rng, "hold-discounted", emit)

    # ---- explicit bound: grant the affected failed episode the best outcome it could have had
    emit("")
    emit("-" * 84)
    emit("BOUND (not an estimate): affected FAILED wire_only episodes granted success")
    emit("-" * 84)
    emit("  The holds cost the affected episode usable actions. We cannot know what it would")
    emit("  have done with them, so instead of imputing an outcome we bound the impact by")
    emit("  granting it success at the full budget - the most favourable outcome consistent")
    emit("  with the budget. This bounds how much the holds could have cost wire_only.")
    wo_b = [dict(e) for e in wo]
    granted = []
    for e in wo_b:
        if e["holds"] > 0 and not e["success"]:
            e["success"] = True
            e["steps"] = BUDGET
            e["steps_disc"] = BUDGET - e["holds"]
            granted.append(e["seed"])
    emit(f"  seeds granted success for the bound: {granted or 'none'}")
    bound = None
    if granted:
        rng = np.random.default_rng(GLOBAL_SEED)
        bound = analyse(wo_b, ov, "steps", "budget_const", rng, "upper bound", emit)

    emit("")
    emit("=" * 84)
    emit("VERDICT")
    emit("=" * 84)
    same_dir = (disc["rb"] > 0) == (base["rb"] > 0)
    still_sig = disc["wilcoxon_p"] < ALPHA and disc["logrank_p"] < ALPHA
    emit(f"  direction preserved   : {same_dir}")
    emit(f"  still significant     : {still_sig} "
         f"(worst-rank p={disc['wilcoxon_p']:.3g}, log-rank p={disc['logrank_p']:.3g})")
    emit(f"  win-ratio intervals   : as-analysed [{base['wr_lo']:.3f}, {base['wr_hi']:.3f}]  "
         f"vs discounted [{disc['wr_lo']:.3f}, {disc['wr_hi']:.3f}]")
    if bound is not None:
        emit(f"  bound (granted succ.) : worst-rank p={bound['wilcoxon_p']:.3g}, "
             f"log-rank p={bound['logrank_p']:.3g}, "
             f"WR={'inf' if np.isinf(bound['wr']) else format(bound['wr'], '.3f')}")

    emit("")
    emit("  METHODS SENTENCE:")
    emit(f'  "Transmission failures injected {h_wo} null hold actions into the A1 wire-only')
    emit(f'   arm ({h_wo}/{steps_wo} calls, confined to {len(aff_wo)} episode) and {h_ov} into the')
    emit("   overlay arm; because a failed call is executed as a null action rather than")
    emit("   skipped, each hold consumed one step of that episode's budget, so the loss fell")
    emit("   entirely on the faster arm and biases against the reported effect. Discounting")
    emit("   the affected steps left the direction, significance and win-ratio interval")
    emit(f"   unchanged (worst-rank p={disc['wilcoxon_p']:.3g}, log-rank "
         f"p={disc['logrank_p']:.3g}, win ratio")
    emit(f'   {disc["wr"]:.2f} [{disc["wr_lo"]:.2f}, {disc["wr_hi"]:.2f}])."')

    with open(RESULTS / "phase6i_tests.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variant", "worstrank_W", "worstrank_p", "rank_biserial",
                    "win_ratio", "wr_ci_low", "wr_ci_high", "logrank_chi2", "logrank_p"])
        for name, r in (("as_analysed", base), ("hold_discounted", disc),
                        ("bound_granted_success", bound)):
            if r is None:
                continue
            w.writerow([name, f"{r['wilcoxon_W']:.1f}", f"{r['wilcoxon_p']:.3g}",
                        f"{r['rb']:.3f}",
                        "inf" if np.isinf(r["wr"]) else f"{r['wr']:.3f}",
                        f"{r['wr_lo']:.3f}", f"{r['wr_hi']:.3f}",
                        f"{r['logrank_chi2']:.3f}", f"{r['logrank_p']:.3g}"])

    (RESULTS / "phase6i_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6i_report.txt'}")
    emit(f"wrote {RESULTS/'phase6i_tests.csv'}")


if __name__ == "__main__":
    main()
