# Manuscript–Repository Concordance and Reproducibility Audit

| | |
|---|---|
| Manuscript | *Vessel overlay slows vision-language-model guidewire navigation in simulated coronary anatomies* (final version as submitted to CMPB, manuscript CMPB-D-26-07590; being resubmitted to IJCARS) |
| Repository audited | `Rugved3-droid/coronav`, `master` @ `b1886b5`, also branch `anonymous-review` @ `3964676` and tag `t-mrb-submitted` |
| Audit date | 2026-10-14 |
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
3. **The promised research artifacts are missing.** The manuscript (Data and
   code availability, §1, §2.8, §5) and the cover letter state that the
   episode traces, analysis scripts, result artifacts and correction record
   are released in this repository. **They are not here**, nor in any branch,
   tag or commit, nor anywhere else accessible to this audit. As a result,
   none of the manuscript's statistics can be regenerated from the
   repository. This is the main publication-readiness blocker (§6, U1–U2).
4. **The environment works for A1.** The Docker image did not build as
   published (Debian 11 archive move). After a one-line apt-source fix it
   builds, passes `check_install.py`, and runs. In the container, the
   open-loop control on A1 at 0.001 s reproduced the manuscript's open-loop
   A1 figures (§5.3). A2 cannot be prepared from the repository (U6).

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
| A2 mesh (§2.2) | 9 boundary edges, 6 non-manifold edges | — | — | unverifiable (A2 not distributable or preparable here) |
| SOFA / BeamAdapter (§2.1) | v23.06 | v23.06 | v23.06 | verified in Dockerfile and built image |
| J-tip (§2.1) | radius 1.5 mm, angle 0.2π | same (`env.py`) | same | verified (code) |
| LCP (§2.1) | Gauss–Seidel, ≤ 2000 it, tol 1e-4 | same (`coronary_sim.py`) | same | verified (code) |
| Contact / alarm (§2.1) | 0.3 / 0.5 mm | same | same | verified (code) |
| Friction (§2.1) | 0.001 | same | same | verified (code) |
| **Timestep (§2.1)** | **0.001 s for every retained arm and result** | **0.006 s** in `env.py` (hard-coded), `coronary_sim.py` default, `protocol.json`, `PROTOCOL.md` | 0.001 s everywhere, single source `protocol.json`, logged per row | corrected; see U4 for the open question about the original harness |
| Image (§2.3) | 512 × 512 grayscale, AP cranial 40° | same | same | verified (code) |
| Conditions (§2.3) | wire-only vs overlay, identical physics | renderer supported both, **runner ran `wire_only` only** | `run_benchmark.py --mode wire_only overlay` | corrected |
| Operator (§2.3) | Claude Sonnet 4.6, SDK v0.72.0, stateless | `claude-sonnet-4-6`; SDK **unpinned** in Dockerfile, `>=0.72.0` in setup.py | Dockerfile pins `anthropic==0.72.0` | corrected; resolved version verified in the built image |
| State string (§2.3) | distance, trend, retractions remaining, no-progress counter | same (`env.py`) | same | verified (code) |
| Proximity gate (§2.3) | < 25 mm and closing: rotate → advance 35 mm/s | same (`env.py`, `prompts.py`) | same; tested against protocol.json | verified (code) |
| Failed API call (§2.3) | null action, consumes one step, no retry | same (`env.py`) | same | verified (code) |
| Open-loop control (§2.4) | 35 mm/s advance, never rotate/retract, 3 reps/anatomy, 0.001 s | **absent** | `--operator open_loop` (`coronav/operator/open_loop.py`), a re-implementation | added; executed (§5.3) |
| Success (§2.5) | tip within 5 mm of target within the step limit | threshold 5.0 mm; but `success = terminal and not truncation` | `episode_outcome()` counts a target reached on the final step | threshold verified; see U5 |
| Step limits (§2.6) | A1 60 both arms; **A2 120 both arms** | A1 60; **A2 45 (wire_only), overlay 62 per PROTOCOL.md** | A1 60; A2 120 | corrected to the manuscript; **contradiction unresolved, U3** |
| Episodes (§2.6) | 25 seed-matched per arm | 25 seeds per anatomy | same | seeds cannot be verified against originals (U11) |
| Seeds vs decoding (§2.6) | seeds fix reset only; decoding unseeded | not stated | stated in README, PROTOCOL, protocol.json, run_meta.json | match; verified that `ClaudeOperator` sets no temperature or seed |
| Exclusion (§2.6) | zero valid actions = non-attempt | "all rows fail API/parse" (same rule); but `lm_metrics` also drops episodes with no LM movement | documented; `episode_outcome()` applies the manuscript rule | see §4 |
| Primary endpoint (§2.5, §2.7) | navigation over all episodes; worst-rank, win ratio, log-rank (A1); paired Wilcoxon + HL (A2) | primary = `lm_rot_mm` MWU; steps for successes only | documented as manuscript; analysis code **absent** (U2) | match (docs); not regenerable |
| Secondary endpoint (§2.5) | `f_rot_LM`, dimensionless [0,1]; paired Wilcoxon + Holm; MWU sensitivity | `lm_rot_mm` primary | `f_rot_LM` secondary, code name `lm_rot_mm` explained | match; definition verified (§4) |
| Endpoint hierarchy post hoc; plan retrospective (§2.5, §2.7) | disclosed | called "pre-specified" | disclosed; "pre-specified" withdrawn | match |
| Analysis plan frozen and released (§2.7) | released with the code | absent | absent | **missing (U2)** |
| Number-to-artifact manifest, build check (§2.8) | exists | absent | absent | **missing (U2)** |

