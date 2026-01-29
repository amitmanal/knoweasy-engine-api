"""Model clients used by KnowEasy Engine API.

This file provides `GeminiClient` used by `ai_router.py`.

Dependency: google-generativeai (import path: `google.generativeai`).
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_TIMEOUT_S,
    CB_FAILURE_THRESHOLD,
    CB_COOLDOWN_S,
)

# Simple in-process circuit breaker.
_cb_failures = 0
_cb_open_until_ts = 0.0

_executor = ThreadPoolExecutor(max_workers=8)


class GeminiCircuitOpen(RuntimeError):
    """Raised when the circuit breaker is open."""


class GeminiClient:
    """Stable Gemini JSON generator for legacy paths.

    NOTE: The main premium orchestration is implemented in `orchestrator.py`.
    This client is here so `ai_router.py` can call Gemini reliably.
    """

    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing. Set it in Render env vars.")
        genai.configure(api_key=GEMINI_API_KEY)

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        n = (name or "").strip()
        if n.startswith("models/"):
            n = n.split("/", 1)[1]
        return n

    def _guard_circuit(self) -> None:
        global _cb_open_until_ts
        now = time.time()
        if _cb_open_until_ts and now < _cb_open_until_ts:
            raise GeminiCircuitOpen("Gemini circuit is temporarily open (cooldown).")

    def _record_success(self) -> None:
        global _cb_failures, _cb_open_until_ts
        _cb_failures = 0
        _cb_open_until_ts = 0.0

    def _record_failure(self) -> None:
        global _cb_failures, _cb_open_until_ts
        _cb_failures += 1
        if _cb_failures >= int(CB_FAILURE_THRESHOLD or 3):
            _cb_open_until_ts = time.time() + int(CB_COOLDOWN_S or 20)

    def _call_generate_content(self, model: str, prompt: str) -> str:
        m = genai.GenerativeModel(model)
        resp = m.generate_content(prompt)
        return getattr(resp, "text", "") or ""

    @staticmethod
    def _extract_json(text: str) -> dict:
        t = (text or "").strip()
        if "{" in t and "}" in t:
            t = t[t.find("{") : t.rfind("}") + 1]
        return json.loads(t)

    def generate_json(self, prompt: str, model: str | None = None) -> dict:
        """Generate strict JSON using Gemini with timeout + model fallback."""
        self._guard_circuit()

        raw_candidates = [
            model,
            GEMINI_PRIMARY_MODEL,
            GEMINI_FALLBACK_MODEL,
            "gemini-2.0-flash",
            ]

        candidates: list[str] = []
        seen: set[str] = set()
        for c in raw_candidates:
            if not c:
                continue
            cn = self._normalize_model_name(str(c))
            if cn and cn not in seen:
                seen.add(cn)
                candidates.append(cn)

        if not candidates:
            raise RuntimeError("No Gemini model configured (GEMINI_PRIMARY_MODEL missing).")

        last_exc: Exception | None = None
        timeout_s = int(GEMINI_TIMEOUT_S or 40)

        for m in candidates:
            try:
                fut = _executor.submit(self._call_generate_content, m, prompt)
                text = fut.result(timeout=timeout_s)
                out = self._extract_json(text)
                self._record_success()
                return out
            except FuturesTimeoutError:
                last_exc = TimeoutError(f"Gemini request timed out (model={m})")
            except Exception as e:
                last_exc = e

        self._record_failure()
        if last_exc:
            raise last_exc
        raise RuntimeError("Gemini request failed for all model candidates.")
