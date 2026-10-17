"""
ASOCA centerline adapter v3 — returns Branch objects compatible with run pipeline.

Public API
----------
asoca_left_coronary_branches(case_n, zip_path, group, min_len_mm, prox_mm)
    -> (List[Branch], ins_pt, ins_dir)
    Same return type as coronary_fixture.pth_centerlines.left_coronary_branches.

asoca_load_stl(case_n, zip_path, group)
    -> pyvista PolyData (full coronary mesh, both LCA and RCA, already in mm)

Heuristic: v3 (min-length filter + most-dissimilar proximal direction + apex alignment).
Validated: Normal_12 (correct, n_lca=4), Normal_5 (correct, n_lca=2).
"""

import os
import sys
import tempfile
import zipfile

import numpy as np
from scipy.spatial import cKDTree

STEVE_ROOT = r'D:\steve\stEVE'
sys.path.insert(0, STEVE_ROOT)

from eve.intervention.vesseltree.util.branch import Branch

ZIP_PATH    = r'D:\ASOCADataAccess.zip'
MIN_LEN_MM  = 60.0
PROX_MM     = 60.0


# ── Low-level loaders ────────────────────────────────────────────────────────

def asoca_load_stl(case_n, zip_path=ZIP_PATH, group='Normal'):
    """Load ASOCA surface mesh from zip. Returns pyvista PolyData (mm, no scaling)."""
    import pyvista as pv
    Z = zipfile.ZipFile(zip_path)
    key = f'ASOCADataAccess/{group}/SurfaceMeshes/{group}_{case_n}.stl'
    data = Z.read(key)
    Z.close()
    t = tempfile.NamedTemporaryFile(suffix='.stl', delete=False)
    t.write(data); t.flush(); t.close()
    mesh = pv.read(t.name)
    os.unlink(t.name)
    return mesh


def _load_cl_paths(case_n, zip_path=ZIP_PATH, group='Normal'):
    """Load ASOCA centerline cells from zip. Returns list of (N,3) float64 arrays (mm)."""
    import pyvista as pv
    Z = zipfile.ZipFile(zip_path)
    key = f'ASOCADataAccess/{group}/Centerlines/{group}_{case_n}.vtp'
    data = Z.read(key)
    Z.close()
    t = tempfile.NamedTemporaryFile(suffix='.vtp', delete=False)
    t.write(data); t.flush(); t.close()
    cl = pv.read(t.name)
    os.unlink(t.name)
    pts = cl.points
    return [pts[cl.get_cell(i).point_ids] for i in range(cl.n_cells)]


# ── LCA group detection ──────────────────────────────────────────────────────

def _group_by_start(cells, tol=1.0):
    sp = [c[0] for c in cells]
    assigned = [False] * len(cells)
    groups = []
    for i in range(len(cells)):
        if assigned[i]:
            continue
        grp = [i]; assigned[i] = True
        for j in range(i + 1, len(cells)):
            if not assigned[j] and np.linalg.norm(sp[i] - sp[j]) < tol:
                grp.append(j); assigned[j] = True
        groups.append(grp)
    return groups


def _path_len(c):
    return float(np.sum(np.linalg.norm(np.diff(c, axis=0), axis=1)))


# ── LM/bifurcation detection ─────────────────────────────────────────────────

def _find_lm_and_bif(lca_paths, tol=1.5):
    ref = max(lca_paths, key=len)
    kd = cKDTree(ref)
    bif_indices = []
    for other in lca_paths:
        if other is ref:
            continue
        dists, idxs = kd.query(other)
        close = dists < tol
        if close.any():
            bif_indices.append(int(idxs[int(np.where(close)[0].max())]))
    if not bif_indices:
        return None, None, ref
    pri = min(bif_indices)
    return ref[: pri + 1], ref[pri], ref


# ── v3 post-bif extraction and LAD/LCX assignment ────────────────────────────

def _extract_post_bif(lca_paths, bif_pt):
    branches = []
    for path in lca_paths:
        dists = np.linalg.norm(path - bif_pt, axis=1)
        bif_idx = int(np.argmin(dists))
        seg = np.vstack([bif_pt.reshape(1, 3), path[bif_idx:]])
        branches.append((seg, _path_len(seg), path))
    return branches


