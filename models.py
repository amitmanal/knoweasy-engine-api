from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from google import genai

from config import settings


def _require(name: str, value: Optional[str]) -> str:
    if value and str(value).strip():
        return str(value).strip()
    raise RuntimeError(f"Missing required environment variable: {name}")


@dataclass
class GeminiClient:
    """
    Thin wrapper around Google's Gen AI SDK (Gemini API).

    Notes:
    - We force api_version='v1' to avoid v1beta model/method mismatches.
    - Model name is configurable via GEMINI_MODEL; defaults to settings.GEMINI_MODEL.
    """
    api_key: str
    model: str = settings.GEMINI_MODEL

    def __post_init__(self) -> None:
        self.api_key = _require("GEMINI_API_KEY", self.api_key)
        # api_version can be overridden via env, but default to stable v1.
        api_version = os.getenv("GEMINI_API_VERSION", "v1")
        self._client = genai.Client(
            api_key=self.api_key,
            http_options={"api_version": api_version},
        )

    def generate_json(self, prompt: str) -> str:
        """
        Returns raw text from the model. Caller is responsible for JSON parsing.
        """
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        # The SDK exposes .text for convenience. Keep a robust fallback.
        text = getattr(resp, "text", None)
        if text and str(text).strip():
            return str(text).strip()

        # Fallback: try to read first candidate parts
        try:
            cand0 = resp.candidates[0]
            parts = getattr(cand0.content, "parts", []) or []
            joined = "".join(getattr(p, "text", "") for p in parts)
            if joined.strip():
                return joined.strip()
        except Exception:
            pass

        raise RuntimeError("Model returned empty response")
