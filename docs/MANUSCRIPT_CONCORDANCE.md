# Manuscript–Repository Concordance and Reproducibility Audit

| | |
|---|---|
| Manuscript | *Vessel overlay slows vision-language-model guidewire navigation in simulated coronary anatomies* (final version as submitted to CMPB, manuscript CMPB-D-26-07590; being resubmitted to IJCARS) |
| Repository audited | `Rugved3-droid/coronav`, `master` @ `b1886b5`, also branch `anonymous-review` @ `3964676` and tag `t-mrb-submitted` |
| Audit date | 2026-10-14 |
| Update | 2026-10-16: the original research records were recovered and added under `artifacts/` (§9). U1, U2, U3, U4, U5, U6, U7, U11 are resolved or answered; U9 is partly resolved. Three new discrepancies were found (U13–U15). |
| Scope | Documentation accuracy, configuration fidelity, metric definitions, artifact availability, environment build and execution. **The manuscript's scientific content and reported numbers were not changed.** |

## 1. Summary

1. **Documentation is now consistent with the manuscript.** Before this
   audit the repository described a different (earlier) study: an "open
   benchmark", three supporting anatomies including A3, `lm_rot_mm` by
   Mann–Whitney as the primary endpoint, success-conditioned navigation
   analyses, and a 0.006 s timestep. All of these are corrected. The earlier
   material is preserved and labelled as superseded (`RESULTS.md` Part 3,
   `PROTOCOL.md` change history, `protocol.json` → `superseded_v1`).
2. **The code ran the superseded timestep.** `coronav/env.py` hard-coded
   `dt_simulation=0.006`. It now defaults to 0.001 s, matching the manuscript,
   and the value is read from `protocol.json` and logged in every trace row.
3. **The promised research artifacts were missing; they are now added
   (2026-10-16 update, §9).** At the 2026-10-14 audit the episode traces,
   analysis scripts, result artifacts and correction record were not in any
   branch, tag or commit reachable on GitHub. They were later found on the
   machine where the study ran, and are now in `artifacts/` and
   `CORRECTIONS.md`. The original analysis scripts, re-run on them, reproduce
   every manuscript statistic checked (§9.2). The ASOCA-derived traces are
   committed as redacted copies (§9.1).
4. **The environment works for A1.** The Docker image did not build as
   published (Debian 11 archive move). After a one-line apt-source fix it
   builds, passes `check_install.py`, and runs. In the container, the
   open-loop control on A1 at 0.001 s reproduced the manuscript's open-loop
   A1 figures (§5.3). A2 could not be prepared from the repository (U6).
   The original A2 preparation script is now in `artifacts/harness/pilot/`,
   and, re-run on the ASOCA archive, it reproduces the A2 mesh exactly (§9.3).

## 2. Concordance table: manuscript claims vs repository

Status key: **match** means the repository now states the manuscript value;
**verified** means it was independently checked against repository files or
by execution; **unverifiable** means it is transcribed only, because the
producing artifact is absent.

### 2.1 Design and configuration

