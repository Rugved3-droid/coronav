"""CoroNav results reporter.

Reads trace.jsonl files from a benchmark run and prints DESCRIPTIVE summaries:
navigation outcome over all attempted episodes, and f_rot_LM (``lm_rot_mm``)
over episodes with left-main-phase movement. ``--compare`` adds an unpaired
Mann-Whitney U on f_rot_LM, which the manuscript reports only as a
sensitivity analysis.

This script does NOT implement the manuscript's confirmatory analyses
(worst-rank Wilcoxon, win ratio, log-rank, Hodges-Lehmann, paired Wilcoxon
with Holm). The original analysis scripts are not in this repository; see
docs/MANUSCRIPT_CONCORDANCE.md.

Usage
-----
    python benchmarks/report.py --run-dir runs/20260101_120000/
    python benchmarks/report.py --trace runs/20260101_120000/a1/trace.jsonl
    python benchmarks/report.py --compare runs/baseline/ runs/my_operator/
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from coronav.metrics import episode_metrics_from_trace, outcomes_from_trace, run_summary

try:
    from scipy.stats import mannwhitneyu
    _SCIPY = True
except ImportError:
    _SCIPY = False


ANATOMY_LABELS = {
    "a1": "A1 (VMR0066)",
    "a2": "A2 (ASOCA N12)",
    "a3": "A3 (ASOCA N5) — EXCLUDED, archival only",
}

# Final-manuscript values, shown for orientation only. They come from the
# original runs (not in this repository) and are NOT recomputed here; a new run
# is not expected to match them (unseeded decoding, new collection epoch).
MANUSCRIPT_REFERENCE = {
    "a1": {"success": "20/25 wire_only, 13/25 overlay",
           "f_rot_LM": "median 0.1452 wire_only vs 0.1749 overlay; paired p = 0.0147 (Holm 0.0147)"},
    "a2": {"success": "25/25 both arms; median steps 41 wire_only vs 56 overlay",
           "f_rot_LM": "median 0.0000 wire_only vs 0.0454 overlay; paired p = 0.000482 (Holm 0.000965)"},
}


def fmt_p(p: Optional[float]) -> str:
    if p is None:
        return "—"
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def report_trace(trace_path: Path, label: Optional[str] = None) -> Dict:
    outcomes = [o for o in outcomes_from_trace(str(trace_path)) if not o["non_attempt"]]
    if not outcomes:
        print(f"  WARNING: No attempted episodes in {trace_path}")
        return {}
    ep_metrics = episode_metrics_from_trace(str(trace_path))
    summary = run_summary(ep_metrics) if ep_metrics else None
    lbl = label or trace_path.parent.name
    return {"label": lbl, "summary": summary, "ep_metrics": ep_metrics,
            "outcomes": outcomes}


def print_single(result: Dict, manuscript_ref: Optional[Dict] = None):
    s = result["summary"]
    outs = result["outcomes"]
    lbl = result["label"]
    n = len(outs)
    succ = [o for o in outs if o["success"]]
    steps_all = [o["steps"] if o["success"] else o["steps_taken"] for o in outs]
    print(f"\n{'='*60}")
    print(f"  {lbl}")
    print(f"{'='*60}")
    print("  Navigation (all attempted episodes)")
    print(f"    Episodes attempted: {n}")
    print(f"    Reached target:     {len(succ)}/{n} = {len(succ)/n:.1%}")
    if succ:
        print(f"    Steps to target, successes (median): {np.median([o['steps'] for o in succ]):.1f}")
    print(f"    Steps executed, all episodes (median; failures at their last step): "
          f"{np.median(steps_all):.1f}")
    print("  f_rot_LM (code name lm_rot_mm; dimensionless)")
    if s is None:
        print("    No episode had left-main-phase movement.")
    else:
        q25, q75 = s["lm_rot_mm_iqr"]
        print(f"    Episodes with LM movement: {s['n']} of {n}")
        print(f"    median {s['lm_rot_mm_median']:.4f}  IQR [{q25:.4f}, {q75:.4f}]"
              f"  mean {s['lm_rot_mm_mean']:.4f}")
        print(f"    LM rotate intents (total): {sum(m['lm_rot_steps'] for m in result['ep_metrics'])}")
    if manuscript_ref:
        print("\n  Manuscript (original runs; not recomputed, not expected to match):")
        print(f"    navigation: {manuscript_ref['success']}")
        print(f"    f_rot_LM:   {manuscript_ref['f_rot_LM']}")


def print_comparison(results: List[Dict]):
    if len(results) < 2:
        print("Need at least 2 runs to compare.")
        return

    print(f"\n{'='*70}")
    print(f"  Comparison: {' vs '.join(r['label'] for r in results)}")
    print(f"{'='*70}")
    print(f"  {'Run':<30}  {'f_rot_LM med':>12}  {'mean':>8}  {'n_LM':>4}  {'reached':>9}")
    for r in results:
        s = r["summary"]
        outs = r["outcomes"]
        reached = sum(o["success"] for o in outs)
        med = f"{s['lm_rot_mm_median']:>12.4f}" if s else f"{'—':>12}"
        mean = f"{s['lm_rot_mm_mean']:>8.4f}" if s else f"{'—':>8}"
        n_lm = s["n"] if s else 0
        print(f"  {r['label']:<30}  {med}  {mean}  {n_lm:>4}  {reached:>3}/{len(outs):<5}")

    if len(results) == 2 and _SCIPY:
        a = [m["lm_rot_mm"] for m in results[0]["ep_metrics"]]
        b = [m["lm_rot_mm"] for m in results[1]["ep_metrics"]]
        if a and b:
            stat, p = mannwhitneyu(a, b, alternative="two-sided")
            print(f"\n  f_rot_LM unpaired Mann-Whitney U (sensitivity analysis only): "
                  f"U={stat:.1f}, p={fmt_p(p)}")
            print("  The manuscript's primary f_rot_LM test is a paired Wilcoxon with Holm "
                  "correction, which this script does not compute.")
    elif len(results) == 2 and not _SCIPY:
        print("\n  (Install scipy for Mann-Whitney U: pip install scipy)")


def find_traces(run_dir: Path) -> List[Tuple[str, Path]]:
    """Return (anatomy_key, trace_path) pairs under a run directory.

    Supports <run>/<anatomy>/trace.jsonl and <run>/<anatomy>/<mode>/trace.jsonl.
    """
    found = []
    for akey in ["a1", "a2", "a3"]:
        tp = run_dir / akey / "trace.jsonl"
        if tp.exists():
            found.append((akey, tp))
        for tp in sorted((run_dir / akey).glob("*/trace.jsonl")):
            found.append((akey, tp))
    if not found:
        tp = run_dir / "trace.jsonl"
        if tp.exists():
            found.append((run_dir.name, tp))
    return found


def main():
    parser = argparse.ArgumentParser(description="CoroNav results reporter")
    parser.add_argument("--run-dir", type=Path, help="Root run directory (contains a1/, a2/, a3/ subdirs)")
    parser.add_argument("--trace", type=Path, nargs="+", help="One or more trace.jsonl files directly")
    parser.add_argument("--compare", type=Path, nargs="+", help="Two run directories to compare")
    args = parser.parse_args()

    if args.compare:
        all_results = []
        for rdir in args.compare:
            traces = find_traces(rdir)
            for akey, tp in traces:
                r = report_trace(tp, label=str(tp.parent.relative_to(rdir.parent)))
                if r:
                    all_results.append(r)
        print_comparison(all_results)

    elif args.trace:
        for tp in args.trace:
            r = report_trace(tp)
            if r:
                akey = tp.parent.name
                print_single(r, manuscript_ref=MANUSCRIPT_REFERENCE.get(akey))

    elif args.run_dir:
        traces = find_traces(args.run_dir)
        if not traces:
            print(f"No trace.jsonl found under {args.run_dir}")
            sys.exit(1)
        for akey, tp in traces:
            lbl = ANATOMY_LABELS.get(akey, akey)
            if tp.parent.name != akey:
                lbl = f"{lbl} — {tp.parent.name}"
            r = report_trace(tp, label=lbl)
            if r:
                print_single(r, manuscript_ref=MANUSCRIPT_REFERENCE.get(akey))

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
