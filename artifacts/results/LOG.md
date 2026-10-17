# Revision analysis log — `revision-cbm`

Running record of decisions, surprises, and corrections. Newest phase at the bottom.

---

## Phase 0 — inventory (2026-09-11)

### Where the data is

The paper's raw logs are **not** in this repository. `D:\coronav\runs\` is empty; the public
repo ships code, the A1 mesh, and frozen protocol seeds only. The episode logs are at
`D:\steve\pilot\runs\` (71 `trace.jsonl` files, ~75 MB). `D:\steve` is **not** a git
repository, so the logs are unversioned. They are treated as read-only inputs.

### Schema

Three incompatible schema generations: mono (current, 38–39 keys), biplane
(`is_rotate_step` / `tip_target_dist_after`, no `truncation`, no `parsed_action`), and an
early 2026-05-30 pilot schema with no `seed`. Only the mono and biplane generations are used.

Fields that do **not** exist and must be derived: success flag, steps-to-target, step budget.
Fields missing from A1 arms specifically: `anatomy`. Fields present only in the ablation arms:
`prompt_variant`.

### Counts and exclusions

A1 25/25 per arm (success 20/25 wire_only, 13/25 overlay — reproduces the paper's Table I).
A2 25/25 per arm. A3 wire_only 25, overlay **23** (seeds 4254, 4265 fully API-failed).
Contrast arm: 15 episodes, 8 fully API-failed → n=7. V3 overlay: 5 of 10 excluded.
All recorded exclusion reasons are transient API failure, not navigation outcome.

### Frames

28,209 PNGs / 3.2 GB retained overall — but **the A1 primary arms retain none** and have no
`frame_path` field at all. A2, A3, contrast and mono120 have per-step frames (verified to
exist on disk). Biplane has none. Phase 9 on A1 therefore requires re-rendering, which is
simulator-only and costs nothing.

### Environment

Python 3.12.10 with numpy 2.4.2, scipy 1.17.1, statsmodels 0.14.6, pandas 3.0.1,
matplotlib 3.11.1, Pillow 12.3.0. **lifelines absent** → Phase 3 time-to-event will use
statsmodels. `pyvista` and `eve` absent → Phases 7 and 9 need the SOFA conda env
(`D:\conda\envs\steve`, Python 3.8, `D:\steve\activate_steve.ps1`); `conda` is not on PATH
in the analysis shell.

---

## Corrections to my own Phase 0 report (2026-09-11)

Two findings I reported were **wrong** and are retracted here in full.

### RETRACTED — "the primary metric is misaligned by one step"

I initially observed `dist_delta[k] == tip_target_dist[k] − tip_target_dist[k−1]` and
concluded `dist_delta` measured the *previous* step's action, which would have meant the
primary endpoint mispaired actions with movement on all three anatomies.

**This was an error.** It assumed `tip_target_dist` is the pre-action distance. The
generating source (`run_coronary.py:661-728,791`; `run_asoca.py:734,798-799`) assigns
`tip_target_dist = dist_post`, the **post**-action distance, with the pre-action value stored
separately as `dist_obs_at_call`. Therefore
`dist_delta[k] = tip_target_dist[k] − dist_obs_at_call[k]` is exactly step k's own movement.

Verified on every row of all six canonical arms (1277/1277, 1448/1448, 1026/1026, 1400/1400,
3438/3438, 3750/3750). **The paper's metric was correctly aligned.** No correction is applied,
and no "corrected variant" is pre-specified.

### RETRACTED — "final distance-to-target is not recorded"

Follows from the same error. Because `tip_target_dist` is post-action, the last row of a
truncated episode **is** the true final distance at budget exhaustion. Phase 3's worst-rank
imputation can use it directly, with no off-by-one caveat. Phase 3 is unblocked.

### STANDS — PAPER_DATA.md provenance statement is inaccurate

`PAPER_DATA.md` states of the A1 v1 arms: "All episodes have api_ok=True, parse_ok=True.
Zero exclusions in either arm." A1 wire_only **ep21 (seed 5221) has 17 consecutive failed
rows, steps 22–38**. No episode was dropped (43 valid rows remain, so the episode is
retained as included-partial), but the statement as written is false, and ep21 is a
truncated failure episode. Overlay arm genuinely has zero failed rows.

### NEW — `tip_branch_obs` convention differs between paper and public repo

The paper's harness classifies the branch from the **pre-action** tip position
(`run_coronary.py:663-664`, `tip_obs`). The published benchmark's port classifies from the
**post-action** tip (`coronav/env.py:314`, `tip_after`). LM-phase membership — and therefore
`f_rot_LM` — is not identical between the two implementations. The paper's convention is
locked for this revision; the divergence is a genuine reproduction discrepancy and belongs in
the limitations and in the reproducibility pack.

---

## Phase 1 — pre-specification (2026-09-11)

`analysis/PRESPEC.md` written and committed before any Phase 3+ analysis.

Decisions taken (user-directed unless noted):

1. **Repo/branch:** `revision-cbm` off `master` in `D:\coronav`; raw logs referenced by
   absolute path and never modified.
2. **Failure ranking for worst-rank imputation:** last recorded `tip_target_dist`. Originally
   chosen as an off-by-one substitute; after the retraction above it is the exact final
   distance, so the caveat is dropped.
3. **Metric alignment:** no correction applied — the premise for one dissolved. Supersedes the
   earlier instruction to pre-specify a corrected variant as primary, because that instruction
   rested on my incorrect finding.
4. **Survival tooling:** statsmodels, no new dependency.
5. **Metric renamed** `rot/mm` → `f_rot_LM`. The manuscript's name implied a per-millimetre
   rate; the quantity is a dimensionless ratio. Quantity unchanged.
6. **Paired test pre-specified for the confirmatory family** in all three anatomies
   (A1 n=25, A2 n=25, A3 n=23 pairs), with Mann–Whitney — the original manuscript's test —
   retained as an unadjusted sensitivity line.

### Repo housekeeping

`.gitignore` ignored `results/`, which would have silently excluded every artifact this
revision is required to produce (`multiplicity_table.csv`, `manifest.csv`, `seeds.txt`,
`reviewer_response.csv`, this log). The `results/` rule was removed on this branch. `*.jsonl`
stays ignored so raw traces are never committed by accident.

### Open blocker

**The reviewers' comments are not on disk.** Searched `D:\coronav`, `D:\steve`,
`D:\coronav_manuscript_work`, and the user profile directories; only
`CoroNav_TMRB_manuscript_ORIGINAL_BACKUP.docx` was found. **Phase 13
(`results/reviewer_response.csv`) cannot be written without the actual review text.** Phases
3–12 do not depend on it.

---

## Phase 3 — steps-to-target selection bias (2026-09-11)

Script `analysis/phase3_selection_bias.py`; output `results/phase3_report.txt`,
`phase3_tests.csv`, `phase3_episodes_a1.csv`. All 50 A1 episodes, seed 20260911.

**All three bias-corrected analyses agree in direction: wire_only outperforms overlay.**

Reviewer 2's objection (comment 3) was correct. The successes-only comparison conditioned on
an outcome that occurs *after* the condition is applied, and on unequal subsets (20 vs 13
episodes). **It is invalid and is replaced, not re-weighted.** No claim is made here that the
corrected analysis is "stronger" or "weaker" than the original: the manuscript's headline
number for this endpoint was a successes-only Mann-Whitney, which estimated a different
quantity on a different sample under a different design. The two are not on a common scale
and are not compared.

| Analysis | Statistic | Two-sided p | Effect |
|---|---|---|---|
| Worst-rank imputation | Wilcoxon W = 47.5, n = 25 (approx) | **0.00206** | rank-biserial +0.708; HL +15.50 ranks [+7.00, +23.25] |
| Win ratio (FS) | 470 W / 84 L / 71 T of 625 pairs | — | WR = 5.595, bootstrap 95% CI [2.431, 17.970] |
| Time-to-event | log-rank χ² = 11.705, df 1 | **0.000623** | CI at 60 steps: 0.800 vs 0.520 |

Direction is uniform: wire_only outperforms overlay. Overlay is worse on 19 of 25
matched seeds, better on 6, tied on 0.

For comparison, the manuscript reported a seed-matched Wilcoxon on only the 9 seeds where
both arms succeeded (W = 3, p = 0.0195). That test is retained solely as a sensitivity line.

### Notes affecting interpretation

- **The failure-ordering rule was favourable to overlay, and the result held anyway.**
  Overlay's failures ended much closer to target (6.1–11.6 mm on 5 of 12) than wire_only's
  (19.3–171.2 mm), so ranking failures by final distance hands overlay the better failure
  ranks. Overlay still loses decisively.
- Ties in the rank differences meant the exact Wilcoxon was not valid; the normal
  approximation with continuity correction was used and is reported as such.
- Both-arms-failed pairs are scored as ties (71 of 625) per PRESPEC §3. An alternative
  tie-break on final distance was *not* used, because PRESPEC specifies success then steps only.
- Administrative censoring at 60 is non-informative here because both arms share the same
  budget; all failures censor at exactly 60 and every success occurs before it.

### Amendments applied 2026-09-11 (author-directed, see PRESPEC §9)

The Phase 3 script was amended and re-run; **every computed value is unchanged** (the RNG is
consumed in the same order, so the bootstrap is bit-identical). What changed is reporting:

- The "strengthened the claim" framing is removed everywhere. The successes-only comparison is
  described as **invalid and replaced**, never as weaker or stronger.
- No effect size from the successes-only design appears beside a matched-design effect size.
- **Log-rank vs Fisher is now reconciled in the report text.** Fisher exact on the same 50
  episodes gives p = 0.0718 (OR 3.69) — computed here, not quoted — against log-rank
  p = 0.000623. Both are correct: Fisher uses only the terminal success proportion; the
  log-rank uses the step at which each episode succeeded or was censored. **The success-rate
  claim stays declined.** The log-rank is about time to target, not the terminal proportion,
  and must not be presented as reviving the abandoned claim.
- Abstract-facing number for Phase 3 is the **win ratio, 5.60 [2.43, 17.97]**.
- New figure `results/fig_cumincidence_a1.{pdf,png}` (manuscript Fig. 3b), annotated at step 50
  (64% vs 8%). The successes-only boxplot is withdrawn as the biased view.

---

## Phase 4 — primary endpoint, matched design (2026-09-11)

Script `analysis/phase4_primary.py`; output `results/phase4_{report.txt,tests.csv,pairs_a1.csv}`.

**Pairing audit passed:** 25 defined episodes per arm, identical seed lists, 25 complete pairs,
no seed dropped. None of the stop conditions fired — direction unchanged, still significant.

**Implementation validated against the paper's own numbers:** medians 0.1452 / 0.1749
(difference +0.0297) and Mann-Whitney U = 496 (≡ 129), p = 0.000384, r = 0.587 reproduce
`PAPER_DATA.md` exactly, confirming the independent `f_rot_LM` implementation.

| Analysis | Result |
|---|---|
| **Primary** — Wilcoxon signed-rank, 25 pairs, **exact** | W = 73.0, **p = 0.0147**, rank-biserial +0.551, HL +0.0285 [+0.0068, +0.0440] |
| Direction | overlay > wire_only; higher on 20/25 seeds |
| Secondary sensitivity (Mann-Whitney, unmatched) | U = 496, p = 0.000384 |
| Sensitivity excl. seed 5155 (0.3709) | W = 48.0, 24 pairs, exact, p = 0.00252, HL +0.0305 |
| Design sensitivity | MDE = 0.0292 (simulated, Wilcoxon); parametric d = 0.584 → 0.0348 |

### Two things that matter for the manuscript

1. **The correctly-matched primary test is far less extreme than the manuscript's headline.**
   The manuscript reported A1 at p = 0.0004 using an unmatched Mann-Whitney. The matched test
   the design actually calls for — and which Reviewer 2 (comment 3) explicitly asked for —
   gives **p = 0.0147**. Same direction, same data, an order of magnitude less extreme. The
   revision must lead with 0.0147; the 0.0004 cannot be carried over.
2. **The study sits essentially at its own detection limit.** The observed HL shift (+0.0285)
   is **0.98x** the smallest paired shift detectable at n = 25 with 80% power (0.0292). A1 was
   powered to detect approximately the effect it found and nothing smaller. This is the honest
   answer to Reviewer 1's power concern and belongs in the limitations.

Note the exact method was available here (no zeros, no ties in the paired differences),
unlike Phase 3's rank-based differences which required the normal approximation.

---

## Phase 5 — multiplicity table (2026-09-11)

Script `analysis/phase5_multiplicity.py`; output `results/multiplicity_table.csv`,
`results/phase5_report.txt`.

**Check 1 — all three anatomies are seed-matched.** A1 and A2 pair completely at 25 seeds;
A3 pairs at 23 (overlay seeds **4254, 4265** have every row `api_ok=False`). Because the
design is matched everywhere, the paired Wilcoxon replaces Mann–Whitney in all three
anatomies, for the same reason Phase 4 switched. No seed is dropped silently — the two A3
seeds are named in the table and in the report.

### Confirmatory family (Holm primary, Bonferroni also reported for Reviewer 1)

| Anatomy | W | n pairs | Method | Raw p | Holm p | Bonferroni p |
|---|---|---|---|---|---|---|
| A1 | 73.0 | 25 | exact | 0.0147 | **0.0147** | 0.0442 |
| A2 | 0.0 | 25 (**16 informative**) | approx | 0.000482 | **0.000965** | 0.00145 |
| A3 | 6.0 | 23 | exact | 3.34e-06 | **1.00e-05** | 1.00e-05 |

All three survive Holm. Direction is overlay > wire_only in every anatomy.

### A2 is a floor effect, not a magnitude shift — report it as such

**All 25 A2 wire-only episodes have `f_rot_LM` of exactly 0.0000**: that arm never rotates
during the LM phase at all. In overlay, 16 of 25 episodes rotate. So A2 evidences
*presence versus absence* of LM rotation, not a graded shift. Nine pairs are (0, 0), give a
zero difference, and are dropped by the signed-rank test — the effective sample is **16, not
25**, and the test reduces to a sign test on 16 uniformly positive differences (hence W = 0
and rank-biserial = +1.000).

This is structurally the same degeneracy the manuscript itself labelled "UNINFORMATIVE" for
prompt variant V2, except that here only one arm is pinned at the floor, so the effect is
real. But A2's median/IQR is degenerate ([0.0000, 0.0000]) and its effect size is **not**
comparable to A1 or A3. The manuscript must not describe A2 as a "+0.045 shift".

### Bug found and fixed in my own reporting

The first Phase 5 run printed `n = 25` for A2, because the helper reported total pairs while
scipy had silently dropped the nine zero-difference pairs. Both scripts now report total and
informative pairs, and the table's `n` column names the informative count whenever it is
smaller. Caught by checking why A2 came back with `W = 0.0` and `rank-biserial = +1.000`.

### Check 2 — success rates, and whether a steps claim is supportable elsewhere

| Anatomy | wire_only | overlay | Fisher p |
|---|---|---|---|
| A1 | 20/25 | 13/25 | 0.0718 |
| A2 | 25/25 | 25/25 | 1.00 |
| A3 | 10/25 | 0/25 | 0.000636 |

- **A2: no selection bias exists** — success is 100% in both arms, so every episode
  contributes and nothing is conditioned away. A steps-to-target claim on A2 would be
  well-founded. Not run, per instruction.
- **A3: a steps claim is not available.** The overlay arm has zero successes, so
  steps-to-target is undefined there. A worst-rank or win-ratio analysis would be driven
  entirely by the success/failure split plus final distance — interpretable, but it would not
  be a "steps" claim. Not run, per instruction.

### Exploratory rows (unadjusted, blank adjusted columns)

Nothing exploratory is significant except the unmatched sensitivity lines and A3's success
rate. Notably **all first-bifurcation LCx tests are p = 1.00** in all three anatomies, and
biplane-vs-mono is p = 0.375 in both modes. V2 has only **2 informative pairs of 10**,
quantitatively confirming the manuscript's own "uninformative" verdict.

---

## Phase 6 — leave-A3-out (2026-09-11)

Script `analysis/phase6_leave_a3_out.py`; output `results/phase6_leave_a3_out.csv`,
`results/phase6_report.txt`.

**The claim survives.** On A1 + A2 only, with Holm over the two-anatomy family: A1 Holm
p = 0.0147, A2 Holm p = 0.000965, both significant, direction preserved in both. Worst
adjusted p in the family = **0.0147**.

Two honest qualifications that belong in the response letter:

1. **Dropping A3 cannot make the adjustment harder.** Holm divides by a smaller m, so the
   surviving adjusted p-values can only shrink or stay equal. The leave-A3-out check is about
   whether the remaining anatomies carry the claim on their own — it is not a stress test of
   the correction.
2. **The two survivors are not equivalent replications.** A2 is the floor effect described
   above. A1 is the only anatomy in the reduced family contributing a graded magnitude
   effect, and it is also the weakest (Holm p = 0.0147, sitting at 0.98x the minimum
   detectable effect). So the replication claim survives A3's exclusion, but it rests on one
   graded result plus one presence/absence result, not on two matching effects.

---

## Phase 6b — repository corrections policy (2026-09-11)

`master` frozen; no history rewritten. `RESULTS.md` and `PROTOCOL.md` each carry a dated
SUPERSEDED banner with the original text retained verbatim beneath. `PROTOCOL.md` additionally
banner-marked as **evidence that must not be edited** — its pre-specification of
"median + Mann-Whitney" and "successes only" is what proves those choices were pre-specified
rather than chosen after seeing results, and it is cited when disclosing the endpoint swap.
`CORRECTIONS.md` added (C1 successes-only steps, C2 unmatched test on matched design, C3 A2
floor effect, C4 post hoc endpoint-hierarchy revision, C5 public repo reflects uncorrected
analyses). Commit `ec3a2f4`.

---

## Phase 6c — integrity checks (2026-09-11)

Script `analysis/phase6c_integrity.py`; output `results/phase6c_report.txt`,
`phase6c_lm_profile.csv`, `phase6c_a3_episodes.csv`.

### Check 1 — A2's zero is real, behavioural, and not trivially expected

I flagged a specific risk before running: `f_rot_LM` weights rotation steps by `|dist_delta|`,
so a rotation that turns the tip *without translating it* would contribute ~0 to the numerator
and be invisible. If that were happening, "A2 never rotates" would be false and the metric
itself would be unsound. **Tested directly, and it is not happening.**

- A2 wire_only: **0 rotate intents during the LM phase, across all 25 episodes** (0 of 25
  episodes had even one). The zero is a true behavioural zero, not a metric artefact.
- A2 overlay: **37 rotate intents across 16/25 episodes** — the overlay condition induces
  rotation where wire-only produces none.

**The LM phase is not trivially short either**, which was the other way this result could have
been hollow:

| Anatomy / arm | LM steps (median) | LM travelled (median) | rotate intents (total, 25 eps) |
|---|---|---|---|
| A1 wire_only | 16 | 28.2 mm | 104 |
| A1 overlay | 27 | 27.8 mm | 195 |
| **A2 wire_only** | **15** | **18.7 mm** | **0** |
| A2 overlay | 19 | 18.6 mm | 37 |
| A3 wire_only | 52 | 34.6 mm | 748 |
| A3 overlay | 112 | 38.9 mm | 1835 |

A2's LM phase is essentially the same length in steps as A1's (15 vs 16), and A1's operator
issued 104 rotate intents over that span. So zero rotation on A2 is a genuine behavioural
contrast, not a by-product of a short phase. **My earlier log claim stands, now substantiated.**
A2 remains a presence/absence effect on 16 informative pairs — that framing is unchanged.

### Check 2 — A3 overlay: behaviourally real, not a simulator failure, but with a confound

**No instability.** 0 NaN tip rows, 0 discontinuous jumps > 20 mm, `reset_attempts` = 1
everywhere (normal), all 25 episodes ran the full 150-step budget. The arm is not crashing.

**Not wrong-branch.** 22/25 left the left main; **0/25 entered the LCx**. Failure is not
mis-selection at the bifurcation.

**The mechanism is visible in the LM dwell time.** A3 overlay spends a median of **112 of 150
steps still inside the left main** (wire_only: 52) and issues **1835 rotate intents there**
(wire_only: 748). It churns in the LM and exits too late to reach the target. Only 4/25
overlay episodes were still closing on the target at budget exhaustion, versus 16/25 for
wire_only — overlay had *plateaued*, not run out of time mid-approach.

**The confound that must be disclosed.** A3 overlay's final distances cluster very tightly
(median 37.8 mm, IQR [35.6, 39.0]) — and **A3 wire_only's failures cluster at the same place**
(~32.8–35.2 mm). Both arms hit the same barrier roughly 33–38 mm from target; wire-only
escapes it in 10/25 episodes and overlay in 0/25. So a large part of A3's difficulty is
anatomical, and the overlay effect on A3 is properly stated as "fails to escape a barrier that
wire-only sometimes escapes", not "navigates worse throughout".

### New problem this check exposed — the A3 success denominator

Seeds **4254 and 4265** are the two all-API-failed overlay episodes. They never left the LM and
sit at 56.7 mm, far outside the other 23 (33.7–40.6 mm). They contributed **no valid operator
actions at all**, yet Phase 5's Fisher test on A3 success counted them as behavioural failures,
using 25 as the overlay denominator.

That is not defensible: an episode with zero valid actions is an exclusion, not a failed
navigation attempt. The honest statement is **0/23**, matching the denominator already used for
A3's rotation endpoint. Phase 5's A3 success row (`Fisher p = 0.000636`) therefore needs
recomputation on 10/25 vs 0/23. **Not recomputed yet** — flagged here and reported, pending
instruction, rather than silently changed.

---

## Phase 6d — exclusion rule applied everywhere (2026-09-11)

Rule recorded in `analysis/PRESPEC.md` §9. Scripts `analysis/phase6d_denominators.py` and an
amended `analysis/phase5_multiplicity.py`; output `results/denominators.csv`,
`phase6d_pairing.csv`, `phase6d_report.txt`.

**How partial failures were handled during collection** — established from the harness source,
not inferred. `run_coronary.py:677-695`: no retry, no skip, no episode termination. On failure
the harness executes `[[0.0, 0.0]]`, a **null hold**, and continues. A partial failure
therefore consumes one step of the budget and can degrade the episode's outcome — it is not
merely lost information. This is recorded in PRESPEC and drives Phase 6e.

**Exclusions found across the whole corpus** (episodes with zero valid operator actions):

| Arm | Attempted | Excluded | Analysed |
|---|---|---|---|
| A3 overlay | 25 | 2 (seeds 4254, 4265) | 23 |
| A1 V3 overlay | 10 | 5 (seeds 5045–5089) | 5 |
| A1 old-prompt contrast | 15 | 8 (seeds 2078–2155) | 7 |
| every other arm | — | 0 | — |

**What the sweep moved:** exactly one row. A3 success 10/25 vs **0/23**, Fisher
**p = 0.000675** (was 0.000636 on 0/25); A3 first-bifurcation LCx now on n = 25+23, p = 1.00
unchanged. The confirmatory family and Phase 6 leave-A3-out are **unchanged** — the paired
tests already dropped undefined-metric episodes. Both were re-run to verify this rather than
assumed.

**Borderline case the rule admits, flagged not hidden:** V3 overlay seed 5034 has **53 of 60
steps failed** and is retained, because 7 valid actions survive. An episode that is 88%
transmission failure passes the rule. Exploratory arm only, but the threshold is a judgement
call.

---

## Phase 6e — API failure audit (2026-09-11)

Script `analysis/phase6e_api_audit.py`; output `results/phase6e_report.txt`,
`phase6e_percall_rates.csv`, `phase6e_failure_steps.csv`.

### Correction to my own first pass

My first run of this audit reported raw per-call rates and concluded that rates "differ
materially by arm" in A1, A3, V3 and mono120, quoting **A3 overlay at 8.11%**. That was
**wrong as a bias statement**, and I reported it to the author before catching it.

Raw rates are dominated by whole-run outages, which the Phase 6d rule already removes and
which therefore cannot bias the analysed data. **300 of A3 overlay's 304 failures are the two
fully-failed episodes.** The audit now separates:

- **(a) whole-run outages** → cause exclusions, cannot bias analysed data;
- **(b) sporadic failures inside retained episodes** → inject holds, *can* bias analysed data.

### Findings on the bias-relevant quantity (retained episodes only)

| Arm pair | wire_only | overlay | Fisher p | Raw p (for contrast) |
|---|---|---|---|---|
| **A1** | 17/1277 (1.331%) | 0/1448 (0.000%) | **2.39e-06 differs** | 2.39e-06 |
| A2 | 0/1026 | 3/1400 (0.214%) | 0.268 | 0.268 |
| **A3** | 1/3438 (0.029%) | 4/3450 (0.116%) | **0.375 no difference** | 6.25e-87 |
| V3 (expl.) | 1/600 | 53/300 (17.667%) | 7.15e-26 differs | 4.09e-137 |
| mono120 (expl.) | 12/960 (1.250%) | 0/1025 | 0.000158 differs | 0.000158 |
| V2, V4, BI120, OLD15 | 0 | 0 | 1.00 | 1.00 |

- Only **A1** differs among the primary anatomies, and it differs **against wire-only** — the
  better arm loses the steps. The bias runs counter to the reported effect.
- A1's whole burden: **17 holds in one episode** (seed 5221), 1.33% of that arm's budget.
- **A3's 0/23 is not a transmission artefact.** Four retained failures, all at steps 147–150
  (median position 0.99 of the episode), 0.20% of budget — after the outcome was settled.
- Excluded episodes are **consecutive and at the end of their run block** (A3 overlay eps
  24–25; V3 overlay 5–9; contrast 8–15), the signature of an outage or credit exhaustion.
  But each arm is one contiguous collection block, so **condition and collection window are
  confounded** and cannot be separated from these logs.

### Consequence

The Methods sentence "exclusions were not outcome-dependent" is **removed**, not softened.
Replacement text drafted in `CORRECTIONS.md` C7, stating the A1 difference, its direction, its
magnitude, and the collection-window confound as an unresolved limitation.

**Stop condition triggered** (per-call rate differs materially by arm in a primary anatomy):
halted before Phase 6f, 6g and Phase 7, pending instruction.

---

## Phase 6f-rev — mesh provenance audit (2026-09-12)

Script `analysis/phase6f_mesh_provenance.py`; output
`results/phase6f_mesh_provenance.{txt,json}`. Logged as `CORRECTIONS.md` **C8**.

### The existential check passes: A1 and A2 are patient-derived

| Mesh | Faces | Boundary edges | Provenance |
|---|---|---|---|
| A1 VMR 0066 | 15,897 | 81 | clipped patient surface — pipeline has **no** fallback path |
| A2 ASOCA Normal_12 | 6,689 | 9 | clipped patient surface — fallback gate never fired (mesh open) |
| A3 ASOCA Normal_5 | 632 | 72 | **entirely generated tube**, constant 2.5 mm radius, 12-sided |
| A3 pre-fallback clip | 3,718 | **0 (closed)** | the closed mesh that triggered the substitution |

`clip_left_coronary.py` contains no substitution path of any kind — verified by reading the
whole file, not inferred from the ASOCA clipper's "identical pipeline" docstring.
`ANATOMY_NOTES.md` recorded all three correctly at the time, and its face counts match the
measured meshes exactly.

### A3 is a phantom, and the error is a misstatement rather than a discovery

`clip_asoca_left.py:246-251` replaces the mesh **wholesale**; `generate_tube_fallback` tubes
**every branch**. Patient-derived in A3: centerline, bifurcation location, ostium, target
index. Generated: the entire lumen wall, with no taper, no calibre variation, no wall
irregularity. The manuscript narrowed this to "a bifurcation region" and called a wholly
generated surface "only partly patient-derived" — while the project's own notes had it right,
including drafted limitations text.

### Measurement: corroborating, not decisive — and one attempt discarded

**First attempt was invalid and its numbers were never used.** It cast rays along *vertex*
normals and took the nearest hit in either direction; on a coarse mesh that strikes
neighbouring facets, so it returned medians of 1.8–2.8 mm for vessels with a ~4.5 mm left
main, minima of ~0.02 mm, and it mislabelled the known-synthetic A3 as patient-derived.

Corrected version casts from face centres along the face normal and accepts a hit only from an
antiparallel face:

| Mesh | median | CV | within 5% of median |
|---|---|---|---|
| A1 | 1.81 mm | 0.455 | 10.0% |
| A2 | 2.83 mm | 0.463 | 6.1% |
| **A3** | 4.22 mm | **0.197** | **35.6%** |
| A3 pre-fallback clip | 1.73 mm | 0.487 | 3.3% |

A3 is by far the most uniform, as a generated tube should be. **But the prediction was a tight
spike near 2R (~4.83 mm) with CV ≈ 0, and that did not occur**, and absolute values are biased
low on every mesh. Residual spread is attributable to `decimate_pro(0.85)` on the tube, ring
collapse, and overlapping tubes at the merged bifurcation. Reported as corroboration only; the
source and the notes carry the claim.

### What propagates

"Three anatomies, two CT sources" → **two patient-derived anatomies plus one phantom**. The
abstract's "replicates across all three anatomies and both CT data sources" must be restated.
And A3 supplies the family's strongest rotation result (raw p = 3.34e-06) from the phantom —
so patient-derived replication rests on A1 + A2, making Phase 6's leave-A3-out result
load-bearing rather than a robustness check. That is what Phase 6h now tests.

---

## Confirmatory family redefined + A3 reframed (2026-09-12)

Three author-directed additions, folded in before 6h.

1. **Family redefined to A1 + A2** (`PRESPEC.md` §9, dated; `CORRECTIONS.md` **C9**). A3 is a
   phantom, not an anatomy, so the confirmatory family now contains like objects only, with A3
   reported as a phantom sensitivity. Post hoc, disclosed as such. **It moves no number:** Holm
   leaves the largest p in a family unmultiplied, and A1 holds the largest raw p in either
   family, so A1's adjusted p is 0.0147 under both a three- and a two-member family, and A2's
   is 9.65e-04 under both. `results/phase6_report.txt` already prints both columns, so a
   reviewer verifies this without rerunning anything.
2. **A3 written up as a curvature-only control**, not as an apology. A constant-radius tube on
   a patient centreline isolates curvature from calibre; the overlay effect survives the
   removal of taper and wall texture and is largest there. Drafted paragraphs in C9.
3. **C8 strengthened on provenance.** `ANATOMY_NOTES.md` documented all three meshes correctly
   during data preparation — including "taper, curvature: Not represented" — and drafted
   accurate limitations text. **The error entered at manuscript drafting, not data
   preparation.** That distinction goes in the response letter: imprecise writing, not
   unreliable data.

---

## Phase 6h — A2 steps-to-target (2026-09-12)

Script `analysis/phase6h_a2_steps.py`; output `results/phase6h_report.txt`,
`phase6h_pairs_a2.csv`, `phase6h_tests.csv`, `fig_cumincidence_a2.{pdf,png}`.

**The promoted primary endpoint replicates on the second patient-derived anatomy, decisively.**

| | wire-only | overlay |
|---|---|---|
| Success | 25/25 | 25/25 |
| Steps, median [IQR] | 41.0 [40, 43] | 56.0 [53, 59] |
| Steps, range | 37–45 | 50–62 |

Wilcoxon signed-rank, 25 pairs, all informative, approx (ties present): **W = 0.0,
p = 1.25e-05**, rank-biserial **+1.000**, Hodges–Lehmann **+14.50 steps [+13.00, +16.50]**.
**Overlay is slower on 25 of 25 seeds** — no exceptions.

### Complete separation, and how it is reported

wire-only's slowest episode (45 steps) is faster than overlay's fastest (50 steps). All 625
cross-arm pairs are wire-only wins: **wins 625, losses 0, ties 0**, so the raw win ratio is
**infinite** and a percentile CI on it does not exist. This is a property of the data, not a
computational failure — the first run crashed on it (`np.percentile` of an empty array) and the
estimator was made separation-tolerant rather than the case being quietly dropped.

The Haldane-corrected value (1251.0, CI [1251.0, 1251.0]) is **degenerate and must not be
reported as an effect size or a confidence interval** — every one of the 10,000 bootstrap
replicates was separated, so the "interval" is a single point produced by the 0.5 correction.
The honest statements are: **win ratio infinite; win fraction 1.0000; 625/625 pairs favour
wire-only.**

### Episode length and rotation

| | total steps | rotate intents (total) | rotate intents (LM) | episodes with any rotation |
|---|---|---|---|---|
| wire-only | 1026 | 26 | **0** | 18/25 |
| overlay | 1400 | 214 | 37 | 25/25 |

This sharpens the 6c finding rather than contradicting it: A2 wire-only **does** rotate (26
intents across 18 episodes) but issues **zero rotate intents during the LM phase**. The 6c
claim was specifically about the LM phase and stands; the induction framing in 6g should say
"zero rotate intents *during the LM phase*", not "never rotates".

### The success parity on A2 is an artefact of unequal budgets

`protocol.json` gives A2 wire-only **45** steps and A2 overlay **62**. Under the common
(smaller) budget of 45:

> **wire-only 25/25, overlay 0/25.** Every one of the 25 overlay episodes took more than 45
> steps.

So the reported "25/25 vs 25/25" success parity on A2 exists only because the overlay arm was
given 38% more budget. Under a matched budget the arms would not be comparable on success at
all.

**What this does and does not invalidate.** The steps-to-target comparison itself stands: every
episode in both arms reached target within its own budget, so nothing is censored and no step
count is truncated. And the operator cannot see the budget — the state string carries distance,
trend, retractions remaining and the no-progress counter, but never the step budget
(`run_coronary.py` state text) — so the longer allowance did not *cause* slower navigation, it
merely permitted those episodes to finish. What is invalidated is the **success-rate parity
claim** on A2, which must be withdrawn or restated on a common budget.

---

## Phase 6i — API-hold sensitivity on the A1 primary (2026-09-12)

Script `analysis/phase6i_hold_sensitivity.py`; output `results/phase6i_report.txt`,
`phase6i_tests.csv`.

**All 17 A1 holds fall in one episode — wire-only seed 5221 — and that episode is a failure.**
Overlay absorbed none. **Zero successful episodes were affected**, so no success step count
moves under the discount; only that failure's censoring time does (60 → 43).

| Variant | worst-rank | win ratio | log-rank |
|---|---|---|---|
| As analysed | W = 47.5, p = 0.00206 | 5.595 [2.431, 17.970] | p = 0.000623 |
| Hold-discounted | W = 47.5, **p = 0.00206** | **5.595 [2.431, 17.970]** | **p = 0.000157** |
| Bound: 5221 granted success | W = 41.5, p = 0.00118 | 5.738 [2.547, 18.101] | p = 0.000274 |

Direction preserved and significance retained everywhere. The worst-rank test and win ratio are
**bit-identical** under the discount — they depend on success step counts and failure distances,
neither of which the holds touched. The log-rank **strengthens** (0.000623 → 0.000157) because
censoring wire-only's failure at 43 rather than 60 removes time-at-risk without an event.

The bound is deliberately not an imputation: we cannot know what seed 5221 would have done with
17 more usable actions, so we grant it the most favourable outcome its budget allows and show
the conclusion survives that too.

**Self-caught wording error.** The script's auto-generated Methods sentence asserted the
discount left results "unchanged" while quoting a log-rank p that had changed. The accurate
sentence — worst-rank and win ratio unchanged, log-rank strengthened — is in `CORRECTIONS.md`
C7 and is what goes to the manuscript.

---

## Phase 6j — validity threshold, and the collection-epoch confound (2026-09-12)

Script `analysis/phase6j_validity_threshold.py`; output `results/phase6j_report.txt`,
`phase6j_threshold.csv`.

**Part 1 — threshold sensitivity (>50% failed calls).** Exactly one retained episode is caught:
**V3 overlay seed 5034, 53/60 calls failed (88.3%)** — the borderline case flagged when the 6d
rule was written.

| | Committed (A1+A2 family) | Under the threshold |
|---|---|---|
| A1 | W = 73.0, p = 0.0147, Holm 0.0147 | W = 73.0, p = 0.0147, Holm 0.0147 |
| A2 | W = 0.0, p = 0.000482, Holm 0.000965 | W = 0.0, p = 0.000482, Holm 0.000965 |

Zero episodes dropped from either confirmatory anatomy; the only movement is exploratory V3
(p = 0.812 → 0.875, on 4 pairs instead of 5), null before and after. **Confirmed: the threshold
changes nothing that matters.**

**Part 2 — collection-epoch confound**, written verbatim as **L1** in
`revision/limitations_draft.md`: *each arm was collected as one contiguous block, so condition
and collection epoch cannot be separated from these logs, and an outage affecting one block is
indistinguishable from a condition effect.* The draft also carries L2–L8, seeded from findings
already committed (hold asymmetry, A3 phantom, A2 budget asymmetry, A1 MDE, A2 floor effect,
seed-matching scope, single model / simulation only).

---

## Phase 6g — A2 rotation reframed as induction (2026-09-12)

Drafted replacement text added under `CORRECTIONS.md` C3, which already diagnoses the
"magnitude shift" error. Rotate-intent **counts** are now the primary A2 rotation evidence:
**zero rotate intents during the left-main phase across all 25 wire-only episodes, versus 37
across 16 of 25 overlay episodes**, over a phase of comparable length to A1's (median 15 steps
vs A1's 16). The signed-rank p is secondary, and its rank-biserial of +1.000 and degenerate
[0.0000, 0.0000] median/IQR are explicitly not reported as effect sizes.

**Scope note carried into the draft** (from 6h): A2 wire-only issues **26 rotate intents in
total across 18 of 25 episodes**. The absence is specific to the left-main phase. "A2 wire-only
never rotates" is false; "issues no rotate intents during the left-main phase" is correct.

---

## Phase 6k — A3 stall zone (2026-09-12, discussion material only)

Script `analysis/phase6k_a3_stall.py`; output `results/phase6k_report.txt`,
`phase6k_a3_stall.csv`. Done from existing traces only — no ASOCA archive, no centreline
recomputation, per instruction. A3 is a phantom, so this gates nothing.

| | wire-only (n=25) | overlay (n=22) |
|---|---|---|
| Arc length at band entry | 34.3 mm [34.0, 35.0] | 35.0 mm [34.5, 35.8] |
| Fraction of path at entry | **0.50** [0.43, 0.63] | **0.76** [0.71, 0.80] |
| Steps spent inside band | 60 [40, 82] | 31 [15, 57] |

Both arms reach the 33–38 mm band at essentially the same absolute arc length (~34–35 mm), so
it is a location both reach rather than an obstacle only one encounters. What differs is **when
in the budget they arrive**: wire-only at half its traversed path, overlay at three-quarters,
having first spent a median 112 of 150 steps inside the left main (Phase 6c). Wire-only arrives
with budget in hand, works the band for a median 60 steps and escapes in 10/25 episodes;
overlay arrives late, spends 31, and escapes in 0/23.

**Two corrections to the script's auto-generated paragraph, not propagated to the manuscript:**

1. It said "what separates the arms is dwell, not location", which implies overlay dwells less
   by choice. Overlay *arrives later*, having burned budget upstream in the left main. Dwell is
   the consequence, not the cause.
2. It compared curvature at the locus with whole-path curvature as though that were vessel
   geometry. **It is not.** The quantity measured is curvature of the **tip trajectory**, and
   both arms traverse the *same* phantom, so the arm difference (0.509 vs 0.697 1/mm at the
   locus; 0.365 vs 0.661 1/mm whole-path) is **behavioural** — overlay's path is more convoluted
   because it rotates more — and licenses no statement about vessel curvature. No geometric
   claim is drawn from it.

The only geometry-relevant statement available: A3's wall is a generated constant-radius tube,
so **no calibre narrowing exists at the band by construction**.

---

## Phase 7 baseline 1 — ALWAYS-ADVANCE on A1 (2026-09-12)

Script `analysis/phase7_always_advance.py`; output `results/baselines/`. Simulator only, no
API calls. Config matched to the study arms, not to `scripted_stability_check.py`: dt = 0.006
(the stability script uses 0.001), max_it = 2000, friction = 0.001, budget 60, the 25 A1 study
seeds, `tip_branch_obs` classified from the pre-action tip. Wall time 3.9 min.

Policy: translation 35.0 mm/s (the harness's own `PROXIMITY_GATE_ADV_DEFAULT`), rotation 0,
every step. Never rotates, never retracts, never sees the image.

### The headline, which changes the paper's framing

| Policy | Success on A1 | Median steps to target |
|---|---|---|
| **Always-advance (no image)** | **17/25 = 68.0%** | **27** (all 17, range 27–27) |
| VLM wire-only | 20/25 = 80% | 48 |
| VLM overlay | 13/25 = 52% | 56 |

**A policy that ignores the image entirely reaches mid-LAD in 68% of episodes**, and does so
in 27 steps — roughly half the VLM's. Descriptively, the VLM's wire-only arm is 12 points
higher on success while taking 78% more steps, and the overlay arm is 16 points lower.

> **RETRACTED 2026-09-13.** This entry previously read "the overlay arm (52%) performs worse
> than the no-image baseline", and the interpretation section below drew a "degrades below a
> policy that never looks at the image" conclusion from it. **That claim is not supportable and
> is withdrawn.** Baselines are calibration, not a tested contrast (PRESPEC §9, Phase 7b).
> Computed once and recorded as a non-result, never to be used in support of anything:
> always-advance 17/25 vs VLM overlay 13/25, Fisher OR = 1.96, **two-sided p = 0.387**; and
> always-advance 17/25 vs VLM wire-only 20/25, OR = 0.53, p = 0.520. Both are far from
> significance at n = 25. Always-advance is also deterministic — every success took exactly 27
> steps — so it is a fixed reference point, not a distribution, and all baseline comparisons
> are stated as point estimates only. The superseded wording also survives in the message of
> commit `73a1674`, which is immutable history; this note is the correction of record.

`f_rot_LM = 0.0000` exactly, and 0 rotate intents, by construction.

### What this does and does not do to the claims

- It does **not** overturn the overlay-vs-wire-only contrast: that comparison is internal to
  the VLM arms and is unaffected.
- It **does** undermine success rate as an informative endpoint on A1, which has a high
  open-loop floor. Reviewer 1's exact test — "if a random policy also reaches 80%, then the VLM
  is not poor" — is close to being met by a trivial policy.
- It **sharpens** the overlay finding into something stronger and more damning: overlay does
  not merely degrade navigation relative to wire-only, it degrades it **below a policy that
  never looks at the image**.
- Steps-to-target remains strongly discriminating (27 vs 48 vs 56) where success rate does not.

### Failure structure, and a fidelity caveat

The 8 failures are bimodal, not scattered: **five end at 135.5–135.7 mm** (seeds 5001, 5012,
5133, 5144, 5254) and **three at 298.5–298.6 mm** (seeds 5056, 5166, 5210). Successes all end
at 1.0–1.1 mm. Two discrete wrong outcomes rather than a continuum, consistent with the wire
committing to a branch at the bifurcation and then running open-loop.

`LCPConstraintSolver` reported non-convergence on several episodes (residual 0.0012–0.0104
after 2000 iterations). No NaN tips occurred, no episode aborted, and all 25 ran to completion,
but the solver residual is a fidelity caveat worth recording.

**Caveat on the policy's strength.** 35 mm/s is the harness's own default advance speed, not a
value tuned here. The baseline's success nonetheless reflects that A1's ostium-to-mid-LAD route
is largely a straight push once the wire is inserted — which is itself the finding.

---

## Phase 7a — always-advance on A2 and A3 (2026-09-13)

Script `analysis/phase7a_always_advance_a2a3.py`; output `results/baselines/`. Same policy
(35 mm/s, rotation 0), each anatomy's own wire-only budget and seeds, study simulator settings.
Centrelines from `asoca_adapter` (`D:\ASOCADataAccess.zip`, 8.3 GB, present).

| Anatomy | Always-advance | VLM wire-only | Steps (baseline successes) | VLM median |
|---|---|---|---|---|
| A1 VMR 0066 | 17/25 = **68.0%** | 20/25 = 80% | 27 (all) | 48 |
| A2 ASOCA Normal_12 | 20/25 = **80.0%** | 25/25 = 100% | 11 (all) | 41 |
| A3 ASOCA Normal_5 (phantom) | **0/25 = 0.0%** | 10/25 = 40% | — | 118 |

**Targets verified comparable before interpreting anything**: the baseline's `gt_target_pos`
matches each study arm's recorded target to **0.000000 mm** on all three anatomies, so
`asoca_adapter`'s heuristic LAD/LCx assignment resolved identically to the original runs.

### The stop condition did not fire, and the second branch is the finding

Always-advance does **not** clear A2 and A3 at rates comparable to the VLM. It is shut out
completely on A3. Per the brief, that means **the environment discriminates — but only on A3.**

On both genuinely patient-derived anatomies a policy that never looks at the image reaches
target in 68% and 80% of episodes, at 27 and 11 steps against the VLM's 48 and 41. **The only
anatomy where the VLM clearly beats a no-vision policy is the synthetic phantom.** That is an
uncomfortable result and it is recorded as-is. Stated descriptively only, per Phase 7b — no
test is run between a baseline and a VLM arm.

### Failure-terminus clustering

- **A2**: all five failures at **66.6–66.7 mm** — a single, extremely tight terminus.
- **A3**: 17 failures in a **27.9–38.2 mm** band, one at 61.9, two at 272–274, five at
  450–460 mm. The main band coincides with the stall zone found in Phase 6k (33–38 mm), where
  both VLM arms also plateau — corroborating that it is a location every policy reaches.

### The simulator is non-deterministic, and this is now load-bearing

Across **all three** anatomies the start state is identical — one distinct step-1 tip position
across all 25 episodes, to six decimals — and the policy is fixed. Yet every non-reference
episode diverges from episode 1 **at step 1**, splitting into distinct outcome groups (A1:
17 success / 5 at ~136 mm / 3 at ~298 mm; A2: 20 / 5; A3: 13 distinct termini).

Identical start, identical action sequence, divergent trajectories. The only thing varying is
the seed passed to `env.reset()`. **The baseline success rates therefore partly measure
simulator non-determinism rather than task difficulty**, and "68% open-loop floor" cannot be
read as a clean statement about how solvable the task is.

This also contradicts `PRESPEC.md` §7 as written, which claims seed-matching fixes "the physics
trajectory for a given action sequence". It does not. That text needs correcting.

### Solver fidelity — A3 is unreliable on essentially every step

Counted per anatomy from the run log, with residuals:

| Anatomy | Non-convergences | Share of steps | Residual median | Residual max |
|---|---|---|---|---|
| A2 Normal_12 | 41 / 445 | **9.2%** | 6.12e-03 | 2.04e-02 |
| A3 Normal_5 (tube) | **3646 / 3750** | **97.2%** | 9.49e-03 | **1.44** |

A3's Gauss–Seidel LCP fails to converge on 97.2% of steps, with a maximum residual of 1.44 —
three orders of magnitude above A2's worst. A3 is simultaneously (i) a wholly synthetic
constant-radius tube rather than an anatomy, (ii) the source of the confirmatory family's
strongest rotation result (raw p = 3.34e-06), and (iii) physically unreliable on nearly every
step. Phase 7e must establish whether the VLM A3 arms show the same, because if they do the A3
result rests on physics the solver never actually resolved.

---

## Phase 7g — the environment does not reproduce a seed (2026-09-13)

Script `analysis/phase7g_nondeterminism_floor.py`; output
`results/baselines/phase7g_report.txt`, `nondeterminism_floor_{a1,a2}.json`. R = 5 repetitions
of the full seed list per anatomy, a freshly built environment per repetition, fixed
always-advance policy.

### My own §7 correction is CONFIRMED, not withdrawn

I flagged it as possibly an over-claim: Phase 7a had varied the *seed*, and different seeds
diverging is what a seed is for, so 7a did not actually contradict the original claim. **7g runs
the decisive test — the same seed, repeated — and the seed does not reproduce.** The correction
stands on its own evidence now rather than on 7a's.

### Measured floor

| | rep 1 | rep 2 | rep 3 | rep 4 | rep 5 | range | seeds concordant across all 5 |
|---|---|---|---|---|---|---|---|
| **A1** | 64.0% | 60.0% | 60.0% | 44.0% | 48.0% | **20.0 pp** | **4/25** |
| **A2** | 76.0% | 80.0% | 68.0% | 72.0% | 52.0% | **28.0 pp** | **2/25** |

Phase 7a's earlier single draws — A1 17/25 = 68%, A2 20/25 = 80% — sit **at or above the top**
of these ranges. Across six draws the spans are **A1 44–68%** and **A2 52–80%**, so the
five-repetition range probably still understates the true spread.

### The structure of the noise, which matters more than its size

- **Start state is identical every time**: one distinct post-reset tip position across all
  repetitions × seeds, on both anatomies. Divergence is entirely downstream of reset.
- **Steps-to-target spread within a seed is exactly 0** (median 0, max 0). A successful episode
  always takes 27 steps on A1 and 11 on A2; a failure always lands on one of a few fixed
  termini.
- So the non-determinism is **not** trajectory jitter. It is a **binary flip at the
  bifurcation**: the wire either commits to the LAD or it does not, and everything downstream
  follows deterministically from that commitment.

### What this does to the analyses — stated carefully

1. **Absolute rates are single draws from wide distributions.** Every success rate in the paper
   — baseline and operator alike — is one sample from something ~20–28 pp wide. No absolute rate
   should be reported as a point estimate.
2. **Between-arm contrasts retain validity, but not for the reason we claimed.** The noise
   enters both arms symmetrically, so a paired test's Type I error is not inflated. But
   **seed-matching provides no blocking and no variance reduction**, because the seed does not
   determine the outcome. The pairing is nominal: it aligns labels, not conditions. The
   "seed-matched, confound-free" justification in the submission is void, and the paired design
   should be defended as a valid test of paired differences rather than as a confound control.
3. **Reviewer 2's comment 2 is sharper than they knew.** They asked that "the independence and
   pairing structure of each round in the repeated experiments must be clear". The honest answer
   is that rounds are not independent replicates of a controlled condition, and the pairing does
   not control what it was said to control.

### Open question for the author, not resolved here

Whether the operator arms' success rates (A1 20/25 vs 13/25; A2 25/25 vs 25/25) can be reported
at all, given each is a single draw. The steps-to-target results may be more robust — step
counts are deterministic given success — but that has not been tested on the VLM arms, where
actions differ per episode and model stochasticity is entangled with this. **Not run; flagged.**

---

## Phase 7e — solver fidelity of the retained arms (2026-09-13)

Scripts `analysis/phase7e_solver_replay.py` (replay) and `phase7e_parse_solver.py` (parser);
output `results/phase7e_report.txt`, `phase7e_solver_rates.csv`, `phase7e_outcome_assoc.csv`.
Scoped to A1 and A2; A3 was already excluded (C11). Solver warnings go to stdout, not into
`trace.jsonl`, and no stdout was captured for the canonical arms, so the rates had to be
re-measured by replaying each arm's recorded action sequence — no API calls.

### Result: the stop condition does not fire

| Arm | Steps | Non-convergent | % of steps | Residual median | Residual max | Replay divergence |
|---|---|---|---|---|---|---|
| A2 overlay | 1400 | 32 | **2.29%** | 1.97e-03 | 6.14e-03 | 0.37 mm |
| A2 wire-only | 1026 | 32 | **3.12%** | 1.83e-03 | 6.52e-03 | 0.34 mm |
| A1 wire-only | 1277 | 80 | **6.26%** | 1.51e-02 | 7.11e-01 | 0.90 mm |
| A1 overlay | 1448 | 192 | *(13.26%)* | 1.46e-02 | 1.31 | **47.98 mm — withheld** |

Worst trustworthy rate is **6.26%**, against A3's 97.2%. Nothing approaches the excluded
geometry, so this produces a Section V fidelity paragraph rather than a second exclusion.

**A1 overlay's rate is withheld, not low.** Its replay finished a median **48 mm** from where
the original episode ended (correlation 0.148 against 0.91–0.98 elsewhere), so it explored
different contact states and cannot characterise the original episodes. The parser withholds it
automatically on a pre-set 10 mm divergence threshold rather than by judgement after the fact.
**The outcome association reported for that arm (failures median 13 non-convergent steps vs 2
for successes, p = 0.0138) comes from the same diverged replay and is equally uninterpretable.**
A1 wire-only shows no association (p = 0.498).

**Two qualifications on "A1 is fine".** Its residual maxima (0.711 wire-only, 1.31 overlay) are
within an order of magnitude of A3's 1.44 — the failures are infrequent but occasionally deep.
And non-convergent steps on A1 involve ~12.8 failed solves each (1022 warnings over 80 steps)
against ~1.4 on A2 (44 over 32), so A1's failures are qualitatively worse where they occur.

### Two bugs found and fixed in my own work here

1. **The first 7e run was void and its numbers were discarded.** It reported 0.00%
   non-convergence across all four arms and 5151 steps — on the same A2 mesh where
   always-advance had just measured 9.2%. The loader read `translation`/`rotation` at the top
   level, but `run_coronary.py` nests them in `parsed_action`; only the repo port and biplane
   traces have them at top level. Every action defaulted to (0, 0) and the wire never moved: no
   motion, no contact, no constraint solving, hence zero warnings rather than few. The
   reproduction counts exposed it — they equalled each arm's original *failure* count exactly.
   Verified: 0/402 sampled rows non-zero via the old path, 402/402 via `parsed_action`. Fixed,
   with an abort guard and a per-episode moved-steps check so it cannot pass silently again.
2. **Binary outcome agreement was withdrawn, not repaired.** Every successful original episode
   crosses the 5 mm threshold *on its final recorded action*, arriving from a median 5.6 mm and
   clearing by ~0.2 mm. The replay lands 0.3–0.9 mm from the original's finish. A 0.2 mm margin
   against a 0.3 mm divergence means agreement records which side of a knife edge the last step
   fell on — on A2, 25/25 replays finish within 5.5 mm but only 7/25 within 5.0 mm. Replaced by
   the continuous divergence measure. Lengthening the replay to chase the threshold would have
   manufactured agreement without improving faithfulness.

---

## Phases 7h and 7i — the variability is binomial, and pairing is unjustified (2026-09-13)

Scripts `analysis/phase7h_dispersion.py`, `phase7i_pairing.py`, `phase7i_worstrank_corr.py`.

### 7h — consistent with binomial on both anatomies

| Anatomy | Counts per rep | Pooled p | Var obs | Var binomial | Ratio | X² (4 df) | Verdict |
|---|---|---|---|---|---|---|---|
| A1 | 16,15,15,11,12 | 0.552 | 4.700 | 6.182 | 0.760 | 3.041, p = 0.551 | **consistent** |
| A2 | 19,20,17,18,13 | 0.696 | 7.300 | 5.290 | 1.380 | 5.520, p = 0.238 | **consistent** |

Concordance is unremarkable in both directions: A1 observed 4 against 1.73 expected under
independence (binomial p = 0.091), A2 observed 2 against 4.15 (p = 0.416).

**Steps-to-target variance is degenerate.** Every successful episode takes exactly 27 steps on
A1 and 11 on A2, so within-seed and between-seed variance are both **0.0000**. Under a fixed
policy there is no continuous variability to decompose; all of it is in the binary outcome.

### My own 7g framing was overstated, and is corrected

I called 7g "the environment does not reproduce a seed" with an "intrinsic run-to-run noise
floor", and treated it as a defect. **That characterisation was wrong.** The narrow fact holds,
but the variability is exactly what independent Bernoulli draws produce. The correct statement
is that **the seed does not propagate to episode outcomes; episodes behave as independent
draws**, and the 20 pp / 28 pp ranges are ordinary sampling variability at n = 25. Corrected in
`PRESPEC.md`, `methods.md`; still to propagate to `response_letter.md` and `title_abstract.md`.

### 7i — within-pair correlation is ~zero on every endpoint

| Anatomy | Endpoint | n | Pearson r [95% CI] | Spearman | Efficiency |
|---|---|---|---|---|---|
| A1 | f_rot_LM | 25 | **−0.072** [−0.455, +0.332] | −0.165 | **0.9416** |
| A1 | worst-rank | 25 | **−0.074** [−0.456, +0.330] | −0.043 | **0.9368** |
| A1 | steps (both succeed) | 9 | +0.219 [−0.521, +0.771] | +0.170 | 1.2764 |
| A2 | f_rot_LM | 25 | **undefined** — wire-only constant at 0.0000 | — | — |
| A2 | steps | 25 | +0.112 [−0.296, +0.486] | +0.158 | 1.1115 |

On both primary endpoints the efficiency ratio is **below 1**: pairing *adds* ~6% to the contrast
variance and costs 24 degrees of freedom. Per the rule fixed in the script before the data were
seen, **the unpaired Mann-Whitney is primary**.

| Endpoint | Paired (was primary) | Unpaired (now primary) |
|---|---|---|
| A1 f_rot_LM | p = 0.0147 | **p = 0.000384** |
| A2 f_rot_LM | p = 0.000482 | **p = 2.95e-06** |

> **Corrected in place, 2026-09-13.** The A2 paired cell first read **0.000438**, taken from
> 7i's own output. That was wrong: `phase7i_pairing.py` called `stats.wilcoxon` directly and so
> took scipy's `correction=False`, where PRESPEC fixes the normal approximation **with**
> continuity correction — which is what `phase5_multiplicity.paired_wilcoxon` applies, giving
> 0.000482 on the same data. Two of my own scripts disagreed on one number and I quoted the
> non-compliant one in three documents. 7i now imports the helper instead of reimplementing it;
> re-running moved A2 f_rot_LM to 0.000482, A2 steps to 1.25e-05 (matching 6h exactly, where it
> had read 1.175e-05), and A1 steps-both-succeed to 0.02427 from 0.01953 — the last because the
> helper forces the approximation when tied absolute differences are present and scipy's auto
> had chosen the exact test. **No decision changes**: the correlations, the efficiency ratios
> and every unpaired p-value are untouched, and 2.95e-06 beats either A2 paired value. An audit
> of the remaining scripts found phase3, phase4, phase5, phase6h and phase6i all implement the
> rule correctly with `correction=True` spelled out, so the worst-rank p = 0.00206 quoted in the
> letter and abstract is unaffected.
>
> Two bare calls remained. **`phase7i_worstrank_corr.py:119`** had the identical defect and is
> fixed the same way. Before re-running I recorded the prediction that its paired worst-rank p
> would move from **0.001969** to **0.00206** and so come to agree exactly with phase3 — because
> if the continuity correction were *not* the whole story, the two scripts would be building the
> worst-ranks differently, which is a substantive problem rather than a formatting one. It
> landed on **0.00206**, W = 47.5 unchanged, with every correlation and efficiency figure
> untouched. The two implementations now agree on one number and no document's worst-rank value
> needed changing. **`phase4_primary.py:143`** is the remaining one, inside the power simulation
> behind the "0.98× minimum detectable effect" figure. It is **not** patched here: that figure
> was computed for the paired test and is withdrawn pending recomputation against the unpaired
> primary, so the simulation is owed a proper revisit and a one-argument fix would only make a
> superseded number look current. Logged as outstanding.
>
> **Scope of the movement, for the record.** Four numbers changed: A2 f_rot_LM 0.000438 →
> 0.000482, A2 steps 1.175e-05 → 1.25e-05 (now matching 6h), A1 steps-both-succeed 0.01953 →
> 0.02427 (the helper forces the approximation under ties where scipy's auto chose exact), and
> worst-rank 0.001969 → 0.00206. Of the four, only the first had ever been quoted outside its
> artifact; it is corrected in `CORRECTIONS.md` C13, `PRESPEC.md` §9 and here.

Navigation is unaffected in substance — the win ratio (5.60 [2.43, 17.97]) and log-rank
(p = 0.000623) are unpaired by construction and remain the proper analyses of that endpoint.

### Two things stated plainly rather than buried

1. **This reverses my own correction C2 and lands on more favourable numbers.** The safeguards
   are that the decision rule preceded the data, that 7h supplies an independent mechanistic
   reason to expect zero correlation, and that both tests appear in the paper regardless.
   Recorded as **C13** (C12 was already taken by the three Methods misstatements).
2. **The correlation CIs are wide.** At n = 25, [−0.46, +0.33] does not exclude moderate positive
   correlation. The supported claim is "no evidence that pairing removes shared variance" — not
   that the correlation is zero.

### Consequence, now discharged

`results/multiplicity_table.csv` was built with the paired tests as confirmatory and Holm
adjusted over them. `phase5_multiplicity.py` is amended to make the unpaired test primary and to
apply Holm to the primary p-values, with the paired result written alongside but not adjusted
over. Both phase5 and phase6 have now been re-run and the table regenerated:

| Anatomy | Primary (unpaired) | Holm | Bonferroni | Paired, alongside (not adjusted over) |
|---|---|---|---|---|
| A1 | U = 496.0, p = 0.000384 | **0.000384** | 0.00115 | W = 73.0, p = 0.0147 (exact, 25/25) |
| A2 | U = 512.5, p = 2.95e-06 | **5.89e-06** | 8.84e-06 | W = 0.0, p = 0.000482 (approx, 16/25) |
| A3 | U = 498.0, p = 3.07e-07 | 9.22e-07 | 9.22e-07 | W = 6.0, p = 3.34e-06 (exact, 23/23) |

**A defect caught in the regenerated output before it was quoted anywhere.** Phase 6 initially
printed each anatomy's *paired* statistic and raw p beside its *unpaired* Holm value, producing
the impossible line `A1 ... raw p=0.0147 Holm p=0.000384` — an adjusted p smaller than its own
raw p. I had changed Holm's input to `p_primary` and left the display reading the paired result,
the same half-a-computation error as the phase5/phase6 Holm-input mismatch earlier in this
phase. `phase6_leave_a3_out.py` is rewritten so the statistic, the raw p and the adjustment all
come from one test, and its closing caveat is computed rather than hardcoded. `phase5_report.txt`
was checked for the same defect and is clean.

**A3's membership in the family turns out to be numerically moot under Holm.** A1 is the largest
p either way and is left unmultiplied; A2 is the middle of three (×2) and the smaller of two
(×2). So the C11 exclusion cannot be said to have eased the correction on either surviving
anatomy — which is the form of the claim the letter now makes. **This was an open question for
the author and has since been decided; see the next section.**

> **SUPERSEDED 2026-09-13 by Decisions 1 and 2 (C11 amendment and C14).** The table and the
> adjusted values in this section were computed with the UNPAIRED test as primary and Holm
> adjusted over THREE members. Both are now wrong: the family is declared as two, and the paired
> Wilcoxon is primary again. The raw measurements in 7h and 7i above stand unchanged — only the
> use made of them changed. Current values are in the next section.

---

## Decisions 1 and 2 — two-member family, and the paired test restored (2026-09-13)

Author-directed, and the second reverses the author's own previous instruction.

### Decision 1 — the confirmatory family is declared as TWO members

A family is the set of tests we draw inferences from, so a geometry excluded from Results cannot
be counted in the correction family. `confirmatory_results()` now declares A1 + A2 and both Holm
and Bonferroni adjust over two. A3's row is gone from the confirmatory table entirely; its raw p
is reported in a clearly separated disposition block and in Section V prose, with **no adjusted
p**.

**Did the exclusion ease the correction? No, and phase6 now computes this rather than asserting
it:**

| anatomy | raw p | Holm (declared, 2) | Holm (if 3) | Bonf (2) | Bonf (if 3) |
|---|---|---|---|---|---|
| A1 | 0.0147 | **0.0147** | 0.0147 | 0.0294 | 0.0442 |
| A2 | 0.000482 | **0.000965** | 0.000965 | 0.000965 | 0.00145 |

Holm is identical under either family size. Only Bonferroni moves, and it is not the primary
adjustment. Recorded as an amendment to C11, including the point that declaring three while
reporting two would have overstated the correction burden in our own favour at no cost to us.

`phase6_leave_a3_out.py` is rewritten: "leave-A3-out" is now the declared design rather than a
sensitivity, so it reports the declared family, computes the counterfactual invariance above,
and never prints an adjusted p for A3. Its old form would have crashed on `three["A3"]`.

### Decision 2 — the paired Wilcoxon is primary again (C14, superseding C13's switch)

**This reverts to the LESS favourable number: A1 returns from 0.000384 to 0.0147.**

C13's defence addressed the *order* in which we did things, not whether the measurement could
bear the weight put on it. At n = 25, ρ = −0.072 carries a 95% CI of [−0.455, +0.332]. That
establishes pairing is not demonstrably helping — not that pairing is unjustified. Too weak a
basis for a 38-fold change in a headline p-value on the test Reviewer 2 specifically requested.

| Anatomy | PRIMARY paired | Holm | Alongside unpaired | ρ [95% CI] | Same conclusion? |
|---|---|---|---|---|---|
| A1 | W = 73.0, exact, p = 0.0147 | 0.0147 | U = 496.0, p = 0.000384 | −0.072 [−0.455, +0.332] | yes |
| A2 | W = 0.0, 16 informative, p = 0.000482 | 0.000965 | U = 512.5, p = 2.95e-06 | undefined (constant arm) | yes |
| A3 | p = 3.34e-06 — **no adjusted p** | — | p = 3.07e-07 | −0.097 [−0.489, +0.329] | n/a, excluded |

7h and 7i are retained in full; only the choice of primary changed. **ρ now never appears
without its 95% CI** anywhere — a bare −0.072 invites exactly the misreading that produced C13.
A3's ρ = −0.097 [−0.489, +0.329] was computed for the first time here and shows the same
imprecision, which strengthens the C14 reasoning rather than weakening it.

### The MDE figure: recomputed, not reinstated

The 0.98× design-sensitivity figure was computed for the paired test, which is primary again, so
it is unblocked. But the bare-call defect logged above touched `phase4_primary.py:143`, so it
was **recomputed** rather than restored. `wilcoxon_1samp_prespec()` now applies the same
exact/approx rule as the analysis. Result: smallest detectable paired shift **0.0292 f_rot_LM**
against an observed HL of **+0.0285** — **0.98×**, unchanged at reporting precision. I had
predicted the compliant call would push the ratio *below* 0.98; it moved in that direction
(reconstructing the old MDE from the old ratio gives ≈0.0291) but by less than the reported
precision, so the sentence stands as written.

**A caveat the fix exposed, reported rather than buried:** 100% of simulated samples fall to the
normal approximation, because resampling with replacement induces tied absolute differences,
while the test actually run on the observed data was **exact**. The simulation therefore
calibrates a marginally different test than the one used. Inherent to bootstrap MDE, not a
defect, and now stated in Methods.

### Endpoint status, enforced in the drafts

f_rot_LM is **secondary**. The primary claim is navigation degradation — A1 worst-rank
p = 0.00206, win ratio 5.60 [2.43, 17.97], log-rank p = 0.000623; A2 complete separation — none
of which is a paired-versus-unpaired question. "Any implication that the paper's strength rests
on the rotation p-value" is now an explicit entry in the claims-deliberately-absent list.

---

## Number injection — drift converted into a build failure (2026-09-13)

Stale arithmetic entered prose three times in this revision, always the same way: a number
hand-copied into a document while its upstream computation was still moving. Twice it was caught
by a verification sweep rather than by design, and once the superseded value had already reached
three documents. Results and Discussion contain more numbers than everything drafted so far, so
the error class is now a build failure rather than something I might notice.

**Pieces.** `results/manifest.csv` (key, value, source, description);
`analysis/build_manuscript.py` (render + fail + lint + `--check` + `--coverage`);
`analysis/retrofit_manuscript.py` and `analysis/retrofit_rules.csv` (migration);
`rendered/` (generated output, mirroring source paths — never edited by hand).

**The direction that matters.** Manifest values trace to artifacts in `results/`, never to the
documents. A manifest populated by reading the prose would make retrofit-then-render a round trip
that proves nothing.

**Final state.** 351 placeholders across four sources, 199 manifest keys, 0 unresolved, 0
hand-typed numerals, and all four rendered files byte-identical to the committed text.

### What it guarantees, and what it does not

Fails on: a placeholder naming a key absent from the manifest; a duplicated manifest row, or one
with an empty value or no source; a literal numeral in rendered prose matching no manifest value
and no structural allowlist pattern.

**It is a coverage check, not a semantic one.** The lint accepts a numeral that appears anywhere
in the manifest, so moving `0.0147` from A1 to A2 would pass. It catches hand-typed and stale
numbers. It does not verify that the right number sits beside the right claim, and it must not be
described as though it does.

**Coverage is 351 of ~395 numerals.** The 44 that remain literal are one-off phrasings whose
values all match manifest entries — covered by the guarantee, not by injection. Each would need a
bespoke single-site rule, which is hand-editing with extra indirection. Stopped deliberately.

### Four defects the build found in its own construction

Recorded because each was invisible to the check that was supposed to catch it.

1. **Wrong key, right value.** Plain value matching bound `Holm p = 0.0147` to `a1.rot.p_paired`,
   the replay correlation `0.98` to `a1.rot.mde_ratio`, and A2's Bonferroni to `a2.rot.holm`. All
   render byte-identically, so `--check` stayed clean and the lint stayed green; the damage would
   have surfaced only when one quantity changed and silently dragged another with it. Fixed by
   refusing to auto-substitute any value carried by more than one key (24 such values, 59 keys),
   and by context-anchored rules where the surrounding words disambiguate.
2. **The ambiguity guard's blind spot.** It only withholds values under *more than one* key. The
   abstract used `100` for the operator's A2 success rate, which had no key at all, so it bound to
   `replay.steps_moved_pct`. Caught by reading the diff, not by the guard. Both operator rates now
   have keys.
3. **Phantom mismatches from line endings.** `core.autocrlf` gives CRLF working files while
   `git show HEAD:` returns LF blobs, so the first `--check` reported all four files as differing.
   The tell was arithmetic: 268 extra bytes against 268 differing lines out of 269. The comparison
   now normalises line endings.
4. **A lint that misreported its own line numbers.** Allowlist patterns containing `\s+` ate
   newlines while masking, shifting every subsequent line number and producing findings with empty
   context. Masking now preserves newlines, and an empty context is reported as a tool bug rather
   than a clean finding.

A fifth, milder: the retrofit converted ASCII hyphens to U+2212 in the CSV because the manifest
stores the typographic minus used in prose. The renderer now spells values per output format —
ASCII for `.csv`, typographic for prose.

### Staleness found by the retrofit

The genuine check was the lint run **before** retrofitting, against artifact-derived values. It
found no stale numbers beyond two already fixed: the hand-rounded ρ interval (`−0.46 to +0.33`
restating a computed `−0.455 to +0.332`, committed separately), and the A2 solver rates, where
`9.2%` (Phase 7a, always-advance replay) and `2.29%/3.12%` (Phase 7e, VLM arms) are both correct
but were quoted without saying which policy produced which. They now carry distinct keys with
distinct sources.

**Retrofit mismatch list: empty.** All four rendered files match their committed text.

---

## Closing brief — measurements, decisions and two defects (2026-09-14 to 2026-09-15)

### Measurements closed

- **7c** closed at 12 shards (15 / 35 / 55 mm/s, both anatomies) by author direction.
- **Pooled 35 mm/s floor** over every artifact-backed draw: A1 99/175 = 56.6% [49.2, 63.7];
  A2 124/175 = 70.9% [63.7, 77.1] (C16). Two A2 smoke draws without artifacts excluded.
- **7d oracle**: best single rotation A1 64.0% [44.5, 79.8], A2 80.0% [60.9, 91.1]; neither above
  the blind policy's own best draw; union 100% selection-inflated (C18).
- **A1 calibre** from VMR's clinical segmentation: LM 4.89 mm, distal LAD 1.73 mm, both within the
  pre-stated ±25% of Dodge et al. The motivation sentence stands.
- **Operator advance speed** from the traces: median 10 mm/s (A1 both arms, A2 wire-only), 5 mm/s
  (A2 overlay); 0–1.3% of steps at 35 mm/s.

### The contradiction that stopped the brief (C17)

35 mm/s had been described everywhere as "the harness default". It is the proximity-gate
substitute translation (`run_coronary.py:708`). The author chose option (a): report the pooled
35 mm/s floor with a corrected rationale, the operator's advance distribution, and the 15 mm/s
figures as the nearest speed-matched comparison; conclude descriptively that the operator clears
the speed-matched blind policy on A1 and not on A2; no margin claim, no operator-versus-baseline
test; state the pooled-versus-single-draw asymmetry.

### Matched blind baseline — costed, NOT run (author to decide)

A blind policy drawing each step's translation from the operator's empirical wire-only
distribution would be the properly matched baseline. Cost, estimated from the observed shard
timings:

- **Shards.** 7 per anatomy to mirror the pooled floor (14 total), or 3 per anatomy (6 total).
- **A1.** Mean advance including non-advancing steps ≈ 16.4 mm/s, so ≈ 58 expected steps against a
  60-step budget; ≈ 4.1–4.3 min per shard, as at 15 and 55 mm/s. 7 shards ≈ 30 min.
- **A2.** Mean advance including non-advancing steps ≈ 7.8 mm/s, so ≈ 49 expected steps against a
  **45-step budget**; ≈ 2.5 min per shard. 7 shards ≈ 18 min.
- **Total** ≈ 48 min of simulation (≈ 21 min at 3 per anatomy) over ≈ 7 foreground calls, plus
  ≈ 20 min to write and probe the runner.
- **Caveat that limits what it could show.** On A2 the matched policy is predicted to be
  budget-limited by construction (≈ 49 steps needed, 45 allowed), so it would largely measure the
  budget rather than the geometry. The operator itself finished A2 wire-only in a median 41 steps
  closed-loop.

### Defect found in committed text: section numbers bound to data keys

The value-matching retrofit (`72b961e`) had rewritten five response-letter headings: `### 1.4` →
`### {{solver.a2_calls_per_nc}}`, `### 1.5` → `### {{cfg.tip_radius}}`, `R1.4` →
`R{{solver.a2_calls_per_nc}}`, `R2.3` → `R{{solver.a2_range_lo}}`, `R2.5` →
`R{{mesh.tube_radius}}`. Every key's value coincided with the section number, so the rendered
letter was byte-identical, `--check` was clean and the lint was green. Changing either solver
figure, the tip radius or the tube radius would have renumbered the letter. Found by reading the
source while editing it, not by any check. Fixed; the retrofit now protects structural positions,
and the build fails on a placeholder in one (probed before being described as a guard).

