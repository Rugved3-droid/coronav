"""A1 calibre check against the Dodge et al. (1992) figures the paper cites as motivation.

THE CLAIM UNDER TEST (manuscript/related_work.md, carried from the submission): coronary navigation
is harder than aortic-arch navigation because "the left main is approximately 4.5 mm in diameter
and the distal LAD approximately 1.9 mm [5]". An earlier mesh measurement returned a median
wall-to-wall diameter of 1.81 mm on A1, which is not obviously consistent with that. The mesh method
was only ever validated as a relative discriminator between meshes, so it cannot settle the
question. This script does not use the mesh.

SOURCE. VMR ships the clinical lumen segmentation for case 0066 as lofted contour groups
(Segmentations/*.ctgr). Each contour is a closed polygon lying in the plane perpendicular to the
centreline at its path point - i.e. it is already a cross-section. Area is computed exactly from
the polygon (Newell's method), and calibre is reported as the equivalent-circle diameter
d = 2 * sqrt(A / pi). Coordinates are in cm (the project's own loader multiplies by 10 to reach
mm: coronary_fixture/pth_centerlines.py, `scale=10.0  # cm -> mm`).

SEGMENT ASSIGNMENT uses the SIMULATOR'S OWN branch definition, not a new one:
left_coronary_branches(PATH_DIR, junction_radius_mm=3.0) - the call the A1 environment is built
with. Each contour is labelled by the nearest branch centreline. "Distal LAD" is the distal third of
the LAD branch by index along its centreline. That is a coarse proxy for Dodge's distal-LAD segment
and is stated as such.

DECISION RULE, RECORDED BEFORE THE NUMBERS WERE SEEN. The cited figures are population means and
this is a single anatomy. A segment is CONSISTENT with the cited figure if its median equivalent
diameter lies within +/-25% of it (left main 3.4-5.6 mm; distal LAD 1.4-2.4 mm). The tolerance is a
judgement call and is recorded as one. If either segment falls outside it, the motivation sentence
must change.

RUN WITH THE SOFA ENV PYTHON (the branch loader lives in the stEVE fixture).
"""
from __future__ import annotations

import csv
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

STEVE_ROOT = r"D:\steve\stEVE"
sys.path.insert(0, STEVE_ROOT)
from coronary_fixture.pth_centerlines import left_coronary_branches  # noqa: E402

CASE = os.path.join(STEVE_ROOT, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR = os.path.join(CASE, "Paths")
SEG_DIR = os.path.join(CASE, "Segmentations")
RESULTS = r"D:\coronav\results"
CM_TO_MM = 10.0

CITED = {"left_main": 4.5, "distal_lad": 1.9}   # Dodge et al. 1992, as cited in the manuscript
TOL = 0.25


def polygon_area(pts: np.ndarray) -> float:
    """Exact area of a planar polygon in 3-D (Newell's method)."""
    n = np.zeros(3)
    for i in range(len(pts)):
        n += np.cross(pts[i], pts[(i + 1) % len(pts)])
    return 0.5 * float(np.linalg.norm(n))


def read_contours(path: str) -> list[dict]:
    # SimVascular .ctgr files carry TWO top-level elements (<format/> then <contourgroup>), which
    # is not well-formed XML and which ElementTree rejects outright ("junk after document
    # element"). The project's own .pth loader works around the same property. Strip the
    # declaration and wrap both elements in a synthetic root; the contour data is untouched.
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if text.lstrip().startswith("<?xml"):
        text = text.split("?>", 1)[1]
    root = ET.fromstring("<ctgr_root>" + text + "</ctgr_root>")
    out = []
    for c in root.iter("contour"):
        pos = c.find("path_point/pos")
        cp = c.find("contour_points")
        if pos is None or cp is None:
            continue
        pts = np.array([[float(p.get("x")), float(p.get("y")), float(p.get("z"))]
                        for p in cp.iter("point")]) * CM_TO_MM
        if len(pts) < 3:
            continue
        centre = np.array([float(pos.get(k)) for k in "xyz"]) * CM_TO_MM
        area = polygon_area(pts)
        out.append({"centre": centre, "area_mm2": area,
                    "d_eq_mm": 2.0 * math.sqrt(area / math.pi), "n_pts": len(pts)})
    return out


def main() -> int:
    branches, _, _ = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
    coords = {b.name: np.asarray(b.coordinates, dtype=float) for b in branches}

    lines = []
    def emit(s=""):
        print(s, flush=True)
        lines.append(s)

    emit("=" * 84)
    emit("A1 CALIBRE CHECK — VMR 0066 clinical lumen segmentation vs Dodge et al. (1992)")
    emit("=" * 84)
    emit(f"branches from the simulator's own loader: {sorted(coords)}")

    rows, groups = [], {"left_main": [], "distal_lad": [], "proximal_lad": []}
    for fn in ("LAD.ctgr", "LCX.ctgr"):
        for c in read_contours(os.path.join(SEG_DIR, fn)):
            best, bd, bidx = None, float("inf"), -1
            for name in ("left_main", "lad", "lcx"):
                if name not in coords:
                    continue
                d = np.linalg.norm(coords[name] - c["centre"], axis=1)
                i = int(np.argmin(d))
                if d[i] < bd:
                    best, bd, bidx = name, float(d[i]), i
            seg = best
            if best == "lad":
                frac = bidx / max(1, len(coords["lad"]) - 1)
                seg = "distal_lad" if frac >= 2 / 3 else ("proximal_lad" if frac < 1 / 3 else "mid_lad")
            if seg in groups:
                groups[seg].append(c["d_eq_mm"])
            rows.append([fn, seg, f"{bd:.2f}", f"{c['area_mm2']:.3f}", f"{c['d_eq_mm']:.3f}"])

    emit("")
    verdicts = {}
    for seg in ("left_main", "proximal_lad", "distal_lad"):
        v = groups[seg]
        if not v:
            emit(f"  {seg:<13} no contours assigned")
            continue
        med = float(np.median(v))
        line = (f"  {seg:<13} n={len(v):2d}  equivalent diameter median {med:.2f} mm  "
                f"range [{min(v):.2f}, {max(v):.2f}]")
        if seg in CITED:
            ref = CITED[seg]
            ok = abs(med - ref) <= TOL * ref
            verdicts[seg] = ok
            line += (f"   cited {ref} mm -> {'CONSISTENT' if ok else 'NOT CONSISTENT'} "
                     f"(tolerance +/-{int(TOL*100)}%: {ref*(1-TOL):.1f}-{ref*(1+TOL):.1f} mm)")
        emit(line)

    emit("")
    if verdicts and all(verdicts.values()):
        emit("VERDICT: A1's clinical segmentation supports the cited calibres. The motivation")
        emit("sentence stands; the earlier 1.81 mm mesh figure was a measurement artefact, as")
        emit("suspected, and is not quoted.")
    else:
        emit("VERDICT: at least one segment falls outside the pre-stated tolerance. The motivation")
        emit("sentence must change to quote A1's own measured calibres rather than the population")
        emit("figures.")

    with open(os.path.join(RESULTS, "phase7_calibre_a1.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["contour_group", "segment", "dist_to_centreline_mm", "area_mm2", "d_eq_mm"])
        w.writerows(rows)
    with open(os.path.join(RESULTS, "phase7_calibre_a1_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    emit(f"wrote {os.path.join(RESULTS, 'phase7_calibre_a1_report.txt')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
