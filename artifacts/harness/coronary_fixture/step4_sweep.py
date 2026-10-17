"""
Step 4 — maxIt sweep + full ostium→mid-LAD traverse.

Phase 1  SWEEP
    For each maxIt ∈ {25, 50, 100, 200, 2000}, run a short traverse (N_SWEEP_STEPS).
    Per step: tip position, d_CL vs local radius (containment), jump (velocity proxy),
    wall-clock time per env.step().
    Ground-truth case (maxIt=2000) is capped at GROUND_TRUTH_STEPS to limit runtime.

Phase 2  SELECTION
    Automatically select the lowest maxIt where:
      (a) deceleration is observed (≥1 step with jump < 0.9 × free-space baseline)
      (b) containment holds (d_CL ≤ local_radius for ≥95% of steps after step 1)

Phase 3  FULL TRAVERSE
    Run 200 steps (or until target reached) at the chosen maxIt.
    Report per-step containment + velocity profile + final verdict.

Run:
    python coronary_fixture/step4_sweep.py [--max-steps N]

    --max-steps overrides the full-traverse step cap (default 200).
"""

import os
import sys
import time
import argparse
from collections import Counter
import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from coronary_fixture.env_coronary_left import build_coronary_env

# ── Constants ─────────────────────────────────────────────────────────────────
SWEEP_MAX_IT   = [25, 50, 100, 200, 2000]   # tested in ascending order
N_SWEEP_STEPS  = 20        # steps per maxIt in the sweep (except ground truth)
GROUND_TRUTH_STEPS = 5     # maxIt=2000 capped here to limit runtime (~50 min)

FREE_SPACE_MM  = 4.67      # 35 mm/s / 7.5 Hz — theoretical free-flight step size
TUNNEL_THRESH  = 3.5       # mm: d_CL beyond this = suspected tunneling
JUMP_THRESH    = 5.0       # mm: jump beyond this = solver blow-up

BRANCH_RADII = {
    "left_main": 3.0,
    "lad": 2.0,  "lcx": 1.8,
    "lad_b1": 1.4, "lad_b2": 1.0, "lad_b3": 1.2, "lad_b3_b1": 0.8,
    "lad_b4": 0.9, "lad_b5": 0.9, "lad_b6": 0.8, "lad_b7": 0.7,
    "lad_b8": 0.8, "lad_b9": 0.7,
    "lcx_b1": 1.2, "lcx_b2": 1.2, "lcx_b3": 1.0, "lcx_b4": 1.0,
    "lcx_b4_b1": 0.7, "lcx_b4_b2": 0.7,
    "lcx_b5": 0.9, "lcx_b6": 0.9, "lcx_b7": 0.8,
}


# ── Geometry helpers ──────────────────────────────────────────────────────────
def build_geometry(vt):
    cl_pts  = vt.centerline_coordinates.copy()
    kd_cl   = cKDTree(cl_pts)
    mesh    = pv.read(os.path.join(HERE, "clipped_left.vtp"))
    kd_surf = cKDTree(mesh.points)
    branch_kds = {b.name: cKDTree(b.coordinates) for b in vt.branches}
    return kd_cl, kd_surf, branch_kds, cl_pts


def measure_step(env, prev_tip, mid_lad, kd_cl, kd_surf, branch_kds):
    """Run one env.step() and return a dict of per-step metrics + wall time."""
    t0 = time.perf_counter()
    obs, reward, terminal, truncation, info = env.step((35.0, 1.0))
    wall = time.perf_counter() - t0

    tip    = np.array(env.intervention.simulation.dof_positions[0], dtype=float)
    d_cl   = float(kd_cl.query(tip)[0])
    d_surf = float(kd_surf.query(tip)[0])
    d_tgt  = float(np.linalg.norm(tip - mid_lad))
    jump   = float(np.linalg.norm(tip - prev_tip))
    near   = min(branch_kds, key=lambda n: branch_kds[n].query(tip)[0])
    r_loc  = BRANCH_RADII.get(near, 1.5)
    path   = env.pathfinder.path_length

    return dict(
        tip=tip, d_cl=d_cl, d_surf=d_surf, d_tgt=d_tgt,
        jump=jump, r_loc=r_loc, near=near, path=path,
        reward=reward, terminal=terminal, truncation=truncation,
        wall=wall, contained=(d_cl <= r_loc),
        decel=(jump < FREE_SPACE_MM * 0.9),
    )


