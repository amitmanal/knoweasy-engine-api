"""
learning_router.py
------------------

This module exposes a lightweight FastAPI router for generating
structured learning answers.  It accepts a question and optional
context parameters (board, class_level, subject, language, and
answer_mode) and returns a JSON AnswerObject built by the
orchestrator.  The endpoint is synchronous for simplicity and
returns quickly even when no AI providers are reachable.

Endpoint: POST /v1/ai/answer

The request body should be JSON with at least a "question" field.
Other fields are optional.  The response conforms to the
AnswerObject specification defined in learning_object.py.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from orchestrator import RequestContext, generate_learning_answer


def _answer_object_to_sections(answer_obj: Dict[str, Any]) -> list:
    """Convert AnswerObject dict into PremiumRenderer `sections`.

    PremiumRenderer (frontend) expects a flat list of section objects.
    This keeps the backend contract friendly for both Chat AI and Luma.
    """
    if not isinstance(answer_obj, dict):
        return []

    sections = []

    title = str(answer_obj.get("title") or "").strip()
    why = str(answer_obj.get("why_this_matters") or "").strip()
    if title or why:
        sections.append({
            "type": "header",
            "title": title or "Answer",
            "subtitle": why,
        })

    blocks = answer_obj.get("explanation_blocks") or []
    if isinstance(blocks, list):
        for i, b in enumerate(blocks):
            if isinstance(b, dict):
                bt = str(b.get("title") or "").strip()
                bc = str(b.get("content") or "").strip()
            else:
                bt = ""
                bc = str(b).strip()
            if not bc:
                continue
            # Map first block to definition (nicer icon), rest to explanation
            stype = "definition" if i == 0 else "explanation"
            sections.append({
                "type": stype,
                "title": bt or ("Definition" if i == 0 else f"Explanation {i}"),
                "content": bc,
            })

    visuals = answer_obj.get("visuals") or []
    if isinstance(visuals, list):
        for v in visuals:
            if not isinstance(v, dict):
                continue
            code = str(v.get("code") or "").strip()
            fmt = str(v.get("format") or "").strip().lower()
            vtype = str(v.get("type") or "diagram").strip().lower()
            vtitle = str(v.get("title") or "Visual").strip()
            # PremiumRenderer currently supports mermaid via `diagram_code`
            if code and fmt == "mermaid":
                sections.append({
                    "type": "diagram",
                    "title": vtitle,
                    "diagram_code": code,
                })
            elif code:
                # Fallback as note
                sections.append({
                    "type": "note",
                    "title": vtitle,
                    "content": code,
                })

    examples = answer_obj.get("examples") or []
    if isinstance(examples, list) and examples:
        sections.append({
            "type": "example",
            "title": "Examples",
            "content": "\n".join([f"• {str(x)}" for x in examples if str(x).strip()]),
        })

    mistakes = answer_obj.get("common_mistakes") or []
    if isinstance(mistakes, list) and mistakes:
        sections.append({
            "type": "tips",
            "title": "Common mistakes",
            "content": "\n".join([f"• {str(x)}" for x in mistakes if str(x).strip()]),
        })

    footer = str(answer_obj.get("exam_relevance_footer") or "").strip()
    if footer:
        sections.append({
            "type": "note",
            "title": "Exam relevance",
            "content": footer,
        })

    return sections


router = APIRouter(prefix="/v1/ai", tags=["ai"])


class AnswerRequest(BaseModel):
    question: str = Field(..., description="User question to answer")
    board: Optional[str] = Field(None, description="Educational board (CBSE, ICSE, MH, etc.)")
    class_level: Optional[str] = Field(None, alias="class", description="Class level (5-12)")
    subject: Optional[str] = Field(None, description="Subject name")
    chapter: Optional[str] = Field(None, description="Chapter name or topic")
    exam_mode: Optional[str] = Field(None, description="Exam mode (BOARD, JEE, NEET, CET, etc.)")
    language: Optional[str] = Field(None, description="Output language (en, hi, mr)")
    mode: Optional[str] = Field(None, description="Answer mode (lite, tutor, mastery)")
    answer_mode: Optional[str] = Field(None, description="Deprecated: alias for mode")
    study_mode: Optional[str] = Field(None, description="Study mode: chat or luma")

    class Config:
        allow_population_by_field_name = True


@router.post("/answer")
async def answer(req: AnswerRequest):
    # Basic validation
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Determine answer mode, supporting both `mode` and `answer_mode` aliases
    requested_mode = None
    if req.mode and str(req.mode).strip():
        requested_mode = str(req.mode).strip().lower()
    elif req.answer_mode and str(req.answer_mode).strip():
        requested_mode = str(req.answer_mode).strip().lower()
    # Fallback default mode (Tutor is the product default)
    if not requested_mode:
        requested_mode = "tutor"

    # Determine study mode (chat or luma)
    study_mode = str(req.study_mode or "chat").strip().lower()
    if study_mode not in {"chat", "luma"}:
        study_mode = "chat"

    # Populate a RequestContext for orchestrator
    ctx = RequestContext(
        request_id="api_" + str(hash(q))[:8],
        question=q,
        board=(req.board or "CBSE"),
        class_level=(req.class_level or "10"),
        subject=(req.subject or ""),
        chapter=(req.chapter or ""),
        exam_mode=(req.exam_mode or "BOARD"),
        language=(req.language or "en"),
        study_mode=study_mode,
        answer_mode=requested_mode,
    )

    # Generate the answer object
    answer_dict = generate_learning_answer(ctx)

    sections = _answer_object_to_sections(answer_dict)
    # Build compatibility wrapper so existing frontend can render
    response: Dict[str, Any] = {
        "ok": True,
        "learning_object": answer_dict,
        "sections": sections,
        # Back-compat text fields (frontend must prefer learning_object)
        "final_answer": "\n".join([b.get("content","") for b in (answer_dict.get("explanation_blocks") or []) if isinstance(b, dict)]) if isinstance(answer_dict, dict) else "",
        "answer": "\n".join([b.get("content","") for b in (answer_dict.get("explanation_blocks") or []) if isinstance(b, dict)]) if isinstance(answer_dict, dict) else "",
        "meta": {
            "credits_used": 0,
            "providers_used": [],
            "ai_strategy": ctx.answer_mode or "lite",
            "confidence": None,
            "confidence_label": "",
            "verified": False
        }
    }
    return response