| Manuscript item (section) | Manuscript | Repository before | Repository now | Status / evidence |
|---|---|---|---|---|
| Purpose (Abstract, §4) | instrument for studying VLM visual behaviour, not a benchmark | "Open benchmark" (README, setup.py, package docstring) | instrument; benchmark wording removed | match |
| Retained anatomies (§2.2) | A1 VMR 0066, A2 ASOCA Normal_12 | A1, A2, **A3 all supporting** | A1, A2 retained; A3 excluded | match |
| A3 (§2.2) | excluded: generated 2.5 mm tube, solver non-convergence, strongest raw result (paired p = 3.34e-06) | used as "cross-anatomy replication" (RESULTS.md); runnable by default | `status: excluded` in protocol.json; runner refuses without `--allow-excluded`; history kept in RESULTS.md Part 2/3 | match; tube radius 2.5 mm verified in `scripts/download_asoca.py` |
| A1 mesh (§2.2) | single connected open surface, 81 boundary edges | — | stated in A1 README | **verified**: 1 component, 7990 vertices, 15897 triangles, 81 boundary edges, 0 non-manifold edges |
| Overlay drawn from the collision mesh (§2.3) | yes | `.vtp` used for the mask, `.obj` for collision | unchanged | **verified**: the `.vtp` and `.obj` have identical vertices (max diff 0.0) and faces |
| A2 mesh (§2.2) | 9 boundary edges, 6 non-manifold edges | — | — | **verified 2026-10-16** on the original A2 mesh: 1 component, 3350 vertices, 6689 faces, 9 boundary edges, 6 non-manifold edges (§9.3) |
| SOFA / BeamAdapter (§2.1) | v23.06 | v23.06 | v23.06 | verified in Dockerfile and built image |
| J-tip (§2.1) | radius 1.5 mm, angle 0.2π | same (`env.py`) | same | verified (code) |
| LCP (§2.1) | Gauss–Seidel, ≤ 2000 it, tol 1e-4 | same (`coronary_sim.py`) | same | verified (code) |
| Contact / alarm (§2.1) | 0.3 / 0.5 mm | same | same | verified (code) |
| Friction (§2.1) | 0.001 | same | same | verified (code) |
| **Timestep (§2.1)** | **0.001 s for every retained arm and result** | **0.006 s** in `env.py` (hard-coded), `coronary_sim.py` default, `protocol.json`, `PROTOCOL.md` | 0.001 s everywhere, single source `protocol.json`, logged per row | corrected; **U4 answered:** the original harness used 0.001 s (`artifacts/harness/pilot/run_ablation.py:628`, `run_asoca.py:431`, `run_coronary.py:419`) |
| Image (§2.3) | 512 × 512 grayscale, AP cranial 40° | same | same | verified (code) |
| Conditions (§2.3) | wire-only vs overlay, identical physics | renderer supported both, **runner ran `wire_only` only** | `run_benchmark.py --mode wire_only overlay` | corrected |
| Operator (§2.3) | Claude Sonnet 4.6, SDK v0.72.0, stateless | `claude-sonnet-4-6`; SDK **unpinned** in Dockerfile, `>=0.72.0` in setup.py | Dockerfile pins `anthropic==0.72.0` | corrected; resolved version verified in the built image |
| State string (§2.3) | distance, trend, retractions remaining, no-progress counter | same (`env.py`) | same | verified (code) |
| Proximity gate (§2.3) | < 25 mm and closing: rotate → advance 35 mm/s | same (`env.py`, `prompts.py`) | same; tested against protocol.json | verified (code) for A1. **A2 used 15 mm** (U14, §9.4) |
| Failed API call (§2.3) | null action, consumes one step, no retry | same (`env.py`) | same | verified (code) |
| Open-loop control (§2.4) | 35 mm/s advance, never rotate/retract, 3 reps/anatomy, 0.001 s | **absent** | `--operator open_loop` (`coronav/operator/open_loop.py`), a re-implementation | added; executed (§5.3). The original A2 open-loop run used a 45-step limit, not 120 (U15) |
| Success (§2.5) | tip within 5 mm of target within the step limit | threshold 5.0 mm; but `success = terminal and not truncation` | `episode_outcome()` counts a target reached on the final step | threshold verified; see U5 |
| Step limits (§2.6) | A1 60 both arms; **A2 120 both arms** | A1 60; **A2 45 (wire_only), overlay 62 per PROTOCOL.md** | A1 60; A2 120 | corrected to the manuscript; **U3 answered:** the harness passes 120 to both A2 arms (`run_asoca.py:122`); 45/62 are the longest observed episodes (§9.4) |
| Episodes (§2.6) | 25 seed-matched per arm | 25 seeds per anatomy | same | **verified** against the traces: A1 5001 + 11i, A2 3001 + 11i (U11) |
| Seeds vs decoding (§2.6) | seeds fix reset only; decoding unseeded | not stated | stated in README, PROTOCOL, protocol.json, run_meta.json | match; verified that `ClaudeOperator` sets no temperature or seed |
| Exclusion (§2.6) | zero valid actions = non-attempt | "all rows fail API/parse" (same rule); but `lm_metrics` also drops episodes with no LM movement | documented; `episode_outcome()` applies the manuscript rule | see §4 |
| Primary endpoint (§2.5, §2.7) | navigation over all episodes; worst-rank, win ratio, log-rank (A1); paired Wilcoxon + HL (A2) | primary = `lm_rot_mm` MWU; steps for successes only | documented as manuscript; analysis code **absent** (U2) | match (docs); not regenerable |
| Secondary endpoint (§2.5) | `f_rot_LM`, dimensionless [0,1]; paired Wilcoxon + Holm; MWU sensitivity | `lm_rot_mm` primary | `f_rot_LM` secondary, code name `lm_rot_mm` explained | match; definition verified (§4) |
| Endpoint hierarchy post hoc; plan retrospective (§2.5, §2.7) | disclosed | called "pre-specified" | disclosed; "pre-specified" withdrawn | match |
| Analysis plan frozen and released (§2.7) | released with the code | absent | `artifacts/analysis/PRESPEC.md` | **added (U2)** |
| Number-to-artifact manifest, build check (§2.8) | exists | absent | `artifacts/results/manifest.csv`, `artifacts/analysis/build_manuscript.py` | **added (U2)**; the check needs the manuscript sources, which are not released (§9.2) |

### 2.2 Results

All values below are now stated in `RESULTS.md` Part 1 exactly as in the
manuscript. "Before" shows what the repository said previously, if anything.
The Status column records the 2026-10-14 audit. **Since the 2026-10-16
update, every value marked "unverifiable" here has been regenerated from the
original traces by the original scripts; see §9.2.**

