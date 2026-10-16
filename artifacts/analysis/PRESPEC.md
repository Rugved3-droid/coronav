# PRESPEC.md — Pre-specified analysis plan

**Study:** CoroNav — VLM-guided coronary guidewire navigation
**Target journal:** International Journal of Computer Assisted Radiology and Surgery (resubmission after IEEE T-MRB rejection). *Changed 2026-09-15 from Computers in Biology and Medicine by author decision; see §9.*
**Branch:** `revision-cbm`
**Frozen:** 2026-09-11, committed before any Phase 3+ analysis was executed.

> ## PARTLY SUPERSEDED — retained as evidence, not as a current plan
>
> **Read this before citing anything below.** This file is the frozen pre-specification and is
> **not edited**: its value is that it records what was committed to *before* the analyses ran.
> Several pre-commitments have since been retired by corrections, and the entries remain below
> unaltered so the record of what was planned survives.
>
> - **The advance-speed sweep (Phase 7c) and the oracle reachability probe (Phase 7d) are
>   withdrawn (C22).** Both ran at a simulation timestep of 0.006 s, which no study arm used.
>   Re-measured at the arms' own 0.001 s, the open-loop policy reaches target in 75/75 episodes on
>   both anatomies, so the probe's two purposes — a ceiling and per-seed reachability — are
>   established by the open-loop control itself. **No speed-dependence claim is made anywhere.**
> - **The environment non-determinism measurement (Phase 7g) and the dispersion analysis
>   (Phase 7h) are withdrawn (C22)**, for the same reason. The seed-propagation claim now rests on
>   the operator arms' own within-pair correlation, measured at 0.001 s.
> - **The three-anatomy framing is withdrawn (C8, C11).** A3 is excluded on physical-validity
>   grounds and supports no inference.
> - **The A2 unequal-budget claim is withdrawn (C20).** Both arms ran under a common step limit.
> - **The target journal above is out of date.** The current target is Computer Methods and
>   Programs in Biomedicine.
>
> What survives unchanged: the exclusion rule, the confirmatory family and Holm correction, the
> endpoint definitions, and the honest statement on timing immediately below — which remains the
> most important thing on this page. See `analysis/SUPERSEDED.md` and `CORRECTIONS.md`.

---

## 0. Honest statement on timing

**This pre-specification is retrospective relative to data collection.** All episodes were
collected 2026-06-14 to 2026-07-07 for the IEEE T-MRB submission, and the original analyses
were already run and reported in that manuscript. This document was written 2026-09-11,
before any of the revision analyses (Phases 3–13) were executed.

It was written *after* a Phase 0 inventory that examined: file layout, schema and field
semantics, episode counts, exclusion counts and reasons, per-arm success counts, and whether
final distance-to-target is recorded. **Phase 0 computed no endpoint value** — no
`lm_rot_mm`, no test statistic, no p-value was calculated before this plan was frozen.

The manuscript will state this in the same terms. We do not claim prospective registration.

### Relationship to the earlier pre-registration

An earlier plan exists: `D:\steve\pilot\PREREGISTRATION.txt` (locked 2026-07-01, before ASOCA
data collection). Its primary prediction was a **dissociation**: overlay-induced excess rotation
present in A1 (LM-bend illusion present) and *attenuated or absent* in A2/A3 (illusion absent).

**That prediction was disconfirmed.** The effect appeared significantly in all three anatomies.
The present plan supersedes it. The manuscript will report the prior prediction and its failure
rather than silently replacing it.

---

## 1. Data provenance (read-only)

Raw logs live outside this repository and are **never modified**:

