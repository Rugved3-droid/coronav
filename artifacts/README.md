# Original research records

These are the records behind the manuscript *Vessel overlay slows
vision-language-model guidewire navigation in simulated coronary anatomies*:
the episode traces the analysis consumed, the analysis scripts as they were
run, the frozen analysis plan, every result artifact, the number-to-artifact
manifest, the original operator harness, and the correction record
(`../CORRECTIONS.md`, C1–C22).

They were recovered on 2026-10-16 from the machine where the study ran. Two
sources were used:

- **The original run folders and harness**, `D:\steve\pilot\` and
  `D:\steve\stEVE\coronary_fixture\` (written 2026-06-22 to 2026-07-09).
- **The analysis workspace**, a local branch `revision-cbm` of this
  repository (last commit `20c872c`, 2026-09-18), which was never pushed.
  Analysis scripts, results, the manifest and `CORRECTIONS.md` are taken from
  its committed blobs.

`PROVENANCE.tsv` gives the original path and modification date of every file.
`CHECKSUMS.sha256` holds the SHA-256 of every file as committed. Verify it from
the repository root:

    sha256sum -c artifacts/CHECKSUMS.sha256

`.gitattributes` stores `artifacts/` without end-of-line conversion, so the
check passes on every platform.

## What is byte-for-byte and what is not

Most files are exact copies. **Twelve are redacted copies**, and
`REDACTIONS.tsv` lists each one with the SHA-256 of the original and of the
committed file:

| What | Files | Why |
|---|---|---|
| ASOCA patient-space coordinates (`gt_tip_pos`, `gt_tip_obs`, `gt_target_pos`, `first_tip`) and `frame_path` removed | A2 and A3 traces (4), `results/baselines/always_advance_a2_trace.jsonl`, `…_a3_trace.jsonl`, `floor_dt001_a2.json`, `nondeterminism_floor_a2.json`, `study_target_reference.json` | ASOCA data must not be redistributed. A tip trajectory and a target point in patient coordinates are derived from the patient geometry. Every other field is unchanged; for the JSONL files this was checked row by row. |
| Author name removed | `harness/pilot/PREREGISTRATION.txt` | anonymous review |
| `lastModifiedBy` metadata blanked | `supplementary/SupplementaryMaterial.docx` | anonymous review; the document body is unchanged |
| A local user-home path replaced | `results/phase7e_report.txt` | personal path |

The unredacted A2/A3 files are kept off-repository. They can be provided to
anyone holding ASOCA access, and their hashes in `REDACTIONS.tsv` identify them
exactly.

Not included: rendered frames (the A2/A3 ones are ASOCA renderings), the ASOCA
meshes, the manuscript sources and reviewer correspondence, and the pilot
runs that no analysis reads.

## Layout

| Path | Contents |
|---|---|
| `traces/` | One `trace.jsonl` per arm, keeping the original run-folder path and file name, plus each run's `summary.txt`. `ARMS.tsv` maps arm names to files, with row and episode counts read from the files. |
| `analysis/` | The analysis scripts. `PRESPEC.md` is the frozen analysis plan. `SUPERSEDED.md` lists artifacts superseded by the 0.001 s timestep correction (C21–C22). `build_manuscript.py` is the manifest build check. `legacy/` holds the July figure script. |
| `results/` | Every result artifact. `manifest.csv` maps each manuscript number to the artifact that produced it. `numeric_claims_table.*` is the claim-to-source table. `esm1_*` are the Supplementary tables. `baselines/` holds the open-loop and solver baselines. `LOG.md` is the analysis log. |
| `harness/pilot/` | The original operator harness. `run_ablation.py` produced the confirmatory A1 arms (`v1_current`). `run_asoca.py` produced A2 and A3. `run_coronary.py` holds `build_env` and produced the old-prompt, contrast and monoplane arms. `run_biplane.py` produced the biplane arms and holds the original `_lm_metrics`. Also: `clip_asoca_left.py` and `asoca_adapter.py` (A2 preparation), the July analysis scripts, `PREREGISTRATION.txt`, `PAPER_DATA.md`, `ANATOMY_NOTES.md`. |
| `harness/coronary_fixture/` | The original `coronary_fixture` package (simulator wrapper, centreline loader, A1 clipping script `clip_left_coronary.py`). |
| `supplementary/` | The Supplementary Material as submitted. |
| `environment/` | The stEVE commit used, and a pip freeze of the original conda env. The freeze was taken on 2026-10-16, not at run time. |

## Arms

Confirmatory arms (all others are exploratory, or excluded in the case of A3):

| Arm | File | Rows | Episodes | Seeds |
|---|---|---|---|---|
| A1 wire-only | `traces/ablation_prompt_robustness/v1_current/wire_only/trace.jsonl` | 1277 | 25 | 5001 + 11i |
| A1 overlay | `traces/ablation_prompt_robustness/v1_current/overlay/trace.jsonl` | 1448 | 25 | 5001 + 11i |
| A2 wire-only | `traces/normal12_wire_only/arm_asoca_normal12_wire_only/trace.jsonl` | 1026 | 25 | 3001 + 11i |
| A2 overlay | `traces/normal12_overlay/arm_asoca_normal12_overlay/trace.jsonl` | 1400 | 25 | 3001 + 11i |

The seeds equal those in `benchmarks/protocol.json`.

## Regenerating the manuscript's statistics

Requires Python ≥ 3.10 with numpy, scipy, statsmodels and matplotlib. No
simulator, network or model call is needed.

    python artifacts/reproduce.py --check

This runs every trace-consuming analysis script, unedited, against
`artifacts/traces/`. The scripts were written against the absolute folder
`D:\steve\pilot\runs`. `reproduce.py` substitutes that single literal in
memory, which works because `traces/` keeps the same relative layout. The
scripts then write to `artifacts/results/`, as they always did. `--check`
compares every output with the committed version, ignoring line endings.
Afterwards, `git checkout -- artifacts/results` restores the committed files.

Expected result on this release: every output is identical except
`phase6c_lm_profile.csv`, `phase6c_report.txt`, `phase6k_a3_stall.csv` and
`phase6k_report.txt`. Those compute Euclidean tip travel from the coordinates
redacted from the A2/A3 traces, so their A2/A3 travel columns come out as
zero. Their other columns, including every value `manifest.csv` takes from
them, are unchanged. On the unredacted originals all four regenerate exactly.
The PDF figures differ only in their embedded creation date.

| Manuscript result | Script | Output |
|---|---|---|
| A1 navigation: worst-rank Wilcoxon, win ratio, log-rank, Fisher (§3.2) | `phase3_selection_bias.py` | `phase3_tests.csv`, `phase3_report.txt`, `fig_cumincidence_a1.*` |
| A1 f_rot_LM: paired Wilcoxon, Hodges–Lehmann, Mann–Whitney (§3.3) | `phase4_primary.py` | `phase4_tests.csv`, `phase4_pairs_a1.csv` |
| Confirmatory family, Holm, A2 f_rot_LM (§3.3, Table 1) | `phase5_multiplicity.py` | `multiplicity_table.csv`, `phase5_report.txt` |
| A2 steps to target: paired Wilcoxon, HL, ranges (§3.2) | `phase6h_a2_steps.py` | `phase6h_tests.csv`, `phase6h_pairs_a2.csv`, `fig_cumincidence_a2.*` |
| A2 left-main rotate intents (§3.3) | `phase6c_integrity.py` | `phase6c_lm_profile.csv` |
| Exclusions and non-attempts (§2.6) | `phase6d_denominators.py` | `denominators.csv` |
| Transmission failures (§3.4) | `phase6e_api_audit.py`, `phase6i_hold_sensitivity.py` | `phase6e_*`, `phase6i_*` |
| Within-pair correlations (§2.6) | `phase7i_pairing.py`, `phase7i_worstrank_corr.py` | `phase7i_*` |
| Supplementary Table S1 | `esm_tables.py` | `esm1_*` |
| Open-loop control, 75/75 both anatomies (§3.1) | `phase7j_floor_dt001.py` (simulator) | `baselines/floor_dt001_a{1,2}.json`, `baselines/phase7j_report.txt` |

`build_manuscript.py --check` and `claims_table.py` read the manuscript
sources, which are not released. They were run on 2026-10-16 against those
sources: 0 hand-typed numerals, 0 mismatches, and one unresolved placeholder,
`{{repo.zenodo_doi}}`, which is unresolved by design until a DOI exists.

### Simulator-driven baselines

`phase7a`, `phase7c`, `phase7d`, `phase7e_solver_replay`, `phase7g`,
`phase7j` and `phase7_always_advance` drive SOFA v23.06 through the original
`coronary_fixture`. They expect it at `D:\steve\stEVE`, and the A2 mesh in
`D:\steve\pilot`. On 2026-10-16, `phase7j_floor_dt001.py` was re-run in the
original environment; see `docs/MANUSCRIPT_CONCORDANCE.md` §5.4 for the result.

### A2 preparation

`harness/pilot/clip_asoca_left.py` (with `asoca_adapter.py`) builds the A2
mesh from the ASOCA archive (`ASOCADataAccess.zip`). Centrelines are read from
the archive at run time; A2 never used `paths/*.pth`. It was re-run on
2026-10-16 (`clip_case(12)`, output redirected so the original was not
touched). The result matched the mesh the A2 arms used:

| Output | SHA-256 |
|---|---|
| `clipped_asoca_normal12.vtp` | `40ef676c4aa804a0f539c210c5751dab0a78c8c7b0a60c68132733f676c106d4` (byte-identical) |
| `clipped_asoca_normal12.obj`, excluding line 1 (meshio's timestamp comment) | `4a831a64addbe2ccfa3e2f94aa0c7c68d37c64cb98c87844da0003095490479e` |

The result has 3350 vertices and 6689 faces; the maximum vertex difference
from the original is 0.0. The script's `__main__` also rebuilds Normal_5 (A3,
excluded) and writes into its hard-coded `OUT_DIR`.

## Known discrepancies these records reveal

These are reported, not corrected. See `docs/MANUSCRIPT_CONCORDANCE.md` §6.

- **The A2 proximity gate was 15 mm**, as pre-registered
  (`harness/pilot/PREREGISTRATION.txt:110`; `run_asoca.py:120`). The
  manuscript (§2.3) gives 25 mm, which was A1's value. No A2 rotation was ever
  suppressed by the gate.
- **The A2 open-loop control ran with a 45-step limit**
  (`analysis/phase7j_floor_dt001.py:66`), not the operator arms' 120. Every
  episode reached target at step 11, so the outcome is unaffected.
- **The final-step success rule.** The original analysis counts an episode as
  successful only if its last row is terminal and not truncated
  (`phase3_selection_bias.py:66`, `phase5_multiplicity.py:125`,
  `phase6h_a2_steps.py:75`). No confirmatory episode reached target on its
  final allowed step, so no confirmatory number is affected. Three exploratory
  prompt-variant V2 episodes did (V2 wire-only episode 7; V2 overlay episodes
  7 and 8). They are counted as failures in Supplementary Table S1.