### Target journal and publishing

IJCARS replaces CBM (guidelines fetched 2026-09-15: structured abstract Purpose / Methods / Results
/ Conclusion; 3,000–5,000 words all-in; 4–6 keywords; single-column editable Word or LaTeX;
"Statements and Declarations"; numbered bracketed references with DOI links; halftone ≥300 dpi,
combination ≥600 dpi, line art ≥1200 dpi; AI-tool use documented in Methods; review model not
stated). Zenodo DOI minting and arXiv posting are the author's to perform.

### A fourth defect, found while answering Reviewer 2's comment 6 (C19)

Building the supplementary biplane table required a per-arm step budget. Taking it from the run
directory name (`biplane_120steps`) would have been an assertion, so the ESM script verifies
budgets from the traces. They disagree.

The monoplane arms behave as a 120-step budget implies: every failure runs to 120 and records
`truncation: true`. The biplane arms do not. Their successes finish in 35–47 steps against
monoplane's 77–90, and the three arms' longest episodes are 120, 40 and 48 steps. Two biplane
wire-only episodes end at 30 and 20 steps — below their own arm's longest of 40 — at 82.8 and
81.9 mm from target, with `terminal: false`. `run_biplane.py` imports `build_env` from
`run_coronary.py`, where the only truncation criterion is `eve.truncation.MaxSteps(n_steps)` — one
fixed count, which cannot end an episode below its arm's maximum. The biplane trace schema records
`terminal` but not `truncation`, so the logs cannot say why those two ended. Episode blocks are
contiguous from step 1, in order, with no duplicates, so they are not the partial episodes an
interrupted run leaves behind.

