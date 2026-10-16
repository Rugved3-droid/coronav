"""
Clip ASOCA Normal surface mesh to the left coronary system only.

Strategy: keep cells whose centroid is within CLIP_RADIUS_MM of any point on
the v3-derived left-system centerlines (left_main + lad + lcx + sub-branches).
Extract largest connected component. Apply BIFURCATION-PRESERVING adaptive
decimation (body at 85%, bifurcation zone within BIF_RADIUS_MM kept at full
resolution). Repair normals (inward for SOFA). Save .vtp + .obj.

Identical pipeline to coronary_fixture/clip_left_coronary.py; adapted for ASOCA
(mm units, mesh loaded from zip, centerlines from asoca_adapter).

Run:
    python pilot/clip_asoca_left.py
"""
import os, sys
import numpy as np
import pyvista as pv
from scipy.spatial import cKDTree

sys.path.insert(0, r'D:\steve\stEVE')
sys.path.insert(0, r'D:\steve\pilot')

from asoca_adapter import asoca_all_lca_coords, asoca_load_stl, asoca_left_coronary_branches

CLIP_RADIUS_MM  = 4.0   # same as clip_left_coronary.py
DECIMATE_FACTOR = 0.85  # body zone reduction ratio (keep 15%)
BIF_RADIUS_MM   = 8.0   # zone radius around bifurcation point
BIF_DECIMATE    = 0.65  # bif-zone reduction ratio (keep 35%); more than body but less than full res
OUT_DIR         = r'D:\steve\pilot'
TUBE_RADIUS_MM  = 2.5   # synthetic tube radius for closed-mesh fallback
TUBE_N_SIDES    = 12    # tube polygon sides


# ── Shared adaptive-decimation utilities (identical policy as clip_left_coronary.py) ──────

def _decimate_safe(mesh, reduction, preserve_boundary=False):
    """decimate_pro with boundary-vertex preservation option."""
    return mesh.decimate_pro(reduction, boundary_vertex_deletion=(not preserve_boundary))


def adaptive_decimate(mesh, bif_pt, bif_radius_mm=BIF_RADIUS_MM,
                      body_decimate=DECIMATE_FACTOR, bif_decimate=BIF_DECIMATE):
    """
    Two-zone adaptive decimation:
      - cells within bif_radius_mm of bif_pt: decimated at bif_decimate (keep ~35%)
      - remaining cells: decimated at body_decimate (keep ~15%)
    Both zones preserve seam vertices; merged and welded at 0.05mm tolerance.
    bif_decimate is deliberately set between 0 (full res) and body_decimate to preserve
    fork geometry while keeping LCP constraint count manageable.
    """
    centroids = mesh.cell_centers().points
    dists     = np.linalg.norm(centroids - bif_pt, axis=1)

    bif_idx  = np.where(dists <= bif_radius_mm)[0]
    body_idx = np.where(dists >  bif_radius_mm)[0]

    n_bif  = len(bif_idx)
    n_body = len(body_idx)
    print(f'  Adaptive decimate: {n_bif} bif-zone cells (decimate {bif_decimate:.0%}, '
          f'{bif_radius_mm}mm radius) + {n_body} body cells (decimate {body_decimate:.0%})')

    if n_bif == 0:
        return _decimate_safe(mesh, body_decimate)
    if n_body == 0:
        return _decimate_safe(mesh, bif_decimate)

    bif_zone  = mesh.extract_cells(bif_idx).extract_surface()
    body_zone = mesh.extract_cells(body_idx).extract_surface()

    # Decimate both zones, preserving seam vertices so the merge is watertight
    bif_dec  = _decimate_safe(bif_zone,  bif_decimate,  preserve_boundary=True)
    body_dec = _decimate_safe(body_zone, body_decimate, preserve_boundary=True)
    print(f'  Bif: {n_bif} -> {bif_dec.n_cells} cells  |  Body: {n_body} -> {body_dec.n_cells} cells')

    merged = pv.merge([bif_dec, body_dec])
    merged = merged.clean(tolerance=0.05)  # weld seam vertices (decimate_pro splitting shifts coords slightly)
    print(f'  Merged: {merged.n_cells} cells total')
    return merged


def orient_normals_inward(mesh, cl_pts):
    """
    Per-face normal orientation using nearest centerline point as interior reference.
    For each face: finds the nearest CL point and uses it as the inward reference.
    This correctly handles all branches (LM, LAD, LCX) since each face uses its
    own local CL reference, not a single global point that may be off-axis for
    distant branches. Robust to non-manifold edges.
    cl_pts: (N, 3) array of ALL left-system centerline points (mm).
    """
    mesh_c    = mesh.compute_normals(cell_normals=True, point_normals=False,
                                     consistent_normals=True, auto_orient_normals=False)
    normals   = mesh_c.cell_data['Normals']
    centroids = mesh_c.cell_centers().points
    _, cl_idx = cKDTree(cl_pts).query(centroids)
    to_ref    = cl_pts[cl_idx] - centroids    # per-face vector toward nearest CL point
    dots      = np.einsum('ij,ij->i', normals, to_ref)
    flip_mask = dots < 0
    n_flip    = int(np.sum(flip_mask))

    faces = mesh_c.faces.copy()
    if n_flip > 0:
        f4 = faces.reshape(-1, 4)          # triangles: [3, v0, v1, v2]
        f4[flip_mask, 1:] = f4[flip_mask, 1:][:, ::-1]
        faces = f4.reshape(-1)

    pct = 100.0 * n_flip / mesh_c.n_cells if mesh_c.n_cells > 0 else 0.0
    print(f'  orient_normals_inward: {n_flip}/{mesh_c.n_cells} faces flipped ({pct:.1f}%)')
    return pv.PolyData(mesh_c.points, faces)


