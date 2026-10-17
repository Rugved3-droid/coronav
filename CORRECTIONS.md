# CORRECTIONS

Corrections to the analyses submitted to IEEE T-MRB as manuscript
**TMRB-07-26-OA-0710**, made while preparing the resubmission. The target journal was first
*Computers in Biology and Medicine* and is now the *International Journal of Computer Assisted
Radiology and Surgery* (author decision, 2026-09-15); entries dated before that decision refer to
the earlier target and are otherwise unchanged. The branch name `revision-cbm` is historical.

**Scope.** `master` is frozen as the T-MRB record and its history is not rewritten.
`RESULTS.md` and `PROTOCOL.md` are not edited in place; each carries a dated SUPERSEDED
banner with the original text retained verbatim beneath it. `PROTOCOL.md` in particular is
**evidence**: it records that "median + Mann-Whitney" and "successes only" were
pre-specified, not chosen after seeing results.

All corrected values are reproducible from `results/` via the scripts in `analysis/`.
Raw episode logs were treated as read-only throughout and no value was imputed or estimated.

---

## C1 — Steps-to-target was compared among successful episodes only

**Original claim.** `RESULTS.md`: "Median steps to target (successes only) 48.0 vs 58.0,
U = 24, p = 0.0001, r = 0.812", with the seed-matched Wilcoxon on the 9 seeds where both arms
succeeded (W = 3, p = 0.020) offered as the confound-free version.

**Why it was wrong.** Success is an outcome of the condition under test, and the arms
contributed unequal subsets (20/25 wire-only vs 13/25 overlay). Conditioning the comparison
on a post-condition outcome is a selection bias — Reviewer 2, comment 3. The 9-seed matched
test does not repair it either: those 9 seeds are themselves the seeds on which *both* arms
succeeded, which is again a post-condition selection.

**What replaced it.** Three analyses over all 50 A1 episodes, pre-specified in
`analysis/PRESPEC.md` before being run:

| Analysis | Result |
|---|---|
| Worst-rank imputation, Wilcoxon signed-rank, 25 pairs (approx) | W = 47.5, **p = 0.00206**, rank-biserial +0.708, HL +15.50 ranks [+7.00, +23.25] |
| Win ratio (Finkelstein–Schoenfeld), 470W/84L/71T of 625 pairs | **WR = 5.595**, bootstrap 95% CI [2.431, 17.970] |
| Time-to-event, failures censored at the 60-step budget | log-rank χ² = 11.705, **p = 0.000623** |

The successes-only Mann-Whitney is **invalid and replaced**, not re-weighted. It is not
described as weaker or stronger than the replacement, and its effect size is never placed
beside a matched-design effect size: the two estimate different quantities on different
samples under different designs.

**Commits.** `2dea786`, amended reporting in `a331993`.
**Artifacts.** `results/phase3_report.txt`, `phase3_tests.csv`, `phase3_episodes_a1.csv`,
`fig_cumincidence_a1.{pdf,png}`.

---

## C2 — An unmatched test was used on a matched design

**Original claim.** `RESULTS.md` and `PROTOCOL.md`: the primary rotation endpoint
(`lm_rot_mm`, here renamed `f_rot_LM`) was tested with a two-sided Mann-Whitney U,
reported for A1 as **p = 0.0004, r = 0.587**.

**Why it was wrong.** The arms are seed-matched pair-for-pair — verified here: A1 and A2 pair
completely at 25 seeds, A3 at 23. Mann-Whitney discards that pairing. Reviewer 2, comment 3,
asked directly for "an analysis method that conforms to the matched design".

**What replaced it.** Wilcoxon signed-rank on the 25 seed-matched pairs, two-sided, exact
method (no zeros, no ties):

> **W = 73.0, n = 25 pairs, p = 0.0147**, matched-pairs rank-biserial +0.551,
> Hodges–Lehmann +0.0285 [+0.0068, +0.0440].

Direction is unchanged (overlay > wire-only, higher on 20 of 25 seeds). Mann-Whitney is
retained only as a clearly-labelled secondary sensitivity line (U = 496, p = 0.000384).

**Consequence, stated plainly.** The corrected primary p is an order of magnitude less
extreme than the figure in the manuscript. Design sensitivity at n = 25 with 80% power gives
a minimum detectable paired shift of 0.0292; the observed shift is 0.0285, i.e. **0.98× the
MDE**. The rotation endpoint sits essentially at its own detection limit. This is reported in
full wherever the endpoint appears, and is not softened.

**Commits.** `ca313e1`.
**Artifacts.** `results/phase4_report.txt`, `phase4_tests.csv`, `phase4_pairs_a1.csv`.

---

## C3 — A2's effect was reported as a magnitude shift; it is a floor effect

**Original claim.** `RESULTS.md`: A2 "LM rot/mm 0.000 vs 0.050", presented alongside A1 and A3
as one of three equivalent cross-anatomy replications, "median diff +0.0454".

**Why it was wrong.** Every one of the 25 A2 wire-only episodes has `f_rot_LM` of exactly
0.0000. Nine overlay episodes are also exactly 0.0000, so nine pairs have a difference of
exactly zero and are **dropped** by the signed-rank test: the effective sample is **16, not
25**, and the test degenerates to a sign test on 16 uniformly positive differences (hence
W = 0 and rank-biserial = +1.000). A2's median/IQR is degenerate, [0.0000, 0.0000].

A2 therefore evidences *presence versus absence* of LM-phase rotation, not a graded shift, and
its effect size is not comparable to A1's or A3's. It must not be described as a
"+0.045 shift". This is structurally the same degeneracy the manuscript itself labelled
"UNINFORMATIVE" for prompt variant V2, except that here only one arm is pinned at the floor.

**Substantiated behaviourally (Phase 6c).** The zero was tested for the obvious failure mode —
`f_rot_LM` weights rotation steps by `|dist_delta|`, so an in-place rotation that turns the tip
without translating it would be silently zeroed. It is not that: A2 wire-only issued **zero
rotate actions during the LM phase across all 25 episodes**, while A2 overlay issued 37 across
16/25 episodes. Nor is the phase trivially short — A2's LM phase spans a median of 15 steps
versus A1's 16, and A1's operator rotated 104 times over that span. The floor is a real
behavioural contrast. See `results/phase6c_report.txt`.

### Replacement reporting for A2's rotation result: induction, not magnitude (Phase 6g)

Rotate-intent **counts** are the primary A2 rotation evidence; the signed-rank p is secondary.
Drafted text:

> Under wire-only, the operator issued **zero rotate intents during the left-main phase in all
> 25 episodes**. Under overlay it issued **37, across 16 of 25 episodes**. The left-main phase
> is not vanishingly short in either arm — a median of 15 steps under wire-only and 19 under
> overlay, against 16 and 27 respectively in A1 — so the absence is not an artefact of a brief
> traversal window. A2 therefore demonstrates **induction of a behaviour that is otherwise
> entirely absent**, rather than a shift in its rate.

> The signed-rank test on `f_rot_LM` is reported as secondary support (W = 0.0; 25 pairs, of
> which 16 informative; p = 4.82e-04). Its rank-biserial of +1.000 and its degenerate median
> and IQR of [0.0000, 0.0000] in the wire-only arm reflect the floor and are not effect-size
> estimates; they are not compared with A1's.

**Scope note, so the claim is not overstated.** A2 wire-only is not motionless: it issues 26
rotate intents in total across 18 of its 25 episodes. The absence is specific to the
**left-main phase**, which is the phase the endpoint is defined over. Any statement that A2
wire-only "never rotates" is wrong; the correct statement is "issues no rotate intents during
the left-main phase". Evidence: `results/phase6h_report.txt`.

**What replaced it.** The confirmatory family is reported with Holm (primary) and Bonferroni
(named by Reviewer 1), with the informative pair count stated wherever it differs from the
pair count:

| Anatomy | W | n pairs | Method | Raw p | Holm | Bonferroni |
|---|---|---|---|---|---|---|
| A1 | 73.0 | 25 | exact | 0.0147 | 0.0147 | 0.0442 |
| A2 | 0.0 | 25 (16 informative) | approx | 0.000482 | 0.000965 | 0.00145 |
| A3 | 6.0 | 23 | exact | 3.34e-06 | 1.00e-05 | 1.00e-05 |

Leave-A3-out (Reviewer 1's request, given A3's synthetic tube surface) retains the claim:
A1 Holm p = 0.0147, A2 Holm p = 0.000965. But the two survivors are **not equivalent
replications** — A2 is the floor effect, so A1 is the only graded result remaining and it is
also the weakest.

**Commits.** `4dd5656`, `01b4aa6`.
**Artifacts.** `results/multiplicity_table.csv`, `phase5_report.txt`,
`phase6_leave_a3_out.csv`, `phase6_report.txt`.

---

## C4 — Endpoint hierarchy revised after seeing the corrected results (post hoc)

**Original hierarchy.** `PROTOCOL.md` pre-specifies `lm_rot_mm` as the **primary** metric, with
`success_rate`, `steps_to_target` and `wrong_branch_rate` as secondary.

**Revised hierarchy.** Navigation degradation (success and steps-to-target, analysed without
conditioning on success) is promoted to **primary**; LM-phase rotation is demoted to a
**mechanistic secondary**.

**Why.** After correction, the rotation endpoint is p = 0.0147 at 0.98× its own MDE, whereas
the navigation endpoint is large and robust: WR 5.60 [2.43, 17.97], log-rank p = 0.000623, and
A3 overlay 0/25 successes (Fisher p = 0.000636).

