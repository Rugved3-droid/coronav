# CoroNav Results

This page has three parts that must not be mixed up:

1. **Final manuscript results**: the findings of *Vessel overlay slows
   vision-language-model guidewire navigation in simulated coronary
   anatomies*. Only these are manuscript claims.
2. **Excluded geometry (A3)**: kept for the record. It supports no claim.
3. **Archived, superseded analyses**: what this page reported before the
   final revision. They are kept, labelled, and explained, and they are not
   manuscript findings.

> **Provenance, read first.** Every number in Part 1 is transcribed from the
> final manuscript. The original episode traces, analysis scripts, the
> number-to-artifact manifest and `CORRECTIONS.md` that produced them are
> **not in this repository** (see
> [`docs/MANUSCRIPT_CONCORDANCE.md`](docs/MANUSCRIPT_CONCORDANCE.md)). So
> none of these numbers can currently be regenerated or checked from this
> repository. Nothing on this page comes from running the code in this
> repository, except where it says so explicitly.

---

## Part 1 — Final manuscript results

### Design in brief

- **Question:** does rendering the vessel lumen into simulated fluoroscopy
  (`overlay`) help one VLM operator, compared with showing the wire only
  (`wire_only`)?
- **Operator:** Claude Sonnet 4.6 (`claude-sonnet-4-6`), Anthropic Python SDK
  v0.72.0. Calls are stateless, and decoding is stochastic and unseeded.
- **Anatomies (retained):** A1 = VMR 0066, A2 = ASOCA Normal_12. A third
  geometry, A3 = ASOCA Normal_5, was excluded (Part 2).
- **Episodes:** 25 seed-matched episodes per arm. Seeds fix the simulator
  reset only, so they align episode labels and do not reproduce trajectories.
- **Step limit:** 60 in both A1 arms and 120 in both A2 arms.
- **Simulation timestep:** 0.001 s for every retained arm and result.
- **Primary endpoint:** navigation efficiency (steps to target; success means
  the tip is within 5 mm of the target within the step limit), analysed over
  all episodes without conditioning on success.
- **Secondary (mechanistic) endpoint:** `f_rot_LM`, the left-main-phase
  rotation-movement fraction. It is dimensionless, in [0, 1], and computed
  by `coronav.metrics.lm_metrics()` under the code name `lm_rot_mm`. The
  endpoint hierarchy was revised after corrected results were known, which
  the manuscript discloses as a post hoc decision. The analysis plan is
  retrospective with respect to data collection.

### Open-loop control: the task is solvable without visual information

The open-loop policy advances at 35 mm/s every step. It never rotates or
retracts and receives no image and no state. It ran over the same seeds and
step limits as the operator arms, 3 times per anatomy, at 0.001 s.

| | A1 | A2 |
|---|---|---|
| Reached target | 75/75 (100.0%; Wilson 95% CI 95.1–100.0) | 75/75 (100.0%; Wilson 95% CI 95.1–100.0) |
| Steps to target | 26 (every episode) | 11 (every episode) |
| Final distance to target | 4.58–4.71 mm | 1.76–1.91 mm |

No hypothesis test is run between the open-loop policy and an operator arm,
because they differ in commanded speed as well as in access to the image.

### Primary endpoint: navigation (overlay slows the operator)

| | A1 (step limit 60) | A2 (step limit 120) |
|---|---|---|
| Reached target, wire_only | 20/25 | 25/25 |
| Reached target, overlay | 13/25 | 25/25 |
| Success-rate comparison | Fisher p = 0.0718; **no success-rate claim** | — (all succeeded) |
| Steps, wire_only vs overlay | — | median 41 vs 56; range 37–45 vs 50–62; overlay slower on all 25 seeds |
| Analysis | worst-rank Wilcoxon W = 47.5, **p = 0.00206**, rank-biserial +0.708 | paired Wilcoxon, Hodges–Lehmann **+14.5 steps (95% CI +13.0 to +16.5), p = 1.25e-05** |
| | win ratio **5.60 (95% CI 2.43–17.97)**; 470 wins, 84 losses, 71 ties | No A2 episode was truncated, so no step count is censored |
| | log-rank χ² = 11.705, **p = 0.000623** (failures censored at the step limit) | |

