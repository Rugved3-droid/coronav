"""
Step 4 — Rigorous instability / containment check (Fix 1+2 version).

Advances the guidewire from ostium to mid-LAD target under a scripted pure-push
action (35 mm/s, no rotation).  Every step logs:

  • Wire tip in vessel-CS (mm)
  • Tip → nearest centerline distance  (lumen-containment proxy)
  • Tip → nearest mesh surface distance (wall contact proxy)
  • Tip → target distance (vessel CS)
  • Tip jump from previous step
  • Nearest branch name
  • Pathfinder remaining path length

Flags raised for:
  TUNNEL  — tip-to-CL distance > TUNNEL_THRESH (tip may have left the lumen)
  JUMP    — tip moved > JUMP_THRESH in one step (instability / solver blowup)
  NAN     — any NaN in tip coordinates
  NEG     — large negative reward (unexpected backward progress)

Run:
    python coronary_fixture/step4_rigorous.py [--max-steps N]
"""

import os
import sys
import argparse
from collections import Counter

import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from coronary_fixture.env_coronary_left import build_coronary_env

# ── Thresholds ────────────────────────────────────────────────────────────────
# Coronary vessel radii: LM ~3mm, LAD trunk ~2mm, distal <1mm.
# Use 3.5mm as a liberal outer bound for "still in lumen".
TUNNEL_THRESH_MM = 3.5

# Any tip jump bigger than this signals a solver discontinuity.
JUMP_THRESH_MM = 5.0

# Negative reward threshold for flagging (PathLengthDelta can go slightly negative).
NEG_REWARD_THRESH = -0.1

# Per-branch approximate lumen radius (mm) — used to compare d_CL to local geometry.
# These are rough estimates for 0066_H_CORO_H; used for CONTAINMENT column only.
BRANCH_RADII = {
    "left_main": 3.0,
    "lad": 2.0,
    "lcx": 1.8,
    "lad_b1": 1.4, "lad_b2": 1.0, "lad_b3": 1.2, "lad_b3_b1": 0.8,
    "lad_b4": 0.9, "lad_b5": 0.9, "lad_b6": 0.8, "lad_b7": 0.7,
    "lad_b8": 0.8, "lad_b9": 0.7,
    "lcx_b1": 1.2, "lcx_b2": 1.2, "lcx_b3": 1.0, "lcx_b4": 1.0,
    "lcx_b4_b1": 0.7, "lcx_b4_b2": 0.7,
    "lcx_b5": 0.9, "lcx_b6": 0.9, "lcx_b7": 0.8,
}
FREE_SPACE_JUMP_MM = 4.67   # theoretical jump for zero collision: 35mm/s / 7.5Hz


def build_geometry(vt):
    """Build KDTrees from vessel-CS geometry (all in mm)."""
    cl_pts = vt.centerline_coordinates.copy()        # all branch points concatenated
    kd_cl  = cKDTree(cl_pts)

    mesh = pv.read(os.path.join(HERE, "clipped_left.vtp"))
    kd_surf = cKDTree(mesh.points)                   # clipped_left already in mm

    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}

    return kd_cl, kd_surf, branch_kds, cl_pts