**This is a post hoc revision of the endpoint hierarchy and is disclosed as such**, in the
manuscript and here. It was decided *after* the corrected values were known. `PROTOCOL.md` is
retained unedited precisely so a reader can verify what the original hierarchy was and confirm
that the original choices were pre-specified rather than selected after the fact.

The corrected rotation result is **not removed or softened anywhere**. It is reported in full
at p = 0.0147 with its confidence interval and its minimum detectable effect, in its new role
as a mechanistic secondary endpoint.

---

## C5 — The public anonymized repository reflects the uncorrected analyses

The anonymized public repository referenced in the T-MRB submission contains `RESULTS.md` and
`PROTOCOL.md` as submitted, and therefore presents the analyses corrected in C1–C4 above as if
current. It is left in place as the frozen record of what was submitted.

**The resubmission will point to a corrected snapshot** — the `revision-cbm` line of
development, carrying these SUPERSEDED banners, this file, and the `results/` artifacts — so
that no reader following the manuscript's repository link reaches the uncorrected numbers
without also reaching this correction record.

---

## C6 — Denominators were inherited rather than recomputed

**Original claim.** A3's success comparison was reported with 25 as the overlay denominator
(`0/25`), and the same inherited denominators ran through the success and first-bifurcation
rows of the Phase 5 multiplicity table.

**Why it was wrong.** Seeds **4254 and 4265** in the A3 overlay arm have **zero valid operator
actions** — all 150 rows of each carry `api_ok=False`. An episode in which the operator never
acted is not a failed navigation attempt; it is not an attempt at all. Counting it as a
behavioural failure inflates the denominator and attributes a transmission outage to the
operator's navigation.

It was also **internally inconsistent**: those same two episodes were already excluded from
A3's rotation endpoint, which was correctly reported on 23 pairs. One table said 23 and
another said 25 for the same arm.

**What replaced it.** An exclusion rule stated once in `analysis/PRESPEC.md` (amendment
2026-09-11) and applied mechanically to **every** count — success rates, Fisher tests,
first-bifurcation counts, biplane arms, prompt variants, all three anatomies:

> Excluded (not an attempt): zero valid operator actions. Included: any valid operator
> actions, partial failures included. Pairing: a seed excluded in one arm is dropped from
> paired tests, with the pair count reported and the dropped seeds named.

Every denominator now traces to `results/denominators.csv`.

**New values.**

| Row | Before | After |
|---|---|---|
| A3 success (Fisher) | 10/25 vs **0/25**, p = 0.000636 | 10/25 vs **0/23**, **p = 0.000675** |
| A3 first-bifurcation LCx | n = 25+25, p = 1.00 | n = 25+23, p = 1.00 |

**What did not move, verified rather than assumed.** The confirmatory family is unchanged
(A1 raw p = 0.0147, A2 0.000482, A3 3.34e-06; Holm unchanged), because the paired tests
already dropped episodes whose metric was undefined. Phase 6 leave-A3-out is unchanged. Both
were re-run to confirm this rather than reasoned about.

**Exclusions elsewhere, now explicit.** The sweep also surfaced two arms whose reduced n had
been implicit in the tables but untraceable: prompt variant **V3 overlay** (10 attempted → 5
analysed, seeds 5045/5056/5067/5078/5089 fully failed) and the **old-prompt contrast** arm
(15 attempted → 7 analysed, 8 seeds fully failed). Both now appear in `denominators.csv`.

**One borderline case the rule produces, flagged rather than hidden.** V3 overlay seed 5034
has **53 of its 60 steps failed** and is nonetheless RETAINED, because 7 valid actions
survive. The rule as written admits an episode that is 88% transmission failure. This affects
an exploratory arm only, but the threshold is a judgement call and is recorded as such.

**Artifacts.** `results/denominators.csv`, `results/phase6d_pairing.csv`,
`results/phase6d_report.txt`; `analysis/phase6d_denominators.py`, amended
`analysis/phase5_multiplicity.py`. Phase 6d.

---

## C7 — "Exclusions were not outcome-dependent" is not supportable as written

**Original claim.** The Methods state that the excluded episodes "were not outcome-dependent."

**Why it required testing rather than repetition.** Two separate mechanisms could make that
claim false. First, exclusion probability scales with the number of API calls per episode,
which scales with episode length, which is itself the outcome under study — and overlay
episodes are substantially longer. Second, and not previously noted anywhere: a failed call
is **not retried and not skipped**. `run_coronary.py:677-695` executes `[[0.0, 0.0]]`, a null
**hold**, and continues. Every failure inside a retained episode therefore **consumes one step
of that episode's budget**, so even partial failures are not outcome-neutral.

**Two quantities that must be separated.** Conflating them gives the wrong answer:

- **(a) Whole-run outages** — every call in an episode fails. These *cause* exclusions and are
  removed by C6's rule, so they cannot bias the analysed data.
- **(b) Sporadic failures inside retained episodes** — these inject holds into episodes that
  remain in the analysis, and are the only bias-relevant quantity.

Raw per-call rates are dominated by (a) and are misleading. A3 overlay's raw rate of **8.11%**
is almost entirely the two fully-failed episodes: 300 of its 304 failures. Among retained
episodes it is **0.116%**.

**Findings — per-call failure rate among retained episodes:**

| Arm pair | wire_only | overlay | Fisher p (retained) | Raw p, for contrast |
|---|---|---|---|---|
| **A1** | 17/1277 (1.331%) | 0/1448 (0.000%) | **2.39e-06 — differs** | 2.39e-06 |
| A2 | 0/1026 (0.000%) | 3/1400 (0.214%) | 0.268 — no difference | 0.268 |
| **A3** | 1/3438 (0.029%) | 4/3450 (0.116%) | **0.375 — no difference** | 6.25e-87 |
| V2, V4, BI120, OLD15 | 0 | 0 | 1.00 — no difference | 1.00 |
| V3 (exploratory) | 1/600 (0.167%) | 53/300 (17.667%) | 7.15e-26 — differs | 4.09e-137 |
| mono120 (exploratory) | 12/960 (1.250%) | 0/1025 (0.000%) | 0.000158 — differs | 0.000158 |

**Direction and magnitude matter here, and they favour caution rather than the claim:**

- Of the three primary anatomies, only **A1** differs, and it differs **against wire-only** —
  the *better-performing* arm is the one losing steps to injected holds. This biases against
  the reported effect, not toward it.
- A1's entire burden is **17 holds concentrated in one episode** (seed 5221), 1.33% of that
  arm's action budget.
- **A3's 0/23 is not explained by transmission failure.** Its four retained failures occur at
  steps 147–150 — median position 0.99 of the episode — after the outcome was already settled,
  and total 0.20% of the arm's budget.
- The excluded episodes are **consecutive and fall at the end of their run block** (A3 overlay
  episodes 24–25 of 25; V3 overlay 5–9; contrast 8–15 of 15), which is the signature of a
  sustained outage or credit exhaustion during that block rather than of the condition. But
  each arm was collected as one contiguous time block, so **condition and collection window
  are confounded and cannot be separated from these logs.**

**Replacement Methods text.** The sentence "exclusions were not outcome-dependent" is removed
and replaced with:

> Transmission failures were logged per step. Episodes in which every call failed (zero valid
> operator actions) were excluded as non-attempts; episodes with partial failures were
> retained. A failed call was neither retried nor skipped: the harness executed a null action,
> so each failure consumed one step of the episode's budget. We therefore do not claim these
> exclusions were outcome-independent. Among retained episodes, per-call failure rates
> differed between arms in one of the three primary anatomies (A1: 1.33% wire-only vs 0.00%
> overlay, Fisher p = 2.4e-06) and in two exploratory arms, while A2 and A3 showed no
> difference (p = 0.268 and p = 0.375). Where a difference exists in the primary anatomies it
> disfavours the wire-only arm — the better-performing condition — and amounts to 17 injected
> holds concentrated in a single episode, 1.3% of that arm's action budget. Excluded episodes
> were consecutive and fell at the end of their collection block; because each arm was
> collected as one contiguous block, condition and collection window are confounded and cannot
> be separated from these logs. We report this as an unresolved limitation and give all
> denominators explicitly.

**Artifacts.** `analysis/phase6e_api_audit.py`; `results/phase6e_report.txt`,
`phase6e_percall_rates.csv`, `phase6e_failure_steps.csv`. Phase 6e.

### Sensitivity closing Reviewer 1's minor comment on excluded API failures (Phase 6i)

Reviewer 1 asked us to "report the frequency and distribution of API transmission failures that
were excluded, to confirm that no selection bias was introduced." Rather than assert the bias
is conservative, we quantify it.

All 17 A1 wire-only holds fall in a **single episode (seed 5221), which is a failure**; overlay
absorbed none, and **no successful episode was affected**. Consequently the worst-rank test and
the win ratio are unchanged to the digit, while the log-rank strengthens because that failure
is censored earlier:

| Variant | worst-rank | win ratio | log-rank |
|---|---|---|---|
| As analysed | p = 0.00206 | 5.60 [2.43, 17.97] | p = 0.000623 |
| Hold-discounted | p = 0.00206 | 5.60 [2.43, 17.97] | p = 0.000157 |
| Bound (5221 granted success) | p = 0.00118 | 5.74 [2.55, 18.10] | p = 0.000274 |

The bound is not an imputation: we cannot know what seed 5221 would have done with 17 more
usable actions, so we grant it the most favourable outcome its budget permits and show the
conclusion survives that too.