*Corrected while writing it up: the first draft of this entry, and of C19, said three episodes
ended unexplained over 82–113 mm. The 48-step overlay episode is that arm's longest and so is
explicable as a truncation, and 113.0 mm was its distance. Two episodes, at 81.9 and 82.8 mm. The
build refused the hand-typed numerals in that first draft, which is how the error surfaced; the
figures now come from `results/esm1_nonterminal_episodes.csv` through manifest keys.*

So "seed- and budget-matched", as the submission described that comparison, was not true. Success
counts are no longer compared across those arms, the f_rot_LM contrast is retained as exploratory
with the caveat, and nothing confirmatory is touched — the biplane study has its own seeds and
enters no family, endpoint or calibration figure. Recorded as **C19**; the general rule that
follows is that a budget is verified from traces, never read off a directory name.

### Submission package

`analysis/make_submission.py` assembles `submission/`: Word files exported from `rendered/` with
python-docx (no LaTeX, pandoc or Word on this machine), the generated figures, the numeric-claims
table, a `git archive` snapshot with `CORRECTIONS.md` at its root, and `UPLOAD_STEPS.md`. The
Zenodo DOI and any arXiv posting are left to the authors; the manuscript carries an unresolved
`{{repo.zenodo_doi}}` placeholder, so the build fails on exactly that one key until the DOI exists.

