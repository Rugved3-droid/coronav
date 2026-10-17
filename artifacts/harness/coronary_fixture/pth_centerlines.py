"""
VMR .pth adapter  +  source-agnostic coronary tree topology builder.

Public API
----------
load_vmr_pth(path_dir, include_prefixes=None, scale=10)
    -> dict {name_lower: np.ndarray (N,3) in mm}

build_branch_tree(named_paths_mm, junction_radius_mm=3.0)
    -> List[Branch]

    Reconstructs non-overlapping topology from independently-traced paths.
    One path may include a shared proximal trunk (e.g. LAD.pth carries
    the left main before the LAD proper). This function:
      1. Detects that "root" path (its proximal tip is farthest from all
         other paths' starts, meaning it extends into shared territory).
      2. Finds the primary bifurcation: the first point along the root
         that is within junction_radius_mm of any other path's start.
      3. Splits root -> trunk ("left_main") + root-branch-proper.
      4. Leaves all other paths as-is (they start at their junctions).

    Compatible with ASOCA .vtp centerlines once loaded through a thin
    adapter that returns the same {name: coords_mm} dict format.
"""

import os
from typing import Dict, List, Optional, Tuple
from xml.dom import minidom

import numpy as np

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from eve.intervention.vesseltree.util.branch import Branch


# ── VMR .pth adapter ────────────────────────────────────────────────────────

def load_vmr_pth(
    path_dir: str,
    include_prefixes: Optional[List[str]] = None,
    scale: float = 10.0,
) -> Dict[str, np.ndarray]:
    """
    Load SimVascular .pth centerline files from path_dir.

    Parameters
    ----------
    include_prefixes : list of str or None
        If given, only load files whose stem starts with one of these
        (case-insensitive). E.g. ["LAD", "LCX"] drops aorta and RCA.
    scale : float
        Multiply all coordinates by this factor (default 10: cm -> mm).

    Returns
    -------
    dict mapping lowercase stem -> (N,3) float32 array in mm.
    """
    result = {}
    for fname in sorted(os.listdir(path_dir)):
        if not fname.lower().endswith(".pth"):
            continue
        stem = fname[:-4]
        if include_prefixes is not None:
            if not any(stem.lower().startswith(p.lower())
                       for p in include_prefixes):
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


# ── Source-agnostic topology builder ────────────────────────────────────────

def build_branch_tree(
    named_paths_mm: Dict[str, np.ndarray],
    junction_radius_mm: float = 3.0,
    trunk_name: str = "left_main",
) -> List[Branch]:
    """
    Reconstruct non-overlapping vessel tree topology from overlapping paths.

    Parameters
    ----------
    named_paths_mm : {name: (N,3) float32 mm}
        Independently-traced centerline paths. ONE path may carry a shared
        proximal trunk before the first bifurcation; all others start at
        their own junction point.
    junction_radius_mm : float
        If another path's first point is within this distance of a root-path
        point, that root point is a bifurcation.
    trunk_name : str
        Name assigned to the extracted shared trunk branch.

    Returns
    -------
    List of Branch objects with non-overlapping coordinates, ordered:
        [trunk, root_branch, ...other_branches...]
    """
    if not named_paths_mm:
        return []

    names = list(named_paths_mm.keys())
    all_coords = [named_paths_mm[n] for n in names]

    # ── 1. Identify root path ──────────────────────────────────────────────
    # Root = the path that:
    #   (a) passes near the most other paths' first points  [primary]
    #   (b) whose own first point is most isolated from others' starts [tiebreak]
    #
    # Rationale: a path that carries a shared trunk will intersect many
    # branching paths' starts. A distal sub-branch isolated in space may
    # also have a far-from-others start, but it intersects zero other starts.
    start_pts = np.array([c[0] for c in all_coords])  # (M, 3)

    hit_counts = []        # how many OTHER paths' starts this path passes near
    min_dist_to_others = []
    for i, c in enumerate(all_coords):
        hits = 0
        for j, c2 in enumerate(all_coords):
            if i == j:
                continue
            if np.linalg.norm(c - c2[0], axis=1).min() <= junction_radius_mm:
                hits += 1
        hit_counts.append(hits)

        others = np.delete(start_pts, i, axis=0)
        d = float(np.linalg.norm(others - start_pts[i], axis=1).min())
        min_dist_to_others.append(d)

    # Score: hits dominate; isolation breaks ties
    scores = [h * 1000 + d for h, d in zip(hit_counts, min_dist_to_others)]
    root_local_idx = int(np.argmax(scores))
    root_name = names[root_local_idx]
    root_coords = all_coords[root_local_idx]

    # ── 2. Find primary bifurcation along root ────────────────────────────
    # For each non-root path, find where its start sits on the root.
    # The EARLIEST such index is the primary bifurcation.
    primary_bifurc_idx = len(root_coords) - 1  # fallback: end of root
    found_bifurc = False
    for i, (n, c) in enumerate(zip(names, all_coords)):
        if n == root_name:
            continue
        dists = np.linalg.norm(root_coords - c[0], axis=1)
        min_d = dists.min()
        if min_d <= junction_radius_mm:
            idx = int(np.argmin(dists))
            if idx < primary_bifurc_idx:
                primary_bifurc_idx = idx
                found_bifurc = True

    # ── 3. Split root into trunk + root-branch-proper ─────────────────────
    branches: List[Branch] = []
    if found_bifurc and primary_bifurc_idx > 0:
        trunk_coords = root_coords[: primary_bifurc_idx + 1]
        root_branch_coords = root_coords[primary_bifurc_idx:]
        branches.append(Branch(trunk_name, trunk_coords))
        branches.append(Branch(root_name, root_branch_coords))
    else:
        # Root has no earlier shared trunk; use as-is.
        branches.append(Branch(root_name, root_coords))

    # ── 4. Add all non-root paths as-is ────────────────────────────────────
    for n, c in zip(names, all_coords):
        if n == root_name:
            continue
        branches.append(Branch(n, c))

    return branches