**Methods sentence (corrected).** An earlier auto-generated draft of this sentence said the
discount left results "unchanged" while quoting a log-rank p that had changed; the accurate
version distinguishes the three analyses:

> Transmission failures injected 17 null hold actions into the A1 wire-only arm (17 of 1277
> calls, confined to a single episode) and none into the overlay arm. Because a failed call was
> executed as a null action rather than skipped, each hold consumed one step of that episode's
> budget, so the loss fell entirely on the faster arm and biases against the reported effect.
> The affected episode was itself a failure and no successful episode was affected, so
> discounting the hold steps left the worst-rank comparison and the win ratio unchanged
> (p = 0.00206; win ratio 5.60, 95% CI 2.43–17.97) and strengthened the log-rank
> (p = 0.000623 to p = 0.000157). Granting that episode success at its full budget as an upper
> bound on the holds' cost also preserved the result (p = 0.00118; log-rank p = 0.000274).

**Artifacts.** `analysis/phase6i_hold_sensitivity.py`; `results/phase6i_report.txt`,
`phase6i_tests.csv`. Phase 6i.

---

## C8 — The Methods misdescribe A3's mesh provenance

**Original claim (as submitted).** That *a bifurcation region* of A3 was reconstructed as a
synthetic open tube, and that A3 is "only partly patient-derived". A3 is presented in the
abstract and in Table 2 alongside A1 and A2 as one of three anatomies drawn from two
independent CT data sources.

**What is actually the case.** `clip_asoca_left.py:246-251` tests the *whole* clipped mesh for
boundary edges and, if it is closed, replaces `final` **in its entirety** with
`generate_tube_fallback(branches, bif_pt)`. That function (lines 114-151) iterates over **every
branch** and builds `pv.Spline(coords, n_points=60).tube(radius=TUBE_RADIUS_MM, n_sides=12,
capping=False)` with `TUBE_RADIUS_MM = 2.5`, merges them, cleans and decimates. **The entire A3
lumen surface is generated. No part of the A3 vessel wall is a patient surface.**

| A3 property | Status |
|---|---|
| Centerline path (LM, LAD, LCX) | Patient-derived — ASOCA Normal_5 |
| Bifurcation location | Patient-derived (`bif_pt` = LM last coordinate) |
| Ostium insertion point and direction | Patient-derived |
| Mid-LAD target index | Patient-derived |
| **Entire lumen wall surface** | **Generated** — constant 2.5 mm radius, 12-sided section |
| Taper, calibre variation, wall irregularity | **Not represented** |
| Bifurcation *shape* | Geometric approximation, not anatomical |

**The existential check — A1 and A2 are genuinely patient-derived.**

- **A1 (VMR 0066)** is produced by `coronary_fixture/clip_left_coronary.py`, which contains
  **no fallback or substitution path of any kind**: it clips the VMR patient surface by
  centerline proximity, keeps the largest connected component, decimates, repairs normals,
  saves. Verified by reading the whole file.
- **A2 (ASOCA Normal_12)** goes through `clip_asoca_left.py`, whose tube fallback is gated on
  the clipped mesh being **closed**. A2's mesh is **open** (9 boundary edges), so the gate
  never fired.
- `ANATOMY_NOTES.md`, written during data preparation, independently records A1 as
  "patient-derived throughout", A2 as "Patient-derived surface mesh throughout", and A3 as
  "**SYNTHETIC OPEN TUBE** … NOT a clipped patient surface mesh". Face counts match that
  record exactly: **15,897 / 6,689 / 632**.

So the two-source patient-derived framing survives — for A1 and A2. A3 was never a third
patient-derived anatomy.

**Supporting measurement, reported with its limits.** Wall-to-wall lumen crossings
(`analysis/phase6f_mesh_provenance.py`) make A3 by far the most uniform mesh — CV **0.197**
with 35.6% of crossings within 5% of the median, against A1 0.455/10.0%, A2 0.463/6.1%, and
A3's own pre-fallback clip 0.487/3.3%. **This corroborates but does not by itself establish
the substitution.** It did not produce the predicted spike at 2R (~4.83 mm for a 12-gon
inradius), returning a median of 4.22 mm with residual spread, and its absolute scale is
biased low on every mesh (A1 measures 1.81 mm where the manuscript itself gives a ~4.5 mm left
main). The residual spread is attributable to `decimate_pro(0.85)` applied to the tube, ring
collapse, and overlapping tubes at the merged bifurcation. **The generating source and the
contemporaneous notes are the authoritative evidence.** An earlier vertex-normal version of
this measurement was invalid and its numbers were discarded, not reported.

One clean corroboration did land: A3's pre-fallback clip
(`clipped_asoca_normal5_oldorient.obj`) is **closed — 0 boundary edges** — precisely the
condition the clipper tests for and precisely what `ANATOMY_NOTES.md` says triggered the
substitution.

### Status of this error: it entered at manuscript drafting, not at data preparation

This distinction is the substance of the correction, and it belongs in the response letter.

**The project record documented all three meshes correctly, at the time they were built.**
`D:\steve\pilot\ANATOMY_NOTES.md` (written during data preparation, before any VLM episodes on
these anatomies) states:

- VMR 0066 — *"Left Coronary, patient-derived throughout"*
- ASOCA Normal_12 — *"Patient-derived surface mesh throughout. Geometry is representative of
  real anatomy."*
- ASOCA Normal_5 — *"**SYNTHETIC OPEN TUBE** generated from patient centerlines. NOT a clipped
  patient surface mesh."*

It goes further, with an explicit property table separating what is preserved from what is
generated — *"Lumen surface geometry: **Synthetic** — uniform 2.5mm tube radius, 12-sided
polygon"* and *"Vessel wall irregularities, taper, curvature: **Not represented**"* — and a
numbered implications list whose first entry reads *"Real patient anatomy is NOT represented at
the surface level for Normal_5."* It even contains a drafted, accurate limitations paragraph
for the manuscript.

Its recorded face counts (15,897 / 6,689 / 632) match the meshes measured in Phase 6f-rev
exactly, so the record is not merely contemporaneous but verifiably describes the same files
that were simulated.

**The manuscript did not carry that record forward.** It narrowed "the entire lumen surface" to
"a bifurcation region", and described a wholly generated surface as "only partly
patient-derived".

**Why this matters for the response letter.** The error is one of *imprecise writing at drafting
time*, not of unreliable data, unrecorded provenance, or an undocumented substitution. Nothing
about the simulation changed; what changed is that the Methods now say what the project record
always said. The corrected description is available without re-running anything, and the
original record is in the repository for verification.

**Replacement Methods text.**

> A3 is not an anatomy and not a third data source. It is a synthetic vessel phantom: a
> constant-radius (2.5 mm), 12-sided open tube generated along the ASOCA Normal_5 patient
> centerline. The ASOCA surface reconstruction for that case could not be used — its lumen
> radius (≤ 2.75 mm) fell entirely within the 4 mm centerline-proximity clip, so the clip
> retained every face and produced a closed surface, which over-constrained the Gauss-Seidel
> LCP solver and diverged. Patient-derived quantities in A3 are limited to the centerline
> path, the bifurcation location, the ostium insertion point and direction, and the mid-LAD
> target index. The lumen wall is entirely generated: no taper, no calibre variation, no wall
> irregularity, and a bifurcation that is anatomically placed but geometrically approximated
> rather than anatomically shaped. Results from A3 therefore characterise navigation in a
> centerline-faithful phantom, not in patient vessel anatomy. A3 is not counted as a
> patient-derived anatomy, and not as an independent CT data source, anywhere in this work.

**Consequences that follow and must propagate.**

1. "Three anatomies, two independent CT data sources" becomes **two patient-derived anatomies
   (VMR 0066, ASOCA Normal_12) from two independent CT sources, plus one centerline-faithful
   synthetic phantom**.
2. The abstract's "replicates across all three anatomies and both CT data sources" is not
   accurate as written and must be restated.
3. A3 supplies the *strongest* rotation result in the confirmatory family
   (raw p = 3.34e-06). That result is from the phantom. Patient-derived replication of the
   rotation endpoint therefore rests on A1 and A2 — which is exactly what Phase 6's
   leave-A3-out analysis already reports, and why that analysis is now load-bearing rather
   than a robustness check.

**Artifacts.** `analysis/phase6f_mesh_provenance.py`;
`results/phase6f_mesh_provenance.{txt,json}`. Phase 6f-rev.

---

## C9 — Confirmatory family redefined as A1 + A2; A3 reported as a phantom control

**Original.** The confirmatory family was A1, A2 and A3, described as three anatomies from two
independent CT data sources, with Holm applied across all three.

**Why it changed.** C8 established that A3's entire lumen surface is generated. A confirmatory
family should compare **like objects**, and A3 shares only a centreline with the ASOCA case it
is named after. The family is therefore **A1 + A2** — the two patient-derived anatomies, from
two independent CT sources — and **A3 is reported separately as a phantom sensitivity
analysis**.

**This is a post hoc amendment**, made after the corrected values were known, and is disclosed
as such here and in `analysis/PRESPEC.md` §9 (dated 2026-09-12), exactly as the
endpoint-hierarchy revision (C4) is.

**It cannot manufacture significance, and a reviewer can verify that in one line.** Holm
multiplies the smallest p in a family by *m*, the next by *m*−1, and leaves **the largest p
unmultiplied**. A1 holds the largest raw p in either family, so its adjusted p equals its raw p
in both:

