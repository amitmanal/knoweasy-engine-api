"""KnowEasy Engine — Orchestrator (Gemini-only, router-compatible)

This module MUST provide: `solve(payload: dict) -> dict`
because `router.py` imports `solve` and calls it synchronously as: `out = solve(payload)`.

Design goals:
- Production-stable (never crash / never raise to router)
- Gemini-only today (future providers can be added without changing router)
- Returns a dict shaped exactly like router expects:
  { final_answer, steps, assumptions, confidence, flags, safe_note, ... }
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import google.generativeai as genai

from config import (
    AI_ENABLED,
    AI_PROVIDER,
    AI_TIMEOUT_SECONDS,
    GEMINI_API_KEY,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODEL,
)

# -----------------------------
# Lazy, safe init
# -----------------------------
_CONFIGURED = False
_PRIMARY_MODEL = None
_FALLBACK_MODEL = None


def _init() -> None:
    global _CONFIGURED, _PRIMARY_MODEL, _FALLBACK_MODEL
    if _CONFIGURED:
        return

    # Configure SDK (does not validate key yet)
    try:
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        # Keep going; errors handled during call
        pass

    try:
        _PRIMARY_MODEL = genai.GenerativeModel(GEMINI_PRIMARY_MODEL or "gemini-2.0-flash")
    except Exception:
        _PRIMARY_MODEL = None

    try:
        _FALLBACK_MODEL = genai.GenerativeModel(GEMINI_FALLBACK_MODEL or "gemini-1.5-flash")
    except Exception:
        _FALLBACK_MODEL = None

    _CONFIGURED = True


def _lang_name(lang: str) -> str:
    l = (lang or "").strip().lower()
    if l.startswith("hi"):
        return "Hindi"
    if l.startswith("mr"):
        return "Marathi"
    return "English"


def _build_prompt(payload: Dict[str, Any]) -> str:
    q = (payload.get("question") or "").strip()
    board = (payload.get("board") or "").strip()
    cls = str(payload.get("class_") or payload.get("class") or payload.get("class_level") or "").strip()
    subject = (payload.get("subject") or "").strip()
    chapter = (payload.get("chapter") or "").strip()
    exam_mode = (payload.get("exam_mode") or "").strip()
    answer_mode = (payload.get("answer_mode") or "").strip()
    explain_like = str(payload.get("explain_like") or payload.get("explain_level") or "").strip()
    study_mode = (payload.get("study_mode") or payload.get("mode") or payload.get("source") or "").strip()
    lang = _lang_name(payload.get("language") or "en")

    # Keep prompt short + structured for latency
    system = (
        "You are KnowEasy AI Tutor.
"
        "Rules:
"
        "- Be correct and student-friendly.
"
        "- Use simple language and short paragraphs.
"
        "- If question is ambiguous, ask ONE clarifying question.
"
        "- If user asks for a definition or example, provide it.
"
        "- Do not mention internal tools, tokens, or policies.
"
    )

    context_lines = []
    if cls:
        context_lines.append(f"Class: {cls}")
    if board:
        context_lines.append(f"Board: {board}")
    if subject:
        context_lines.append(f"Subject: {subject}")
    if chapter:
        context_lines.append(f"Chapter: {chapter}")
    if exam_mode:
        context_lines.append(f"Exam focus: {exam_mode}")
    if answer_mode:
        context_lines.append(f"Answer style: {answer_mode}")
    if explain_like:
        context_lines.append(f"Explain like: {explain_like}")
    if study_mode:
        context_lines.append(f"Study mode: {study_mode}")

    context = "\n".join(context_lines) if context_lines else "Context: (not provided)"

    return (
        f"{system}\n"
        f"Reply language: {lang}\n\n"
        f"{context}\n\n"
        f"Student question: {q}\n\n"
        "Answer:"
    )


def _call_model(model, prompt: str, timeout_s: int) -> str:
    # google.generativeai SDK is sync; we approximate timeout by checking elapsed
    t0 = time.perf_counter()
    # A small safety: set generation config conservatively
    try:
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 800,
            },
        )
        # If it took too long, still return what we got (router will log latency)
        _ = (time.perf_counter() - t0)
        text = getattr(resp, "text", None)
        if text is None:
            # Some SDK variants store candidates differently
            try:
                text = resp.candidates[0].content.parts[0].text  # type: ignore
            except Exception:
                text = ""
        return (text or "").strip()
    except Exception:
        return ""


def solve(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Router-compatible solve.

    Input: payload dict from SolveRequest.model_dump()
    Output: dict with `final_answer` at minimum.
    """
    _init()

    # Hard disable switch
    if not AI_ENABLED:
        return {
            "final_answer": "AI is temporarily disabled. Please try again later.",
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["AI_DISABLED"],
            "safe_note": "Try again in a minute.",
        }

    # Provider guardrail (we are Gemini-only in this build)
    if (AI_PROVIDER or "gemini").lower() not in ("gemini", "google", "genai"):
        # Still try Gemini if configured, but flag the mismatch
        provider_flag = "PROVIDER_MISMATCH"
    else:
        provider_flag = None

    q = (payload.get("question") or "").strip()
    if not q:
        return {
            "final_answer": "Please type your question so I can help 😊",
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["NO_QUESTION"],
            "safe_note": "Add the exact doubt (1–2 lines) and I'll answer.",
        }

    if not GEMINI_API_KEY:
        return {
            "final_answer": "AI is not configured on the server (missing GEMINI_API_KEY).",
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["MISSING_API_KEY"],
            "safe_note": "Admin: set GEMINI_API_KEY in Render environment variables.",
        }

    prompt = _build_prompt(payload)

    timeout_s = int(AI_TIMEOUT_SECONDS or 60)
    timeout_s = max(10, min(timeout_s, 120))

    answer = ""
    # Primary model
    if _PRIMARY_MODEL is not None:
        answer = _call_model(_PRIMARY_MODEL, prompt, timeout_s)

    # Fallback model
    if not answer and _FALLBACK_MODEL is not None:
        answer = _call_model(_FALLBACK_MODEL, prompt, timeout_s)

    if not answer:
        return {
            "final_answer": "I couldn't generate an answer right now. Please try again in a few seconds 😊",
            "steps": [],
            "assumptions": [],
            "confidence": 0.2,
            "flags": ["AI_NO_RESPONSE"],
            "safe_note": "If it repeats, refresh once and try again.",
        }

    flags = ["GEMINI"]
    if provider_flag:
        flags.append(provider_flag)

    return {
        "final_answer": answer,
        "steps": [],
        "assumptions": [],
        "confidence": 0.75,
        "flags": flags,
        "safe_note": "If you want, ask for an example or a quick MCQ.",
    }
