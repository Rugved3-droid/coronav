# Step 1 Findings — Coronary VesselTree

Base commit: `f909e7122d846a3c2fec91eedddaa0ba88b6391d`

---

## 1. VesselTree Base Class — Required Attributes

**File:** `eve/intervention/vesseltree/vesseltree.py`, lines 20–29

A custom subclass must set all of the following in `__init__()` or `reset()`:

| Attribute | Type | Notes |
|---|---|---|
| `branches` | `Tuple[Branch]` | One `Branch` per vessel segment; each Branch has `.coordinates` (N×3 float32 array, mm) and `.name` (str) |
| `branching_points` | `List[BranchingPoint]` | Junction spheres; computed by `calc_branching()` or `calc_branching_with_radii()` |
| `centerline_coordinates` | `np.ndarray` | Concatenated coordinates from all branches (N×3) |
| `insertion` | `Insertion` | `Insertion(position: np.ndarray, direction: np.ndarray)` — the catheter entry point and approach direction |
| `coordinate_space` | `gym.spaces.Box` | Bounding box across all branches (low/high in mm) |
| `coordinate_space_episode` | `gym.spaces.Box` | Usually same as `coordinate_space` for static trees |
| `mesh_path` | `str` | Path to the **collision** mesh (`.obj`) |
| `visu_mesh_path` | `Optional[str]` | Path to the **visual** mesh; can equal `mesh_path` |

The `Insertion` dataclass is defined at `vesseltree.py:14–17`.

---

## 2. SOFA Mesh Loader — Required File Extension

**File:** `eve/intervention/simulation/sofabeamadapter.py`, line 231

```python
vessel_object.addObject(
    "MeshObjLoader",
    filename=mesh_path,
    ...
)
```

**→ Must supply `.obj` format.**

The temp-mesh path generator (`meshing.py:73`) also hard-codes `.obj`:
```python
mesh_path = os.path.join(gettempdir(), f"Test_{pid}-{nr}.obj")
```

`FromMesh.__init__` calls `load_mesh()` → `pv.read()` (any format pyvista supports) then `save_mesh()` → `pv.save_meshio(path, mesh)` which writes `.obj` to the temp path. So you can supply any mesh format pyvista reads; it will be converted to `.obj` automatically.

---

## 3. Unit / Scale Factor in sofabeamadapter.py

**File:** `eve/intervention/simulation/sofabeamadapter.py` — **no explicit mm↔m transform present**.

The file receives `mesh_path` and `insertion_point` already in mm and passes them straight to SOFA. Collision distances are set in mm:
```python
# sofabeamadapter.py lines 213–214
contactDistance=0.3,   # mm
alarmDistance=0.5,     # mm
```

The scaling lives upstream in **vmr.py** (not sofabeamadapter):
```python
# vmr.py line 14
SCALING_FACTOR = 10
# applied at vmr.py lines 149, 167: mesh.scale([10, 10, 10])
# applied at vmr.py / _load_points_from_pth lines 64–66: x *= 10
```
VMR files are stored in **cm**; the ×10 converts them to **mm** before SOFA sees them. If supplying a custom mesh, it must already be in **mm** — no automatic rescaling happens in sofabeamadapter.

---

## 4. Default VMR IDs

**File:** `vmrfiledownload.py`, lines 8–21

| VMR ID | Anatomy |
|---|---|
| `0078_0001` | Aorta / aortic arch |
| `0079_0001` | Aorta / aortic arch |
| `0094_0001` | Aorta / aortic arch |
| `0095_0001` | Aorta / aortic arch |
| `0105_0001` | Aorta / aortic arch |
| `0111_0001` | Aorta / aortic arch |
| `0131_0000` | Aorta / aortic arch |
| `0154_0001` | Aorta / aortic arch |
| `0166_0001` | Aorta / aortic arch |
| `0167_0001` | Aorta / aortic arch |
| `0175_0000` | Aorta / aortic arch |
| `0176_0000` | Aorta / aortic arch |

**None are coronary.** All 12 are aortic arch models (consistent with stEVE's published use case). To get a coronary fixture, a separate VMR coronary case ID is needed — see Step 2.

---

## 5. Cleanest Template for Custom User Mesh

**File:** `eve/intervention/vesseltree/frommesh.py` — the `FromMesh` class.

Constructor signature:
```python
FromMesh(
    mesh: str,                                          # path to your surface mesh (any pyvista format → auto-converted to .obj)
    insertion_position: Tuple[float, float, float],     # ostium point in mm
    insertion_direction: Tuple[float, float, float],    # catheter approach direction (unit vector)
    branch_list: Optional[List[Union[Branch, BranchWithRadii]]] = None,  # centerline branches
    approx_branch_radii: Optional[Union[List[float], float]] = None,
    visu_mesh: Optional[str] = None,
    scaling_xyz: Optional[Tuple[float, float, float]] = None,
    rotation_yzx_deg: Optional[Tuple[float, float, float]] = None,
    rotate_branches: bool = True,
    rotate_ip: bool = True,
)
```

If `branch_list` is omitted, branching points and centerline are set to empty/zeros — pathfinder and target will not work. For a navigation fixture, `branch_list` must be provided.
