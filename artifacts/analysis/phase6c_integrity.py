"""Phase 6c — two integrity checks before anything reaches a manuscript.

CHECK 1 (A2 floor effect). All 25 A2 wire_only episodes score f_rot_LM = 0.0000.
Is that because the LM phase is trivially short, or because the operator never rotated,
or because the metric ZEROED real rotations? The metric weights rotation steps by
|dist_delta| (change in distance-to-target), so a rotation that turns the tip without
translating it contributes ~0 to the numerator even though it happened. Reports LM-phase
length in steps and in mm actually travelled, per arm, for all three anatomies, plus the
rotate-intent census for A2 wire_only.

CHECK 2 (A3 overlay 0/25). Strong effect, or degenerate condition? Per episode: final
distance, LCx entry, whether the wire ever left the LM, whether the budget ran out while
still closing, and instability indicators (NaN tips, resets, discontinuous jumps).

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

RESULTS = Path(__file__).resolve().parent.parent / "results"
ROT_INTENTS = {"rotate_cw", "rotate_ccw"}
JUMP_MM = 20.0          # same discontinuity threshold as scripted_stability_check.py

R = r"D:\steve\pilot\runs"
TRACES = {
    ("A1", "wire_only"): rf"{R}\ablation_prompt_robustness\v1_current\wire_only\trace.jsonl",
    ("A1", "overlay"):   rf"{R}\ablation_prompt_robustness\v1_current\overlay\trace.jsonl",
    ("A2", "wire_only"): rf"{R}\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    ("A2", "overlay"):   rf"{R}\normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl",
    ("A3", "wire_only"): rf"{R}\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl",
    ("A3", "overlay"):   rf"{R}\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl",
}


def episodes(path: str) -> dict[int, list[dict]]:
    by_ep: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by_ep[r["episode"]].append(r)
    for rows in by_ep.values():
        rows.sort(key=lambda r: r["step"])
    return dict(by_ep)


def step_travel_mm(r: dict) -> float:
    """Euclidean tip displacement during this step: gt_tip_obs (pre) -> gt_tip_pos (post)."""
    a, b = r.get("gt_tip_obs"), r.get("gt_tip_pos")
    if not a or not b:
        return float("nan")
    return float(np.linalg.norm(np.asarray(b, float) - np.asarray(a, float)))


def lm_profile(rows: list[dict]) -> dict:
    valid = [r for r in rows if r.get("api_ok", True) and r.get("parse_ok", True)]
    lm = [r for r in valid if r.get("tip_branch_obs", "") == "left_main"]
    travel = [step_travel_mm(r) for r in lm]
    travel = [t for t in travel if not math.isnan(t)]
    rot_rows = [r for r in lm if r.get("intended_direction", "") in ROT_INTENTS]
    rot_travel = [step_travel_mm(r) for r in rot_rows]
    rot_travel = [t for t in rot_travel if not math.isnan(t)]
    return {
        "lm_steps": len(lm),
        "lm_travel_mm": float(np.sum(travel)) if travel else 0.0,
        "lm_dist_mm": float(np.sum([abs(r.get("dist_delta", 0.0)) for r in lm])),
        "lm_rot_intents": len(rot_rows),
        "lm_rot_travel_mm": float(np.sum(rot_travel)) if rot_travel else 0.0,
        "lm_rot_dist_mm": float(np.sum([abs(r.get("dist_delta", 0.0)) for r in rot_rows])),
        "n_valid": len(valid),
    }


def fmt(vals: list[float], unit: str = "") -> str:
    if not vals:
        return "n/a"
    a = np.asarray(vals, float)
    return (f"median {np.median(a):.2f}{unit}  IQR[{np.percentile(a,25):.2f},"
            f"{np.percentile(a,75):.2f}]  min {a.min():.2f}  max {a.max():.2f}")


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    out: list[str] = []
    def emit(s: str = "") -> None:
        print(s)
        out.append(s)

    data = {k: episodes(p) for k, p in TRACES.items()}

    emit("=" * 78)
    emit("PHASE 6c — INTEGRITY CHECKS")
    emit("=" * 78)

    # ================= CHECK 1 =================
    emit("")
    emit("=" * 78)
    emit("CHECK 1 — IS A2's ZERO ROTATION TRIVIAL? (LM-phase size, all anatomies)")
    emit("=" * 78)
    emit("")
    emit("LM phase = rows where tip_branch_obs == 'left_main' (valid rows only).")
    emit("'travelled' = summed Euclidean tip displacement per step (gt_tip_obs -> gt_tip_pos).")
    emit("'dist-change' = summed |dist_delta|, i.e. the DENOMINATOR of f_rot_LM.")
    emit("")

    prof: dict[tuple[str, str], list[dict]] = {}
    for key, eps in data.items():
        prof[key] = [lm_profile(rows) for rows in eps.values()]

    for an in ("A1", "A2", "A3"):
        emit(f"--- {an} " + "-" * (74 - len(an)))
        for arm in ("wire_only", "overlay"):
            ps = prof[(an, arm)]
            emit(f"  {arm}")
            emit(f"    LM steps       : {fmt([p['lm_steps'] for p in ps])}")
            emit(f"    LM travelled   : {fmt([p['lm_travel_mm'] for p in ps], ' mm')}")
            emit(f"    LM dist-change : {fmt([p['lm_dist_mm'] for p in ps], ' mm')}")
            emit(f"    episodes with >=1 rotate intent in LM: "
                 f"{sum(1 for p in ps if p['lm_rot_intents'] > 0)}/{len(ps)}")
            emit(f"    total rotate intents in LM           : "
                 f"{sum(p['lm_rot_intents'] for p in ps)}")
        emit("")

    # the decisive A2 wire_only census
    emit("-" * 78)
    emit("A2 wire_only — DID THE OPERATOR ROTATE, OR DID THE METRIC ZERO IT?")
    emit("-" * 78)
    ps = prof[("A2", "wire_only")]
    n_rot_eps = sum(1 for p in ps if p["lm_rot_intents"] > 0)
    tot_rot = sum(p["lm_rot_intents"] for p in ps)
    rot_travel = sum(p["lm_rot_travel_mm"] for p in ps)
    rot_dist = sum(p["lm_rot_dist_mm"] for p in ps)
    tot_dist = sum(p["lm_dist_mm"] for p in ps)
    emit(f"  episodes with >=1 rotate intent during LM : {n_rot_eps}/{len(ps)}")
    emit(f"  total rotate intents during LM            : {tot_rot}")
    emit(f"  tip actually travelled on those steps     : {rot_travel:.3f} mm")
    emit(f"  |dist_delta| accrued on those steps       : {rot_dist:.6f} mm  <- f_rot_LM numerator")
    emit(f"  |dist_delta| accrued on all LM steps      : {tot_dist:.3f} mm  <- f_rot_LM denominator")
    emit("")
    if tot_rot == 0:
        emit("  VERDICT: the operator issued NO rotate action at all during the LM phase.")
        emit("  f_rot_LM = 0 is a true behavioural zero, not a metric artefact.")
    elif rot_dist == 0.0:
        emit("  *** VERDICT: ROTATIONS DID OCCUR and the metric ZEROED them. ***")
        emit("  The operator rotated during the LM phase, but those steps produced no change")
        emit("  in distance-to-target, so they contribute 0 to the numerator. f_rot_LM = 0.0000")
        emit("  therefore does NOT mean 'never rotated' — it means 'rotations moved the tip")
        emit("  without changing its distance to target'. Any claim that A2 wire_only never")
        emit("  rotates is FALSE and must be corrected.")
    else:
        emit("  VERDICT: rotations occurred AND contributed non-zero distance; the per-episode")
        emit("  zeros arise some other way — inspect the per-episode table below.")

    # ================= CHECK 2 =================
    emit("")
    emit("=" * 78)
    emit("CHECK 2 — A3 OVERLAY 0/25: STRONG EFFECT OR DEGENERATE CONDITION?")
    emit("=" * 78)

    a3_rows = []
    for arm in ("wire_only", "overlay"):
        for ep, rows in sorted(data[("A3", arm)].items()):
            valid = [r for r in rows if r.get("api_ok", True) and r.get("parse_ok", True)]
            last = rows[-1]
            branches = {r.get("tip_branch_obs", "") for r in rows}
            left_lm = any(b and b != "left_main" for b in branches)
            entered_lcx = any(str(b).startswith("lcx") for b in branches)
            dists = [r["tip_target_dist"] for r in rows]
            # still closing at the end? compare last 10 recorded distances
            tail = dists[-10:] if len(dists) >= 10 else dists
            closing = (tail[-1] - tail[0]) < -0.5
            # instability indicators
            nan_tip = sum(1 for r in rows
                          if any(not np.isfinite(v) for v in (r.get("gt_tip_pos") or [0.0])))
            jumps = sum(1 for a, b in zip(dists, dists[1:]) if abs(b - a) > JUMP_MM)
            resets = max((r.get("reset_attempts", 0) or 0) for r in rows)
            a3_rows.append({
                "arm": arm, "episode": ep, "seed": last["seed"],
                "success": bool(last.get("terminal")) and not bool(last.get("truncation", True)),
                "n_rows": len(rows), "n_valid": len(valid),
                "final_dist": last["tip_target_dist"], "min_dist": min(dists),
                "left_LM": left_lm, "entered_LCx": entered_lcx,
                "closing_at_end": closing, "nan_tip_rows": nan_tip,
                "big_jumps": jumps, "reset_attempts": resets,
                "all_api_failed": len(valid) == 0,
            })

    for arm in ("overlay", "wire_only"):
        sub = [r for r in a3_rows if r["arm"] == arm]
        emit("")
        emit(f"--- A3 {arm} (n={len(sub)}) " + "-" * 40)
        emit(f"  {'seed':>5} {'ok':>3} {'steps':>6} {'final':>8} {'min':>8} "
             f"{'leftLM':>7} {'LCx':>5} {'closing':>8} {'NaN':>4} {'jump':>5} {'rst':>4}")
        for r in sub:
            emit(f"  {r['seed']:>5} {('Y' if r['success'] else 'n'):>3} {r['n_rows']:>6} "
                 f"{r['final_dist']:>8.1f} {r['min_dist']:>8.1f} "
                 f"{('Y' if r['left_LM'] else 'n'):>7} {('Y' if r['entered_LCx'] else 'n'):>5} "
                 f"{('Y' if r['closing_at_end'] else 'n'):>8} {r['nan_tip_rows']:>4} "
                 f"{r['big_jumps']:>5} {r['reset_attempts']:>4}")
        fd = [r["final_dist"] for r in sub]
        md = [r["min_dist"] for r in sub]
        emit(f"  final dist : {fmt(fd,' mm')}")
        emit(f"  min dist   : {fmt(md,' mm')}")
        emit(f"  left LM: {sum(r['left_LM'] for r in sub)}/{len(sub)}   "
             f"entered LCx: {sum(r['entered_LCx'] for r in sub)}/{len(sub)}   "
             f"still closing at budget: {sum(r['closing_at_end'] for r in sub)}/{len(sub)}")
        emit(f"  NaN tip rows: {sum(r['nan_tip_rows'] for r in sub)}   "
             f"discontinuous jumps >{JUMP_MM:.0f}mm: {sum(r['big_jumps'] for r in sub)}   "
             f"episodes all-API-failed: {sum(r['all_api_failed'] for r in sub)}")

    with open(RESULTS / "phase6c_a3_episodes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(a3_rows[0].keys()))
        w.writeheader()
        w.writerows(a3_rows)

    with open(RESULTS / "phase6c_lm_profile.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["anatomy", "arm", "lm_steps", "lm_travel_mm", "lm_dist_mm",
                    "lm_rot_intents", "lm_rot_travel_mm", "lm_rot_dist_mm"])
        for (an, arm), ps in prof.items():
            for p in ps:
                w.writerow([an, arm, p["lm_steps"], f"{p['lm_travel_mm']:.4f}",
                            f"{p['lm_dist_mm']:.4f}", p["lm_rot_intents"],
                            f"{p['lm_rot_travel_mm']:.4f}", f"{p['lm_rot_dist_mm']:.6f}"])

    (RESULTS / "phase6c_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6c_report.txt'}")
    emit(f"wrote {RESULTS/'phase6c_lm_profile.csv'}")
    emit(f"wrote {RESULTS/'phase6c_a3_episodes.csv'}")


if __name__ == "__main__":
    main()
