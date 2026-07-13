# CoroNav Evaluation Protocol (v1.0 — frozen)

This document defines the frozen evaluation protocol for CoroNav.
**Do not modify seeds, step budgets, or metric definitions** — changes break
comparability with the paper baseline numbers in `RESULTS.md`.

## Anatomies

| Key | Name | Source | Episodes | Step budget |
|-----|------|--------|----------|-------------|
| A1  | VMR0066 | Vascular Model Repository (bundled) | 25 | 60 |
| A2  | ASOCA Normal_12 | ASOCA challenge (registration required) | 25 | 45 |
| A3  | ASOCA Normal_5 (synthetic tube) | ASOCA challenge (registration required) | 25 | 150 |

See `benchmarks/protocol.json` for the exact seeds.

> A2's step budget (45) is the `wire_only` budget — the only mode this
> protocol and `run_benchmark.py` execute. The paper's overlay-condition runs
> on A2 used a different budget (62 steps); that arm isn't reproduced by this
> repo's benchmark runner.

### A3 note

The patient lumen in ASOCA Normal_5 is below the guidewire diameter.
A synthetic tube (radius = 2.5 mm) was generated from the patient centerlines
and used as the vessel wall.  This is NOT the patient surface; it is documented
in the paper (Section 3.1) and in `data/anatomy/a3_asoca_n5/README.md`.

## Imaging

| Parameter | Value |
|-----------|-------|
| Mode | `wire_only` (guidewire visible, no vessel overlay) |
| Projection | AP Cranial 40 deg (image_rot_zx = [0, -40]) |
| Image size | 512 × 512 px, uint8 grayscale |
| Wire diameter | 0.89 mm |
| Frame rate | 7.5 Hz (simulated) |

## Simulation

| Parameter | Value |
|-----------|-------|
| SOFA version | 23.06.00 |
| Timestep | 0.006 s |
| Contact distance | 0.3 mm |
| Alarm distance | 0.5 mm |
| LCP max iterations | 2000 |
| LCP tolerance | 1e-4 |
| Friction | 0.001 |
| Wire diameter | 0.89 mm |

## Primary metric: `lm_rot_mm`

**Definition:**

```
lm_rot_mm = sum(|dist_change| on rotation steps during LM phase)
            / sum(|dist_change| on ALL steps during LM phase)
```

- The LM (left main) phase is identified by `tip_branch_obs == "left_main"`.
- A step is a rotation step if `intended_direction` is `rotate_cw` or `rotate_ccw`.
- `dist_change` = |`tip_target_dist_after` - `tip_target_dist`| for each step.
- Only rows with `api_ok=True` AND `parse_ok=True` are included.
- Episodes where **all** rows fail API/parse are excluded from aggregate statistics.

**Rationale:**
Lower `lm_rot_mm` means the model uses fewer rotation actions (relative to
total wire movement) while traversing the LM trunk — indicating more decisive
advance toward the bifurcation.  The metric is dimensionless [0, 1].

**Summary statistic:** Median per-episode value; two-sided Mann-Whitney U test
(pre-specified because the per-episode distribution is right-skewed, skew = 3.22
in the wire_only condition).

## Secondary metrics

| Metric | Definition | Test |
|--------|-----------|------|
| `success_rate` | Fraction of episodes reaching mid-LAD target within budget | Fisher two-sided |
| `steps_to_target` | Step count for successful episodes only | Seed-matched Wilcoxon signed-rank |
| `wrong_branch_rate` | Fraction of advance steps where tip is in LCx | — |

## Prompt variants (ablation)

| Variant | System prompt | n per arm |
|---------|---------------|-----------|
| V1 | Full scaffold (default, `DEFAULT_SYSTEM_PROMPT` in `coronav/prompts.py`) | 25 |
| V2 | No spatial scaffold | 10 |
| V3 | Compressed / minimal | 10 |
| V4 | Rephrased scaffold | 10 |

V2, V3, V4 use n=10 per arm; this is **underpowered** relative to V1 (n=25 gives
80% power at α=0.05, r=0.587).  See `RESULTS.md` for per-variant outcomes.

## Reproducibility checklist

Before reporting a result as comparable to the paper baseline:

- [ ] Use the exact seeds in `benchmarks/protocol.json`
- [ ] Step budget matches the anatomy (A1=60, A2=62, A3=150)
- [ ] Mode = `wire_only`
- [ ] `image_rot_zx = [0, -40]`
- [ ] SOFA version 23.06.00 (+ BeamAdapter, IncrSAP fix, tip-DOF fix)
- [ ] Primary metric computed by `coronav.metrics.lm_metrics()` — do not recompute from scratch
- [ ] Report median + IQR + Mann-Whitney U (two-sided)