### Secondary endpoint: left-main rotation (`f_rot_LM`)

Confirmatory family: {A1, A2}, Holm-corrected. The paired Wilcoxon test is
primary, and the unpaired Mann–Whitney test is a sensitivity analysis.

| | A1 | A2 |
|---|---|---|
| Median `f_rot_LM`, wire_only vs overlay | 0.1452 vs 0.1749 (higher on 20 of 25 seeds) | 0.0000 vs 0.0454 |
| Paired Wilcoxon | W = 73.0, **p = 0.0147**, Holm **0.0147**; matched-pairs rank-biserial +0.551 | 16 informative pairs, W = 0.0, **p = 0.000482**, Holm **0.000965** |
| Unpaired sensitivity | U = 496.0, p = 0.000384 | p = 2.95e-06 |
| Hodges–Lehmann shift | +0.0285 (95% CI +0.0068 to +0.0440); effect detected, magnitude poorly constrained | not applicable: presence-versus-absence, not compared in magnitude with A1 |
| Left-main rotate intents, wire_only vs overlay | — | 0 (across 25 episodes) vs 37 (across 16 episodes) |

### Pairing, robustness and exploratory analyses (as reported)

- The within-pair correlation on A1 is −0.072 (95% CI −0.455 to +0.332) for
  `f_rot_LM` and −0.074 (−0.456 to +0.330) for the worst-rank endpoint. On A2
  it is undefined because the wire-only arm is constant. The paired test is
  retained as the more conservative choice.
- Transmission failures among retained episodes differed between arms in A1
  (1.33% of wire-only calls vs 0.00% of overlay calls; p = 2.4e-06) but not
  in A2 (p = 0.268). In A1 they all fell in one failed episode on the faster
  arm. Discounting the affected steps left the worst-rank test and the win
  ratio unchanged and strengthened the log-rank result (p = 0.000157).
- Episodes with zero valid operator actions are excluded as non-attempts,
  which removes no retained episode. A sensitivity analysis that excludes
  episodes with more than 50% failed calls changes nothing in the
  confirmatory family.
- A biplane second view (LAO 60°, cranial 20°), tested in a separate
  exploratory study on A1, did not change left-main rotation (p = 0.375).
  Its arms did not share a common effective step limit, and 2 biplane
  episodes ended at 20 and 30 steps for reasons the retained logs do not
  record.
- Prompt-variant and contrast arms were also collected. They are
  exploratory, unadjusted, and reported in the manuscript's Supplementary
  Material, which is not in this repository. No main-text claim rests on
  them.

### Limitations (from the manuscript)

- One VLM was tested, in simulation only, with rigid walls and one instrument
  model. There is no bench or clinical validation, and nothing generalises
  across models.
- Two anatomies, 25 episodes per arm, and one run of each operator arm.
- Unseeded decoding means pairing is weak (see the correlation above).
- Each arm was collected as one contiguous block, so condition and collection
  epoch are confounded.
- The analysis plan is retrospective, and the endpoint hierarchy was revised
  post hoc.
- A third geometry was excluded on physical-validity grounds even though it
  gave the strongest raw result.
- The open-loop control differs from the operator in commanded speed as well
  as in image access.
- Rotation-endpoint sensitivity is stated by its interval rather than by a
  power calculation.

---

## Part 2 — Excluded geometry: A3 (ASOCA Normal_5)

A3 was attempted and is **excluded**. The manuscript (§2.2) gives three
reasons, stated together:

1. **It is not an anatomy.** The mesh pipeline replaces the lumen surface
   wholesale. Every branch is a constant-radius 2.5 mm tube along the patient
   centerline, so no part of the vessel wall is patient surface (see
   `scripts/download_asoca.py`, `_generate_a3_tube`).
