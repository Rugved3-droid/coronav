"""Phase 6e — API failure audit as a selection-bias question.

The manuscript's Methods assert exclusions "were not outcome-dependent". That is a claim to
be TESTED, not repeated.

Two DIFFERENT things must be separated, because conflating them gives a misleading answer:

  (a) WHOLE-RUN OUTAGES. An episode in which every call fails contributes its entire length
      to the raw failure count. These episodes are already removed by the exclusion rule
      (Phase 6d), so they cannot bias the analysed data — they only determine which episodes
      exist. Raw per-call rates are dominated by these.

  (b) SPORADIC FAILURES INSIDE RETAINED EPISODES. These DO bias the analysed data, because
      a failed call is not skipped: run_coronary.py executes action_arr = [[0.0, 0.0]], a
      null HOLD, and continues. So each such failure consumes one step of the episode's
      budget. This is the bias-relevant quantity.

Reported separately, with the arm comparison run on (b).

One trace row == one operator.act() call == one API call.
A HOLD is injected whenever parse_ok is False (api_ok False implies parse_ok False).

READ-ONLY with respect to raw logs. No API calls made by this script.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

RESULTS = Path(__file__).resolve().parent.parent / "results"
R = r"D:\steve\pilot\runs"

ARMS = {
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


def episodes(path: str) -> dict[int, list[dict]]:
    by: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by[r["episode"]].append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["step"])
    return dict(by)


def arm_stats(eps: dict[int, list[dict]]) -> dict:
    s = {
        "n_eps": len(eps), "calls_all": 0, "fails_all": 0,
        "excl_eps": 0, "excl_calls": 0, "excl_fails": 0,
        "ret_eps": 0, "ret_calls": 0, "ret_fails": 0, "ret_holds": 0,
        "ret_partial_eps": 0, "fail_steps": [], "fail_frac": [],
        "ep_lengths": [], "ret_holds_per_ep": [],
    }
    for ep, rows in eps.items():
        n = len(rows)
        n_api_bad = sum(1 for r in rows if r.get("api_ok") is False)
        n_holds = sum(1 for r in rows if r.get("parse_ok") is False)
        n_valid = sum(1 for r in rows
                      if r.get("api_ok", True) and r.get("parse_ok", True))
        s["calls_all"] += n
        s["fails_all"] += n_api_bad
        s["ep_lengths"].append(n)
        if n_valid == 0:                      # (a) whole-run outage -> excluded
            s["excl_eps"] += 1
            s["excl_calls"] += n
            s["excl_fails"] += n_api_bad
        else:                                 # (b) retained -> can bias the analysis
            s["ret_eps"] += 1
            s["ret_calls"] += n
            s["ret_fails"] += n_api_bad
            s["ret_holds"] += n_holds
            s["ret_holds_per_ep"].append(n_holds)
            if n_api_bad or n_holds:
                s["ret_partial_eps"] += 1
            for r in rows:
                if r.get("api_ok") is False:
                    s["fail_steps"].append(r["step"])
                    s["fail_frac"].append(r["step"] / max(1, n))
    return s


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    out: list[str] = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    S = {k: arm_stats(episodes(p)) for k, p in ARMS.items()}

    emit("=" * 100)
    emit("PHASE 6e — API FAILURE AUDIT (selection-bias test, not bookkeeping)")
    emit("=" * 100)
    emit("")
    emit("A failed call is NOT skipped: run_coronary.py executes [[0.0, 0.0]] — a null HOLD —")
    emit("and continues. Every failure inside a retained episode therefore consumes one step")
    emit("of that episode's budget. That is the bias-relevant quantity.")
    emit("")
    emit("Whole-run outages (every call failed) are removed by the Phase 6d exclusion rule and")
    emit("cannot bias the analysed data; they dominate the RAW per-call counts, so raw rates")
    emit("are reported but are NOT the basis for the arm comparison.")

    emit("")
    emit("-" * 100)
    emit("RAW (all episodes) vs RETAINED-ONLY (analysed episodes)")
    emit("-" * 100)
    emit(f"{'arm':<22} {'raw fails/calls':>18} {'raw rate':>9} | "
         f"{'excl eps':>8} {'ret fails/calls':>18} {'ret rate':>9} {'holds/ep':>9}")
    emit("-" * 100)
    for (an, arm), s in S.items():
        raw = s["fails_all"] / s["calls_all"] if s["calls_all"] else float("nan")
        ret = s["ret_fails"] / s["ret_calls"] if s["ret_calls"] else float("nan")
        hpe = np.mean(s["ret_holds_per_ep"]) if s["ret_holds_per_ep"] else 0.0
        emit(f"{an + ' ' + arm:<22} {str(s['fails_all']) + '/' + str(s['calls_all']):>18} "
             f"{raw:>8.3%} | {s['excl_eps']:>8} "
             f"{str(s['ret_fails']) + '/' + str(s['ret_calls']):>18} {ret:>8.3%} {hpe:>9.2f}")

    emit("")
    emit("=" * 100)
    emit("BIAS-RELEVANT TEST: per-call failure rate among RETAINED episodes, by arm")
    emit("=" * 100)
    rows_csv = []
    for an in ("A1", "A2", "A3", "V2", "V3", "V4", "MONO120", "BI120", "OLD15"):
        if (an, "wire_only") not in S or (an, "overlay") not in S:
            continue
        w, o = S[(an, "wire_only")], S[(an, "overlay")]
        tbl = [[w["ret_fails"], w["ret_calls"] - w["ret_fails"]],
               [o["ret_fails"], o["ret_calls"] - o["ret_fails"]]]
        orr, p = stats.fisher_exact(tbl)
        rw = w["ret_fails"] / w["ret_calls"] if w["ret_calls"] else float("nan")
        ro = o["ret_fails"] / o["ret_calls"] if o["ret_calls"] else float("nan")
        raw_tbl = [[w["fails_all"], w["calls_all"] - w["fails_all"]],
                   [o["fails_all"], o["calls_all"] - o["fails_all"]]]
        _, p_raw = stats.fisher_exact(raw_tbl)
        verdict = ("DIFFERS" if p < 0.05 else "no difference")
        emit("")
        emit(f"  {an}:  [{verdict} among retained episodes]")
        emit(f"    wire_only retained {w['ret_fails']:>4}/{w['ret_calls']:<6} = {rw:.4%}   "
             f"holds/episode {np.mean(w['ret_holds_per_ep']) if w['ret_holds_per_ep'] else 0:.2f}")
        emit(f"    overlay   retained {o['ret_fails']:>4}/{o['ret_calls']:<6} = {ro:.4%}   "
             f"holds/episode {np.mean(o['ret_holds_per_ep']) if o['ret_holds_per_ep'] else 0:.2f}")
        emit(f"    Fisher (retained only): OR = {orr:.4g}, two-sided p = {p:.3g}")
        emit(f"    Fisher (raw, for contrast): two-sided p = {p_raw:.3g}   "
             f"[excluded eps: wire_only {w['excl_eps']}, overlay {o['excl_eps']}]")
        rows_csv.append([an, w["ret_calls"], w["ret_fails"], f"{rw:.6f}",
                         o["ret_calls"], o["ret_fails"], f"{ro:.6f}",
                         f"{orr:.6g}", f"{p:.3g}", f"{p_raw:.3g}",
                         w["excl_eps"], o["excl_eps"],
                         f"{np.mean(w['ret_holds_per_ep']) if w['ret_holds_per_ep'] else 0:.3f}",
                         f"{np.mean(o['ret_holds_per_ep']) if o['ret_holds_per_ep'] else 0:.3f}"])

    emit("")
    emit("=" * 100)
    emit("BUDGET CONSUMED BY INJECTED HOLDS, among retained episodes")
    emit("=" * 100)
    for (an, arm), s in S.items():
        if not s["ret_holds"]:
            continue
        frac = s["ret_holds"] / s["ret_calls"] if s["ret_calls"] else float("nan")
        emit(f"  {an} {arm}: {s['ret_holds']} holds over {s['ret_calls']} steps "
             f"({frac:.2%} of the action budget), in {s['ret_partial_eps']}/{s['ret_eps']} "
             f"retained episodes")

    emit("")
    emit("=" * 100)
    emit("STEP INDEX AT WHICH API FAILURES OCCURRED (all episodes)")
    emit("=" * 100)
    for (an, arm), s in S.items():
        if not s["fail_steps"]:
            continue
        fs = np.asarray(s["fail_steps"])
        ff = np.asarray(s["fail_frac"])
        emit(f"  {an} {arm}: n={len(fs)}  step median {np.median(fs):.0f} "
             f"[{fs.min()}, {fs.max()}]   position-in-episode median {np.median(ff):.2f}")
        hist = Counter((int(x) // 10) * 10 for x in fs)
        emit("      step-decade histogram: " +
             "  ".join(f"{k}-{k+9}:{hist[k]}" for k in sorted(hist)))

    with open(RESULTS / "phase6e_percall_rates.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "wo_retained_calls", "wo_retained_fails", "wo_retained_rate",
                    "ov_retained_calls", "ov_retained_fails", "ov_retained_rate",
                    "fisher_or_retained", "fisher_p_retained", "fisher_p_raw_all_episodes",
                    "wo_excluded_eps", "ov_excluded_eps",
                    "wo_holds_per_retained_ep", "ov_holds_per_retained_ep"])
        w.writerows(rows_csv)

    with open(RESULTS / "phase6e_failure_steps.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "arm", "step", "position_in_episode"])
        for (an, arm), s in S.items():
            for st, fr in zip(s["fail_steps"], s["fail_frac"]):
                w.writerow([an, arm, st, f"{fr:.4f}"])

    (RESULTS / "phase6e_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6e_report.txt'}")
    emit(f"wrote {RESULTS/'phase6e_percall_rates.csv'}")
    emit(f"wrote {RESULTS/'phase6e_failure_steps.csv'}")


if __name__ == "__main__":
    main()
