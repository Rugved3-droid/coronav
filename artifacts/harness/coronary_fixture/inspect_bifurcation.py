"""
Step A — Mesh geometry inspection at the LM→LAD bifurcation.

Wire escaped at step 10: tip jumped from (-40.48, 188.71, -132.30) [inside lad_b1]
to (-41.76, 182.61, -121.49) [d_CL=10.17mm, free space].  Jump vector crosses the
LM/LAD/LCX crotch region.  We inspect the mesh at that location for:

  1. Open boundary edges (holes) — free edges shared by only one face
  2. Non-manifold edges — shared by 3+ faces (self-intersection or fold)
  3. Geometry defects within a 15mm search radius around the escape mid-point
  4. Wall thickness proxy — nearest-opposite-surface distance at the crotch
  5. Watertightness of the region (open edge loop closure)
"""

import os, sys
import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

from coronary_fixture.pth_centerlines import left_coronary_branches

MODEL_DIR = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
PATH_DIR  = os.path.join(MODEL_DIR, "Paths")
VTP_PATH  = os.path.join(HERE, "clipped_left.vtp")
OBJ_PATH  = os.path.join(HERE, "clipped_left.obj")

# Step-9 and step-10 tip positions from the traverse (vessel CS = mm)
STEP9_TIP  = np.array([-40.48, 188.71, -132.30])
STEP10_TIP = np.array([-41.76, 182.61, -121.49])
ESCAPE_MID = (STEP9_TIP + STEP10_TIP) / 2   # midpoint of the jump
SEARCH_R   = 15.0   # mm radius for local defect search

print("=" * 70)
print("STEP A — Mesh geometry at LM→LAD bifurcation")
print("=" * 70)
print(f"\nStep-9 tip  (last contained) : {STEP9_TIP}")
print(f"Step-10 tip (first escaped)  : {STEP10_TIP}")
print(f"Jump vector                  : {STEP10_TIP - STEP9_TIP}")
print(f"Jump magnitude               : {np.linalg.norm(STEP10_TIP - STEP9_TIP):.2f} mm")
print(f"Search centre (jump midpoint): {ESCAPE_MID}")
print(f"Search radius                : {SEARCH_R} mm")

# ── Load mesh ─────────────────────────────────────────────────────────────────
print(f"\nLoading {VTP_PATH} ...")
mesh = pv.read(VTP_PATH)
pts  = np.asarray(mesh.points)
print(f"  {mesh.n_points} vertices, {mesh.n_cells} faces")

# ── 1. Open boundary edges ────────────────────────────────────────────────────
print("\n--- 1. Open boundary edges (free edges) ---")
boundary = mesh.extract_feature_edges(
    boundary_edges=True,
    non_manifold_edges=False,
    feature_edges=False,
    manifold_edges=False,
)
b_pts = np.asarray(boundary.points)
n_boundary_pts = b_pts.shape[0]
print(f"  Total boundary-edge points in mesh : {n_boundary_pts}")

if n_boundary_pts > 0:
    # Find boundary points near the escape zone
    kd_b = cKDTree(b_pts)
    idx_near = kd_b.query_ball_point(ESCAPE_MID, SEARCH_R)
    near_b_pts = b_pts[idx_near] if idx_near else np.empty((0, 3))
    print(f"  Boundary-edge points within {SEARCH_R}mm of escape mid: {len(idx_near)}")

    # Show them
    if len(idx_near) > 0:
        print(f"  >> OPEN BOUNDARY EDGES FOUND NEAR BIFURCATION <<")
        for i, p in enumerate(near_b_pts):
            dist = np.linalg.norm(p - ESCAPE_MID)
            print(f"    [{i:3d}] ({p[0]:7.2f}, {p[1]:7.2f}, {p[2]:7.2f})  "
                  f"dist_to_mid={dist:.2f}mm")
    else:
        print("  No boundary edges within search radius — region looks closed.")

    # Also find closest boundary point to step-9 and step-10 tips
    d9, _ = kd_b.query(STEP9_TIP)
    d10, _ = kd_b.query(STEP10_TIP)
    print(f"\n  Nearest boundary-edge point to step-9  tip: {d9:.2f} mm")
    print(f"  Nearest boundary-edge point to step-10 tip: {d10:.2f} mm")
else:
    print("  No boundary edges found anywhere in mesh.")

# ── 2. Non-manifold edges ─────────────────────────────────────────────────────
print("\n--- 2. Non-manifold edges (shared by 3+ faces) ---")
nonmanifold = mesh.extract_feature_edges(
    boundary_edges=False,
    non_manifold_edges=True,
    feature_edges=False,
    manifold_edges=False,
)
nm_pts = np.asarray(nonmanifold.points)
print(f"  Total non-manifold-edge points in mesh : {nm_pts.shape[0]}")

if nm_pts.shape[0] > 0:
    kd_nm = cKDTree(nm_pts)
    idx_near_nm = kd_nm.query_ball_point(ESCAPE_MID, SEARCH_R)
    print(f"  Non-manifold-edge points within {SEARCH_R}mm of escape mid: {len(idx_near_nm)}")
    if len(idx_near_nm) > 0:
        print(f"  >> NON-MANIFOLD EDGES NEAR BIFURCATION <<")
        for p in nm_pts[idx_near_nm]:
            print(f"    ({p[0]:7.2f}, {p[1]:7.2f}, {p[2]:7.2f})")
    d9_nm, _ = kd_nm.query(STEP9_TIP)
    d10_nm, _ = kd_nm.query(STEP10_TIP)
    print(f"  Nearest non-manifold point to step-9  tip: {d9_nm:.2f} mm")
    print(f"  Nearest non-manifold point to step-10 tip: {d10_nm:.2f} mm")
