"""Convert literal numbers in manuscript sources into {{key}} placeholders.

A one-directional migration tool, not part of the build. `build_manuscript.py` is the thing that
runs every time; this exists to perform the initial retrofit and to help when a new draft section
arrives with literals in it.

SAFETY RULE, and the reason this is not a blind search-and-replace. Substituting every manifest
value textually would wreck the document: the value "25" appears in "25 seeds" (data) but also in
"TMRB-07-26" and "§2.5" (structure), and "2" appears everywhere. So by default only DISTINCTIVE
values are substituted - those containing a decimal point or an exponent, or having three or more
digits. Short integers are left alone deliberately; `build_manuscript.py`'s lint then reports each
one with its line and context, and those get anchored by hand where the surrounding words make the
meaning unambiguous.

Longest values first, so "0.000482" is consumed before "0.0004" can match inside it. Text already
inside a placeholder is never touched.

Default is --dry-run. Nothing is written unless --apply is passed.

READ-ONLY with respect to results/. No API calls.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "results" / "manifest.csv"
RULES = ROOT / "analysis" / "retrofit_rules.csv"

SOURCES = [
    "manuscript/methods.md",
    "manuscript/response_letter.md",
    "manuscript/title_abstract.md",
    "results/reviewer_response.csv",
]

PLACEHOLDER_SPAN = re.compile(r"\{\{[^}]*\}\}")

# The documents mix ASCII hyphen-minus with U+2212 MINUS SIGN for negative numbers. The lint
# normalises them; this script matched literally, so "-0.455" (ASCII) went unsubstituted while
# "+0.332" beside it was replaced, leaving one interval half-placeholder and half-literal.
MINUS_FORMS = ("−", "–", "‐", "‑")


def norm(s: str) -> str:
    for ch in MINUS_FORMS:
        s = s.replace(ch, "-")
    return s


def needle_variants(value: str) -> list[str]:
    """The spellings of a value that may appear in prose: ASCII minus and U+2212."""
    ascii_form = norm(value)
    out = [ascii_form]
    if ascii_form.startswith("-"):
        out.append("−" + ascii_form[1:])
    return out


def distinctive(value: str) -> bool:
    """Is this value specific enough to substitute textually without collateral damage?"""
    if "." in value or "e" in value.lower():
        return True
    digits = sum(c.isdigit() for c in value)
    return digits >= 3


def load_manifest() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with open(MANIFEST, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            k = (row.get("key") or "").strip()
            v = (row.get("value") or "").strip()
            if k and v:
                rows.append((k, v))
    # Longest value first so that a longer literal is never eaten by a shorter prefix.
    rows.sort(key=lambda kv: len(kv[1]), reverse=True)
    return rows


def ambiguous_values(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Values carried by more than one key.

    THIS IS THE IMPORTANT GUARD. Text matching cannot tell which quantity a literal means, only
    what it reads. Several keys legitimately share a value - a1.rot.p_paired and a1.rot.holm are
    both 0.0147, a1.rot.mde_ratio and replay.corr_hi are both 0.98 - and substituting by text
    alone silently binds prose to whichever key sorted first.

    That failure is invisible: the rendered output is byte-identical, the HEAD diff is clean and
    the lint is green, because the VALUE is right and only the KEY is wrong. It surfaces later,
    when one of the two quantities changes and drags the other with it. An earlier version of
    this script did exactly that to four passages before the diff was read.

    So: a value with more than one key is never substituted automatically. It is reported, and
    anchored by hand where the surrounding words disambiguate it.

    KNOWN BLIND SPOT, stated because this guard is easy to over-trust. It only withholds values
    carried by MORE THAN ONE manifest key. A literal whose meaning has NO key in the manifest is
    still bound to whatever unrelated key happens to share its digits, and the guard cannot see
    it. That is not hypothetical: the abstract used "100" for the operator's A2 success rate,
    which had no key, and it was bound to replay.steps_moved_pct - the percentage of replayed
    steps on which the wire moved - because that key alone carried the value 100. The guard
    passed it. It was caught by reading the diff.

    The lesson is that this tool reduces hand-checking, it does not replace it. Read the applied
    diff. A value that appears in prose but is absent from the manifest is the dangerous case,
    and the only defence is that every data numeral has a key of its own.
    """
    by_value: dict[str, list[str]] = {}
    for k, v in pairs:
        by_value.setdefault(norm(v), []).append(k)
    return {v: ks for v, ks in by_value.items() if len(ks) > 1}


