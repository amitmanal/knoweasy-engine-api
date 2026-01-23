from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


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
    intent: str
    question: Optional[str] = ""
    ai_hints: Dict[str, Any] = Field(default_factory=dict)


class LumaHelpResponse(BaseModel):
    explanation: str
    example: str = ""
    check_question: str = ""
    next_options: List[str] = Field(default_factory=list)


# ----------------- Gemini call -----------------
def _env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v.strip() if v else default


def _build_prompt(req: LumaHelpRequest) -> str:
    # Hard safety constraints
    lang = req.user.language or "en"
    lesson = req.lesson
    hints = req.ai_hints or {}

    do_not_say = hints.get("do_not_say") or []
    if isinstance(do_not_say, str):
        do_not_say = [do_not_say]

    # Keep the system instruction short & strict
    sys = (
        "You are a calm senior teacher helping an Indian school student.\n"
        "Rules:\n"
        "1) Explain ONLY the current concept (current card/section). Do not jump ahead.\n"
        "2) Use simple language. Be brief.\n"
        "3) Do not copy textbook lines.\n"
        "4) Do not provide full-chapter teaching.\n"
        "5) Output must be VALID JSON with keys: explanation, example, check_question, next_options.\n"
    )

    scope = (
        f"Lesson context:\n"
        f"- Subject: {lesson.subject}\n"
        f"- Chapter: {lesson.chapter}\n"
        f"- Section: {lesson.section}\n"
        f"- Card type: {lesson.card_type}\n"
        f"- Card title: {lesson.card_title}\n"
        f"- Current card content:\n{lesson.card_content}\n"
    )

    intent = req.intent or "custom_question"
    question = (req.question or "").strip()

    guidance = []
    if hints.get("simple"):
        guidance.append(f"Simple-explain hint: {hints['simple']}")
    if hints.get("example"):
        guidance.append(f"Example hint: {hints['example']}")
    if hints.get("check_questions"):
        guidance.append(f"Check-question ideas: {hints['check_questions']}")

    if do_not_say:
        guidance.append("Avoid these terms/topics: " + ", ".join(map(str, do_not_say)))

    user_task = f"Intent: {intent}\n"
    if question:
        user_task += f"Student question: {question}\n"

    user_task += (
        "Return JSON only. explanation should be 2-4 short sentences. "
        "example should be max 1 short example/analogy. "
        "check_question should be 1 short question. "
        "next_options should be an array of 1-3 short strings like 'Explain even simpler'. "
        f"Language: {lang}.\n"
    )

    return sys + "\n" + scope + "\n" + ("\n".join(guidance) + "\n" if guidance else "") + user_task


async def _gemini_generate_json(prompt: str) -> Dict[str, Any]:
    api_key = _env("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not set")

    model = _env("GEMINI_MODEL", "gemini-1.5-flash")
    # Gemini REST endpoint (Generative Language API)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    body = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": float(_env("LUMA_AI_TEMPERATURE", "0.4")),
            "maxOutputTokens": int(_env("LUMA_AI_MAX_TOKENS", "400"))
        }
    }

    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=body)
        if r.status_code >= 400:
            raise HTTPException(status_code=503, detail=f"Gemini error HTTP {r.status_code}")

        data = r.json()
        # Extract text from Gemini response
        text = ""
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            raise HTTPException(status_code=503, detail="Gemini response parse error")

    # Attempt to extract JSON object from text safely
    # Some models may wrap in ```json ... ```
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise HTTPException(status_code=503, detail="AI returned non-JSON output")
    raw = m.group(0)

    import json
    try:
        obj = json.loads(raw)
        return obj
    except Exception:
        raise HTTPException(status_code=503, detail="AI returned invalid JSON")


def _normalize_response(obj: Dict[str, Any]) -> LumaHelpResponse:
    explanation = str(obj.get("explanation") or "").strip()
    example = str(obj.get("example") or "").strip()
    check_q = str(obj.get("check_question") or "").strip()
    next_opts = obj.get("next_options") or []
    if not isinstance(next_opts, list):
        next_opts = []
    next_opts = [str(x).strip() for x in next_opts if str(x).strip()][:3]

    # Minimal guarantees
    if not explanation:
        explanation = "Let’s look at it slowly. This part is about the current concept in your card. Try reading it once more and ask me what exactly feels confusing."

    return LumaHelpResponse(
        explanation=explanation[:800],
        example=example[:500],
        check_question=check_q[:250],
        next_options=next_opts or ["Explain even simpler", "Another example"]
    )


@router.post("/help", response_model=LumaHelpResponse)
async def luma_help(req: LumaHelpRequest):
    prompt = _build_prompt(req)
    obj = await _gemini_generate_json(prompt)
    return _normalize_response(obj)
