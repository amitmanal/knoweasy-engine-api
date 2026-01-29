
"""orchestrator.py — KnowEasy One-Brain Orchestrator (Phase-4)

Fixes:
- Supports ONLY 3 modes: lite / tutor / mastery (front-end compatible)
- Two-tier Academic Engine:
  - Foundation Builder (Classes 5–10): ceiling enforced (1–2 grades ahead)
  - Competitive Mentor (11–12 or JEE/NEET/CET/Olympiad): deep answers, NO short answers
- Keeps backward compatible async `solve()` for router.py
- Optional OpenAI verification pass for hard/mastery competitive (one repair max)

This file is designed to boot on Render reliably (no import loops).
"""

from __future__ import annotations

import json
import os
import time
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from ai_router import generate_json, ProviderError
from config import (
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODELS,
    AI_TIMEOUT_SECONDS,
    OPENAI_API_KEY,
)

logger = logging.getLogger("knoweasy.orchestrator")


# -----------------------------
# Helpers: profile + ceilings
# -----------------------------

def _norm(s: Any) -> str:
    return ("" if s is None else str(s)).strip()

def _detect_profile(ctx: Dict[str, Any]) -> str:
    exam = _norm(ctx.get("exam_mode") or ctx.get("board_or_exam")).upper()
    klass = _norm(ctx.get("class") or ctx.get("class_level"))
    try:
        k = int("".join([c for c in klass if c.isdigit()]) or "0")
    except Exception:
        k = 0

    if exam in {"JEE", "NEET", "CET", "OLYMPIAD"}:
        return "competitive_mentor"
    if k >= 11:
        return "competitive_mentor"
    return "foundation_builder"

def _normalize_mode(answer_mode: str) -> str:
    m = _norm(answer_mode).lower()
    # Accept legacy values too
    if m in {"quick", "one_liner", "hint_only"}:
        return "lite"
    if m in {"deep", "step_by_step", "tutor"}:
        return "tutor"
    if m in {"exam", "mastery"}:
        return "mastery"
    if m in {"lite", "tutor", "mastery"}:
        return m
    return "tutor"


def _build_writer_prompt(question: str, ctx: Dict[str, Any], mode: str, profile: str) -> str:
    """Prompt the writer model to return JSON with an 'answer' string."""
    subject = _norm(ctx.get("subject"))
    board = _norm(ctx.get("board"))
    exam = _norm(ctx.get("exam_mode") or ctx.get("board_or_exam"))
    klass = _norm(ctx.get("class") or ctx.get("class_level"))
    lang = (_norm(ctx.get("language")) or "en").lower()

    ceiling_note = ""
    if profile == "foundation_builder":
        ceiling_note = (
            "You MUST stay syllabus-safe for Classes 5–10. "
            "Do NOT introduce Olympiad/JEE depth. Max 1–2 grades ahead even in mastery."
        )
    else:
        ceiling_note = (
            "You are teaching for JEE/NEET/CET/Olympiad. Depth is allowed. "
            "Do NOT be short. Provide full reasoning and exam-safe steps."
        )

    mode_rules = {
        "lite": (
            "Fast clarity. For foundation: 2–5 short lines. "
            "For competitive: NOT short — give final result/formula + 3–6 bullet steps + key idea."
        ),
        "tutor": (
            "Teach step-by-step like a great teacher. Use headings and bullets. "
            "Include key definitions, steps, and 1–2 exam tips."
        ),
        "mastery": (
            "Deep exam mentor. Provide: concept foundation, full derivation/logic, alternative method if applicable, "
            "common traps, and 3–5 practice questions at end."
        ),
    }[mode]

    # Force JSON output so downstream is stable
    return json.dumps({
        "instruction": (
            "Return ONLY valid JSON. No markdown. "
            "Schema: {answer: string, confidence: number(0..1), key_points: [string], flags:[string]}."
        ),
        "context": {
            "profile": profile,
            "mode": mode,
            "board": board,
            "class": klass,
            "exam": exam,
            "subject": subject,
            "language": lang,
        },
        "rules": {
            "ceiling": ceiling_note,
            "mode_rules": mode_rules,
            "tone": "calm, premium, exam-safe",
            "format": "structured headings + bullets; no fluff; no fake citations",
        },
        "question": question
    }, ensure_ascii=False)


# -----------------------------
# Optional verification (OpenAI)
# -----------------------------

