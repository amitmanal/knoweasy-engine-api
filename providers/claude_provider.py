"""
providers/claude_provider.py
Placeholder-ready. Safe if CLAUDE_API_KEY missing: returns ProviderError.
"""

from __future__ import annotations
from typing import Any, Dict

from config import CLAUDE_API_KEY
from .base import ProviderError


class ClaudeProvider:
    name = "claude"

    def generate_json(self, prompt: str, timeout_s: int) -> Dict[str, Any]:
        if not (CLAUDE_API_KEY or "").strip():
            raise ProviderError("Claude API key not set")
        try:
            from ai_router import _claude_request  # type: ignore
            return _claude_request(prompt, timeout_s)
        except Exception as e:
            raise ProviderError(f"Claude failed: {e}") from e
