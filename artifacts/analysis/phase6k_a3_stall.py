"""Phase 6k — A3 stall-zone characterisation (downgraded to discussion material).

Both A3 arms plateau roughly 33-38 mm from target. A3 is a phantom, so this is no longer a
gate on anything; it is one paragraph of discussion. Done from the EXISTING TRACES only — no
ASOCA archive, no centreline recomputation, per instruction.

METHOD, with its limitation stated up front. The logged wire-tip positions (gt_tip_pos) are
used as a proxy for the vessel axis. The tip leans on the wall rather than running down the
centre, so absolute arc-length values carry that error; the COMPARISON between arms, and the
location of the stall band along the path, are what this supports.

  - arc length s[k] = cumulative |p[k] - p[k-1]| along the logged tip path
  - stall locus   = first step at which distance-to-target enters the 33-38 mm band
  - curvature     = Menger curvature of the tip path, 1/R of the circle through three
                    points spaced at least MIN_SPACING mm apart (spacing avoids the
                    degenerate triples that adjacent near-identical points produce)

READ-ONLY with respect to raw logs. No API calls.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

RESULTS = Path(__file__).resolve().parent.parent / "results"
R = r"D:\steve\pilot\runs"
TRACES = {
    "wire_only": rf"{R}\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl",
    "overlay":   rf"{R}\normal5_overlay\arm_asoca_normal5_overlay\trace.jsonl",
}
STALL_LO, STALL_HI = 33.0, 38.0
MIN_SPACING = 1.0        # mm between the three points used for a curvature estimate


def episodes(path: str):
    by: dict[int, list[dict]] = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                by[r["episode"]].append(r)
    for rows in by.values():
        rows.sort(key=lambda r: r["step"])
    return dict(by)


def menger(a, b, c) -> float:
    """Curvature of the circle through three points: 4*Area / (|ab||bc||ca|)."""
    ab, bc, ca = (np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c))
    if min(ab, bc, ca) < 1e-9:
        return float("nan")
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a))
    denom = ab * bc * ca
    return float(4.0 * area / denom) if denom > 0 else float("nan")


def path_curvature(pts: np.ndarray, idx: int) -> float:
    """Menger curvature near index idx, using neighbours at least MIN_SPACING mm away."""
    n = len(pts)
    lo = idx
    while lo > 0 and np.linalg.norm(pts[idx] - pts[lo]) < MIN_SPACING:
        lo -= 1
    hi = idx
    while hi < n - 1 and np.linalg.norm(pts[hi] - pts[idx]) < MIN_SPACING:
        hi += 1
    if lo == idx or hi == idx:
        return float("nan")
    return menger(pts[lo], pts[idx], pts[hi])


def analyse_arm(eps) -> list[dict]:
    rows = []
    for ep, raw in sorted(eps.items()):
        valid = [r for r in raw if r.get("api_ok", True) and r.get("parse_ok", True)]
        pts = np.array([r["gt_tip_pos"] for r in valid
                        if r.get("gt_tip_pos") and len(r["gt_tip_pos"]) == 3], dtype=float)
        if len(pts) < 5:
            continue
        d = np.array([r["tip_target_dist"] for r in valid
                      if r.get("gt_tip_pos") and len(r["gt_tip_pos"]) == 3], dtype=float)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        total = float(s[-1])

        band = np.nonzero((d >= STALL_LO) & (d <= STALL_HI))[0]
        if len(band) == 0:
            continue
        i = int(band[0])
        kappa_all = np.array([path_curvature(pts, k) for k in range(len(pts))], dtype=float)
        kappa_all = kappa_all[np.isfinite(kappa_all)]
        rows.append({
            "episode": ep,
            "seed": valid[-1]["seed"],
            "arc_at_stall_mm": float(s[i]),
            "arc_total_mm": total,
            "arc_frac": float(s[i] / total) if total > 0 else float("nan"),
            "dist_at_stall": float(d[i]),
            "kappa_at_stall_1_per_mm": path_curvature(pts, i),
            "kappa_median_path": float(np.median(kappa_all)) if len(kappa_all) else float("nan"),
            "steps_in_band": int(len(band)),
            "n_steps": len(valid),
        })
    return rows


def desc(vals):
    v = np.array([x for x in vals if np.isfinite(x)], dtype=float)
    if len(v) == 0:
        return "n/a"
    return (f"median {np.median(v):.3f}  IQR [{np.percentile(v,25):.3f}, "
            f"{np.percentile(v,75):.3f}]  n={len(v)}")


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 84)
    emit("PHASE 6k — A3 STALL ZONE (discussion material; phantom, not a gate)")
    emit("=" * 84)
    emit("")
    emit("Tip path used as an axis proxy: the wire leans on the wall, so absolute arc lengths")
    emit("carry that error. The arm comparison and the band's position are what this supports.")
    emit(f"Stall band: distance-to-target in [{STALL_LO:.0f}, {STALL_HI:.0f}] mm.")

    all_rows = []
    for arm, path in TRACES.items():
        rows = analyse_arm(episodes(path))
        for r in rows:
            r["arm"] = arm
        all_rows += rows
        emit("")
        emit(f"--- A3 {arm}  (n={len(rows)} episodes entering the band) " + "-" * 20)
        emit(f"  arc length at stall locus : {desc([r['arc_at_stall_mm'] for r in rows])} mm")
        emit(f"  fraction of path traversed: {desc([r['arc_frac'] for r in rows])}")
        emit(f"  curvature at stall locus  : "
             f"{desc([r['kappa_at_stall_1_per_mm'] for r in rows])} 1/mm")
        emit(f"  curvature, whole path     : {desc([r['kappa_median_path'] for r in rows])} 1/mm")
        emit(f"  steps spent inside band   : {desc([r['steps_in_band'] for r in rows])}")

    wo = [r for r in all_rows if r["arm"] == "wire_only"]
    ov = [r for r in all_rows if r["arm"] == "overlay"]
    emit("")
    emit("=" * 84)
    emit("ONE-PARAGRAPH SUMMARY")
    emit("=" * 84)
    if wo and ov:
        a_wo = np.median([r["arc_at_stall_mm"] for r in wo])
        a_ov = np.median([r["arc_at_stall_mm"] for r in ov])
        f_wo = np.median([r["arc_frac"] for r in wo])
        f_ov = np.median([r["arc_frac"] for r in ov])
        k_wo = np.nanmedian([r["kappa_at_stall_1_per_mm"] for r in wo])
        k_ov = np.nanmedian([r["kappa_at_stall_1_per_mm"] for r in ov])
        kp_wo = np.nanmedian([r["kappa_median_path"] for r in wo])
        b_wo = np.median([r["steps_in_band"] for r in wo])
        b_ov = np.median([r["steps_in_band"] for r in ov])
        emit(f"  Both A3 arms enter the 33-38 mm band at a similar point along the traversed")
        emit(f"  path: median arc length {a_wo:.1f} mm (wire-only) vs {a_ov:.1f} mm (overlay),")
        emit(f"  i.e. {f_wo:.0%} vs {f_ov:.0%} of the path each episode ultimately travels.")
        emit(f"  Local path curvature at that locus is {k_wo:.3f} 1/mm (wire-only) and")
        emit(f"  {k_ov:.3f} 1/mm (overlay), against a whole-path median of {kp_wo:.3f} 1/mm,")
        emit(f"  so the band is not a locally sharp bend relative to the rest of the course.")
        emit(f"  What separates the arms is dwell, not location: a median of {b_wo:.0f} steps")
        emit(f"  inside the band for wire-only against {b_ov:.0f} for overlay. The stall is")
        emit("  therefore better described as time spent in a region both arms reach than as a")
        emit("  geometric obstacle only one arm encounters. Because A3's wall is a generated")
        emit("  constant-radius tube, no calibre narrowing exists there by construction.")

    with open(RESULTS / "phase6k_a3_stall.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["arm", "episode", "seed", "arc_at_stall_mm",
                                           "arc_total_mm", "arc_frac", "dist_at_stall",
                                           "kappa_at_stall_1_per_mm", "kappa_median_path",
                                           "steps_in_band", "n_steps"])
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r[k] for k in w.fieldnames})

    (RESULTS / "phase6k_report.txt").write_text("\n".join(out), encoding="utf-8")
    emit("")
    emit(f"wrote {RESULTS/'phase6k_report.txt'}")
    emit(f"wrote {RESULTS/'phase6k_a3_stall.csv'}")


if __name__ == "__main__":
    main()