else:
    print("  No non-manifold edges found.")

# ── 3. Local face density at crotch (thinness proxy) ─────────────────────────
print(f"\n--- 3. Local face sampling near bifurcation (r={SEARCH_R}mm) ---")
kd_all = cKDTree(pts)
idx_local = kd_all.query_ball_point(ESCAPE_MID, SEARCH_R)
print(f"  Mesh vertices within {SEARCH_R}mm of escape mid: {len(idx_local)}")

# Faces whose ALL vertices are within search radius
cells = mesh.faces.reshape(-1, 4)[:, 1:]   # (N,3) triangle indices
mask  = np.all(np.isin(cells, idx_local), axis=1)
local_faces = cells[mask]
print(f"  Faces fully within {SEARCH_R}mm of escape mid : {local_faces.shape[0]}")

# ── 4. Wall thickness proxy: for each local vertex, find the nearest mesh point
#       on the OPPOSITE side (using ray-casting or nearest-but-not-self).
#       Proxy: for each local surface point, nearest OTHER surface point distance.
print(f"\n--- 4. Wall thickness proxy (min inter-surface distance at bifurcation) ---")
if len(idx_local) > 1:
    local_pts = pts[idx_local]
    # For each local point, find nearest other local point (skip self by offset)
    kd_local = cKDTree(local_pts)
    # Query with k=2 (skip self), take second-nearest
    dists, _ = kd_local.query(local_pts, k=2)
    nearest_other = dists[:, 1]  # distance to nearest non-self local point
    print(f"  Min distance between local surface vertices : {nearest_other.min():.3f} mm")
    print(f"  Mean distance between local surface vertices: {nearest_other.mean():.3f} mm")
    print(f"  Note: this is vertex spacing, not true wall thickness.")

    # True wall thickness proxy: for each local surface point, cast through the
    # normal and find the nearest OPPOSITE surface point.
    # Simplified: find pairs of surface points within a tight range (1-10mm apart)
    # that are on geometrically opposite sides of the tube.
    # We use: for every local pt, find all local pts at distance 0.5-8mm away.
    pairs_close = []
    for i, p in enumerate(local_pts):
        d_others, _ = kd_local.query(p, k=min(50, len(local_pts)))
        # Wall thickness estimate: pairs separated 0.5-6mm are likely opposite walls
        for d in d_others:
            if 0.5 <= d <= 6.0:
                pairs_close.append(d)
    if pairs_close:
        print(f"  Vertex pairs 0.5-6mm apart (wall thickness range): {len(pairs_close)}")
        print(f"  Min separation in 0.5-6mm range: {min(pairs_close):.3f} mm  "
              f"(likely wall thickness floor)")
        print(f"  Mean separation in 0.5-6mm range: {np.mean(pairs_close):.3f} mm")
    else:
        print("  No vertex pairs in 0.5-6mm range near bifurcation.")
else:
    print("  Insufficient local vertices for thickness analysis.")

# ── 5. Ostium check — the INTENDED open boundary ─────────────────────────────
print("\n--- 5. Ostium check (expected open boundary at insertion) ---")
branches, ins_pt, ins_dir = left_coronary_branches(PATH_DIR, junction_radius_mm=3.0)
ins_pt_arr = np.asarray(ins_pt)
print(f"  Insertion point: ({ins_pt_arr[0]:.2f}, {ins_pt_arr[1]:.2f}, {ins_pt_arr[2]:.2f}) mm")

if n_boundary_pts > 0:
    kd_b2 = cKDTree(b_pts)
    idx_ostium = kd_b2.query_ball_point(ins_pt_arr, 10.0)
    print(f"  Boundary-edge points within 10mm of insertion: {len(idx_ostium)}")
    if len(idx_ostium) > 0:
        print("  (This is the intended ostium opening — expected.)")

    # How many boundary points are NOT near the ostium?
    idx_all_b  = np.arange(n_boundary_pts)
    non_ostium = [i for i in idx_all_b if np.linalg.norm(b_pts[i] - ins_pt_arr) > 15.0]
    print(f"  Boundary-edge points far (>15mm) from ostium: {len(non_ostium)}")
    if non_ostium:
        non_pts = b_pts[non_ostium]
        print(f"  >> UNEXPECTED OPEN BOUNDARIES (not ostium) <<")
        # Cluster them by proximity and print representative points
        rep_printed = 0
        printed_set = []
        for p in non_pts:
            if all(np.linalg.norm(p - q) > 5.0 for q in printed_set):
                dist_to_esc = np.linalg.norm(p - ESCAPE_MID)
                print(f"    ({p[0]:7.2f}, {p[1]:7.2f}, {p[2]:7.2f})  "
                      f"dist_to_escape_mid={dist_to_esc:.1f}mm")
                printed_set.append(p)
                rep_printed += 1
                if rep_printed >= 20:
                    print(f"    ... ({len(non_ostium) - rep_printed} more)")
                    break
    else:
        print("  All boundary edges are near the ostium — no unexpected holes.")

# ── 6. Summary ────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("GEOMETRY SUMMARY")
print("=" * 70)
print(f"  Total boundary-edge pts  : {n_boundary_pts}")
print(f"  Non-manifold-edge pts    : {nm_pts.shape[0]}")
print(f"  Local faces at crotch    : {local_faces.shape[0]} (within {SEARCH_R}mm)")
if n_boundary_pts > 0 and 'idx_near' in dir():
    print(f"  Boundary pts at escape   : {len(idx_near)}")
print()
print("Done.")