| Arm | Path (under `D:\steve\pilot\runs\`) | n eps | analysed |
|---|---|---|---|
| A1 wire_only | `ablation_prompt_robustness\v1_current\wire_only\trace.jsonl` | 25 | 25 |
| A1 overlay | `ablation_prompt_robustness\v1_current\overlay\trace.jsonl` | 25 | 25 |
| A2 wire_only | `normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl` | 25 | 25 |
| A2 overlay | `normal12_overlay\arm_asoca_normal12_overlay\trace.jsonl` | 25 | 25 |
| A3 wire_only | `normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl` | 25 | 25 |
| A3 overlay | `normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl` | 25 | **23** |

Exploratory arms: prompt variants V2/V3/V4 (`ablation_prompt_robustness\v{2,3,4}_*`),
biplane and monoplane 120-step arms (`biplane_120steps\`, `mono_120steps\`), and the
contrast condition (`2026-06-28_21-00-25\arm_coronary_contrast\`).

All analysis output goes to `results/`. Raw logs are read-only inputs.

---

## 2. Metric definitions (locked)

### 2.1 Schema conventions — verified, not assumed

Two logging conventions exist. Both were verified against the data in Phase 0:

**Mono arms** (A1, A2, A3, contrast, mono120) — `run_coronary.py:661-728,791`,
`run_asoca.py:734,798-799`:
- `dist_obs_at_call[k]` = distance to target **before** step k's action
- `tip_target_dist[k]` = distance to target **after** step k's action
- `dist_delta[k] = tip_target_dist[k] − dist_obs_at_call[k]` = the movement caused by
  **step k's own action**

Verified on every row of all six canonical arms: identity holds 1277/1277, 1448/1448,
1026/1026, 1400/1400, 3438/3438, 3750/3750. The chained identity
`dist_obs_at_call[k] == tip_target_dist[k−1]` holds on every non-first row.

**Biplane arms** — `tip_target_dist[k]` is the **pre**-action distance and
`tip_target_dist_after[k]` the post-action distance; verified
`tip_target_dist_after[k] == tip_target_dist[k+1]`, 332/332.

**Consequence:** both conventions yield the same physical quantity — the magnitude of the
distance change attributable to that step's action. **No temporal realignment is applied,
because none is required.** An earlier suspicion of a one-step misalignment was checked
against the generating source and the data and found to be incorrect; it is recorded and
retracted in `results/LOG.md`.

### 2.2 LM-phase membership

LM phase = rows where `tip_branch_obs == "left_main"`.

In the paper's harness `tip_branch_obs` is classified from the **pre-action** tip position
(`run_coronary.py:663-664`, using `tip_obs`). The public benchmark's port classifies from the
**post-action** tip (`coronav/env.py:314`). We lock the **paper harness convention** for
continuity with the submitted results, and document the divergence as a reproduction
discrepancy in the limitations and in `results/manifest.csv`.

### 2.3 Primary endpoint

```
f_rot_LM = sum(|dist_delta|  over LM rows that are rotation steps)
         / sum(|dist_delta|  over ALL LM rows)
```

- Rotation step: `intended_direction in {rotate_cw, rotate_ccw}` (mono) or
  `is_rotate_step == True` (biplane).
- Only rows with `api_ok == True AND parse_ok == True` contribute.
- Episodes where **all** rows fail api/parse are excluded (pre-existing rule, unchanged).
- Dimensionless, range [0, 1].

**Naming correction.** The manuscript calls this metric "rot/mm". It is a dimensionless
ratio of distances, **not** a per-millimetre rate. The revision renames it `f_rot_LM`
("LM-phase rotation-movement fraction") and states the correction explicitly. The
quantity itself is unchanged.

### 2.4 Derived endpoints

| Endpoint | Definition |
|---|---|
| success | `terminal AND NOT truncation` (mono). Biplane traces have no `truncation` field → `terminal` alone; documented wherever biplane is reported. |
| steps-to-target | number of logged rows in a successful episode |
| final distance | last row's `tip_target_dist` — the true post-action distance at budget exhaustion |
| first-bifurcation branch | first `tip_branch_obs` after the last `left_main` row |
| step budget | not a logged field; taken from `benchmarks/protocol.json` and cross-checked against max observed step (A1 = 60; A2 wire_only = 45, overlay = 62; A3 = 150) |

---

## 3. Primary analyses (confirmatory)

**P1 — Primary endpoint.** `f_rot_LM`, anatomy A1, wire_only vs overlay.
Wilcoxon signed-rank on **25 seed-matched pairs** (seeds 5001–5265; both arms verified to
carry identical seed lists), two-sided, α = 0.05.

**P2 — Primary steps-to-target.** Worst-rank imputation over **all 50 A1 episodes**:
every failure ranks below every success; failures are ordered among themselves by final
distance-to-target at budget exhaustion (closer = better rank). Wilcoxon signed-rank on the
25 matched seed pairs, two-sided, α = 0.05.

Mann–Whitney on successes only is retained **solely** as a secondary sensitivity line, and is
reported as such — it is the selection-biased comparison Reviewer 2 objected to.

---

## 4. Confirmatory multiplicity family

Family = `f_rot_LM`, wire_only vs overlay, on **A1, A2, A3** (3 tests). **Holm** correction.

Same paired test as P1 in each anatomy, on seeds present and valid in both arms:
A1 = 25 pairs, A2 = 25 pairs, **A3 = 23 pairs** (seeds 4254 and 4265 excluded — all rows
`api_ok=False`). Mann–Whitney (the test used in the original manuscript) is reported
alongside as an unadjusted sensitivity line.

Bonferroni is also tabulated for transparency but Holm governs.

---

## 5. Exploratory (declared in advance, unadjusted)

All of the following are **exploratory**, reported with raw p-values, an `exploratory` flag,
and a blank adjusted-p column:

- Biplane vs monoplane (all endpoints)
- Prompt variants V2 / V3 / V4
- First-bifurcation branch selection
- Success rate (Fisher)
- Contrast condition
- Phase 7 scripted/random baselines
- Phase 8 anatomical difficulty metrics
- Phase 9 instrument-contrast measurements

**The causal claim that the effect "scales with anatomical difficulty" is deleted from the
paper.** Phase 8 geometry metrics are descriptive only and will not be used to support any
causal or ordering claim.

---

## 6. Statistical conventions (apply everywhere)

- **Global RNG seed: `20260911`**, set explicitly in every script that resamples.
- Bootstrap: **10,000 resamples**, percentile CIs.
- Wilcoxon signed-rank: **exact** method when zeros and ties permit, otherwise normal
  approximation with continuity correction. Which was used is reported for every test.
- Paired effect size: **matched-pairs rank-biserial correlation**, plus the
  **Hodges–Lehmann** estimate (median of Walsh averages) of the paired difference with a
  distribution-free CI.
- p-values to **three significant figures**; small p in scientific notation, **never
  rounded to zero**.
- Every test reports: test name, statistic, n, exact-or-approximate, two-sided p, effect
  size, CI.
- Survival analysis uses **statsmodels** (`SurvfuncRight`, `survdiff`); lifelines is not
  installed and is not a dependency.

---

## 7. What seed-matching does and does not control

Seed-matching fixes the **simulator RNG only** — the seed passed to `env.reset()`.

> **CORRECTED 2026-09-13.** This section previously read: "Seed-matching fixes the simulator
> RNG only: episode reset, insertion state, **and the physics trajectory for a given action
> sequence**." The final clause is **false**, and Phase 7a demonstrated it directly.
>
> The always-advance baseline starts every episode from an identical tip position — one
> distinct step-1 tip across all 25 episodes, to six decimal places — and issues the same fixed
> action (35 mm/s, rotation 0) at every step. Yet on **all three** anatomies every
> non-reference episode diverges from episode 1 **at step 1**, and the episodes separate into
> distinct outcome groups (A1: 17 success / 5 at ~136 mm / 3 at ~298 mm; A2: 20 / 5; A3: 13
> distinct termini). Identical start plus identical actions does **not** produce an identical
> trajectory.
>
> The physics is therefore non-deterministic across seeds, consistent with the non-converged
> Gauss–Seidel LCP solver measured in the same run (non-convergence on 9.2% of A2 steps and
> **97.2% of A3 steps**, with A3 residuals reaching 1.44).
>
> What seed-matching actually fixes is the reset draw and the insertion state. It does **not**
> fix the trajectory. Whether this also perturbs the VLM arms is **not yet established** —
> there the actions differ between episodes anyway, so model stochasticity and simulator
> non-determinism are entangled and cannot be separated from the existing logs. That is Phase
> 7e's question.

**It does not control the model's sampling.** The operator is a hosted VLM whose decoding is
stochastic and exposes no seed. Two episodes with the same simulator seed can diverge purely
because the model sampled a different action. **API stochasticity is uncontrolled and
unquantified in this dataset**, since no arm was re-run under a repeated-sampling design.

This is stated plainly in the manuscript. Reviewer 2 asked directly.

---

## 8. Deviation register

Any departure from this plan is logged in `results/LOG.md` with date, what changed, and why,
and is surfaced in the manuscript rather than absorbed silently.

---

## 9. Amendments

### 2026-09-11 — Phase 3 reporting clarifications (author-directed)

These change how Phase 3 is *reported*; they change no computed value. The Phase 3 numbers
were already final and committed (`2dea786`) when these were issued.

1. **No strength comparison against the superseded analysis.** The successes-only
   Mann–Whitney is described as **invalid and replaced**, never as weaker or stronger than
   the corrected analyses. Reason: it conditioned on a post-condition outcome and on unequal
   subsets, so it estimated a different quantity on a different sample. Statements of the
   form "the correction strengthened the finding" are removed wherever they appeared.
2. **Effect sizes from the two designs are never juxtaposed.** The successes-only rank-biserial
   and the matched-pairs rank-biserial come from different samples and different designs and
   must not appear in the same sentence or the same table row.
3. **Log-rank and Fisher are reconciled explicitly in the report text**, so the manuscript
   carries the distinction: both are correct and they test different things — Fisher uses only
   the terminal success proportion, the log-rank uses the step at which every episode succeeded
   or was censored. The success-rate claim the manuscript declined to make (Fisher p = 0.072)
   remains declined; the log-rank is a statement about *time to target*, not about the terminal
   proportion, and is not a re-test of the abandoned claim.
4. **Abstract-facing effect measure for Phase 3: the win ratio**, WR = 5.60, 95% CI
   [2.43, 17.97]. It is hierarchical (success first, then speed), so it carries both components
   of the endpoint in one number without conditioning on success.
5. **Figure:** cumulative-incidence curves (`results/fig_cumincidence_a1.{pdf,png}`) replace
   the successes-only boxplot as manuscript Fig. 3b. The boxplot is the selection-biased view
   and is withdrawn.

### 2026-09-11 — Confirmatory-family test, pairing confirmed

Seed pairing was verified before Phase 4 (see `results/LOG.md`). A1 and A2 are completely
paired at 25 seeds; A3 loses two pairs (overlay seeds 4254, 4265, all rows `api_ok=False`),
leaving 23. Per §4 the paired Wilcoxon is therefore used in all three anatomies, on 25, 25 and
23 pairs respectively. No seed is silently dropped: the two unpaired A3 seeds are named in the
multiplicity table and in the exclusion audit.

### 2026-09-11 — Exclusion rule, defined once and applied everywhere (Phase 6d)

**Excluded (not an attempt).** Episodes with **zero valid operator actions** — total API
transmission failure (every row `api_ok=False`, or every row failing `api_ok`/`parse_ok`).
These leave the denominator **entirely**: they are not counted as attempted, as failures, or
as successes, in any table.

**Included.** Episodes with **any** valid operator actions, including those with partial
transmission failures.

**Pairing.** When an episode is excluded from one arm, its seed-matched counterpart is dropped
from all paired tests. The pair count is reported per test and the dropped seeds are named,
never silently omitted.

**No denominator is inherited.** Every count in every table — success rates, Fisher tests,
first-bifurcation branch counts, biplane arms, prompt variants, all three anatomies — is
recomputed under this rule and must trace to a row in `results/denominators.csv`.

#### How partial failures were handled during data collection

Established from the harness source, not inferred (`run_coronary.py:677-695`; `run_asoca.py`
has the same structure):

- **Not retried.** `call_vlm()` is invoked once inside a bare `try/except`. On any exception
  the harness records `api_ok=False` and moves on. There is no retry loop, no backoff, and no
  `max_retries` anywhere in the call path. (The only retry logic in the harness is
  `safe_reset`, which retries the *simulator* reset, not the API.)
- **Not skipped, and the episode is not terminated.** `parse_action()` returns `(None, False)`,
  so `parse_ok=False`, and the harness executes `action_arr = [[0.0, 0.0]]` — a **null (hold)
  action** — then proceeds to the next step.
- **Consequence, which is outcome-relevant and is disclosed rather than assumed away:** a
  partial API failure **consumes one step of the episode's step budget and injects a hold**.
  It does not merely lose information about that step; it can degrade the episode's outcome.
  Episodes carrying many partial failures are therefore penalised relative to clean episodes,
  and any claim that transmission failures are outcome-neutral must be tested (Phase 6e), not
  asserted.
- **Recoverability.** `api_ok` and `parse_ok` are recorded per row, so partial failures are
  fully reconstructable from the traces. No retry attempt is recorded because none was made.

### 2026-09-12 — Confirmatory family redefined as A1 + A2 (post hoc)

**A3 is not an anatomy.** Phase 6f-rev established that its entire lumen surface is generated
— a constant 2.5 mm, 12-sided tube along a patient centreline — so it shares only a centreline
with the ASOCA case it is named after. A confirmatory family should contain like objects.

The confirmatory family is therefore **A1 + A2**: the two patient-derived anatomies, from two
independent CT sources. **A3 is reported separately as a phantom sensitivity analysis**, not as
a family member.

**This is a post hoc amendment.** It was made after the corrected values were known, and is
disclosed as such here and in the manuscript, exactly as the endpoint-hierarchy revision (§9,
2026-09-11) is.

**It cannot manufacture significance, and that is verifiable in one line.** Holm multiplies the
smallest p in a family by m, the next by m−1, and so on, leaving **the largest p unmultiplied**.
A1 holds the largest raw p in either family, so its adjusted p equals its raw p in both:

| Anatomy | Raw p | Holm, 3-member family | Holm, 2-member family |
|---|---|---|---|
| A3 (phantom) | 3.34e-06 | 1.00e-05 (×3) | excluded — reported as sensitivity |
| A2 | 4.82e-04 | 9.65e-04 (×2) | 9.65e-04 (×2) |
| **A1** | **0.0147** | **0.0147 (×1)** | **0.0147 (×1)** |

**Dropping the member with the strongest result changes neither surviving adjusted p-value.**
A reviewer can confirm this without rerunning anything, and `results/phase6_report.txt` already
prints both columns side by side. The amendment reorganises what the family *means*; it moves
no number in our favour.

### 2026-09-12 — A3's role restated: a curvature-only control

A3 is not a failed anatomy to be apologised for. A constant-radius tube following a patient
centreline **isolates curvature from calibre**: it retains the centreline's three-dimensional
course, bifurcation location and target, while removing wall irregularity, taper and calibre
variation entirely.

That makes A3 a *deliberate control condition* answering a question the two patient anatomies
cannot: does the overlay effect survive when wall irregularity and taper are removed? It does —
most strongly of the three (raw p = 3.34e-06, HL +0.1007 [+0.0688, +0.1257]). The effect
therefore does not depend on lumen texture or calibre change, and is attributable to the
centreline course and the bifurcation. A3 is written up in that register, and is still never
counted as a patient-derived anatomy or an independent data source.

### 2026-09-13 — Baselines are calibration, not tested contrasts (Phase 7b)

Scripted baselines exist to calibrate the reader's sense of task difficulty. They are **not**
an arm in a comparison and their contrasts with the VLM arms are **not** significance-tested.

- **No hypothesis test is run between a baseline and a VLM arm.** The Fisher test of
  always-advance (17/25) against VLM overlay (13/25) is computed **once**, recorded as a
  non-result, and never used to support a claim.
- Always-advance is **deterministic** — every success took exactly 27 steps — so it is a fixed
  reference point, not a sampled distribution. All baseline comparisons are stated
  descriptively, as point estimates.
- **The sentence "overlay degrades navigation below a policy that never looks at the image" is
  not supportable and must not appear anywhere**, in any phrasing. Where it was already
  written, it is retracted (see `results/LOG.md`).

### 2026-09-13 — A3 removed from the confirmatory family on physical-validity grounds

The confirmatory family is **A1 + A2**, two members. A3 is removed from Results entirely and
reported in Section V as an attempted-and-excluded geometry.

The grounds are **physical validity, not the result**: a wholly generated constant-radius
surface (C8), Gauss–Seidel LCP non-convergence on **97.2% of steps** with a residual to 1.44,
and an always-advance baseline shut out at 0/25 indicating the geometry is not navigable rather
than merely hard (Phase 7a). See `CORRECTIONS.md` **C11**.

**This removes the family's strongest result** (A3 raw p = 3.07e-07 on the primary unpaired
test, smaller than either surviving member). The exclusion is therefore conservative in
direction.

Holm is unaffected by the family size, which is worth stating precisely because it is the one
thing that would make the exclusion look self-serving. A1 is the largest p in the family either
way, so Holm leaves it unmultiplied: **0.0147** at three members and at two. A2 is the middle
of three (×2) and the smaller of two (×2), so it is **0.000965** either way. Only Bonferroni
moves (A1: 0.0442 → 0.0294), and Bonferroni is not the primary adjustment.

> **Figures corrected 2026-09-13.** This paragraph was first written while the unpaired test was
> primary (C13) and argued the invariance with those values — A1 0.000384, A2 5.89e-06,
> Bonferroni 0.00115 → 0.000768. C14 restored the paired test as primary, so the numbers above
> are the paired ones. **The argument is unchanged and did not depend on which test was
> primary**: Holm's invariance to family size here follows from A1 being the largest p and A2
> taking the same multiplier in both families, which holds under either test. Only the
> arithmetic moved.

> **Superseded figures, kept visible.** This paragraph previously read "A1 remains 0.0147 and A2
> 9.65e-04 under either family size". Those were the paired-era values; the arithmetic claim was
> correct and survives the switch to the unpaired primary (C13), but the numbers do not.

### 2026-09-13 — §7 correction is PROVISIONAL pending Phase 7g

The correction recorded in §7 above may itself be an over-claim, and is flagged here rather
than left to stand unexamined.

§7 originally said seed-matching fixes "the physics trajectory for a given action sequence".
Phase 7a showed that **different** seeds, under identical start states and identical actions,
diverge. But that is what a seed is *for* — it does not contradict the original claim, which
concerns what happens when the seed is **held fixed**.

The decisive test is whether the **same** seed reproduces across repetitions, which is exactly
what Phase 7g measures. If 7g finds every seed reproducing its outcome, the environment is
reproducible given a seed, the §7 correction is withdrawn, and Decision 2's premise weakens
accordingly. If outcomes vary within a seed, the correction stands and 7g quantifies the floor.

No downstream claim rests on the §7 correction until 7g reports.

> **RESOLVED 2026-09-13 — the §7 correction is CONFIRMED, not withdrawn.** Phase 7g ran the
> decisive test: R = 5 repetitions of the full seed list per anatomy, fresh environment per
> repetition, fixed policy. **The same seed does not reproduce.** Only 4/25 seeds on A1 and
> 2/25 on A2 gave the same outcome in all five repetitions; success rate varied over 20.0 pp
> (A1: 64/60/60/44/48%) and 28.0 pp (A2: 76/80/68/72/52%). The start state was identical
> throughout (one distinct post-reset tip across all repetitions × seeds), so the divergence is
> downstream of reset, and steps-to-target within a seed had spread exactly 0 — the noise is a
> **binary commitment flip at the bifurcation**, not trajectory jitter.
>
> Consequence for this section's claim: seeds are matched but **do not determine trajectories**,
> so seed-matching supplies **no blocking and no variance reduction**. Paired tests remain valid
> — the noise is symmetric across arms, so Type I error is not inflated — but the paired design
> must be defended as a valid test of paired differences, **not** as a confound control. The
> submission's "seed-matched, confound-free" justification is withdrawn.

### 2026-09-13 — The variability is BINOMIAL, not instability (Phase 7h)

The §7 correction above stands, but the **characterisation** attached to it was wrong and is
corrected here. Phase 7g was described as showing the environment "does not reproduce a seed",
with an "intrinsic run-to-run noise floor" — language that frames it as a defect.

Phase 7h tested the alternative and simpler reading: the seed carries no information and each
episode is an independent Bernoulli draw. **Both anatomies are consistent with binomial.** A1:
observed variance 4.700 against binomial 6.182, ratio 0.760, X² = 3.041 on 4 df, p = 0.551. A2:
7.300 against 5.290, ratio 1.380, X² = 5.520, p = 0.238. Concordance is unremarkable in either
direction (A1 4 observed vs 1.73 expected, p = 0.091; A2 2 vs 4.15, p = 0.416).

**The correct statement is therefore: the simulator seed does not propagate to episode outcomes,
and episodes behave as independent draws.** The 20 pp and 28 pp run-to-run ranges are ordinary
sampling variability at n = 25 — what any n = 25 binary endpoint carries — and are **not**
evidence that the environment is unreliable.

The continuous endpoint is degenerate under a fixed policy: every successful episode takes
exactly 27 steps on A1 and 11 on A2, so within-seed and between-seed variance are both zero.
All variability lives in the binary outcome.

### 2026-09-13 — Primary test selected by measured correlation, not by p-value (Phase 7i)

**Procedure, fixed before the data were seen and recorded in the script:** compute the
within-pair correlation first; correlation near zero means seed-matching removes no shared
variance and the unpaired Mann-Whitney is primary; meaningfully positive correlation means
pairing does real work and the paired result stays primary. Both tests are reported either way,
with the correlation given as the justification.

**Measured:** A1 f_rot_LM Pearson −0.072 [−0.455, +0.332], efficiency 0.9416; A1 worst-rank
−0.074 [−0.456, +0.330], efficiency 0.9368; A2 f_rot_LM **undefined** (wire-only constant at
0.0000); A2 steps +0.112 [−0.296, +0.486]. On both primary endpoints pairing **adds** ~6% to the
contrast variance while costing 24 degrees of freedom.

**Decision: the unpaired Mann-Whitney is the primary test for f_rot_LM on A1 and A2.** The
paired Wilcoxon is reported alongside. Navigation is unchanged in substance — the win ratio and
log-rank are unpaired by construction and were always the proper analyses of that endpoint.

**This reverses the earlier correction C2 and restores more favourable p-values** (A1 0.0147 →
0.000384; A2 0.000482 → 2.95e-06). The safeguards against that being motivated reasoning are:
the rule preceded the data, Phase 7h independently establishes a mechanistic reason for zero
correlation, and both tests appear in the paper regardless. See `CORRECTIONS.md` **C13**.

**Limit of the claim:** at n = 25 the correlation CIs span [−0.46, +0.33] and do not exclude
moderate positive correlation. The supported claim is "no evidence that pairing removes shared
variance" — not that the correlation is zero.

### 2026-09-13 — Advance-speed sweep: reporting rule fixed BEFORE running (Phase 7c)

The always-advance baseline is run at the harness's own default advance speed,
`PROXIMITY_GATE_ADV_DEFAULT = 35.0 mm/s` (`run_coronary.py`). **That value, and only that
value, is the open-loop baseline reported in the manuscript.**

The sweep over other advance speeds is a **sensitivity curve** showing how the open-loop floor
varies with speed. It is **not** a set of candidate numbers from which a baseline is selected.

This rule is recorded **before the sweep is run**, so the default-is-primary choice is visibly
pre-committed and cannot be read as a selection made after seeing which speed is most
favourable to the manuscript. If the sweep shows a higher floor at some other speed, that
appears in the sensitivity curve and **the headline baseline stays at 35 mm/s**.

### 2026-09-13 — The confirmatory family is TWO members, and A3 gets no adjusted p

**A family is the set of tests we draw inferences from.** A3 is excluded from Results on
physical-validity grounds (`CORRECTIONS.md` C11), so it cannot be counted in the correction
family.

- `confirmatory_results()` declares **A1 + A2**. Holm and Bonferroni both adjust over **two**.
- A3's row is **removed from the confirmatory table entirely**. It is not printed in a table it
  sits outside.
- A3's raw p is reported in the Phase 5 disposition block and in **Section V prose only**,
  beside the exclusion reason, with **no adjusted p** — we do not adjust a test we are not
  inferring from.

**Why this direction and not the other.** Declaring a three-member family while reporting a
two-member result would have inflated the apparent multiplicity burden we overcame, in our own
favour, at no cost to us. We did not, and the invariance is computed rather than asserted:
every declared member's Holm-adjusted p is **identical** under either family size (A1 is the
largest p and is left unmultiplied either way; A2 is the middle of three and the smaller of
two, taking ×2 in both). Only Bonferroni is sensitive (A1 0.0294 at two members, 0.0441 at
three), and Bonferroni is not the primary adjustment. **The exclusion bought us nothing on the
primary correction**, which is the honest form of the claim and the one the response letter now
makes.

Recorded as an amendment to **C11**.

### 2026-09-13 — The paired Wilcoxon is RESTORED as primary (supersedes the C13 switch)

**This reverses the amendment dated 2026-09-13 above that made the unpaired Mann-Whitney
primary, and it reverts to the LESS favourable number. That direction is stated first.**

The earlier amendment let the measured within-pair correlation select the test. That was wrong,
and the reason is **the precision of the correlation itself**. At n = 25, ρ = −0.072 carries a
95% CI of approximately **[−0.455, +0.332]**. That interval does not establish that pairing is
unjustified; it establishes only that pairing is **not demonstrably helping**. Those are
different claims, and only the first would license abandoning the matched analysis.

A 38-fold improvement in the headline p-value — A1 from 0.0147 to 0.000384 — on a test
**Reviewer 2 specifically requested** cannot rest on an estimate that imprecise.

**The rule, restated:**

1. The **paired Wilcoxon signed-rank is primary** for f_rot_LM on A1 (p = 0.0147) and A2
   (p = 0.000482, via phase5's single implementation).
2. The **unpaired Mann-Whitney is reported alongside** — A1 U = 496.0, p = 0.000384; A2
   U = 512.5, p = 2.95e-06 — together with ρ and its 95% CI, and with the explicit statement
   that **the conclusion is unchanged under either test** on both anatomies.
3. **Phases 7h and 7i are retained in full.** The seed genuinely does not propagate to outcomes,
   and that belongs in Methods and in the R2.3 response. Only the choice of primary changes.
4. **ρ is never reported without its 95% CI**, anywhere. A bare ρ = −0.072 invites the reader to
   treat an imprecise estimate as precise, which is the error the superseded amendment made.
   Measured: A1 f_rot_LM −0.072 [−0.455, +0.332]; A1 worst-rank −0.074 [−0.456, +0.330]; A3
   −0.097 [−0.489, +0.329]; A2 **undefined**, the wire-only arm being constant at 0.0000.

**Endpoint status, so the drafts cannot imply otherwise.** f_rot_LM is a **secondary,
mechanistic** endpoint. The paper's primary claim is navigation degradation — A1's worst-rank
imputation, win ratio and log-rank, and A2's complete separation — none of which is affected by
any of this. No draft may imply the paper's strength rests on the rotation p-value.

Recorded as **C14**, superseding C13's switch. C13's entry stays in `CORRECTIONS.md` as the
record of what we did and why; it is marked superseded, not deleted.

### 2026-09-13 — Oracle reachability: definition and reporting rule, fixed BEFORE running (7d)

The oracle exists to give the reader a **ceiling** to set against the open-loop floor, so the
operator's rate can be read as a position between the two rather than as a bare number.

**Definition.** The oracle is not a path-following controller. The action space is (advance
speed, rotation) on a J-tip guidewire, where branch selection is governed by tip orientation
rather than by steering to a waypoint, so "follow the centreline" has no direct realisation in
the action space. The oracle is therefore a **reachability probe over a restricted policy
class**: a grid of constant rotation values, each run over the full seed list at the
pre-committed advance speed of 35 mm/s. It is described in exactly those terms and never as "the
best achievable policy".

**The bias this design carries, and the rule that contains it.** Counting a seed as reachable if
*any* rotation value succeeds is a **maximum over noisy binary trials**. Phase 7g measured a
run-to-run floor of 20.0 pp (A1) and 28.0 pp (A2) for a fixed policy, and Phase 7h showed that
spread is consistent with independent binomial draws. A maximum over G grid values therefore
drifts upward even when no rotation value is genuinely better than another: with enough grid
points the union approaches 100% by selection alone.

So **two figures are reported, always together, and neither is reported without the other**:

1. **Union reachability** — a seed counts if any grid value reached target. This is an
   **upper bound inflated by selection over noise**, and is labelled as such wherever it
   appears. It is not a policy anybody could run, because it requires knowing per seed which
   rotation to use.
2. **Best single rotation value** — the highest success rate achieved by one fixed rotation
   across the whole seed list. This is a deployable policy and is **not** inflated by per-seed
   cherry-picking. This is the figure the calibration sentence uses.

**Pre-committed, so it cannot be chosen afterwards:** where the manuscript needs one oracle
number, it uses **the best single rotation value**, not the union. If the union is far higher,
that gap is reported as a measure of how much of the apparent ceiling is selection over noise —
it is not promoted to the headline because it is larger.

**Scope.** A1 and A2. A3 is absent, as everywhere else (C11). Baseline speed fixed at the
harness default per the 7c pre-commitment, so the oracle and the floor are measured at the same
speed and remain comparable.

### 2026-09-15 — 35 mm/s is not the harness default; the 7c rule's rationale is corrected (C17)

The 7c rule above describes 35 mm/s as "the harness's own default advance speed". **That is
wrong.** `PROXIMITY_GATE_ADV_DEFAULT = 35.0` is used only as the translation substituted when the
proximity gate suppresses a rotate intent (`run_coronary.py:708`). The operator chose its own
translation on every other step, with a median advance of 10 mm/s on A1 (both arms) and A2
wire-only, and 5 mm/s on A2 overlay.

**What stands.** 35 mm/s was fixed in advance and remains the reported floor speed; the
pre-commitment was honoured. **What changes.** Its rationale: it is a fixed speed chosen before
the sweep, not the operator's speed and not a harness default. The floor at 35 mm/s is reported
pooled over every artifact-backed draw (C16), the operator's own advance distribution is reported
beside it, and the 15 mm/s figures are given as the nearest speed-matched comparison. The
operator-versus-floor statement is descriptive only; no test is run between them (7b unchanged).

The 7c sweep was **closed at 12 shards** (15 / 35 / 55 mm/s on both anatomies) by author direction
on 2026-09-14, replacing the five-speed grid; this is a scope decision, recorded here.

### 2026-09-15 — The oracle is not a ceiling (C18)

The 7d amendment above says the oracle "exists to give the reader a ceiling". That framing is
**withdrawn**: best single rotation does not exceed the blind policy's own best draw at the same
speed on either anatomy. The oracle is reported as a reachability probe over constant-rotation
policies. The two-figure reporting rule is unchanged and was followed.

### 2026-09-15 — The biplane arms are not budget-matched (C19)

Verifying step budgets from the traces, rather than from run-directory names, showed that the
monoplane arms ran to their 120-step budget (every failure truncated at 120) while the biplane
arms' longest episodes were 40 and 48 steps, and two biplane wire-only episodes ended at 30 and
20 steps — below their own arm's longest — without reaching target. The only truncation criterion
in the environment builder is a fixed maximum step count, which cannot end an episode below its
arm's maximum, and the biplane trace schema does not record truncation. The cause of those two is
not recoverable from the logs.

The biplane study is exploratory and enters no confirmatory family. Its f_rot_LM contrast is
retained with the caveat attached; **no success comparison is drawn between monoplane and biplane
arms**, and the "seed- and budget-matched" description is withdrawn. Budgets quoted anywhere in
this work are now verified from traces, never from directory names.

### 2026-09-15 — Target journal

The resubmission target is the *International Journal of Computer Assisted Radiology and
Surgery*. No analysis decision depends on the venue.
