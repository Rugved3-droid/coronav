"""
Clip 0066_H_CORO_H surface mesh to the left coronary system only.

Strategy
--------
Keep surface cells whose centroid is within CLIP_RADIUS_MM of any point
on the left-system centerlines (LAD, LCX, and all sub-branches).
Then extract the largest connected component of the kept region.

Outputs (relative to coronary_fixture/)
----------------------------------------
  clipped_left.vtp   -- for verification / pyvista
  clipped_left.obj   -- for SOFA MeshObjLoader via FromMesh

Run from the stEVE repo root:
    python coronary_fixture/clip_left_coronary.py
"""

import os
import sys
import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from coronary_fixture.pth_centerlines import load_vmr_pth

# ── Paths ───────────────────────────────────────────────────────────────────
HERE       = os.path.dirname(os.path.abspath(__file__))
REPO       = os.path.dirname(HERE)
MODEL_DIR  = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H")
MESH_DIR   = os.path.join(MODEL_DIR, "Meshes")
PATH_DIR   = os.path.join(MODEL_DIR, "Paths")
OUT_VTP    = os.path.join(HERE, "clipped_left.vtp")
OUT_OBJ    = os.path.join(HERE, "clipped_left.obj")

SCALE           = 10      # VMR cm -> mm
CLIP_RADIUS_MM  = 4.0     # keep cells within this distance of left-side CL


def find_file(directory, ext):
    for f in os.listdir(directory):
        if f.endswith(ext):
            return os.path.join(directory, f)
    raise FileNotFoundError(f"No *{ext} in {directory}")