2. **Its physics was not resolved.** The contact solver failed to converge
   on the large majority of replayed steps, against a small minority on the
   retained anatomies. That comparison came from a replay at the superseded
   0.006 s timestep, so no percentage is quoted. The qualitative contrast is
   what the exclusion rests on.
3. **The exclusion is not outcome-driven.** A3 produced the strongest raw
   rotation result of the three (paired p = 3.34e-06, unadjusted and outside
   any inference family). It is excluded on physical validity, not on its
   result.

**A3 supports no manuscript claim.** Earlier versions of this page used A3 as
"cross-anatomy replication" evidence (archived below). That use is withdrawn.

---

## Part 3 — Archived, superseded analyses (not manuscript findings)

Everything below was published on this page before the final revision. The
original wording and numbers are kept so the record is complete. They are
**superseded** by Part 1 and must not be cited as the study's findings. Like
Part 1, they come from the original research runs and cannot be regenerated
from this repository.

### 3.1 Earlier "primary result": `lm_rot_mm` by Mann–Whitney U, three anatomies

| Anatomy | Condition | Median lm_rot_mm | n | Mann-Whitney U p | Effect direction |
|---------|-----------|-----------------|---|-----------------|-----------------|
| A1 (VMR0066) | wire_only | 0.1452 | 25 | — | — |
| A1 (VMR0066) | overlay | 0.1749 | 25 | p = 0.0004 | overlay > wire_only |
| A2 (ASOCA N12) | wire_only | — | 25 | — | — |
| A2 (ASOCA N12) | overlay | — | 25 | p = 0.000003 | overlay > wire_only |
| A3 (ASOCA N5) | wire_only | — | 25 | — | — |
| A3 (ASOCA N5) | overlay | — | 25 | p = 0.000009 | overlay > wire_only |

Original text: *"All three anatomies show significant overlay > wire_only
effect (all p < 0.001). Cross-anatomy replication is the primary robustness
evidence. A1 effect size: r = 0.587."*

How this relates to the final manuscript:

- **Endpoint role.** `lm_rot_mm` is the same quantity as `f_rot_LM`
  (Part 1). It is now the *secondary* endpoint, tested by paired Wilcoxon
  with Holm correction. The unpaired Mann–Whitney test is only a sensitivity
  analysis.
- **A1 / A2 p-values.** The archived A1 value of 0.0004 and A2 value of
  0.000003 agree, after rounding, with the manuscript's unpaired sensitivity
  values of 0.000384 and 2.95e-06. They are not the confirmatory values (A1
  paired p = 0.0147; A2 paired p = 0.000482).
- **A3.** Excluded (Part 2). The archived A3 value (Mann–Whitney p =
  0.000009) is not the manuscript's A3 figure (paired p = 3.34e-06). Neither
  supports any claim.
- **"All three anatomies" / "cross-anatomy replication".** Withdrawn. Only A1
  and A2 are retained.
- **r = 0.587.** This was an unpaired effect size from the earlier analysis.
  The manuscript reports a matched-pairs rank-biserial of +0.551 for A1.
- **Interpretation.** The archived text read higher rotation as *"consistent
  with the model using the visible vessel wall to guide directional
  choices"*. The manuscript says only that the results are *consistent with*
  the overlay drawing the operator into exploratory steering, and that the
  mechanism is not established.

### 3.2 Prompt ablation (A1, n = 10 per variant): exploratory

| Variant | Description | n per arm | wire_only median | overlay median | Δ | p (two-sided) | Archived interpretation |
|---------|-------------|-----------|-----------------|----------------|---|--------------|---------------|
| V1 | Full scaffold (DEFAULT_SYSTEM_PROMPT) | 25 | 0.1452 | 0.1749 | +0.0297 | 0.0004 | significant |
| V2 | No spatial scaffold | 10 | 0.0000 | 0.0000 | — | 0.1681 | uninformative (both arms ~zero rotation) |
| V3 | Compressed / minimal | 10 | 0.0970 | 0.0428 | −0.0542 | 0.1375 | excluded (navigation collapsed, 0/10 success in both arms) |
| V4 | Rephrased scaffold | 10 | 0.1398 | 0.1476 | +0.0078 | 0.2413 | same direction, n.s. |

