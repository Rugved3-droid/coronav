"""Resolve DOIs for the manuscript's references against Crossref, and verify every match.

WHY THE VERIFICATION MATTERS. Crossref's top hit is not trustworthy on its own. Querying
"win ratio composite endpoints Pocock" returns a ResearchHub record before the European Heart
Journal paper it paraphrases. A DOI written into a manuscript on the strength of a fuzzy title
match is a fabricated citation, so every candidate here must clear four independent checks before
it is accepted:

  1. title similarity >= 0.90 after normalisation (difflib ratio on alphanumeric-lowercased text);
  2. the reference's first-author surname appears in the record's author list;
  3. the publication year matches within +/- 1 (Crossref's issued year can lag a print year);
  4. the container (journal/book) title shares a distinctive token with the expected venue, where a
     venue is known.

A candidate failing any check is rejected, and a reference with no passing candidate is left with
NO DOI and reported. Nothing is guessed, and a near-miss is never rounded up to a match.

Preprints, plugin URLs and similar non-article references legitimately have no DOI; they are marked
'not applicable' rather than searched.

Output: results/reference_dois.csv (one row per reference, with the decision and the evidence).
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "reference_dois.csv"
API = "https://api.crossref.org/works"
# Crossref asks for a contact in the User-Agent so it can reach you about abusive polling. A
# personal address does not belong in a public repository, so this reads from the environment and
# falls back to the project URL, which Crossref accepts.
UA = "coronav-reference-check/1.0 ({})".format(
    os.environ.get("CROSSREF_CONTACT", "https://github.com/Rugved3-droid/coronav"))

TITLE_MIN = 0.90
YEAR_TOL = 1

# (ref number, title, first-author surname, year, expected venue token or "", known DOI or "")
REFS = [
    (1, "Learning-based autonomous navigation, benchmark environments and simulation framework for endovascular interventions",
     "Karstensen", 2025, "Computers in Biology and Medicine", ""),
    (2, "Deep reinforcement learning for guidewire navigation in coronary artery phantom",
     "Kweon", 2021, "IEEE Access", "10.1109/ACCESS.2021.3135277"),
    (3, "Recurrent neural networks for generalization towards the vessel geometry in autonomous endovascular guidewire navigation in the aortic arch",
     "Karstensen", 2023, "International Journal of Computer Assisted Radiology and Surgery", ""),
    (4, "", "", 0, "", "NOT_APPLICABLE:software plugin, cited by URL"),
    (5, "Lumen diameter of normal human coronary arteries",
     "Dodge", 1992, "Circulation", ""),
    (6, "SOFA - an open source framework for medical simulation",
     "Allard", 2007, "Studies in Health Technology and Informatics", ""),
    (7, "CathSim: an open-source simulator for endovascular intervention",
     "Jianu", 2024, "IEEE Transactions on Medical Robotics and Bionics", ""),
    (8, "", "", 0, "", "NOT_APPLICABLE:arXiv preprint, cited by arXiv identifier"),
    (9, "The Vascular Model Repository: a public resource of medical imaging data and blood flow simulation results",
     "Wilson", 2013, "Journal of Medical Devices", ""),
    (10, "Annotated computed tomography coronary angiogram images and associated data of normal and diseased arteries",
     "Gharleghi", 2023, "Scientific Data", ""),
    (11, "", "", 0, "", "NOT_APPLICABLE:vendor announcement, cited by URL"),
    (12, "Combining mortality and longitudinal measures in clinical trials",
     "Finkelstein", 1999, "Statistics in Medicine", ""),
    (13, "The win ratio: a new approach to the analysis of composite endpoints in clinical trials based on clinical priorities",
     "Pocock", 2012, "European Heart Journal", ""),
    (14, "Estimates of location based on rank tests",
     "Hodges", 1963, "Annals of Mathematical Statistics", ""),
    (15, "A simple sequentially rejective multiple test procedure",
     "Holm", 1979, "Scandinavian Journal of Statistics", ""),
    (16, "Probable inference, the law of succession, and statistical inference",
     "Wilson", 1927, "Journal of the American Statistical Association", ""),
]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def query(title: str, surname: str, rows: int = 5) -> list[dict]:
    q = urllib.parse.urlencode({
        "query.bibliographic": f"{title} {surname}",
        "rows": rows,
        "select": "DOI,title,author,issued,container-title,type",
    })
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)["message"]["items"]


def year_of(item: dict) -> int | None:
    for k in ("issued", "published-print", "published-online"):
        parts = (item.get(k) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def check(item: dict, title: str, surname: str, year: int, venue: str) -> tuple[bool, dict]:
    cand_title = (item.get("title") or [""])[0]
    t = sim(title, cand_title)
    authors = " ".join(f"{a.get('family', '')}" for a in item.get("author") or [])
    a_ok = norm(surname) in norm(authors) if surname else False
    y = year_of(item)
    y_ok = y is not None and abs(y - year) <= YEAR_TOL
    cont = (item.get("container-title") or [""])[0]
    if venue:
        tokens = [w for w in norm(venue).split() if len(w) > 3]
        v_ok = any(w in norm(cont) for w in tokens) if tokens else True
    else:
        v_ok = True
    ok = t >= TITLE_MIN and a_ok and y_ok and v_ok
    return ok, {"cand_title": cand_title, "title_sim": round(t, 3), "author_ok": a_ok,
                "cand_year": y, "year_ok": y_ok, "container": cont, "venue_ok": v_ok}


def main() -> int:
    rows = []
    for num, title, surname, year, venue, known in REFS:
        if known.startswith("NOT_APPLICABLE"):
            rows.append({"ref": num, "decision": "no DOI - not applicable",
                         "doi": "", "reason": known.split(":", 1)[1], "title_sim": "",
                         "matched_title": "", "matched_container": "", "matched_year": ""})
            print(f"[{num:>2}] not applicable — {known.split(':', 1)[1]}")
            continue
        try:
            items = query(title, surname)
        except Exception as exc:  # network or API failure is reported, never silently skipped
            rows.append({"ref": num, "decision": "UNRESOLVED - query failed", "doi": "",
                         "reason": str(exc)[:120], "title_sim": "", "matched_title": "",
                         "matched_container": "", "matched_year": ""})
            print(f"[{num:>2}] QUERY FAILED: {exc}")
            continue
        best = None
        for it in items:
            ok, ev = check(it, title, surname, year, venue)
            if ok and (best is None or ev["title_sim"] > best[1]["title_sim"]):
                best = (it, ev)
        if best is None:
            top = items[0] if items else {}
            _, ev = check(top, title, surname, year, venue) if top else (False, {})
            rows.append({"ref": num, "decision": "UNRESOLVED - no candidate passed all checks",
                         "doi": "", "reason": f"best hit: {ev.get('cand_title', 'none')[:70]!r} "
                                              f"sim={ev.get('title_sim')} author_ok={ev.get('author_ok')} "
                                              f"year={ev.get('cand_year')}",
                         "title_sim": ev.get("title_sim", ""), "matched_title": "",
                         "matched_container": "", "matched_year": ""})
            print(f"[{num:>2}] UNRESOLVED — {rows[-1]['reason']}")
        else:
            it, ev = best
            doi = it["DOI"]
            agree = (not known) or known.lower() == doi.lower()
            rows.append({"ref": num, "decision": "verified" + ("" if agree else " - DISAGREES WITH EXISTING"),
                         "doi": doi, "reason": "" if agree else f"manuscript had {known}",
                         "title_sim": ev["title_sim"], "matched_title": ev["cand_title"],
                         "matched_container": ev["container"], "matched_year": ev["cand_year"]})
            flag = "" if agree else "  *** DISAGREES WITH THE DOI ALREADY IN THE MANUSCRIPT ***"
            print(f"[{num:>2}] {doi}  sim={ev['title_sim']}  {ev['container'][:42]}{flag}")
        time.sleep(1.0)  # be polite to a free public API

    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["ref", "decision", "doi", "title_sim", "matched_title",
                                           "matched_container", "matched_year", "reason"])
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["decision"].startswith("verified"))
    na = sum(1 for r in rows if "not applicable" in r["decision"])
    un = len(rows) - ok - na
    print(f"\nverified: {ok}   not applicable: {na}   unresolved: {un}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
