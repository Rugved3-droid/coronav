"""Render the manuscript by injecting values from results/manifest.csv, and FAIL on drift.

WHY THIS EXISTS. Stale arithmetic entered prose three times during this revision, always the
same way: a number hand-copied into a document while its upstream computation was still moving.
Twice it was caught by a verification sweep rather than by design. Results and Discussion contain
more numbers than everything drafted so far combined, so this converts that error class from
"something I might notice" into a build failure.

THE RULE. No numeric claim is typed into a manuscript source. Sources carry `{{key}}`
placeholders; `results/manifest.csv` maps each key to a value and names the artifact it came
from. Rendered output goes to `rendered/`, mirroring source paths.

Manifest values must trace to ARTIFACTS, never to the documents. If the manifest were populated
by reading the prose, retrofitting and then rendering would be a round trip that proves nothing.
A document literal that matches no artifact-derived value is exactly the staleness finding this
is built to surface.

THREE FAILURE MODES, all exit non-zero:
  1. a placeholder whose key is absent from the manifest;
  2. a malformed or duplicate manifest row;
  3. a literal numeral in rendered prose that matches no manifest value and no structural
     allowlist pattern - i.e. a hand-typed number.

`--check` compares a fresh render against the COMMITTED `rendered/` output, answering the
question that matters once this is in place: has a source or a manifest value changed without
anybody rebuilding? That invariant survives the retrofit.

`--check-retrofit` is the migration-only comparison against the SOURCE at HEAD, used once to
prove the retrofit reproduced the literal prose byte-for-byte. It stops being meaningful the
moment sources carry placeholders, because then it differs on every file by construction.

Output is written with byte-level fidelity (decode utf-8, substitute, encode utf-8) so line
endings survive and the HEAD comparison is exact rather than approximate.

READ-ONLY with respect to raw logs and results/. No API calls.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "results" / "manifest.csv"
OUT_ROOT = ROOT / "rendered"

# Sources rendered by this build. Results and Discussion join this list when drafted.
SOURCES = [
    "manuscript/paper_cmpb.md",       # the CMPB submission text (current target)
    # manuscript/paper.md is NOT built. It is the superseded IJCARS text, and it rests on the
    # dt=0.006 calibration retired by C22; rebuilding it would require maintaining two
    # manuscripts through that rewrite. It carries a banner saying so and is kept as a record.
    # manuscript/cover_letter.md is NOT built: it is addressed to IJCARS and superseded. The CMPB
    # letter is manuscript/cover_letter_cmpb.md, which carries no injected values (it states no
    # statistics) and is untracked because its signature block contains a personal email address.
    "manuscript/response_letter.md",
    "manuscript/methods.md",          # working draft, kept consistent with paper.md
    "manuscript/title_abstract.md",   # working draft
    "manuscript/related_work.md",     # working draft; was outside the build until 2026-09-15
    "results/reviewer_response.csv",
]

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_.]+)\s*\}\}")

# A numeral as it appears in prose. The lookbehind rejects digits embedded in identifiers
# (v23.06, VMR0066, a1_overlay); the lookahead rejects the head of one (5mm is caught, 5_x is
# not a numeral in this sense).
NUMERAL = re.compile(r"(?<![\w.])[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w])")

# Structural numerals: identifiers and scaffolding, not data claims. Matched spans are blanked
# before the numeral scan, so anything surviving is a candidate data claim. Keep this list
# narrow - every pattern added here is a class of number the lint stops policing.
ALLOWLIST = [
    ("section_ref",      re.compile(r"§\s?\d+(?:\.\d+)?")),
    ("correction_ref",   re.compile(r"\bC\d{1,2}[a-c]?\b")),
    ("phase_ref",        re.compile(r"\bPhase[s]?\s+\d+[a-k]?(?:\s*(?:,|and|/)\s*\d*[a-k]?)*")),
    ("phase_short",      re.compile(r"\b\d?7[a-k]\b")),
    ("reviewer_ref",     re.compile(r"\bR\d(?:\.\d)?(?:\s*minor)?\b|\bReviewer\s+\d\b")),
    ("slot_ref",         re.compile(r"\bslot\s+\d+[a-z]?\b", re.I)),
    ("iso_date",         re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("manuscript_id",    re.compile(r"TMRB-\d{2}-\d{2}-OA-\d{4}")),
    ("anatomy_id",       re.compile(r"VMR\s?0066|Normal_\d+|ASOCA\s+Normal_\d+")),
    ("ci_label",         re.compile(r"\b95%\s*(?:CI\b|confidence intervals?\b|intervals?\b)|"
                                    r"\bWilson\s+95%")),
    ("sofa_version",     re.compile(r"v\d+\.\d+(?:\.\d+)?")),
    ("commit_hash",      re.compile(r"\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")),
    ("ordered_list",     re.compile(r"(?m)^\s*\d+\.\s")),
    ("table_rule",       re.compile(r"(?m)^\s*\|[\s\-|:]+\|\s*$")),
    ("md_heading",       re.compile(r"(?m)^#{1,6}\s+\d+(?:\.\d+)?")),
    ("figure_ref",       re.compile(r"\bFig(?:ure)?\.?\s*\d+[a-z]?\b")),
    # Section RANGES and enumerations: "Sections 1-3", "Phases 7e, 7g, 7h and 7i".
    ("section_range",    re.compile(r"\bSections?\s+\d+(?:\s*[-–]\s*\d+)?")),
    ("csv_item_number",  re.compile(r'(?m)(?<=")\d+[a-z]?\.\s')),
    # Scientific notation written typographically: 1x10^-4, 6.5x10^-3. The mantissa is a data
    # value and must come from the manifest; the "10" of the base is notation, not a claim.
    ("sci_base",         re.compile(r"(?<=[×x])\s?10(?=[⁻⁰-⁹^-])")),
    # Thousands separator: 10,000 bootstrap replicates tokenises as "10" and "000" otherwise.
    ("thousands",        re.compile(r"\b\d{1,3}(?:,\d{3})+\b")),
    # Abstract slot headers: "**3 — Primary result", "**7 — Scope sentence". Document scaffolding.
    ("abstract_slot",    re.compile(r"(?m)^\*\*\d+[a-z]?\s*[—–-]")),
    # The metric's range is true BY CONSTRUCTION - f_rot_LM is a ratio of non-negative sums over
    # the same steps, so it cannot leave [0, 1] no matter what any analysis returns. Definitional,
    # not measured, so it cannot drift and needs no manifest key.
    ("metric_bounds",    re.compile(r"\[0,\s*1\]")),
    # Editorial scaffolding in the abstract skeleton: "(2 sentences)", and the longer
    # "(1-2 sentences, and it belongs in the abstract)" - the trailing clause is why an
    # anchored-to-close-paren pattern missed it.
    ("editorial_count",  re.compile(r"\(\d+(?:[-–]\d+)?\s+sentences?\b")),
    # Cross-references to numbered tables and sections of the paper itself.
    ("table_ref",        re.compile(r"\b(?:Table|Tbl\.?)\s*\d+[a-z]?\b")),
    ("limitations_ref",  re.compile(r"\bL\d+\b")),
    # Bibliography: a whole reference-list line is bibliographic scaffolding (years, volumes,
    # pages, DOIs), and in-text citations are numbers in brackets. Neither is a data claim.
    ("reference_line",   re.compile(r"(?m)^\[\d+\][^\n]*")),
    ("citation",         re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]")),
    ("doi",              re.compile(r"(?:https://doi\.org/|doi:\s?)\S+")),
    ("url",              re.compile(r"https?://\S+")),
    ("model_version",    re.compile(r"Claude\s+(?:Sonnet|Opus|Haiku)\s+\d+(?:\.\d+)?")),
    ("month_date",       re.compile(
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|"
        r"November|December)\s+\d{4}\b|\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4}\b")),
    ("section_number",   re.compile(r"\bSections?\s+\d+(?:\.\d+)*")),
    # Supplementary material and table identifiers: "Online Resource 1", "Table S2", "Tables 1-2".
    ("online_resource",  re.compile(r"\bOnline Resource\s+\d+\b")),
    ("table_range",      re.compile(r"\bTables?\s+S?\d+(?:\s*[-–]\s*S?\d+)?\b|\bS\d\b")),
    ("draft_edit_label", re.compile(r"\bEDIT\s+\d+\b")),
    # Reviewer comment numbers at the start of a response-matrix field, quoted or not.
    ("matrix_item",      re.compile(r"(?m)^(?:AE|R1|R2|SELF),\"?\d+[a-z]?\.")),
]

# Numerals that are typographically distinct but numerically identical must not pass in one file
# and fail in another. The documents mix ASCII hyphen-minus with U+2212 for negative numbers, so
# both forms are normalised before comparison rather than duplicated in the manifest.
_MINUS_FORMS = ("−", "–", "‐", "‑")


def normalise_numeral(tok: str) -> str:
    for ch in _MINUS_FORMS:
        tok = tok.replace(ch, "-")
    return tok.lstrip("+")


def load_manifest(path: Path) -> tuple[dict[str, str], list[str]]:
    """key -> value, plus structural errors. Duplicate or empty rows are failures, not warnings:
    a manifest that silently takes the last of two definitions is how drift re-enters."""
    errors: list[str] = []
    values: dict[str, str] = {}
    if not path.exists():
        return {}, [f"manifest not found: {path}"]
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"key", "value", "source", "description"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            return {}, [f"manifest missing column(s): {', '.join(sorted(missing))}"]
        for i, row in enumerate(reader, start=2):
            key = (row.get("key") or "").strip()
            val = (row.get("value") or "").strip()
            src = (row.get("source") or "").strip()
            if not key:
                errors.append(f"manifest line {i}: empty key")
                continue
            if not val:
                errors.append(f"manifest line {i}: key '{key}' has an empty value")
            if not src:
                errors.append(f"manifest line {i}: key '{key}' names no source artifact")
            if key in values:
                errors.append(f"manifest line {i}: duplicate key '{key}'")
            # A source column whose path does not exist is worse than no source column: it
            # asserts provenance nobody can follow. Thirteen keys pointed at
            # 'coronav/run_coronary.py', which has never existed in this repo - the harness lives
            # outside it - and that went unnoticed until a hand audit. Sources outside the repo
            # are legitimate but must SAY SO, because those values are the only ones a reader of
            # the repository cannot audit for themselves.
            if src:
                if src.startswith("external:"):
                    ext = src.split(":", 1)[1]
                    if not Path(ext).exists():
                        errors.append(f"manifest line {i}: key '{key}' names external source "
                                      f"'{ext}' which does not exist")
                elif not (ROOT / src.replace("/", os.sep)).exists():
                    errors.append(f"manifest line {i}: key '{key}' names source '{src}' which "
                                  f"does not resolve under the repo root. If it is outside the "
                                  f"repo, mark it 'external:<path>' so the audit gap is visible.")
            values[key] = val
    return values, errors


def manifest_numerals(values: dict[str, str]) -> set[str]:
    """Every numeral token appearing in any manifest value.

    Tokenising the VALUES (not just comparing whole strings) is what lets a composite value like
    '2.43-17.97' or '25 (16 informative)' satisfy the lint for each numeral it contains.
    """
    toks: set[str] = set()
    for v in values.values():
        # U+2212 MINUS SIGN is not matched by the ASCII regex, so fold it first.
        folded = v
        for ch in _MINUS_FORMS:
            folded = folded.replace(ch, "-")
        for m in NUMERAL.finditer(folded):
            toks.add(normalise_numeral(m.group(0)))
    return toks


def _blank(m: re.Match) -> str:
    """Blank a span WITHOUT destroying its newlines.

    Several allowlist patterns contain \\s+, and \\s matches a newline. Replacing the whole span
    with spaces therefore deleted line breaks and shifted every subsequent line number - which
    made this tool report findings at lines they were not on, with empty context. Newlines are
    preserved; everything else becomes a space.
    """
    return "".join("\n" if c == "\n" else " " for c in m.group(0))


def mask_allowlisted(text: str) -> str:
    """Blank out structural spans so only candidate data numerals remain. Length and line
    structure are both preserved, so reported line numbers stay true to the source."""
    out = text
    for _name, rx in ALLOWLIST:
        out = rx.sub(_blank, out)
    return out


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def spell_for(value: str, rel: str) -> str:
    """Spell a manifest value appropriately for its destination.

    The manifest holds the NUMBER; typography belongs to the output format. Prose uses the
    typographic minus U+2212, but a CSV that other tools parse should stay ASCII - and letting a
    markdown convention leak into a data file is not a cosmetic matter, it changes the bytes
    downstream consumers read.

    This exists because the retrofit bound the CSV's ASCII "-0.455" to a key whose value carries
    U+2212, so rendering silently converted three hyphens and the file no longer matched its
    committed form. Fixing the class beats patching the three instances.
    """
    if rel.lower().endswith(".csv"):
        for ch in _MINUS_FORMS:
            value = value.replace(ch, "-")
    return value


STRUCTURAL_PLACEHOLDER = re.compile(
    r"(?m)^#{1,6}[ \t]+\{\{|\bR\{\{|§\s?\{\{|\bC\{\{|\bFig\.?\s?\{\{|\bTable\s\{\{")


def structural_placeholders(src_text: str, rel: str) -> list[str]:
    """A placeholder standing where a section, reviewer, correction, figure or table NUMBER belongs.

    These are always wrong and always invisible to every other check. The retrofit bound heading
    numbers to data keys whose values happened to coincide - '### 1.4' became
    '### {{solver.a2_calls_per_nc}}' because that key is 1.4, and 'R2.3' became
    'R{{solver.a2_range_lo}}' - so the rendered text was byte-identical, --check was clean and the
    lint was green. Changing either solver figure would have renumbered the response letter.
    Found by reading the source, not by any check. Now it is a build failure.
    """
    out = []
    for m in STRUCTURAL_PLACEHOLDER.finditer(src_text):
        ln = line_of(src_text, m.start())
        ctx = src_text.splitlines()[ln - 1].strip()
        out.append(f"{rel}:{ln}: placeholder in a structural position (section/reviewer/"
                   f"correction/figure/table number)  |  {ctx[:100]}")
    return out


def render_one(src_text: str, values: dict[str, str], rel: str) -> tuple[str, list[str]]:
    errors: list[str] = []

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            errors.append(f"{rel}:{line_of(src_text, m.start())}: "
                          f"placeholder '{{{{{key}}}}}' has no manifest key")
            return m.group(0)
        return spell_for(values[key], rel)

    return PLACEHOLDER.sub(sub, src_text), errors


def coverage_one(src_text: str, rel: str) -> list[str]:
    """Literal numerals still sitting in a SOURCE, i.e. not yet behind a placeholder.

    The lint cannot surface these. It scans RENDERED prose, where every remaining literal matches
    some manifest value and therefore passes - by design, since its job is to catch hand-typed
    numbers, not to measure how much of the document is parameterised. But the requirement is
    that every numeric claim resolves from the manifest, so the unanchored literals need their
    own report. This is the hand-anchoring worklist.

    Placeholder spans are masked first, so a number already injected is not re-reported.
    """
    masked = PLACEHOLDER.sub(lambda m: " " * len(m.group(0)), src_text)
    masked = mask_allowlisted(masked)
    for ch in _MINUS_FORMS:
        masked = masked.replace(ch, "-")
    out: list[str] = []
    lines = src_text.splitlines()
    for m in NUMERAL.finditer(masked):
        ln = line_of(masked, m.start())
        ctx = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
        out.append(f"{rel}:{ln}: unanchored literal '{m.group(0)}'  |  {ctx[:100]}")
    return out


def lint_one(rendered: str, allowed: set[str], rel: str) -> list[str]:
    findings: list[str] = []
    masked = mask_allowlisted(rendered)
    for ch in _MINUS_FORMS:
        masked = masked.replace(ch, "-")
    for m in NUMERAL.finditer(masked):
        tok = normalise_numeral(m.group(0))
        if tok in allowed:
            continue
        ln = line_of(masked, m.start())
        lines = rendered.splitlines()
        ctx = lines[ln - 1].strip() if 0 < ln <= len(lines) else "<LINE OUT OF RANGE>"
        if not ctx:
            # An empty context means the mask desynchronised from the source. That is a bug in
            # this tool, not a clean finding, and it must not be reported as one.
            ctx = "<EMPTY LINE — masking/line-number bug, investigate before trusting this>"
        findings.append(f"{rel}:{ln}: literal numeral '{tok}' matches no manifest value"
                        f"  |  {ctx[:110]}")
    return findings


def head_bytes(rel: str) -> bytes | None:
    try:
        r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(ROOT),
                           capture_output=True, check=True)
        return r.stdout
    except Exception:
        return None


def same_content(a: bytes, b: bytes) -> bool:
    """Compare after normalising line-ending CONVENTION only.

    `core.autocrlf` is on in this working tree, so checked-out files carry CRLF while
    `git show HEAD:<path>` returns the stored blob with LF. A raw byte comparison therefore
    reports EVERY line as differing and the rendered file as larger by exactly one byte per line
    break - which is precisely what it did on the first --check run, turning a clean retrofit
    into four phantom mismatches. The tell was the arithmetic: 268 extra bytes against 268
    differing lines out of 269.

    Only the CRLF/LF distinction is normalised. Everything else counts as a difference.
    """
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare a fresh render against the COMMITTED rendered/ output, i.e. "
                         "is rendered/ stale with respect to its sources and the manifest?")
    ap.add_argument("--check-retrofit", action="store_true",
                    help="MIGRATION ONLY: compare rendered output against the source path at "
                         "HEAD. Meaningful only while HEAD still holds literal prose; once "
                         "sources carry placeholders this always differs and means nothing.")
    ap.add_argument("--no-lint", action="store_true",
                    help="skip the literal-numeral lint (diagnostic only; never in CI)")
    ap.add_argument("--coverage", action="store_true",
                    help="list numerals in SOURCES not yet behind a placeholder "
                         "(the hand-anchoring worklist; the lint cannot see these)")
    args = ap.parse_args()

    values, m_errors = load_manifest(MANIFEST)
    allowed = manifest_numerals(values)

    print("=" * 84)
    print("MANUSCRIPT BUILD — values injected from results/manifest.csv")
    print("=" * 84)
    print(f"  manifest keys        : {len(values)}")
    print(f"  distinct numerals in manifest values : {len(allowed)}")
    if m_errors:
        print("\nMANIFEST ERRORS")
        for e in m_errors:
            print(f"  {e}")

    render_errors: list[str] = []
    lint_findings: list[str] = []
    mismatches: list[str] = []
    coverage: list[str] = []
    used: set[str] = set()
    used_by_source: dict[str, set[str]] = {}
    total_placeholders = 0

    # Descriptions carry the superseded marker, so they are read alongside the values.
    descriptions: dict[str, str] = {}
    if MANIFEST.exists():
        with open(MANIFEST, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                descriptions[(row.get("key") or "").strip()] = row.get("description") or ""

    for rel in SOURCES:
        src = ROOT / rel
        if not src.exists():
            render_errors.append(f"{rel}: source not found")
            continue
        raw = src.read_bytes().decode("utf-8")
        n_ph = len(PLACEHOLDER.findall(raw))
        total_placeholders += n_ph
        used.update(PLACEHOLDER.findall(raw))
        used_by_source[rel] = set(PLACEHOLDER.findall(raw))

        rendered, errs = render_one(raw, values, rel)
        render_errors.extend(errs)
        render_errors.extend(structural_placeholders(raw, rel))

        out = OUT_ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        # In --check mode the artifact on disk IS the thing under test, so it must not be
        # overwritten before it has been compared. Writing first would destroy the evidence and
        # guarantee a pass - which is exactly how the earlier version could never fail.
        if not args.check:
            out.write_bytes(rendered.encode("utf-8"))

        if not args.no_lint:
            lint_findings.extend(lint_one(rendered, allowed, rel))
        if args.coverage:
            coverage.extend(coverage_one(raw, rel))

        status = ""
        if args.check_retrofit:
            # Migration check: does the render reproduce the literal prose HEAD still holds?
            hb = head_bytes(rel)
            if hb is None:
                status = "  [no HEAD version]"
            elif same_content(hb, rendered.encode("utf-8")):
                status = "  [matches HEAD source]"
            else:
                status = "  [DIFFERS FROM HEAD source]"
                mismatches.append(rel)
        elif args.check:
            # Ongoing check: does the generated artifact ON DISK match what the sources and the
            # manifest currently produce?
            #
            # This compared the fresh render against the COMMITTED blob and never looked at the
            # file on disk at all. Since the fresh render is recomputed from source every run, it
            # always equalled the blob, so the check could not fail: a probe that corrupted a real
            # p-value inside rendered/ (0.0147 -> 0.0148) still reported "up to date". A guard
            # that cannot fire is worse than no guard, because it is reported as a guarantee.
            #
            # The comparison that actually detects drift is fresh-render vs on-disk artifact. The
            # committed blob is checked separately, so "someone edited generated output" and
            # "someone forgot to rebuild before committing" are distinguishable rather than
            # conflated.
            fresh = rendered.encode("utf-8")
            on_disk = out.read_bytes() if out.exists() else None
            committed = head_bytes(f"rendered/{rel}")
            if on_disk is not None and not same_content(on_disk, fresh):
                status = "  [rendered/ ON DISK DIFFERS - generated output was edited by hand]"
                mismatches.append(rel)
            elif committed is None:
                status = "  [rendered/ not yet committed]"
            elif not same_content(committed, fresh):
                status = "  [rendered/ STALE IN GIT - rebuild and commit]"
                mismatches.append(rel)
            else:
                status = "  [rendered/ up to date]"
        print(f"  {rel:<40s} placeholders={n_ph:<4d} -> {out.relative_to(ROOT)}{status}")

    unused = sorted(set(values) - used)

    # A key whose description is marked [SUPERSEDED must not supply a manuscript number.
    #
    # 105 keys were marked rather than deleted, because their VALUES are the true record of what
    # was measured at dt=0.006 and deleting them would destroy that record. But retaining them
    # leaves nothing stopping one being referenced again, which would reduce "no superseded key
    # reaches the text" from a guarantee to a habit. This makes it a build failure instead.
    superseded = {k for k, d in descriptions.items() if "[SUPERSEDED" in d}
    for rel, keys in used_by_source.items():
        for k in sorted(keys & superseded):
            render_errors.append(
                f"{rel}: references SUPERSEDED key '{{{{{k}}}}}' — that value was measured at a "
                f"timestep no study arm used and must not appear in the manuscript (C22)")

    if render_errors:
        print(f"\nUNRESOLVED PLACEHOLDERS ({len(render_errors)})")
        for e in render_errors:
            print(f"  {e}")

    if lint_findings:
        print(f"\nHAND-TYPED NUMERALS ({len(lint_findings)}) — each is either a number that must "
              f"become a placeholder,\nor a structural numeral the allowlist should cover. "
              f"Neither is ignorable.")
        for f in lint_findings:
            print(f"  {f}")

    if args.coverage:
        print(f"\nUNANCHORED LITERALS ({len(coverage)}) — numerals still typed into sources "
              f"rather than\nresolved from the manifest. Each is either a data claim needing a "
              f"key, or a structural\nnumeral the allowlist should cover.")
        for c in coverage:
            print(f"  {c}")

    if unused:
        print(f"\nUNUSED MANIFEST KEYS ({len(unused)}) — defined but referenced by no placeholder:")
        for k in unused:
            print(f"  {k}")

    if args.check_retrofit:
        print("\nRETROFIT VERIFICATION (rendered vs the SOURCE at HEAD) — migration only")
        if mismatches:
            print(f"  {len(mismatches)} file(s) DIFFER from the committed text:")
            for r in mismatches:
                print(f"    {r}")
            print("  A difference means the rendered output and the committed prose disagree.")
            print("  One of them is stale. Diff them before committing anything.")
        else:
            print("  all rendered files reproduce the committed prose byte-for-byte")
    elif args.check:
        print("\nGENERATED-OUTPUT CHECK (fresh render vs committed rendered/)")
        if mismatches:
            print(f"  {len(mismatches)} file(s) are STALE in rendered/:")
            for r in mismatches:
                print(f"    {r}")
            print("  A source or a manifest value changed without rebuilding. Re-run this")
            print("  script without --check and commit the regenerated rendered/ output.")
        else:
            print("  rendered/ is up to date with its sources and the manifest")

    print("\n" + "-" * 84)
    print(f"  placeholders rendered : {total_placeholders}")
    print(f"  manifest keys         : {len(values)}  ({len(unused)} unused)")
    print(f"  unresolved            : {len(render_errors)}")
    print(f"  hand-typed numerals   : {len(lint_findings)}")
    if args.check:
        print(f"  HEAD mismatches       : {len(mismatches)}")

    failed = bool(m_errors or render_errors or lint_findings or mismatches)
    print(f"  BUILD {'FAILED' if failed else 'OK'}")
    print("-" * 84)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