### 2.2 Results

All values below are now stated in `RESULTS.md` Part 1 exactly as in the
manuscript. "Before" shows what the repository said previously, if anything.

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
quantity (same numerator, denominator, units, phase and interpretation). The
name differs; the quantity does not. This could not be checked against the
original `run_biplane.py:_lm_metrics()`, which `metrics.py` says it was
ported from verbatim, because that file is not available (U5).

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

OPEN_LOOP_RESULTS_PLACEHOLDER

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
| U1 | **Blocker** | Original **episode traces** are not in the repository. The manuscript states they are released here. | Add them under `artifacts/` (e.g. `artifacts/<anatomy>/<arm>/trace.jsonl`, plus open-loop traces). `.gitignore` now allows `artifacts/**/*.jsonl`. Large files: GitHub release asset or Zenodo deposit, linked here. Check that A2 traces contain no ASOCA-derived geometry beyond per-step scalars. |
| U2 | **Blocker** | **Analysis scripts**, the **frozen analysis plan**, the **number-to-artifact manifest** with its build check, **result artifacts**, and **`CORRECTIONS.md`** (cited for C21–C22) are absent. | Add the original files unmodified, with a README stating how to run them against `artifacts/` to regenerate Table 1 and all §3 statistics. |
| U3 | High | **A2 step limit.** The manuscript says 120 in both arms. This repository's v1.0 protocol recorded 45 (wire_only) and 62 (overlay). The manuscript's A2 step ranges (37–45 and 50–62) have maxima equal to exactly those values. The repository cannot tell which is right. If the arms ran at 45/62, the "common limit / nothing truncated / not censored" statements would need re-examination. | The original A2 run configs or trace headers. `protocol.json` now follows the manuscript (120) and flags this. |
| U4 | High | **Timestep of the original operator arms.** This repository's harness, described as ported from the original `run_coronary.py`, hard-coded 0.006 s, while the manuscript says all retained arms used 0.001 s. Either the port diverged from the original or the original used 0.006 s. | The original `run_coronary.py` / run configuration (and the traces if they log dt). The code now uses 0.001 s per the manuscript. |
| U5 | Medium | `lm_metrics()` is described as a verbatim port but cannot be checked. Its legacy success field mis-scores a target reached on the final step, and it is unknown whether the original analysis did the same or whether any retained episode is affected. | The original `run_biplane.py`/analysis code and traces: check for rows with `terminal` and `truncation` both true. |
| U6 | High | **A2 is not reproducible from this repository.** `download_asoca.py` only extracts zip members. The clipping, centerline ordering and export to `clipped_left.obj/.vtp` + `paths/*.pth` used for the manuscript are absent, and the ASOCA archive layout was not verified (no registration available to this audit). The script now checks the layout and says "NOT READY". | Add the A2 preparation script (it can be redistributed even though the data cannot), with checksums of the expected outputs. |
| U7 | Medium | The Supplementary Material (prompt-variant, contrast, biplane arms) is not in the repository. The archived prompt-ablation figures were not checked against it, and the biplane runner is absent. | Add the Supplementary Material or its source tables, and the biplane harness if it is to be described as released. |
| U8 | Low | Author metadata: `CITATION.cff` has no top-level `title`/`authors` (required by CFF 1.2.0), `LICENSE` has an empty copyright holder, and the README BibTeX author is `X,Y,Z`. These look deliberate (recent commits removed them), so they were left alone. | Author decision. Complete them after any double-blind phase. |
| U9 | Medium | The exact original software environment (stEVE commit, numpy/scipy versions, OS) is not recorded. The verified image pins stEVE `f909e712` and anthropic 0.72.0, but nothing shows the original used these. | The original environment record (`pip freeze`, stEVE commit). |
| U10 | Low | The A1 clinical segmentation diameters (LM 4.89 mm, distal LAD 1.73 mm; §1) were not verified. | Optional: a script that measures them from the bundled mesh. |
| U11 | Low | It cannot be confirmed that the seeds in `protocol.json` are the seeds of the original runs. | Traces (they record `seed`). |
| U12 | Low | The manuscript says the materials are "archived". There is no archival snapshot (DOI). | Create a GitHub release and a Zenodo DOI once U1/U2 are resolved, and cite it in the manuscript. |

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

## 8. How to regenerate the manuscript statistics (once U1–U2 are resolved)

This cannot be done today. When the original artifacts are added, the
expected procedure is:

1. Place the original traces under `artifacts/` without modification, and
   record their SHA-256 checksums in `artifacts/CHECKSUMS.sha256`.
2. Run the original analysis scripts against them to regenerate Table 1 and
   §3, and compare against `RESULTS.md` Part 1. Any difference is a finding
   to report, not to adjust.
3. As an independent cross-check, `coronav.metrics.lm_metrics()` and
   `episode_outcome()` can be run on the same traces. Medians of `f_rot_LM`
   should equal 0.1452 / 0.1749 (A1) and 0.0000 / 0.0454 (A2), and success
   counts should equal 20/13 (A1) and 25/25 (A2).
