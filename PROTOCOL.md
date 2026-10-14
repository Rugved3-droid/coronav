# CoroNav Evaluation Protocol (v2.0)

This protocol describes the experimental design of the final manuscript. The
machine-readable copy is `benchmarks/protocol.json`, which the runner reads.
Changing seeds, step limits, timestep or metric code makes new runs
non-comparable with the manuscript's design. It does not change any reported
result.

v1.0 of this file (originally released with this repository) differed in
several places. Its values are kept under [Change history](#change-history)
and in `protocol.json` → `superseded_v1`.

## Purpose

CoroNav is an **instrument for studying how image-based operators use visual
information**. It is not a validated navigation-difficulty benchmark. As
configured, the task is solvable without any visual information (an open-loop
policy reaches target in every episode), so a lower score for an operator
says something about how that operator uses the image, not about task
difficulty.

## Anatomies

| Key | Name | Source | Status | Episodes/arm | Step limit (both arms) |
|-----|------|--------|--------|--------------|------------------------|
| A1 | VMR 0066 | Vascular Model Repository (bundled) | **retained** | 25 | 60 |
| A2 | ASOCA Normal_12 | ASOCA challenge (registration required, not bundled) | **retained** | 25 | 120 |
| A3 | ASOCA Normal_5 | ASOCA challenge | **excluded** | — | (150 in archived runs) |

Seeds are listed in `benchmarks/protocol.json`. They fix the simulator reset
only. Operator decoding is stochastic and unseeded, so matched seeds align
episode labels and do not reproduce trajectories.

**A3 is excluded** on physical validity: its surface is a constant-radius
2.5 mm tube generated along the patient centerline, so no part of it is
patient lumen, and the contact solver did not converge adequately on it. It
supports no claim. `run_benchmark.py` refuses to run it without
`--allow-excluded`.

## Observation conditions

| Parameter | Value |
|-----------|-------|
| Conditions compared | `wire_only` (instrument on a noise background) vs `overlay` (pixel raster of the lumen, drawn beneath the wire) |
| Exploratory only | `contrast`; biplane (LAO 60° / cranial 20°) is not implemented in this repository's runner |
| Projection | AP cranial 40° (`image_rot_zx = [0, -40]`) |
| Image | 512 × 512 px, uint8 grayscale |
| Wire diameter (render) | 0.89 mm |
| Frame rate | 7.5 Hz simulated (one operator step = 1/7.5 s of simulation) |

Both conditions share identical physics. Within an anatomy, the observation is
the only manipulated variable.

## Simulation

| Parameter | Value |
|-----------|-------|
| SOFA | v23.06.00 + BeamAdapter v23.06 (via stEVE) |
| **Timestep** | **0.001 s** |
| Sub-steps per operator step | `int((1/7.5) / 0.001)` = 133 |
| Instrument | J-tip guidewire, tip radius 1.5 mm, tip angle 0.2π |
| Collision | local minimum distance; contact 0.3 mm, alarm 0.5 mm |
| Constraint solver | Gauss–Seidel LCP, max 2000 iterations, tolerance 1e-4 |
| Friction | 0.001 |
| Target | mid-LAD centerline point; reached when the tip is within 5 mm |

### Simulation timestep

Every retained operator arm and every quantitative result supporting the
manuscript ran at **0.001 s**. Per-sub-step insertion is the commanded speed
multiplied by the timestep, so a coarser timestep moves the wire further
between contact resolutions. Open-loop baselines first run at 0.006 s gave
materially different results and are **withdrawn**. Do not compare 0.006 s
runs with the manuscript.

## Operator harness

| Parameter | Value |
|-----------|-------|
| Reference operator | `claude-sonnet-4-6` via Anthropic Python SDK v0.72.0, stateless calls |
| Per-step input | one image + one-line state string (distance to target, distance trend, retractions remaining, no-progress counter) |
| Output | JSON with `intended_direction` and `action` {translation mm/s, rotation rad/s} |
| Proximity gate | within 25 mm of target and closing, a rotate intent is replaced by an advance of 35 mm/s |
| Retraction budget | 2 per episode |
| Failed API call | not retried or skipped; a null action is executed and consumes the step |

## Open-loop control

Advances at 35 mm/s every step and never rotates or retracts. It receives no
image and no state. It is run over the same seeds and step limits, 3 times
per anatomy, at 0.001 s. It establishes that the task is solvable without
vision. No hypothesis test is run between it and an operator arm.
`--operator open_loop` in this repository re-implements this policy. It is
not the original script.

## Endpoints

### Primary: navigation efficiency

Steps to target, where success means the tip is within 5 mm of the target
within the step limit. Because success is itself an outcome of the condition,
steps are analysed over **all episodes without conditioning on success**:

- **A1:** worst-rank imputation (every failure ranked below every success)
  with a Wilcoxon signed-rank test; Finkelstein–Schoenfeld win ratio with a
  bootstrap CI; log-rank test with failures censored at the step limit.
- **A2** (every episode succeeded): paired Wilcoxon signed-rank with a
  Hodges–Lehmann estimate.

### Secondary (mechanistic): `f_rot_LM`

Code name `lm_rot_mm` (`coronav.metrics.lm_metrics`). The "mm" is historical:
the quantity is a **dimensionless fraction**.

```
f_rot_LM = Σ |d_after − d_before|  over LM-phase steps with a rotate intent
           ───────────────────────────────────────────────────────────────
           Σ |d_after − d_before|  over all LM-phase steps
```

- `d` is the 3-D tip-to-target distance (`tip_target_dist`,
  `tip_target_dist_after`).
- **LM phase:** steps whose *post-step* tip position is nearest the
  `left_main` centerline segment (`tip_branch_obs == "left_main"`).
- **Rotate intent:** `intended_direction` ∈ {`rotate_cw`, `rotate_ccw`}, the
  operator's stated intent after the proximity-gate override.
- Only rows with `api_ok` and `parse_ok` count.
- Numerator and denominator are sums over the same phase, so units and
  episode length cancel. The result is bounded in [0, 1].
- An episode with no valid left-main-phase movement has no defined value.

Left-main-phase rotate-intent counts (`lm_rot_steps`) are also recorded.

Analysis: the confirmatory family is {A1, A2} with Holm correction. The
paired Wilcoxon test is primary, and the unpaired Mann–Whitney U is a
sensitivity analysis.

The endpoint hierarchy was revised after corrected results were known, which
is disclosed as a post hoc decision. The analysis plan is retrospective with
respect to data collection.

### Statistical conventions

Two-sided tests at α = 0.05. Exact tests are used where zeros and ties allow,
otherwise the normal approximation with continuity correction. Resampling
uses a fixed seed and 10 000 replicates. Rates carry Wilson intervals.

## Exclusions

Episodes with **zero valid operator actions** are excluded as non-attempts.
Partial-failure episodes are included. A sensitivity analysis additionally
excludes episodes with more than 50% failed calls.

## What this repository implements

| Item | Status |
|------|--------|
| Environment, both observation conditions, timestep, step limits | `coronav/env.py`, `benchmarks/run_benchmark.py --mode` |
| Reference operator, prompt, harness rules | `coronav/operator/claude.py`, `coronav/prompts.py`, `coronav/env.py` |
| Open-loop control | `--operator open_loop` (re-implementation) |
| `f_rot_LM` | `coronav.metrics.lm_metrics` |
| Navigation outcome over all episodes | `coronav.metrics.episode_outcome` |
| Confirmatory statistics (worst-rank, win ratio, log-rank, HL, paired Wilcoxon + Holm) | **not in this repository**: the original analysis scripts are missing |

## Reporting checklist for a new run

- [ ] Seeds and step limits from `benchmarks/protocol.json`
- [ ] Timestep 0.001 s (recorded in each trace row and in `run_meta.json`)
- [ ] Both `wire_only` and `overlay` arms, same step limit within an anatomy
- [ ] `image_rot_zx = [0, -40]`
- [ ] SOFA 23.06.00 + BeamAdapter (with the IncrSAP and tip-DOF fixes in `coronav/sim/coronary_sim.py`)
- [ ] `f_rot_LM` computed by `coronav.metrics.lm_metrics()`, navigation by `episode_outcome()`
- [ ] State that the run is new, and report operator decoding settings

## Change history

| Item | v1.0 (initial release) | v2.0 (final manuscript) |
|------|------------------------|-------------------------|
| Purpose | "open benchmark" | instrument for studying VLM visual behaviour, not a benchmark |
| Timestep | 0.006 s (also hard-coded in `coronav/env.py`) | 0.001 s |
| A2 step limit | 45 (wire_only); overlay "used a different budget (62 steps)" | 120 in both arms |
| A3 | active anatomy, step budget 150 | excluded |
| Modes run by the runner | `wire_only` only | `wire_only` and `overlay` |
| Primary endpoint | `lm_rot_mm`, median, two-sided Mann–Whitney U ("pre-specified") | navigation efficiency over all episodes |
| `lm_rot_mm` / `f_rot_LM` | primary | secondary; paired Wilcoxon + Holm, MWU as sensitivity |
| Steps to target | successful episodes only, seed-matched Wilcoxon | all episodes, no conditioning on success |
| Prompt variants V2–V4 | ablation (n=10) | exploratory, reported in the Supplementary Material |

**Unresolved:** v1.0 recorded A2 budgets of 45 (wire_only) and 62 (overlay).
The manuscript states 120 for both arms, and reports A2 step ranges of 37–45
and 50–62, whose maxima equal exactly those v1.0 budgets. The repository
cannot tell whether the A2 arms ran under 45/62 or 120. Only the original A2
run configuration and traces can resolve this. See
`docs/MANUSCRIPT_CONCORDANCE.md`, issue U3.