| Anatomy | Raw p | Holm, 3-member | Holm, 2-member |
|---|---|---|---|
| A3 (phantom) | 3.34e-06 | 1.00e-05 (×3) | excluded — reported as sensitivity |
| A2 | 4.82e-04 | 9.65e-04 (×2) | 9.65e-04 (×2) |
| **A1** | **0.0147** | **0.0147 (×1)** | **0.0147 (×1)** |

**Removing the member with the strongest result changes neither surviving adjusted p-value.**
`results/phase6_report.txt` already prints both columns side by side, so this requires no
recomputation and no trust. The amendment changes what the family *means*; it moves no number
in our favour.

### A3's role, stated positively

A3 is not a failed anatomy requiring apology. A constant-radius tube following a patient
centreline **isolates curvature from calibre**. Drafted manuscript text:

> A3 is a curvature-only control rather than a third anatomy. It is a constant-radius
> (2.5 mm), twelve-sided open tube generated along the ASOCA Normal_5 patient centreline. The
> construction preserves the centreline's three-dimensional course, the bifurcation location,
> the ostium insertion point and the mid-LAD target, while removing wall irregularity, taper
> and calibre variation entirely. It therefore isolates centreline curvature from lumen
> calibre, and tests whether the overlay effect depends on vessel-wall geometry that the two
> patient-derived anatomies necessarily confound with curvature.

> The overlay effect survives that removal, and is in fact largest there: Wilcoxon signed-rank
> on 23 matched pairs, W = 6.0, raw p = 3.34e-06, Hodges–Lehmann +0.1007 [+0.0688, +0.1257].
> Because taper and wall texture are absent by construction, the effect cannot be attributed to
> them; it tracks the centreline course and the bifurcation. A3 is not counted as a
> patient-derived anatomy, and not as an independent CT data source, anywhere in this work.

**Artifacts.** `analysis/PRESPEC.md` §9 (amendments dated 2026-09-12);
`results/phase6_report.txt`, `results/phase6_leave_a3_out.csv`.

---

## C11 — A3 removed from Results on physical-validity grounds

**What changes.** A3 (ASOCA Normal_5) is removed from all Results tables, figures, and the
confirmatory family. The confirmatory family is **A1 + A2**. A3 moves to Section V as an
**attempted-and-excluded geometry**.

**Three independent reasons, each sufficient on its own:**

1. **The surface is wholly synthetic.** Not a bifurcation region — the entire lumen wall is a
   generated constant-radius 2.5 mm, twelve-sided tube along a patient centreline (C8).
2. **The solver does not resolve the physics.** Gauss–Seidel LCP fails to converge on
   **97.2% of steps** (3646 of 3750) with a residual reaching **1.44**, against 9.2% and
   2.04e-02 on A2 (Phase 7a). Results computed on A3 describe contact physics the solver never
   actually solved.
3. **The geometry is not navigable, not merely difficult.** The always-advance baseline is shut
   out at **0/25**, while clearing A1 at 17/25 and A2 at 20/25 (Phase 7a).

**This removes our strongest result, and that is the point.** A3 supplied the largest rotation
effect in the confirmatory family (raw p = 3.34e-06, HL +0.1007 [+0.0688, +0.1257]) — larger
than A1's or A2's. It is removed **on physical-validity grounds, not on its result**. Had the
decision been outcome-driven it would have gone the other way. The direction of this exclusion
is conservative and should be read as such.

**Relationship to C9.** C9 already moved A3 out of the confirmatory family on
*like-objects* grounds (a phantom is not an anatomy). C11 supersedes that with a stronger
reason: even as a phantom, its physics is unresolved. Both rationales stand; C11 is the
governing one.

**Nothing is deleted.** Every A3 artifact, trace, script and result stays in the repository,
reported as excluded rather than removed. A reader can audit the excluded analysis in full.

**Holm is unaffected**, as C9 already established: A1's adjusted p is 0.0147 and A2's 9.65e-04
under both the three- and two-member family, because Holm leaves the largest p in a family
unmultiplied.

### Amendment, 2026-09-13 — the family is DECLARED as two, and A3 gets no adjusted p

C11 removed A3 from Results but left the analysis code still iterating three anatomies and
still adjusting Holm over three members. That gap is closed here. **A family is the set of
tests we draw inferences from**, so a geometry excluded from Results cannot be counted in the
correction family.

- `confirmatory_results()` declares **A1 + A2**. Holm and Bonferroni both adjust over **two**.
- **A3's row is removed from the confirmatory table entirely.** It is not printed in a table it
  sits outside.
- A3's raw p is reported in the Phase 5 disposition block and in **Section V prose only**,
  beside the exclusion reason, with **no adjusted p**. We do not adjust a test we are not
  inferring from.

**Why we did not declare three.** Declaring a three-member family while reporting a two-member
result would have inflated the apparent multiplicity burden we overcame — in our own favour,
and at no cost to us, since the adjusted values would not have changed. We did not do that, and
the invariance is now computed in `phase6_leave_a3_out.py` rather than asserted: every declared
member's Holm-adjusted p is **identical** under either family size (A1 is the largest p and is
left unmultiplied either way; A2 is the middle of three and the smaller of two, taking ×2 in
both). Only Bonferroni is sensitive — A1 **0.0294** at two members against 0.0441 at three —
and Bonferroni is not the primary adjustment. **The exclusion bought us nothing on the primary
correction**, which is the honest form of the claim and the one the response letter now makes.

The figures quoted in the paragraph above remain correct under the restored paired primary
(**C14**): A1 Holm **0.0147**, A2 Holm **0.000965**.

**Artifacts.** `results/phase6f_mesh_provenance.txt`, `results/LOG.md` (Phase 7a),
`results/baselines/always_advance_a3_*`; amendment: `results/phase5_report.txt`,
`multiplicity_table.csv`, `phase6_report.txt`, `analysis/phase5_multiplicity.py`,
`analysis/phase6_leave_a3_out.py`. Phase 8 / Decision 1.

---

## C12 — Three further Methods misstatements, found by reading the submission against the code

These were found by extracting the submitted manuscript text
(`revision/submitted_manuscript_text.txt`) and checking each Methods assertion against the
implementation and against the measurements in Phases 6c and 6f-rev. All three quotes are
verbatim from the submission.

### C12a — The primary endpoint is defined as a quantity the code does not compute

**Submitted (Methods §D):** "LM-phase rotation rate (**rotation-only actions per mm traveled**
while the tip is proximal to the bifurcation), our primary measure".

**What the code computes** (`PROTOCOL.md`, `coronav/metrics.py`, the paper's own
`_lm_metrics()`):

```
f_rot_LM = Σ |Δdistance-to-target| over LM rotation steps
         / Σ |Δdistance-to-target| over all LM steps
```

That is a **dimensionless ratio bounded in [0, 1]**. "Actions per mm travelled" is a count
divided by a length — units of 1/mm, unbounded. These are different quantities, and the
difference is not cosmetic:

- the numerator is a **distance-change sum**, not an action count;
- the denominator is **change in distance to target**, not distance travelled. Phase 6c
  measured both on A1's left-main phase: median 28.2 mm travelled against 9.7 mm of
  distance-change. They are not interchangeable.

**Consequence for a defensive claim.** Results §A argues "Because the metric is per unit
distance, it is not an artifact of longer dwell in the left main." The conclusion happens to
survive — a ratio of two distance-change sums is indeed dwell-robust — but **the stated reason
is wrong**, because the metric is not a per-unit-distance rate. The corrected justification is
that numerator and denominator are both distance-change sums over the same phase, so episode
length cancels.

**Replacement definition for Methods:** the LM-phase rotation-movement fraction `f_rot_LM`, the
fraction of the wire's total change in distance-to-target during left-main traversal that
occurs on steps whose intended action is a rotation; dimensionless, in [0, 1]. This supersedes
the "rot/mm" naming noted at the end of this file, which addressed the name only and not the
definition.

### C12b — The meshes are not watertight, and two carry non-manifold edges

**Submitted (Methods §B):** each mesh was "verified as a single **watertight** component in
millimeter coordinates with inward normals".

**Measured (Phase 6f-rev):**

| Mesh | Boundary edges | Non-manifold edges |
|---|---|---|
| A1 VMR 0066 | 81 | 0 |
| A2 ASOCA Normal_12 | 9 | **6** |
| A3 ASOCA Normal_5 | 72 | **8** |

A surface with boundary edges is by definition not watertight. These are **deliberately open**
tubes — the ostia are open, and the pipeline expects that; `clip_left_coronary.py` prints
"Boundary edges (open ostia) … expected for open tube". The clipper's watertightness check
(`check_watertight_near_bif`) verifies only that no boundary edge lies **near the
bifurcation**, not that the mesh is globally closed. The Methods sentence promotes a local
check into a global property the geometry does not have, and omits the non-manifold edges on
A2 and A3 entirely.

**Replacement:** each mesh is a single connected open surface with inward-facing normals, open
at the ostium by construction; watertightness was verified in the bifurcation neighbourhood
only. A2 carries 6 non-manifold edges and A3 eight; A1 has none.

### C12c — "The only manipulated variable is the observation" is false on A2

**Submitted (Methods §C):** "Both arms of any comparison receive an identical prompt, so
**within a comparison the only manipulated variable is the observation**."

> **SUPERSEDED BY C20 (2026-09-16). This entry is wrong and is retained as the record of what
> we claimed.** It asserted that A2's arms did not share a step budget, citing `protocol.json`
> and the traces. Neither citation holds: `protocol.json` declares a single A2 value and
> contains no 62, and no A2 episode was truncated, so the traces confirm no budget at all. The
> sentence it qualified is correct as originally written, on A2 as well as A1.

