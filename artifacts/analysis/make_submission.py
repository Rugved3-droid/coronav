"""Assemble submission/ : the files to upload, plus a snapshot of the repository.

Builds nothing new. It renders the already-built Markdown to Word (IJCARS requires editable
single-column files - "PDF files are not feasible"), copies the figures and the integrity table,
and archives the committed repository with CORRECTIONS.md at its root.

WHAT IT DOES NOT DO. It does not mint the Zenodo DOI and does not post to arXiv. Both publish
irreversibly under the authors' names and credentials, so they are the authors' to perform;
UPLOAD_STEPS.md sets out exactly how, and the manuscript carries a {{repo.zenodo_doi}} placeholder
that stays unresolved until the DOI exists.

    python analysis/make_submission.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUB = ROOT / "submission"
REND = ROOT / "rendered"
sys.path.insert(0, str(ROOT / "analysis"))
from export_docx import export  # noqa: E402

DOCX = [
    (REND / "manuscript" / "paper.md", SUB / "manuscript.docx"),
    (ROOT / "manuscript" / "title_page.md", SUB / "title_page.docx"),
    (REND / "manuscript" / "cover_letter.md", SUB / "cover_letter.docx"),
    (REND / "manuscript" / "response_letter.md", SUB / "response_to_reviewers.docx"),
    (ROOT / "results" / "esm1_supplementary_tables.md", SUB / "online_resource_1.docx"),
]
COPY = [
    (REND / "results" / "reviewer_response.csv", SUB / "reviewer_response_matrix.csv"),
    (ROOT / "results" / "numeric_claims_table.md", SUB / "numeric_claims_table.md"),
    (ROOT / "results" / "esm1_arm_descriptives.csv", SUB / "online_resource_1_arm_descriptives.csv"),
    (ROOT / "results" / "reference_dois.csv", SUB / "reference_dois.csv"),
]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                          check=True).stdout.strip()


def main() -> int:
    SUB.mkdir(parents=True, exist_ok=True)
    for src, dst in DOCX:
        if not src.exists():
            print(f"MISSING SOURCE: {src}")
            continue
        export(src, dst)
    for src, dst in COPY:
        if src.exists():
            shutil.copyfile(src, dst)
            print(f"copied {src.name} -> {dst.name}")
        else:
            print(f"MISSING: {src}")

    sha = git("rev-parse", "--short", "HEAD")
    dirty = git("status", "--porcelain")
    snap = SUB / f"coronav-snapshot-{sha}.zip"
    for old in SUB.glob("coronav-snapshot-*.zip"):
        old.unlink()
    subprocess.run(["git", "archive", "--format=zip", "-o", str(snap), "HEAD"], cwd=str(ROOT),
                   check=True)
    print(f"wrote {snap.name} from commit {sha}"
          + ("  *** WORKING TREE NOT CLEAN: the snapshot is of HEAD, not of your edits ***"
             if dirty else ""))

    (SUB / "READ_ME_FIRST.md").write_text(f"""# Read me first

This folder is a complete IJCARS submission for *Vessel overlay slows vision-language-model
guidewire navigation in simulated coronary anatomies*, except for three things only you can do.
Nothing here was submitted anywhere. No file in this folder should be edited by hand: the Word
files are generated from `rendered/`, which is generated from `manuscript/` with every number
injected from `results/manifest.csv`.

**The build is deliberately red.** It fails on one unresolved placeholder,
`{{{{repo.zenodo_doi}}}}`, which appears in the manuscript where the archive DOI belongs. That DOI
does not exist yet because minting it publishes a permanent record under your name, which is yours
to do rather than mine. `manuscript.docx` and `cover_letter.docx` currently contain that literal
placeholder text. Follow `UPLOAD_STEPS.md` in order: it mints the DOI first, because every later
step depends on it, and the build turns green as soon as the DOI is in the manifest.

**Two other gaps are marked in the text and are yours to fill.** Author contributions read
`[AUTHOR TO COMPLETE]` on both the title page and the manuscript. And the statement on AI-tool use
in Methods 2.8 is drafted from what the logs show; read it and confirm it describes what you
actually did before you submit, because it is a declaration in your name.