def run(max_steps: int = 200):
    # ── Setup ─────────────────────────────────────────────────────────────────
    import time as _time, sys as _sys

    def _tstamp(msg):
        print(f"[{_time.strftime('%H:%M:%S')}] {msg}", flush=True)
        _sys.stdout.flush()

    _tstamp("Building environment ...")
    env, vt, mid_lad_vessel_cs = build_coronary_env(seed=42)
    _tstamp("build_coronary_env DONE")

    kd_cl, kd_surf, branch_kds, cl_pts = build_geometry(vt)
    _tstamp("build_geometry DONE")

    _tstamp("Calling env.reset() ...")
    obs = env.reset()
    _tstamp("env.reset() DONE")
    initial_path_len = env.pathfinder.path_length
    initial_inserted = float(env.intervention.simulation.inserted_lengths[0])

    print(f"\nPathfinder optimal path : {initial_path_len:.1f} mm")
    print(f"Target (vessel CS)      : ({mid_lad_vessel_cs[0]:.1f}, "
          f"{mid_lad_vessel_cs[1]:.1f}, {mid_lad_vessel_cs[2]:.1f}) mm")
    print(f"Action                  : (35.0 mm/s, 1.0 rad/s)  pure push")
    print(f"Duration/step           : {1/7.5:.4f} s  ->  ~{35.0/7.5:.2f} mm/step advance")
    print()

    # Velocity profile header — 'jump' column is the key signal.
    # FREE-SPACE baseline: 35mm/s / 7.5Hz = 4.67mm/step.
    # Wall contact manifests as jump < FREE_SPACE baseline.
    header = (f"{'Step':>4}  {'Tip (vessel CS, mm)':>34}"
              f"  {'d_CL':>6}  {'r_loc':>5}  {'CONT':>4}  {'d_surf':>7}"
              f"  {'d_tgt':>6}  {'jump':>6}  {'vs_free':>7}"
              f"  {'path_rem':>8}  {'near_branch':>12}  flags")
    print(header)
    print("-" * 150)
    print(f"  [free-space baseline jump = {FREE_SPACE_JUMP_MM:.2f} mm/step — deceleration below this = wall contact]")

    # ── Main loop ─────────────────────────────────────────────────────────────
    prev_tip    = np.array(env.intervention.simulation.dof_positions[0], dtype=float)
    log_rows    = []
    all_flags   = []
    step_n      = 0
    terminal    = False
    truncation  = False

    while not (terminal or truncation) and step_n < max_steps:
        step_n += 1
        obs, reward, terminal, truncation, info = env.step((35.0, 1.0))

        tip = np.array(env.intervention.simulation.dof_positions[0], dtype=float)

        # Geometric measures (vessel CS, mm)
        d_cl   = float(kd_cl.query(tip)[0])
        d_surf = float(kd_surf.query(tip)[0])
        d_tgt  = float(np.linalg.norm(tip - mid_lad_vessel_cs))
        jump   = float(np.linalg.norm(tip - prev_tip))

        near_branch = min(branch_kds,
                          key=lambda n: branch_kds[n].query(tip)[0])
        local_radius = BRANCH_RADII.get(near_branch, 1.5)
        contained = d_cl <= local_radius
        path_rem = env.pathfinder.path_length
        inserted = float(env.intervention.simulation.inserted_lengths[0])

        # Velocity vs free-space: negative = decelerated (wall contact evidence)
        delta_vs_free = jump - FREE_SPACE_JUMP_MM

        # Flag raising
        step_flags = []
        if np.any(np.isnan(tip)):
            step_flags.append("NAN")
        if d_cl > TUNNEL_THRESH_MM:
            step_flags.append(f"TUNNEL(d_CL={d_cl:.1f})")
        if jump > JUMP_THRESH_MM:
            step_flags.append(f"JUMP({jump:.1f}mm)")
        if reward < NEG_REWARD_THRESH:
            step_flags.append(f"NEG_R({reward:.3f})")
        # Flag free-space motion (no wall interaction)
        if jump > FREE_SPACE_JUMP_MM * 0.95 and step_n > 1:
            step_flags.append("FREE")

        flag_str = " ".join(step_flags)
        all_flags.extend(step_flags)

        row = dict(step=step_n, tip=tip.copy(), d_cl=d_cl, d_surf=d_surf,
                   d_tgt=d_tgt, jump=jump, delta_vs_free=delta_vs_free,
                   reward=reward, path_rem=path_rem, near_branch=near_branch,
                   local_radius=local_radius, contained=contained,
                   flags=step_flags, terminal=terminal,
                   truncation=truncation, inserted=inserted)
        log_rows.append(row)

        cont_str = "YES" if contained else "NO "
        print(f"{step_n:>4}  ({tip[0]:>8.2f},{tip[1]:>8.2f},{tip[2]:>8.2f})"
              f"  {d_cl:>6.2f}  {local_radius:>5.1f}  {cont_str}  {d_surf:>7.2f}"
              f"  {d_tgt:>6.2f}  {jump:>6.2f}  {delta_vs_free:>+7.2f}"
              f"  {path_rem:>8.1f}  {near_branch:>12}  {flag_str}")

        prev_tip = tip

    env.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print("STEP 4 — SUMMARY REPORT")
    print("=" * 80)

    target_reached = any(r["terminal"] for r in log_rows)
    print(f"\nOutcome")
    print(f"  Target reached        : {target_reached}")
    print(f"  Truncated (maxsteps)  : {any(r['truncation'] for r in log_rows)}")
    print(f"  Total env.step() calls: {step_n}")

    print(f"\nPath length")
    print(f"  Pathfinder optimal    : {initial_path_len:.1f} mm")
    if log_rows:
        final_path = log_rows[-1]["path_rem"]
        consumed   = initial_path_len - final_path
        print(f"  Remaining at end      : {final_path:.1f} mm")
        print(f"  Consumed              : {consumed:.1f} mm  "
              f"({'target' if target_reached else 'partial'})")

    # Wire insertion progress
    if log_rows:
        final_ins = log_rows[-1]["inserted"]
        print(f"  Wire inserted length  : {final_ins:.1f} mm")

    # Containment
    d_cls = [r["d_cl"] for r in log_rows]
    tunnel_rows = [r for r in log_rows if r["d_cl"] > TUNNEL_THRESH_MM]
    max_cl_step = max(log_rows, key=lambda r: r["d_cl"]) if log_rows else None

    print(f"\nContainment  (tip -> nearest CL point, tunnel threshold={TUNNEL_THRESH_MM}mm)")
    print(f"  Mean d_CL             : {np.mean(d_cls):.2f} mm")
    print(f"  Max  d_CL             : {max_cl_step['d_cl']:.2f} mm  "
          f"(step {max_cl_step['step']}, branch={max_cl_step['near_branch']}, "
          f"d_surf={max_cl_step['d_surf']:.2f}mm)")
    print(f"  Tunnel-suspect steps  : {len(tunnel_rows)}")
    if tunnel_rows:
        print(f"  --- TUNNEL DETAIL ---")
        for r in tunnel_rows:
            t = r["tip"]
            print(f"    step {r['step']:3d}  "
                  f"tip=({t[0]:.1f},{t[1]:.1f},{t[2]:.1f})  "
                  f"d_CL={r['d_cl']:.2f}mm  d_surf={r['d_surf']:.2f}mm  "
                  f"branch={r['near_branch']}")

    # Velocity profile (the key signal for wall contact)
    jumps = [r["jump"] for r in log_rows]
    free_steps = [r for r in log_rows if r["jump"] > FREE_SPACE_JUMP_MM * 0.95 and r["step"] > 1]
    contact_steps = [r for r in log_rows if r["jump"] < FREE_SPACE_JUMP_MM * 0.9 and r["step"] > 1]
    jump_rows = [r for r in log_rows if r["jump"] > JUMP_THRESH_MM]
    max_jmp_row = max(log_rows, key=lambda r: r["jump"]) if log_rows else None

    print(f"\nVelocity profile  (free-space baseline = {FREE_SPACE_JUMP_MM:.2f} mm/step)")
    print(f"  Mean jump                 : {np.mean(jumps):.2f} mm/step")
    print(f"  Max  jump                 : {max_jmp_row['jump']:.2f} mm/step  (step {max_jmp_row['step']})")
    print(f"  Steps at free-space speed : {len(free_steps)} / {step_n}  "
          f"({'ZERO CONTACT — collision not working' if len(free_steps) > step_n * 0.8 else 'some free motion expected'})")
    print(f"  Steps showing deceleration: {len(contact_steps)} / {step_n}  "
          f"({'WALL CONTACT CONFIRMED' if len(contact_steps) > 5 else 'insufficient evidence of contact'})")
    if contact_steps:
        min_jump_row = min(contact_steps, key=lambda r: r["jump"])
        print(f"  Min jump (max deceleration): {min_jump_row['jump']:.2f} mm/step  "
              f"at step {min_jump_row['step']}, branch={min_jump_row['near_branch']}, "
              f"d_CL={min_jump_row['d_cl']:.2f}mm")
    print(f"  Instability (jump>{JUMP_THRESH_MM}mm)  : {len(jump_rows)} steps")
    if jump_rows:
        for r in jump_rows:
            t = r["tip"]
            print(f"    step {r['step']:3d}  "
                  f"tip=({t[0]:.1f},{t[1]:.1f},{t[2]:.1f})  "
                  f"jump={r['jump']:.2f}mm  branch={r['near_branch']}")

    # Velocity profile table (first 30 steps for readability)
    print(f"\n  Jump per step (first {min(30, step_n)} steps):")
    print(f"  {'Step':>4}  {'jump mm':>8}  {'vs_free':>8}  {'contact?':>8}")
    for r in log_rows[:30]:
        decel = r["jump"] < FREE_SPACE_JUMP_MM * 0.9
        print(f"  {r['step']:>4}  {r['jump']:>8.2f}  {r['delta_vs_free']:>+8.2f}  "
              f"{'YES' if decel else '---':>8}")

    # Branch tracking
    print(f"\nNearest-branch distribution")
    bcount = Counter(r["near_branch"] for r in log_rows)
    for bn, cnt in bcount.most_common():
        pct = 100 * cnt / step_n
        divert_note = " <-- possible diversion" if (
            bn not in ("lad", "left_main") and cnt > 3) else ""
        print(f"  {bn:<20}  {cnt:>4} steps  ({pct:4.1f}%){divert_note}")

    # NaN
    nan_rows = [r for r in log_rows if np.any(np.isnan(r["tip"]))]
    print(f"\nNaN positions           : {len(nan_rows)} steps")

    # Final verdict
    print(f"\n{'='*80}")
    all_clean = (target_reached and not tunnel_rows and not jump_rows
                 and not nan_rows)
    if all_clean:
        print("VERDICT: PASS — wire reached mid-LAD, no tunneling, no instability.")
    else:
        issues = []
        if not target_reached:
            issues.append("DID NOT REACH TARGET")
        if tunnel_rows:
            issues.append(f"TUNNELING SUSPECTED ({len(tunnel_rows)} steps)")
        if jump_rows:
            issues.append(f"INSTABILITY ({len(jump_rows)} steps)")
        if nan_rows:
            issues.append("NAN POSITIONS")
        print("VERDICT: NEEDS ATTENTION")
        for issue in issues:
            print(f"  >> {issue}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-steps", type=int, default=200)
    args = parser.parse_args()
    run(max_steps=args.max_steps)
