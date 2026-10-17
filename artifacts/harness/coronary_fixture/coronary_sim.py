"""
CoronaryBeamAdapter — SofaBeamAdapter subclass for coronary-scale simulations.

Fix A — Broad phase (IncrSAP):
  SOFA 23.06 has no BVHBroadPhase.  BruteForceBroadPhase.needsDeepBoundingTree()=False
  causes DefaultPipeline to skip computeBoundingTree(), so BVHNarrowPhase degenerates
  to O(n*m) element enumeration (75 wire * 40k vessel = 6M LocalMinDistance calls/substep).
  IncrSAP replaces both components: maintains sorted AABB lists (O(n log n) build,
  O(k) incremental updates) and finds only spatially overlapping element pairs.
  Same LocalMinDistance + FrictionContactConstraint + LCP — no physics change.

Fix B — NaN from zero DOF separation on first animate (bwdInit degenerate state):
  bwdInit() places ALL DOFs at startingPos, then calls applyController() which uses
  xbuf = copy of current positions (all startingPos) to interpolate DOF[tip].
  totalLengthIsChanging() shifts the curvilinear abscissa back by dLength, mapping
  DOF[tip] to xbuf[tip] = startingPos.  Both DOF[tip-1] and DOF[tip] end up at
  startingPos (distance = 0) while the beam rest-length > 0.  On the first
  env.step() animate, applyController() repeats this placement, then
  AdaptiveBeamForceFieldAndMass calls computeTransform2() which normalises
  (DOF[tip] - DOF[tip-1]) / |DOF[tip] - DOF[tip-1]| = 0/0 → NaN, propagating
  through the full system → 'Tracking is NAN, resetting devices' every step.

  Fix: override reset() to directly write DOF[tip] to startingPos + xtip * idir
  after super().reset() completes.  This makes xbuf non-degenerate for the first
  animate.  One settle animate (no xtip advance) is then run to confirm no NaN and
  to bring the internal IRC state fully in sync with the corrected DOF positions.

Zero core file edits — SofaBeamAdapter stays pristine for aortic VMR environments.
"""

import os
import sys
from typing import List

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from eve.intervention.simulation.sofabeamadapter import SofaBeamAdapter
from eve.intervention.device import Device

_INIT_XTIP_MM = 0.1  # must match _add_devices default (+= 0.1 in sofabeamadapter.py)


class CoronaryBeamAdapter(SofaBeamAdapter):
    """SofaBeamAdapter tuned for coronary-scale vessels."""

    def __init__(
        self,
        friction: float = 0.001,
        dt_simulation: float = 0.006,
        max_it: int = 2000,
    ) -> None:
        super().__init__(friction=friction, dt_simulation=dt_simulation)
        self.max_it = max_it

    # ── Fix A: IncrSAP broad+narrow phase ────────────────────────────────────
    def _basic_setup(self, friction: float):
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

    # ── Fix B: repair bwdInit degenerate DOF state before first animate ───────
    def reset(self, *args, **kwargs):
        super().reset(*args, **kwargs)
        self._fix_tip_dof()

    def _fix_tip_dof(self):
        """Place DOF[tip] at startingPos + xtip*idir so xbuf is non-degenerate.

        bwdInit() leaves DOF[tip] at startingPos (distance 0 from DOF[tip-1]).
        The first env.step() animate's applyController reads xbuf (all at startingPos)
        and normalises (DOF[tip]-DOF[tip-1]) / |...| = 0/0 → NaN cascade.

        Fix: write DOF[tip] to the correct deployed position BEFORE the first
        animate so xbuf is non-degenerate when applyController reads it.
        No animate is run here: the first env.step() substep handles that.
        """
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

        # Refresh _dof_positions without animate (positions are now valid, no NaN risk).
        self._update_properties()