def _proximal_dir(seg, mm=60.0):
    cumlen = 0.0
    for i in range(1, len(seg)):
        cumlen += float(np.linalg.norm(seg[i] - seg[i - 1]))
        if cumlen >= mm:
            diff = seg[i] - seg[0]
            n = float(np.linalg.norm(diff))
            return diff / (n + 1e-9)
    diff = seg[-1] - seg[0]
    n = float(np.linalg.norm(diff))
    return diff / (n + 1e-9)


def _lad_lcx_v3(branches, bif_pt, prox_mm=PROX_MM, min_len_mm=MIN_LEN_MM):
    eligible = [(i, b) for i, b in enumerate(branches) if b[1] >= min_len_mm]
    if len(eligible) < 2:
        raise ValueError(f'<2 eligible branches after {min_len_mm}mm filter')
    dirs = {i: _proximal_dir(b[0], mm=prox_mm) for i, b in eligible}
    min_dot = 2.0
    ci, cj = eligible[0][0], eligible[1][0]
    for a in range(len(eligible)):
        for bx in range(a + 1, len(eligible)):
            ia, ib = eligible[a][0], eligible[bx][0]
            d = float(np.dot(dirs[ia], dirs[ib]))
            if d < min_dot:
                min_dot = d; ci, cj = ia, ib
    all_ends = [b[2][-1] for b in branches]
    end_dists = [float(np.linalg.norm(e - bif_pt)) for e in all_ends]
    apex_pt = all_ends[int(np.argmax(end_dists))]
    apex_dir = apex_pt - bif_pt
    apex_dir /= float(np.linalg.norm(apex_dir)) + 1e-9
    si = float(np.dot(dirs[ci], apex_dir))
    sj = float(np.dot(dirs[cj], apex_dir))
    lad_idx, lcx_idx = (ci, cj) if si >= sj else (cj, ci)
    return lad_idx, lcx_idx, 1.0 - min_dot


# ── Public API ────────────────────────────────────────────────────────────────

def asoca_left_coronary_branches(case_n, zip_path=ZIP_PATH, group='Normal',
                                  min_len_mm=MIN_LEN_MM, prox_mm=PROX_MM):
    """
    Load ASOCA Normal case and return (branches, ins_pt, ins_dir) using v3 heuristic.

    Returns
    -------
    branches : List[Branch]
        [left_main, lad, lcx, <sub-branches that pass min_len filter>]
    ins_pt   : (3,) float32  — left main ostium in mm
    ins_dir  : (3,) float32  — unit vector pointing distally into LM
    """
    cells = _load_cl_paths(case_n, zip_path=zip_path, group=group)
    groups = _group_by_start(cells)
    lca_grp = max(groups, key=lambda g: np.mean([_path_len(cells[i]) for i in g]))
    lca_paths = [cells[i] for i in lca_grp]

    lm_coords, bif_pt, _ = _find_lm_and_bif(lca_paths)
    if lm_coords is None:
        raise ValueError(f'No bifurcation found for ASOCA Normal_{case_n}')

    post_bif = _extract_post_bif(lca_paths, bif_pt)
    lad_idx, lcx_idx, dissim = _lad_lcx_v3(post_bif, bif_pt,
                                             prox_mm=prox_mm, min_len_mm=min_len_mm)

    branches = []
    branches.append(Branch('left_main', lm_coords.astype(np.float32)))
    branches.append(Branch('lad',       post_bif[lad_idx][0].astype(np.float32)))
    branches.append(Branch('lcx',       post_bif[lcx_idx][0].astype(np.float32)))

    sub_idx = 1
    for i, (seg, length, _) in enumerate(post_bif):
        if i not in (lad_idx, lcx_idx) and length >= min_len_mm:
            branches.append(Branch(f'lad_b{sub_idx}', seg.astype(np.float32)))
            sub_idx += 1

    ins_pt  = lm_coords[0].astype(np.float32)
    dir_vec = lm_coords[1] - lm_coords[0]
    ins_dir = (dir_vec / np.linalg.norm(dir_vec)).astype(np.float32)

    return branches, ins_pt, ins_dir


def asoca_all_lca_coords(case_n, zip_path=ZIP_PATH, group='Normal'):
    """Return all left-system centerline coords stacked as (N,3) float32.
    Used by the mesh clipper to build the KD-tree for proximity clipping."""
    branches, _, _ = asoca_left_coronary_branches(case_n, zip_path=zip_path,
                                                   group=group)
    return np.vstack([b.coordinates for b in branches]).astype(np.float32)