| Result (section) | Manuscript | Repository before | Status |
|---|---|---|---|
| Open-loop A1 (§3.1, Table 1) | 75/75; 26 steps; 4.58–4.71 mm | absent | match; **independently re-run, §5.3** |
| Open-loop A2 (§3.1) | 75/75; 11 steps; 1.76–1.91 mm | absent | match; unverifiable (A2 not available) |
| Wilson CI (§3.1) | 95.1–100.0 | absent | match; arithmetic check: Wilson lower bound for 75/75 = 0.9513 ✓ |
| A1 success (§3.2) | 20/25 vs 13/25, Fisher p = 0.0718 | 20/25 vs 13/25, Fisher p = 0.072 | match; arithmetic check: two-sided Fisher exact on 20/25 vs 13/25 = 0.0718 ✓ |
| A1 worst-rank (§3.2) | W = 47.5, p = 0.00206, rank-biserial +0.708 | absent | match; unverifiable |
| A1 win ratio (§3.2) | 5.60 (2.43–17.97); 470 W / 84 L / 71 T | absent | match; arithmetic check: 470/84 = 5.595 → 5.60 ✓; 470 + 84 + 71 = 625 = 25² ✓ |
| A1 log-rank (§3.2) | χ² = 11.705, p = 0.000623 | absent | match; arithmetic check: P(χ²₁ > 11.705) = 0.000623 ✓ |
| A2 navigation (§3.2) | 25/25 both; median 41 vs 56; HL +14.5 (+13.0 to +16.5); p = 1.25e-05; ranges 37–45 vs 50–62 | absent | match; arithmetic check: with all 25 differences the same sign, the Wilcoxon normal approximation gives p = 1.23e-05 (no corrections) to 1.31e-05 (continuity correction), bracketing the reported 1.25e-05, so the value is consistent with the stated "normal approximation where ties" rule (the exact test would give 5.96e-08); exact value needs the data |
| A1 f_rot_LM (§3.3) | 0.1452 vs 0.1749; 20/25 seeds higher; W = 73.0, p = 0.0147, Holm 0.0147; r_rb +0.551; U = 496.0, p = 0.000384; HL +0.0285 (+0.0068 to +0.0440) | medians match; "p = 0.0004" MWU presented as primary | match; MWU 0.0004 ≈ 0.000384 (rounding); arithmetic check: matched-pairs r_rb = 1 − 2·73/325 = 0.551 ✓ |
| A2 f_rot_LM (§3.3, Table 1) | 0.0000 vs 0.0454; 0 vs 37 rotate intents (16 episodes); 16 informative pairs, W = 0.0, p = 0.000482, Holm 0.000965; unpaired p = 2.95e-06 | "p = 0.000003" MWU presented as primary | match; 0.000003 ≈ 2.95e-06 (rounding); arithmetic check: Wilcoxon normal approximation with continuity correction on 16 same-sign pairs gives p = 0.000482403 ✓, and Holm 2 × 0.000482403 = 0.000965 ✓ |
| Holm, A1 (§3.3) | 0.0147 | — | arithmetic check: Holm step-down on {0.000482, 0.0147} gives {0.000965, max(0.000965, 0.0147) = 0.0147} ✓ |
| Within-pair correlations (§2.6) | −0.072 (−0.455 to +0.332); −0.074 (−0.456 to +0.330) | absent | match; unverifiable |
| Transmission failures (§3.4) | 1.33% vs 0.00%, p = 2.4e-06; A2 p = 0.268; log-rank after discounting p = 0.000157 | absent | match; unverifiable |
| Biplane (§3.4) | p = 0.375; 2 early-ended episodes | absent | match; unverifiable; biplane runner not in the repository |
| A3 (§2.2) | paired p = 3.34e-06, excluded | MWU p = 0.000009, supporting | A3 excluded; old value archived and explained |
| Prompt variants (§3.4) | exploratory, Supplementary Material | V1–V4 table as "ablation" | archived as exploratory; **not checked** against the Supplementary Material, which is not in the repository (U7) |
| Withdrawn 0.006 s baselines (§2.1, §4) | "roughly half to two-thirds"; withdrawn; C21–C22 | not present | described as withdrawn; `CORRECTIONS.md` missing (U2) |

The arithmetic checks recompute a reported statistic from other reported
numbers, for example a p-value from its test statistic. They confirm the
manuscript is internally consistent. They are **not** a reproduction from
data.

### 2.3 Remaining repository statements that differ from the manuscript

None of the numerical results presented as manuscript findings in the
repository differ from the manuscript. The open contradictions are in the
design record (U3, U4) and in the availability statements (U1, U2, U6),
listed in §6.

## 3. Search for obsolete claims (final pass)

Searched the whole tree (excluding `.git`) for: `0.006`, `0.0004`,
`0.000003`, `0.000009`, `3e-6`, `9e-6`, `a3`/`A3`, `benchmark`,
`all three`, `pre-specified`, `T-MRB`, `Transactions on Medical Robotics`,
`step_budget.*45`, `62`, `r = 0.587`, `48.0`, `58.0`, `Gharleghi.*2022`,
`dib.2022`. Every remaining hit is in one of these:

- an explicitly labelled archival or superseded section (`RESULTS.md` Part 3,
  `PROTOCOL.md` change history, `protocol.json` → `superseded_v1`);
- an explanation of why the value is superseded (README, this document);
- the excluded-A3 machinery (`download_asoca.py`, `--allow-excluded`);
- the generic word "benchmark" in file names (`benchmarks/`,
  `run_benchmark.py`), kept for backward compatibility of commands.

## 4. Metric audit: is `lm_rot_mm` the manuscript's `f_rot_LM`?

Manuscript (§2.5): *"the fraction of the wire's total change in distance to
target during left-main traversal occurring on steps whose intended action is
a rotation … dimensionless and bounded in [0, 1]; numerator and denominator
are distance-change sums over the same phase, so episode length cancels.
Rotate-intent counts during the left-main phase were also recorded."*

Implementation (`coronav/metrics.py: lm_metrics`, arithmetic unchanged by this audit):

| Component | Implementation | Agrees with manuscript? |
|---|---|---|
| Numerator | Σ `|tip_target_dist_after − tip_target_dist|` over valid LM-phase rows with rotate intent | yes |
| Denominator | the same sum over all valid LM-phase rows | yes ("same phase") |
| Per-step absolute value vs net change | per-step absolute. A net-change definition would not be bounded in [0, 1] | yes: only per-step absolute values give the stated [0, 1] bound (tested) |
| Units | mm / mm → dimensionless. The `_mm` suffix is a misnomer | yes; the name is documented, not renamed, so traces stay compatible |
| Rotate intent | `is_rotate_step`, else `intended_direction ∈ {rotate_cw, rotate_ccw}`, recorded **after** the proximity-gate override | consistent with "intended action" |
| Phase boundary | `tip_branch_obs == "left_main"`, where the branch is the nearest centerline segment to the **post-step** tip (`_classify_branch(tip_after)`); `left_main` is the trunk segment before the first detected bifurcation (`build_branch_tree`, junction radius 3 mm) | the manuscript does not specify pre- vs post-step; documented in PROTOCOL.md |
| Valid rows | `api_ok and parse_ok` | consistent with the failed-call handling |
| Rotate-intent count | `lm_rot_steps` | yes |
| Undefined case | returns `None` if there are no valid rows **or** zero LM-phase distance change | stricter than the manuscript's non-attempt rule; see below |

**Conclusion.** `lm_rot_mm` and `f_rot_LM` are the same mathematical
quantity (same numerator, denominator, units and interpretation). The name
differs; the quantity does not. On the original traces, `lm_metrics()` gives
the same per-episode values as the manuscript's analysis
(`artifacts/analysis/phase5_multiplicity.py:91`, `f_rot_lm`) to within the
6-decimal rounding of `phase4_pairs_a1.csv`, and the same medians (§9.2).