**What was checked and what was not.** Word count, abstract structure and length, keyword count,
declaration headings, reference formatting and figure resolution were all checked against the
journal's guidelines as retrieved on 2026-09-15; a re-fetch on 2026-09-16 could not get past the
publisher's cookie redirect, so those checks stand on the cached copy of the page rather than a
live one. The page did not state the journal's peer-review model, so nothing here assumes one; the
manuscript body carries no author names in any case, so it suits either. Verify the model in
Editorial Manager when you submit.

**Two references carry no DOI.** Allard et al. 2007 (the SOFA framework paper) and Holm 1979 have
no Crossref record that passes verification, so they are cited without one rather than with a
guessed identifier. `reference_dois.csv` records what was searched and what matched, for every
reference.

**Read `CORRECTIONS.md`** in the repository root before you submit. It lists every correction made
to the T-MRB version, numbered C1 to C19 with no C10, several of which weaken claims that version
made, and the cover letter and response letter disclose them. You should know what they say,
because reviewers will.

The prior IEEE T-MRB review is disclosed in full: `cover_letter.docx` states it,
`response_to_reviewers.docx` answers every comment, and `reviewer_response_matrix.csv` maps each
comment and each self-found correction to where it is answered.

Snapshot in this folder: `{snap.name}`, a `git archive` of commit `{sha}`.
""", encoding="utf-8")
    print("wrote READ_ME_FIRST.md")

    (SUB / "UPLOAD_STEPS.md").write_text(f"""# Upload steps

In the order they must actually be performed. Each step lists what has to be true before you start
it, because the later steps depend on the earlier ones: the manuscript cites an archive DOI, so the
archive has to exist before the manuscript is final, and the manuscript has to be final before it
is submitted anywhere.

## Step 1 — Archive the snapshot on Zenodo and mint the DOI

*Precondition:* none. Do this first. Everything else waits on it.

1. Sign in at https://zenodo.org with the account that should own the record.
2. New upload, and attach `{snap.name}` (a `git archive` of commit `{sha}`, with
   `CORRECTIONS.md` at its root).
3. Metadata:
   - **Type**: Software (or Dataset if you prefer the analysis artifacts to lead).
   - **Title**: CoroNav: coronary guidewire navigation environment, analysis code and correction
     record.
   - **Authors**: as on the title page.
   - **Licence**: the repository's LICENSE.
   - **Version**: `{sha}`.
4. Publish. Zenodo issues the DOI immediately. Publishing is irreversible.

## Step 2 — Put the DOI into the manifest

*Precondition:* step 1 done, and you have the DOI.

Add one row to `results/manifest.csv`:

```
repo.zenodo_doi,10.5281/zenodo.XXXXXXX,external:https://doi.org/10.5281/zenodo.XXXXXXX,Zenodo DOI for the archived repository snapshot
```

Do not type the DOI into the manuscript. It appears there three times, and the build is what puts
it in all three places consistently.

## Step 3 — Turn the build green and regenerate the package

*Precondition:* step 2 done.

```
python analysis/build_manuscript.py     # must now pass; it fails today on exactly this one key
python analysis/make_submission.py      # regenerates the Word files with the DOI in place
```

If the build reports anything other than success, stop and read what it says. It refuses a
manuscript whose numbers do not come from the manifest, and that is the point of it.

Then re-read `manuscript.docx` and confirm the DOI appears where `{{{{repo.zenodo_doi}}}}` used to
be. Commit the manifest row, and if you want the archived snapshot to contain it, re-run step 1
with the newer zip — the snapshot necessarily lags the commit that adds the package itself.

## Step 4 — Preprint on arXiv (optional)

*Precondition:* step 3 green, so the preprint and the submitted manuscript are the same document.

The guidelines page as retrieved does not state a preprint policy. Check it before posting if that
matters to you; posting is public and effectively permanent.

arXiv needs a PDF or LaTeX source. This machine has no LaTeX, pandoc or Word, so no PDF was
produced here. Open `manuscript.docx` in Word or LibreOffice and export to PDF, then submit at
https://arxiv.org/submit, primary category `eess.IV` or `cs.CV` (cross-list `cs.RO` for the
robotics audience). Use the manuscript's own title and abstract, and put the Zenodo DOI in the
comments field.

## Step 5 — Submit to IJCARS (Editorial Manager)

*Precondition:* step 3 green. Step 4 is optional and independent.

Upload in this order:

