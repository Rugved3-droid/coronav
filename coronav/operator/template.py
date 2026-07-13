"""TemplateOperator: copy this file and fill in act() to add your model.

You only need to implement ONE method.  Everything else — the environment,
metrics, seeds, step budget, logging — is handled automatically.

Quick-start
-----------
1. Copy this file:  cp coronav/operator/template.py coronav/operator/my_model.py
2. Rename the class: MyModelOperator
3. Fill in __init__: load your client / model weights
4. Fill in act():    encode images, call your API, return the dict

Then run the benchmark with your operator:
    python benchmarks/run_benchmark.py --operator coronav.operator.my_model.MyModelOperator

See examples/add_your_model.py for a complete GPT-4o example (~20 lines).
"""
from typing import Any, Dict, List

import numpy as np

from .base import VLMOperator
from ..prompts import DEFAULT_SYSTEM_PROMPT


class TemplateOperator(VLMOperator):
    """Heavily-commented stub.  Replace every ``# TODO`` block with your code."""

    def __init__(self, system_prompt: str = None):
        super().__init__(system_prompt or DEFAULT_SYSTEM_PROMPT)

        # ── TODO: initialise your model / client here ─────────────────────────
        #
        # OpenAI example:
        #   import openai, os
        #   self.client = openai.OpenAI()          # reads OPENAI_API_KEY from env
        #   self.model  = "gpt-4o"
        #
        # Google Gemini example:
        #   import google.generativeai as genai, os
        #   genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        #   self.model = genai.GenerativeModel("gemini-1.5-pro-vision")
        #
        # Local model example:
        #   self.model = AutoModelForVision2Seq.from_pretrained("path/to/weights")
        #   self.processor = AutoProcessor.from_pretrained("path/to/weights")
        # ──────────────────────────────────────────────────────────────────────
        pass

    def act(self, images: List[np.ndarray], state_text: str) -> Dict[str, Any]:
        """Return a guidewire action for the current step.

        Parameters
        ----------
        images : list of (H, W) uint8 arrays
            Fluoroscopy frame(s).  Standard benchmark = one image (monoplane
            AP Cranial 40 deg view, 512x512 px grayscale).
        state_text : str
            Step context, e.g.:
                "Distance to mid-LAD target: 42.3 mm. Trend: decreasing.
                 Retractions remaining: 2 of 2. Navigate the wire to the target."

        Returns
        -------
        dict — must contain these keys:

            "intended_direction" : str
                One of: "advance" | "retract" | "rotate_cw" | "rotate_ccw" | "hold"

            "action" : dict
                "translation" : float  # mm/s, range [-50, 50], positive = advance
                "rotation"    : float  # rad/s, range [-3.14, 3.14], positive = CW

        Optional keys (logged but not required):
            "tip_location_statement"    : str  — where the wire tip is
            "target_location_statement" : str  — where the target appears to be
            "reasoning"                 : str  — chain-of-thought for analysis
        """
        # ── TODO: encode images for your API ─────────────────────────────────
        #
        # PNG-base64 helper (works for most APIs):
        #
        #   import base64
        #   from io import BytesIO
        #   from PIL import Image
        #
        #   def to_b64(arr):
        #       buf = BytesIO()
        #       Image.fromarray(arr, mode="L").save(buf, format="PNG")
        #       return base64.standard_b64encode(buf.getvalue()).decode()
        #
        #   b64_frames = [to_b64(img) for img in images]
        # ──────────────────────────────────────────────────────────────────────

        # ── TODO: call your model ─────────────────────────────────────────────
        #
        # OpenAI example:
        #   resp = self.client.chat.completions.create(
        #       model=self.model,
        #       max_tokens=512,
        #       messages=[
        #           {"role": "system", "content": self.system_prompt},
        #           {"role": "user", "content": [
        #               {"type": "image_url",
        #                "image_url": {"url": f"data:image/png;base64,{b64_frames[0]}"}},
        #               {"type": "text", "text": state_text},
        #           ]},
        #       ],
        #   )
        #   raw_text = resp.choices[0].message.content
        #
        # The model should return a JSON object with "intended_direction" and "action".
        # Use the DEFAULT_SYSTEM_PROMPT (imported above) as your system message so
        # the model knows the task, the anatomy, and the action schema.
        # ──────────────────────────────────────────────────────────────────────

        # ── TODO: parse the JSON response ────────────────────────────────────
        #
        #   import json
        #   data = json.loads(raw_text)   # or use ClaudeOperator._parse_json for robustness
        #   return data
        # ──────────────────────────────────────────────────────────────────────

        raise NotImplementedError(
            "Fill in act() with your model call.  "
            "See the TODO comments above and examples/add_your_model.py."
        )

    def reset(self) -> None:
        """Called at the start of each episode.

        Override this if your operator is stateful — e.g. you maintain a
        per-episode conversation history or store context across steps.
        """
        # ── TODO: clear per-episode state if needed ───────────────────────────
        pass