The manuscript treats prompt-variant arms as exploratory and unadjusted, and
reports them in the Supplementary Material. That file is not in this
repository, so these figures **have not been checked** against the final
Supplementary Material. The V1 row repeats the archived unpaired A1 test
(§3.1).

### 3.3 Earlier success-conditioned navigation analysis (A1)

Labelled in an earlier version as "Table I of the paper", from a previous
submission:

| Metric | wire_only | overlay | Test (two-sided) |
|--------|-----------|---------|-------------------|
| Episodes reaching mid-LAD (success) | 20 / 25 (80%) | 13 / 25 (52%) | Fisher p = 0.072 (n.s.) |
| Median steps to target (successes only) | 48.0 | 58.0 | U = 24, p = 0.0001, r = 0.812 |
| Steps to target, seed-matched (n=9 both succeeded) | — | — | Wilcoxon W = 3, p = 0.020 |
| First-bifurcation LCx (wrong branch) | 8 / 25 | 9 / 25 | Fisher p = 1.000 (n.s.) |

Superseded. These analyses **condition on success**, and success is itself an
outcome of the condition. The manuscript's primary analysis uses all 50 A1
episodes instead (worst-rank, win ratio, log-rank; Part 1). The archived page
called the success-conditioned steps comparison "pre-specified". The
manuscript describes its analysis plan as retrospective with respect to data
collection, so that word is withdrawn. The success counts (20/25, 13/25) and
the Fisher test (0.072 → 0.0718) agree with the manuscript. The
branch-selection null result is not reported in the manuscript.

### 3.4 Withdrawn 0.006 s open-loop baselines

The open-loop baselines were first run at a simulation timestep of 0.006 s,
coarser than the operator arms' 0.001 s. At that timestep the open-loop
policy appeared to solve roughly half to two-thirds of episodes, which led to
the conclusion that success rate was a weak but informative discriminator.
Re-measured at 0.001 s, it solves every episode. **The 0.006 s figures and
that conclusion are withdrawn** (manuscript §2.1 and §4; `CORRECTIONS.md`
C21–C22, which is not in this repository). A speed-sensitivity check run at
0.006 s is likewise not carried forward.

### 3.5 Container smoke-run (n = 9): not a reproduction, superseded physics

An earlier README reported a partial run of this repository's Docker
container: A1, `wire_only`, seeds 5001–5100 (one seed lost to an exhausted
API key), median `lm_rot_mm` 0.1911, and 6/9 reached target. At that time
this repository hard-coded a **0.006 s** timestep (`coronav/env.py`), so the
run presumably used the superseded timestep. Its traces are not in the
repository, so this cannot be confirmed. It is not comparable with any
manuscript result and is kept only as a record.

---

## Running your own operator

This repository runs the same harness design (seeds, step limits, timestep,
observation conditions, metric code). **Nothing here has been shown to
reproduce Part 1 at full scale.** Treat any numbers you obtain as your own new
run.

```bash
# Image-free control (no API calls)
python benchmarks/run_benchmark.py --operator open_loop --anatomy a1
# Both observation conditions (paid API calls)
python benchmarks/run_benchmark.py --operator claude --anatomy a1 --mode wire_only overlay
# Descriptive summary of a run
python benchmarks/report.py --run-dir runs/<timestamp>/
```

`benchmarks/report.py` gives descriptive statistics and an unpaired
sensitivity test only. It does not implement the manuscript's confirmatory
analyses.

### Sharing results from a new operator

Open a PR or issue with:

- [ ] `trace.jsonl` and `run_meta.json` for each anatomy × condition (or a link to a public deposit)
- [ ] `scripts/check_install.py` output
- [ ] Operator description (model, API/SDK version, decoding settings, prompt changes)
- [ ] Whether you used `DEFAULT_SYSTEM_PROMPT` unchanged