def _openai_verify(draft_answer: str, question: str, ctx: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """Return (ok, issues, fix_instructions). Strict JSON response."""
    if not OPENAI_API_KEY:
        return True, [], []

    model = os.getenv("OPENAI_VERIFIER_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    timeout_s = int(os.getenv("OPENAI_VERIFY_TIMEOUT", "18"))

    system = "You are a strict verifier for exam answers. Check correctness, missing steps, equation/unit errors, and misleading claims. Return ONLY JSON: {ok:boolean, issues:[string], fix_instructions:[string]}"
    payload = {
        "model": model,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({
                "question": question,
                "draft_answer": draft_answer,
                "context": {
                    "exam_mode": ctx.get("exam_mode"),
                    "class_level": ctx.get("class") or ctx.get("class_level"),
                    "subject": ctx.get("subject"),
                }
            }, ensure_ascii=False)}
        ]
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
        chk = json.loads(content)
        ok = bool(chk.get("ok", False))
        issues = list(chk.get("issues") or [])
        fixes = list(chk.get("fix_instructions") or [])
        return ok, issues[:12], fixes[:12]
    except Exception as e:
        # If verifier fails, do not block user; just skip
        logger.warning(f"Verifier skipped due to error: {e}")
        return True, [], []


# -----------------------------
# Public API: solve()
# -----------------------------

_STATS = {
    "requests": 0,
    "failures": 0,
    "last_error": None,
    "last_provider": None,
}

async def solve(question: str, context: Dict[str, Any], user_tier: str = "free") -> Dict[str, Any]:
    """Backwards compatible entry used by router.py (async)."""
    t0 = time.time()
    _STATS["requests"] += 1

    ctx = context or {}
    profile = _detect_profile(ctx)
    mode = _normalize_mode(ctx.get("answer_mode") or ctx.get("mode") or "tutor")

    # Writer prompt
    prompt = _build_writer_prompt(question, ctx, mode, profile)

    # Decide if we run verifier:
    difficulty = _norm(ctx.get("difficulty")).lower()
    is_competitive = (profile == "competitive_mentor")
    use_verifier = (is_competitive and mode == "mastery") or (difficulty in {"hard", "extreme"})

    providers_used: List[str] = []
    ai_strategy = "gemini_only"

    try:
        # 1) Primary write (uses ai_router provider order; default Gemini)
        out = generate_json(prompt)
        providers_used.append(out.get("provider") or os.getenv("AI_PROVIDER", "gemini"))
        ai_strategy = out.get("strategy") or ai_strategy

        answer = _norm(out.get("answer"))
        confidence = float(out.get("confidence") or 0.7)

        # 2) Verify + repair once (optional)
        verification_notes: List[str] = []
        if use_verifier and answer:
            ok, issues, fixes = _openai_verify(answer, question, ctx)
            if not ok and fixes:
                verification_notes.extend(issues)
                repair_prompt = json.dumps({
                    "instruction": "Regenerate a corrected answer. Return ONLY JSON {answer:string, confidence:number, key_points:[string], flags:[string]}",
                    "question": question,
                    "draft_answer": answer,
                    "fix_instructions": fixes,
                    "context": {"profile": profile, "mode": mode, "exam_mode": ctx.get("exam_mode"), "subject": ctx.get("subject")}
                }, ensure_ascii=False)
                out2 = generate_json(repair_prompt)
                providers_used.append(out2.get("provider") or "unknown")
                answer = _norm(out2.get("answer")) or answer
                confidence = float(out2.get("confidence") or confidence)

        dt = time.time() - t0
        _STATS["last_provider"] = providers_used[-1] if providers_used else None

        flags = list(out.get("flags") or [])
        if profile == "competitive_mentor":
            flags.append("COMPETITIVE")
        else:
            flags.append("FOUNDATION")

        return {
            "success": True,
            "answer": answer,
            "confidence": max(0.05, min(0.99, confidence)),
            "confidence_label": "high" if confidence >= 0.8 else "medium" if confidence >= 0.55 else "low",
            "ai_strategy": ai_strategy,
            "providers_used": providers_used[:4],
            "latency_ms": int(dt * 1000),
            "profile": profile,
            "mode": mode,
            "verification_notes": verification_notes[:8],
        }

    except ProviderError as e:
        _STATS["failures"] += 1
        _STATS["last_error"] = str(e)
        logger.exception("ProviderError in solve()", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "answer": "Sorry, I couldn't reach the AI provider. Please try again.",
        }
    except Exception as e:
        _STATS["failures"] += 1
        _STATS["last_error"] = str(e)
        logger.exception("Unexpected error in solve()", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "answer": "Sorry, something went wrong while solving. Please try again.",
        }


def get_orchestrator_stats() -> Dict[str, Any]:
    return dict(_STATS)
