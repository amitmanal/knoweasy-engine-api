"""
providers/manager.py

Central provider selection logic. Keeps behavior backward-compatible:
- Respects AI_PROVIDER and AI_PROVIDER_FALLBACKS if present
- Defaults to Gemini
- Never imports heavy SDKs; uses existing ai_router request helpers for now
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import AI_PROVIDER, AI_TIMEOUT_SECONDS

from .base import Provider, ProviderError
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider


def _provider_order() -> List[str]:
    # Backward-compatible: AI_PROVIDER can be "auto" or comma-separated.
    raw = (AI_PROVIDER or "gemini").strip().lower()
    if raw in {"auto", "fallback"}:
        return ["gemini", "openai", "claude"]
    if "," in raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [raw]


def get_provider(name: str) -> Provider:
    name = (name or "").strip().lower()
    if name in {"gemini", "google"}:
        return GeminiProvider()
    if name in {"openai", "chatgpt"}:
        return OpenAIProvider()
    if name in {"claude", "anthropic"}:
        return ClaudeProvider()
    raise ProviderError(f"Unknown provider: {name}")


def generate_json(prompt: str) -> Dict[str, Any]:
    timeout_s = int(AI_TIMEOUT_SECONDS or 30)

    last_err: Optional[Exception] = None
    for name in _provider_order():
        try:
            prov = get_provider(name)
            return prov.generate_json(prompt=prompt, timeout_s=timeout_s)
        except ProviderError as e:
            last_err = e
        except Exception as e:
            last_err = e

    if last_err:
        raise ProviderError(f"All providers failed. Last error: {last_err}")
    raise ProviderError("All providers failed.")
