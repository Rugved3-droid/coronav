"""ASOCA optional-anatomy installer for CoroNav.

ASOCA data is NOT bundled because the license requires individual registration
and prohibits redistribution.  This script guides you through the manual steps
and organises the files into the layout CoroNav expects.

ASOCA registration: https://asoca.grand-challenge.org/
License:            Non-commercial research only; see asoca.grand-challenge.org/data

Usage
-----
After registering and downloading the ASOCA zip(s):

    python scripts/download_asoca.py \\
        --asoca-zip /path/to/ASOCA_Normal.zip \\
        --out-dir data/anatomy

The script will:
  1. Verify the zip contents.
  2. Extract and rename the two ASOCA cases used in the CoroNav paper:
       Normal_12  -> a2_asoca_n12/
       Normal_5   -> a3_asoca_n5/
  3. Write a README.md in each subdirectory with the license reminder.

Note on A3:
  The patient surface in Normal_5 is too narrow for guidewire simulation.
  This script extracts the centerlines and generates a synthetic tube mesh
  (radius=2.5mm) to use as the vessel wall.  This is NOT the patient surface —
  it is documented in the paper (§3.1) and in the A3 README.
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_ROOT = ROOT / "data" / "anatomy"

CASE_MAP = {
    "Normal_12": "a2_asoca_n12",
    "Normal_5":  "a3_asoca_n5",
}

A3_NOTE = """\
NOTE (A3 synthetic surface)
---------------------------
The patient vessel in ASOCA Normal_5 has a lumen radius below the guidewire
diameter used in this simulation.  The .obj mesh in this directory is a
SYNTHETIC TUBE (radius=2.5mm) generated from the patient centerlines, not
the patient surface.  The centerlines themselves (.pth files) are extracted
directly from the ASOCA data and are patient-derived.

This is documented in the CoroNav paper, Section 3.1.
"""


def _write_readme(out_dir: Path, case_name: str, extra: str = ""):
    text = f"""\
# CoroNav anatomy: {case_name}

Source: ASOCA challenge ({case_name})
License: Non-commercial research only.
         See https://asoca.grand-challenge.org/data for full terms.
         DO NOT redistribute this data.
Required citation: Gharleghi et al. 2022, https://doi.org/10.1016/j.dib.2022.108543

{extra}
This directory is gitignored. Re-run scripts/download_asoca.py to regenerate.
"""
    (out_dir / "README.md").write_text(text, encoding="utf-8")


def _extract_case(zip_path: Path, case_name: str, out_dir: Path):
    """Extract one ASOCA case from the zip into out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if case_name in m]
        if not members:
            print(f"  ERROR: '{case_name}' not found in {zip_path.name}")
            print(f"  Found top-level entries: {sorted({m.split('/')[0] for m in zf.namelist()})[:10]}")
            return False

        print(f"  Extracting {len(members)} files for {case_name}...")
        for member in members:
            out_name = member.split(case_name + "/", 1)[-1]
            if not out_name:
                continue
            dest = out_dir / out_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)

    return True


