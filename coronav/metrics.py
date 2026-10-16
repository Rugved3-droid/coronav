"""CoroNav metrics: per-episode and per-run summaries.

``lm_metrics()`` computes the manuscript's secondary endpoint f_rot_LM. Its
output key is ``lm_rot_mm`` for historical reasons; the quantity is a
dimensionless fraction in [0, 1], not a length. The function is described as a
verbatim port of the research codebase's ``run_biplane.py:_lm_metrics()``.
That original file and the original traces are not in this repository, so the
port cannot be checked against them here (docs/MANUSCRIPT_CONCORDANCE.md).
Its arithmetic is deliberately left unchanged.

``episode_outcome()`` computes the primary (navigation) endpoint inputs for
every attempted episode, independently of the left-main phase.
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

    Definition (manuscript f_rot_LM)::

        f_rot_LM = sum(|d_after - d_before| over LM-phase rotate-intent steps)
                   / sum(|d_after - d_before| over all LM-phase steps)

    where d is the tip-to-target distance, "LM phase" means the row's
    post-step tip is classified ``left_main``, a rotate-intent step has
    ``intended_direction`` in {rotate_cw, rotate_ccw}, and only rows with
    ``api_ok`` and ``parse_ok`` count. Numerator and denominator are sums over
    the same phase, so the units (mm) cancel and episode length cancels.

    Returns
    -------
    dict with keys:
        lm_rot_mm   : float  — f_rot_LM, dimensionless, range [0, 1]
                               (name kept for compatibility; not millimetres)
        lm_rot_pct  : float  — lm_rot_mm expressed as percentage
        lm_rot_steps: int    — left-main-phase rotate-intent count
        lm_total_steps: int  — all valid steps in LM phase
        success     : bool   — LEGACY: terminal=True AND truncation=False.
                               Counts a target reached on the final allowed
                               step as a failure (stEVE sets both flags then).
                               Use ``episode_outcome()`` for navigation.
        steps       : int or None — LEGACY step count for ``success`` episodes
    Returns None if the episode has no valid rows OR no left-main-phase
    distance change. Such episodes are dropped by
    ``episode_metrics_from_trace()``; that is a different (broader) exclusion
    than the manuscript's "zero valid operator actions" rule, so do not use
    the length of its output as the number of attempted episodes.
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


def episode_outcome(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Navigation outcome for ONE episode (primary-endpoint input).

    success      : the target was reached (any row with ``terminal`` True),
                   including on the final allowed step.
    steps        : step index at which the target was reached, else None.
    steps_taken  : number of steps executed.
    n_valid      : rows with ``api_ok`` and ``parse_ok``.
    non_attempt  : True if the episode had zero valid operator actions
                   (manuscript exclusion rule).
    failed_call_fraction : fraction of rows that were not valid actions.
    """
    valid = [r for r in rows if r.get("api_ok", True) and r.get("parse_ok", True)]
    reached = [r for r in rows if r.get("terminal")]
    success = bool(reached)
    steps = int(reached[0].get("step", rows.index(reached[0]) + 1)) if success else None
    return {
        "success": success,
        "steps": steps,
        "steps_taken": len(rows),
        "n_valid": len(valid),
        "non_attempt": len(valid) == 0,
        "failed_call_fraction": (1.0 - len(valid) / len(rows)) if rows else float("nan"),
    }


def outcomes_from_trace(trace_path: str) -> List[Dict[str, Any]]:
    """Per-episode navigation outcomes for every episode in a trace file."""
    results = []
    for ep, rows in sorted(_rows_by_episode(trace_path).items()):
        o = episode_outcome(rows)
        o["episode"] = ep
        o["seed"] = rows[0].get("seed") if rows else None
        results.append(o)
    return results


def _rows_by_episode(trace_path: str) -> Dict[int, List[Dict[str, Any]]]:
    rows_by_ep: Dict[int, List] = {}
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                ep = r.get("episode", 0)
                rows_by_ep.setdefault(ep, []).append(r)
    return rows_by_ep


def episode_metrics_from_trace(trace_path: str) -> List[Dict[str, Any]]:
    """Load a trace.jsonl file and compute per-episode metrics.

    Returns a list of metric dicts (one per episode) with an additional
    ``episode`` key.
    """
    results = []
    for ep, rows in sorted(_rows_by_episode(trace_path).items()):
        m = lm_metrics(rows)
        if m is not None:
            m["episode"] = ep
            results.append(m)
    return results


def run_summary(ep_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Descriptive summary of ``lm_metrics()`` outputs (f_rot_LM median/IQR).

    ``success_*`` and ``steps_*`` here use the LEGACY ``lm_metrics`` success
    definition and only cover episodes with left-main-phase movement; they are
    success-conditioned and are NOT the manuscript's primary navigation
    analysis. Use ``episode_outcome()`` / ``outcomes_from_trace()`` for that.
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
