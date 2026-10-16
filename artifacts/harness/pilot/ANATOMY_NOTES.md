# Anatomy Notes for Coronary VLM Pilot

## VMR 0066 (Left Coronary, patient-derived throughout)

- Mesh: `D:\steve\stEVE\coronary_fixture\clipped_left.obj`
- Source: SimVascular VMR case 0066_H_CORO_H, surface mesh clipped to left coronary
  by proximity to LAD/LCX centerlines (CLIP_RADIUS_MM=4mm).
- Commit: **coronary-nav-v1** (d25e515) — this is the LOCKED mesh for the entire study.
- Faces: 15,897 | Non-manifold edges: 0 | Boundary edges: 81
- Watertight at bifurcation: 3 boundary vertices at 7.56mm from bif_pt (pre-existing
  anatomical feature of the LM/LAD junction; does not cause instability with this mesh).
- Stability gate: PASS — target reached in 26 steps, max_d_CL=3.44mm, seed=2001.
- VLM history: 15 episodes run at coronary-nav-v1 (Findings 1 and 2).

**DO NOT re-run `clip_left_coronary.py` for the study.** Any regeneration risks
introducing non-manifold edges at the LM/LAD junction (confirmed this session: the
adaptive-decimation reprocess produced 3 non-manifold edges → non-deterministic SOFA →
stability failure). The tagged mesh is the canonical source.

If regeneration is ever needed: use the nav-v1 clip pipeline (no adaptive_decimate),
verify 0 non-manifold edges, re-run the 40-step stability check, and confirm target
reached before using.

---

## ASOCA Normal_12 (Left Coronary, patient-derived throughout)

- Mesh: `D:\steve\pilot\clipped_asoca_normal12.obj`
- Source: ASOCA challenge dataset, Normal case 12, surface mesh clipped to left coronary
  by proximity to asoca_adapter-derived centerlines (CLIP_RADIUS_MM=4mm), with
  bifurcation-preserving adaptive decimation (BIF_RADIUS_MM=8mm, BIF_DECIMATE=0.65).
- Faces: (see clip_asoca_left.py output) | Watertight at bif: OK
- Stability gate: PASS — target reached in 11 steps, max_d_CL=2.37mm, seed=3001.
- Patient-derived surface mesh throughout. Geometry is representative of real anatomy.

---

## ASOCA Normal_5 — SYNTHETIC TUBE FALLBACK (methods/limitations note)

- Mesh: `D:\steve\pilot\clipped_asoca_normal5.obj`
- Source: ASOCA challenge dataset, Normal case 5, **SYNTHETIC OPEN TUBE** generated from
  patient centerlines. NOT a clipped patient surface mesh.

### Why synthetic

Normal_5's lumen extends only 0–2.75mm from the nearest centerline point (vessel radius
≤ 2.75mm). The standard 4mm proximity clip (CLIP_RADIUS_MM=4mm) keeps ALL faces of the
patient surface mesh — the resulting mesh is CLOSED (no boundary edges). A closed mesh
with 100% inward-facing normals surrounds the wire axis from all lateral directions
simultaneously, over-constraining the GaussSeidel LCP solver → deterministic divergence
at step 3 (confirmed: exit code 5, d_CL=38mm spike).

The fix: `generate_tube_fallback()` in `clip_asoca_left.py` detects a closed mesh after
the clip+decimate pipeline and replaces it with a synthetic open tube built from
`pv.Spline().tube(radius=2.5mm, n_sides=12, capping=False)` along the same patient
centerlines.

### What is preserved vs. synthetic

| Property | Status |
|----------|--------|
| Centerline geometry (LM, LAD, LCX paths) | **Patient-derived** — from ASOCA case 5 |
| Bifurcation location | **Patient-derived** — bif_pt = LM last coordinate |
| Insertion point and direction | **Patient-derived** — LM ostium |
| Navigation targets (mid-LAD BranchIndex) | **Patient-derived** — LAD coordinates |
| Lumen surface geometry | **Synthetic** — uniform 2.5mm tube radius, 12-sided polygon |
| Vessel wall irregularities, taper, curvature | **Not represented** |

### Implications for methods/limitations

1. **Real patient anatomy is NOT represented at the surface level** for Normal_5.
   The wire navigates a smooth synthetic tube, not an irregular patient vessel.
2. **Bifurcation geometry is anatomically placed but not anatomically shaped.**
   The T-junction of LM/LAD/LCX tubes is a geometric approximation; a real bifurcation
   has a gradual flare and sinus. The wire may behave differently at the fork than in vivo.
3. **Stability result is expected to be easier than patient mesh.** The synthetic tube
   has no wall bumps or curvature changes that could cause LCP contact instability.
   The max_d_CL=2.68mm over 40 steps (stability gate) reflects tube smoothness, not
   patient anatomy.
4. **VLM navigation results are internally valid** (VLM sees only fluoroscopy images;
   the anatomical positioning of branches matches the patient). The geometry limitation
   affects physics realism, not image-level validity.

**Recommended methods/limitations text:**
> "ASOCA Normal_5's lumen radius (≤2.75mm) was smaller than the 4mm proximity clip
> threshold, producing a closed surface mesh that caused LCP solver divergence. A
> synthetic tube mesh (radius=2.5mm) aligned to the patient centerlines was substituted.
> Centerline geometry, bifurcation location, and navigation targets are patient-derived;
> the vessel wall surface is not. Findings from Normal_5 should be interpreted with the
> caveat that wire-wall contact physics were evaluated on a smooth synthetic tube, not
> a patient surface reconstruction."

- Stability gate: PASS — 40 steps, max_d_CL=2.68mm, seed=4001.
- Mesh: 632 faces (synthetic), open topology (72 boundary edges).
