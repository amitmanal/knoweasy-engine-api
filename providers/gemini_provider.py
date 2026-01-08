"""
providers/gemini_provider.py
Thin wrapper around existing ai_router Gemini request implementation.
"""

from __future__ import annotations
from typing import Any, Dict

from .base import ProviderError


class GeminiProvider:
    name = "gemini"

    def generate_json(self, prompt: str, timeout_s: int) -> Dict[str, Any]:
        try:
            # Import inside to keep module import light and avoid cycles at startup.
            from ai_router import _gemini_request  # type: ignore
            return _gemini_request(prompt, timeout_s)
        except Exception as e:
            raise ProviderError(f"Gemini failed: {e}") from e