# ── Sweep phase ───────────────────────────────────────────────────────────────
def run_sweep():
    print("=" * 80)
    print(f"PHASE 1 — maxIt SWEEP  (short traverse, {N_SWEEP_STEPS} steps each)")
    print(f"          maxIt=2000 (ground truth) capped at {GROUND_TRUTH_STEPS} steps")
    print(f"          free-space baseline = {FREE_SPACE_MM:.2f} mm/step")
    print("=" * 80)
    sys.stdout.flush()

    sweep_results = {}

    for max_it in SWEEP_MAX_IT:
        n_steps = GROUND_TRUTH_STEPS if max_it == 2000 else N_SWEEP_STEPS
        print(f"\n{'-'*70}")
        print(f"  maxIt = {max_it:>5d}   ({n_steps} steps)")
        print(f"{'-'*70}")
        sys.stdout.flush()

        env, vt, mid_lad = build_coronary_env(seed=42, max_it=max_it)
        kd_cl, kd_surf, branch_kds, _ = build_geometry(vt)

        t_reset = time.perf_counter()
        obs = env.reset()
        reset_wall = time.perf_counter() - t_reset
        print(f"  env.reset() in {reset_wall:.1f}s")
        sys.stdout.flush()

        prev_tip = np.array(env.intervention.simulation.dof_positions[0], dtype=float)

        hdr = (f"  {'step':>4}  {'jump':>6}  {'vs_free':>7}  {'d_CL':>6}"
               f"  {'r_loc':>5}  {'CONT':>4}  {'d_surf':>7}  {'wall_s':>7}"
               f"  {'near_branch':>12}")
        print(hdr)
        print("  " + "-" * 78)
        sys.stdout.flush()

        rows = []
        for sn in range(1, n_steps + 1):
            r = measure_step(env, prev_tip, mid_lad, kd_cl, kd_surf, branch_kds)
            r["step"] = sn
            rows.append(r)
            prev_tip = r["tip"]

            vs = r["jump"] - FREE_SPACE_MM
            cont_s = "YES" if r["contained"] else "NO "
            decel_s = " *" if r["decel"] else "  "
            print(f"  {sn:>4}  {r['jump']:>6.2f}  {vs:>+7.2f}  {r['d_cl']:>6.2f}"
                  f"  {r['r_loc']:>5.1f}  {cont_s}  {r['d_surf']:>7.2f}"
                  f"  {r['wall']:>7.2f}s  {r['near']:>12}{decel_s}",
                  flush=True)

            if r["terminal"] or r["truncation"]:
                print(f"  [EPISODE ENDED at step {sn}: terminal={r['terminal']} "
                      f"truncation={r['truncation']}]", flush=True)
                break

        env.close()

        # Mini-summary for this maxIt
        jumps   = [r["jump"] for r in rows]
        walls   = [r["wall"] for r in rows]
        decel_n = sum(1 for r in rows if r["decel"] and r["step"] > 1)
        cont_n  = sum(1 for r in rows if r["contained"])
        max_dcl = max(r["d_cl"] for r in rows)

        print(f"\n  Summary maxIt={max_it}: "
              f"mean_jump={np.mean(jumps):.2f}mm  "
              f"decel_steps={decel_n}/{len(rows)-1}  "
              f"contained={cont_n}/{len(rows)}  "
              f"max_d_CL={max_dcl:.2f}mm  "
              f"mean_wall={np.mean(walls):.2f}s/step")
        sys.stdout.flush()

        sweep_results[max_it] = dict(
            rows=rows, n_steps=len(rows),
            mean_jump=np.mean(jumps), mean_wall=np.mean(walls),
            decel_n=decel_n, cont_n=cont_n, max_dcl=max_dcl,
        )

    return sweep_results


# ── Selection phase ───────────────────────────────────────────────────────────
def select_max_it(sweep_results):
    """Return lowest maxIt with deceleration ≥1 step AND containment ≥95%."""
    print("\n" + "=" * 80)
    print("PHASE 2 — SELECTION")
    print("=" * 80)
    print(f"\n{'maxIt':>6}  {'steps':>5}  {'mean_jump':>10}  {'decel_steps':>11}"
          f"  {'contained':>9}  {'max_d_CL':>8}  {'mean_s/step':>11}  OK?")
    print("-" * 80)
    sys.stdout.flush()

    chosen = None
    for max_it in SWEEP_MAX_IT:
        sr = sweep_results[max_it]
        n  = sr["n_steps"]
        n_non_first = max(n - 1, 1)    # steps after step 1 (step 1 may be free-space)
        decel_ok = sr["decel_n"] >= 1
        cont_ok  = sr["cont_n"] / n >= 0.95
        ok = decel_ok and cont_ok
        print(f"{max_it:>6}  {n:>5}  {sr['mean_jump']:>10.2f}  "
              f"{sr['decel_n']:>5}/{n_non_first:<5}  "
              f"{sr['cont_n']:>5}/{n:<5}  "
              f"{sr['max_dcl']:>8.2f}  "
              f"{sr['mean_wall']:>11.2f}  "
              f"{'YES' if ok else 'NO'}", flush=True)
        if ok and chosen is None:
            chosen = max_it

    if chosen is None:
        print("\n  WARNING: no maxIt passed both decel+containment. "
              "Falling back to 2000.", flush=True)
        chosen = 2000

    print(f"\n  => Selected maxIt = {chosen}", flush=True)
    return chosen