## 2026-09-16 — References, artwork, and a defect the build could not see

### Reference DOIs

`analysis/resolve_reference_dois.py` queries Crossref and accepts a match only on four independent
checks: title similarity >= 0.90 after normalisation, the first author's surname present in the
record, year within one, and a shared distinctive token with the expected venue. The verification
is the point of the script. Crossref's top hit is not trustworthy on its own — a bibliographic
query for the Pocock win-ratio paper returns a ResearchHub record, `10.55277/researchhub.xu35li4p`,
ahead of the European Heart Journal article it paraphrases. Writing that into a manuscript on the
strength of a fuzzy title match would be a fabricated citation.

Eleven references now carry a verified DOI. Three legitimately have none and were not searched: a
plugin cited by URL, an arXiv preprint cited by its identifier, and a vendor announcement. Two
remain **unresolved and are cited without a DOI**: Allard et al. 2007 (the SOFA framework paper,
Stud Health Technol Inform 125:13-18) and Holm 1979 (Scand J Stat 6(2):65-70). Both were re-queried
with full titles and venue variants; neither has a Crossref record that passes. Holm's best
candidates are other authors' papers on sequentially rejective procedures, and Allard's is a
conference-proceedings abstract in a different journal. Nothing was guessed. Evidence per
reference is in `results/reference_dois.csv`.

