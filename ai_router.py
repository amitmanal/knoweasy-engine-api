# DEPRECATED: This file is no longer used. Main flow uses orchestrator.py via router.py.
# Kept for backward compatibility only. Remove in next cleanup.

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from config import (
    AI_PROVIDER,
    AI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
)

# Gemini client already exists in models.py (kept stable)
from models import GeminiClient

logger = logging.getLogger("knoweasy.ai_router")


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured or returns an unusable response."""


def _extract_json(text: str) -> Dict[str, Any]:
    """Best-effort JSON extraction for models that wrap JSON in text."""
    text = (text or "").strip()
    # If it's already JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find the first JSON object in the text
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ProviderError("Model did not return JSON.")
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise ProviderError(f"Invalid JSON from model: {e}") from e


def _provider_order() -> List[str]:
    p = (AI_PROVIDER or "gemini").strip().lower()
    if p in {"auto", "multi"}:
        # Prefer Gemini first (current Phase-1), then OpenAI, then Claude.
        return ["gemini", "openai", "claude"]
    return [p]


def _openai_request(prompt: str, timeout_s: int) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise ProviderError("OPENAI_API_KEY missing.")
    model = OPENAI_MODEL or "gpt-4o-mini"

    url = "https://api.openai.com/v1/chat/completions"
    body = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return ONLY valid JSON. No markdown."},
            {"role": "user", "content": prompt},
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise ProviderError(f"OpenAI HTTPError {e.code}: {detail[:300]}") from e
    except Exception as e:
        # urllib raises TimeoutError sometimes, keep it consistent
        if isinstance(e, TimeoutError):
            raise
        raise ProviderError(f"OpenAI request failed: {e}") from e

    data = json.loads(raw)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _extract_json(content)


def _claude_request(prompt: str, timeout_s: int) -> Dict[str, Any]:
    if not CLAUDE_API_KEY:
        raise ProviderError("CLAUDE_API_KEY missing.")
    model = CLAUDE_MODEL or "claude-3-5-sonnet-20240620"

    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": model,
        "max_tokens": 1200,
        "temperature": 0.2,
        "system": "Return ONLY valid JSON. No markdown.",
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        raise ProviderError(f"Claude HTTPError {e.code}: {detail[:300]}") from e
    except Exception as e:
        if isinstance(e, TimeoutError):
            raise
        raise ProviderError(f"Claude request failed: {e}") from e

    data = json.loads(raw)
    content_blocks = data.get("content") or []
    text = ""
    if content_blocks and isinstance(content_blocks, list):
        text = content_blocks[0].get("text", "") if isinstance(content_blocks[0], dict) else str(content_blocks[0])
    return _extract_json(text)


def generate_json(prompt: str) -> Dict[str, Any]:
    """Generate a JSON response using the configured provider (or auto fallback)."""
    timeout_s = int(AI_TIMEOUT_SECONDS or 30)

    last_err: Optional[Exception] = None
    for provider in _provider_order():
        provider = provider.strip().lower()
        try:
            if provider == "gemini":
                if not GEMINI_API_KEY:
                    raise ProviderError("GEMINI_API_KEY missing.")
                return GeminiClient().generate_json(prompt)
            if provider == "openai":
                return _openai_request(prompt, timeout_s)
            if provider in {"claude", "anthropic"}:
                return _claude_request(prompt, timeout_s)

            raise ProviderError(f"Unknown AI_PROVIDER: {provider}")
        except TimeoutError as e:
            # Bubble up as timeout (orchestrator handles deterministic fallback)
            raise
        except Exception as e:
            last_err = e
            logger.warning("Provider failed (%s): %s", provider, str(e)[:200])

    # If all providers failed:
    if last_err:
        raise ProviderError(f"All providers failed. Last error: {last_err}") from last_err
    raise ProviderError("All providers failed.")
