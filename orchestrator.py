import json
from config import (
    AI_ENABLED,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_STEPS,
    MAX_CHARS_ANSWER,
)
from models import GeminiClient, GeminiCircuitOpen
from verifier import basic_verify


def build_prompt(payload: dict) -> str:
    """
    Forces strict JSON output with a stable schema.
    """
    question = payload.get("question","")
    clazz = payload.get("class") or payload.get("class_")
    board = payload.get("board","")
    subject = payload.get("subject","")
    chapter = payload.get("chapter") or ""
    exam_mode = payload.get("exam_mode", "BOARD")
    language = payload.get("language", "en")

    # Keep prompt short + predictable (stable cost)
    return f"""You are KnowEasy AI Mentor. You MUST answer strictly in JSON.
Schema:
{{
  \"final_answer\": string,
  \"steps\": [string],
  \"assumptions\": [string],
  \"confidence\": number,  # 0 to 1
  \"flags\": [string],
  \"safe_note\": string|null
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
    """Main solve pipeline. Phase-1 focuses on stability, not features."""

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

    prompt = build_prompt(payload)
    client = GeminiClient()

    try:
        out = client.generate_json(prompt)
    except TimeoutError:
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

    out = _normalize_output(out)

    # Basic verification adds safety flags + minor confidence adjustment
    adj, flags, assumptions = basic_verify(payload["question"], out["final_answer"], out["steps"])
    out["flags"] = list(dict.fromkeys((out.get("flags") or []) + flags))
    out["assumptions"] = list(dict.fromkeys((out.get("assumptions") or []) + assumptions))
    out["confidence"] = max(0.0, min(1.0, float(out.get("confidence", 0.5)) + adj))

    # Low-confidence second pass (kept, but bounded)
    if out["confidence"] < LOW_CONFIDENCE_THRESHOLD:
        try:
            out2 = client.generate_json(prompt)
            out2 = _normalize_output(out2)
            adj2, flags2, assumptions2 = basic_verify(payload["question"], out2["final_answer"], out2["steps"])
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