Dodge 1992 was initially unresolved because our reference carried a truncated title. The full
title, verified against Crossref, is now in the reference list.

### Figures

`analysis/make_figures_1_2.py` re-runs the original Figure 1 and Figure 2 composition at the
journal's resolution; the script that composed them for T-MRB is committed unchanged at
`analysis/legacy/generate_figures.py` as provenance, with a README saying what in it is superseded.
All four of Figure 2's source frames were confirmed present, so nothing had to be re-rendered from
the simulator. The legacy script does run, in the stEVE environment, where its
`from run_biplane import _lm_metrics` resolves; it does not run in the base environment, which has
no pyvista. The new script needs only matplotlib, numpy and Pillow.

All four figures are now 600 dpi RGB TIFF at exactly 174 mm, plus vector PDF (and EPS for 1, 3 and
4). The TIFFs are rendered at the dpi that lands the tight bounding box on 174 mm at 600 dpi, so
they are true 600 dpi renderings rather than upscaled 300 dpi images. Figures 3 and 4 were being
written as RGBA; the alpha channel was already opaque, but the journal asks for RGB and alpha in a
submitted TIFF is a common cause of production rejection, so both are flattened onto white.

Three things were wrong in Figure 2 and are corrected:

1. **The caption claimed the wrong anatomy.** It read "Observation conditions at a mid-LAD wire
   position". The traces say otherwise: at step 20 of seed 2001 the tip is in the left main in all
   three arms (`tip_branch_obs: left_main`), 89.3, 89.1 and 88.6 mm from the mid-LAD target.
   Mid-LAD is where the wire is going, not where it is. The caption now says early left main.