# Structural positions a data value must never be substituted into. The value-matching retrofit
# turned '### 1.4' into '### {{solver.a2_calls_per_nc}}' and 'R2.3' into 'R{{solver.a2_range_lo}}'
# because those keys happen to equal 1.4 and 2.3. Heading lines are protected whole; reviewer,
# section, correction, figure and table references are protected as tokens.
STRUCTURAL_SPAN = re.compile(
    r"(?m)^#{1,6}[^\n]*|\bR\d(?:\.\d)?\b|§\s?\d+(?:\.\d+)?|\bC\d{1,2}[a-c]?\b"
    r"|\bFig\.?\s?\d+[a-z]?\b|\bTable\s\d+\b")


def protected_spans(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in PLACEHOLDER_SPAN.finditer(text)]
    spans += [(m.start(), m.end()) for m in STRUCTURAL_SPAN.finditer(text)]
    return spans


def replace_outside_placeholders(text: str, needle: str, repl: str) -> tuple[str, int]:
    """Replace `needle` with `repl` except where it falls inside an existing placeholder."""
    out = []
    i = 0
    n = 0
    spans = protected_spans(text)

    def inside(pos: int) -> bool:
        return any(a <= pos < b for a, b in spans)

    while True:
        j = text.find(needle, i)
        if j == -1:
            out.append(text[i:])
            break
        if inside(j):
            out.append(text[i:j + len(needle)])
            i = j + len(needle)
            continue
        # Reject a match that is part of a longer number: 0.0004 inside 0.000482.
        # A following "." is only disqualifying when a DIGIT follows it - otherwise this rejected
        # every number ending a sentence, which silently skipped "residual reaching 1.44." and
        # "friction 0.001." in the first retrofit.
        before = text[j - 1] if j > 0 else ""
        after = text[j + len(needle)] if j + len(needle) < len(text) else ""
        after2 = text[j + len(needle) + 1] if j + len(needle) + 1 < len(text) else ""
        if before.isdigit() or after.isdigit() or (after == "." and after2.isdigit()):
            out.append(text[i:j + len(needle)])
            i = j + len(needle)
            continue
        out.append(text[i:j])
        out.append(repl)
        i = j + len(needle)
        n += 1
    return "".join(out), n


def load_rules() -> list[tuple[str, re.Pattern, str, str]]:
    """Context-anchored rules: (file, compiled pattern, key, note).

    Plain value matching cannot tell `Holm p = 0.0147` from `p = 0.0147`, because the value is
    identical and only the surrounding words differ. That is why 0.0147 and 0.000965 and 0.000384
    are all withheld by the ambiguity guard - and why they need rules rather than hand edits at
    twelve, five and four sites respectively.

    Each pattern must contain a group named `v` marking exactly the numeral to replace. Only that
    group's span is rewritten, so punctuation, emphasis markers and units around it survive
    untouched.
    """
    rules: list[tuple[str, re.Pattern, str, str]] = []
    if not RULES.exists():
        return rules
    with open(RULES, newline="", encoding="utf-8") as fh:
        for i, row in enumerate(csv.DictReader(fh), start=2):
            f = (row.get("file") or "*").strip()
            p = (row.get("pattern") or "").strip()
            k = (row.get("key") or "").strip()
            note = (row.get("note") or "").strip()
            if not p or not k:
                continue
            try:
                rx = re.compile(p)
            except re.error as e:
                print(f"  rules line {i}: bad regex for key '{k}': {e}")
                continue
            if "v" not in (rx.groupindex or {}):
                print(f"  rules line {i}: pattern for '{k}' has no (?P<v>...) group; skipped")
                continue
            rules.append((f, rx, k, note))
    return rules


