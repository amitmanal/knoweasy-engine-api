from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ai_router import generate_json, ProviderError

logger = logging.getLogger("knoweasy.luma_router")

router = APIRouter(prefix="/luma", tags=["luma"])


class LumaProfile(BaseModel):
    goal: Optional[str] = None  # learn | revise | exam
    difficulty: Optional[str] = None  # basic | exam | advanced


class LumaStep(BaseModel):
    type: Optional[str] = None
    id: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    q: Optional[str] = None
    options: Optional[list[str]] = None


class LumaTutorRequest(BaseModel):
    cls: str
    board: str
    subject: str
    chapter: str
    chapterTitle: Optional[str] = ""
    mode: str = "full"
    lang: str = "en"
    profile: Optional[Dict[str, Any]] = None
    step: Optional[LumaStep] = None
    question: str = Field(default="", description="User doubt/question")


class LumaTutorResponse(BaseModel):
    answer: str
    followup_mcq: Optional[Dict[str, Any]] = None


def _build_prompt(req: LumaTutorRequest) -> str:
    # Keep prompt compact and deterministic. We ask for JSON.
    step_bits = ""
    if req.step:
        step_bits = f"""
CURRENT_STEP:
- type: {req.step.type}
- title: {req.step.title}
- text: {req.step.text}
- question: {req.step.q}
- options: {req.step.options}
"""
    profile = req.profile or {}
    return f"""
You are "Luma", a friendly Indian school teacher AI tutor.
You help CBSE/State-board students with clear, step-by-step explanations.

Return ONLY valid JSON with keys:
- "answer": string (helpful, short, student-friendly)
- "followup_mcq": optional object with keys {{"q": string, "options": [..], "answer": number, "explain": string}}

Constraints:
- Do not mention you are an AI model. Be calm, encouraging.
- If user asks for the answer directly, still explain briefly.
- Language: {req.lang}. If {req.lang} is not English, respond in that language.

CONTEXT:
- class: {req.cls}
- board: {req.board}
- subject: {req.subject}
- chapter: {req.chapterTitle or req.chapter}
- mode: {req.mode}
- profile: goal={profile.get("goal")} difficulty={profile.get("difficulty")}

{step_bits}

USER_QUESTION:
{req.question}
""".strip()


@router.post("/tutor", response_model=LumaTutorResponse)
def luma_tutor(req: LumaTutorRequest) -> LumaTutorResponse:
    prompt = _build_prompt(req)
    try:
        out = generate_json(prompt)
    except ProviderError as e:
        logger.warning("Provider error: %s", e)
        raise
    except Exception as e:
        logger.exception("Unexpected luma tutor error")
        raise

    answer = str(out.get("answer") or "").strip()
    follow = out.get("followup_mcq")
    if not answer:
        answer = "I can help — please ask your doubt again in one line."

    # Basic sanitation
    if follow and isinstance(follow, dict):
        if "options" in follow and not isinstance(follow["options"], list):
            follow["options"] = []
    else:
        follow = None

    return LumaTutorResponse(answer=answer, followup_mcq=follow)


class LumaEvent(BaseModel):
    name: str
    payload: Optional[Dict[str, Any]] = None


@router.post("/event")
def luma_event(ev: LumaEvent) -> Dict[str, Any]:
    # Lightweight analytics hook (logs only). You can later store in DB/Redis.
    logger.info("LUMA_EVENT %s %s", ev.name, ev.payload or {})
    return {"ok": True}
