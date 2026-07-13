"""CoroNav results reporter.

Reads trace.jsonl files from a benchmark run and prints a formatted table
matching the statistics reported in the paper.

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

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from coronav.metrics import episode_metrics_from_trace, lm_metrics, run_summary

try:
    from scipy.stats import mannwhitneyu
    _SCIPY = True
except ImportError:
    _SCIPY = False


ANATOMY_LABELS = {
    "a1": "A1 (VMR0066)",
    "a2": "A2 (ASOCA N12)",
    "a3": "A3 (ASOCA N5)",
}

PAPER_BASELINE = {
    "a1": {"wire_only": 0.1452, "overlay": 0.1749, "p": 0.0004, "n": 25},
    "a2": {"wire_only": None,   "overlay": None,    "p": 3e-6,   "n": 25},
    "a3": {"wire_only": None,   "overlay": None,    "p": 9e-6,   "n": 25},
}


def fmt_p(p: Optional[float]) -> str:
    if p is None:
        return "—"
    if p < 0.001:
        return f"{p:.2e}"
    return f"{p:.4f}"


def report_trace(trace_path: Path, label: Optional[str] = None) -> Dict:
    ep_metrics = episode_metrics_from_trace(str(trace_path))
    if not ep_metrics:
        print(f"  WARNING: No valid episodes in {trace_path}")
        return {}
    summary = run_summary(ep_metrics)
    lbl = label or trace_path.parent.name
    return {"label": lbl, "summary": summary, "ep_metrics": ep_metrics}


def print_single(result: Dict, paper_ref: Optional[Dict] = None):
    s = result["summary"]
    lbl = result["label"]
    print(f"\n{'='*60}")
    print(f"  {lbl}")
    print(f"{'='*60}")
    print(f"  Episodes:        {s['n']}")
    print(f"  lm_rot_mm median: {s['lm_rot_mm_median']:.4f}")
    print(f"  lm_rot_mm mean:   {s['lm_rot_mm_mean']:.4f}")
    q25, q75 = s["lm_rot_mm_iqr"]
    print(f"  lm_rot_mm IQR:    [{q25:.4f}, {q75:.4f}]")
    print(f"  Success rate:    {s['success_n']}/{s['n']} = {s['success_rate']:.1%}")
    if s["steps_median"] == s["steps_median"]:  # not nan
        print(f"  Steps (median):  {s['steps_median']:.0f}")
    if paper_ref:
        wo = paper_ref.get("wire_only")
        ov = paper_ref.get("overlay")
        p  = paper_ref.get("p")
        if wo is not None:
            print(f"\n  Paper baseline (wire_only → overlay): {wo:.4f} → {ov:.4f}, p={fmt_p(p)}")


def print_comparison(results: List[Dict]):
    if len(results) < 2:
        print("Need at least 2 runs to compare.")
        return

    print(f"\n{'='*70}")
    print(f"  Comparison: {' vs '.join(r['label'] for r in results)}")
    print(f"{'='*70}")
    print(f"  {'Run':<30}  {'median':>8}  {'mean':>8}  {'n':>4}  {'success':>8}")
    for r in results:
        s = r["summary"]
        print(
            f"  {r['label']:<30}  {s['lm_rot_mm_median']:>8.4f}"
            f"  {s['lm_rot_mm_mean']:>8.4f}"
            f"  {s['n']:>4}"
            f"  {s['success_rate']:>7.1%}"
        )

    if len(results) == 2 and _SCIPY:
        a = [m["lm_rot_mm"] for m in results[0]["ep_metrics"]]
        b = [m["lm_rot_mm"] for m in results[1]["ep_metrics"]]
        stat, p = mannwhitneyu(a, b, alternative="two-sided")
        print(f"\n  Mann-Whitney U: stat={stat:.1f}, p={fmt_p(p)}")
    elif len(results) == 2 and not _SCIPY:
        print("\n  (Install scipy for Mann-Whitney U: pip install scipy)")


def find_traces(run_dir: Path) -> List[Tuple[str, Path]]:
    """Return (anatomy_key, trace_path) pairs under a run directory."""
    found = []
    for akey in ["a1", "a2", "a3"]:
        tp = run_dir / akey / "trace.jsonl"
        if tp.exists():
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
                r = report_trace(tp, label=f"{rdir.name}/{akey}")
                if r:
                    all_results.append(r)
        print_comparison(all_results)

    elif args.trace:
        for tp in args.trace:
            r = report_trace(tp)
            if r:
                akey = tp.parent.name
                print_single(r, paper_ref=PAPER_BASELINE.get(akey))

    elif args.run_dir:
        traces = find_traces(args.run_dir)
        if not traces:
            print(f"No trace.jsonl found under {args.run_dir}")
            sys.exit(1)
        for akey, tp in traces:
            lbl = ANATOMY_LABELS.get(akey, akey)
            r = report_trace(tp, label=lbl)
            if r:
                print_single(r, paper_ref=PAPER_BASELINE.get(akey))

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
