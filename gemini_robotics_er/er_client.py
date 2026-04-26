"""Wrapper around the Gemini Robotics-ER 1.6 API.

Mirrors the helpers in google-gemini/robotics-samples Getting Started notebook
(parse_json + the three core prompt patterns: detection, pointing, trajectory).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image

DEFAULT_MODEL_ID = "gemini-robotics-er-1.6-preview"


def parse_json(json_output: str) -> str:
    """Strip ```json fencing the model sometimes wraps responses in."""
    lines = json_output.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "```json":
            json_output = "\n".join(lines[i + 1:])
            json_output = json_output.split("```")[0]
            break
    return json_output


@dataclass
class ERResult:
    raw_text: str
    parsed: list = field(default_factory=list)


class GeminiERClient:
    def __init__(self, api_key: Optional[str] = None,
                 model_id: str = DEFAULT_MODEL_ID):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to .env in the package root "
                "or export it before launching."
            )
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id

    def _call(self, image: Image.Image, prompt: str,
              thinking_budget: int = 0) -> ERResult:
        config = types.GenerateContentConfig(
            temperature=1.0,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        )
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[image, prompt],
            config=config,
        )
        text = response.text or ""
        cleaned = parse_json(text)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = []
        if not isinstance(parsed, list):
            parsed = []
        return ERResult(raw_text=text, parsed=parsed)

    def detect_objects(self, image: Image.Image,
                       query: str = "all visible objects") -> ERResult:
        prompt = (
            f"Detect {query}. Return bounding boxes as JSON: "
            "[{\"box_2d\": [ymin, xmin, ymax, xmax], \"label\": <label>}]. "
            "Coordinates are normalized to 0-1000 (integers)."
        )
        return self._call(image, prompt)

    def point_at(self, image: Image.Image, query: str) -> ERResult:
        prompt = (
            f"Point to {query}. Return JSON: "
            "[{\"point\": [y, x], \"label\": <label>}]. "
            "Coordinates normalized to 0-1000."
        )
        return self._call(image, prompt)

    def plan_trajectory(self, image: Image.Image, source: str,
                        dest: str, n_steps: int = 15) -> ERResult:
        prompt = (
            f"Place a point on {source}, then {n_steps} additional points "
            f"forming a smooth trajectory that moves {source} to {dest}. "
            f"Label points '0' through '{n_steps}' in order. "
            "Return JSON: [{\"point\": [y, x], \"label\": <label>}]. "
            "Coordinates normalized to 0-1000."
        )
        return self._call(image, prompt, thinking_budget=1024)