def _generate_a3_tube(a3_dir: Path):
    """Generate synthetic tube mesh from A3 centerlines using numpy + vtk."""
    pth_dir = a3_dir / "paths"
    if not pth_dir.exists():
        print("  WARNING: A3 paths/ dir not found — tube generation skipped.")
        return

    try:
        import numpy as np
    except ImportError:
        print("  WARNING: numpy not available — tube generation skipped.")
        return

    try:
        import vtk
        from vtk.util.numpy_support import numpy_to_vtkIdTypeArray
    except ImportError:
        print("  INFO: vtk not available; cannot auto-generate synthetic tube.")
        print("       You can generate it manually using the centerlines in paths/.")
        (a3_dir / "TUBE_NOT_GENERATED.txt").write_text(
            "Run scripts/download_asoca.py with vtk installed to generate "
            "the synthetic tube mesh, or supply clipped_left.obj manually.\n"
        )
        return

    print("  Generating synthetic tube mesh (radius=2.5mm) from centerlines...")

    sys.path.insert(0, str(ROOT))
    from coronav.sim.pth_centerlines import load_vmr_pth

    raw = load_vmr_pth(str(pth_dir), include_prefixes=["LAD", "LCX"])
    if not raw:
        print("  WARNING: No LAD/LCX paths found — tube generation skipped.")
        return

    all_pts = np.vstack(list(raw.values()))
    center = all_pts.mean(axis=0)

    TUBE_RADIUS = 2.5  # mm — documented in paper §3.1
    N_SIDES = 8

    points = vtk.vtkPoints()
    polys = vtk.vtkCellArray()

    for path_coords in raw.values():
        n = len(path_coords)
        if n < 2:
            continue
        for i in range(n):
            tangent = (path_coords[min(i+1, n-1)] - path_coords[max(i-1, 0)])
            t_norm = np.linalg.norm(tangent)
            if t_norm < 1e-6:
                continue
            tangent /= t_norm
            perp = np.array([1.0, 0.0, 0.0])
            if abs(np.dot(perp, tangent)) > 0.9:
                perp = np.array([0.0, 1.0, 0.0])
            n1 = np.cross(tangent, perp)
            n1 /= np.linalg.norm(n1)
            n2 = np.cross(tangent, n1)

            ring_start = points.GetNumberOfPoints()
            for k in range(N_SIDES):
                angle = 2 * np.pi * k / N_SIDES
                pt = path_coords[i] + TUBE_RADIUS * (np.cos(angle) * n1 + np.sin(angle) * n2)
                points.InsertNextPoint(pt.tolist())

            if i > 0:
                prev_start = ring_start - N_SIDES
                for k in range(N_SIDES):
                    k1 = k
                    k2 = (k + 1) % N_SIDES
                    quad = vtk.vtkQuad()
                    ids = quad.GetPointIds()
                    ids.SetId(0, prev_start + k1)
                    ids.SetId(1, prev_start + k2)
                    ids.SetId(2, ring_start + k2)
                    ids.SetId(3, ring_start + k1)
                    polys.InsertNextCell(quad)

    poly_data = vtk.vtkPolyData()
    poly_data.SetPoints(points)
    poly_data.SetPolys(polys)

    obj_path = a3_dir / "clipped_left.obj"
    writer = vtk.vtkOBJWriter()
    writer.SetFileName(str(obj_path))
    writer.SetInputData(poly_data)
    writer.Write()

    vtp_path = a3_dir / "clipped_left.vtp"
    writer2 = vtk.vtkXMLPolyDataWriter()
    writer2.SetFileName(str(vtp_path))
    writer2.SetInputData(poly_data)
    writer2.Write()

    print(f"  Tube mesh written: {obj_path} ({obj_path.stat().st_size//1024} KB)")
    print(f"                     {vtp_path} ({vtp_path.stat().st_size//1024} KB)")


def main():
    parser = argparse.ArgumentParser(
        description="Install ASOCA anatomy for CoroNav (A2 + A3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--asoca-zip",
        type=Path,
        required=True,
        help="Path to the ASOCA Normal zip downloaded from the challenge website.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DATA_ROOT,
        help=f"Output anatomy directory. Default: {DATA_ROOT}",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=list(CASE_MAP.keys()),
        choices=list(CASE_MAP.keys()),
        help="Which ASOCA cases to install. Default: both Normal_12 and Normal_5.",
    )
    args = parser.parse_args()

    if not args.asoca_zip.exists():
        print(f"ERROR: {args.asoca_zip} not found.")
        print("Register at https://asoca.grand-challenge.org/ and download the ASOCA Normal zip.")
        sys.exit(1)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nInstalling ASOCA anatomy from {args.asoca_zip.name}")
    print(f"Output: {args.out_dir}\n")

    for case_name in args.cases:
        dir_name = CASE_MAP[case_name]
        out_dir = args.out_dir / dir_name

        print(f"[{case_name} -> {dir_name}]")
        ok = _extract_case(args.asoca_zip, case_name, out_dir)
        if not ok:
            continue

        extra = A3_NOTE if case_name == "Normal_5" else ""
        _write_readme(out_dir, case_name, extra)

        if case_name == "Normal_5":
            _generate_a3_tube(out_dir)

        print(f"  Done: {out_dir}\n")

    print("Installation complete.")
    print("Run smoke test:  python scripts/check_install.py")
    print("Run benchmark:   python benchmarks/run_benchmark.py --operator claude --anatomy a1 a2 a3")


if __name__ == "__main__":
    main()
