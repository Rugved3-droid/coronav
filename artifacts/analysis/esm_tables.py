"""Online Resource 1 (ESM): supplementary tables for R2.1 and R2.6. READ-ONLY on the logged traces.

WHY THIS EXISTS. Reviewer 2 asked for complete quantitative results per anatomy and condition
(R2.1), and for a complete statistical presentation of the biplane experiment - four groups,
sample size, budget, all result values and exact tests (R2.6). The response letter said such a
table existed. It did not: the committed artifacts held denominators and the two within-mode
Wilcoxon results, but no per-arm success counts, f_rot_LM medians or IQRs, and no verified budget.
This script makes that statement true rather than leaving it asserted.

It computes DESCRIPTIVE statistics only (counts, medians, quartiles) per arm, using phase5's own
loader and metric - the single implementation every confirmatory result uses. It computes no new
test: the exploratory test results are read from results/multiplicity_table.csv, where they were
produced by phase5.

Budgets are VERIFIED from the traces, not taken from folder names: the largest episode length in
an arm is reported, and an arm whose failures all stop at that length is confirmed as run to that
budget.

No API calls. Outputs: results/esm1_arm_descriptives.csv, results/esm1_supplementary_tables.md
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from phase5_multiplicity import TRACES, load  # noqa: E402

RES = ROOT / "results"

GROUPS = [
    ("A1", "Confirmatory", ["wire_only", "overlay"]),
    ("A2", "Confirmatory", ["wire_only", "overlay"]),
    ("MONO120", "Exploratory: biplane study, monoplane arms", ["wire_only", "overlay"]),
    ("BI120", "Exploratory: biplane study, biplane arms", ["wire_only", "overlay"]),
    ("V2", "Exploratory: prompt variant V2 (A1)", ["wire_only", "overlay"]),
    ("V3", "Exploratory: prompt variant V3 (A1)", ["wire_only", "overlay"]),
    ("V4", "Exploratory: prompt variant V4 (A1)", ["wire_only", "overlay"]),
    ("OLD15", "Exploratory: original prompt with contrast condition (A1)", ["wire_only", "overlay", "contrast"]),
]
# The biplane arms must NOT be labelled by a budget. The run directory says 120 steps; the traces
# say otherwise, and asserting the budget in a table label would reinstate exactly the claim C19
# withdraws. The monoplane arms are labelled with their budget because the traces confirm it:
# every failure runs to 120 and records truncation.
LABEL = {"A1": "A1 VMR 0066", "A2": "A2 ASOCA Normal_12",
         "MONO120": "A1 monoplane arms (120-step budget, verified)",
         "BI120": "A1 biplane arms (budget not established; see C19)",
         "V2": "A1 prompt V2", "V3": "A1 prompt V3",
         "V4": "A1 prompt V4", "OLD15": "A1 original prompt"}


def q(a: np.ndarray, p: float) -> float:
    return float(np.percentile(a, p))


def main() -> int:
    rows, md = [], []
    for key, role, arms in GROUPS:
        for arm in arms:
            if (key, arm) not in TRACES:
                continue
            eps = load(TRACES[(key, arm)])
            attempted = len(eps)
            analysed = {s: v for s, v in eps.items() if v["analysed"]}
            n = len(analysed)
            succ = sum(1 for v in analysed.values() if v["success"])
            fvals = np.array([v["f"] for v in analysed.values() if v["f"] is not None], float)
            lengths = [v["n_rows"] for v in analysed.values()]
            longest = max(lengths) if lengths else 0
            fail_len = sorted({v["n_rows"] for v in analysed.values() if not v["success"]})
            budget_ok = bool(fail_len) and fail_len == [longest]
            rows.append({
                "group": LABEL[key], "role": role, "arm": arm, "attempted": attempted,
                "analysed": n, "successes": succ,
                "success_pct": f"{100.0 * succ / n:.1f}" if n else "",
                "frot_defined_n": len(fvals),
                "frot_median": f"{np.median(fvals):.4f}" if len(fvals) else "",
                "frot_q1": f"{q(fvals, 25):.4f}" if len(fvals) else "",
                "frot_q3": f"{q(fvals, 75):.4f}" if len(fvals) else "",
                "longest_episode_steps": longest,
                "failures_all_at_longest": "yes" if budget_ok else ("no failures" if not fail_len else "no"),
            })

    with open(RES / "esm1_arm_descriptives.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Per-episode evidence for C19. The biplane episodes that ended without reaching target did so
    # at lengths below their own arm's maximum, which a fixed-step-count truncation cannot produce.
    # Writing them to an artifact is what lets the manuscript cite them: the same prose first
    # carried these as hand-typed numbers and the build refused it.
    early = []
    for key in ("MONO120", "BI120"):
        for arm in ("wire_only", "overlay"):
            eps = load(TRACES[(key, arm)])
            longest = max(v["n_rows"] for v in eps.values())
            for seed, v in sorted(eps.items()):
                if not v["success"]:
                    early.append({
                        "group": LABEL[key], "arm": arm, "seed": seed,
                        "steps": v["n_rows"], "arm_longest_episode": longest,
                        "ended_below_arm_longest": "yes" if v["n_rows"] < longest else "no",
                    })
    with open(RES / "esm1_nonterminal_episodes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(early[0].keys()))
        w.writeheader()
        w.writerows(early)
    print("  non-terminal episodes (C19 evidence):")
    for e in early:
        print(f"    {e['group']:<48s} {e['arm']:<9s} seed={e['seed']} steps={e['steps']:<4d}"
              f" arm_longest={e['arm_longest_episode']} below={e['ended_below_arm_longest']}")

    tests = list(csv.DictReader(open(RES / "multiplicity_table.csv", newline="", encoding="utf-8")))

    md += ["# Supplementary Material", "",
           "Generated by `analysis/esm_tables.py` from the logged episode traces and "
           "`results/multiplicity_table.csv`. Descriptive statistics only; every test shown was "
           "produced by `analysis/phase5_multiplicity.py`. Do not edit by hand.", "",
           "**Supplementary Fig. S1** shows the exploratory observation conditions — the contrast "
           "rendering and the biplane view pair — that are not part of the wire-only versus "
           "overlay comparison in the main text. Every arm below is exploratory unless its Role "
           "column says otherwise, and every test in Table S3 is unadjusted.", "",
           "**Table S1** Every arm, per anatomy and condition. *Analysed* excludes episodes with "
           "zero valid operator actions. *Longest* is the longest episode in the arm; where every "
           "failure stopped at that length, the arm is confirmed to have run to that budget, and "
           "where it did not, the arm's effective budget is not established (see C19 for the "
           "biplane arms). Success is not compared between the monoplane and biplane arms (C19). "
           "A2's two arms ran under a common step limit and nothing was truncated, so their "
           "success counts ARE comparable; an earlier version of this caption said otherwise on "
           "the strength of a per-arm budget claim that is withdrawn (C20).", "",
           "| Group | Role | Arm | Attempted | Analysed | Success | f_rot_LM median [IQR] (n defined) | Longest | Failures at longest |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = (f"{r['frot_median']} [{r['frot_q1']}, {r['frot_q3']}] ({r['frot_defined_n']})"
             if r["frot_median"] else "—")
        md.append(f"| {r['group']} | {r['role']} | {r['arm']} | {r['attempted']} | {r['analysed']} | "
                  f"{r['successes']}/{r['analysed']} ({r['success_pct']}%) | {f} | "
                  f"{r['longest_episode_steps']} | {r['failures_all_at_longest']} |")

    # The S2 caption is DERIVED from `early`, never typed. An earlier version of it asserted
    # "three biplane episodes ended at 20, 30 and 48 steps". That is the claim C19 withdrew: the
    # 48-step episode is its own arm's longest and so is explicable as a truncation, leaving two
    # episodes that a single fixed step count cannot produce. This file is generated, so it is not
    # covered by the manuscript build's number-injection guard, and the stale numerals survived
    # here after being corrected everywhere the guard does reach. Deriving them is the fix.
    below = sorted((e for e in early if e["ended_below_arm_longest"] == "yes"),
                   key=lambda e: e["steps"])
    mono_budget = max(e["arm_longest_episode"] for e in early if e["group"] == LABEL["MONO120"])
    n_word = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}.get(len(below), str(len(below)))
    below_steps = " and ".join(str(e["steps"]) for e in below)
    arm_longest = ", ".join(sorted({str(e["arm_longest_episode"]) for e in below}))

    md += ["", "**Table S2** Biplane experiment (A1, the same 10 seeds in all four arms). The "
               "contrasts are exploratory and were not pre-specified; the analysis plan is "
               "retrospective. Biplane versus monoplane is tested within each observation mode by "
               "paired Wilcoxon signed-rank on f_rot_LM. **The arms were not budget-matched** "
               f"(CORRECTIONS C19): monoplane failures ran to the {mono_budget}-step budget and "
               f"were recorded as truncated, whereas {n_word} biplane episodes ended at "
               f"{below_steps} steps, below their own arm's longest episode of {arm_longest}, "
               "which a single fixed step count cannot produce, for a reason the traces do not "
               "record. Success counts are therefore not compared between the monoplane and "
               "biplane arms.", "",
           "| Observation | Monoplane arm | Biplane arm | Test | Statistic | Pairs | p |",
           "|---|---|---|---|---|---|---|"]
    by = {(r["group"], r["arm"]): r for r in rows}
    for mode in ("wire_only", "overlay"):
        mono = by[(LABEL["MONO120"], mode)]
        bi = by[(LABEL["BI120"], mode)]
        t = next(x for x in tests if x["endpoint"] == f"f_rot_LM biplane vs mono ({mode})")
        md.append(
            f"| {mode} | n={mono['analysed']}, success {mono['successes']}/{mono['analysed']}, f_rot_LM "
            f"{mono['frot_median']} [{mono['frot_q1']}, {mono['frot_q3']}] | n={bi['analysed']}, success "
            f"{bi['successes']}/{bi['analysed']}, f_rot_LM {bi['frot_median']} [{bi['frot_q1']}, "
            f"{bi['frot_q3']}] | {t['test']} | {t['statistic']} | {t['n']} | {t['raw_p']} |")

    md += ["", "**Table S3** Every exploratory test, unadjusted, as produced. The excluded geometry "
               "(A3) appears only here, and is not part of any inference family.", "",
           "| Endpoint | Anatomy / arm | Test | Statistic | n | Raw p |", "|---|---|---|---|---|---|"]
    for x in tests:
        if x["family"].startswith("exploratory") or x["family"].startswith("EXCLUDED"):
            md.append(f"| {x['endpoint']} | {x['anatomy']} | {x['test']} | {x['statistic']} | "
                      f"{x['n']} | {x['raw_p']} |")

    (RES / "esm1_supplementary_tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for r in rows:
        print(f"  {r['group']:<34s} {r['arm']:<9s} analysed={r['analysed']:<3} "
              f"success={r['successes']}/{r['analysed']}  f_rot_LM median={r['frot_median'] or '-':<7s} "
              f"longest={r['longest_episode_steps']}  failures_at_longest={r['failures_all_at_longest']}")
    print(f"wrote {RES / 'esm1_arm_descriptives.csv'}")
    print(f"wrote {RES / 'esm1_supplementary_tables.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
