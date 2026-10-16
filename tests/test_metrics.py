"""Unit tests for coronav.metrics on hand-built synthetic trace rows.

These check the mathematical definition of f_rot_LM (code name lm_rot_mm) and
of the navigation outcome. They use invented rows, not experimental data, and
are not evidence that any manuscript result reproduces.
"""
import json

import pytest

from coronav.metrics import (
    episode_metrics_from_trace,
    episode_outcome,
    lm_metrics,
    outcomes_from_trace,
    run_summary,
)


def row(step, d_before, d_after, branch="left_main", intent="advance",
        api_ok=True, parse_ok=True, terminal=False, truncation=False, episode=0):
    return {
        "episode": episode, "step": step, "seed": 1,
        "api_ok": api_ok, "parse_ok": parse_ok,
        "intended_direction": intent,
        "is_rotate_step": intent in ("rotate_cw", "rotate_ccw"),
        "tip_target_dist": d_before, "tip_target_dist_after": d_after,
        "tip_branch_obs": branch, "terminal": terminal, "truncation": truncation,
    }


def test_f_rot_lm_definition_hand_computed():
    # LM phase: advance moves 4 mm, rotate moves 1 mm, rotate moves 0.5 mm (away).
    rows = [
        row(1, 80.0, 84.0, intent="advance"),
        row(2, 84.0, 83.0, intent="rotate_cw"),
        row(3, 83.0, 83.5, intent="rotate_ccw"),
        row(4, 83.5, 60.0, branch="lad", intent="rotate_cw"),  # not LM phase
    ]
    m = lm_metrics(rows)
    assert m["lm_rot_mm"] == pytest.approx(1.5 / 5.5)
    assert m["lm_rot_steps"] == 2
    assert m["lm_total_steps"] == 3


def test_uses_absolute_per_step_change_not_net_change():
    # Net LM change is 0 but movement occurred; a net-change definition would
    # divide by zero. The implemented quantity sums |per-step change|.
    rows = [row(1, 80.0, 85.0, intent="advance"), row(2, 85.0, 80.0, intent="rotate_cw")]
    assert lm_metrics(rows)["lm_rot_mm"] == pytest.approx(0.5)


def test_dimensionless_scale_invariant():
    rows = [row(1, 80.0, 84.0), row(2, 84.0, 83.0, intent="rotate_cw")]
    scaled = [row(1, 8.0, 8.4), row(2, 8.4, 8.3, intent="rotate_cw")]
    assert lm_metrics(rows)["lm_rot_mm"] == pytest.approx(lm_metrics(scaled)["lm_rot_mm"])


def test_bounded_zero_and_one():
    no_rot = [row(1, 80.0, 84.0), row(2, 84.0, 83.0)]
    all_rot = [row(1, 80.0, 84.0, intent="rotate_cw"), row(2, 84.0, 83.0, intent="rotate_ccw")]
    assert lm_metrics(no_rot)["lm_rot_mm"] == 0.0
    assert lm_metrics(all_rot)["lm_rot_mm"] == 1.0


def test_invalid_rows_excluded_from_numerator_and_denominator():
    rows = [
        row(1, 80.0, 84.0),
        row(2, 84.0, 74.0, intent="rotate_cw", api_ok=False),
        row(3, 74.0, 73.0, intent="rotate_cw", parse_ok=False),
        row(4, 73.0, 72.0, intent="rotate_cw"),
    ]
    assert lm_metrics(rows)["lm_rot_mm"] == pytest.approx(1.0 / 5.0)


def test_is_rotate_step_field_takes_precedence_over_intent():
    r = row(1, 80.0, 84.0, intent="advance")
    r["is_rotate_step"] = True
    assert lm_metrics([r, row(2, 84.0, 85.0)])["lm_rot_mm"] == pytest.approx(0.8)


def test_returns_none_without_lm_movement():
    assert lm_metrics([row(1, 80.0, 80.0)]) is None                 # no movement
    assert lm_metrics([row(1, 80.0, 70.0, branch="lad")]) is None   # no LM rows
    assert lm_metrics([row(1, 80.0, 70.0, api_ok=False)]) is None   # no valid rows


def test_legacy_success_misses_target_reached_on_final_step():
    # stEVE sets terminal (target reached) and truncation (step limit) at the
    # same step when the target is reached on the last allowed step.
    rows = [row(1, 80.0, 70.0), row(2, 10.0, 4.0, branch="lad", terminal=True, truncation=True)]
    assert lm_metrics(rows)["success"] is False      # legacy field, documented
    assert episode_outcome(rows)["success"] is True  # manuscript definition
    assert episode_outcome(rows)["steps"] == 2


def test_episode_outcome_failure_and_non_attempt():
    fail = [row(1, 80.0, 81.0), row(2, 81.0, 82.0, truncation=True)]
    o = episode_outcome(fail)
    assert (o["success"], o["steps"], o["steps_taken"], o["non_attempt"]) == (False, None, 2, False)
    dead = [row(1, 80.0, 80.0, api_ok=False, parse_ok=False)]
    o = episode_outcome(dead)
    assert o["non_attempt"] is True and o["failed_call_fraction"] == 1.0


def test_trace_roundtrip_keeps_episodes_without_lm_movement_in_outcomes(tmp_path):
    ep0 = [row(1, 80.0, 84.0, episode=0), row(2, 84.0, 83.0, intent="rotate_cw", episode=0,
                                               terminal=True)]
    ep1 = [row(1, 80.0, 70.0, branch="lad", episode=1, truncation=True)]  # no LM rows
    p = tmp_path / "trace.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in ep0 + ep1))
    assert [m["episode"] for m in episode_metrics_from_trace(str(p))] == [0]
    outs = outcomes_from_trace(str(p))
    assert [o["episode"] for o in outs] == [0, 1]
    assert [o["success"] for o in outs] == [True, False]


def test_run_summary_median_and_iqr():
    ms = [{"lm_rot_mm": v, "success": False, "steps": None} for v in (0.0, 0.1, 0.2, 0.3)]
    s = run_summary(ms)
    assert s["n"] == 4
    assert s["lm_rot_mm_median"] == pytest.approx(0.15)
    assert s["lm_rot_mm_iqr"] == pytest.approx((0.075, 0.225))
