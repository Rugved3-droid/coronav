"""
Verify 0066_H_CORO_H geometry and centerlines.
Reports bbox (in mm, after x10 from VMR's cm), vertex/face counts,
connected components, and LAD/LCX centerline spot-check.
"""
import os
import sys
import numpy as np
from xml.dom import minidom
import pyvista as pv

MODEL_ID = "0066_H_CORO_H"
SCALING_FACTOR = 10  # VMR ships in cm, stEVE works in mm

def find_file(directory, ext):
    for f in os.listdir(directory):
        if f.endswith(ext):
            return os.path.join(directory, f)
    return None

def load_pth(pth_path):
    with open(pth_path, "r", encoding="utf-8") as fh:
        next(fh); next(fh)
        tree = minidom.parse(fh)
    pts = []
    for pt in tree.getElementsByTagName("pos"):
        pts.append([
            float(pt.attributes["x"].value) * SCALING_FACTOR,
            float(pt.attributes["y"].value) * SCALING_FACTOR,
            float(pt.attributes["z"].value) * SCALING_FACTOR,
        ])
    return np.array(pts, dtype=np.float32)

here = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(here, "..", ".data", "vmr", MODEL_ID)
mesh_dir  = os.path.join(model_dir, "Meshes")
path_dir  = os.path.join(model_dir, "Paths")

# ── Surface mesh (.vtp) ─────────────────────────────────────────────────────
vtp_path = find_file(mesh_dir, ".vtp")
surf = pv.read(vtp_path)
surf.scale([SCALING_FACTOR]*3, inplace=True)
b = surf.bounds  # xmin xmax ymin ymax zmin zmax
bbox_mm = {
    "x": (b[0], b[1]),
    "y": (b[2], b[3]),
    "z": (b[4], b[5]),
}
extent_mm = (b[1]-b[0], b[3]-b[2], b[5]-b[4])

print("=== SURFACE MESH (.vtp) ===")
print(f"  File       : {os.path.basename(vtp_path)}")
print(f"  N vertices : {surf.n_points}")
print(f"  N faces    : {surf.n_cells}")
print(f"  BBox X mm  : [{b[0]:.1f}, {b[1]:.1f}]  extent={extent_mm[0]:.1f}")
print(f"  BBox Y mm  : [{b[2]:.1f}, {b[3]:.1f}]  extent={extent_mm[1]:.1f}")
print(f"  BBox Z mm  : [{b[4]:.1f}, {b[5]:.1f}]  extent={extent_mm[2]:.1f}")

# Connected components
conn = surf.connectivity()
n_comp = conn.get_array("RegionId").max() + 1
print(f"  Connected components: {n_comp}")

# ── Volume mesh (.vtu) ──────────────────────────────────────────────────────
vtu_path = find_file(mesh_dir, ".vtu")
vol = pv.read(vtu_path)
vol.scale([SCALING_FACTOR]*3, inplace=True)
print(f"\n=== VOLUME MESH (.vtu) ===")
print(f"  File       : {os.path.basename(vtu_path)}")
print(f"  N points   : {vol.n_points}")
print(f"  N cells    : {vol.n_cells}")
vb = vol.bounds
print(f"  BBox X mm  : [{vb[0]:.1f}, {vb[1]:.1f}]")
print(f"  BBox Y mm  : [{vb[2]:.1f}, {vb[3]:.1f}]")
print(f"  BBox Z mm  : [{vb[4]:.1f}, {vb[5]:.1f}]")

# ── Centerlines (.pth) ──────────────────────────────────────────────────────
print(f"\n=== CENTERLINES (Paths/) ===")
pth_files = sorted(f for f in os.listdir(path_dir) if f.endswith(".pth"))
print(f"  Total .pth files: {len(pth_files)}")

for name in pth_files:
    pts = load_pth(os.path.join(path_dir, name))
    label = name[:-4]
    if pts.size > 0:
        length = np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))
        print(f"  {label:20s}: {len(pts):4d} pts  length={length:6.1f} mm  "
              f"start=({pts[0,0]:.1f},{pts[0,1]:.1f},{pts[0,2]:.1f})")
    else:
        print(f"  {label:20s}: EMPTY")

# ── LAD/LCX bifurcation check ───────────────────────────────────────────────
print(f"\n=== LAD / LCX BIFURCATION CHECK ===")
lad = load_pth(os.path.join(path_dir, "LAD.pth"))
lcx = load_pth(os.path.join(path_dir, "LCX.pth"))
print(f"  LAD trunk: {len(lad)} pts, start=({lad[0,0]:.1f},{lad[0,1]:.1f},{lad[0,2]:.1f})")
print(f"  LCX trunk: {len(lcx)} pts, start=({lcx[0,0]:.1f},{lcx[0,1]:.1f},{lcx[0,2]:.1f})")
dist_lad_lcx_start = np.linalg.norm(lad[0] - lcx[0])
print(f"  Distance LAD[0]->LCX[0]: {dist_lad_lcx_start:.1f} mm  (<=5mm = shared ostium)")

# Mid-LAD candidate point (for Step 3 target)
mid_idx = len(lad) // 2
print(f"\n  Mid-LAD candidate (target): ({lad[mid_idx,0]:.1f},{lad[mid_idx,1]:.1f},{lad[mid_idx,2]:.1f})")
print(f"  (index {mid_idx} of {len(lad)} LAD trunk points)")

# ── Plausibility assertion ───────────────────────────────────────────────────
print(f"\n=== UNITS SANITY CHECK ===")
max_extent = max(extent_mm)
assert 20 < max_extent < 200, (
    f"FAIL: max extent {max_extent:.1f} mm is outside coronary range 20-200 mm. "
    "Possible units error."
)
print(f"  Max extent {max_extent:.1f} mm — PASS (20–200 mm expected for full coronary tree)")
