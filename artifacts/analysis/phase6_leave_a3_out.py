"""Phase 6 — the declared confirmatory family, and what excluding A3 did to the correction.

Reviewer 1 asked whether the conclusions hold when A3 is excluded, and asked us to discuss
excluding it. That question has since been answered by the design rather than by a sensitivity
analysis: A3 is excluded from Results on physical-validity grounds (CORRECTIONS C11), and the
confirmatory family is therefore **A1 + A2, two members** (PRESPEC amendment 2026-09-13). A
family is the set of tests we draw inferences from.

So this file is no longer a leave-one-out sensitivity. It records two things:

  1. the declared two-member family, adjusted over two; and
  2. the answer to the question the exclusion invites - did dropping A3 make the multiplicity
     correction easier on us? It did not, and that is computed here rather than asserted.

**A3 is given NO adjusted p anywhere in this file, and no row in any table.** We do not adjust a
test we are not inferring from. The counterfactual three-member adjustment is computed only to
establish the invariance in point 2, and only the A1 and A2 entries of it are ever reported.

PRIMARY TEST IS THE PAIRED WILCOXON (CORRECTIONS C14, superseding C13). Rho is reported with its
95% CI wherever it appears.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv

from phase5_multiplicity import (ALPHA, CONFIRMATORY, EXCLUDED_GEOMETRY, RESULTS, TRACES,
                                 confirmatory_results, excluded_results, holm, load, n_label,
                                 rho_label)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    data = {k: load(p) for k, p in TRACES.items()}
    conf = confirmatory_results(data)
    excl = excluded_results(data)

    out = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    emit("=" * 82)
    emit("PHASE 6 — THE DECLARED CONFIRMATORY FAMILY, AND THE COST OF EXCLUDING A3")
    emit("=" * 82)
    emit("")
    emit("Primary test: PAIRED Wilcoxon signed-rank (C14). Holm and Bonferroni adjust over the")
    emit(f"{len(conf)} declared members ({', '.join(CONFIRMATORY)}). The unpaired Mann-Whitney is")
    emit("reported alongside and is never adjusted over.")
    emit("")
    emit("f_rot_LM is a SECONDARY endpoint. The paper's primary claim is navigation")
    emit("degradation, which none of this touches.")

    raw = [c["p_primary"] for c in conf]
    hp = holm(raw)
    bp = [min(1.0, p * len(raw)) for p in raw]

    emit("")
    emit(f"DECLARED FAMILY — {len(conf)} MEMBERS, both patient-derived")
    for c, h, b in zip(conf, hp, bp):
        emit("")
        emit(f"  {c['anatomy']}")
        emit(f"    PRIMARY  Wilcoxon signed-rank W={c['W_primary']:.1f}  "
             f"n={n_label(c['n'], c['n_nonzero'])} pairs  {c['paired_method']}")
        emit(f"             raw p={c['p_primary']:.3g}   Holm p={h:.3g}   "
             f"Bonferroni p={b:.3g}   "
             f"{'SIGNIFICANT' if h < ALPHA else 'NOT SIGNIFICANT'}")
        emit(f"             matched-pairs rank-biserial={c['rb']:+.3f}  HL={c['hl']:+.4f} "
             f"[{c['hl_lo']:+.4f}, {c['hl_hi']:+.4f}]")
        emit(f"    alongside Mann-Whitney U={c['U']:.1f}  n={c['n_wo']}v{c['n_ov']}  "
             f"p={c['p_unpaired']:.3g}  (not Holm-adjusted)")
        emit(f"    within-pair correlation rho = {rho_label(c)}")
        emit(f"    conclusion unchanged under either test: "
             f"{(c['p_primary'] < ALPHA) == (c['p_unpaired'] < ALPHA)}")
        emit(f"    median {c['median_wo']:.4f} -> {c['median_ov']:.4f}")
        if c["n_nonzero"] < c["n"]:
            emit(f"    *** the signed-rank test drops {c['n'] - c['n_nonzero']} zero-difference "
                 f"pair(s): its effective sample is {c['n_nonzero']}, not {c['n']}.")

    emit("")
    emit(f"  DIRECTION preserved in both: "
         f"{all(c['median_ov'] > c['median_wo'] for c in conf)} (overlay > wire_only)")
    emit(f"  ALL MEMBERS SIGNIFICANT AFTER HOLM: {all(h < ALPHA for h in hp)}")
    emit(f"  worst adjusted p in the family = {max(hp):.3g}")

    # ---- Did excluding A3 ease the correction? Counterfactual, reported for A1/A2 ONLY.
    counter_raw = raw + [e["p_primary"] for e in excl]
    counter_holm = holm(counter_raw)
    counter_bonf = [min(1.0, p * len(counter_raw)) for p in counter_raw]

    emit("")
    emit("DID EXCLUDING A3 EASE THE MULTIPLICITY CORRECTION?")
    emit("  The question matters because A3 supplied the largest effect available to us, so its")
    emit("  removal has to be shown not to have been self-serving. Below, each declared member's")
    emit("  adjusted p under the family as declared, against what it WOULD have been had the")
    emit("  excluded geometry been counted. A3's own adjusted p is not computed for reporting")
    emit("  and appears nowhere: it is not in a family.")
    emit("")
    emit(f"  {'anatomy':<9} {'raw p':>11} {'Holm (declared, 2)':>20} {'Holm (if 3)':>13} "
         f"{'Bonf (2)':>11} {'Bonf (if 3)':>13}")
    eased = False
    for i, c in enumerate(conf):
        emit(f"  {c['anatomy']:<9} {c['p_primary']:>11.3g} {hp[i]:>20.3g} "
             f"{counter_holm[i]:>13.3g} {bp[i]:>11.3g} {counter_bonf[i]:>13.3g}")
        if hp[i] < counter_holm[i]:
            eased = True
    emit("")
    if not eased:
        emit("  NO. Every declared member's Holm-adjusted p is IDENTICAL under either family")
        emit("  size. Holm leaves the largest p in a family unmultiplied, so A1 is unadjusted")
        emit("  either way; A2 is the middle of three and the smaller of two, taking the same")
        emit("  multiplier in both. The exclusion bought us nothing on the primary adjustment.")
        emit("  Only Bonferroni is sensitive to the family size, and Bonferroni is not the")
        emit("  primary adjustment.")
    else:
        emit("  YES — at least one member's adjusted p improved because A3 was dropped. That is")
        emit("  a material benefit from our own exclusion decision and MUST be disclosed as such")
        emit("  in the response letter rather than presented as a neutral tidying-up.")

    # ---- A3's disposition, raw only
    emit("")
    emit("EXCLUDED GEOMETRY — REPORTED RAW, IN NO FAMILY")
    for e in excl:
        emit(f"  {e['anatomy']}: paired Wilcoxon W={e['paired_W']:.1f}  "
             f"n={n_label(e['n'], e['n_nonzero'])} pairs  {e['paired_method']}  "
             f"raw p={e['p_primary']:.3g}   [NO ADJUSTED p — not in any inference family]")
        emit(f"      Mann-Whitney U={e['U']:.1f}  raw p={e['p_unpaired']:.3g}")
        emit(f"      within-pair correlation rho = {rho_label(e)}")
    emit("  Grounds: wholly generated lumen surface (C8), 97.2% solver non-convergence, and an")
    emit("  open-loop policy shut out at 0/25 (Phase 7a). Reported in Section V prose.")

    # ---- what actually carries the claim
    a2 = next(c for c in conf if c["anatomy"] == "A2")
    weakest = max(range(len(conf)), key=lambda i: hp[i])
    emit("")
    emit("  WHAT CARRIES THE TWO-MEMBER CLAIM. Of the two, A2 is a floor effect:")
    emit(f"  all {a2['n']} A2 wire_only episodes sit at exactly 0.0000 LM rotation, so A2")
    emit("  evidences presence-versus-absence of rotation rather than a magnitude shift. A1 is")
    emit("  the only member contributing a graded effect, and it is also the weakest member")
    emit(f"  (Holm p = {hp[weakest]:.3g} for {conf[weakest]['anatomy']}). The claim survives, but")
    emit("  it does not rest on two equivalent replications, and the paper says so.")

    with open(RESULTS / "phase6_leave_a3_out.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["endpoint", "anatomy", "family", "prespecified", "test",
                    "statistic", "n", "raw_p", "holm_p", "bonferroni_p", "within_pair_rho"])
        for c, h, b in zip(conf, hp, bp):
            w.writerow(["f_rot_LM (wire_only vs overlay)", c["anatomy"],
                        f"confirmatory ({len(conf)} members: {', '.join(CONFIRMATORY)})", "yes",
                        f"Wilcoxon signed-rank ({c['paired_method']}, primary)",
                        f"W={c['W_primary']:.1f}", n_label(c["n"], c["n_nonzero"]),
                        f"{c['p_primary']:.3g}", f"{h:.3g}", f"{b:.3g}", rho_label(c)])
            w.writerow(["f_rot_LM (wire_only vs overlay) - unpaired, reported alongside",
                        c["anatomy"], "confirmatory (secondary presentation)", "yes",
                        "Mann-Whitney U (unpaired)", f"U={c['U']:.1f}",
                        f"{c['n_wo']}v{c['n_ov']}", f"{c['p_unpaired']:.3g}", "", "",
                        rho_label(c)])
        for e in excl:
            w.writerow(["f_rot_LM (wire_only vs overlay)", e["anatomy"],
                        f"EXCLUDED (C11) - not in any inference family",
                        "n/a", f"Wilcoxon signed-rank ({e['paired_method']})",
                        f"W={e['paired_W']:.1f}", n_label(e["n"], e["n_nonzero"]),
                        f"{e['p_primary']:.3g}", "", "", rho_label(e)])

    (RESULTS / "phase6_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6_leave_a3_out.csv'}")
    emit(f"wrote {RESULTS/'phase6_report.txt'}")


if __name__ == "__main__":
    main()
