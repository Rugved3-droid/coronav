"""Export rendered Markdown to Word (.docx) for submission.

IJCARS requires editable source files - Word or LaTeX, single column; "PDF files are not
feasible". No LaTeX, pandoc or LibreOffice is available on this machine, but python-docx is, so
the submission files are produced as .docx from the RENDERED Markdown (rendered/, values already
injected and linted). Nothing here computes or alters a number.

Handles the Markdown subset the manuscript uses: # headings, paragraphs, **bold** / *italic*,
pipe tables, "- " bullets, "> " block quotes, and figure lines of the form
    ![caption](relative/path.png)
It is deliberately small. Anything it does not recognise is emitted as a plain paragraph, so
content is never silently dropped.

USAGE
    python analysis/export_docx.py rendered/manuscript/paper.md submission/manuscript.docx
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")
FIGURE = re.compile(r"^!\[(?P<cap>[^\]]*)\]\((?P<path>[^)]+)\)\s*$")


def add_inline(par, text: str) -> None:
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            par.add_run(part[2:-2]).bold = True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            par.add_run(part[1:-1]).italic = True
        else:
            par.add_run(part)


def is_table_rule(line: str) -> bool:
    return bool(re.match(r"^\s*\|[\s\-|:]+\|\s*$", line))


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def export(src: Path, dst: Path, line_spacing: float | None = None,
           margins_mm: float = 25.0, font_pt: float = 11) -> None:
    """Render one Markdown file to .docx.

    `line_spacing` and `margins_mm` default to the previous behaviour, so existing callers are
    unaffected. CMPB asks for a double-spaced, wide-margined single-column manuscript, which is
    `line_spacing=2.0, margins_mm=30`; the value is applied to the Normal style so it reaches
    body text, headings and table cells alike rather than only the paragraphs added after it.
    """
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Mm(margins_mm))
    base = doc.styles["Normal"]
    base.font.name = "Times New Roman"
    base.font.size = Pt(font_pt)
    if line_spacing is not None:
        base.paragraph_format.line_spacing = line_spacing

    lines = src.read_text(encoding="utf-8").splitlines()
    i, para_buf = 0, []

    def flush():
        nonlocal para_buf
        if para_buf:
            add_inline(doc.add_paragraph(), " ".join(s.strip() for s in para_buf))
            para_buf = []

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            flush(); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            level = min(len(m.group(1)), 4)
            h = doc.add_heading(level=0 if level == 1 else level - 1)
            add_inline(h, m.group(2))
            i += 1; continue
        f = FIGURE.match(s)
        if f:
            flush()
            img = (src.parent / f.group("path")).resolve()
            if img.exists():
                doc.add_picture(str(img), width=Mm(174))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                doc.add_paragraph(f"[MISSING FIGURE FILE: {f.group('path')}]")
            add_inline(doc.add_paragraph(), f.group("cap"))
            i += 1; continue
        if s.startswith("|") and i + 1 < len(lines) and is_table_rule(lines[i + 1]):
            flush()
            header = split_row(s)
            body = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(split_row(lines[i])); i += 1
            t = doc.add_table(rows=1 + len(body), cols=len(header))
            t.style = "Table Grid"
            for c, txt in enumerate(header):
                cell = t.rows[0].cells[c]; cell.text = ""
                add_inline(cell.paragraphs[0], txt)
                for r in cell.paragraphs[0].runs:
                    r.bold = True
            for r_i, row in enumerate(body, start=1):
                for c in range(len(header)):
                    cell = t.rows[r_i].cells[c]; cell.text = ""
                    add_inline(cell.paragraphs[0], row[c] if c < len(row) else "")
            continue
        if s.startswith("- "):
            flush()
            add_inline(doc.add_paragraph(style="List Bullet"), s[2:])
            i += 1; continue
        if s.startswith(">"):
            flush()
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Mm(8)
            add_inline(p, s.lstrip(">").strip())
            i += 1; continue
        para_buf.append(s)
        i += 1
    flush()
    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dst))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    export(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"wrote {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