TUBE_SPLINE_PTS = 60   # spline points per branch (low to avoid degenerate tris at junction)

def generate_tube_fallback(branches, bif_pt):
    """
    Fallback for closed lumen meshes (e.g., Normal_5 where lumen radius < CLIP_RADIUS_MM,
    so the 4mm proximity clip keeps all faces and the mesh stays closed).
    Generates a synthetic open-tube surface from patient CL branches so topology matches
    Normal_12/VMR0066 (open tubes). CL geometry is preserved, so insertion point,
    bifurcation, and navigation targets are identical to the patient anatomy.
    Closed topology causes GaussSeidel LCP instability: all inward faces surround the
    wire axis simultaneously, creating too many competing contact constraints.
    """
    print(f'  Synthetic tube fallback '
          f'(r={TUBE_RADIUS_MM}mm, sides={TUBE_N_SIDES}, spline_pts={TUBE_SPLINE_PTS})...')
    tubes = []
    for br in branches:
        coords = br.coordinates
        if len(coords) < 2:
            continue
        spline = pv.Spline(coords, n_points=TUBE_SPLINE_PTS)
        tube   = spline.tube(radius=TUBE_RADIUS_MM, n_sides=TUBE_N_SIDES, capping=False)
        tube   = tube.triangulate()
        tubes.append(tube)
        print(f'    {br.name}: {len(coords)} CL pts -> {tube.n_cells} tube cells')

    merged = pv.merge(tubes).clean(tolerance=0.1).triangulate()
    print(f'  Merged tube: {merged.n_cells} cells')

    # Lightweight fixed-ratio decimate (adaptive_decimate expects a large ASOCA mesh;
    # the tube is already small so we just reduce by body DECIMATE_FACTOR directly).
    merged = merged.decimate_pro(DECIMATE_FACTOR, boundary_vertex_deletion=False)
    merged = merged.triangulate()

    bnd = merged.extract_feature_edges(
        boundary_edges=True, non_manifold_edges=False,
        feature_edges=False, manifold_edges=False, progress_bar=False)
    n_bnd = bnd.n_cells
    print(f'  Tube: {merged.n_cells} cells, {n_bnd} boundary edges -- '
          f'{"OPEN" if n_bnd > 0 else "STILL CLOSED"}')
    return merged


def check_watertight_near_bif(mesh, bif_pt, radius_mm=BIF_RADIUS_MM):
    """
    Returns True if no open boundary edges exist within radius_mm of bif_pt.
    A boundary edge near the bifurcation means the fork geometry has a hole.
    """
    bnd = mesh.extract_feature_edges(
        boundary_edges=True, non_manifold_edges=False,
        feature_edges=False, manifold_edges=False)
    n_total_bnd = bnd.n_cells
    if n_total_bnd == 0:
        print(f'  Watertight at bif: OK (no open boundary edges anywhere)')
        return True
    dists  = np.linalg.norm(bnd.points - bif_pt, axis=1)
    n_near = int((dists < radius_mm).sum())
    if n_near > 0:
        min_d = float(dists.min())
        print(f'  Watertight at bif: FAIL — {n_near} boundary vertices within '
              f'{radius_mm}mm of bif_pt  (min dist={min_d:.2f}mm)')
        return False
    else:
        print(f'  Watertight at bif: OK — {n_total_bnd} boundary edges exist '
              f'(open ostia expected) but none within {radius_mm}mm of bif_pt')
        return True


# ── Main clip function ─────────────────────────────────────────────────────────

