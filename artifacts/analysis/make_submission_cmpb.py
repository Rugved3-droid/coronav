"""Assemble CMPB_FINAL_SUBMISSION/ : the files to upload to Computer Methods and Programs in
Biomedicine, plus a snapshot of the repository.

Builds nothing new and computes no statistic. The manuscript comes from `rendered/`, which
`analysis/build_manuscript.py` generates with every number injected from `results/manifest.csv`;
the figures come from `submission/figures/`, which `analysis/make_figures.py` generates from the
committed result artifacts.

CMPB asks for a single-column, double-spaced, editable manuscript, so the .docx files are written
with `line_spacing=2.0` and wide margins. The title page, cover letter and highlights are exported
straight from `manuscript/` rather than from `rendered/`: they contain no injected values, and the
title page carries a postal address whose digits would trip the build's hand-typed-numeral lint
for no benefit.

WHAT IT DOES NOT DO. It does not mint a DOI, does not create a Zenodo release, and does not submit
anything. The manuscript carries an unresolved `{{repo.zenodo_doi}}` placeholder so the build
stays red until the archive exists; that is the TODO_FOR_AUTHOR_ZENODO_DOI item.

    python analysis/make_submission_cmpb.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "CMPB_FINAL_SUBMISSION"
REND = ROOT / "rendered"
FIGS = ROOT / "submission" / "figures"
sys.path.insert(0, str(ROOT / "analysis"))
from export_docx import export  # noqa: E402

# CMPB: single column, double spaced, wide margins.
SPACING, MARGIN = 2.0, 30.0

DOCX = [
    (REND / "manuscript" / "paper_cmpb.md", "Manuscript_CMPB_CLEAN.docx"),
    (ROOT / "manuscript" / "title_page_cmpb.md", "Title_Page_CMPB.docx"),
    (ROOT / "manuscript" / "cover_letter_cmpb.md", "Cover_Letter_CMPB.docx"),
    (ROOT / "manuscript" / "highlights_cmpb.md", "Highlights_CMPB.docx"),
    (ROOT / "results" / "esm1_supplementary_tables.md", "Supplementary_Material_CMPB.docx"),
]

# Vector first where it exists; the TIFFs are 600 dpi RGB at 174 mm.
#
# Fig4 is absent by design. It was the calibration figure - blind success by advance speed, the
# operator's advance distribution, and the constant-rotation probe. The sweep and the probe were
# measured at a timestep no study arm used and are retired by C22, which left the middle panel
# with nothing to contextualise it. Four figures remain.
FIGURES = ["Fig1", "Fig2", "Fig3", "FigS1"]

COPY = [
    (ROOT / "results" / "numeric_claims_table.md", "numeric_claims_table.md"),
    (ROOT / "results" / "esm1_arm_descriptives.csv", "supplementary_arm_descriptives.csv"),
    (ROOT / "results" / "reference_dois.csv", "reference_dois.csv"),
    (ROOT / "CORRECTIONS.md", "CORRECTIONS.md"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                          check=True).stdout.strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(exist_ok=True)

    for src, name in DOCX:
        if not src.exists():
            print(f"MISSING SOURCE: {src}")
            continue
        export(src, OUT / name, line_spacing=SPACING, margins_mm=MARGIN)
        print(f"wrote {name}  (single column, double spaced, {MARGIN:.0f} mm margins)")

    # Copy the figures this package declares, then REMOVE any other figure already sitting in the
    # output. Without the prune step a figure dropped from FIGURES survives from the previous run:
    # Fig4 was retired by C22 and its stale .tif/.pdf/.eps shipped in the package regardless,
    # because copying alone never deletes.
    n_fig, written = 0, set()
    for stem in FIGURES:
        for ext in ("tif", "pdf", "eps"):
            p = FIGS / f"{stem}.{ext}"
            if p.exists():
                shutil.copyfile(p, OUT / "figures" / p.name)
                written.add(p.name)
                n_fig += 1
    stale = [f for f in (OUT / "figures").iterdir() if f.is_file() and f.name not in written]
    for f in stale:
        f.unlink()
        print(f"pruned stale figure {f.name} (not in FIGURES)")
    print(f"copied {n_fig} figure files for {len(FIGURES)} figures -> figures/")

    for src, name in COPY:
        if src.exists():
            shutil.copyfile(src, OUT / name)
            print(f"copied {name}")
        else:
            print(f"MISSING: {src}")

    sha = git("rev-parse", "--short", "HEAD")
    dirty = git("status", "--porcelain")
    snap = OUT / f"coronav-snapshot-{sha}.zip"
    for old in OUT.glob("coronav-snapshot-*.zip"):
        old.unlink()
    subprocess.run(["git", "archive", "--format=zip", "-o", str(snap), "HEAD"], cwd=str(ROOT),
                   check=True)
    print(f"wrote {snap.name} from commit {sha}"
          + ("  *** WORKING TREE NOT CLEAN: the snapshot is of HEAD, not of your edits ***"
             if dirty else ""))

    for hand_written in ("FINAL_AUDIT.md", "SUBMISSION_CHECKLIST.md", "CHANGELOG.md",
                         "READ_ME_FIRST.md"):
        if not (OUT / hand_written).exists():
            print(f"NOTE: {hand_written} is not present in {OUT.name}/")

    print(f"\n{OUT.name}/ contains {len(list(OUT.rglob('*')))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
