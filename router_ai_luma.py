from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_router import generate_json, ProviderError

router = APIRouter(prefix="/ai/luma", tags=["ai", "luma"])


# ----------------- Schemas -----------------
class LumaUser(BaseModel):
    class_: Optional[str] = Field(default=None, alias="class")
    board: Optional[str] = None
    language: Optional[str] = None


class LumaLesson(BaseModel):
    subject: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    card_type: Optional[str] = None
    card_title: Optional[str] = None
    card_content: Optional[str] = None


class LumaHelpRequest(BaseModel):
    user: LumaUser
    lesson: LumaLesson
    intent: str  # "Explain simpler" | "Another example" | "Ask me 3 quick questions" | "Check my steps" | "Free doubt"
    question: Optional[str] = ""
    ai_hints: Dict[str, Any] = Field(default_factory=dict)


class LumaHelpResponse(BaseModel):
    explanation: str
    example: str = ""
    check_question: str = ""
    next_options: List[str] = Field(default_factory=list)


def _safe_str(x: Any, limit: int = 1800) -> str:
    s = "" if x is None else str(x)
    s = s.replace("\x00", "").strip()
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


def _build_prompt(req: LumaHelpRequest) -> str:
    lang = (req.user.language or "en").strip() or "en"

    # Hard scope policy (trust-first)
    scope = req.ai_hints.get("scope") or "current_card_only"
    ncert = req.ai_hints.get("ncertAligned", True)

    lesson = req.lesson
    intent = _safe_str(req.intent, 60)
    student_q = _safe_str(req.question, 600)

    card_ctx = {
        "subject": _safe_str(lesson.subject, 80),
        "chapter": _safe_str(lesson.chapter, 120),
        "section": _safe_str(lesson.section, 120),
        "card_type": _safe_str(lesson.card_type, 40),
        "card_title": _safe_str(lesson.card_title, 120),
        "card_content": _safe_str(lesson.card_content, 1800),
    }

    # Output contract: keep predictable for UI
    schema = {
        "explanation": "string (main helpful reply, calm tone, short)",
        "example": "string (optional, only when asked or useful)",
        "check_question": "string (optional, a quick check question)",
        "next_options": ["string"]
    }

    rules = [
        "You are Luma: a calm, premium teacher helping an Indian school student.",
        "Stay strictly within the CURRENT card/context. Do not teach the full chapter.",
        "If something is missing in the card content, ask ONE short clarifying question inside 'explanation'.",
        "No hallucinated facts. If unsure, say so and suggest what to check in NCERT.",
        "Use simple English (unless lang != 'en'). Keep it brief and point-wise when possible.",
        "Return ONLY valid JSON. No markdown. No extra keys.",
    ]
    if ncert:
        rules.insert(2, "NCERT-aligned only. Avoid out-of-syllabus expansions.")

    prompt = {
        "task": "Luma help for a single learning card",
        "language": lang,
        "scope": scope,
        "intent": intent,
        "student_question": student_q,
        "card_context": card_ctx,
        "output_schema": schema,
        "rules": rules,
    }
    return json.dumps(prompt, ensure_ascii=False)


@router.post("/help", response_model=LumaHelpResponse)
def luma_help(req: LumaHelpRequest) -> Dict[str, Any]:
    try:
        prompt = _build_prompt(req)
        out = generate_json(prompt)  # provider-configured (Gemini by default)
        # Normalize + validate keys (never crash UI)
        explanation = _safe_str(out.get("explanation") or out.get("answer") or "")
        example = _safe_str(out.get("example") or "")
        check_q = _safe_str(out.get("check_question") or out.get("check") or "")
        next_opts = out.get("next_options") or out.get("next") or []
        if not isinstance(next_opts, list):
            next_opts = []
        next_opts = [ _safe_str(x, 60) for x in next_opts if str(x).strip() ][:6]

        if not explanation:
            explanation = "I can help — please share the exact line you are stuck on from this card."

        return {
            "explanation": explanation,
            "example": example,
            "check_question": check_q,
            "next_options": next_opts,
        }
    except ProviderError as e:
        raise HTTPException(status_code=503, detail=f"AI provider error: {e}")
    except Exception as e:
        # Safety: never expose stack traces
        raise HTTPException(status_code=500, detail=f"Luma help failed: {type(e).__name__}")
