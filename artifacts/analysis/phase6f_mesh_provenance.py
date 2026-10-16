"""Phase 6f-rev — mesh provenance audit.

The submitted Methods say a BIFURCATION REGION of A3 was reconstructed as a synthetic
tube and that A3 is "only partly patient-derived". clip_asoca_left.py:249-251 replaces the
mesh WHOLESALE via generate_tube_fallback(), which tubes EVERY branch at a constant radius.

EXISTENTIAL CHECK: if A2 is also a generated tube, the "two independent patient-derived CT
data sources" framing does not survive.

--------------------------------------------------------------------------------------
NOTE ON A FAILED FIRST ATTEMPT (kept deliberately, so the record shows what was tried).
The first version cast rays along VERTEX normals and took the nearest hit in either
direction. That was invalid: vertex normals are averaged across adjacent faces, so on a
coarse mesh the ray strikes a neighbouring facet instead of the opposite wall. It returned
medians of 1.8-2.8 mm for vessels whose left main is ~4.5 mm across, minima of ~0.02 mm,
and it mislabelled the known-synthetic A3 tube as "patient-derived". Its numbers were
discarded, not reported.

This version casts from FACE CENTRES along the FACE normal and accepts a hit only if the
struck face is roughly ANTIPARALLEL to the origin face (dot < -0.5) and farther than
MIN_HIT mm. That is the genuine wall-to-wall crossing.
--------------------------------------------------------------------------------------

DISCRIMINATOR. A mesh built by pv.Spline(...).tube(radius=R) has every wall at exactly R
from its axis, so wall-to-wall crossings all measure 2R: near-zero spread. A patient lumen
tapers from ostium to distal vessel, so its crossings are broadly distributed.

RUN WITH THE SOFA ENV PYTHON (pyvista is not in the analysis interpreter):
    D:\\conda\\envs\\steve\\python.exe analysis\\phase6f_mesh_provenance.py

READ-ONLY. No API calls.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np

try:
    import pyvista as pv
    from scipy.spatial import cKDTree
except ImportError:  # pragma: no cover
    sys.exit("pyvista/scipy missing — run with D:\\conda\\envs\\steve\\python.exe")

OUT_JSON = r"D:\coronav\results\phase6f_mesh_provenance.json"
OUT_TXT = r"D:\coronav\results\phase6f_mesh_provenance.txt"

MESHES = {
    "A1 VMR0066":             r"D:\coronav\data\anatomy\a1_vmr0066\clipped_left.obj",
    "A2 ASOCA Normal_12":     r"D:\steve\pilot\clipped_asoca_normal12.obj",
    "A3 ASOCA Normal_5":      r"D:\steve\pilot\clipped_asoca_normal5.obj",
    "A3 N5 (pre-tube clip)":  r"D:\steve\pilot\clipped_asoca_normal5_oldorient.obj",
}

# Wire tip trajectories, used as an independent corroboration of lumen calibre.
TRACES = {
    "A2 ASOCA Normal_12": r"D:\steve\pilot\runs\normal12_wire_only\arm_asoca_normal12_wire_only\trace.jsonl",
    "A3 ASOCA Normal_5":  r"D:\steve\pilot\runs\normal5_wire_only\arm_asoca_normal5_wire_only\trace.jsonl",
}

N_SAMPLE = 3000
RAY_LEN = 30.0
MIN_HIT = 0.60          # mm; below this the ray struck a neighbouring facet
ANTIPARALLEL = -0.5     # required dot(normal_hit, normal_origin)
SEED = 20260911


def wall_to_wall(mesh, rng):
    """Distance across the lumen at sampled faces, cast along the face normal."""
    m = mesh.compute_normals(cell_normals=True, point_normals=False,
                             consistent_normals=True, auto_orient_normals=False,
                             inplace=False)
    nrm = np.asarray(m.cell_data["Normals"], dtype=float)
    ctr = np.asarray(m.cell_centers().points, dtype=float)

    n = len(ctr)
    idx = rng.choice(n, size=min(N_SAMPLE, n), replace=False)

    out = []
    for i in idx:
        p, v = ctr[i], nrm[i]
        nv = np.linalg.norm(v)
        if not np.all(np.isfinite(v)) or nv < 1e-9:
            continue
        v = v / nv
        for sign in (1.0, -1.0):       # orientation-agnostic
            a = p + sign * 1e-3 * v
            b = p + sign * RAY_LEN * v
            try:
                hit, cid = m.ray_trace(a, b, first_point=True)
            except Exception:
                continue
            hit = np.atleast_1d(hit)
            if hit.size < 3 or not np.all(np.isfinite(hit[:3])):
                continue
            cid = int(np.atleast_1d(cid)[0]) if np.atleast_1d(cid).size else -1
            if cid < 0 or cid >= len(nrm):
                continue
            d = float(np.linalg.norm(hit[:3] - p))
            if d < MIN_HIT:
                continue
            # must strike the OPPOSITE wall, not a neighbouring facet
            if float(np.dot(nrm[cid] / (np.linalg.norm(nrm[cid]) + 1e-12), v)) > ANTIPARALLEL:
                continue
            out.append(d)
            break
    return np.asarray(out, dtype=float)


def tip_to_wall(trace_path, mesh):
    """Distance from each logged wire-tip position to the nearest mesh vertex.

    Corroboration only. CAVEAT: the tip is not axial — it leans on the wall — so this
    UNDERSTATES the true radius. Its SPREAD is the informative part: a constant-radius
    tube bounds it tightly, a tapering patient lumen does not.
    """
    if not os.path.exists(trace_path):
        return np.asarray([])
    kd = cKDTree(np.asarray(mesh.points, dtype=float))
    tips = []
    with open(trace_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if not (r.get("api_ok", True) and r.get("parse_ok", True)):
                continue
            t = r.get("gt_tip_pos")
            if t and len(t) == 3 and all(np.isfinite(t)):
                tips.append(t)
    if not tips:
        return np.asarray([])
    d, _ = kd.query(np.asarray(tips, dtype=float))
    return np.asarray(d, dtype=float)


def describe(d):
    if len(d) < 2:
        return {}
    return {
        "n": int(len(d)), "median": float(np.median(d)), "mean": float(np.mean(d)),
        "sd": float(np.std(d, ddof=1)),
        "cv": float(np.std(d, ddof=1) / np.mean(d)),
        "iqr": [float(np.percentile(d, 25)), float(np.percentile(d, 75))],
        "min": float(d.min()), "max": float(d.max()),
        "within_5pct_of_median": float(np.mean(np.abs(d - np.median(d)) <= 0.05 * np.median(d))),
    }


def main():
    rng = np.random.default_rng(SEED)
    out = []
    def emit(s=""):
        print(s)
        out.append(s)

    emit("=" * 98)
    emit("PHASE 6f-rev — MESH PROVENANCE AUDIT")
    emit("=" * 98)
    emit("")
    emit("Wall-to-wall crossings, cast from face centres along the face normal, accepted")
    emit("only when the struck face is antiparallel (a genuine opposite wall).")
    emit("A generated constant-radius tube -> tight spike at 2R. A patient lumen -> broad.")
    emit("")

    recs = []
    for label, path in MESHES.items():
        if not os.path.exists(path):
            emit(f"  MISSING: {label} -> {path}")
            recs.append({"label": label, "path": path, "exists": False})
            continue
        mesh = pv.read(path)
        surf = mesh if isinstance(mesh, pv.PolyData) else mesh.extract_surface()
        tri = surf.triangulate()
        bnd = tri.extract_feature_edges(boundary_edges=True, non_manifold_edges=False,
                                        feature_edges=False, manifold_edges=False)
        nm = tri.extract_feature_edges(boundary_edges=False, non_manifold_edges=True,
                                       feature_edges=False, manifold_edges=False)
        d = wall_to_wall(tri, rng)
        rec = {
            "label": label, "path": path, "exists": True,
            "file_kb": round(os.path.getsize(path) / 1024, 1),
            "n_points": int(tri.n_points), "n_cells": int(tri.n_cells),
            "boundary_edges": int(bnd.n_cells), "non_manifold_edges": int(nm.n_cells),
            "wall_to_wall": describe(d),
        }
        if label in TRACES:
            rec["tip_to_wall"] = describe(tip_to_wall(TRACES[label], tri))
        recs.append(rec)

    emit(f"{'mesh':<24} {'KB':>7} {'verts':>7} {'faces':>7} {'bnd':>5} {'nonmani':>8}")
    emit("-" * 98)
    for r in recs:
        if not r.get("exists"):
            continue
        emit(f"{r['label']:<24} {r['file_kb']:>7} {r['n_points']:>7} {r['n_cells']:>7} "
             f"{r['boundary_edges']:>5} {r['non_manifold_edges']:>8}")

    emit("")
    emit("WALL-TO-WALL LUMEN DIAMETER")
    emit(f"{'mesh':<24} {'n':>5} {'median':>8} {'IQR':>16} {'sd':>7} {'CV':>7} "
         f"{'within 5% of med':>17}")
    emit("-" * 98)
    for r in recs:
        w = r.get("wall_to_wall") or {}
        if not w:
            continue
        emit(f"{r['label']:<24} {w['n']:>5} {w['median']:>8.3f} "
             f"[{w['iqr'][0]:>6.2f},{w['iqr'][1]:>6.2f}] {w['sd']:>7.3f} {w['cv']:>7.3f} "
             f"{w['within_5pct_of_median']*100:>16.1f}%")

    emit("")
    emit("TIP-TO-WALL (corroboration; understates radius, spread is the signal)")
    for r in recs:
        t = r.get("tip_to_wall") or {}
        if not t:
            continue
        emit(f"  {r['label']:<24} n={t['n']:<6} median {t['median']:.3f} mm  "
             f"IQR [{t['iqr'][0]:.2f}, {t['iqr'][1]:.2f}]  sd {t['sd']:.3f}  "
             f"max {t['max']:.3f}")

    emit("")
    emit("VERDICT (measurement; cross-check against the generating source)")
    for r in recs:
        w = r.get("wall_to_wall") or {}
        if not w:
            continue
        if w["cv"] < 0.12 and w["within_5pct_of_median"] > 0.60:
            v = "CONSTANT CALIBRE -> generated tube, not a patient lumen surface"
        elif w["cv"] < 0.20:
            v = "narrow spread -> inspect before calling it patient-derived"
        else:
            v = "calibre varies -> consistent with a clipped patient lumen surface"
        emit(f"  {r['label']:<24} median {w['median']:.2f} mm  CV {w['cv']:.3f}  -> {v}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(recs, fh, indent=2)
    with open(OUT_TXT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    emit("")
    emit("wrote " + OUT_JSON)
    emit("wrote " + OUT_TXT)


if __name__ == "__main__":
    main()
