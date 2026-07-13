"""How to add a new VLM operator — complete GPT-4o example (~20 lines of real code).

This file shows the minimal implementation needed to benchmark any multimodal
model against CoroNav.  The GPT4oOperator below is fully runnable — set
OPENAI_API_KEY and run:

    python benchmarks/run_benchmark.py \
        --operator examples.add_your_model.GPT4oOperator \
        --anatomy a1
"""
import base64
import json
import os
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from coronav.operator.base import VLMOperator
from coronav.prompts import DEFAULT_SYSTEM_PROMPT


class GPT4oOperator(VLMOperator):
    """Reference implementation for OpenAI GPT-4o.  ~20 lines of operator logic."""

    def __init__(self):
        super().__init__(DEFAULT_SYSTEM_PROMPT)
        import openai
        self.client = openai.OpenAI()  # reads OPENAI_API_KEY from env
        self.model = "gpt-4o"

    def act(self, images: List[np.ndarray], state_text: str) -> Dict[str, Any]:
        b64 = self._encode(images[0])  # monoplane: one image per step

        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": state_text},
                ]},
            ],
        )
        return json.loads(resp.choices[0].message.content)

    @staticmethod
    def _encode(arr: np.ndarray) -> str:
        buf = BytesIO()
        Image.fromarray(arr, mode="L").save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode()


# ──────────────────────────────────────────────────────────────────────────────
# That's it.  The act() method is the entire interface.
#
# The environment calls operator.act(images, state_text) every step and passes
# the result straight to the sim.  No other hooks required.
#
# Need to adapt?
# - Gemini 1.5 Pro:  swap self.client for genai.GenerativeModel(...) and change
#   the API call shape (image goes in as PIL.Image, not base64).
# - Local model (LLaVA, Qwen-VL, …): replace client call with your forward pass.
# - Stateful operator: override reset() to clear per-episode context.
# ──────────────────────────────────────────────────────────────────────────────