2. **The panels were not a matched instant.** The three monoplane frames are step 20 of three
   separate runs, so the wire is in a similar but not identical position; the original burned
   "seed 2001, step 20" into the image, which reads as though one position were shown in all
   panels. The caption now says so explicitly, and the burned-in titles are gone.
3. **The frames were stretched.** Every render is 512x512, and the original composition drew them
   at `aspect="auto"`, fitting each into a wide axes and distorting the projected anatomy. They are
   now drawn at `aspect="equal"`. This defect is in the figure as published in the T-MRB version.

The biplane panels are also cropped to the render itself, dropping the preview's annotation bars,
one of which read `step=19 dist_to_target=2.4mm seed=2001`. A distance printed into artwork is a
number that cannot be checked against the manifest.

The contrast panel is **kept**. The contrast arm is still reported — Methods section C, the
supplementary-information paragraph, and Table S1 — so the panel documents a condition the paper
describes. It is labelled exploratory in the panel title and in the caption.

Figure 1's parameter line said `N_ep = 25, N_step = 60`. 60 is A1's budget; A2's arms did not share
one (C13), so as a global statement it was false. It now gives the episode count and solver
constants and points to Methods for budgets.

### A stale correction in a file the build does not reach

The build's number-injection guard covers `manuscript/*.md` and `results/reviewer_response.csv`. It
does not cover `results/esm1_supplementary_tables.md`, which is generated by
`analysis/esm_tables.py` — and that file still carried the **withdrawn** version of C19 in its
Table S2 caption: "three biplane episodes ended at 20, 30 and 48 steps". C19 was corrected to two
episodes, because the 48-step episode is its own arm's longest and so is explicable as a
truncation. Every place the guard reaches had been corrected; this one had not, and it would have
shipped as `online_resource_1.docx`.

