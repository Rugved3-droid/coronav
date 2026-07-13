"""CoronaryBeamAdapter: SofaBeamAdapter tuned for coronary-scale vessels.

Ported from stEVE/coronary_fixture/coronary_sim.py.

Fix A (IncrSAP):
  SOFA 23.06 has no BVHBroadPhase. BruteForceBroadPhase skips computeBoundingTree(),
  causing O(n*m) element enumeration. IncrSAP replaces both phases with sorted AABB
  lists: O(n log n) build, O(k) incremental updates.

Fix B (NaN on first animate):
  bwdInit() leaves DOF[tip] at startingPos (distance 0 from DOF[tip-1]).
  The first env.step() animate normalises (DOF[tip]-DOF[tip-1])/|...| = 0/0 -> NaN.
  Fix: write DOF[tip] to startingPos + xtip*idir before the first animate.
"""
import os
import sys

import numpy as np

# stEVE must be on sys.path (installed via pip or submodule)
from eve.intervention.simulation.sofabeamadapter import SofaBeamAdapter

_INIT_XTIP_MM = 0.1


class CoronaryBeamAdapter(SofaBeamAdapter):
    """SofaBeamAdapter tuned for coronary-scale vessels.

    Parameters
    ----------
    friction : float  — LCP friction coefficient (default 0.001)
    dt_simulation : float  — SOFA timestep in seconds (default 0.006)
    max_it : int  — LCPConstraintSolver maxIt (default 2000)
    """

    def __init__(
        self,
        friction: float = 0.001,
        dt_simulation: float = 0.006,
        max_it: int = 2000,
    ) -> None:
        super().__init__(friction=friction, dt_simulation=dt_simulation)
        self.max_it = max_it

    def _basic_setup(self, friction: float):
        """Fix A: replace BruteForceBroadPhase+BVHNarrowPhase with IncrSAP."""
        self.root.addObject("FreeMotionAnimationLoop")
        self.root.addObject("DefaultPipeline", draw="0", depth="6", verbose="1")
        self.root.addObject("IncrSAP")
        self.root.addObject(
            "LocalMinDistance",
            contactDistance=0.3,
            alarmDistance=0.5,
            angleCone=0.02,
            name="localmindistance",
        )
        self.root.addObject(
            "DefaultContactManager", response="FrictionContactConstraint"
        )
        self.root.addObject(
            "LCPConstraintSolver",
            mu=friction,
            tolerance=1e-4,
            maxIt=self.max_it,
            name="LCP",
            build_lcp=False,
        )

    def reset(self, *args, **kwargs):
        """Fix B: repair bwdInit degenerate DOF state before first animate."""
        super().reset(*args, **kwargs)
        self._fix_tip_dof()

    def _fix_tip_dof(self):
        ic = self._instruments_combined
        xtip = float(ic.m_ircontroller.xtip.value[0])
        if xtip < _INIT_XTIP_MM:
            x = ic.m_ircontroller.xtip.value.copy()
            x[0] = _INIT_XTIP_MM
            ic.m_ircontroller.xtip.value = x
            xtip = _INIT_XTIP_MM

        ip = np.asarray(self._insertion_point, dtype=np.float64)
        idir = np.asarray(self._insertion_direction, dtype=np.float64)
        idir = idir / np.linalg.norm(idir)

        pos = ic.DOFs.position.value.copy()
        pos[-1, 0:3] = ip + xtip * idir
        ic.DOFs.position.value = pos
        self._update_properties()