A2's arms did not share a step budget: **wire-only 45 steps, overlay 62** (`protocol.json`,
confirmed in the traces). The observation was therefore not the only manipulated variable on
A2, and every one of the 25 overlay episodes exceeded the wire-only budget (C6, Phase 6h). The
sentence stands for A1 and must be qualified for A2.

**Artifacts.** `revision/submitted_manuscript_text.txt`;
`results/phase6f_mesh_provenance.{txt,json}`; `results/phase6c_report.txt`;
`results/phase6h_report.txt`. Phase 8.

---

## C13 — The primary test reverts to unpaired, and this reverses C2

**This entry reverses an earlier correction of ours and lands on more favourable numbers. It is
placed at the front of the entry rather than the end.**

**What C2 said.** That the submitted analysis used an unmatched Mann-Whitney on a seed-matched
design, that Reviewer 2 was right to object, and that the honest primary value for A1 rotation
was the paired **p = 0.0147** rather than the submitted **p = 0.0004**.

**What changed.** Adopting the matched analysis raised a question nobody had tested: *does the
matching carry any information?* Phase 7h established that the simulator seed does not propagate
to episode outcomes — variability is consistent with independent Bernoulli draws on both
anatomies. Phase 7i then measured the within-pair correlation directly:

| Anatomy | Endpoint | n | Pearson r [95% CI] | Efficiency (unpaired/paired) |
|---|---|---|---|---|
| A1 | f_rot_LM | 25 | −0.072 [−0.455, +0.332] | **0.9416** |
| A1 | worst-rank | 25 | −0.074 [−0.456, +0.330] | **0.9368** |
| A2 | f_rot_LM | 25 | **undefined** — wire-only constant at 0.0000 | — |
| A2 | steps | 25 | +0.112 [−0.296, +0.486] | 1.1115 |

On both primary endpoints pairing **increases** the contrast variance by roughly 6% while
costing 24 degrees of freedom. On A2's rotation endpoint the correlation cannot be computed at
all, because the wire-only arm is constant — pairing there is definitionally useless.

**Decision.** The **unpaired Mann-Whitney is primary** for f_rot_LM; the paired Wilcoxon is
reported alongside, with the measured correlation as the stated justification.

| Endpoint | Paired | Unpaired (primary) |
|---|---|---|
| A1 f_rot_LM | p = 0.0147 | **p = 0.000384** |
| A2 f_rot_LM | p = 0.000482 | **p = 2.95e-06** |

Navigation is unaffected in substance: the win ratio (5.60, 95% CI 2.43–17.97) and the log-rank
(p = 0.000623) are unpaired by construction and were always the proper analyses of that
endpoint.

**Why this is not the favourable result being selected after the fact.** Three safeguards,
offered so a reader can judge rather than take it on trust:

1. **The decision rule was written into the analysis script before the correlations were
   computed**, and is reproduced verbatim in `analysis/PRESPEC.md` and in the script's own
   output.
2. **Phase 7h supplies an independent mechanistic reason** to expect zero correlation, derived
   from repetition data that has nothing to do with the rotation endpoint.
3. **Both tests are reported in the paper regardless**, so nothing is hidden by the choice.

**The limit of the claim, stated rather than glossed.** At n = 25 the correlation CIs span
roughly [−0.46, +0.33] and do not exclude moderate positive correlation. What the data support
is "no evidence that seed-matching removes shared variance" — supported by point estimates near
zero and a measured efficiency below 1 — **not** that the correlation is zero.

**What C2 retains.** Its factual account of the submission is unchanged: the design *was*
seed-matched, the submission *did* justify it as "seed-matched, confound-free", and that
justification is withdrawn (C13 does not restore it). What C13 overturns is C2's conclusion
about which test should be primary.

**Artifacts.** `results/phase7h_report.txt`, `phase7h_dispersion.csv`,
`phase7i_report.txt`, `phase7i_pairing.csv`, `phase7i_worstrank_report.txt`,
`phase7i_worstrank_corr.csv`. Phases 7h, 7i.

---

## C14 — The paired Wilcoxon is restored as primary, superseding C13's switch

**This entry reverses C13, which was itself a reversal of C2, and it moves our headline p-value
in the direction LESS favourable to us: A1 returns from 0.000384 to 0.0147. That is stated at
the front of the entry rather than at the end.**

**What C13 did.** C13 measured the within-pair correlation, found it near zero, and made the
unpaired Mann-Whitney the primary test for f_rot_LM. It defended that against the charge of
motivated reasoning by pointing to a pre-committed decision rule, an independent mechanism from
Phase 7h, and the fact that both tests were reported regardless.

**Why that defence was insufficient.** It addressed the *order* in which we did things, not
whether the measurement could bear the weight placed on it. At n = 25:

| Anatomy | Endpoint | ρ | 95% CI |
|---|---|---|---|
| A1 | f_rot_LM | −0.072 | **[−0.455, +0.332]** |
| A1 | worst-rank | −0.074 | **[−0.456, +0.330]** |
| A3 | f_rot_LM | −0.097 | **[−0.489, +0.329]** |
| A2 | f_rot_LM | **undefined** | wire-only arm constant at 0.0000 |

An interval spanning −0.46 to +0.33 is consistent with moderate positive correlation. It
establishes that pairing is **not demonstrably helping** — not that pairing is unjustified.
Only the second claim would license abandoning the matched analysis, and the data do not
support it. A **38-fold** improvement in the headline p-value, on a test Reviewer 2
specifically asked for, cannot rest on an estimate that imprecise. C13 treated a wide interval
as if it were a point estimate.

**Decision.** The **paired Wilcoxon signed-rank is primary** for f_rot_LM. The unpaired
Mann-Whitney is reported alongside, with ρ and its CI, and with the conclusion stated under
both:

| Anatomy | PRIMARY paired Wilcoxon | Holm (2 members) | Alongside: unpaired | Same conclusion? |
|---|---|---|---|---|
| A1 | W = 73.0, n = 25, exact, **p = 0.0147** | **0.0147** | U = 496.0, p = 0.000384 | yes |
| A2 | W = 0.0, n = 25 (16 informative), approx, **p = 0.000482** | **0.000965** | U = 512.5, p = 2.95e-06 | yes |

Bonferroni: A1 0.0294, A2 0.000965.

**What is retained from C13, in full.** Phases 7h and 7i stand. The simulator seed genuinely
does not propagate to episode outcomes; the variability is consistent with independent binomial
draws; the submission's "seed-matched, confound-free" justification remains **withdrawn** (C13
does not restore it, and neither does C14). What changes is only which test is primary. The
matched test is now defended as the **conservative** analysis of the design actually run, not
as a confound control.

**ρ never appears without its CI.** Anywhere it is quoted — Methods, response letter, abstract,
`multiplicity_table.csv` — it carries its interval. A bare ρ = −0.072 invites precisely the
misreading that produced C13.

**Endpoint status.** f_rot_LM is a **secondary, mechanistic** endpoint. The paper's primary
claim is navigation degradation: A1's worst-rank imputation (p = 0.00206), win ratio (5.60,
95% CI 2.43–17.97) and log-rank (p = 0.000623), and A2's complete separation. None of those is
a paired-versus-unpaired question — the win ratio and log-rank are unpaired by construction —
so **none of this correction touches the paper's primary result**, and no draft may imply the
paper's strength rests on the rotation p-value.

**Consequence for the design-sensitivity figure.** The minimum-detectable-effect figure was
computed for the paired test, which is primary again, so it is no longer superseded and is
restored. It was **recomputed rather than reinstated**, because the bare-call defect recorded in
`results/LOG.md` touched the power simulation at `phase4_primary.py:143`. Under the
PRESPEC-compliant call the smallest detectable paired shift is **0.0292 f_rot_LM** against an
observed Hodges–Lehmann shift of **+0.0285** — **0.98×**, unchanged at reporting precision. One
caveat surfaced by the fix and reported rather than buried: **100% of simulated samples fall to
the normal approximation** because resampling with replacement induces tied absolute
differences, while the test actually run on the observed data was **exact**. The simulation
therefore calibrates a marginally different test than the one used; this is inherent to
bootstrap MDE, not a defect, and it is stated in Methods.

**Artifacts.** `results/phase5_report.txt`, `multiplicity_table.csv`, `phase6_report.txt`,
`phase4_report.txt`, `phase4_tests.csv`; `analysis/phase5_multiplicity.py`,
`phase6_leave_a3_out.py`, `phase4_primary.py`. Supersedes **C13**, which is retained above as
the record of what we did and why.

---

## C15 — The rotation limitation is stated by the Hodges–Lehmann interval, not by a simulated MDE

**What changes.** The sensitivity limitation on the rotation endpoint was led by a simulated
minimum detectable effect: "the observed shift is 0.98× the minimum effect detectable at n = 25
with 80% power." **That figure is demoted and no longer carries the limitation.**

**Why.** We recomputed the simulation under the PRESPEC-compliant Wilcoxon call (C14) and, in
doing so, surfaced a defect in what it measures. Bootstrap resampling with replacement from 25
observed differences induces tied absolute values that the observed sample does not have, so
**100% of simulated replicates fall to the normal approximation, while the test actually run on
the observed data was exact.** The simulation therefore calibrates a different test than the one
we report. It is not wrong so much as not about our test — and a damaging admission should not
rest on a number with that defect.