The caption is now derived from the same `early` list that produces
`results/esm1_nonterminal_episodes.csv`, so the count, the step lengths, the arm's longest episode
and the monoplane budget are all read from the traces and cannot drift again. It renders as "two
biplane episodes ended at 20 and 30 steps, below their own arm's longest episode of 40".

The general lesson is the one C19 already taught in a different form: a number that is not derived
is a number that goes stale. The guard's coverage is a property of its SOURCES list, not of the
submission, and a generated artifact can sit outside it while still being uploaded.

### Statements and Declarations

"Data and code availability" is split into "Data availability" and "Code availability", which are
Springer's own heading names. Both cite the same archive.

### Guidelines

The live guidelines page could not be re-fetched: three attempts on 2026-09-16 each bounced through
the publisher's cookie-consent redirect, ending at `idp.springer.com/authorize`. Every compliance
item was therefore checked against the extraction retrieved on **2026-09-15**, and the submission
package says so. That page does not state the journal's peer-review model, so nothing in the
package assumes one; the manuscript body carries no author names in any case.

## 2026-09-17 — Retarget to CMPB, and two parameter claims that did not survive audit

The target changed to Computer Methods and Programs in Biomedicine, positioned as a computational
environment plus one controlled experiment rather than a benchmark. Preparing it meant auditing
every Methods parameter against the code that produced the data, and two of them failed.