# ── Convenience: full left-coronary load + build ─────────────────────────────

def left_coronary_branches(
    path_dir: str,
    junction_radius_mm: float = 3.0,
) -> Tuple[List[Branch], np.ndarray, np.ndarray]:
    """
    Load left-system VMR paths and return (branch_list, insertion_point, insertion_dir).

    The insertion point is the proximal end of the detected trunk (left main ostium).
    Direction points distally into the vessel.

    Returns
    -------
    branches : List[Branch]
    insertion_point : (3,) float32 mm
    insertion_direction : (3,) float32 unit vector
    """
    raw = load_vmr_pth(path_dir, include_prefixes=["LAD", "LCX"])
    if not raw:
        raise FileNotFoundError(f"No LAD/LCX .pth files found in {path_dir}")

    branches = build_branch_tree(raw, junction_radius_mm=junction_radius_mm)

    # The trunk is always first in the returned list.
    trunk = branches[0]
    ip = trunk.coordinates[0].copy()
    dir_vec = trunk.coordinates[1] - trunk.coordinates[0]
    ip_dir = (dir_vec / np.linalg.norm(dir_vec)).astype(np.float32)

    return branches, ip, ip_dir


# ── CLI: print branch tree report ───────────────────────────────────────────

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser()
    parser.add_argument("path_dir", help="Directory containing .pth files")
    parser.add_argument("--radius", type=float, default=3.0)
    args = parser.parse_args()

    branches, ip, ip_dir = left_coronary_branches(args.path_dir, args.radius)

    print(f"\nInsertion point : ({ip[0]:.2f}, {ip[1]:.2f}, {ip[2]:.2f}) mm")
    print(f"Insertion dir   : ({ip_dir[0]:.3f}, {ip_dir[1]:.3f}, {ip_dir[2]:.3f})")
    print(f"\nBranch tree ({len(branches)} branches):")
    print(f"{'Name':<20} {'Pts':>4} {'Length(mm)':>10} {'Start':>36} {'End':>36}")
    print("-" * 110)
    for b in branches:
        l = float(np.sum(np.linalg.norm(np.diff(b.coordinates, axis=0), axis=1)))
        s = b.coordinates[0]
        e = b.coordinates[-1]
        print(f"  {b.name:<18} {len(b.coordinates):>4} {l:>10.1f}"
              f"  ({s[0]:.1f},{s[1]:.1f},{s[2]:.1f})"
              f"  ({e[0]:.1f},{e[1]:.1f},{e[2]:.1f})")