**What replaces it.** The Hodges–Lehmann estimate and its distribution-free confidence interval,
which come from the test we actually ran and require no resampling at all:

> **+0.0285 f_rot_LM, 95% CI [+0.0068, +0.0440].** The lower bound is roughly a **quarter** of
> the point estimate.

That is the exact statement of the limitation: **the effect is detected, and its magnitude is
poorly constrained at n = 25.** It is a stronger and more honest admission than the MDE ratio,
not a weaker one — it gives the reader the range of effects compatible with our data rather than
a single pass/fail comparison against a power threshold.

**Where it applies.** `manuscript/methods.md` §G (leads with the interval; retains one
parenthesised secondary sentence for the simulated MDE, carrying its tie caveat, so the figure
stays auditable), `manuscript/response_letter.md` §1.1, `manuscript/title_abstract.md` slot 4,
and `results/reviewer_response.csv`. The MDE sentence is **dropped** from the letter, the
abstract and the response matrix.

**A2 needs no equivalent change.** Its rotation limitation never carried an MDE figure; its
magnitude statement is already its own Hodges–Lehmann interval, **+0.0498 [+0.0227, +0.0722]**.

**What this does NOT change, stated so the entry is not read as broader than it is.** C2 and C4
are dated entries and are left as the record of what we said at the time, including their
MDE-based phrasing. C4 justified demoting rotation to a mechanistic secondary endpoint partly on
"p = 0.0147 at 0.98× its own MDE". **That decision stands**, because it rested independently and
sufficiently on the navigation endpoint being large and robust — win ratio 5.60 (95% CI
2.43–17.97), log-rank p = 0.000623 — and because the HL interval supports the same reading of
the rotation endpoint as the MDE ratio did: detected, imprecise. Only the number used to say so
has changed.

**Artifacts.** `results/phase4_report.txt`, `results/phase4_tests.csv` (both figures remain
computed and published), `analysis/phase4_primary.py`.

---

## C16 — The open-loop floor was quoted from one draw at the top of its own distribution

**Original.** The always-advance baseline on A1 was quoted as **17/25 = 68%** from its single
Phase 7a run, and later as a range "44–68% across six runs" with 68% still carried as the
standalone single-run figure.

**What is actually the case.** The same policy, speed, seeds and budget were drawn seven times
across Phases 7a, 7g and 7c. Phase 7h showed the across-repetition variance is consistent with
independent binomial draws, so pooling them is the defensible estimate:

| Anatomy | Draws | Pooled | Wilson 95% CI | Range across draws |
|---|---|---|---|---|
| A1 | 7 | **99/175 = 56.6%** | [49.2, 63.7] | 44–68% |
| A2 | 7 | **124/175 = 70.9%** | [63.7, 77.1] | 52–80% |

**68% was the highest of A1's seven draws, observed once.** Two further A2 smoke-test draws at
this speed (15/25, 17/25) have no surviving artifact and are excluded; including them would give
69.3%.

**Direction of the retired figure, stated because it matters.** A higher floor made the task look
easier than it is — favourable to the limitation we were writing about success rate as a weak
discriminator — and made the operator's margin over the blind policy look smaller, i.e.
unfavourable to the operator comparison. The pooled figure moves both the other way. How the
operator comparison is made at all is changed separately by C17.

**Where it applies.** The pooled rate with its range replaces the single draw wherever the floor
is quoted: the manuscript abstract and Results, Methods, response letter §1.3, §1.7 and R1.1,
`manuscript/related_work.md`, and `results/reviewer_response.csv`.

**Artifacts.** `analysis/phase7c_pool_default.py`; `results/phase7c_pooled_default.csv`,
`results/phase7c_pooled_default_report.txt`.

---

## C17 — 35 mm/s was described as the harness's default advance speed; it is not the operator's speed

**Original.** PRESPEC's 7c rule, the Phase 7 baseline docstrings, the manifest and the drafts
described the open-loop baselines' 35 mm/s as "the harness's own default advance speed"
(`PROXIMITY_GATE_ADV_DEFAULT`), and the author's instructions relied on that description, including
the premise that both operator arms "ran at the harness default". The text was approved by the
author and written by the analyst; the error is ours jointly.

**What is actually the case.** `PROXIMITY_GATE_ADV_DEFAULT = 35.0` is used in exactly one place,
`run_coronary.py:708`: it is the translation **substituted when the proximity gate suppresses a
rotate intent**. On every other step the operator chooses its own translation. From the logged
traces:

| Arm | Median advance | Mean advance | Steps at 35 mm/s | Most common value |
|---|---|---|---|---|
| A1 wire-only | 10 mm/s | 18.8 | 1.3% | 10 mm/s on 39.4% of steps |
| A1 overlay | 10 mm/s | 16.0 | 0.8% | 10 mm/s on 49.2% |
| A2 wire-only | 10 mm/s | 8.0 | 0.0% | 10 mm/s on 55.9%, 5 mm/s on 35.5% |
| A2 overlay | 5 mm/s | 6.8 | 0.0% | 5 mm/s on 49.0% |

The operator advances slowly, and that is a finding in its own right.

**Why it matters.** Phase 7c showed blind success varies jointly with advance speed and geometry.
A floor measured at 35 mm/s is therefore not a speed-matched calibration for an operator that
navigated mostly at 5–10 mm/s. The nearest tested speed, 15 mm/s, gives **61.3% [50.0, 71.5]** on
A1 and **100% [95.1, 100]** on A2.

**What replaces it (author decision, option (a)).** The pooled 35 mm/s floor is reported with its
rationale corrected — a fixed speed chosen in advance, not the harness default — alongside the
operator's own advance distribution, and the 15 mm/s figures are given as the nearest
speed-matched comparison. The conclusion is stated descriptively: **the operator's single
wire-only draw clears the speed-matched blind policy on A1 and does not on A2**, where a blind
policy reaches 100%. **No margin is claimed and no test is run between operator and baseline.**

**The asymmetry, stated rather than left implicit.** The floor is pooled over repeats; the
operator rates are single draws and carry roughly the run-to-run noise measured in those repeats
(a 20 pp range on A1 and 28 pp on A2 for a fixed policy). That is why no success-rate claim is
made and why the primary endpoint is steps-based.

**What does not change.** The 35 mm/s pre-commitment was honoured — the value was fixed before
the sweep ran — only its stated rationale was wrong. The overlay-versus-wire-only contrast is
unaffected, because both arms chose their own speeds under identical harness rules, and neither
the navigation-degradation result nor the rotation endpoint uses the floor. Because blind success
depends on speed and geometry together, **baseline calibration is mandatory for anyone using
CoroNav**, and Methods says so.

**Artifacts.** `analysis/phase7_operator_speed.py`; `results/phase7_operator_speed.csv`,
`results/phase7_operator_speed_distribution.csv`; `results/phase7c_speed_sweep.csv`.

---

## C18 — The oracle was framed as a ceiling; it is not one

**Original.** PRESPEC's 7d amendment stated that the oracle "exists to give the reader a
ceiling" against the open-loop floor; the drafts referred to a "centreline oracle" and reserved a
slot for an oracle range in the calibration sentence.

**What the measurement shows.** Best single constant rotation at 35 mm/s — the deployable figure
fixed in advance — is **64.0% [44.5, 79.8]** on A1 and **80.0% [60.9, 91.1]** on A2. Neither exceeds
the blind always-advance policy's own best draw at the same speed (68% and 80%). On A1 the spread
across the seven rotation values (12 pp) is below the 20 pp run-to-run floor, so no rotation is
demonstrably better than another. Union reachability is 100% on both anatomies and is inflated by
selection over noise; it is reported only as such.

**What replaces it.** The oracle is reported as what it is: a reachability probe over
constant-rotation policies at one speed, which does not raise success above the blind policy. The
ceiling framing is withdrawn everywhere, including PRESPEC (amendment 2026-09-15). The pre-committed
two-figure rule is unaffected and was followed.

**Artifacts.** `analysis/phase7d_oracle.py`; `results/phase7d_oracle.csv`,
`results/phase7d_report.txt`.

---

## C19 — The biplane arms were not budget-matched, and two episodes ended for an unrecorded reason

**Original claim.** Results §E of the submission: "Across a four-arm, seed-matched comparison at
120-step budget, no biplane effect reached significance", with the apparent benefit shrinking
"from −6.3 pp (unmatched seeds) to −2.2 pp (seed-matched) to −0.6 pp (seed- and budget-matched,
final)". The response letter repeated the budget-matched description.

**What the traces show.** Episode lengths, read from the logged traces:

