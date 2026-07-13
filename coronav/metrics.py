"""CoroNav metrics: per-episode and per-run summaries.

The authoritative metric function is ``lm_metrics()``, ported verbatim from
the paper's run_biplane.py:_lm_metrics(). All numbers in RESULTS.md were
produced by this function on the trace files described in PROTOCOL.md.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

import numpy as np


def lm_metrics(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Compute per-episode LM-phase metrics from a trace row list.

    Parameters
    ----------
    rows : list of dicts — all rows for ONE episode from a trace.jsonl file.
        Rows must have fields: api_ok, parse_ok, tip_branch_obs,
        is_rotate_step (or intended_direction), tip_target_dist_after
        (or dist_delta), terminal, truncation.

    Returns
    -------
    dict with keys:
        lm_rot_mm   : float  — primary metric: fraction of LM wire-movement
                               that occurred during rotation steps
                               (dimensionless, range [0, 1])
        lm_rot_pct  : float  — lm_rot_mm expressed as percentage
        lm_rot_steps: int    — rotation steps in LM phase
        lm_total_steps: int  — all steps in LM phase
        success     : bool   — episode reached target (terminal=True, truncation=False)
        steps       : int or None — step count for successful episodes
    Returns None if episode has no valid LM data.
    """
    valid = [r for r in rows if r.get("api_ok", True) and r.get("parse_ok", True)]
    if not valid:
        return None

    lm_rot_steps = 0
    lm_total_steps = 0
    rot_dist_sum = 0.0
    all_dist_sum = 0.0

    for r in valid:
        if r.get("tip_branch_obs", "") != "left_main":
            continue
        lm_total_steps += 1

        if "is_rotate_step" in r:
            is_rot = bool(r["is_rotate_step"])
        else:
            is_rot = r.get("intended_direction", "") in ("rotate_cw", "rotate_ccw")

        if "tip_target_dist_after" in r:
            dc = abs(r["tip_target_dist_after"] - r["tip_target_dist"])
        elif "dist_delta" in r:
            dc = abs(r.get("dist_delta", 0.0))
        else:
            dc = 0.0

        if is_rot:
            lm_rot_steps += 1
            rot_dist_sum += dc
        all_dist_sum += dc

    if all_dist_sum == 0.0:
        return None

    terminal_rows = [r for r in rows if r.get("terminal")]
    success = bool(
        terminal_rows and not terminal_rows[-1].get("truncation", True)
    )
    steps = int(terminal_rows[-1].get("step", len(rows))) if (success and terminal_rows) else None

    lm_rot_mm = rot_dist_sum / all_dist_sum

    return {
        "lm_rot_mm": lm_rot_mm,
        "lm_rot_pct": lm_rot_mm * 100.0,
        "lm_rot_steps": lm_rot_steps,
        "lm_total_steps": lm_total_steps,
        "success": success,
        "steps": steps,
    }


def episode_metrics_from_trace(trace_path: str) -> List[Dict[str, Any]]:
    """Load a trace.jsonl file and compute per-episode metrics.

    Returns a list of metric dicts (one per episode) with an additional
    ``episode`` key.
    """
    rows_by_ep: Dict[int, List] = {}
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                ep = r.get("episode", 0)
                rows_by_ep.setdefault(ep, []).append(r)

    results = []
    for ep, rows in sorted(rows_by_ep.items()):
        m = lm_metrics(rows)
        if m is not None:
            m["episode"] = ep
            results.append(m)
    return results


def run_summary(ep_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-episode metrics into a run-level summary.

    Matches the summary statistics reported in the paper (median + Mann-Whitney
    pre-specified for the right-skewed lm_rot_mm distribution).
    """
    rot_mm = np.array([m["lm_rot_mm"] for m in ep_metrics])
    successes = [m for m in ep_metrics if m["success"]]
    steps = np.array([m["steps"] for m in successes]) if successes else np.array([])

    return {
        "n": len(rot_mm),
        "lm_rot_mm_median": float(np.median(rot_mm)) if len(rot_mm) else float("nan"),
        "lm_rot_mm_mean": float(np.mean(rot_mm)) if len(rot_mm) else float("nan"),
        "lm_rot_mm_iqr": (
            float(np.percentile(rot_mm, 25)),
            float(np.percentile(rot_mm, 75)),
        ) if len(rot_mm) else (float("nan"), float("nan")),
        "success_n": len(successes),
        "success_rate": len(successes) / len(ep_metrics) if ep_metrics else float("nan"),
        "steps_median": float(np.median(steps)) if len(steps) else float("nan"),
        "steps_mean": float(np.mean(steps)) if len(steps) else float("nan"),
    }
