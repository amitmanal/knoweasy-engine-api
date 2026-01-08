"""
providers/openai_provider.py
Placeholder-ready. Safe if OPENAI_API_KEY missing: returns ProviderError.
"""

from __future__ import annotations
from typing import Any, Dict

from config import OPENAI_API_KEY
from .base import ProviderError


class OpenAIProvider:
    name = "openai"

    def generate_json(self, prompt: str, timeout_s: int) -> Dict[str, Any]:
        if not (OPENAI_API_KEY or "").strip():
            raise ProviderError("OpenAI API key not set")
        try:
            from ai_router import _openai_request  # type: ignore
            return _openai_request(prompt, timeout_s)
        except Exception as e:
            raise ProviderError(f"OpenAI failed: {e}") from e
