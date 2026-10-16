"""Phase 6d — the exclusion rule, applied to every arm, with a traceable denominator table.

RULE (PRESPEC.md amendment 2026-09-11):
  EXCLUDED (not an attempt): episodes with ZERO valid operator actions, i.e. total API
    transmission failure. They leave the denominator entirely.
  INCLUDED: episodes with any valid operator actions, including partial transmission failures.
  PAIRING: when an episode is excluded from one arm, its seed-matched counterpart is dropped
    from paired tests, and the pair count is reported per test.

Produces results/denominators.csv, to which every manuscript table cell must trace.

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
R = r"D:\steve\pilot\runs"

ARMS = {
    ("A1", "wire_only"): rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    ("A1", "overlay"):   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
    ("A2", "wire_only"): rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    ("A2", "overlay"):   rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
    ("A3", "wire_only"): rf"{R}\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl",
    ("A3", "overlay"):   rf"{R}\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl",
    ("A1 V2", "wire_only"): rf"{R}\ablation_prompt_robustness\v2_neutral\wire_only\trace.jsonl",
    ("A1 V2", "overlay"):   rf"{R}\ablation_prompt_robustness\v2_neutral\overlay\trace.jsonl",
    ("A1 V3", "wire_only"): rf"{R}\ablation_prompt_robustness\v3_reworded\wire_only\trace.jsonl",
    ("A1 V3", "overlay"):   rf"{R}\ablation_prompt_robustness\v3_reworded\overlay\trace.jsonl",
    ("A1 V4", "wire_only"): rf"{R}\ablation_prompt_robustness\v4_gentle\wire_only\trace.jsonl",
    ("A1 V4", "overlay"):   rf"{R}\ablation_prompt_robustness\v4_gentle\overlay\trace.jsonl",
    ("A1 mono120", "wire_only"): rf"{R}\mono_120steps\arm_coronary_wire_only\trace.jsonl",
    ("A1 mono120", "overlay"):   rf"{R}\mono_120steps\arm_coronary_overlay\trace.jsonl",
    ("A1 biplane120", "wire_only"): rf"{R}\biplane_120steps\wire_only\trace.jsonl",
    ("A1 biplane120", "overlay"):   rf"{R}\biplane_120steps\overlay\trace.jsonl",
    ("A1 old-prompt", "wire_only"): rf"{R}\2026-06-28_18-03-27\arm_coronary_wire_only\trace.jsonl",
    ("A1 old-prompt", "overlay"):   rf"{R}\2026-06-28_19-29-24\arm_coronary_overlay\trace.jsonl",
    ("A1 old-prompt", "contrast"):  rf"{R}\2026-06-28_21-00-25\arm_coronary_contrast\trace.jsonl",
}


def audit(path: str) -> dict:
    by: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by[r["episode"]].append(r)

    attempted = len(by)
    excluded, partial = [], []
    analysed_seeds = []
    for ep, rows in sorted(by.items()):
        rows.sort(key=lambda r: r["step"])
        seed = rows[-1]["seed"]
        n_api_bad = sum(1 for r in rows if r.get("api_ok") is False)
        n_parse_bad = sum(1 for r in rows if r.get("parse_ok") is False)
        n_valid = sum(1 for r in rows
                      if r.get("api_ok", True) and r.get("parse_ok", True))
        if n_valid == 0:
            reason = ("all rows api_ok=False" if n_api_bad == len(rows)
                      else "all rows api_ok/parse_ok False")
            excluded.append((seed, ep, len(rows), reason))
        else:
            analysed_seeds.append(seed)
            if n_api_bad or n_parse_bad:
                partial.append((seed, n_api_bad, n_parse_bad, len(rows)))
    return {
        "attempted": attempted, "excluded": excluded, "partial": partial,
        "analysed": attempted - len(excluded), "analysed_seeds": sorted(analysed_seeds),
    }


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    out: list[str] = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    res = {k: audit(p) for k, p in ARMS.items()}

    emit("=" * 92)
    emit("PHASE 6d — DENOMINATORS AFTER THE EXCLUSION RULE")
    emit("=" * 92)
    emit("")
    emit("EXCLUDED = zero valid operator actions (total API transmission failure).")
    emit("INCLUDED = any valid operator actions, partial transmission failures included.")
    emit("Nothing keeps a denominator by inheritance.")
    emit("")
    emit(f"{'anatomy':<16} {'arm':<11} {'attempted':>10} {'excluded':>9} {'analysed':>9} "
         f"{'partial':>8}  exclusion reasons")
    emit("-" * 92)
    for (an, arm), r in res.items():
        reasons = ("; ".join(f"seed {s} (ep{e}, {n} rows): {why}"
                             for s, e, n, why in r["excluded"]) or "none")
        emit(f"{an:<16} {arm:<11} {r['attempted']:>10} {len(r['excluded']):>9} "
             f"{r['analysed']:>9} {len(r['partial']):>8}  {reasons}")

    # ---- pairing consequences
    emit("")
    emit("=" * 92)
    emit("PAIRING AFTER EXCLUSION (a seed excluded in one arm is dropped from paired tests)")
    emit("=" * 92)
    pair_rows = []
    seen = []
    for (an, arm) in res:
        if an not in seen:
            seen.append(an)
    for an in seen:
        if (an, "wire_only") not in res or (an, "overlay") not in res:
            continue
        w, o = res[(an, "wire_only")], res[(an, "overlay")]
        sw, so = set(w["analysed_seeds"]), set(o["analysed_seeds"])
        pairs = sorted(sw & so)
        dropped = sorted((sw | so) - set(pairs))
        emit(f"  {an:<16} wire_only analysed {len(sw):>3}   overlay analysed {len(so):>3}   "
             f"complete pairs {len(pairs):>3}   dropped from pairing: "
             f"{dropped if dropped else 'none'}")
        pair_rows.append([an, len(sw), len(so), len(pairs),
                          ";".join(str(d) for d in dropped)])

    # ---- partial-failure detail
    emit("")
    emit("=" * 92)
    emit("PARTIAL TRANSMISSION FAILURES (retained; listed for the exclusion audit)")
    emit("=" * 92)
    any_partial = False
    for (an, arm), r in res.items():
        for seed, nb, npb, tot in r["partial"]:
            any_partial = True
            emit(f"  {an:<16} {arm:<11} seed {seed}: {nb} api_ok=False, "
                 f"{npb} parse_ok=False of {tot} rows -> RETAINED")
    if not any_partial:
        emit("  none")

    with open(RESULTS / "denominators.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "arm", "attempted", "excluded", "analysed",
                    "exclusion_reasons"])
        for (an, arm), r in res.items():
            reasons = ("; ".join(f"seed {s} (ep{e}, {n} rows): {why}"
                                 for s, e, n, why in r["excluded"]) or "none")
            w.writerow([an, arm, r["attempted"], len(r["excluded"]), r["analysed"], reasons])

    with open(RESULTS / "phase6d_pairing.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "wire_only_analysed", "overlay_analysed",
                    "complete_pairs", "seeds_dropped_from_pairing"])
        w.writerows(pair_rows)

    (RESULTS / "phase6d_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'denominators.csv'}")
    emit(f"wrote {RESULTS/'phase6d_pairing.csv'}")
    emit(f"wrote {RESULTS/'phase6d_report.txt'}")


if __name__ == "__main__":
    main()
