"""Integrity table: every numeric claim in the manuscript sources against its manifest key, the
artifact it traces to, and the script that produced that artifact.

Brief item 8. Two kinds of numeric claim exist in the sources:

  1. PLACEHOLDERS - {{key}} resolved from results/manifest.csv. Each row gives key, value, source
     artifact and producing script.
  2. UNANCHORED LITERALS - numerals still typed into a source. The lint guarantees each matches SOME
     manifest value, but not which. Each is listed with every key carrying that value, so an
     ambiguous one is visible rather than silently attributed.

The producing script is FOUND, not asserted: analysis/*.py is searched for the artifact's filename,
and a script that writes it is preferred over one that merely reads it. Sources outside the repo
(external:) are labelled as such. An artifact no script mentions is reported as "no producing script
found", never guessed.

Outputs: results/numeric_claims_table.csv (all sources) and results/numeric_claims_table.md
(the submission manuscript only, readable).
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis"))
from build_manuscript import (MANIFEST, NUMERAL, PLACEHOLDER, SOURCES, _MINUS_FORMS,  # noqa: E402
                              load_manifest, mask_allowlisted, normalise_numeral)

WRITE_HINT = re.compile(r"open\([^)]*[\"']w|write_text|savefig|to_csv|json\.dump|writer\(")


def producing_scripts() -> dict[str, str]:
    """artifact basename -> script that most plausibly writes it."""
    scripts = sorted((ROOT / "analysis").glob("*.py"))
    texts = {s: s.read_text(encoding="utf-8", errors="replace") for s in scripts}
    return {"__texts__": texts}  # resolved lazily per artifact


def find_producer(artifact: str, texts: dict) -> str:
    if artifact.startswith("external:"):
        return "external harness (outside repo)"
    base = Path(artifact).name
    stem = base.rsplit(".", 1)[0]
    # Scripts often build filenames with f-strings - always_advance_{key}_summary.json - so a literal
    # search misses them. Also try the stem with each underscore-separated token replaced by a
    # {placeholder}; this is what found phase7a as the producer of always_advance_a3_summary.json.
    tokens = stem.split("_")
    templated = [re.compile("_".join(re.escape(x) for x in tokens[:i]) + ("_" if i else "")
                            + r"\{[^}]+\}" + ("_" if i < len(tokens) - 1 else "")
                            + "_".join(re.escape(x) for x in tokens[i + 1:]))
                 for i in range(len(tokens))]
    writers, readers = [], []
    for s, t in texts.items():
        if s.name in ("claims_table.py", "build_manuscript.py", "retrofit_manuscript.py"):
            continue
        if base in t or stem in t or any(rx.search(t) for rx in templated):
            (writers if WRITE_HINT.search(t) else readers).append(s)
    # A script that names the artifact AND writes files is the likeliest producer. Prefer one whose
    # own name shares the artifact's phase prefix.
    pref = base.split("_")[0]
    for pool in (writers, readers):
        named = [s for s in pool if s.name.startswith(pref)]
        if named:
            return f"analysis/{named[0].name}"
        if pool:
            return f"analysis/{pool[0].name}"
    if base == "LOG.md":
        return "log entry (value transcribed from a phase report; see LOG.md)"
    if base == "PRESPEC.md" or base.endswith(".txt") and "submitted" in base:
        return "document (not script-produced)"
    return "no producing script found"


def main() -> int:
    values, errors = load_manifest(MANIFEST)
    with open(MANIFEST, newline="", encoding="utf-8") as fh:
        meta = {r["key"]: r for r in csv.DictReader(fh)}
    texts = producing_scripts()["__texts__"]
    by_value = defaultdict(list)
    for k, v in values.items():
        for m in NUMERAL.finditer(normalise_numeral(v) if len(v) < 12 else v):
            by_value[normalise_numeral(m.group(0))].append(k)

    rows = []
    for rel in SOURCES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        lines = text.splitlines()
        for m in PLACEHOLDER.finditer(text):
            ln = text.count("\n", 0, m.start()) + 1
            key = m.group(1)
            src = meta.get(key, {}).get("source", "")
            rows.append({
                "file": rel, "line": ln, "kind": "placeholder", "key": key,
                "value": values.get(key, "UNRESOLVED"), "source_artifact": src or "NO MANIFEST KEY",
                "producing_script": find_producer(src, texts) if src else "",
                "context": lines[ln - 1].strip()[:140],
            })
        masked = PLACEHOLDER.sub(lambda mm: " " * len(mm.group(0)), text)
        masked = mask_allowlisted(masked)
        for ch in _MINUS_FORMS:
            masked = masked.replace(ch, "-")
        for m in NUMERAL.finditer(masked):
            ln = masked.count("\n", 0, m.start()) + 1
            tok = normalise_numeral(m.group(0))
            keys = sorted(set(by_value.get(tok, [])))
            rows.append({
                "file": rel, "line": ln, "kind": "unanchored literal",
                "key": " | ".join(keys) if keys else "NO MATCHING KEY",
                "value": m.group(0),
                "source_artifact": " | ".join(sorted({meta[k]["source"] for k in keys})) if keys else "",
                "producing_script": "ambiguous" if len(keys) > 1 else (
                    find_producer(meta[keys[0]]["source"], texts) if keys else ""),
                "context": lines[ln - 1].strip()[:140],
            })

    out_csv = ROOT / "results" / "numeric_claims_table.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "line", "kind", "key", "value",
                                           "source_artifact", "producing_script", "context"])
        w.writeheader()
        w.writerows(rows)

    # The detail table documents whichever manuscript is currently being submitted. This was
    # hardcoded to manuscript/paper.md, so when that file left SOURCES the filter matched nothing
    # and the table shipped EMPTY while its heading still claimed to document it - an audit
    # artifact certifying traceability by showing no rows at all. It now follows SOURCES.
    MANUSCRIPT = next((s for s in SOURCES if s.endswith("paper_cmpb.md")),
                      next((s for s in SOURCES if "paper" in s), SOURCES[0]))
    paper = [r for r in rows if r["file"] == MANUSCRIPT]
    if not paper:
        raise SystemExit(f"claims_table: no rows for {MANUSCRIPT}; the detail table would be "
                         f"empty. Check that it is still in SOURCES.")
    md = [f"# Numeric claims in the submission manuscript (`{MANUSCRIPT}`)", "",
          f"Every numeral in `{MANUSCRIPT}` that is a data claim, with the manifest key it is "
          "injected from, the artifact that key cites, and the script that produced the artifact. "
          "Generated by `analysis/claims_table.py`; do not edit by hand.", "",
          "| Line | Key | Value | Source artifact | Producing script |", "|---|---|---|---|---|"]
    for r in paper:
        md.append(f"| {r['line']} | `{r['key']}` | {r['value']} | `{r['source_artifact']}` | "
                  f"`{r['producing_script']}` |")
    summary = defaultdict(int)
    for r in rows:
        summary[(r["file"], r["kind"])] += 1
    md += ["", "## Summary across all build sources", "", "| File | Placeholders | Unanchored literals |",
           "|---|---|---|"]
    for rel in SOURCES:
        md.append(f"| `{rel}` | {summary[(rel, 'placeholder')]} | {summary[(rel, 'unanchored literal')]} |")
    unresolved = [r for r in rows if r["value"] == "UNRESOLVED"]
    nomatch = [r for r in rows if r["kind"] == "unanchored literal" and r["key"] == "NO MATCHING KEY"]
    noscript = [r for r in rows if r["producing_script"] == "no producing script found"]
    md += ["", f"- Unresolved placeholders: **{len(unresolved)}** "
               f"({', '.join(sorted({r['key'] for r in unresolved})) or 'none'})",
           f"- Literal numerals matching no manifest value: **{len(nomatch)}**",
           f"- Claims whose artifact no script mentions: **{len(noscript)}** "
           f"({', '.join(sorted({r['source_artifact'] for r in noscript})) or 'none'})"]
    (ROOT / "results" / "numeric_claims_table.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"rows: {len(rows)}  (paper.md: {len(paper)})")
    for rel in SOURCES:
        print(f"  {rel:<36s} placeholders={summary[(rel, 'placeholder')]:<4d} "
              f"unanchored={summary[(rel, 'unanchored literal')]}")
    print(f"unresolved placeholders: {len(unresolved)} {sorted({r['key'] for r in unresolved})}")
    print(f"literals matching no manifest value: {len(nomatch)}")
    print(f"claims with no producing script found: {len(noscript)} "
          f"{sorted({r['source_artifact'] for r in noscript})}")
    print(f"wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