# ── Full traverse phase ───────────────────────────────────────────────────────
def run_full_traverse(chosen_max_it: int, max_steps: int = 200):
    print("\n" + "=" * 80)
    print(f"PHASE 3 — FULL TRAVERSE  (maxIt={chosen_max_it}, up to {max_steps} steps)")
    print("=" * 80)
    sys.stdout.flush()

    env, vt, mid_lad = build_coronary_env(seed=42, max_it=chosen_max_it)
    kd_cl, kd_surf, branch_kds, _ = build_geometry(vt)
    obs = env.reset()

    initial_path = env.pathfinder.path_length
    print(f"\nPathfinder optimal path : {initial_path:.1f} mm")
    print(f"Target (vessel CS)      : ({mid_lad[0]:.1f}, {mid_lad[1]:.1f}, {mid_lad[2]:.1f}) mm")
    print(f"Action                  : (35.0 mm/s, 1.0 rad/s)  pure push")
    print(f"Duration/step           : {1/7.5:.4f} s  ->  ~{FREE_SPACE_MM:.2f} mm/step (free-space)")
    print()

    hdr = (f"{'Step':>4}  {'Tip (vessel CS, mm)':>34}"
           f"  {'d_CL':>6}  {'r_loc':>5}  {'CONT':>4}  {'d_surf':>7}"
           f"  {'d_tgt':>6}  {'jump':>6}  {'vs_free':>7}"
           f"  {'path_rem':>8}  {'near_branch':>12}  {'wall_s':>6}  flags")
    print(hdr)
    print("-" * 160)
    print(f"  [free-space baseline = {FREE_SPACE_MM:.2f} mm/step  |  * = deceleration]")
    sys.stdout.flush()

    prev_tip  = np.array(env.intervention.simulation.dof_positions[0], dtype=float)
    log_rows  = []
    step_n    = 0
    terminal  = False
    truncation = False

    while not (terminal or truncation) and step_n < max_steps:
        step_n += 1
        r = measure_step(env, prev_tip, mid_lad, kd_cl, kd_surf, branch_kds)
        r["step"] = step_n
        log_rows.append(r)
        prev_tip = r["tip"]
        terminal   = r["terminal"]
        truncation = r["truncation"]

        tip = r["tip"]
        vs  = r["jump"] - FREE_SPACE_MM
        cont_s  = "YES" if r["contained"] else "NO "
        flags = []
        if np.any(np.isnan(tip)):     flags.append("NAN")
        if r["d_cl"] > TUNNEL_THRESH: flags.append(f"TUNNEL(d={r['d_cl']:.1f})")
        if r["jump"] > JUMP_THRESH:   flags.append(f"JUMP({r['jump']:.1f})")
        if r["decel"] and step_n > 1: flags.append("*")
        flag_s = " ".join(flags)

        print(f"{step_n:>4}  ({tip[0]:>8.2f},{tip[1]:>8.2f},{tip[2]:>8.2f})"
              f"  {r['d_cl']:>6.2f}  {r['r_loc']:>5.1f}  {cont_s}  {r['d_surf']:>7.2f}"
              f"  {r['d_tgt']:>6.2f}  {r['jump']:>6.2f}  {vs:>+7.2f}"
              f"  {r['path']:>8.1f}  {r['near']:>12}  {r['wall']:>6.2f}s  {flag_s}",
              flush=True)

    env.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 80)
    print(f"FULL TRAVERSE SUMMARY  (maxIt={chosen_max_it})")
    print("=" * 80)

    target_reached = any(r["terminal"] for r in log_rows)
    print(f"\nOutcome")
    print(f"  Target reached        : {target_reached}")
    print(f"  Truncated             : {any(r['truncation'] for r in log_rows)}")
    print(f"  Total steps           : {step_n}")

    if log_rows:
        final_path = log_rows[-1]["path"]
        consumed   = initial_path - final_path
        print(f"\nPath length")
        print(f"  Pathfinder optimal    : {initial_path:.1f} mm")
        print(f"  Remaining at end      : {final_path:.1f} mm")
        print(f"  Consumed              : {consumed:.1f} mm")

    jumps   = [r["jump"] for r in log_rows]
    walls   = [r["wall"] for r in log_rows]
    dcls    = [r["d_cl"] for r in log_rows]
    tunnel_rows  = [r for r in log_rows if r["d_cl"] > TUNNEL_THRESH]
    decel_rows   = [r for r in log_rows if r["decel"] and r["step"] > 1]
    free_rows    = [r for r in log_rows if r["jump"] > FREE_SPACE_MM * 0.95 and r["step"] > 1]

    print(f"\nVelocity profile  (free-space baseline = {FREE_SPACE_MM:.2f} mm/step)")
    print(f"  Mean jump             : {np.mean(jumps):.2f} mm/step")
    print(f"  Max  jump             : {max(jumps):.2f} mm/step  (step {log_rows[np.argmax(jumps)]['step']})")
    print(f"  Steps free-space      : {len(free_rows)}/{step_n}  "
          f"({'ZERO CONTACT — check normals!' if len(free_rows) > step_n * 0.8 else 'expected'})")
    print(f"  Steps decelerating    : {len(decel_rows)}/{step_n}  "
          f"({'WALL CONTACT CONFIRMED' if len(decel_rows) > 5 else 'limited contact evidence'})")
    if decel_rows:
        min_j = min(decel_rows, key=lambda r: r["jump"])
        print(f"  Max deceleration      : jump={min_j['jump']:.2f} mm/step at step "
              f"{min_j['step']}, branch={min_j['near']}")

    print(f"\nContainment  (d_CL <= local radius, tunnel threshold={TUNNEL_THRESH}mm)")
    print(f"  Mean d_CL             : {np.mean(dcls):.2f} mm")
    print(f"  Max  d_CL             : {max(dcls):.2f} mm  (step {log_rows[np.argmax(dcls)]['step']})")
    print(f"  Contained steps       : {sum(r['contained'] for r in log_rows)}/{step_n}")
    print(f"  Tunnel-suspect steps  : {len(tunnel_rows)}")

    print(f"\nTiming  (maxIt={chosen_max_it})")
    print(f"  Mean wall/step        : {np.mean(walls):.2f}s")
    print(f"  Total wall time       : {sum(walls)/60:.1f} min")
    print(f"  Projected 200 steps   : {200*np.mean(walls)/60:.1f} min")

    # Velocity profile table (first 30 steps)
    print(f"\n  Jump per step (first {min(30, step_n)} steps):")
    print(f"  {'step':>4}  {'jump mm':>8}  {'vs_free':>8}  {'wall_s':>7}  contact?")
    for r in log_rows[:30]:
        print(f"  {r['step']:>4}  {r['jump']:>8.2f}  {r['jump']-FREE_SPACE_MM:>+8.2f}"
              f"  {r['wall']:>7.2f}  {'YES *' if r['decel'] else '---'}")

    # Branch distribution
    print(f"\nNearest-branch distribution")
    bcount = Counter(r["near"] for r in log_rows)
    for bn, cnt in bcount.most_common():
        note = " <-- possible diversion" if bn not in ("lad","left_main") and cnt > 3 else ""
        print(f"  {bn:<20}  {cnt:>4} steps  ({100*cnt/step_n:4.1f}%){note}")

    # Tunnel detail
    if tunnel_rows:
        print(f"\nTunnel-suspect details:")
        for r in tunnel_rows:
            t = r["tip"]
            print(f"  step {r['step']:3d}  "
                  f"tip=({t[0]:.1f},{t[1]:.1f},{t[2]:.1f})  "
                  f"d_CL={r['d_cl']:.2f}mm  d_surf={r['d_surf']:.2f}mm  branch={r['near']}")

    # Final verdict
    print(f"\n{'='*80}")
    all_clean = (target_reached and not tunnel_rows
                 and all(r["jump"] <= JUMP_THRESH for r in log_rows)
                 and not any(np.any(np.isnan(r["tip"])) for r in log_rows))
    if all_clean:
        print("VERDICT: PASS — wire reached mid-LAD, no tunneling, no instability.")
    else:
        issues = []
        if not target_reached: issues.append("DID NOT REACH TARGET")
        if tunnel_rows:        issues.append(f"TUNNELING SUSPECTED ({len(tunnel_rows)} steps)")
        if any(r["jump"] > JUMP_THRESH for r in log_rows):
            issues.append("INSTABILITY (large jumps)")
        print("VERDICT: NEEDS ATTENTION")
        for i in issues:
            print(f"  >> {i}")
    print("=" * 80)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-steps", type=int, default=200,
                        help="Full-traverse step cap (default 200)")
    args = parser.parse_args()

    sweep_results = run_sweep()
    chosen = select_max_it(sweep_results)
    run_full_traverse(chosen_max_it=chosen, max_steps=args.max_steps)
