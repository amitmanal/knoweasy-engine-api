import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from google import genai

from config import (
    GEMINI_API_KEY,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_TIMEOUT_S,
    CB_FAILURE_THRESHOLD,
    CB_COOLDOWN_S,
)

# Simple circuit breaker state (module-level; per-process).
# On Render free tier you typically run 1 instance, so this works well for Phase-1.
_cb_failures = 0
_cb_open_until_ts = 0.0

_executor = ThreadPoolExecutor(max_workers=8)


class GeminiCircuitOpen(RuntimeError):
    pass


class GeminiClient:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing. Set it in Render env vars.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def _call_generate_content(self, model: str, prompt: str):
        return self.client.models.generate_content(model=model, contents=prompt)

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
        if _cb_failures >= CB_FAILURE_THRESHOLD:
            _cb_open_until_ts = time.time() + CB_COOLDOWN_S

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        # Some SDK examples use "models/<name>" while config typically uses "<name>".
        n = (name or "").strip()
        if n.startswith("models/"):
            n = n[len("models/") :]
        return n

    def generate_json(self, prompt: str, model: str | None = None) -> dict:
        """Generate strict JSON using Gemini with timeout + circuit breaker.

        Robust model selection:
        - Tries requested model (if provided), then env primary/fallback, then safe known models.
        - Never crashes the server on model 404; it will try the next candidate.
        """
        self._guard_circuit()

        # Build candidate models in priority order and de-duplicate.
        raw_candidates = [
            model,
            GEMINI_PRIMARY_MODEL,
            GEMINI_FALLBACK_MODEL,
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
        ]
        candidates: list[str] = []
        seen: set[str] = set()
        for c in raw_candidates:
            if not c:
                continue
            c_norm = self._normalize_model_name(str(c))
            if c_norm and c_norm not in seen:
                seen.add(c_norm)
                candidates.append(c_norm)

        if not candidates:
            raise RuntimeError("No Gemini model configured (GEMINI_PRIMARY_MODEL missing).")

        def _extract_json(text: str) -> dict:
            t = (text or "").strip()
            if "{" in t and "}" in t:
                t = t[t.find("{") : t.rfind("}") + 1]
            return json.loads(t)

        last_exc: Exception | None = None

        for m in candidates:
            try:
                fut = _executor.submit(self._call_generate_content, m, prompt)
                resp = fut.result(timeout=GEMINI_TIMEOUT_S)
                out = _extract_json(getattr(resp, "text", "") or "")
                self._record_success()
                return out
            except FuturesTimeoutError as e:
                last_exc = TimeoutError(f"Gemini request timed out (model={m})")
            except Exception as e:
                # Covers model 404, API errors, JSON parse errors, etc.
                last_exc = e

        # If we reached here, all models failed.
        self._record_failure()
        if last_exc:
            raise last_exc
        raise RuntimeError("Gemini request failed for all model candidates.")
