from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse

from tests_schemas import TestGenerateRequest, GeneratedTest
from ai_router import generate_json as generate_ai_json

from auth_store import session_user
from payments_store import get_subscription
import billing_store
from redis_store import setnx_ex as redis_setnx_ex

logger = logging.getLogger("knoweasy.tests_router")

router = APIRouter(prefix="/test", tags=["tests"])


def _auth_user(authorization: Optional[str]) -> Optional[Dict[str, Any]]:
    if not authorization:
        return None
    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token:
        return None
    try:
        return session_user(token)
    except Exception:
        return None


def _credits_for(kind: str, n_questions: int) -> int:
    # Simple, transparent defaults. Tune later via env without redeploy.
    base = int(os.getenv("CREDITS_TEST_BASE", "2"))
    per_10q = int(os.getenv("CREDITS_TEST_PER_10Q", "1"))
    if kind == "entrance":
        base = int(os.getenv("CREDITS_TEST_ENTRANCE_BASE", str(base + 1)))
    # scale with size
    units = base + (max(0, int(n_questions) - 10) // 10) * per_10q
    return max(1, min(10, units))


def _build_prompt(req: TestGenerateRequest) -> str:
    # Keep prompt deterministic + JSON-only.
    # IMPORTANT: Do not mention credits or internal system.
    exam_context = "Board Exam"
    if req.goal == "JEE_PCM":
        exam_context = "JEE (PCM)"
    elif req.goal == "NEET_PCB":
        exam_context = "NEET (PCB)"
    elif req.goal == "CET_PCM":
        exam_context = "CET (PCM)"
    elif req.goal == "CET_PCB":
        exam_context = "CET (PCB)"

    dur = req.duration_minutes or (20 if req.kind == "quiz" else (45 if req.kind == "boards" else 60))

    return f"""You are an expert teacher and exam setter.

Return ONLY valid JSON (no markdown, no extra text). The JSON must follow this schema EXACTLY:
{{
  "title": string,
  "class_n": integer,
  "board": string,
  "subject": string,
  "chapters": [string],
  "kind": "quiz" | "boards" | "entrance",
  "goal": "NONE" | "BOARD" | "JEE_PCM" | "NEET_PCB" | "CET_PCM" | "CET_PCB",
  "duration_minutes": integer,
  "questions": [
    {{
      "id": integer,
      "question": string,
      "options": [string,string,string,string],
      "answer_index": integer,   // 0-3
      "explanation": string
    }}
  ]
}}

Rules:
- Create exactly {req.n_questions} MCQ questions with 4 options each.
- answer_index MUST be 0,1,2,or 3.
- Questions must match Class {req.class_n} {req.board.upper()} syllabus level for subject {req.subject}.
- Chapters focus: {", ".join(req.chapters) if req.chapters else "mixed from the subject syllabus"}.
- Difficulty: {req.difficulty}.
- Exam context overlay (for 11-12): {exam_context}. This only changes style/depth, not the base syllabus.
- Language: {req.language}. If not English, translate question + options + explanation.
- Explanations: concise, teacher-like (2-5 lines).

Now generate the JSON test."""


@router.post("/generate")
async def generate_test(
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Generate a test JSON for the Tests page (separate from chapter mini-quizzes).

    - If user is authenticated, we consume credits (idempotent).
    - If guest, we allow generation (no ledger) for Phase-1 stability.
    """
    t0 = time.time()
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        req = TestGenerateRequest(**(payload or {}))
    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": "BAD_REQUEST", "message": str(e)})

    # Optional idempotency guard (prevents double-credit + double-gen on retries)
    request_id = (req.request_id or "").strip()
    idem_key = ""
    if request_id:
        idem_key = f"idem:testgen:{request_id}"
        try:
            ok = redis_setnx_ex(idem_key, 180, value=str(int(time.time())))
            if not ok:
                # Already processing or done recently
                return JSONResponse(status_code=409, content={"ok": False, "error": "DUPLICATE_REQUEST", "message": "Duplicate request_id. Please retry with a new request_id."})
        except Exception:
            # Redis not available: proceed (Phase-1 stability)
            pass

    user_ctx = _auth_user(authorization)
    sub = None
    plan = "free"
    user_id = None
    if user_ctx:
        user_id = int(user_ctx.get("user_id"))
        try:
            sub = get_subscription(user_id)
        except Exception:
            sub = None
        try:
            plan = (sub or {}).get("plan") or "free"
        except Exception:
            plan = "free"

    # Credit consumption (only for logged-in users)
    credits_units = _credits_for(req.kind, req.n_questions)
    if user_id:
        try:
            billing_store.consume_credits(
                user_id=user_id,
                plan=str(plan),
                units=int(credits_units),
                meta={
                    "feature": "TEST_GENERATE",
                    "kind": req.kind,
                    "class_n": req.class_n,
                    "board": req.board,
                    "subject": req.subject,
                    "n_questions": req.n_questions,
                },
            )
        except ValueError as e:
            return JSONResponse(
                status_code=402,
                content={
                    "ok": False,
                    "error": "INSUFFICIENT_CREDITS",
                    "message": str(e),
                    "required_credits": int(credits_units),
                },
            )
        except Exception:
            # If DB is down, allow but report warning (trust-safe)
            pass

    prompt = _build_prompt(req)

    try:
        out = generate_ai_json(prompt)
        # Validate shape
        test_obj = GeneratedTest(**out)
    except Exception as e:
        logger.exception("test generation failed: %s", e)
        return JSONResponse(status_code=502, content={"ok": False, "error": "AI_FAILED", "message": "AI failed to generate a valid test. Please try again."})

    ms = int((time.time() - t0) * 1000)
    meta = {
        "ms": ms,
        "credits_charged": int(credits_units) if user_id else 0,
        "plan": plan if user_id else "guest",
        "ai_provider": os.getenv("AI_PROVIDER", "gemini"),
    }
    return {"ok": True, "test": test_obj.model_dump(), "meta": meta}
