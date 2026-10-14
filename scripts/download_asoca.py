"""ASOCA optional-anatomy installer for CoroNav.

ASOCA data is NOT bundled because the license requires individual registration
and prohibits redistribution.  This script extracts one case from a
registration-gated ASOCA archive and then CHECKS whether the result has the
layout ``build_env()`` needs:

    clipped_left.obj   collision surface, left-coronary system, mm
    clipped_left.vtp   same surface, used for the overlay mask
    paths/LAD*.pth, paths/LCX*.pth   ordered SimVascular-style centerlines

IMPORTANT: the manuscript's A2 was produced by clipping the ASOCA Normal_12
surface to the left-coronary system and pairing it with ordered centerlines.
That preparation pipeline is NOT in this repository, and the layout of the
ASOCA archive has not been verified against this script. If the check below
fails, A2 cannot be built from this repository alone (see
docs/MANUSCRIPT_CONCORDANCE.md, issue U6).

ASOCA registration: https://asoca.grand-challenge.org/
License:            Non-commercial research only; see asoca.grand-challenge.org/data

Usage
-----
After registering and downloading the ASOCA zip(s):

    python scripts/download_asoca.py \\
        --asoca-zip /path/to/ASOCA_Normal.zip \\
        --out-dir data/anatomy

The script will:
  1. Extract the requested case(s):
       Normal_12  -> a2_asoca_n12/   (A2, retained)
       Normal_5   -> a3_asoca_n5/    (A3, EXCLUDED — only with --cases Normal_5)
  2. Write a README.md in each subdirectory with the license reminder.
  3. Report whether the files build_env() needs are present.

Note on A3 (excluded):
  ASOCA Normal_5 is excluded from the manuscript on physical-validity grounds:
  its surface is a constant-radius 2.5 mm tube generated along the patient
  centerline, so no part of its wall is patient surface, and the contact
  solver did not converge adequately on it. The tube generator is kept only so
  archived A3 runs can be re-inspected. A3 supports no manuscript claim.
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
NOTE (A3 — EXCLUDED, synthetic surface)
---------------------------------------
The .obj mesh in this directory is a SYNTHETIC TUBE (radius=2.5mm) generated
along the patient centerlines, not the patient surface. A3 is excluded from
the manuscript on physical-validity grounds (non-patient lumen; inadequate
contact-solver convergence) and supports no claim. Archival use only.
"""


def _write_readme(out_dir: Path, case_name: str, extra: str = ""):
    text = f"""\
# CoroNav anatomy: {case_name}

Source: ASOCA challenge ({case_name})
License: Non-commercial research only.
         See https://asoca.grand-challenge.org/data for full terms.
         DO NOT redistribute this data.
Required citation: Gharleghi R. et al., Sci Data 10, 128 (2023),
                   https://doi.org/10.1038/s41597-023-02016-2

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

    TUBE_RADIUS = 2.5  # mm — the excluded A3 geometry (manuscript §2.2)
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


def _missing_layout(adir: Path):
    missing = [f for f in ("clipped_left.obj", "clipped_left.vtp") if not (adir / f).exists()]
    paths = adir / "paths"
    if not (paths.exists() and any(paths.glob("LAD*.pth")) and any(paths.glob("LCX*.pth"))):
        missing.append("paths/LAD*.pth + paths/LCX*.pth")
    return missing


def main():
    parser = argparse.ArgumentParser(
        description="Install ASOCA anatomy for CoroNav (A2; A3 is excluded).",
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
        default=["Normal_12"],
        choices=list(CASE_MAP.keys()),
        help="Which ASOCA cases to install. Default: Normal_12 (A2). "
             "Normal_5 (A3) is excluded from the manuscript; archival use only.",
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

        missing = _missing_layout(out_dir)
        if missing:
            print(f"  NOT READY: {out_dir} lacks {', '.join(missing)}.")
            print("  The extracted ASOCA files must be converted to this layout; the")
            print("  conversion used for the manuscript is not in this repository.")
        else:
            print(f"  Done: {out_dir} has the layout build_env() needs.\n")

    print("Run smoke test:  python scripts/check_install.py")
    print("Run A2:          python benchmarks/run_benchmark.py --operator claude --anatomy a2 --mode wire_only overlay")


if __name__ == "__main__":
    main()