1. `cover_letter.docx` — discloses the prior IEEE T-MRB review.
2. `title_page.docx` — author-identifying information, kept separate from the manuscript.
3. `manuscript.docx` — no author names in the body.
4. `Fig1.tif`, `Fig2.tif`, `Fig3.tif`, `Fig4.tif` from `figures/` (600 dpi RGB, 174 mm wide).
   Vector PDF and EPS versions of Figures 1, 3 and 4 are in the same folder if the system prefers
   vector; Figure 2 contains rendered frames and is raster by nature.
5. `online_resource_1.docx` as supplementary material, with
   `online_resource_1_arm_descriptives.csv`.
6. `response_to_reviewers.docx` and `reviewer_response_matrix.csv` as the prior-review disclosure.

The journal's peer-review model is not stated on the guidelines page as retrieved on 2026-09-15,
and a re-fetch on 2026-09-16 did not get past the publisher's cookie redirect, so nothing in this
package assumes one. The manuscript body carries no author names, so it is ready for either a
single- or double-blind model. Note that if the journal turns out to be double-blind, the Zenodo
record and the GitHub repository both identify the authors; ask the editor how they want the code
citation handled rather than removing it.
""", encoding="utf-8")
    print("wrote UPLOAD_STEPS.md")

    (SUB / "README.md").write_text(f"""# Submission package

Generated by `analysis/make_submission.py` from commit `{sha}`. Do not edit these files by hand:
the Word files come from `rendered/`, which is itself generated by
`analysis/build_manuscript.py` with every number injected from `results/manifest.csv`.

Start with `READ_ME_FIRST.md`, then `UPLOAD_STEPS.md`.

| File | What it is |
|---|---|
| `READ_ME_FIRST.md` | One page: what is done, what is not, and what only you can do. |
| `UPLOAD_STEPS.md` | The steps in the order they must be performed, with preconditions. |
| `manuscript.docx` | The manuscript. Single column, structured abstract, no author names in the body. |
| `title_page.docx` | Author-identifying information, supplied separately. |
| `cover_letter.docx` | Cover letter, disclosing the prior review in full. |
| `response_to_reviewers.docx` | Point-by-point response to the earlier IEEE T-MRB reviews. |
| `reviewer_response_matrix.csv` | Every reviewer comment and self-found correction, with where each is answered. |
| `online_resource_1.docx` | Supplementary tables: every arm, the biplane study, every exploratory test. |
| `online_resource_1_arm_descriptives.csv` | The same per-arm descriptives as data. |
| `numeric_claims_table.md` | Every numeric claim in the manuscript against its manifest key and producing script. |
| `reference_dois.csv` | Every reference, what was searched on Crossref, and what verified. |
| `figures/` | Fig1-Fig4 as 600 dpi RGB TIFF at 174 mm, plus vector PDF (and EPS for 1, 3, 4). |
| `coronav-snapshot-{sha}.zip` | `git archive` of the repository at `{sha}`, with `CORRECTIONS.md` at its root. |

> **The snapshot necessarily lags by one commit.** It is an archive of `{sha}`, the commit that was
> HEAD when this package was built, so it cannot contain the commit that adds the package itself.
> If that matters for the DOI, re-run `python analysis/make_submission.py` after committing and
> archive the newer zip. The packager warns whenever the working tree is not clean, because then
> the snapshot reflects HEAD rather than what is on disk.

## Known gaps, stated rather than hidden

1. **The DOI is not minted.** `manuscript.docx` and `cover_letter.docx` contain the literal text
   `{{{{repo.zenodo_doi}}}}` where the DOI belongs. The build fails on that one placeholder by
   design. See `UPLOAD_STEPS.md`.
2. **Two references have no DOI.** Allard et al. 2007 (SOFA) and Holm 1979 have no Crossref record
   that passes verification, so they are cited without one. Eleven references carry a DOI verified
   on title, first author, year and venue; three legitimately have none (a plugin URL, an arXiv
   preprint, a vendor announcement). `reference_dois.csv` has the evidence for each.
3. **Author contributions are not written.** The manuscript and title page carry
   `[AUTHOR TO COMPLETE]`.
4. **The AI-tool statement needs the authors' confirmation** before submission (Methods 2.8).
5. **Compliance was checked against a cached copy of the guidelines** (retrieved 2026-09-15);
   a re-fetch on 2026-09-16 could not get past the publisher's cookie redirect. The peer-review
   model is not stated on that page, so nothing here assumes one.
""", encoding="utf-8")
    print("wrote README.md")
    print(f"\nsubmission/ contains {len(list(SUB.rglob('*')))} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