| Arm | Episodes | Successes | Success episode length | Non-terminal episode length |
|---|---|---|---|---|
| Monoplane wire-only | 10 | 6 | 77–83 steps | 120 (all four, truncated at budget) |
| Monoplane overlay | 10 | 5 | 81–90 | 120 (all five, truncated) |
| Biplane wire-only | 10 | 8 | 35–40 | **30 and 20** (arm's longest: 40) |
| Biplane overlay | 10 | 9 | 40–47 | **48** (arm's longest: 48) |

The monoplane arms behave as a 120-step budget implies: every failure runs to 120 and records
`truncation: true`. The biplane arms do not. Their successes finish in roughly half the steps, and
the three arms ran to three different maximum lengths: **120, 40 and 48**.

**Two episodes cannot be budget truncations; the third can.** `run_biplane.py` imports `build_env`
from `run_coronary.py`, where the only truncation criterion is `eve.truncation.MaxSteps(n_steps)` —
a single fixed step count per arm. The biplane overlay episode that stopped at 48 steps is that
arm's longest, so it is consistent with truncation at 48. The two biplane wire-only episodes that
stopped at **30 and 20 steps**, 82.8 mm and 81.9 mm from target, are **below their own arm's
longest episode of 40**, which one fixed count cannot produce. The episode loop breaks only on
`terminated or truncated`, and the biplane trace schema records `terminal` but **not**
`truncation`, so the traces cannot say why those two ended. Their blocks are contiguous from
step 1 and in order, with no duplicates, so they are not the partial episodes an
interrupted-and-resumed run would leave.

**What we can and cannot say.** We can say the arms did not run under a common effective budget —
120 steps against 40 and 48 — and that two wire-only episodes ended below even their own arm's
maximum. We cannot say why those two ended, from these logs.

*An earlier draft of this entry said three episodes ended for an unrecorded reason, over a range of
82–113 mm. That was wrong on both counts: the 48-step episode is explicable as a truncation, and
113.0 mm was its final distance, not an early stop's. Corrected here rather than quietly amended.*

**Consequences.**

1. **"Seed- and budget-matched" is withdrawn** for the biplane comparison, in the manuscript, the
   response letter and the supplementary tables.
2. **Biplane success counts are not comparable** with monoplane success counts (8/10 and 9/10
   against 6/10 and 5/10), because the arms' effective budgets differ by a factor of about three
   and two biplane episodes ended below their own arm's maximum for an unrecorded reason. No
   success comparison is drawn between them.
3. **The f_rot_LM contrast is retained but as exploratory only**, with the caveat attached. Both
   biplane-versus-monoplane tests remain non-significant.
4. **Nothing confirmatory is affected.** The biplane study uses its own seeds and arms, and enters
   no confirmatory family, no primary or secondary endpoint, and no calibration figure.

**How it was found.** Building the supplementary table for Reviewer 2's comment 6 required a
per-arm budget, so the ESM script verified budgets from the traces instead of taking them from the
run directory names. The mismatch surfaced immediately. The directory is named
`biplane_120steps`; the runner's own default is 60.

**Artifacts.** `analysis/esm_tables.py`; `results/esm1_arm_descriptives.csv`,
`results/esm1_nonterminal_episodes.csv`, `results/esm1_supplementary_tables.md`.

---

## C20 — The A2 "unequal step budgets" claim is unsupported, and is withdrawn

**This entry reverses a correction of ours and lands on a conclusion more favourable to the
paper. It is therefore set out in full evidence rather than in summary.**

**What we claimed.** That A2 ran wire-only under a 45-step budget and overlay under 62; that the
25/25-versus-25/25 success parity was "an artefact of unequal budgets"; and that the Methods
sentence "within a comparison the only manipulated variable is the observation" was false on A2
(C6, C12c, Phase 6h, response letter §1.4).

**Why it is unsupported.** Four independent checks, none of which the claim survives:

1. **Nothing records it.** `run_asoca.py` keeps the step limit in `stats["n_steps_limit"]`, but
   its `write_summary` never emits it. Both A2 summaries record only "Budget : 2 retractions per
   episode" — the *retraction* budget, a different quantity.
2. **The traces cannot reveal it.** Both A2 arms show 25/25 terminal rows and **zero** truncation
   rows. No episode hit any limit, so no limit is observable in the data.
3. **The cited source says otherwise.** `benchmarks/protocol.json` declares one A2 value,
   `step_budget: 45`, and contains no 62 anywhere. `analysis/phase6h_a2_steps.py:48` hardcoded
   `BUDGET = {"wire_only": 45, "overlay": 62}` under the comment `# benchmarks/protocol.json`.
4. **The harness gives both arms the same limit.** `ANATOMY_PARAMS["normal12"]` sets
   `n_steps = 120`, and the script's own documented full-run invocation passes no `--steps`
   override for either mode.

**What 45 and 62 actually are.** The longest episode in each arm (wire-only 37–45, overlay
50–62). Reading them as budgets is the same error class as C19, in the opposite direction: there
we read a budget off a directory name, here off the data.

**What this changes.** The success-parity withdrawal is withdrawn: both arms ran under a common
limit, nothing was truncated, no step count is censored, and the success counts are comparable.
C12c is superseded — the observation was the only manipulated variable on A2 as well as A1. The
steps-to-target result is untouched: it never depended on the budget.

**What it does not change, and must be said.** We cannot *prove* what limit was passed, because
it was never persisted. The evidence points one way and no artifact points the other, but the
honest statement is that the limit is unrecorded. That is a reproducibility gap in the original
data collection, and the fix for future runs is to write `n_steps_limit` into the summary.

**Artifacts.** `D:\steve\pilot\run_asoca.py` (ANATOMY_PARAMS, usage block, `write_summary`);
`benchmarks/protocol.json`; both A2 `summary.txt` files; the A2 traces;
`analysis/phase6h_a2_steps.py`.

---

## C21 — The reported simulation timestep is wrong, and the baselines ran at a different one

**Submitted (Methods).** "Simulation timestep 0.006 s."

**What the code does.** Every VLM arm overrides the class default: `run_ablation.py:628` (A1
confirmatory arms), `run_asoca.py:431` (A2), and `run_coronary.py:419` all construct
`CoronaryBeamAdapter(..., dt_simulation=0.001, ...)`. **The VLM arms ran at 0.001 s.** The 0.006
figure traces to `extract_paper_data.py:478`, which read `sofabeamadapter.py` L16 — the library
default — and so could not see the call-site override.

**The second half, which matters more.** Every Phase-7 baseline, sweep, probe and replay sets
`DT_SIMULATION = 0.006` (`phase7_always_advance.py:63`, `7a:74`, `7c:96`, `7e:83`, `7g:67`), on
the strength of a comment asserting "the VLM arms used dt_simulation=0.006". They did not. So the
blind floor, the speed sweep, the rotation probe, the non-determinism measurement and the solver
replay were all run at a timestep six times larger than the arms they calibrate.

**What that does and does not do.** `monoplanestatic.py:81` sets `duration = 1/image_frequency`
= 0.1333 s and calls `simulation.step(action, duration)`; `sofabeamadapter.step` runs
`int(duration/dt)` sub-steps, each advancing insertion by `action x dt`. Net commanded
displacement per environment step is therefore `action x duration` either way and differs by
about 0.9% (133 sub-steps x 0.001 against 22 x 0.006). What differs is contact resolution: the
constraint solver is invoked six times less often per step in the baselines. The solver
non-convergence percentages, which are measured by replaying VLM action sequences, were measured
under the coarser setting.

**What changes.** `cfg.timestep` becomes 0.001 and is sourced to a call site rather than a
library default; Figure 1's parameter line is corrected; a new key records the baseline timestep;
and Limitations states the mismatch explicitly. The baseline figures are retained, because the
policy they execute is unchanged and the commanded motion is preserved, but they are no longer
described as sharing the arms' physics.

**Not corrected, deliberately.** `PROTOCOL.md` records 0.006 and is frozen evidence; it is cited
here rather than edited. `benchmarks/protocol.json` and `coronav/env.py` also carry 0.006, which
means **the released environment does not reproduce the study arms' timestep** — flagged for the
authors rather than changed unilaterally, since altering it changes the public environment's
behaviour.

**Artifacts.** `run_ablation.py:628`; `run_asoca.py:431`; `run_coronary.py:419`;
`coronary_fixture/coronary_sim.py:39`; `sofabeamadapter.py:16,75,81`; `monoplanestatic.py:81`;
`extract_paper_data.py:478`; the Phase-7 scripts named above.

---

## C22 — The open-loop floor is 100%, not 56.6% and 70.9%, and the calibration argument is withdrawn

**This is the largest correction in this record. It removes a finding, not a caveat, and the
figures it retires were favourable to us while the corrected one is not.**

**What we claimed.** That a blind always-advance policy reached target in **56.6%** of A1 episodes
and **70.9%** of A2 episodes; that blind success "varies jointly with advance speed and geometry";
that success rate was therefore "a weak discriminator" which the operator nonetheless cleared on
A1; and that "blind baselines must be speed-matched before they calibrate anything". This was the
answer to Reviewer 1's mandatory request for a baseline, and it ran through the abstract, Results
§3.3, Table 2, Fig. 4, Methods §G and response-letter §1.7, §1.8 and R1.1.

**Why it was wrong.** Every one of those figures was measured at a simulation timestep of
0.006 s. **No study arm ever ran at 0.006 s** (C21). Re-measured at the arms' own 0.001 s, with
identical seeds, budgets, policy and success criterion, the same policy reaches target in
**75/75 episodes on A1 and 75/75 on A2 — 100% of both** (Wilson 95% CI 95.1–100.0), across three
repetitions of the full seed list.

| | dt = 0.006 (retired) | dt = 0.001 (arms' physics) | shift | prior noise band |
|---|---|---|---|---|
| A1 | 56.6% | **100.0%** | +43.4 pp | 20.0 pp |
| A2 | 70.9% | **100.0%** | +29.1 pp | 28.0 pp |

Both shifts exceed the run-to-run range previously measured for a fixed policy, so this is not
sampling noise. It was checked for degeneracy before being believed: every A1 episode takes
exactly 26 steps and finishes 4.58–4.71 mm from target, against a 27-step median at 0.006; every
A2 episode takes exactly 11 steps and finishes 1.76–1.91 mm out. Nothing terminates early and
nothing reaches budget. Per-sub-step insertion is the commanded speed times the timestep, so at
0.006 s the wire advanced six times further between contact resolutions — precisely the condition
under which a blind wire catches instead of tracking the lumen.

**What it changes, and how the paper is reframed rather than patched.** The task, as configured,
is solvable open-loop on both patient-derived anatomies. That is now stated plainly and early, as
a property we measured ourselves. It is not a caveat but the **control condition**: because the
task requires no visual information, any degradation observed when visual information is added is
attributable to how the model uses the image rather than to task difficulty. The result reads that
a blind policy completes the task every time, a VLM operator succeeds 20/25 with a wire-only view
and 13/25 with overlay, and is reliably slower with overlay — more visual information made it
worse. The environment is described as a controlled instrument for studying visual behaviour, and
**no difficulty claim is made anywhere**.

**What is withdrawn outright.** The speed-dependence finding, the "weak discriminator" framing,
the claim that baselines must be speed-matched, the operator-clears-the-floor-on-A1 comparison,
and the constant-rotation reachability probe. The probe existed to supply a ceiling and per-seed
reachability; an open-loop policy succeeding on 25/25 seeds in both anatomies establishes both, so
it is removed from Results and its script and artifacts are retained marked superseded. Table 2 and
Fig. 4 are deleted.

**Scope of the retirement, enforced mechanically.** 105 manifest keys measured at 0.006 s are
marked `[SUPERSEDED` in their descriptions rather than deleted, because their values are the true
record of what was measured. `analysis/build_manuscript.py` now **fails** if any manuscript source
references such a key, so "no superseded value reaches the text" is a build guarantee rather than
an intention. The speed sweep and the oracle were costed for re-measurement (12 and 14 shards,
about 2.5 hours, simulator-only) and deliberately not re-run: the scope of this revision closes
here.

**Not re-run, and what rests on it instead.** The non-determinism measurement (7g) also ran at
0.006 s and is not repeated. The claim that the simulator seed does not propagate to outcomes now
rests on the within-pair correlation of the **operator arms themselves** — ρ = −0.072 (95% CI
−0.455 to +0.332) on A1 — which was computed from those arms' own traces at 0.001 s and is
unaffected. Any Methods sentence asserting environment non-determinism on the basis of 7g is
removed. Note that the 0.001 s open-loop runs are perfectly concordant across repetitions, but
with success saturated at 100% that design cannot distinguish a deterministic environment from a
saturated one, so no determinism claim is made either.

**What is untouched.** The primary result. Overlay versus wire-only compares two operator arms
that both ran at 0.001 s, and no baseline enters it. Navigation degradation on A1 (worst-rank
p = 0.00206; win ratio 5.60, 95% CI 2.43–17.97; log-rank p = 0.000623), complete separation on A2
(Hodges–Lehmann +14.5 steps, p = 1.25e-05), and the rotation endpoint are all unchanged.

**Artifacts.** `analysis/phase7j_floor_dt001.py`; `results/baselines/floor_dt001_a1.json`,
`floor_dt001_a2.json`, `phase7j_report.txt`; the superseded `phase7c_*`, `phase7d_*`,
`phase7g_*` and `phase7e_*` artifacts, retained and marked.

---

## C23 — The A2 proximity gate was 15 mm, not 25 mm

*Recorded 2026-10-16, after submission of CMPB-D-26-07590, while recovering the original records
into `artifacts/`. To be corrected in the manuscript at revision.*

**Submitted (Methods §2.3).** "When the tip was within 25 mm of target and closing, a rotate
intent was replaced by an advance of 35 mm/s." One threshold is given for both anatomies.

**What the code does.** The threshold is anatomy-specific. A1 used 25 mm
(`run_ablation.py:67`, `PROXIMITY_GATE_DIST_MM = 25.0`). A2 used **15 mm**
(`run_asoca.py:120`, `ANATOMY_PARAMS["normal12"]["proximity_gate_mm"] = 15.0`). This was not a
drift: it was pre-registered (`PREREGISTRATION.txt:110`, "Normal_12: gate=15mm, LM~17mm"), and
both A2 run summaries print "suppress rotation when dist < 15mm".

**Why it did not change any action.** The gate never suppressed a rotation in either A2 arm
(`gate_suppressed_rotation` is false on all 2426 A2 rows). A 25 mm gate could have acted only on
steps with the tip between 15 and 25 mm and closing. There are 10 such steps (wire-only, 9
episodes) and 0 (overlay), and **none carries a rotate intent**. So a 25 mm gate would have
replaced no action.

**What it did change.** The operator saw the threshold. The A2 system prompt states it
("under 15mm, do NOT rotate", `run_asoca.py:233-235`). The per-step "PROXIMITY GATE ACTIVE"
line (`run_asoca.py:295-298`) appears only below 15 mm, so under a 25 mm gate it would also
have appeared on those 10 wire-only steps. The A2 operator therefore saw a slightly different
prompt from the one the Methods describe. Whether that altered its choices cannot be determined
from the logs, because decoding is unseeded and no 25 mm A2 arm exists.

**What changes.** At revision, §2.3 should read, e.g., "within 25 mm (A1) or 15 mm (A2) of
target and closing", with the per-anatomy value sourced to the harness. `benchmarks/protocol.json`
in the public repository gives 25 mm for A2 and should follow (an author decision, not yet made;
concordance U14).

**What it does not change.** Every reported number. The gate never fired differently from how
a 25 mm gate would have.

**Artifacts.** `artifacts/harness/pilot/run_asoca.py:120,233-235,280-298`;
`artifacts/harness/pilot/run_ablation.py:67`; `artifacts/harness/pilot/PREREGISTRATION.txt:110`;
both A2 `summary.txt`; the A2 traces (`dist_obs_at_call`, `dist_trend`, `intended_direction`,
`gate_active`, `gate_suppressed_rotation`).

---

## C24 — The A2 open-loop control did not use the operator arms' step limit

*Recorded 2026-10-16. To be corrected in the manuscript at revision.*

**Submitted (Methods §2.4).** The open-loop policy "was run over the same seeds and the same step
limits as the operator arms".

**What the code does.** The seeds are the same. The A1 step limit is the same (60). The A2 step
limit is **45** (`analysis/phase7j_floor_dt001.py:66`; `floor_dt001_a2.json` records
`"budget": 45`), not the operator arms' 120 (C20). The 45 is the A2 value
`benchmarks/protocol.json` then declared, which C20 shows to be the longest observed wire-only
episode rather than a budget. It entered the baselines through Phase 7a
(`phase7a_always_advance_a2a3.py:11-12,60`) and Phase 7g (`phase7g_nondeterminism_floor.py:62`).
Phase 7j copied 7g's configuration deliberately, so that the timestep would be the only
difference ("Identical to Phase 7g. Do not vary these", `phase7j_floor_dt001.py:51`). The 45 was
therefore kept on purpose, but the §2.4 sentence describing it is wrong.

**Why it does not matter for the result.** All 75 A2 open-loop episodes reached target at step 11
in every repetition, far inside either limit. Nothing was truncated, so the open-loop result
(75/75) is the same under 45 and under 120. A re-run of the unedited script in the original
environment on 2026-10-16 again gave 75/75 at step 11.

**What changes.** At revision, §2.4 should say the A2 open-loop limit was 45 steps and that no
episode approached it, or the A2 floor should be re-run at 120. The outcome cannot differ.

**Artifacts.** `analysis/phase7j_floor_dt001.py:51,58,66`; `results/baselines/floor_dt001_a2.json`;
`results/baselines/phase7j_report.txt`.

---

## C25 — Three exploratory prompt-variant episodes that reached target on their final step are counted as failures

*Recorded 2026-10-16. Affects Supplementary Table S1 only.*

**Submitted (Methods §2.5).** Success is "the tip reaching within 5 mm of target within the step
limit".

**What the analysis does.** The scripts score success as "last row terminal **and not**
truncated" (`phase3_selection_bias.py:66`, `phase5_multiplicity.py:125`, `phase6h_a2_steps.py:75`).
stEVE sets both flags when the target is reached on the last allowed step. Such an episode
met the §2.5 definition but is scored as a failure.

**Where it occurs.** In no confirmatory arm: no A1 or A2 episode has both flags set. It
occurs three times in the exploratory prompt variant V2, all at step 60 of 60:
`v2_neutral/wire_only` episode 7 (final distance 4.55 mm), and `v2_neutral/overlay` episodes 7
(4.37 mm) and 8 (4.58 mm).

**What changes.** Supplementary Table S1 reports V2 success as 3/10 (wire-only) and 2/10
(overlay). Under §2.5 these are **4/10 and 4/10**. The V2 `f_rot_LM` values and the V2 test
(p = 0.371) do not use success and are unchanged. At revision, Table S1 should be corrected,
or its success column defined as "reached target before the final step".

**What it does not change.** Any main-text number. The confirmatory analyses are unaffected
because the case never arises in them.

**Artifacts.** `artifacts/traces/ablation_prompt_robustness/v2_neutral/{wire_only,overlay}/trace.jsonl`;
`results/esm1_arm_descriptives.csv`; the three scripts named above.

---

## Numbering note

There is no C10. The number was never assigned to an entry; the gap is an artefact of drafting
and conceals nothing.

---

## Naming correction (not an error, but a change of terminology)

The metric the manuscript calls "rot/mm" is a **dimensionless ratio** of distances, not a
per-millimetre rate. It is renamed `f_rot_LM` ("LM-phase rotation-movement fraction"). The
quantity is unchanged; only the name and its stated units change.
