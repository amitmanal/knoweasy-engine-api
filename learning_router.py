"""learning_router.py — Premium answer endpoint

POST /v1/ai/answer

Frontend contract (core.js / chat.js):
- Returns:
  - ok: bool
  - learning_object: AnswerObject-like dict (for back-compat + export)
  - sections: PremiumRenderer sections list (preferred UI)
  - meta: { providers_used, ai_strategy, verified, request_id, ... }
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from orchestrator import RequestContext, generate_learning_answer

router = APIRouter()

def _sections_to_blocks(sections: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    for s in (sections or []):
        if not isinstance(s, dict):
            continue
        t = (s.get("type") or "").lower()
        if t in {"definition","explanation","answer","tips","warning"}:
            title = str(s.get("title") or "").strip() or ("Explanation" if t=="explanation" else t.title())
            content = str(s.get("content") or "").strip()
            if content:
                blocks.append({"title": title, "content": content})
    if not blocks:
        # fall back to first header content if present
        for s in (sections or []):
            if isinstance(s, dict) and (s.get("type")=="header") and (s.get("subtitle") or s.get("content")):
                blocks.append({"title": "Summary", "content": str(s.get("subtitle") or s.get("content") or "")})
                break
    return blocks

class AnswerRequest(BaseModel):
    question: str = Field(..., description="User question to answer")
    board: Optional[str] = Field(None, description="Educational board (CBSE, ICSE, MH, etc.)")
    class_level: Optional[str] = Field(None, alias="class", description="Class level (5-12)")
    subject: Optional[str] = Field(None, description="Subject name")
    chapter: Optional[str] = Field(None, description="Chapter name or topic")
    exam_mode: Optional[str] = Field(None, description="Exam mode (BOARD, JEE, NEET, CET, OLYMPIAD, etc.)")
    language: Optional[str] = Field(None, description="Output language (en, hi, mr)")
    answer_mode: Optional[str] = Field("tutor", description="Answer mode: lite | tutor | mastery")
    study_mode: Optional[str] = Field(None, description="Study mode: chat or luma")
    request_id: Optional[str] = Field(None, description="Client idempotency id")

    class Config:
        allow_population_by_field_name = True

@router.post("/v1/ai/answer")
def answer(req: AnswerRequest) -> Dict[str, Any]:
    ctx = RequestContext(
        request_id=req.request_id or "",
        question=req.question or "",
        board=req.board or "",
        class_level=req.class_level or "",
        subject=req.subject or "",
        chapter=req.chapter or "",
        exam_mode=req.exam_mode or "",
        language=req.language or "en",
        study_mode=req.study_mode or "chat",
        answer_mode=req.answer_mode or "tutor",
    )

    ans = generate_learning_answer(ctx) or {}
    sections = ans.get("sections") if isinstance(ans, dict) else []
    meta = ans.get("meta") if isinstance(ans, dict) and isinstance(ans.get("meta"), dict) else {}
    providers_used = ans.get("providers_used") if isinstance(ans, dict) else []
    if not isinstance(providers_used, list):
        providers_used = []

    # Build AnswerObject-like learning_object for export/back-compat
    learning_object = {
        "title": ans.get("title") or "Answer",
        "why_this_matters": ans.get("why_this_matters") or "",
        "explanation_blocks": _sections_to_blocks(sections),
        "visuals": [],
        "examples": [],
        "common_mistakes": ans.get("common_mistakes") or [],
        "exam_relevance_footer": ans.get("exam_relevance_footer") or "",
        "follow_up_chips": ans.get("follow_up_chips") or [],
        "language": ctx.language or "en",
        "mode": (ctx.answer_mode or "tutor").lower(),
    }

    # Back-compat plain text
    final_text = "\n".join([b.get("content","") for b in (learning_object.get("explanation_blocks") or []) if isinstance(b, dict)])

    response: Dict[str, Any] = {
        "ok": True,
        "learning_object": learning_object,
        "sections": sections or [],
        "final_answer": final_text,
        "answer": final_text,
        "meta": {
            "providers_used": providers_used or meta.get("providers_used") or [],
            "ai_strategy": (ctx.answer_mode or "tutor").lower(),
            "verified": bool(meta.get("verified", False)),
            "request_id": meta.get("request_id") or ctx.request_id or "",
            "profile": meta.get("profile", ""),
            "difficulty": meta.get("difficulty", ""),
        }
    }

    # Pass through extra meta for debugging (safe)
    if meta:
        response["meta"]["models"] = meta.get("models", {})
        response["meta"]["verification_notes"] = meta.get("verification_notes", [])

    return response