**Update 2026-10-16: the "verbatim port" description is not accurate**,
although nothing published depends on the difference:

- The original `run_biplane.py:_lm_metrics()`
  (`artifacts/harness/pilot/run_biplane.py:378`) pools the sums over all
  episodes of an arm and returns one ratio per arm. It scores success as
  "last row terminal", with no truncation check. `lm_metrics()` works per
  episode. The manuscript's statistics come from the per-episode `f_rot_lm`
  in `phase5_multiplicity.py`, which `lm_metrics()` matches exactly.
- **Phase boundary:** the original harness classifies `tip_branch_obs` from
  the **pre-action** tip (`tip_obs`; `artifacts/harness/pilot/run_ablation.py:774`
  for the A1 arms, `run_asoca.py:672` for A2, `run_coronary.py:663`), and the frozen plan locks that convention
  (`artifacts/analysis/PRESPEC.md` §2.2). This repository's environment
  classifies from the **post-step** tip (`coronav/env.py:322`). On the
  released traces the two conventions cannot differ, because the field is
  read, not recomputed. **New runs made with this repository use a slightly
  different left-main phase from the manuscript** (U13).

Two behaviours of the legacy code are documented and covered by tests, but
deliberately **not** changed in `lm_metrics()`:

1. `lm_metrics()["success"]` is `terminal and not truncation`. In stEVE
   (`eve/terminal/targetreached.py`, `eve/truncation/maxsteps.py`, checked in
   the built image) both flags are set when the target is reached on the last
   allowed step. That case is scored as a failure, which contradicts §2.5.
   New code uses `episode_outcome()`, which counts it as success. Whether the
   original analysis had this behaviour is unknown, and only the original
   traces can show whether any retained episode reached the target on its
   final step (U5).
2. `episode_metrics_from_trace()` drops episodes with no LM-phase movement.
   The old `report.py` then computed success rates over that reduced set.
   `report.py` now reports navigation over all attempted episodes.

## 5. Validation evidence (what was actually executed)

Environment: Linux container, Docker 29.8.2, network via an HTTPS proxy. A
scratch copy of the Dockerfile adding only the proxy CA certificate was used
to build; the repository Dockerfile itself carries no environment-specific
changes.

### 5.1 Docker build

| Build | Result |
|---|---|
| Unmodified `master` Dockerfile | **failed** at `apt-get install`: 404 for `debian-security` bullseye packages. Confirmed upstream: `security.debian.org` also returns 404 and `archive.debian.org` returns 200 (Debian 11 LTS ended Aug 2026). Anyone building today hits this. |
| `master` code + apt-archive fix only | built; `check_install.py` all OK (A2/A3/API-key warnings only) |
| This branch | built; `check_install.py` all OK, including the new checks "protocol.json timestep is 0.001 s" and "coronav.env default timestep matches protocol.json" |

Resolved versions in the verified image: Python 3.8.20, SOFA v23.06.00,
BeamAdapter v23.06, stEVE `f909e7122d846a3c2fec91eedddaa0ba88b6391d`,
anthropic 0.72.0, numpy 1.24.4, scipy 1.10.1, pillow 10.4.0, pyvista 0.44.2,
vtk 9.3.1, gymnasium 1.1.1.

### 5.2 Unit tests

`tests/` holds 17 deterministic tests on hand-built synthetic rows, run on
Python 3.13 (host) and Python 3.8 (container): **17 passed** on both. They
cover the f_rot_LM definition (hand-computed value, absolute vs net change,
scale invariance, [0, 1] bounds, invalid-row exclusion, field precedence,
undefined cases), the final-step success edge case, navigation outcomes and
non-attempts, trace round-trip, and protocol/code consistency (timestep, step
limits, A3 status, both conditions, harness constants). Run against `master`,
all 5 protocol tests **fail**, so they detect the defects corrected here.
*Synthetic tests check definitions only. They are not a reproduction of any
experiment.*

### 5.3 Open-loop control, A1, executed in the container

Command (in the `coronav:audit` image built from this branch), run three
times with different `--out-dir`:
`python3 benchmarks/run_benchmark.py --operator open_loop --anatomy a1`

| | Manuscript (§3.1, Table 1) | This repository, new run (2026-10-14) |
|---|---|---|
| Reached target | 75/75 | **75/75** |
| Steps to target | 26 in every episode | **26 in every episode** |
| Final distance to target | 4.58–4.71 mm | **4.582–4.707 mm** |
| Timestep (from trace rows) | 0.001 s | 0.001 s |
| Non-advance actions | none (policy definition) | 0 |

Wall time was about 16–17 s per episode. The three repetitions gave identical
traces (650 rows each): the simulator is deterministic for a fixed seed, and
this operator has no stochastic component.

**Interpretation.** This is the one manuscript result this repository has
independently re-run, and it agrees at the precision reported. It shows that
the ported environment, at 0.001 s, reproduces the open-loop solvability
finding on A1. It says **nothing** about the VLM arms, A2, or any statistic
that depends on the operator. The open-loop operator here is a
re-implementation (`coronav/operator/open_loop.py`), not the original script.
The traces are kept outside the repository: they are new runs, not the
manuscript's artifacts.

Additional integration checks in the same image (open-loop, so no cost):
`--mode wire_only overlay` in one process (2 seeds each, both 26 steps, which
exercises the overlay renderer and a second `build_env()`); `report.py
--run-dir`, `--compare` and two-mode layouts; A3 refused without
`--allow-excluded` (exit code 1); `--dry-run` with both modes.

Small finding: inside Docker, `run_meta.json` records `git_commit:
"unknown"` because the image contains no `.git`. Record the image tag or
commit yourself when running in a container.

### 5.4 Not executed (and why)