def apply_rules(text: str, rel: str, rules,
                valid_keys: set[str]) -> tuple[str, int, list[str], list[tuple[str, int]]]:
    """Apply context rules, rewriting only the `v` group. One pass per rule, IN FILE ORDER.

    Order is load-bearing and not incidental. The specific patterns must precede the general
    ones: once `Holm p = 0.0147` has been rewritten to `Holm p = {{a1.rot.holm}}`, the later
    general rule `p = (?P<v>0\\.0147)` finds nothing at that site and cannot steal it. Reversing
    the two would silently bind every Holm figure to the raw p-value - the same wrong-key,
    right-value corruption that `--check` cannot see, because the rendered digits are identical.

    Per-rule counts are returned so that ordering can be VERIFIED rather than assumed. A file
    total alone cannot distinguish "the specific rules fired" from "the general rule took
    everything".
    """
    total = 0
    errs: list[str] = []
    per_rule: list[tuple[str, int]] = []
    for f, rx, key, _note in rules:
        if f != "*" and f != rel:
            continue
        if key not in valid_keys:
            errs.append(f"{rel}: rule names key '{key}' which is not in the manifest")
            continue
        count = 0

        def sub(m: re.Match) -> str:
            nonlocal count
            whole, base = m.group(0), m.start()
            # Never rewrite something already inside a placeholder.
            if "{{" in whole and "}}" in whole:
                return whole
            count += 1
            return (whole[: m.start("v") - base]
                    + "{{" + key + "}}"
                    + whole[m.end("v") - base:])

        text = rx.sub(sub, text)
        if count:
            per_rule.append((key, count))
        total += count
    return text, total, errs, per_rule


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes (default is dry-run)")
    ap.add_argument("--rules", action="store_true",
                    help="apply context-anchored rules from analysis/retrofit_rules.csv instead "
                         "of plain value matching (this is how ambiguous values get anchored)")
    ap.add_argument("--all-values", action="store_true",
                    help="also substitute short/ambiguous values (DANGEROUS - inspect the diff)")
    args = ap.parse_args()

    pairs = load_manifest()
    ambig = ambiguous_values(pairs)
    usable = [(k, v) for k, v in pairs
              if (args.all_values or distinctive(v)) and norm(v) not in ambig]
    skipped = [(k, v) for k, v in pairs
               if not (args.all_values or distinctive(v)) and norm(v) not in ambig]
    ambiguous = [(k, v) for k, v in pairs if norm(v) in ambig]

    print("=" * 84)
    print(f"RETROFIT {'(APPLYING)' if args.apply else '(dry run - nothing written)'}")
    print("=" * 84)
    print(f"  manifest values           : {len(pairs)}")
    print(f"  distinctive, substitutable: {len(usable)}")
    print(f"  short, left for hand work : {len(skipped)}")
    print(f"  AMBIGUOUS (>1 key), never auto-substituted : {len(ambiguous)}")

    grand = 0
    for rel in SOURCES:
        p = ROOT / rel
        if not p.exists():
            print(f"  {rel}: MISSING")
            continue
        text = p.read_bytes().decode("utf-8")
        before = text
        per_file = 0
        hits: list[tuple[str, int]] = []

        if args.rules:
            rules = load_rules()
            valid = {k for k, _ in pairs}
            text, n_rules, rule_errs, per_rule = apply_rules(text, rel, rules, valid)
            print(f"\n  {rel}  ->  {n_rules} rule substitution(s)")
            for e in rule_errs:
                print(f"      RULE ERROR: {e}")
            # Aggregate by key: a key claimed by several patterns should show one combined count.
            agg: dict[str, int] = {}
            for k, c in per_rule:
                agg[k] = agg.get(k, 0) + c
            for k, c in sorted(agg.items(), key=lambda kc: (-kc[1], kc[0])):
                print(f"      {c:>3d}x  {k}")
            grand += n_rules
            if args.apply and text != before:
                p.write_bytes(text.encode("utf-8"))
            continue

        for key, val in usable:
            n_key = 0
            for needle in needle_variants(val):
                text, n = replace_outside_placeholders(text, needle, "{{" + key + "}}")
                n_key += n
            if n_key:
                hits.append((key, n_key))
                per_file += n_key
        grand += per_file
        print(f"\n  {rel}  ->  {per_file} substitution(s)")
        for key, n in sorted(hits, key=lambda kn: -kn[1]):
            print(f"      {n:>3d}x  {key}")
        if args.apply and text != before:
            p.write_bytes(text.encode("utf-8"))

    print("\n" + "-" * 84)
    print(f"  total substitutions: {grand}")
    if ambig:
        print(f"\n  AMBIGUOUS VALUES ({len(ambig)}) — shared by two or more keys, so a text match")
        print("  cannot tell which quantity the prose means. NEVER auto-substituted; anchor each")
        print("  occurrence by hand using the surrounding words.")
        for v, ks in sorted(ambig.items()):
            print(f"      {v:<12s} <- {', '.join(sorted(ks))}")
    if skipped:
        print(f"\n  LEFT AS LITERALS ({len(skipped)}) — short values that cannot be substituted")
        print("  safely by text match. build_manuscript.py will report each occurrence with its")
        print("  line and context; anchor those by hand.")
        for k, v in skipped:
            print(f"      {v:<10s} {k}")
    if not args.apply:
        print("\n  DRY RUN — rerun with --apply to write.")
    print("-" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
