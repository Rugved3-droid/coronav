# Legacy figure script — provenance only, superseded

`generate_figures.py` is a byte-for-byte copy of `D:\steve\pilot\generate_figures.py`, the script
that composed the figures for the original IEEE T-MRB submission (TMRB-07-26-OA-0710). It is
committed so that the provenance of Figures 1 and 2 is in the repository rather than only on one
machine. **Nothing in this directory is run to produce the current submission**, and no analysis
here should be trusted.

## What it is good for

Figures 1 and 2 only — the environment schematic and the observation-conditions montage. Their
composition is carried over into `analysis/make_figures_1_2.py`, which re-runs it at the journal's
600 dpi and is the script that actually produces the submitted artwork. Three differences between
the two are deliberate and are listed in the header of `make_figures_1_2.py`: the burned-in figure
titles are removed, Figure 1 no longer asserts a single step budget (A2's arms did not share one —
CORRECTIONS.md, C13), and Figure 2's panels no longer carry "seed 2001, step 20", which read as
though one wire position were shown in all panels when the three monoplane frames come from three
separate runs.

## What it must NOT be used for

Its `fig3_primary`, `fig4_dissociation` and `fig5_robustness_biplane` are built on the analysis
this revision superseded, and they would contradict the manuscript if regenerated:

- they use Mann–Whitney throughout, where the confirmatory tests are now paired Wilcoxon with Holm
  adjustment over a declared two-member family (CORRECTIONS.md, C11 and C14);
- they plot A3 (ASOCA Normal_5) as a third anatomy, which is excluded: its lumen is a generated
  constant-radius tube and its contact solver failed to converge on most steps (C8, C11);
- `fig4_dissociation`'s panel title asserts significance "in all 3" anatomies, and
  `fig5_robustness_biplane`'s panel (b) hard-codes a biplane cascade read from a superseded
  `PAPER_DATA.md`, whose arms are now known not to have shared a step budget (C19);
- several statistics are hard-coded as numerals in titles and annotations, which is the practice
  the number-injection build in `analysis/build_manuscript.py` exists to prevent.

## Does it run?

Yes, in the stEVE environment (`D:\steve\activate_steve.ps1`; Python 3.8, matplotlib 3.7.5,
pyvista 0.44.2), where its module-level `from run_biplane import _lm_metrics` resolves. It does not
run in the base environment, which has no pyvista. Verified 2026-09-16. Its four Figure 2 source
frames were confirmed present on the same date. `analysis/make_figures_1_2.py`, by contrast, needs
only matplotlib, numpy and Pillow, and runs in the base environment.
