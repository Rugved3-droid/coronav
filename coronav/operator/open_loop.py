"""OpenLoopOperator: the image-free control condition (manuscript §2.4).

Advances at a fixed speed every step and never rotates or retracts. It ignores
the image and the state text, so it is not a competing method: it measures what
the configured task requires without visual information. No API calls are made.

This is a re-implementation in this repository's harness of the policy the
manuscript describes, not the original research script. Results produced with
it are new runs, not reproductions of the manuscript's open-loop figures.
"""
from typing import Any, Dict, List

import numpy as np

from .base import VLMOperator

OPEN_LOOP_ADVANCE_MM_S = 35.0


class OpenLoopOperator(VLMOperator):
    """Always advance at ``advance_mm_s``; never rotate, never retract."""

    def __init__(self, advance_mm_s: float = OPEN_LOOP_ADVANCE_MM_S):
        super().__init__(system_prompt=None)
        self.advance_mm_s = float(advance_mm_s)

    def act(self, images: List[np.ndarray], state_text: str) -> Dict[str, Any]:
        return {
            "intended_direction": "advance",
            "action": {"translation": self.advance_mm_s, "rotation": 0.0},
        }
