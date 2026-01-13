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

    def generate_json(self, prompt: str, model: str | None = None) -> dict:
        """Generate strict JSON using Gemini with timeout + circuit breaker."""
        self._guard_circuit()

        use_model = model or GEMINI_PRIMARY_MODEL

        def _do_call(m: str):
            return self._call_generate_content(m, prompt)

        try:
            fut = _executor.submit(_do_call, use_model)
            resp = fut.result(timeout=GEMINI_TIMEOUT_S)
            text = (resp.text or "").strip()
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
                    resp2 = fut2.result(timeout=GEMINI_TIMEOUT_S)
                    text2 = (resp2.text or "").strip()
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
