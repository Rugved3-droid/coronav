# Coronary Navigation — Working Environment

Milestone locked 2026-06-28. Wire navigates ostium → mid-LAD in 26 steps, 0 NaN,
0 tunneling, collision live throughout.

## Reproduce the traverse

```
cd D:\steve\stEVE
D:\conda\envs\steve\python.exe coronary_fixture/step5_traverse.py --dt 0.001
```

Set SOFA env vars first (or source the activation script):

```powershell
$env:SOFA_ROOT = "D:\steve\deps\SOFA_v23.06.00_Win64"
$env:PYTHONPATH = "D:\steve\deps\SOFA_v23.06.00_Win64\plugins\SofaPython3\lib\python3\site-packages"
$env:PATH = "D:\steve\deps\SOFA_v23.06.00_Win64\bin;" + $env:PATH
```

Or from bash:
```bash
cd /d/steve/stEVE
SOFA_ROOT="D:/steve/deps/SOFA_v23.06.00_Win64" \
PYTHONPATH="D:/steve/deps/SOFA_v23.06.00_Win64/plugins/SofaPython3/lib/python3/site-packages" \
PATH="D:/steve/deps/SOFA_v23.06.00_Win64/bin:$PATH" \
/d/conda/envs/steve/python.exe -u coronary_fixture/step5_traverse.py --dt 0.001
```

## Run the regression check

```bash
/d/conda/envs/steve/python.exe coronary_fixture/regression_check.py
```

Exit 0 = PASS. Exit 1 = FAIL (prints failing criteria).

## Working configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Device | `JShaped(tip_radius=1.5, tip_angle=0.2*pi)` | 0.94mm arc; gives non-zero tangent at DOF[-1] |
| `dt_simulation` | 0.001 s | 133 substeps/env.step; 0.035mm/substep = 7% of 0.5mm wall |
| `contactDistance` | 0.3 mm | Unchanged from stEVE default |
| `alarmDistance` | 0.5 mm | Unchanged from stEVE default |
| Broad phase | `IncrSAP` | Replaces BruteForce+BVH (O(n²) on 40k-face coronary mesh) |
| LCP maxIt | 2000 | Unchanged |
| Mesh | `clipped_left.obj` | World coordinates, no recenter applied |
| Action | (35.0 mm/s, 1.0 rad/s) | Pure push, scripted |
| Image frequency | 7.5 Hz | step duration = 0.1333 s |

## Key results (baseline run)

| Metric | Value |
|--------|-------|
| Target reached | Yes (step 26 / 60 max) |
| NaN positions | 0 |
| Tunnel steps (d_CL > 3.5mm) | 0 |
| Mean d_CL | 1.29 mm |
| Max d_CL | 3.44 mm (step 5, left main) |
| Path consumed | 115.4 mm / 120.1 mm optimal |
| Wall-time | 16.9 s total / 0.65 s per env.step |

Full per-step trace saved in `baseline_trace.json`.

## Known acceptable quirks

**8 corner-rounding JUMP > 5mm events** (steps 6, 7, 8, 9, 11, 16, 18, 20):
Wire tip snaps forward as it rounds the LM→LAD bend and LAD curves.
Max jump 7.72mm (step 11). All within the lumen (d_CL ≤ 3.5mm). Not solver
instability — d_surf stays positive, no NaN follows. Acceptable for scripted
and VLM runs.

**0.65 s/env.step wall-time** from dt=0.001 (133 substeps vs 22 at default
dt=0.006). Adequate for scripted traversal and VLM inference loops. If RL
training needs millions of steps, investigate: (a) adaptive substep count near
junctions only, or (b) parallelising env instances. Do not increase dt back
without re-verifying containment at the LM→LAD bifurcation.

**`Straight` device NaNs immediately** (confirmed by RUN 6 in diag_three_runs.py):
zero initial curvature → 0/0 in direction normalization at DOF[-1]. Use JShaped
for coronary. The Straight device works fine in the aortic scene (which uses
JShaped in stEVE's shipped examples).

## Diagnosis trail

See `diag_three_runs.py` (6 runs) and `inspect_bifurcation.py` for the empirical
ruling-out of: core SOFA bug, IncrSAP, coordinate magnitude, mesh defect.
Cause was Straight device (RUN 6) + step-over at bifurcation (dt fix).
