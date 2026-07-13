# A1 Anatomy — VMR0066 (Vascular Model Repository)

This directory contains the coronary geometry for the default CoroNav anatomy (A1).

## Source

- **Dataset**: Vascular Model Repository (VMR), case 0066
- **URL**: https://www.vascularmodel.com/
- **License**: See `LICENSE_VMR0066` in this directory (BSD/MIT-style, permissive)
- **Required citation**: Wilson N et al. 2013, doi:10.1115/1.4025983

## Contents

| File | Description |
|------|-------------|
| `clipped_left.obj` | Left coronary artery surface mesh (tessellated, ~742 KB) |
| `clipped_left.vtp` | Same mesh in VTK PolyData format for mask precomputation |
| `paths/LAD.pth` | Left anterior descending artery centerline (SimVascular .pth) |
| `paths/LAD_b*.pth` | LAD branch centerlines |
| `paths/LCX.pth` | Left circumflex artery centerline |
| `paths/LCX_b*.pth` | LCX branch centerlines |
| `LICENSE_VMR0066` | VMR data license (required by VMR terms — do not remove) |

## Processing

The `.obj` and `.vtp` files were derived from the VMR0066 patient geometry by:
1. Cropping to the left coronary system (LAD + LCX).
2. Smoothing the surface mesh to remove sharp edges that destabilise the LCP solver.
3. Scaling from SimVascular cm units to mm.

The `.pth` centerline files are the original VMR SimVascular paths, re-exported at
1 mm inter-point spacing and scaled to mm.

## Simulation parameters

- Wire diameter: 0.89 mm (floppy coronary guidewire)
- Insertion point: LM ostium (proximal end of left_main trunk)
- Step budget: 60 steps per episode
- Fluoroscopy: AP Cranial 40 deg, 512 x 512 px, wire-only rendering
