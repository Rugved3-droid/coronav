"""Phase 5 — multiplicity table.

CONFIRMATORY FAMILY (PRESPEC §4, as amended 2026-09-13): f_rot_LM, wire_only vs overlay, on
**A1 and A2 only**. A family is the set of tests we draw inferences from. A3 is excluded from
Results on physical-validity grounds (CORRECTIONS C11), so it cannot be counted in the
correction family: declaring three members while reporting two would inflate the apparent
correction burden in our own favour. A3's raw p is reported in the disposition block below and
in Section V prose, beside the exclusion reason, and is given NO adjusted p — we do not adjust a
test we are not inferring from.

PRIMARY TEST = PAIRED WILCOXON SIGNED-RANK (CORRECTIONS C14, superseding C13).

Phase 7h established that the simulator seed does not propagate to episode outcomes, and Phase
7i measured the within-pair correlation at about zero. C13 took that as licence to make the
unpaired Mann-Whitney primary. C14 reverses that switch on the precision of the correlation
itself: at n = 25, rho = -0.072 carries a 95% CI of roughly [-0.45, +0.33], which establishes
only that pairing is not demonstrably helping - NOT that pairing is unjustified. That is too
weak a basis for a 38-fold improvement in the headline p-value on a test Reviewer 2
specifically requested. The conservative matched test is retained as primary; the unpaired test
is reported alongside with rho and its CI; the conclusion is unchanged under either.

Rho is reported WITH its 95% CI everywhere it appears. A bare rho = -0.072 invites the reader
to treat an imprecise estimate as precise, which is the error C13 made.

Rotation is a SECONDARY endpoint. The paper's primary claim is navigation degradation, where
A1's win ratio and A2's complete separation are untouched by any of this.

Everything else — biplane, prompt variants, first-bifurcation branch selection, success rate,
contrast condition — is listed as exploratory with blank adjusted columns, answering Reviewer 2
comment 4 (the full multiplicity picture).

EXCLUSION RULE (PRESPEC amendment 2026-09-11, applied here to EVERY count):
  Episodes with ZERO valid operator actions (total API transmission failure) are
  EXCLUDED and leave the denominator entirely. Episodes with partial failures are
  INCLUDED. No denominator is inherited; every count traces to
  results/denominators.csv.

NOTE ON n: the Wilcoxon signed-rank drops pairs whose difference is exactly zero
(scipy zero_method='wilcox'), so the number of pairs and the number of INFORMATIVE
pairs can differ. Both are reported; the n column names the informative count
whenever it is smaller.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

GLOBAL_SEED = 20260911
ALPHA = 0.05
RESULTS = Path(__file__).resolve().parent.parent / "results"
ROT_INTENTS = {"rotate_cw", "rotate_ccw"}

# The declared inference family, and the geometry that is NOT in it.
CONFIRMATORY = ("A1", "A2")
EXCLUDED_GEOMETRY = ("A3",)
ALL_ANATOMIES = CONFIRMATORY + EXCLUDED_GEOMETRY

R = r"D:\steve\pilot\runs"
TRACES = {
    ("A1", "wire_only"): rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    ("A1", "overlay"):   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
    ("A2", "wire_only"): rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    ("A2", "overlay"):   rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
    ("A3", "wire_only"): rf"{R}\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl",
    ("A3", "overlay"):   rf"{R}\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl",
    ("V2", "wire_only"): rf"{R}\ablation_prompt_robustness\v2_neutral\wire_only\trace.jsonl",
    ("V2", "overlay"):   rf"{R}\ablation_prompt_robustness\v2_neutral\overlay\trace.jsonl",
    ("V3", "wire_only"): rf"{R}\ablation_prompt_robustness\v3_reworded\wire_only\trace.jsonl",
    ("V3", "overlay"):   rf"{R}\ablation_prompt_robustness\v3_reworded\overlay\trace.jsonl",
    ("V4", "wire_only"): rf"{R}\ablation_prompt_robustness\v4_gentle\wire_only\trace.jsonl",
    ("V4", "overlay"):   rf"{R}\ablation_prompt_robustness\v4_gentle\overlay\trace.jsonl",
    ("MONO120", "wire_only"): rf"{R}\mono_120steps\arm_coronary_wire_only\trace.jsonl",
    ("MONO120", "overlay"):   rf"{R}\mono_120steps\arm_coronary_overlay\trace.jsonl",
    ("BI120", "wire_only"):   rf"{R}\biplane_120steps\wire_only\trace.jsonl",
    ("BI120", "overlay"):     rf"{R}\biplane_120steps\overlay\trace.jsonl",
    ("OLD15", "wire_only"): rf"{R}\2026-06-28_18-03-27\arm_coronary_wire_only\trace.jsonl",
    ("OLD15", "overlay"):   rf"{R}\2026-06-28_19-29-24\arm_coronary_overlay\trace.jsonl",
    ("OLD15", "contrast"):  rf"{R}\2026-06-28_21-00-25\arm_coronary_contrast\trace.jsonl",
}


# ── metric + episode facts ────────────────────────────────────────────────────

def f_rot_lm(rows: list[dict]) -> float | None:
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
    return None if tot_sum == 0.0 else rot_sum / tot_sum


def load(path: str) -> dict[int, dict]:
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
        last = rows[-1]
        # biplane traces carry no `truncation` field -> success = terminal alone
        has_trunc = any("truncation" in r for r in rows)
        success = (bool(last.get("terminal")) and not bool(last.get("truncation", True))
                   if has_trunc else bool(last.get("terminal")))
        seen_lm = False
        first_bif = None
        for r in rows:
            b = r.get("tip_branch_obs", "")
            if b == "left_main":
                seen_lm = True
            elif seen_lm and b and b != "left_main":
                first_bif = b
                break
        n_valid = sum(1 for r in rows
                      if r.get("api_ok", True) and r.get("parse_ok", True))
        out[last["seed"]] = {
            "f": f_rot_lm(rows), "success": success, "first_bif": first_bif,
            "n_rows": len(rows), "n_valid": n_valid,
            # EXCLUSION RULE: zero valid operator actions is not an attempt
            "analysed": n_valid > 0,
        }
    return out


def analysed_only(d: dict[int, dict]) -> dict[int, dict]:
    """Apply the exclusion rule. Nothing downstream may use the raw dict for counts."""
    return {s: v for s, v in d.items() if v["analysed"]}


# ── paired inference ──────────────────────────────────────────────────────────

def n_label(n: int, nz: int) -> str:
    """Pairs, naming the informative count whenever zero-differences were dropped."""
    return str(n) if nz == n else f"{n} ({nz} informative)"


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


def paired_wilcoxon(a: np.ndarray, b: np.ndarray) -> dict:
    """diff = b - a. Reports both total pairs and informative (non-zero) pairs.

    THIS IS THE SINGLE IMPLEMENTATION. Every script that needs a paired Wilcoxon imports it
    rather than calling scipy directly: PRESPEC fixes the normal approximation WITH continuity
    correction, where scipy's default is correction=False, and two scripts once disagreed on the
    same statistic for exactly that reason (results/LOG.md, 2026-09-13).
    """
    d = b - a
    nz = d[d != 0]
    if len(nz) == 0:
        return {"n": len(d), "n_nonzero": 0, "method": "undefined", "W": float("nan"),
                "p": float("nan"), "rb": float("nan"), "hl": 0.0,
                "hl_lo": float("nan"), "hl_hi": float("nan")}
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
            "rb": (rp - rn) / (rp + rn), "hl": hl, "hl_lo": lo, "hl_hi": hi}


def pearson_with_ci(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """Within-pair Pearson correlation with a Fisher-z 95% CI.

    Returns (nan, nan, nan) when either arm is constant, which is the A2 case: a constant
    variable has no shared variance to remove, so the correlation does not exist rather than
    being zero. The CI is mandatory wherever rho is reported (C14) - the whole reason C13 was
    wrong is that rho's imprecision at n = 25 was not carried alongside the point estimate.
    """
    n = len(x)
    if n < 5 or float(np.std(x)) < 1e-12 or float(np.std(y)) < 1e-12:
        return float("nan"), float("nan"), float("nan")
    r, _ = stats.pearsonr(x, y)
    if abs(r) >= 1.0:
        return float(r), float("nan"), float("nan")
    z, se = np.arctanh(r), 1.0 / np.sqrt(n - 3)
    return float(r), float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se))


def rho_label(c: dict) -> str:
    """rho and its CI as one string, or an explicit statement of degeneracy."""
    if not np.isfinite(c["rho"]):
        return "undefined (wire_only arm constant at 0.0000; no shared variance to remove)"
    return f"{c['rho']:+.3f}  95% CI [{c['rho_lo']:+.3f}, {c['rho_hi']:+.3f}]"


def holm(ps: list[float]) -> list[float]:
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * ps[i]
        running = max(running, val)
        adj[i] = min(1.0, running)
    return adj


def pair_arms(a: dict[int, dict], b: dict[int, dict]):
    """Seeds where the metric is defined in BOTH arms (excluded episodes have f=None)."""
    seeds = sorted(s for s in set(a) & set(b)
                   if a[s]["f"] is not None and b[s]["f"] is not None)
    return (seeds,
            np.array([a[s]["f"] for s in seeds]),
            np.array([b[s]["f"] for s in seeds]))


# ── confirmatory family (importable by Phase 6) ───────────────────────────────

def anatomy_result(data: dict, an: str) -> dict:
    """Both tests plus rho-with-CI for one anatomy. Says nothing about family membership."""
    wo, ov = data[(an, "wire_only")], data[(an, "overlay")]
    seeds, x_wo, x_ov = pair_arms(wo, ov)
    res = paired_wilcoxon(x_wo, x_ov)
    mw = stats.mannwhitneyu(x_ov, x_wo, alternative="two-sided")
    n1, n2 = len(x_ov), len(x_wo)
    rho, rho_lo, rho_hi = pearson_with_ci(x_wo, x_ov)
    return {
        "anatomy": an, "seeds": seeds,
        "unpaired": sorted((set(wo) | set(ov)) - set(seeds)),
        "median_wo": float(np.median(x_wo)), "median_ov": float(np.median(x_ov)),
        "wo_all_zero": bool(np.all(x_wo == 0)),
        "wo_nonzero": int(np.sum(x_wo != 0)), "ov_nonzero": int(np.sum(x_ov != 0)),
        # PRIMARY: paired Wilcoxon (C14, superseding C13)
        "p_primary": res["p"], "W_primary": res["W"],
        "paired_W": res["W"], "paired_p": res["p"], "paired_method": res["method"],
        # reported alongside, never adjusted over
        "U": float(mw.statistic), "p_unpaired": float(mw.pvalue),
        "rb_unpaired": abs(1.0 - (2.0 * float(mw.statistic)) / (n1 * n2)),
        "n_wo": n2, "n_ov": n1,
        # rho ALWAYS travels with its CI
        "rho": rho, "rho_lo": rho_lo, "rho_hi": rho_hi,
        **res,
    }


def confirmatory_results(data: dict | None = None) -> list[dict]:
    """The declared confirmatory family: f_rot_LM, wire_only vs overlay, on A1 and A2.

    A3 is NOT here. It is excluded from Results (C11) and therefore from the correction family;
    call `excluded_results()` for its disposition.

    PRIMARY TEST IS THE PAIRED WILCOXON (C14). The unpaired Mann-Whitney and rho-with-CI ride on
    every row so the paper can report both and state that the conclusion is unchanged either way.
    """
    if data is None:
        data = {k: load(p) for k, p in TRACES.items()}
    return [anatomy_result(data, an) for an in CONFIRMATORY]


def excluded_results(data: dict | None = None) -> list[dict]:
    """Geometries excluded from Results, reported raw and UNADJUSTED (Section V prose)."""
    if data is None:
        data = {k: load(p) for k, p in TRACES.items()}
    return [anatomy_result(data, an) for an in EXCLUDED_GEOMETRY]


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    data = {k: load(p) for k, p in TRACES.items()}
    out = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    emit("=" * 78)
    emit("PHASE 5 — MULTIPLICITY TABLE")
    emit(f"seed={GLOBAL_SEED}  alpha={ALPHA}  two-sided")
    emit("Exclusion rule applied to EVERY count (PRESPEC amendment 2026-09-11):")
    emit("zero valid operator actions = not an attempt; denominators trace to")
    emit("results/denominators.csv. No denominator is inherited.")
    emit("=" * 78)
    emit("")
    emit("ENDPOINT STATUS: f_rot_LM is a SECONDARY, mechanistic endpoint. The paper's primary")
    emit("claim is navigation degradation (worst-rank, win ratio, log-rank on A1; complete")
    emit("separation on A2), which none of the choices below affect.")

    # ---- check 1: is every anatomy seed-matched?
    emit("")
    emit("CHECK 1 — seed matching per anatomy (audit; membership of the family is separate)")
    for an in ALL_ANATOMIES:
        wo, ov = data[(an, "wire_only")], data[(an, "overlay")]
        seeds, _, _ = pair_arms(wo, ov)
        tag = "IN the confirmatory family" if an in CONFIRMATORY else "EXCLUDED (C11)"
        emit(f"  {an}: seeds identical across arms = {sorted(wo) == sorted(ov)}; "
             f"complete pairs = {len(seeds)}; "
             f"unpaired = {sorted((set(wo)|set(ov)) - set(seeds)) or 'none'}   [{tag}]")
    emit("  -> the design is seed-matched, and the PAIRED test is primary (C14). Phase 7i")
    emit("     measured the within-pair correlation at about zero, but at n = 25 its CI spans")
    emit("     roughly [-0.45, +0.33]: that shows pairing is not demonstrably helping, NOT that")
    emit("     pairing is unjustified. The conservative matched test is retained; the unpaired")
    emit("     test is reported alongside with rho and its CI.")

    # ---- confirmatory family. PRIMARY = paired Wilcoxon (C14); Holm over primary p.
    conf = confirmatory_results(data)
    raw = [c["p_primary"] for c in conf]
    hp = holm(raw)
    bp = [min(1.0, p * len(raw)) for p in raw]

    emit("")
    emit("-" * 78)
    emit(f"CONFIRMATORY FAMILY — f_rot_LM, wire_only vs overlay, {len(conf)} MEMBERS: "
         f"{', '.join(CONFIRMATORY)}")
    emit("PRIMARY TEST = PAIRED WILCOXON SIGNED-RANK (CORRECTIONS C14, superseding C13).")
    emit("A3 is NOT a member: it is excluded from Results on physical-validity grounds (C11),")
    emit("and a family is the set of tests we draw inferences from. Declaring three while")
    emit("reporting two would overstate the correction burden in our own favour.")
    emit("Holm and Bonferroni both adjust over TWO. The unpaired Mann-Whitney is reported")
    emit("alongside and is never adjusted over.")
    emit("-" * 78)
    for c, h, b in zip(conf, hp, bp):
        emit(f"  {c['anatomy']}: median {c['median_wo']:.4f} -> {c['median_ov']:.4f}  "
             f"(diff {c['median_ov']-c['median_wo']:+.4f})")
        emit(f"      PRIMARY  Wilcoxon signed-rank W={c['W_primary']:.1f}  "
             f"n={n_label(c['n'], c['n_nonzero'])} pairs  {c['paired_method']}  "
             f"raw p={c['p_primary']:.3g}  Holm p={h:.3g}  Bonferroni p={b:.3g}")
        emit(f"               matched-pairs rank-biserial={c['rb']:+.3f}  "
             f"HL={c['hl']:+.4f} [{c['hl_lo']:+.4f}, {c['hl_hi']:+.4f}]  "
             f"{'SIGNIFICANT' if h < ALPHA else 'NOT SIGNIFICANT'} after Holm")
        emit(f"      alongside Mann-Whitney U={c['U']:.1f}  n={c['n_wo']}v{c['n_ov']}  "
             f"p={c['p_unpaired']:.3g}  rank-biserial={c['rb_unpaired']:.3f}  "
             f"(NOT Holm-adjusted)")
        emit(f"      within-pair correlation rho = {rho_label(c)}")
        same = (c["p_primary"] < ALPHA) == (c["p_unpaired"] < ALPHA)
        emit(f"      conclusion unchanged under either test: {same}")
        if c["n_nonzero"] < c["n"]:
            emit(f"      *** {c['n'] - c['n_nonzero']} pair(s) have a difference of exactly "
                 f"zero and are DROPPED by the signed-rank test;")
            emit(f"          the effective sample is {c['n_nonzero']}, not {c['n']}.")
        if c["unpaired"]:
            emit(f"      unpaired seeds excluded (named, not silent): {c['unpaired']}")
    emit("")
    emit(f"  All {len(conf)} members significant after Holm: {all(h < ALPHA for h in hp)}")
    emit(f"  Worst adjusted p in the family: {max(hp):.3g}")

    # ---- structural caveat on A2
    a2 = next(c for c in conf if c["anatomy"] == "A2")
    if a2["wo_all_zero"]:
        emit("")
        emit("  STRUCTURAL CAVEAT — A2 IS A FLOOR EFFECT, NOT A MAGNITUDE SHIFT")
        emit(f"    Every one of the {a2['n']} A2 wire_only episodes has f_rot_LM of exactly")
        emit("    0.0000 — the arm never rotates during the LM phase at all (Phase 6c")
        emit("    confirms zero rotate INTENTS, so this is behavioural, not a metric")
        emit(f"    artefact). In overlay, {a2['ov_nonzero']}/{a2['n']} episodes rotate.")
        emit("    The signed-rank test reduces to a sign test on the "
             f"{a2['n_nonzero']} informative")
        emit("    pairs (all positive, hence W=0 and rank-biserial=+1.000).")
        emit("    Report A2 as a presence/absence induction result, not a '+0.045 shift'.")
        emit("    This is also why rho is undefined on A2: a constant arm has no shared")
        emit("    variance, so pairing there is definitionally useless - which is an argument")
        emit("    about A2 specifically, not a general licence to drop the matched test.")

    # ---- A3 disposition: raw only, NO adjusted p, not in any inference family
    emit("")
    emit("-" * 78)
    emit("EXCLUDED GEOMETRY — NOT IN ANY INFERENCE FAMILY (CORRECTIONS C11)")
    emit("-" * 78)
    emit("Reported here and in Section V prose so the number is auditable. It carries NO")
    emit("adjusted p: we do not adjust a test we are not inferring from.")
    for c in excluded_results(data):
        emit("")
        emit(f"  {c['anatomy']}: median {c['median_wo']:.4f} -> {c['median_ov']:.4f}")
        emit(f"      paired Wilcoxon W={c['paired_W']:.1f}  "
             f"n={n_label(c['n'], c['n_nonzero'])} pairs  {c['paired_method']}  "
             f"raw p={c['p_primary']:.3g}   [NO ADJUSTED p]")
        emit(f"      Mann-Whitney U={c['U']:.1f}  raw p={c['p_unpaired']:.3g}   "
             f"[NO ADJUSTED p]")
        emit(f"      within-pair correlation rho = {rho_label(c)}")
        if c["unpaired"]:
            emit(f"      unpaired seeds (named, not silent): {c['unpaired']}")
        emit("      EXCLUSION REASON: the lumen surface is wholly generated as a constant-radius")
        emit("      2.5 mm tube along the patient centreline, not a patient surface (C8); the")
        emit("      Gauss-Seidel contact solver fails to converge on 97.2% of steps; and an")
        emit("      open-loop always-advance policy is shut out at 0/25, indicating the geometry")
        emit("      is not navigable rather than merely hard (Phase 7a).")
        emit("      NOTE THE DIRECTION: this was the largest effect available to us. Excluding")
        emit("      it costs us the strongest result in the original analysis.")

    # ---- check 2: success rates, and whether a steps claim would be supported
    emit("")
    emit("-" * 78)
    emit("CHECK 2 — success rates per arm, ON CORRECTED DENOMINATORS")
    emit("-" * 78)
    emit("  (attempted -> analysed after removing episodes with zero valid actions)")
    for an in ALL_ANATOMIES:
        wo_all, ov_all = data[(an, "wire_only")], data[(an, "overlay")]
        wo, ov = analysed_only(wo_all), analysed_only(ov_all)
        nwo = sum(1 for s in wo if wo[s]["success"])
        nov = sum(1 for s in ov if ov[s]["success"])
        _, p_f = stats.fisher_exact([[nwo, len(wo) - nwo], [nov, len(ov) - nov]])
        emit(f"  {an}: wire_only {nwo}/{len(wo)} (of {len(wo_all)} attempted)   "
             f"overlay {nov}/{len(ov)} (of {len(ov_all)} attempted)   "
             f"Fisher two-sided p = {p_f:.3g}")
    emit("")
    emit("  A2: success rates are IDENTICAL, so the Phase 3 selection bias does NOT")
    emit("      apply. A steps-to-target claim on A2 would be well-founded.")
    emit("  A3: the overlay arm has ZERO successes among analysed episodes, so")
    emit("      steps-to-target is undefined in that arm. NOT RUN — awaiting instruction.")

    # ---- exploratory rows
    #
    # f_rot_LM "unmatched sensitivity" rows are NOT listed here any more. The unpaired test is
    # now reported on the confirmatory row itself, alongside the primary; listing it a second
    # time as exploratory would enter one comparison in the table twice under two names.
    exploratory: list[tuple] = []

    for an in ALL_ANATOMIES:
        wo, ov = analysed_only(data[(an, "wire_only")]), analysed_only(data[(an, "overlay")])
        nwo = sum(1 for s in wo if wo[s]["success"])
        nov = sum(1 for s in ov if ov[s]["success"])
        orr, p_f = stats.fisher_exact([[nwo, len(wo)-nwo], [nov, len(ov)-nov]])
        exploratory.append(("success rate", an, "Fisher exact", f"OR={orr:.3f}",
                            f"{len(wo)}+{len(ov)}", p_f))
        lwo = sum(1 for s in wo if (wo[s]["first_bif"] or "").startswith("lcx"))
        lov = sum(1 for s in ov if (ov[s]["first_bif"] or "").startswith("lcx"))
        orb, p_b = stats.fisher_exact([[lwo, len(wo)-lwo], [lov, len(ov)-lov]])
        exploratory.append(("first-bifurcation LCx", an, "Fisher exact", f"OR={orb:.3f}",
                            f"{len(wo)}+{len(ov)}", p_b))

    for v in ("V2", "V3", "V4"):
        wo, ov = analysed_only(data[(v, "wire_only")]), analysed_only(data[(v, "overlay")])
        seeds, x_wo, x_ov = pair_arms(wo, ov)
        if len(seeds) >= 2:
            r = paired_wilcoxon(x_wo, x_ov)
            exploratory.append((f"f_rot_LM prompt variant {v}", "A1",
                                f"Wilcoxon signed-rank ({r['method']})",
                                f"W={r['W']:.1f}", n_label(r["n"], r["n_nonzero"]), r["p"]))

    for mode in ("wire_only", "overlay"):
        mono = analysed_only(data[("MONO120", mode)])
        bi = analysed_only(data[("BI120", mode)])
        seeds, x_m, x_b = pair_arms(mono, bi)
        if len(seeds) >= 2:
            r = paired_wilcoxon(x_m, x_b)
            exploratory.append((f"f_rot_LM biplane vs mono ({mode})", "A1",
                                f"Wilcoxon signed-rank ({r['method']})",
                                f"W={r['W']:.1f}", n_label(r["n"], r["n_nonzero"]), r["p"]))

    for ref in ("wire_only", "overlay"):
        base = analysed_only(data[("OLD15", ref)])
        con = analysed_only(data[("OLD15", "contrast")])
        seeds, x_b, x_c = pair_arms(base, con)
        if len(seeds) >= 2:
            r = paired_wilcoxon(x_b, x_c)
            exploratory.append((f"f_rot_LM contrast vs {ref}", "A1 (old prompt, n=15)",
                                f"Wilcoxon signed-rank ({r['method']})",
                                f"W={r['W']:.1f}", n_label(r["n"], r["n_nonzero"]), r["p"]))

    emit("")
    emit("-" * 78)
    emit("EXPLORATORY (unadjusted; blank adjusted columns in the CSV)")
    emit("-" * 78)
    for ep, an, test, stat, n, p in exploratory:
        emit(f"  {ep:<42s} {an:<22s} {test:<34s} {stat:>12s} n={n:<20s} p={p:.3g}")

    # ---- write CSV
    with open(RESULTS / "multiplicity_table.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["endpoint", "anatomy", "family", "prespecified", "test",
                    "statistic", "n", "raw_p", "holm_p", "bonferroni_p", "within_pair_rho"])
        for c, h, b in zip(conf, hp, bp):
            # PRIMARY row: paired Wilcoxon, Holm-adjusted over the TWO family members (C14).
            w.writerow(["f_rot_LM (wire_only vs overlay)", c["anatomy"], "confirmatory",
                        "yes", f"Wilcoxon signed-rank ({c['paired_method']}, primary)",
                        f"W={c['W_primary']:.1f}", n_label(c["n"], c["n_nonzero"]),
                        f"{c['p_primary']:.3g}", f"{h:.3g}", f"{b:.3g}", rho_label(c)])
            # Reported alongside, per C14. NOT adjusted over: including it in the Holm family
            # would double-count the same comparison.
            # ASCII hyphen deliberately: this row label reached the CSV as mojibake ("a<euro>")
            # when an em dash was written without a BOM and read back as cp1252.
            w.writerow(["f_rot_LM (wire_only vs overlay) - unpaired, reported alongside",
                        c["anatomy"], "confirmatory (secondary presentation)", "yes",
                        "Mann-Whitney U (unpaired)", f"U={c['U']:.1f}",
                        f"{c['n_wo']}v{c['n_ov']}", f"{c['p_unpaired']:.3g}", "", "",
                        rho_label(c)])
        # A3: present for audit, explicitly OUTSIDE every inference family, adjusted cols blank.
        for c in excluded_results(data):
            w.writerow(["f_rot_LM (wire_only vs overlay)", c["anatomy"],
                        "EXCLUDED (C11) - not in any inference family; Section V prose only",
                        "n/a", f"Wilcoxon signed-rank ({c['paired_method']})",
                        f"W={c['paired_W']:.1f}", n_label(c["n"], c["n_nonzero"]),
                        f"{c['p_primary']:.3g}", "", "", rho_label(c)])
        for ep, an, test, stat, n, p in exploratory:
            w.writerow([ep, an, "exploratory", "no", test, stat, n, f"{p:.3g}", "", "", ""])

    (RESULTS / "phase5_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'multiplicity_table.csv'}")
    emit(f"wrote {RESULTS/'phase5_report.txt'}")


if __name__ == "__main__":
    main()
