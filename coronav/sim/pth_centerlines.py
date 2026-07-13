"""VMR .pth centerline loader and source-agnostic branch-tree builder.

Ported from stEVE/coronary_fixture/pth_centerlines.py.

Public API
----------
left_coronary_branches(path_dir, junction_radius_mm=3.0)
    -> (List[Branch], insertion_point, insertion_direction)

load_vmr_pth(path_dir, include_prefixes=None, scale=10)
    -> dict {name_lower: np.ndarray (N,3) mm}

build_branch_tree(named_paths_mm, junction_radius_mm=3.0)
    -> List[Branch]
"""
import os
from typing import Dict, List, Optional, Tuple
from xml.dom import minidom

import numpy as np

from eve.intervention.vesseltree.util.branch import Branch


def load_vmr_pth(
    path_dir: str,
    include_prefixes: Optional[List[str]] = None,
    scale: float = 10.0,
) -> Dict[str, np.ndarray]:
    """Load SimVascular .pth centerline files.

    Parameters
    ----------
    include_prefixes : load only files whose stem starts with one of these.
    scale : multiply coordinates by this factor (VMR files are in cm; default 10 -> mm).
    """
    result = {}
    for fname in sorted(os.listdir(path_dir)):
        if not fname.lower().endswith(".pth"):
            continue
        stem = fname[:-4]
        if include_prefixes is not None:
            if not any(stem.lower().startswith(p.lower()) for p in include_prefixes):
                continue
        coords = _parse_pth(os.path.join(path_dir, fname), scale)
        if len(coords) > 1:
            result[stem.lower()] = coords
    return result


def _parse_pth(filepath: str, scale: float) -> np.ndarray:
    with open(filepath, "r", encoding="utf-8") as fh:
        next(fh)
        next(fh)
        tree = minidom.parse(fh)
    pts = []
    for pt in tree.getElementsByTagName("pos"):
        pts.append([
            float(pt.attributes["x"].value) * scale,
            float(pt.attributes["y"].value) * scale,
            float(pt.attributes["z"].value) * scale,
        ])
    return np.array(pts, dtype=np.float32)


def build_branch_tree(
    named_paths_mm: Dict[str, np.ndarray],
    junction_radius_mm: float = 3.0,
    trunk_name: str = "left_main",
) -> List[Branch]:
    """Reconstruct non-overlapping vessel topology from overlapping centerline paths.

    One path may carry a shared proximal trunk (LM) before the first bifurcation.
    This function detects that path, splits it into trunk + branch-proper, and
    returns all branches with non-overlapping coordinates.
    """
    if not named_paths_mm:
        return []

    names = list(named_paths_mm.keys())
    all_coords = [named_paths_mm[n] for n in names]
    start_pts = np.array([c[0] for c in all_coords])

    hit_counts = []
    min_dist_to_others = []
    for i, c in enumerate(all_coords):
        hits = sum(
            1 for j, c2 in enumerate(all_coords)
            if i != j and np.linalg.norm(c - c2[0], axis=1).min() <= junction_radius_mm
        )
        hit_counts.append(hits)
        others = np.delete(start_pts, i, axis=0)
        min_dist_to_others.append(float(np.linalg.norm(others - start_pts[i], axis=1).min()))

    scores = [h * 1000 + d for h, d in zip(hit_counts, min_dist_to_others)]
    root_idx = int(np.argmax(scores))
    root_name = names[root_idx]
    root_coords = all_coords[root_idx]

    primary_bifurc_idx = len(root_coords) - 1
    found_bifurc = False
    for i, (n, c) in enumerate(zip(names, all_coords)):
        if n == root_name:
            continue
        dists = np.linalg.norm(root_coords - c[0], axis=1)
        if dists.min() <= junction_radius_mm:
            idx = int(np.argmin(dists))
            if idx < primary_bifurc_idx:
                primary_bifurc_idx = idx
                found_bifurc = True

    branches: List[Branch] = []
    if found_bifurc and primary_bifurc_idx > 0:
        branches.append(Branch(trunk_name, root_coords[: primary_bifurc_idx + 1]))
        branches.append(Branch(root_name, root_coords[primary_bifurc_idx:]))
    else:
        branches.append(Branch(root_name, root_coords))

    for n, c in zip(names, all_coords):
        if n != root_name:
            branches.append(Branch(n, c))

    return branches


def left_coronary_branches(
    path_dir: str,
    junction_radius_mm: float = 3.0,
) -> Tuple[List[Branch], np.ndarray, np.ndarray]:
    """Load left-system VMR paths and return (branches, insertion_pt, insertion_dir).

    The insertion point is the proximal end of the detected trunk (LM ostium).
    """
    raw = load_vmr_pth(path_dir, include_prefixes=["LAD", "LCX"])
    if not raw:
        raise FileNotFoundError(f"No LAD/LCX .pth files found in: {path_dir}")

    branches = build_branch_tree(raw, junction_radius_mm=junction_radius_mm)

    trunk = branches[0]
    ip = trunk.coordinates[0].copy()
    dir_vec = trunk.coordinates[1] - trunk.coordinates[0]
    ip_dir = (dir_vec / np.linalg.norm(dir_vec)).astype(np.float32)

    return branches, ip, ip_dir
