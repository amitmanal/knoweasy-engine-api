"""learning_router.py
------------------

Lightweight endpoint for returning a **structured AnswerObject** (Learning Object).

This router is safe to import even if other modules change, and it is compatible with the
current One-Brain orchestrator which exposes `solve()` (async).

Endpoint: POST /v1/ai/answer
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from orchestrator import solve
from learning_object import build_answer_object, ensure_answer_object_dict


router = APIRouter()


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)

    # Optional context (keep names aligned with frontend payloads)
    board: Optional[str] = ""
    class_level: Optional[str] = ""
    subject: Optional[str] = ""
    language: Optional[str] = "en"

    # Supported: lite|tutor|mastery (legacy synonyms accepted in orchestrator)
    answer_mode: Optional[str] = "tutor"

    # Optional hints
    exam_mode: Optional[str] = ""
    difficulty: Optional[str] = ""


@router.post("/v1/ai/answer")
async def answer(req: AnswerRequest) -> Dict[str, Any]:
    try:
        ctx = {
            "board": req.board or "",
            "class_level": req.class_level or "",
            "subject": req.subject or "",
            "language": req.language or "en",
            "answer_mode": (req.answer_mode or "tutor"),
            "exam_mode": req.exam_mode or "",
            "difficulty": req.difficulty or "",
        }

        raw = await solve(req.question, ctx, user_tier="free")
        if not raw.get("success"):
            raise HTTPException(status_code=502, detail=raw.get("error") or "AI provider error")

        ao = build_answer_object(
            question=req.question,
            raw_answer=raw.get("answer", ""),
            language=req.language or "en",
            mode=(req.answer_mode or "tutor"),
            board=req.board or "",
            class_level=req.class_level or "",
            subject=req.subject or "",
            exam_mode=req.exam_mode or "",
            ai_meta={
                "confidence": raw.get("confidence"),
                "confidence_label": raw.get("confidence_label"),
                "providers_used": raw.get("providers_used"),
                "ai_strategy": raw.get("ai_strategy"),
                "latency_ms": raw.get("latency_ms"),
                "profile": raw.get("profile"),
                "mode": raw.get("mode"),
                "verification_notes": raw.get("verification_notes"),
            },
        )
        return ensure_answer_object_dict(ao)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