- **VLM operator arms (any anatomy).** These make paid Anthropic API calls,
  which were not authorised for this audit. Command to run when approved:
  `python3 benchmarks/run_benchmark.py --operator claude --anatomy a1 --mode wire_only overlay`
  (25 seeds × 2 arms × ≤60 steps ≈ ≤3000 calls). Because decoding is
  unseeded, such a run is a **new sample**, not a replay, and is expected to
  differ episode by episode.
- **Anything on A2.** The ASOCA data needs registration, and the preparation
  pipeline is missing (U6).
- **The manuscript's confirmatory statistics.** The analysis scripts and the
  traces are missing (U1, U2).

## 6. Unresolved issues

Severity: **Blocker** means the manuscript makes an availability claim the
repository does not support. **High** means a material contradiction or
reproducibility gap. **Medium/Low** means it should be fixed but does not
affect the claims.

| ID | Severity | Issue | What resolves it |
|---|---|---|---|
| U1 | ~~Blocker~~ **Resolved 2026-10-16** | Original **episode traces** were not in the repository. | Added under `artifacts/traces/` (19 arms + run summaries; §9.1). A1 and other VMR arms are byte-identical. A2/A3 are redacted copies without ASOCA coordinates; original hashes are in `artifacts/REDACTIONS.tsv`. |
| U2 | ~~Blocker~~ **Resolved 2026-10-16** | Analysis scripts, frozen plan, manifest and build check, result artifacts, `CORRECTIONS.md` were absent. | Added: `artifacts/analysis/` (incl. `PRESPEC.md`, `build_manuscript.py`), `artifacts/results/` (incl. `manifest.csv`), `CORRECTIONS.md` (C1–C22). Regenerated with `python artifacts/reproduce.py --check` (§9.2). The build check needs the unreleased manuscript sources. |
| U3 | High → **Answered** | A2 step limit: 120 or 45/62? | **120 in both arms.** `artifacts/harness/pilot/run_asoca.py:122` sets `n_steps = 120` for Normal_12, used for both modes; no A2 trace row has `truncation` true; 45 and 62 are the longest observed episodes (`CORRECTIONS.md` C20). Caveat: the harness never wrote the limit to its summary, so 120 is the configured default, not a recorded value. Consistent with the manuscript. |
| U4 | High → **Answered** | Timestep of the original operator arms. | **0.001 s.** `run_ablation.py:628` (A1 confirmatory arms), `run_asoca.py:431` (A2), `run_coronary.py:419` all build `CoronaryBeamAdapter(..., dt_simulation=0.001, ...)`. Consistent with the manuscript; the 0.006 s value came from the port. |
| U5 | Medium → **Answered** | Final-step success; verbatim-port claim. | No confirmatory episode has `terminal` and `truncation` both true. The original analysis used the same legacy rule as `lm_metrics()` (`phase3_selection_bias.py:66`, `phase5_multiplicity.py:125`, `phase6h_a2_steps.py:75`), so no confirmatory number is affected. **Three exploratory V2 episodes** reached target on their final step and are counted as failures in Supplementary Table S1 (§9.4). The port is not verbatim (§4). |
| U6 | High → **Resolved for the original harness** | A2 not preparable. | `artifacts/harness/pilot/clip_asoca_left.py` + `asoca_adapter.py` reproduce the A2 mesh exactly from `ASOCADataAccess.zip` (§9.3; reference hashes in `artifacts/README.md`). Remaining gap: this repository's `coronav` package expects `paths/*.pth` centrelines, which A2 never used; a converter is still needed to run A2 through `run_benchmark.py`. |
| U7 | Medium → **Resolved** | Supplementary Material absent. | `artifacts/supplementary/SupplementaryMaterial.docx` (metadata-redacted copy); its tables are generated by `artifacts/analysis/esm_tables.py` and regenerate exactly. Biplane harness: `artifacts/harness/pilot/run_biplane.py`. The archived prompt-ablation figures in `RESULTS.md` §3.2 differ from Table S1 in places; see §9.4. |
| U8 | Low | Author metadata: `CITATION.cff` has no top-level `title`/`authors` (required by CFF 1.2.0), `LICENSE` has an empty copyright holder, and the README BibTeX author is `X,Y,Z`. These look deliberate (recent commits removed them), so they were left alone. | Author decision. Complete them after any double-blind phase. |
| U9 | Medium → **Partly resolved** | Original environment not recorded. | stEVE: upstream `f909e71` plus three local commits that only add `coronary_fixture/` (`artifacts/environment/steve_commit.txt`) — the same `eve/` as the Docker pin. The original conda env still exists; its `pip freeze` (taken 2026-10-16, not at run time) shows the same versions as the verified image (anthropic 0.72.0, numpy 1.24.4, scipy 1.10.1). No contemporaneous record exists. |
| U10 | Low | The A1 clinical segmentation diameters (LM 4.89 mm, distal LAD 1.73 mm; §1) were not verified. | Optional: a script that measures them from the bundled mesh. |
| U11 | Low → **Resolved** | Seeds. | The traces' seeds equal `protocol.json`: A1 5001 + 11i, A2 3001 + 11i, 25 each. |
| U12 | Low | The manuscript says the materials are "archived". There is no archival snapshot (DOI). | Create a GitHub release and a Zenodo DOI once U1/U2 are resolved, and cite it in the manuscript. |
| U13 | Medium (new) | **Left-main phase boundary differs between the original harness and this repository.** Original: pre-action tip (`run_ablation.py:774`, `run_asoca.py:672`); this repository: post-step tip (`coronav/env.py:322`). | Decide whether `coronav/env.py` should follow the original convention, as `PRESPEC.md` §2.2 locks it. Not changed here. Affects new runs only. |
| U14 | Medium (new) | **A2 proximity gate was 15 mm, not 25 mm.** Manuscript §2.3 gives one value (< 25 mm). The A2 harness used 15 mm (`run_asoca.py:120`, pre-registered in `PREREGISTRATION.txt:110`; A2 `summary.txt`: "< 15mm"); A1 used 25 mm (`run_ablation.py:67`). `protocol.json` says 25 for A2. The gate never suppressed a rotation in either A2 arm, but the threshold appears in the A2 prompt text (`run_asoca.py:235`). | Author decision: correct manuscript §2.3 (e.g. "25 mm for A1, 15 mm for A2") and `protocol.json`. Not changed here. |
| U15 | Low (new) | **A2 open-loop control ran with a 45-step limit**, not the operator arms' 120 (`artifacts/analysis/phase7j_floor_dt001.py:66`; `floor_dt001_a2.json` `"budget": 45`). Manuscript §2.4 says "the same step limits as the operator arms". Every open-loop episode reached target at step 11, so the result (75/75) is unaffected. | Author decision: adjust the §2.4 wording, or re-run at 120 (the outcome cannot change). Not changed here. |