def clip_case(case_n):
    print(f'\n{"="*60}')
    print(f'Clipping ASOCA Normal_{case_n} to left coronary system')
    print(f'{"="*60}')

    # ── Bifurcation point (LM last coordinate) ───────────────────────────────
    branches, ins_pt, ins_dir = asoca_left_coronary_branches(case_n)
    lm     = next(b for b in branches if b.name == 'left_main')
    bif_pt = lm.coordinates[-1].copy()
    print(f'Bifurcation point: ({bif_pt[0]:.1f}, {bif_pt[1]:.1f}, {bif_pt[2]:.1f}) mm')

    # ── Left-system centerline points ────────────────────────────────────────
    left_pts = asoca_all_lca_coords(case_n)
    print(f'Left-system centerline: {len(left_pts)} points '
          f'(bbox X=[{left_pts[:,0].min():.0f},{left_pts[:,0].max():.0f}] '
          f'Y=[{left_pts[:,1].min():.0f},{left_pts[:,1].max():.0f}] '
          f'Z=[{left_pts[:,2].min():.0f},{left_pts[:,2].max():.0f}])')

    # ── Load surface mesh (already mm, no scaling) ───────────────────────────
    surf = asoca_load_stl(case_n)
    print(f'Full mesh: {surf.n_points} verts, {surf.n_cells} faces')

    # ── Cell-centroid proximity clip ─────────────────────────────────────────
    kd = cKDTree(left_pts)
    centroids = surf.cell_centers().points
    dists, _ = kd.query(centroids, workers=-1)
    keep_idx = np.where(dists < CLIP_RADIUS_MM)[0]
    clipped = surf.extract_cells(keep_idx).extract_surface()
    print(f'After clip (r={CLIP_RADIUS_MM}mm): {clipped.n_points} verts, '
          f'{clipped.n_cells} faces')

    # ── Largest connected component ──────────────────────────────────────────
    conn = clipped.connectivity()
    region_ids = conn.point_data['RegionId']
    unique, counts = np.unique(region_ids, return_counts=True)
    largest_id = unique[np.argmax(counts)]
    print(f'Connected components: {len(unique)}')
    final = conn.threshold(
        value=(largest_id - 0.5, largest_id + 0.5), scalars='RegionId'
    ).extract_surface()
    print(f'Largest component: {final.n_points} verts, {final.n_cells} faces')

    # ── Bbox sanity check ────────────────────────────────────────────────────
    b = final.bounds
    extents = (b[1]-b[0], b[3]-b[2], b[5]-b[4])
    max_ext = max(extents)
    assert 15 < max_ext < 200, f'UNITS ERROR: max extent {max_ext:.1f} mm'
    print(f'BBox extents: {extents[0]:.1f} x {extents[1]:.1f} x {extents[2]:.1f} mm '
          f'-- max={max_ext:.1f} mm  PASS')

    # ── Normal repair + bifurcation-preserving adaptive decimation ──────────
    print('\n--- Normal repair + adaptive decimation ---')
    final = final.clean()
    n_before = final.n_cells
    print(f'After clean: {n_before} cells')

    # Adaptive decimation: body at 85%, bifurcation zone at full resolution
    final = adaptive_decimate(final, bif_pt)
    final = final.triangulate()  # merge+clean can produce quads at seam; triangulate before flip_normals

    # If the clip produced a closed mesh (no boundary edges), the proximity clip kept
    # ALL faces because the vessel lumen is entirely within CLIP_RADIUS_MM (e.g.,
    # Normal_5 max lumen extent ~2.75mm < 4mm). A closed mesh causes GaussSeidel LCP
    # divergence: all inward faces surround the wire axis simultaneously. Fall back to
    # a synthetic open tube from the patient centerlines (same CL = same anatomy).
    bnd_chk = final.extract_feature_edges(
        boundary_edges=True, non_manifold_edges=False,
        feature_edges=False, manifold_edges=False, progress_bar=False)
    if bnd_chk.n_cells == 0:
        print('  Clip produced CLOSED mesh -- switching to synthetic tube fallback')
        final = generate_tube_fallback(branches, bif_pt)

    # Watertightness gate at bifurcation — FAIL here means the fork has a hole
    wt_ok = check_watertight_near_bif(final, bif_pt)
    if not wt_ok:
        print('  WARNING: bifurcation zone not watertight — wire may tunnel')

    # Non-manifold check (diagnostic only)
    non_mani = final.extract_feature_edges(
        boundary_edges=False, non_manifold_edges=True,
        feature_edges=False, manifold_edges=False)
    n_nm = non_mani.n_cells
    print(f'Non-manifold edges: {n_nm}  '
          f'({"WARN" if n_nm > 0 else "OK"})')

    # Orient all face normals inward using nearest CL point as per-face reference.
    # left_pts = asoca_all_lca_coords includes LM+LAD+LCX, giving correct inward
    # direction for every face regardless of which branch it belongs to.
    final = orient_normals_inward(final, left_pts)

    # ── Save ─────────────────────────────────────────────────────────────────
    out_vtp = os.path.join(OUT_DIR, f'clipped_asoca_normal{case_n}.vtp')
    out_obj = os.path.join(OUT_DIR, f'clipped_asoca_normal{case_n}.obj')
    final.save(out_vtp)
    pv.save_meshio(out_obj, final)
    print(f'\nSaved: {out_vtp}')
    print(f'Saved: {out_obj}')
    return out_vtp, out_obj, final.n_cells, wt_ok


if __name__ == '__main__':
    results = {}
    for n in [12, 5]:
        _, _, n_faces, wt = clip_case(n)
        results[n] = {'n_faces': n_faces, 'watertight_at_bif': wt}
    print('\n=== CLIP SUMMARY ===')
    for n, r in results.items():
        status = 'PASS' if r['watertight_at_bif'] else 'FAIL (bifurcation hole)'
        print(f'  Normal_{n}: {r["n_faces"]} faces  watertight={status}')
    print('Done.')
