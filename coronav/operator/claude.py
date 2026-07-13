"""ClaudeOperator: reference implementation using claude-sonnet-4-6."""
import base64
import json
import os
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
from PIL import Image

from .base import VLMOperator
from ..prompts import DEFAULT_SYSTEM_PROMPT


class ClaudeOperator(VLMOperator):
    """VLM operator backed by Anthropic Claude.

    Reads ``ANTHROPIC_API_KEY`` from the environment (never hardcode keys).

    Parameters
    ----------
    model : str
        Anthropic model ID. Default: claude-sonnet-4-6 (paper's baseline).
    system_prompt : str or None
        Override the default CoroNav prompt (e.g. to test prompt robustness).
    """

    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, model: str = None, system_prompt: str = None):
        super().__init__(system_prompt or DEFAULT_SYSTEM_PROMPT)
        self.model = model or self.DEFAULT_MODEL

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it in your shell or add it to a .env file."
            )
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def act(self, images: List[np.ndarray], state_text: str) -> Dict[str, Any]:
        content = [self._encode(img) for img in images]
        content.append({"type": "text", "text": state_text})

        resp = self._client.messages.create(
            model=self.model,
            max_tokens=600,
            system=self.system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        raw = resp.content[0].text.strip()
        return self._parse_json(raw)

    @staticmethod
    def _encode(arr: np.ndarray) -> dict:
        buf = BytesIO()
        Image.fromarray(arr, mode="L").save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        }

    @staticmethod
    def _parse_json(raw: str) -> dict:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        last = raw.rfind("}")
        if last == -1:
            raise ValueError(f"No JSON object in model response: {raw!r}")
        depth = 0
        first = -1
        for i in range(last, -1, -1):
            if raw[i] == "}":
                depth += 1
            elif raw[i] == "{":
                depth -= 1
                if depth == 0:
                    first = i
                    break
        if first == -1:
            raise ValueError(f"Unbalanced JSON in model response: {raw!r}")
        return json.loads(raw[first : last + 1])
