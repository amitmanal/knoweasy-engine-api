import json
import logging

from config import (
    AI_ENABLED,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_STEPS,
    MAX_CHARS_ANSWER,
    AI_TIMEOUT_SECONDS,
    AI_PROVIDER,
    AI_MODE,
)
from models import GeminiClient, GeminiCircuitOpen
from verifier import basic_verify

logger = logging.getLogger(__name__)


def _get(payload: dict, *keys, default=None):
    """Safe getter: returns the first key found (supports alias fields)."""
    for k in keys:
        if k in payload and payload.get(k) is not None:
            return payload.get(k)
    return default


def build_prompt(payload: dict) -> str:
    """
    Forces strict JSON output with a stable schema.
    NOTE: Supports both 'class' and 'class_' (Pydantic v2 model_dump default).
    """
    question = str(_get(payload, "question", default="")).strip()
    clazz = _get(payload, "class", "class_", "class_level", default="")
    board = str(_get(payload, "board", default="")).strip()
    subject = str(_get(payload, "subject", default="")).strip()
    chapter = str(_get(payload, "chapter", default="") or "").strip()
    exam_mode = str(_get(payload, "exam_mode", default="BOARD")).strip()
    language = str(_get(payload, "language", default="en")).strip()

    return f"""You are KnowEasy AI Mentor. You MUST answer strictly in JSON.
Schema:
{{
  "final_answer": string,
  "steps": [string],
  "assumptions": [string],
  "confidence": number,  # 0 to 1
  "flags": [string],
  "safe_note": string|null
}}

Rules:
- Student class: {clazz}
- Board: {board}
- Subject: {subject}
- Chapter: {chapter}
- Exam mode: {exam_mode}
- Language: {language}
- Keep final_answer under {MAX_CHARS_ANSWER} characters.
- Keep steps <= {MAX_STEPS}.
- If question is unclear, ask 1-2 short clarifying questions inside final_answer.
- Do not include markdown fences. Output ONLY JSON.

Question:
{question}
"""


def _normalize_output(out: dict) -> dict:
    out = out or {}
    out.setdefault("final_answer", "")
    out.setdefault("steps", [])
    out.setdefault("assumptions", [])
    out.setdefault("confidence", 0.5)
    out.setdefault("flags", [])
    out.setdefault("safe_note", None)

    # Hard caps (never exceed)
    try:
        out["steps"] = list(out.get("steps") or [])[:MAX_STEPS]
    except Exception:
        out["steps"] = []
    try:
        out["final_answer"] = (out.get("final_answer") or "")[:MAX_CHARS_ANSWER]
    except Exception:
        out["final_answer"] = ""

    # Ensure types
    try:
        out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.5))))
    except Exception:
        out["confidence"] = 0.5
    if not isinstance(out.get("flags"), list):
        out["flags"] = []
    if not isinstance(out.get("assumptions"), list):
        out["assumptions"] = []

    return out


def solve(payload: dict) -> dict:
    """Main solve pipeline. Phase-1C focuses on stability + determinism."""

    # CEO kill-switch: app stays alive even if AI is paused.
    if not AI_ENABLED:
        return _normalize_output(
            {
                "final_answer": "AI Mentor is temporarily paused for safety. Please try again later 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_DISABLED"],
                "safe_note": "You can still use study content and quizzes.",
            }
        )

    # Deterministic input handling (supports both aliases)
    question = str(_get(payload, "question", default="")).strip()
    if len(question) < 3:
        return _normalize_output(
            {
                "final_answer": "Please type your full question (at least 3 characters) 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["INVALID_INPUT"],
                "safe_note": "Tip: add chapter/topic for better answers.",
            }
        )

    prompt = build_prompt(payload)
    client = GeminiClient()

    try:
        out = client.generate_json(prompt)
    except TimeoutError:
        # Deterministic timeout behavior (uses AI_TIMEOUT_SECONDS via config)
        logger.warning("AI timeout (%ss) provider=%s mode=%s", AI_TIMEOUT_SECONDS, AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI is taking too long right now. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_TIMEOUT"],
                "safe_note": "Tip: add chapter/topic to get faster answers.",
            }
        )
    except GeminiCircuitOpen:
        logger.warning("AI circuit open provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI is busy right now due to high load. Please try again shortly 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_BUSY"],
                "safe_note": "This is a temporary safety limit.",
            }
        )
    except json.JSONDecodeError:
        # Gemini returned non-JSON (deterministic handling)
        logger.exception("AI returned invalid JSON provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI returned an unclear format. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_BAD_JSON"],
                "safe_note": "Tip: add chapter/topic for clearer answers.",
            }
        )
    except Exception:
        # Provider or unexpected runtime (keep stable, but visible in logs)
        logger.exception("AI provider error provider=%s mode=%s", AI_PROVIDER, AI_MODE)
        return _normalize_output(
            {
                "final_answer": "AI had a small hiccup while solving. Please try again in a few seconds 😊",
                "steps": [],
                "assumptions": [],
                "confidence": 0.2,
                "flags": ["AI_PROVIDER_ERROR"],
                "safe_note": "Tip: add chapter/topic or give more details.",
            }
        )

    out = _normalize_output(out)

    # Basic verification adds safety flags + minor confidence adjustment
    try:
        adj, flags, assumptions = basic_verify(question, out["final_answer"], out["steps"])
        out["flags"] = list(dict.fromkeys((out.get("flags") or []) + flags))
        out["assumptions"] = list(dict.fromkeys((out.get("assumptions") or []) + assumptions))
        out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.5)) + adj))
    except Exception:
        # Verification must never crash
        out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["VERIFY_FAILED"]))

    # Low-confidence second pass (kept, but bounded)
    if out["confidence"] < LOW_CONFIDENCE_THRESHOLD:
        try:
            out2 = client.generate_json(prompt)
            out2 = _normalize_output(out2)
            adj2, flags2, assumptions2 = basic_verify(question, out2["final_answer"], out2["steps"])
            out2["flags"] = list(dict.fromkeys((out2.get("flags") or []) + flags2))
            out2["assumptions"] = list(dict.fromkeys((out2.get("assumptions") or []) + assumptions2))
            out2["confidence"] = max(0.0, min(1.0, float(out2.get("confidence", 0.5)) + adj2))

            # choose better result
            if out2["confidence"] >= out["confidence"]:
                out = out2
                out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["SECOND_PASS"]))
        except Exception:
            # If second pass fails, keep first output (stability first)
            out["flags"] = list(dict.fromkeys((out.get("flags") or []) + ["SECOND_PASS_FAILED"]))

    return out