### C20 — our own A2 unequal-budget claim is unsupported

This is the second time the project has got a step budget wrong, and this time in the opposite
direction from C19. There we read a budget off a directory name. Here we read one off the data.

`phase6h_a2_steps.py:48` hardcoded `BUDGET = {"wire_only": 45, "overlay": 62}` under the comment
`# benchmarks/protocol.json`. That file declares a single A2 value, `step_budget: 45`, and
contains no 62 anywhere. `CORRECTIONS.md` C12c repeated the claim and cited both protocol.json
"and the traces". The traces cannot support it either: both A2 arms show 25/25 terminal rows and
**zero** truncation rows, so nothing hit any limit and no limit is observable. `run_asoca.py`
keeps the limit in `stats["n_steps_limit"]` but its `write_summary` never emits it, so the two
`summary.txt` files record only the retraction budget. `ANATOMY_PARAMS["normal12"]` sets
`n_steps = 120`, and the script's own documented full-run invocation passes no `--steps` override
for either mode.

45 and 62 are exactly the longest episode in each arm (ranges 37–45 and 50–62). Under the
hypothesis that both arms ran at 120 that is a tautology; under the hypothesis that the budgets
really were 45 and 62, both arms would have had to land their slowest episode precisely on the
limit while nothing truncated.

The claim is withdrawn. The A2 success comparison is restored, nothing is censored, and the
Methods sentence "within a comparison the only manipulated variable is the observation" holds on
A2 as well as A1 — C12c is marked superseded rather than deleted. **This correction favours us**,
which is exactly why the evidence is set out in full rather than the conclusion alone. What cannot
be proved is what limit was actually passed, because it was never persisted; that is a
reproducibility gap in the original collection and it is stated as one. The fix for future runs is
to write `n_steps_limit` into the summary.

### C21 — the reported timestep was a library default, and the baselines used it

Every operator arm ran at `dt_simulation = 0.001`: `run_ablation.py:628` (the A1 confirmatory
arms), `run_asoca.py:431` (A2), `run_coronary.py:419`. The published 0.006 traces to
`extract_paper_data.py:478`, which read `sofabeamadapter.py` L16 — the class default — and so
could not see a call-site override.

The consequential half is that every Phase-7 baseline, sweep, probe and replay sets
`DT_SIMULATION = 0.006`, on the strength of a comment in `phase7_always_advance.py` asserting
"the VLM arms used dt_simulation=0.006". They did not. `monoplanestatic.py:81` sets
`duration = 1/image_frequency` and `sofabeamadapter.step` runs `int(duration/dt)` sub-steps of
`action x dt` each, so net commanded displacement per environment step is `action x duration`
either way and differs by about 0.9% — but contact is resolved 133 times per step in the arms and
22 times in the baselines. The baselines execute the same policy under coarser physics, and the
solver non-convergence percentages, which are measured by replaying operator actions, were
measured at the coarser setting. Corrected in Methods, Figure 1 and the manifest; disclosed in
Limitations. `PROTOCOL.md` is frozen evidence and is cited rather than edited, and the released
environment still carries 0.006, which is flagged for the authors rather than changed unilaterally.

### What did not move

No statistic was recomputed. `phase6h_a2_steps.py` was re-run after C20 purely to regenerate its
narrative, and its medians, Hodges–Lehmann estimate, interval and p-value came back identical.
That was checked precisely because a correction that silently moved a number would be the serious
case.

### Figures

Four defects, two of them inherited from the published version. Figure 1's metrics logger sat on
the path of the actuation arrow and read as the component driving the guidewire; it is now a
recording sink taking one arrow in and sending nothing on. Figure 2 carried the exploratory
contrast and biplane panels beside the two conditions actually compared; those moved to a new
Supplementary Fig. S1. Figure 3 distinguished arms by hue alone; it now uses colour, line style
and marker, and its annotations are read from the manifest, because the build lints prose and not
artwork. Figure 4's advance-speed bins left the open interval between 30 and 35 mm/s in no bin at
all — no observed value fell there, so no bar was wrong, but the shares were not guaranteed to sum
to 100%, and an assertion now enforces that they do.

Each figure was rendered and looked at after every change. Two of my own passes on Figure 1 made
it worse before it got better, and Figure 4's legend had to be shortened after it overflowed the
axes and clipped mid-word. Reading the rendered image rather than the code is what caught both.

### Verification

References: one duplicate removed (the arXiv preprint of an already-cited article), all 15 now
cited, numbering follows first appearance, figures cited 1, 2, 3, 4, S1 and tables 1, 2 in order.
Abstract 241 words against a 250 limit, main text 3,014 against 3,500. Build: 0 hand-typed
numerals, unresolved on `repo.zenodo_doi` alone. Claims table: 0 literals matching no manifest
value, 0 claims without a producing script. The .docx output was opened and checked rather than
assumed: double spacing on the Normal style, single column, real Word tables.

## 2026-09-17 (later) — The floor at the arms' timestep is 100%, and that breaks the calibration

### The audit

| Artifact | dt | How established |
|---|---|---|
| Operator arms A1 (`v1_current`) | 0.001 | `run_ablation.py:628` |
| Operator arms A2 (`normal12`) | 0.001 | `run_asoca.py:431` |
| Operator arms, old prompt + contrast | 0.001 | `run_coronary.py:419` |
| Biplane arms | 0.001 | `run_biplane.py:48` imports `build_env` from `run_coronary` |
| Scripted traversals (illusion analysis) | 0.001 | `lm_illusion_compare.py:76,114` |
| 7 always-advance, A1 floor | 0.006 | source, **and recorded** in `always_advance_a1_summary.json` |
| 7a always-advance, A2/A3 | 0.006 | source, **and recorded** in the A2/A3 summaries |
| 7c speed sweep | 0.006 | `phase7c_speed_sweep.py:96` — **not recorded in the shards** |
| 7d oracle | 0.006 | inherits `build_env` from 7c (`phase7d_oracle.py:67`) — not recorded |
| 7g non-determinism floor | 0.006 | `phase7g_nondeterminism_floor.py:67` — not recorded |
| 7e solver replay | 0.006 | `phase7e_solver_replay.py:83` — not recorded |
| **7j floor (new)** | **0.001** | source, **and recorded** in `floor_dt001_*.json` |

Only three pre-existing baseline artifacts record their own timestep. For 7c, 7d, 7g and 7e it is
recoverable only by reading source — the same class of gap as the unrecorded A2 step limit in C20,
and why the new script writes `dt_simulation` into its output. The illusion analysis those
scripted traversals fed is not reported in the current manuscript.

### The re-run

`analysis/phase7j_floor_dt001.py`: three repetitions per anatomy, 35 mm/s, same seeds, budgets,
policy and success criterion as 7g. Only dt differs.

| | dt = 0.006 (committed) | dt = 0.001 (arms' physics) | shift | 7g noise band |
|---|---|---|---|---|
| A1 | 56.6% | **75/75 = 100.0%** [95.1, 100.0] | +43.4 pp | 20.0 pp |
| A2 | 70.9% | **75/75 = 100.0%** [95.1, 100.0] | +29.1 pp | 28.0 pp |

Both shifts exceed the measured band. Checked for degeneracy before believing it: every A1 success
takes exactly 26 steps ending 4.58–4.71 mm from target, against a 27-step median at 0.006; every
A2 success takes exactly 11 steps ending 1.76–1.91 mm out, against 11. Nothing terminates within
two steps, nothing reaches budget. Real traversals.

Per sub-step insertion is `action x dt`: 0.21 mm at 0.006, 0.035 mm at 0.001. The coarse timestep
advanced the wire in jumps six times larger between contact resolutions, which is exactly what
decides whether a blind wire tracks the lumen or catches.

### What it does to the paper

**The primary result is untouched.** Overlay versus wire-only compares two VLM arms that both ran
at 0.001; no baseline enters Section 3.1 or 3.2.

**The calibration section is destroyed as written.** A policy that never looks at the image solves
the task completely on both anatomies under the arms' physics. The operator's wire-only draw is
20/25 on A1 — below it. The floor is a ceiling, and every sentence resting on 56.6% / 70.9% is
false, including the answer to Reviewer 1's mandatory revision.

**The noise floor is largely a timestep artifact.** 7g found 4/25 and 2/25 seeds reproducing at
0.006; at 0.001 the step count is identical across all 75 runs. Stated carefully: with success
saturated at 100% this design cannot separate "deterministic" from "saturated", so the honest
claim is that 7g's run-to-run variability does not appear at the arms' timestep — not that the
environment is proven deterministic. It says nothing about the operator's own variability, which
comes from unseeded decoding.

### Not propagated, deliberately

Updating the 35 mm/s row alone would leave the 15 and 55 mm/s rows, Fig. 4a and the oracle at a
timestep the arms never used — worse than either consistent state. 7c (12 shards) and 7d (14
shards) are costed and not started, as instructed.

## 2026-09-17 (final) — Reframed on the control condition, and the scope closed

### The reframe

The 100% floor was not patched into the old calibration section; the paper was rebuilt around it.
The argument now runs: the task is solvable open-loop on both patient-derived anatomies, therefore
it demands no visual information, therefore any degradation observed when visual information is
added is attributable to how the model uses the image rather than to task difficulty. The trivial
floor is the **control condition**, not a caveat — and it is a better foundation for the paper's
actual claim than the framing it replaces. The reading is that a blind policy completes the task
every time, the operator succeeds 20/25 with a wire-only view and 13/25 with overlay, and is
reliably slower with overlay. More visual information made it worse. No difficulty claim survives
anywhere, and the environment is described as a controlled instrument rather than a benchmark.

`manuscript/paper_cmpb.md` was rewritten end to end rather than edited: Results now open with the
control (§3.1), navigation degradation follows as primary, rotation as mechanistic secondary.
Table 2 (calibration) is deleted and the open-loop control folded into Table 1. Figure 4 is
dropped — its speed curve and oracle panels are retired and the orphaned advance-distribution
panel had nothing left to contextualise; the stale `Fig4.*` artifacts were deleted from
`submission/figures/`. Four figures remain: 1, 2, 3 and S1.

### Scope closed, as instructed

The speed sweep is not re-run; Methods states in one sentence that the sensitivity check was
performed at the coarser timestep and is not carried forward, and no partial curve is shown. The
oracle is dropped entirely: its two purposes were a ceiling and per-seed reachability, and an
open-loop policy succeeding on 25/25 seeds in both anatomies establishes both. 7g is not re-run;
the seed-propagation claim now rests on the operator arms' own within-pair correlation
(ρ = −0.072, 95% CI −0.455 to +0.332), measured at dt = 0.001 and unaffected. Every Methods
sentence asserting environment non-determinism on 7g's basis is removed.

### The guard, because marking is not enforcement

105 manifest keys were marked `[SUPERSEDED` rather than deleted — their values are the true record
of what was measured at dt = 0.006, and deleting them would destroy it. But marking alone reduces
"no superseded value reaches the text" from a guarantee to a habit, which is the failure mode this
project keeps designing out. `build_manuscript.py` now **fails** if any source references such a
key. It caught 131 references on its first run and drove the rewrite to completion; the final
build reports one unresolved placeholder, `repo.zenodo_doi`, and zero hand-typed numerals.

### A stale contradiction found while reading

`methods.md` §C still asserted that "the only manipulated variable is the observation" does not
hold on A2, on the basis of unequal step budgets — the claim **C20 already withdrew**. §E had been
corrected and §C missed. Fixed.

### Privacy

`submission/` and `CMPB_FINAL_SUBMISSION/` are untracked: pushing them would publish an
unsubmitted manuscript and a title page carrying a postal address and email. Untracking the built
packages was not sufficient on its own — the *sources* carry the same details, so
`manuscript/title_page.md`, `title_page_cmpb.md` and `cover_letter_cmpb.md` are untracked too, and
`analysis/resolve_reference_dois.py` no longer embeds a personal address in its Crossref
User-Agent. A scan of every remaining tracked text file returns nothing.
