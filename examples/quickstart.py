"""CoroNav quickstart — A1 (VMR0066, bundled), 3 episodes, wire_only fluoroscopy.

A 3-episode smoke run that shows the pipeline executes. It is not comparable
with the manuscript's n=25 arms and is not a reproduction of any result.
Runs at the protocol timestep (0.001 s) and makes ~60 paid API calls/episode.

Prerequisites:
    pip install -e .
    export ANTHROPIC_API_KEY=...   # or set it in .env

Run:
    python examples/quickstart.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

ANATOMY_DIR = ROOT / "data" / "anatomy" / "a1_vmr0066"
N_EPISODES = 3
N_STEPS = 60
SEEDS = [5001, 5012, 5023]  # first 3 of the A1 seeds in benchmarks/protocol.json


def main():
    if not ANATOMY_DIR.exists():
        print(f"ERROR: Anatomy directory not found: {ANATOMY_DIR}")
        print("The A1 anatomy should be bundled. If you moved data/, point ANATOMY_DIR above.")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        print("  Or copy .env.example to .env and fill it in.")
        sys.exit(1)

    print("=== CoroNav Quickstart ===")
    print(f"Anatomy: A1 (VMR0066) at {ANATOMY_DIR}")
    print(f"Episodes: {N_EPISODES}, steps/episode: {N_STEPS}")
    print()

    from coronav.env import build_env, run_episode
    from coronav.metrics import episode_outcome, lm_metrics, run_summary
    from coronav.operator.claude import ClaudeOperator

    print("Building environment (first run compiles SOFA — may take ~60s)...")
    env, sim, fluoro, branch_kds, mid_lad, binary_mask = build_env(
        anatomy_dir=str(ANATOMY_DIR),
        n_steps=N_STEPS,
        image_rot_zx=[0, -40],
    )

    operator = ClaudeOperator()
    all_rows = []

    for i, seed in enumerate(SEEDS):
        print(f"\n--- Episode {i+1}/{N_EPISODES}  (seed={seed}) ---")
        operator.reset()
        rows = run_episode(
            env=env,
            sim=sim,
            fluoro=fluoro,
            binary_mask=binary_mask,
            branch_kds=branch_kds,
            mid_lad=mid_lad,
            operator=operator,
            seed=seed,
            episode_num=i,
            n_steps=N_STEPS,
            mode="wire_only",
            verbose=True,
        )
        all_rows.extend(rows)

        out = episode_outcome(rows) if rows else None
        ep_m = lm_metrics(rows)
        if out:
            print(f"  reached target = {out['success']}  |  steps = {out['steps']}")
        if ep_m:
            print(f"  f_rot_LM (lm_rot_mm) = {ep_m['lm_rot_mm']:.4f}")
        else:
            print("  (no valid left-main-phase movement for this episode)")

    env.close()

    print("\n=== Run Summary ===")
    from collections import defaultdict
    rows_by_ep = defaultdict(list)
    for r in all_rows:
        rows_by_ep[r["episode"]].append(r)
    ep_metrics = []
    for ep_idx in sorted(rows_by_ep):
        m = lm_metrics(rows_by_ep[ep_idx])
        if m:
            m["episode"] = ep_idx
            ep_metrics.append(m)

    if ep_metrics:
        s = run_summary(ep_metrics)
        print(f"  f_rot_LM   median={s['lm_rot_mm_median']:.4f}  mean={s['lm_rot_mm_mean']:.4f}")
    reached = sum(episode_outcome(rows_by_ep[e])["success"] for e in rows_by_ep)
    print(f"  reached target  {reached}/{len(rows_by_ep)}")
    print()
    print("This 3-episode smoke run is not comparable with the manuscript (n=25 per arm).")
    print("Final manuscript results and their provenance: RESULTS.md.")


if __name__ == "__main__":
    main()
