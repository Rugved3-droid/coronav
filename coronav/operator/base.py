"""VLMOperator: the single interface every model must implement."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import numpy as np


class VLMOperator(ABC):
    """Abstract base class for VLM-based coronary guidewire operators.

    To add a new model, subclass this and implement ``act()``.
    See ``template.py`` for a heavily commented stub.
    """

    def __init__(self, system_prompt: str = None):
        """
        Parameters
        ----------
        system_prompt : str or None
            Override the default CoroNav system prompt.
            If None, each concrete operator uses its own default.
        """
        self.system_prompt = system_prompt

    @abstractmethod
    def act(self, images: List[np.ndarray], state_text: str) -> Dict[str, Any]:
        """Choose the next guidewire action given the current observation.

        Parameters
        ----------
        images : list of numpy arrays, shape (H, W), dtype uint8
            Fluoroscopy frame(s). One image for monoplane (standard), two for
            biplane. The first image is always the AP Cranial 40 deg view.
        state_text : str
            Textual step summary delivered alongside the image, e.g.:
            "Distance to mid-LAD target: 42.3 mm. Trend: decreasing.
             Retractions remaining: 2 of 2."

        Returns
        -------
        dict with at minimum:
            "intended_direction" : one of "advance" | "retract" |
                                   "rotate_cw" | "rotate_ccw" | "hold"
            "action" : {"translation": float, "rotation": float}
                translation : mm/s  range [-50, 50]  (positive = advance)
                rotation    : rad/s range [-pi, pi]  (positive = clockwise)

        Optional keys (logged to trace but not required):
            "tip_location_statement"    : str
            "target_location_statement" : str
            "reasoning"                 : str
            "safety_rationale"          : str
        """
        ...

    def reset(self) -> None:
        """Called at the start of each new episode.

        Override this if your operator is stateful (e.g. maintains a
        conversation history or stores episode context).
        """