## 7. Corrections made in this audit

| File | Change | Why |
|---|---|---|
| `README.md` | Repositioned as an instrument; two retained anatomies plus excluded A3; design, endpoints, final results summary; three-part reproducibility status; open-loop and two-condition commands; A2 preparation caveat; corrected ASOCA citation; removed outdated "0.145 median" and n = 9 framing (archived in RESULTS.md); install instructions kept | E, A, B, §4, §7 of the brief |
| `RESULTS.md` | Part 1 final manuscript results with provenance; Part 2 A3 exclusion; Part 3 archived analyses verbatim with how each relates to the final results | A, B, C |
| `PROTOCOL.md` | v2.0: 0.001 s, A2 120, both modes, open-loop control, primary/secondary endpoints, exact f_rot_LM definition and phase boundary, exclusions, implemented vs missing table, change history, U3 flagged | B, C, D |
| `benchmarks/protocol.json` | v2.0 values; A3 `status: excluded`; operator, open-loop and endpoint blocks; `superseded_v1` record | D; runner reads it |
| `coronav/env.py` | `DT_SIMULATION = 0.001`, `build_env(dt_simulation=…)` instead of hard-coded 0.006; `dt_simulation` logged per trace row; docstring fixes | D: the code ran the superseded timestep |
| `coronav/sim/coronary_sim.py` | default `dt_simulation` 0.006 → 0.001 | D |
| `coronav/metrics.py` | docstrings: f_rot_LM definition, misnomer, legacy success and exclusion behaviour; new `episode_outcome()` / `outcomes_from_trace()`; `lm_metrics()` arithmetic **unchanged** | C; primary endpoint needs all-episode outcomes |
| `coronav/operator/open_loop.py` (new), `operator/__init__.py` | open-loop control operator | §2.4 control was not runnable |
| `benchmarks/run_benchmark.py` | `--mode` (both arms), `--operator open_loop`, dt from protocol, A3 guard (`--allow-excluded`), `run_meta.json` labelling new runs, success = target reached | B, D, E |
| `benchmarks/report.py` | removed hard-coded outdated "paper baseline" (A1 p = 0.0004, A2 3e-6, A3 9e-6); navigation over all episodes; MWU labelled as sensitivity only; states that confirmatory analyses are absent; finds per-mode traces | B, C |
| `examples/quickstart.py` | removed outdated baseline line; prints reached-target and f_rot_LM; smoke-test caveat | B |
| `scripts/check_install.py` | A3 no longer treated as installable; A2 layout checks; timestep consistency checks | D |
| `scripts/download_asoca.py` | default installs A2 only; A3 marked excluded; layout validation with "NOT READY" message; corrected citation | A, U6 |
| `docker/Dockerfile` | apt sources → archive.debian.org (build was broken); `anthropic==0.72.0`; stEVE pinned to the verified commit; comments | environment reproducibility |
| `docker/README.md` | verification status, open-loop command, both-mode commands, A2 only | consistency |
| `setup.py`, `coronav/__init__.py` | description wording; stEVE commit pin | E |
| `CITATION.cff`, `LICENSE` | ASOCA reference corrected to the one cited in the manuscript (Sci Data 2023, doi:10.1038/s41597-023-02016-2); the previous reference (Data in Brief 2022, "Annotated Stenoses Coronary Arteries") does not match the manuscript and its title is not the ASOCA name | provenance |
| `data/anatomy/a1_vmr0066/README.md` | verified topology, timestep, both modes (documentation only; no data file changed) | A, D |
| `.gitignore` | ignore `data/anatomy/a2_asoca_n12/` and `a3_asoca_n5/` (registration-gated data, previously not ignored although the generated README claimed it was); allow `artifacts/**/*.jsonl` | licence compliance; U1 |
| `tests/` (new) | 17 synthetic unit tests | §6 of the brief |
| `docs/MANUSCRIPT_CONCORDANCE.md` (new) | this document | §7 of the brief |

**Unchanged on purpose:** all anatomy data files (`.obj`, `.vtp`, `.pth`,
licence), `coronav/prompts.py`, `coronav/operator/claude.py`, the
control-loop logic in `run_episode()`, and the `lm_metrics()` arithmetic.

**Changes in the 2026-10-16 update** (branch `artifacts/original-research-records`):

| File | Change |
|---|---|
| `artifacts/` (new) | original traces, analysis scripts, frozen plan, results, manifest, harness, Supplementary Material, environment record; `CHECKSUMS.sha256`, `PROVENANCE.tsv`, `REDACTIONS.tsv`, `ARMS.tsv`, `README.md`, `reproduce.py` (§9) |
| `CORRECTIONS.md` (new) | the correction record, C1–C22, as last committed on `revision-cbm` |
| `.gitattributes` (new) | `artifacts/` and `CORRECTIONS.md` stored without end-of-line conversion |
| `.gitignore` | `!artifacts/results/` (the generic `results/` rule was hiding it) |
| `README.md`, `RESULTS.md`, this document | reproducibility status, provenance notes, issue status |

**Unchanged on purpose in this update:** all code under `coronav/`,
`benchmarks/`, `scripts/` and `tests/`; `benchmarks/protocol.json` (U14 is
an author decision); all numbers in `RESULTS.md` Part 1.

