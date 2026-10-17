"""
Minimal probe to isolate the Simulation.init() hang seen with Straight device.

Tests two scenarios in order:
  A) JShaped(tip_radius=1.5)  -- known working geometry, tests mesh normals
  B) Straight()                -- tests spireDiameter=0 in WireRestShape

Prints a timestamp before and after each Simulation.init() call so we can
see which device hangs and how long init takes.

Run:
    python coronary_fixture/step4_device_probe.py
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

MESH_PATH = os.path.join(HERE, "clipped_left.obj")
PATH_DIR  = os.path.join(REPO, ".data", "vmr", "0066_H_CORO_H", "Paths")

from coronary_fixture.pth_centerlines import left_coronary_branches
from eve.intervention.device.jshaped import JShaped
from eve.intervention.device.straight import Straight

import importlib
import math
import numpy as np


def _calculate_insertion_pose(insertion_point, insertion_direction):
    insertion_direction = insertion_direction / np.linalg.norm(insertion_direction)
    original_direction = np.array([1.0, 0.0, 0.0])
    if np.all(np.cross(insertion_direction, original_direction) == 0):
        w0 = 0.0
        xyz0 = [0.0, 1.0, 0.0]
    else:
        half = (original_direction + insertion_direction) / np.linalg.norm(
            original_direction + insertion_direction
        )
        w0 = np.dot(original_direction, half)
        xyz0 = np.cross(original_direction, half)
    pose = list(insertion_point) + list(xyz0) + [w0]
    return pose


def run_probe(device_label, device):
    print(f"\n{'='*60}")
    print(f"PROBE: {device_label}")
    print(f"  spireDiameter = {device.sofa_device.spire_diameter}")
    print(f"  density_of_beams = {device.sofa_device.density_of_beams}")
    print(f"{'='*60}")

    sofa = importlib.import_module("Sofa")
    sofa_runtime = importlib.import_module("SofaRuntime")

    branches, insertion_pt, insertion_dir = left_coronary_branches(PATH_DIR)
    insertion_pose = _calculate_insertion_pose(insertion_pt, insertion_dir)

    root = sofa.Core.Node()
    root.gravity = [0.0, 0.0, 0.0]
    root.dt = 0.006

    # --- Plugins ---
    root.addObject(
        "RequiredPlugin",
        pluginName=(
            "BeamAdapter "
            "Sofa.Component.AnimationLoop "
            "Sofa.Component.Collision.Detection.Algorithm "
            "Sofa.Component.Collision.Detection.Intersection "
            "Sofa.Component.LinearSolver.Direct "
            "Sofa.Component.IO.Mesh "
            "Sofa.Component.ODESolver.Backward "
            "Sofa.Component.Constraint.Lagrangian.Correction "
            "Sofa.Component.Topology.Mapping"
        ),
    )

    # --- Basic setup ---
    root.addObject("FreeMotionAnimationLoop")
    root.addObject("DefaultPipeline", draw="0", depth="6", verbose="1")
    root.addObject("BruteForceBroadPhase")
    root.addObject("BVHNarrowPhase")
    root.addObject("LocalMinDistance", contactDistance=0.3, alarmDistance=0.5, angleCone=0.02)
    root.addObject("DefaultContactManager", response="FrictionContactConstraint")
    root.addObject("LCPConstraintSolver", mu=0.001, tolerance=1e-4, maxIt=2000, build_lcp=False)

    # --- Vessel tree ---
    vessel = root.addChild("vesselTree")
    vessel.addObject("MeshObjLoader", filename=MESH_PATH, flipNormals=False, name="meshLoader")
    vessel.addObject("MeshTopology", position="@meshLoader.position", triangles="@meshLoader.triangles")
    vessel.addObject("MechanicalObject", name="dofs", src="@meshLoader")
    vessel.addObject("TriangleCollisionModel", moving=False, simulated=False)
    vessel.addObject("LineCollisionModel", moving=False, simulated=False)

    # --- Wire device ---
    sofa_dev = device.sofa_device
    topo = root.addChild("topolines_" + device.name)
    topo.addObject(
        "WireRestShape",
        name="rest_shape_" + device.name,
        isAProceduralShape=sofa_dev.is_a_procedural_shape,
        straightLength=sofa_dev.straight_length,
        length=sofa_dev.length,
        spireDiameter=sofa_dev.spire_diameter,
        radiusExtremity=sofa_dev.radius_extremity,
        youngModulusExtremity=sofa_dev.young_modulus_extremity,
        massDensityExtremity=sofa_dev.mass_density_extremity,
        radius=sofa_dev.radius,
        youngModulus=sofa_dev.young_modulus,
        massDensity=sofa_dev.mass_density,
        poissonRatio=sofa_dev.poisson_ratio,
        keyPoints=sofa_dev.key_points,
        densityOfBeams=sofa_dev.density_of_beams,
        numEdgesCollis=sofa_dev.num_edges_collis,
        numEdges=sofa_dev.num_edges,
        spireHeight=sofa_dev.spire_height,
        printLog=True,
        template="Rigid3d",
    )
    topo.addObject("EdgeSetTopologyContainer", name="meshLines_" + device.name)
    topo.addObject("EdgeSetTopologyModifier", name="Modifier")
    topo.addObject("EdgeSetGeometryAlgorithms", name="GeomAlgo", template="Rigid3d")
    topo.addObject("MechanicalObject", name="dofTopo_" + device.name, template="Rigid3d")

    # --- InstrumentCombined ---
    ic = root.addChild("InstrumentCombined")
    ic.addObject("EulerImplicitSolver", rayleighStiffness=0.2, rayleighMass=0.1)
    ic.addObject("BTDLinearSolver", verification=False, subpartSolve=False, verbose=False)
    nx = sum(sofa_dev.density_of_beams)
    ic.addObject("RegularGridTopology", name="MeshLines", nx=nx+1, ny=1, nz=1,
                 xmax=1.0, xmin=0.0, ymin=0, ymax=0, zmax=1, zmin=1, p0=[0,0,0])
    ic.addObject("MechanicalObject", showIndices=False, name="DOFs", template="Rigid3d")

    wire_ref = "@../topolines_" + device.name + "/rest_shape_" + device.name
    ic.addObject("WireBeamInterpolation", name="Interpol_" + device.name,
                 WireRestShape=wire_ref, radius=sofa_dev.radius, printLog=False)
    ic.addObject("AdaptiveBeamForceFieldAndMass", name="ForceField_" + device.name,
                 massDensity=sofa_dev.mass_density, interpolation="@Interpol_" + device.name)

    ic.addObject("InterventionalRadiologyController", name="m_ircontroller",
                 template="Rigid3d",
                 instruments="Interpol_" + device.name,
                 startingPos=insertion_pose,
                 xtip=[0.1],
                 printLog=True,
                 rotationInstrument=[0.0],
                 speed=0.0, listening=True, controlledInstrument=0)
    ic.addObject("LinearSolverConstraintCorrection", wire_optimization="true", printLog=False)
    ic.addObject("FixedConstraint", indices=0, name="FixedConstraint")
    ic.addObject("RestShapeSpringsForceField",
                 points="@m_ircontroller.indexFirstNode",
                 angularStiffness=1e8, stiffness=1e8,
                 external_points=0, external_rest_shape="@DOFs")

    beam_collis = ic.addChild("CollisionModel")
    beam_collis.activated = True
    beam_collis.addObject("EdgeSetTopologyContainer", name="collisEdgeSet")
    beam_collis.addObject("EdgeSetTopologyModifier", name="colliseEdgeModifier")
    beam_collis.addObject("MechanicalObject", name="CollisionDOFs")
    beam_collis.addObject("MultiAdaptiveBeamMapping", controller="../m_ircontroller",
                          useCurvAbs=True, printLog=False, name="collisMap")
    beam_collis.addObject("LineCollisionModel", proximity=0.0)
    beam_collis.addObject("PointCollisionModel", proximity=0.0)

    print(f"Scene built — calling Simulation.init() at {time.strftime('%H:%M:%S')} ...")
    sys.stdout.flush()
    t0 = time.time()
    sofa.Simulation.init(root)
    dt = time.time() - t0
    print(f"Simulation.init() COMPLETED in {dt:.1f}s at {time.strftime('%H:%M:%S')}")
    sys.stdout.flush()

    print("Running 1 animate step ...")
    sys.stdout.flush()
    t1 = time.time()
    sofa.Simulation.animate(root, root.dt.value)
    dt2 = time.time() - t1
    print(f"animate() done in {dt2:.3f}s")
    sys.stdout.flush()

    sofa.Simulation.unload(root)
    print(f"PROBE {device_label}: PASSED")


if __name__ == "__main__":
    print("Loading SOFA plugins (first import is slow) ...")
    sys.stdout.flush()

    # Probe A: JShaped with small tip -- known working geometry
    run_probe("JShaped(tip_radius=1.5)", JShaped(tip_radius=1.5))

    # Probe B: Straight -- tests spireDiameter=0
    run_probe("Straight()", Straight())
