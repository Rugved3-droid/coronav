# Superseded analyses — retained as evidence, supplying no manuscript number

Everything listed here ran at a **simulation timestep of 0.006 s**. No study arm ever did: every
operator arm ran at **0.001 s** (`run_ablation.py:628`, `run_asoca.py:431`, `run_coronary.py:419`).
The discrepancy and its consequences are recorded as **C21** and **C22** in `CORRECTIONS.md`.

**Why this matters, in one sentence.** Per-sub-step insertion is the commanded speed multiplied by
the timestep, so at 0.006 s the wire advanced six times further between contact resolutions — and
contact resolution is exactly what decides whether a blind wire tracks the lumen or catches on it.

**Nothing here is deleted.** These scripts and artifacts are the true record of what was measured,
and that record is worth keeping. They simply supply no value to the manuscript, and
`analysis/build_manuscript.py` **fails the build** if any manuscript source references a manifest
key derived from them.

## What was re-measured, and what changed

| | at 0.006 s (retired) | at 0.001 s (current) |
|---|---|---|
| Open-loop success, A1 | 56.6% | **75/75 = 100%** |
| Open-loop success, A2 | 70.9% | **75/75 = 100%** |

Re-measured by `analysis/phase7j_floor_dt001.py` over three repetitions of the full seed list,
with identical seeds, budgets, policy and success criterion. Artifacts:
`results/baselines/floor_dt001_a1.json`, `floor_dt001_a2.json`, `phase7j_report.txt`.

## Superseded scripts

| Script | What it measured | Status |
|---|---|---|
| `phase7_always_advance.py` | open-loop floor, A1 | superseded by `phase7j_floor_dt001.py` |
| `phase7a_always_advance_a2a3.py` | open-loop floor, A2 and A3 | superseded by `phase7j_floor_dt001.py` |
| `phase7c_speed_sweep.py` | advance-speed sensitivity | **withdrawn, not re-run.** No speed-dependence claim is made anywhere |
| `phase7c_shard.py`, `phase7c_pool_default.py` | sharding and pooling for the sweep | withdrawn with it |
| `phase7d_oracle.py` | constant-rotation reachability probe | **withdrawn.** Its purposes — a ceiling and per-seed reachability — are established by an open-loop policy that succeeds on every seed |
| `phase7e_solver_replay.py` | solver non-convergence, replay fidelity | withdrawn; no convergence percentage appears in the manuscript |
| `phase7g_nondeterminism_floor.py` | environment run-to-run reproducibility | withdrawn; the seed claim rests on the arms' own within-pair correlation |
| `phase7h_dispersion.py` | dispersion test over 7g's repetitions | withdrawn with 7g |

## Superseded artifacts

`results/baselines/always_advance_a{1,2,3}_{summary.json,trace.jsonl}`,
`results/baselines/phase7c_speed_sweep.json`, `phase7c_shards/`, `phase7d_oracle.json`,
`phase7d_shards/`, `phase7e_replay_*.json`, `phase7g_report.txt`,
`results/phase7c_*.csv`, `phase7d_*.csv`, `phase7e_*.csv`, `phase7h_dispersion.csv`.

Of these, only the three `always_advance_*_summary.json` files record their own `dt_simulation`.
For the rest the timestep is recoverable only by reading the source — which is why
`phase7j_floor_dt001.py` writes `dt_simulation` into its output, and why this file exists.

## Manifest keys

105 keys are marked `[SUPERSEDED` in their `description` field in `results/manifest.csv`. They are
marked rather than deleted because their values are the record. The build refuses to render any
source that references one.

## Also superseded, for unrelated reasons

- **A3 (ASOCA Normal_5)** is excluded on physical-validity grounds (C8, C11) and supports no
  inference. Its lumen surface is wholly generated — every branch a constant-radius 2.5 mm tube —
  so it is not an anatomy. It produced the strongest raw effect of the three, which is stated
  precisely so the exclusion cannot read as outcome-driven.
- **The A2 "unequal step budgets" claim** (45 vs 62 steps) is withdrawn (C20). No artifact records
  the step limit, nothing was truncated, and those two numbers are simply the longest episode in
  each arm. Both A2 arms ran under a common limit.
- **`benchmarks/protocol.json`** still lists A2 `step_budget: 45` and an A3 entry. It describes
  itself as frozen and is the protocol the public benchmark runner executes, not a statement about
  the paper's analysis. Treat `CORRECTIONS.md` and the manuscript as authoritative where they
  differ.
