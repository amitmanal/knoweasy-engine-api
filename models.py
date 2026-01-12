"""LLM provider clients.

Gemini-only is the default for KnowEasy Engine v1.

Stability goal: never crash-loop on import. The `google-genai` package commonly
supports `from google import genai`, but some environments have a shadowing
`google` namespace which can break that import. We try a fallback import so the
service can start and surface a clear error.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

_GENAI_IMPORT_ERROR: Exception | None = None

try:
    # Preferred import for google-genai
    from google import genai  # type: ignore
except Exception as e1:  # pragma: no cover
    try:
        # Fallback import style (some environments expose it this way)
        import google.genai as genai  # type: ignore
    except Exception as e2:  # pragma: no cover
        genai = None  # type: ignore
        _GENAI_IMPORT_ERROR = e2

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
    """Raised when circuit breaker is open."""


class GeminiClient:
    def __init__(self) -> None:
        if genai is None:
            # Provide a very explicit dependency error.
            raise RuntimeError(
                "Gemini client import failed. Ensure `google-genai` is installed and no conflicting `google` package is shadowing it. "
                f"Import error: {_GENAI_IMPORT_ERROR}"
            )
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
        if _cb_failures >= int(CB_FAILURE_THRESHOLD):
            _cb_open_until_ts = time.time() + float(CB_COOLDOWN_S)

    def generate_json(self, prompt: str, model: str | None = None) -> dict:
        """Generate strict JSON using Gemini with timeout + circuit breaker."""
        self._guard_circuit()

        use_model = model or GEMINI_PRIMARY_MODEL

        def _do_call(m: str):
            return self._call_generate_content(m, prompt)

        try:
            fut = _executor.submit(_do_call, use_model)
            resp = fut.result(timeout=float(GEMINI_TIMEOUT_S))
            text = (getattr(resp, 'text', '') or '').strip()
            # Best-effort trimming to the first JSON object.
            if "{" in text and "}" in text:
                text = text[text.find("{") : text.rfind("}") + 1]
            out = json.loads(text)
            self._record_success()
            return out

        except FuturesTimeoutError:
            self._record_failure()
            raise TimeoutError("Gemini request timed out")

        except Exception:
            # fallback model attempt
            try:
                if use_model != GEMINI_FALLBACK_MODEL:
                    fut2 = _executor.submit(_do_call, GEMINI_FALLBACK_MODEL)
                    resp2 = fut2.result(timeout=float(GEMINI_TIMEOUT_S))
                    text2 = (getattr(resp2, 'text', '') or '').strip()
                    if "{" in text2 and "}" in text2:
                        text2 = text2[text2.find("{") : text2.rfind("}") + 1]
                    out2 = json.loads(text2)
                    self._record_success()
                    return out2
            except FuturesTimeoutError:
                self._record_failure()
                raise TimeoutError("Gemini fallback request timed out")
            except Exception:
                self._record_failure()
                raise

            self._record_failure()
            raise