## 8. How to regenerate the manuscript statistics

From the repository root (Python ≥ 3.10 with numpy, scipy, statsmodels,
matplotlib; no simulator, network or API key):

    sha256sum -c artifacts/CHECKSUMS.sha256      # the records are intact
    python artifacts/reproduce.py --check        # re-run the analyses, diff against committed outputs
    git checkout -- artifacts/results            # restore the committed outputs

`artifacts/README.md` maps each manuscript result to its script and output
file. §9.2 gives the outcome of doing this on 2026-10-16.

## 9. Recovery and verification of the original records (2026-10-16)

### 9.1 What was found and added

The records were on the machine where the study ran:

- the run folders and harness in `D:\steve\pilot\` and
  `D:\steve\stEVE\coronary_fixture\` (June–July 2026);
- the analysis workspace, a local, never-pushed branch `revision-cbm` of this
  repository (`20c872c`, 2026-09-18). It holds the analysis scripts, results,
  manifest, `PRESPEC.md` and `CORRECTIONS.md`, and copies of the 19 trace
  files. Those copies were LF-normalised by git, so the run folders were used
  as the byte-for-byte source instead.

The Supplementary Material is `CMPB_FINAL_SUBMISSION/SupplementaryMaterial.docx`
(2026-09-18). The file name the manuscript workflow used,
`Supplementary_Material_CMPB.docx`, no longer exists on disk.

Everything added is listed with its original path and date in
`artifacts/PROVENANCE.tsv`, with hashes in `artifacts/CHECKSUMS.sha256`.

**Redacted copies (12 files, `artifacts/REDACTIONS.tsv`):**

- **ASOCA licensing.** The A2/A3 traces and four A2/A3 baseline files carry
  patient-space coordinates in every row: tip position before and after each
  step, the target point, and the path of the rendered ASOCA frame. These
  were removed. Each JSONL row was checked to be otherwise identical to the
  original. The originals are kept off-repository, identified by SHA-256.
- **Anonymous review.** An author name in `PREREGISTRATION.txt` and the
  `lastModifiedBy` field of the Supplementary docx.
- **Personal path.** A local user-home path in `phase7e_report.txt`.

No API keys, tokens or e-mail addresses were found. The only names left are
the repository URL (`Rugved3-droid/coronav`), which `README.md` already
contains. No file exceeds 50 MB; `artifacts/` totals about 55 MB.

Not added: the manuscript sources and reviewer correspondence (they carry
author names), rendered frames, the ASOCA meshes, and pilot runs that no
analysis reads.

### 9.2 Regeneration from the original traces

**Procedure.** The original analysis scripts, unedited, were run against the
original (unredacted) traces in `D:\steve\pilot\runs`, in a checkout of
`revision-cbm`. Python 3.12.10, numpy 2.4.2, scipy 1.17.1, statsmodels
0.14.6.

**Outcome.** All 17 trace-consuming scripts exit 0. **Every CSV and report
they write is byte-identical to the committed artifact.** The two PDF figures
differ only in their embedded `CreationDate`.

`build_manuscript.py --check`, run against the unreleased manuscript sources,
reports 0 hand-typed numerals, 0 HEAD mismatches, and "rendered/ is up to
date". It exits non-zero only because of `{{repo.zenodo_doi}}`, which is
unresolved by design until a DOI exists.

The same run from this repository (`python artifacts/reproduce.py --check`,
against the redacted release) reproduces every output except the A2/A3
Euclidean-travel columns of `phase6c_*` and the A3 stall geometry of
`phase6k_*`. Those are computed from the redacted coordinates. No value in
`manifest.csv` depends on them.

| Manuscript value (`RESULTS.md` Part 1) | Regenerated | Source | Match |
|---|---|---|---|
| A1 open-loop 75/75; 26 steps; 4.58–4.71 mm | 75/75; 26 in all; 4.582–4.707 mm | `baselines/floor_dt001_a1.json` | ✓ |
| A2 open-loop 75/75; 11 steps; 1.76–1.91 mm | 75/75; 11 in all; 1.757–1.905 mm | `baselines/floor_dt001_a2.json` | ✓ |
| Wilson 95% CI 95.1–100.0 | 95.13–100.0 | same | ✓ |
| A1 success 20/25 vs 13/25, Fisher p = 0.0718 | 20/25, 13/25, p = 0.0718 | `phase3_tests.csv` | ✓ |
| A1 worst-rank W = 47.5, p = 0.00206, r_rb +0.708 | W = 47.5, p = 0.00206, 0.708 | `phase3_tests.csv` | ✓ |
| Win ratio 5.60 (2.43–17.97); 470/84/71 | 5.595 (2.431–17.970); wins 470, losses 84, ties 71 | `phase3_tests.csv`, `phase3_report.txt` | ✓ |
| Log-rank χ² = 11.705, p = 0.000623 | 11.705, 0.000623 | `phase3_tests.csv` | ✓ |
| A1 f_rot_LM medians 0.1452 vs 0.1749 | 0.1452, 0.1749 | `phase4_report.txt` | ✓ |
| Paired W = 73.0, p = 0.0147, Holm 0.0147, r_rb +0.551 | 73.0, 0.0147, 0.0147, 0.551 | `phase4_tests.csv`, `multiplicity_table.csv` | ✓ |
| HL +0.0285 (+0.0068 to +0.0440); overlay higher on 20/25 | +0.0285 (+0.0068, +0.0440); 20/25 | `phase4_report.txt` | ✓ |
| Unpaired U = 496.0, p = 0.000384 | 496.0, 0.000384 | `phase4_tests.csv` | ✓ |
| A2 25/25 both arms; medians 41 vs 56; ranges 37–45 vs 50–62 | same | `phase6h_report.txt` | ✓ |
| A2 HL +14.5 (+13.0 to +16.5), p = 1.25e-05 | +14.50 (+13.00, +16.50), 1.25e-05 | `phase6h_tests.csv` | ✓ |
| A2 f_rot_LM 0.0000 vs 0.0454 | 0.0000, 0.0454 | `phase5_report.txt` | ✓ |
| A2 rotate intents 0 vs 37 (16 episodes) | LM phase 0 vs 37; overlay 16/25 episodes | `phase6c_lm_profile.csv`, `phase6h_report.txt` | ✓ |
| A2 paired W = 0.0, p = 0.000482, Holm 0.000965 | 0.0, 0.000482, 0.000965 | `multiplicity_table.csv` | ✓ |
| A2 unpaired p = 2.95e-06 | 2.95e-06 | `multiplicity_table.csv` | ✓ |
| Within-pair r −0.072 (−0.455, +0.332); −0.074 (−0.456, +0.330) | −0.0725 (−0.4546, 0.3322); −0.0744 (−0.4561, 0.3305) | `phase7i_pairing.csv`, `phase7i_worstrank_corr.csv` | ✓ |
| Transmission failures 1.33% vs 0.00%, p = 2.4e-06; A2 p = 0.268 | 17/1277 = 1.33%, 0; p = 2.39e-06; 0.268 | `phase6e_report.txt` | ✓ |
| Log-rank after discounting failed calls p = 0.000157 | 0.000157 | `phase6i_report.txt` | ✓ |
| Biplane p = 0.375 | 0.375 | `multiplicity_table.csv` | ✓ |
| A3 (excluded) paired p = 3.34e-06 | 3.34e-06 | `multiplicity_table.csv` | ✓ |

**Independent cross-check** with this repository's `coronav.metrics` on the
same four confirmatory traces:

- `episode_outcome()` gives 20/13 (A1) and 25/25 (A2) successes, 0
  non-attempts.
- `lm_metrics()` is defined for all 100 episodes and gives medians
  0.1452/0.1749 (A1) and 0.0000/0.0454 (A2), with 0 vs 37 left-main rotate
  intents in 0 vs 16 A2 episodes.
- The per-seed A1 values agree with `phase4_pairs_a1.csv` to ≤ 5e-7 (that file
  is rounded to 6 decimals). The A2 per-seed steps and rotate counts agree
  with `phase6h_pairs_a2.csv` exactly.

**No mismatch was found in any confirmatory number.**

### 9.3 A2 preparation and the open-loop control, re-executed

- **A2 mesh.** `artifacts/harness/pilot/clip_asoca_left.py` was edited on
  2026-07-03, after the A2 mesh was written on 2026-07-01. It was re-run on
  2026-10-16 (`clip_case(12)` only, output redirected to a scratch folder),
  using `D:\ASOCADataAccess.zip` and the original conda env. The `.vtp` is
  byte-identical. The `.obj` differs only in meshio's timestamp comment on
  line 1. Both have 3350 vertices and 6689 faces, with a maximum vertex
  difference of 0.0. The original mesh has 1 component, 9 boundary edges and
  6 non-manifold edges, as the manuscript states. Reference hashes are in
  `artifacts/README.md`.
- **Open-loop control.** `artifacts/analysis/phase7j_floor_dt001.py` was
  re-run, unedited, in the original SOFA environment
  (`D:\conda\envs\steve`, SOFA v23.06, original `coronary_fixture`):
  - **A1:** 75/75; 26 steps in every episode; final distance 4.582–4.707 mm.
  - **A2:** 75/75; 11 steps in every episode; 1.756–1.906 mm.

  This matches the manuscript (§3.1) and the committed
  `floor_dt001_a{1,2}.json` in every aggregate. Per-seed final distances
  differ from the committed run by up to 0.12 mm (A1) and 0.14 mm (A2). This
  is consistent with the run-to-run simulator nondeterminism the study
  measured itself (`artifacts/results/baselines/phase7g_report.txt`). It
  differs from the container run in §5.3, where three repetitions were
  identical. Within this rerun, all three repetitions agreed per seed
  (25/25). The rerun used the A2 step limit of 45 that the script hard-codes
  (U15).

  Side effect, recorded for completeness: the script writes its outputs to
  the absolute path `D:\coronav\results\baselines\`. The rerun overwrote
  those three files in a local checkout; they were restored from git
  afterwards, and nothing from the rerun is committed.

### 9.4 Findings that the manuscript or the archived pages do not reflect

These are reported, not corrected. Nothing in the manuscript, the code or the
data was changed to resolve them.

1. **A2 proximity gate 15 mm (U14).** It differs from manuscript §2.3 and
   from `protocol.json`.
2. **A2 open-loop step limit 45 (U15).** It differs from manuscript §2.4
   ("same step limits as the operator arms"). The outcome is unaffected.
3. **Final-step successes in the exploratory V2 arms.** Three episodes reached
   target exactly at their 60th and last step:
   `v2_neutral/wire_only` episode 7 (4.55 mm), `v2_neutral/overlay` episodes
   7 (4.37 mm) and 8 (4.58 mm). The original analysis, using "terminal and
   not truncated", scores them as failures. Supplementary Table S1 therefore
   reports V2 success as 3/10 (wire-only) and 2/10 (overlay). Under the
   manuscript's success definition (§2.5) they would be 4/10 and 4/10. No
   confirmatory arm has such an episode.
4. **Archived prompt-ablation table (`RESULTS.md` §3.2) versus Table S1.**
   The V3 overlay median is 0.0428 in the archived table and 0.1050 in
   Table S1. Table S1 excludes the 5 V3-overlay episodes with zero valid
   actions (`denominators.csv`). The archived p-values (0.1681 / 0.1375 /
   0.2413) come from a different, unpaired test than Table S1's paired
   Wilcoxon (0.371 / 0.812 / 0.322). The archived table is superseded and
   labelled as such.
5. **Left-main phase convention of the port (U13).**