def main():
    # ── Load left-system centerline points ──────────────────────────────────
    raw_paths = load_vmr_pth(PATH_DIR, include_prefixes=["LAD", "LCX"], scale=SCALE)
    left_pts = np.vstack(list(raw_paths.values()))
    print(f"Left-system centerline: {len(raw_paths)} paths, {len(left_pts)} total points")

    # ── Load and scale surface mesh ──────────────────────────────────────────
    vtp_path = find_file(MESH_DIR, ".vtp")
    surf = pv.read(vtp_path)
    surf.scale([SCALE] * 3, inplace=True)
    print(f"Full mesh: {surf.n_points} vertices, {surf.n_cells} faces")

    # ── Build KD-tree and compute cell-centroid distances ────────────────────
    kd = cKDTree(left_pts)
    centroids = surf.cell_centers().points          # (N_cells, 3)
    dists, _ = kd.query(centroids, workers=-1)

    # ── Extract cells within threshold ──────────────────────────────────────
    keep_idx = np.where(dists < CLIP_RADIUS_MM)[0]
    clipped = surf.extract_cells(keep_idx)
    # convert UnstructuredGrid -> PolyData
    clipped = clipped.extract_surface()
    print(f"After clip (r={CLIP_RADIUS_MM}mm): {clipped.n_points} verts, {clipped.n_cells} faces")

    # ── Keep largest connected component ────────────────────────────────────
    conn = clipped.connectivity()
    region_ids = conn.point_data["RegionId"]
    unique, counts = np.unique(region_ids, return_counts=True)
    largest_id = unique[np.argmax(counts)]
    n_components = len(unique)
    print(f"Connected components after clip: {n_components}")

    final = conn.threshold(
        value=(largest_id - 0.5, largest_id + 0.5), scalars="RegionId"
    ).extract_surface()
    print(f"Largest component: {final.n_points} verts, {final.n_cells} faces")

    # ── Verify bbox is in plausible coronary range ───────────────────────────
    b = final.bounds
    extents = (b[1]-b[0], b[3]-b[2], b[5]-b[4])
    max_ext = max(extents)
    assert 15 < max_ext < 200, (
        f"UNITS ERROR: max extent {max_ext:.1f} mm is outside 15-200 mm range."
    )
    print(f"\nBBox X: [{b[0]:.1f}, {b[1]:.1f}] extent={extents[0]:.1f} mm")
    print(f"BBox Y: [{b[2]:.1f}, {b[3]:.1f}] extent={extents[1]:.1f} mm")
    print(f"BBox Z: [{b[4]:.1f}, {b[5]:.1f}] extent={extents[2]:.1f} mm")
    print(f"Units sanity: max extent {max_ext:.1f} mm -- PASS")

    # ── Final connectivity check ─────────────────────────────────────────────
    conn2 = final.connectivity()
    n_final_comp = len(np.unique(conn2.point_data["RegionId"]))
    print(f"Final connected components: {n_final_comp}  (want 1)")

    # ── Robust normal repair ─────────────────────────────────────────────────
    # VMR surface meshes have normals pointing OUTWARD from the lumen (VTK default
    # for a surface bounding a filled solid).  SOFA's TriangleCollisionModel +
    # LocalMinDistance detects contact only from the normal-facing side of each
    # triangle.  Wire inside the lumen must be on that side → normals must point
    # INWARD.  vmr.py:166 achieves this with a bare flip_normals(); here we do it
    # robustly:
    #
    #   DECIMATE first → then consistent-orient → flip inward
    #
    # Order matters: VTK's decimation re-scrambles face winding, so normals must
    # be fixed AFTER decimation, not before.

    print("\n--- Robust normal repair ---")

    # Step 1: remove degenerate / duplicate geometry
    n_raw = final.n_cells
    final = final.clean()
    print(f"  Degenerate/duplicate removed : {n_raw - final.n_cells} faces "
          f"({final.n_points} verts, {final.n_cells} faces remain)")

    # Step 2: decimate to SOFA-tractable face count (BEFORE fixing normals,
    # because decimation reorders face windings).
    # vmr.py uses decimate(0.9) keeping 10%; for a pre-clipped mesh keep 15%
    # to preserve sub-mm coronary curvature while keeping BVH/LCP fast.
    DECIMATE_FACTOR = 0.85   # remove 85%, keep 15%
    n_before_dec = final.n_cells
    final = final.decimate(DECIMATE_FACTOR)
    print(f"  Decimation (85% reduction)   : {n_before_dec} -> {final.n_cells} faces  "
          f"({final.n_points} verts remain)")

    # Step 3: manifold analysis on decimated mesh
    non_mani = final.extract_feature_edges(
        boundary_edges=False, non_manifold_edges=True,
        feature_edges=False, manifold_edges=False
    )
    boundary_fe = final.extract_feature_edges(
        boundary_edges=True, non_manifold_edges=False,
        feature_edges=False, manifold_edges=False
    )
    n_nm  = non_mani.n_cells
    n_bnd = boundary_fe.n_cells
    print(f"  Non-manifold edges           : {n_nm}  "
          f"({'WARN — orientation may be unreliable' if n_nm > 0 else 'OK'})")
    print(f"  Boundary edges (open ostia)  : {n_bnd}  (expected for open tube)")

    # Step 4: capture per-face normals before any reorientation
    normals_pre = final.compute_normals(
        cell_normals=True, point_normals=False,
        consistent_normals=False, auto_orient_normals=False,
    ).cell_data["Normals"].copy()

    # Step 5: make winding globally consistent + auto-orient outward
    final = final.compute_normals(
        cell_normals=True, point_normals=True,
        consistent_normals=True, auto_orient_normals=True,
        non_manifold_traversal=(n_nm > 0),
    )
    normals_post = final.cell_data["Normals"].copy()

    # Count faces the consistency pass had to reorient (dot < 0 → winding reversed)
    dot_pp = np.einsum("ij,ij->i", normals_pre, normals_post)
    n_reoriented = int(np.sum(dot_pp < 0))
    pct_reoriented = 100.0 * n_reoriented / final.n_cells
    print(f"  Faces reoriented (consistency): {n_reoriented} / {final.n_cells} "
          f"({pct_reoriented:.1f}%)")
    if n_reoriented == 0:
        print("    -> All faces already consistently wound")
    elif pct_reoriented > 45 and pct_reoriented < 55:
        print("    -> ~50% reoriented: consistently wound but global sense was flipped by decimation")
    else:
        print(f"    -> {n_reoriented} locally inconsistent faces repaired")

    # Step 6: verify global orientation relative to lumen interior
    # Reference: centroid of all left-system centerline points = inside the lumen
    lumen_center = left_pts.mean(axis=0)
    face_centers = final.cell_centers().points
    to_lumen = lumen_center - face_centers            # vectors from faces → lumen center
    dot_inward = np.einsum("ij,ij->i", normals_post, to_lumen)
    n_inward  = int(np.sum(dot_inward > 0))
    pct_inward = 100.0 * n_inward / final.n_cells
    print(f"  After auto_orient: inward-facing faces : {n_inward} / {final.n_cells} "
          f"({pct_inward:.1f}%)")
    print(f"  Global orientation after auto_orient   : "
          f"{'INWARD (unusual)' if pct_inward > 50 else 'OUTWARD (expected)'}")

    # Step 7: flip ALL normals to point inward — matches vmr.py:166 behaviour
    final.flip_normals()
    # (cell_data["Normals"] array is not refreshed by flip_normals in this pyvista
    # version; the FACE VERTEX ORDER in the saved OBJ is what SOFA uses — verified
    # to be reversed relative to pre-flip by direct inspection of the OBJ f-lines.)
    print(f"  flip_normals() applied — OBJ face winding is now INWARD for SOFA")

    # ── Save ─────────────────────────────────────────────────────────────────
    final.save(OUT_VTP)
    print(f"\nSaved: {OUT_VTP}")

    pv.save_meshio(OUT_OBJ, final)
    print(f"Saved: {OUT_OBJ}")

    return {
        "n_vertices": final.n_points,
        "n_faces": final.n_cells,
        "bbox_mm": b,
        "n_components": n_final_comp,
    }


if __name__ == "__main__":
    main()
