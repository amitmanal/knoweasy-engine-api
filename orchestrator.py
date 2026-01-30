"""orchestrator.py — KnowEasy Academic Engine v3 (One Brain)

This replaces legacy quick/deep/exam routing with the locked system:
- Two-tier Academic Engine:
  - Foundation Builder (Classes 5–10): syllabus/age-safe ceiling
  - Competitive Mentor (11–12 + JEE/NEET/CET/Olympiad): deep exam mentor (no short answers)
- 3 Modes: lite / tutor / mastery (frontend sends answer_mode)
- Multi-model: Gemini as backbone + optional Claude writer + OpenAI verifier for hard/extreme

Output contract:
- Returns a premium object containing `sections` (for PremiumRenderer) and
  minimal top-level fields (`title`, `why_this_matters`, `providers_used`, `meta`).

No external side effects here (no DB writes).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from config import (
    GEMINI_API_KEY,
    GEMINI_PRIMARY_MODEL,
    GEMINI_FALLBACK_MODELS,
    OPENAI_API_KEY,
    OPENAI_VERIFIER_MODEL,
    OPENAI_MODEL,
    CLAUDE_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_WRITER_MODEL,
    AI_TIMEOUT_SECONDS,
    MAX_CHARS_ANSWER,
)

logger = logging.getLogger("knoweasy.orchestrator")


# -----------------------------
# Enums / Context
# -----------------------------

class Mode(str, Enum):
    LITE = "lite"
    TUTOR = "tutor"
    MASTERY = "mastery"


class AcademicProfile(str, Enum):
    FOUNDATION_BUILDER = "foundation_builder"
    COMPETITIVE_MENTOR = "competitive_mentor"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXTREME = "extreme"


@dataclass
class RequestContext:
    request_id: str
    question: str
    board: str = ""
    class_level: str = ""
    subject: str = ""
    chapter: str = ""
    exam_mode: str = ""          # JEE/NEET/CET/OLYMPIAD/BOARD etc
    language: str = "en"
    study_mode: str = "chat"
    answer_mode: str = "tutor"   # lite|tutor|mastery (frontend)
    user_tier: str = "free"

    def mode(self) -> Mode:
        v = (self.answer_mode or "tutor").strip().lower()
        if v in {"luma_lite", "lite"}:
            return Mode.LITE
        if v in {"luma_mastery", "mastery", "exam"}:
            return Mode.MASTERY
        return Mode.TUTOR

    def grade_int(self) -> Optional[int]:
        try:
            g = int(str(self.class_level).strip())
            if 1 <= g <= 20:
                return g
        except Exception:
            return None
        return None


# -----------------------------
# Helpers
# -----------------------------

_HARD_CUES = [
    "derive", "prove", "mechanism", "multi-step", "calculate", "integral", "differential",
    "rank", "assertion", "reason", "matrix", "electrochem", "thermo", "rotation", "rbd", "kinematics",
    "eigen", "laplace", "stereochemistry", "sn1", "sn2", "e1", "e2"
]
_EXTREME_CUES = ["olympiad", "irodov", "inequality", "functional equation", "non-trivial", "contest", "tricky"]

def select_profile(ctx: RequestContext) -> AcademicProfile:
    exam = (ctx.exam_mode or ctx.board or "").strip().lower()
    if exam in {"jee", "neet", "cet", "olympiad"}:
        return AcademicProfile.COMPETITIVE_MENTOR
    g = ctx.grade_int()
    if g is not None and g >= 11:
        return AcademicProfile.COMPETITIVE_MENTOR
    return AcademicProfile.FOUNDATION_BUILDER

def estimate_difficulty(question: str, profile: AcademicProfile) -> Difficulty:
    q = (question or "").lower()
    if profile == AcademicProfile.COMPETITIVE_MENTOR:
        if any(c in q for c in _EXTREME_CUES):
            return Difficulty.EXTREME
        if any(c in q for c in _HARD_CUES) or len(q) > 180:
            return Difficulty.HARD
        return Difficulty.MEDIUM
    # foundation
    if len(q) > 220:
        return Difficulty.MEDIUM
    return Difficulty.EASY

def _json_extract(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("Model did not return JSON.")
        return json.loads(m.group(0))


# -----------------------------
# Prompting (sections schema)
# -----------------------------

def _schema_hint() -> str:
    return (
        "Return ONLY valid JSON (no markdown).\n"
        "Schema:\n"
        "{\n"
        "  \"title\": string,\n"
        "  \"why_this_matters\": string,\n"
        "  \"sections\": [\n"
        "    {\n"
        "      \"type\": \"header\"|\"definition\"|\"explanation\"|\"steps\"|\"diagram\"|\"practice\"|\"table\"|\"tips\"|\"warning\"|\"answer\",\n"
        "      \"title\": string,\n"
        "      \"content\": string,\n"
        "      \"steps\": [string],\n"
        "      \"diagram\": {\"format\": \"mermaid\"|\"text\", \"code\": string},\n"
        "      \"items\": [string],\n"
        "      \"questions\": [ { \"q\": string, \"options\": [string], \"answer\": string, \"why\": string } ]\n"
        "    }\n"
        "  ],\n"
        "  \"follow_up_chips\": [string],\n"
        "  \"common_mistakes\": [string],\n"
        "  \"exam_relevance_footer\": string\n"
        "}\n"
        "Rules: Keep it exam-safe, structured, calm, and very clear."
    )

def _system_prompt(profile: AcademicProfile, mode: Mode, ctx: RequestContext) -> str:
    # Competitive: NO short answers (even in lite)
    competitive_no_short = (profile == AcademicProfile.COMPETITIVE_MENTOR)

    if mode == Mode.LITE:
        if competitive_no_short:
            mode_rule = (
                "Mode=Luma Lite (Competitive): FAST but not short. Include: final result/formula, 3–6 bullet steps, "
                "and one mini diagram only if it improves clarity."
            )
        else:
            mode_rule = "Mode=Luma Lite: short and clear: definition/formula + 3 key points."
    elif mode == Mode.TUTOR:
        mode_rule = "Mode=Luma Tutor: teach step-by-step with exactly 1 strong visual thinking tool by default."
    else:
        mode_rule = (
            "Mode=Luma Mastery: deep exam mentor. Multiple methods if possible, trap alerts, "
            "and 5 practice questions (mix MCQ + PYQ-style)."
        )

    ceiling = (
        "Ceiling: Foundation Builder — stay within syllabus; avoid going beyond 1–2 grades ahead."
        if profile == AcademicProfile.FOUNDATION_BUILDER
        else "Ceiling: Competitive Mentor — full exam depth (JEE/NEET/CET/Olympiad relevant), but stay focused."
    )

    lang = (ctx.language or "en").lower()
    lang_rule = "Language: English." if lang == "en" else (
        "Language: Use the user's language, but keep key scientific terms in English in brackets once."
    )

    return f"""You are KnowEasy — a calm, premium AI Teacher for India.
Profile: {profile.value}
{ceiling}
{mode_rule}
{lang_rule}

Visual rule:
- Prefer Mermaid diagrams for biology/chemistry processes, flowcharts, cycles, and labeled boxes.
- Keep diagrams simple and readable.

Output rule:
{_schema_hint()}
""".strip()

def _user_prompt(ctx: RequestContext) -> str:
    payload = {
        "question": ctx.question,
        "board": ctx.board,
        "class_level": ctx.class_level,
        "subject": ctx.subject,
        "chapter": ctx.chapter,
        "exam_mode": ctx.exam_mode,
        "language": ctx.language,
    }
    return json.dumps(payload, ensure_ascii=False)


# -----------------------------
# Providers
# -----------------------------

async def _gemini_generate(model_name: str, system: str, user: str, timeout_s: int) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing.")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system)

    def _call():
        resp = model.generate_content(
            user,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 4096,
            },
        )
        return (resp.text or "").strip()

    return await asyncio.wait_for(asyncio.to_thread(_call), timeout=timeout_s)

async def _openai_json(model: str, system: str, user: str, timeout_s: int) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing.")
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    # response_format json_object to reduce junk
    coro = client.chat.completions.create(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    resp = await asyncio.wait_for(coro, timeout=timeout_s)
    return (resp.choices[0].message.content or "").strip()

async def _claude_json(model: str, system: str, user: str, timeout_s: int) -> str:
    if not CLAUDE_API_KEY:
        raise RuntimeError("CLAUDE_API_KEY missing.")
    client = AsyncAnthropic(api_key=CLAUDE_API_KEY)
    coro = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    resp = await asyncio.wait_for(coro, timeout=timeout_s)
    # anthropic SDK returns list content blocks
    txt = ""
    for b in (resp.content or []):
        if getattr(b, "type", None) == "text":
            txt += b.text
    return (txt or "").strip()


# -----------------------------
# Verification loop (OpenAI)
# -----------------------------

def _checker_system() -> str:
    return (
        "You are a strict exam-safety verifier.\n"
        "Check: wrong facts, missing conditions, wrong equations, unit mistakes, confusing wording, unsafe claims.\n"
        "Return ONLY JSON: { \"ok\": boolean, \"issues\": [string], \"fix_instructions\": [string] }"
    )

def _checker_user(draft_json: Dict[str, Any], ctx: RequestContext) -> str:
    return json.dumps(
        {
            "draft": draft_json,
            "context": {
                "subject": ctx.subject,
                "class_level": ctx.class_level,
                "exam_mode": ctx.exam_mode,
                "board": ctx.board,
                "mode": ctx.answer_mode,
            },
            "instruction": "Verify correctness and exam-safety. Be strict.",
        },
        ensure_ascii=False,
    )


# -----------------------------
# Plan / Routing
# -----------------------------

def _timeout_for(difficulty: Difficulty) -> int:
    base = int(AI_TIMEOUT_SECONDS or 25)
    if difficulty == Difficulty.EASY:
        return min(base, 20)
    if difficulty == Difficulty.MEDIUM:
        return max(base, 25)
    if difficulty == Difficulty.HARD:
        return max(base, 35)
    return max(base, 45)

def _gemini_model_for(mode: Mode, difficulty: Difficulty) -> str:
    # Prefer 2.5 Flash-Lite for ultra fast, 2.5 Flash for most, 2.5 Pro for hard/mastery
    if mode == Mode.LITE and difficulty in {Difficulty.EASY, Difficulty.MEDIUM}:
        return os.getenv("GEMINI_LITE_MODEL", "gemini-2.5-flash-lite")
    if mode == Mode.MASTERY or difficulty in {Difficulty.HARD, Difficulty.EXTREME}:
        return os.getenv("GEMINI_MASTERY_MODEL", "gemini-2.5-pro")
    return GEMINI_PRIMARY_MODEL or "gemini-2.5-flash"

def _should_verify(profile: AcademicProfile, mode: Mode, difficulty: Difficulty) -> bool:
    if profile != AcademicProfile.COMPETITIVE_MENTOR:
        return False
    if difficulty in {Difficulty.HARD, Difficulty.EXTREME}:
        return True
    if mode == Mode.MASTERY:
        return True
    return False

async def _generate(ctx: RequestContext) -> Dict[str, Any]:
    rid = ctx.request_id or str(uuid.uuid4())
    profile = select_profile(ctx)
    mode = ctx.mode()
    difficulty = estimate_difficulty(ctx.question, profile)
    timeout_s = _timeout_for(difficulty)

    system = _system_prompt(profile, mode, ctx)
    user = _user_prompt(ctx)

    providers_used: List[str] = []
    draft_text: str = ""

    # Writer routing
    try:
        if difficulty == Difficulty.EXTREME and profile == AcademicProfile.COMPETITIVE_MENTOR and CLAUDE_API_KEY:
            # Claude writer for extreme (deep reasoning), then Gemini can be used later if needed
            draft_text = await _claude_json(CLAUDE_WRITER_MODEL or CLAUDE_MODEL or "claude-sonnet-4-5", system, user, timeout_s)
            providers_used.append("claude")
        else:
            model = _gemini_model_for(mode, difficulty)
            draft_text = await _gemini_generate(model, system, user, timeout_s)
            providers_used.append("gemini")
    except Exception as e:
        logger.exception("Writer failed: %s", e)
        # Fallback attempt: Gemini fallbacks
        for m in (GEMINI_FALLBACK_MODELS or []):
            try:
                draft_text = await _gemini_generate(m, system, user, timeout_s)
                providers_used.append("gemini")
                break
            except Exception:
                continue

    if not draft_text:
        # deterministic fallback
        return {
            "title": "Unable to generate right now",
            "why_this_matters": "Network/provider issue — here’s a safe fallback explanation.",
            "sections": [
                {"type": "definition", "title": "What you can do", "content": "Please try again in a moment. If the issue persists, contact support."}
            ],
            "providers_used": providers_used,
            "meta": {
                "request_id": rid,
                "mode": mode.value,
                "profile": profile.value,
                "difficulty": difficulty.value,
                "verified": False,
            }
        }

    draft = _json_extract(draft_text)

    # Verify if needed
    verified = False
    verification_notes: List[str] = []
    if _should_verify(profile, mode, difficulty) and OPENAI_API_KEY:
        try:
            chk_text = await _openai_json(
                OPENAI_VERIFIER_MODEL or OPENAI_MODEL or "o3-mini",
                _checker_system(),
                _checker_user(draft, ctx),
                min(timeout_s, 35),
            )
            chk = _json_extract(chk_text)
            if chk.get("ok") is True:
                verified = True
                providers_used.append("openai")
            else:
                verification_notes = (chk.get("issues") or [])[:8]
                fix = (chk.get("fix_instructions") or [])[:8]
                # One repair pass with same writer (Gemini preferred for formatting)
                repair_user = json.dumps(
                    {"draft": draft, "fix_instructions": fix, "instruction": "Regenerate corrected JSON only."},
                    ensure_ascii=False,
                )
                # Use Gemini Pro-ish for repair
                repair_model = os.getenv("GEMINI_REPAIR_MODEL", "gemini-2.5-flash")
                repaired_text = await _gemini_generate(repair_model, system, repair_user, timeout_s)
                providers_used.append("openai")
                providers_used.append("gemini")
                draft = _json_extract(repaired_text)
                verified = True  # verified-after-fix (best effort)
        except Exception as e:
            logger.warning("Verifier failed: %s", str(e)[:200])

    # Stamp meta & normalize for frontend
    out: Dict[str, Any] = dict(draft)
    out.setdefault("sections", [])
    out["providers_used"] = list(dict.fromkeys(providers_used))
    out["meta"] = {
        "request_id": rid,
        "mode": mode.value,
        "profile": profile.value,
        "difficulty": difficulty.value,
        "verified": bool(verified),
        "verification_notes": verification_notes,
        "models": {
            "gemini_primary": GEMINI_PRIMARY_MODEL,
            "openai_verifier": OPENAI_VERIFIER_MODEL or OPENAI_MODEL,
            "claude_writer": CLAUDE_WRITER_MODEL or CLAUDE_MODEL,
        },
    }
    return out


def generate_learning_answer(ctx: RequestContext) -> Dict[str, Any]:
    """Sync wrapper used by FastAPI routers."""
    try:
        return asyncio.run(_generate(ctx))
    except RuntimeError:
        # If we're already in an event loop (unlikely for sync FastAPI route), use a new loop in thread
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_generate(ctx))
        finally:
            loop.close()

# -----------------------------
# Public Orchestrator API (async)
# -----------------------------

async def run_orchestrator(
    *,
    question: str,
    context: dict | None = None,
    answer_mode: str = "tutor",
    user_tier: str | None = None,
    **kwargs,
) -> Dict[str, Any]:
    """Main orchestrator entrypoint expected by router.py.

    Returns a dict that includes premium fields (title/sections/why_this_matters)
    AND a compatibility `answer` string for older consumers.
    """
    ctx = RequestContext(
        question=str(question or "").strip(),
        board=str((context or {}).get("board") or ""),
        class_level=int((context or {}).get("class_level") or (context or {}).get("class") or 11),
        exam_goal=str((context or {}).get("exam_goal") or (context or {}).get("exam") or ""),
        language=str((context or {}).get("language") or "en"),
        answer_mode=str(answer_mode or "tutor"),
        user_tier=str(user_tier or (context or {}).get("user_tier") or ""),
        luma_context=(context or {}).get("luma_context") or None,
        request_id=str((context or {}).get("request_id") or ""),
    )
    out = await _generate(ctx)

    # Compatibility: provide a readable plain-text answer string (used by some UI paths).
    if isinstance(out, dict) and not out.get("answer"):
        parts: list[str] = []
        if out.get("title"):
            parts.append(str(out["title"]))
        for sec in (out.get("sections") or []):
            if not isinstance(sec, dict):
                continue
            t = sec.get("title")
            c = sec.get("content")
            if t:
                parts.append(str(t))
            if c:
                parts.append(str(c))
        if out.get("why_this_matters"):
            parts.append("Why this matters")
            parts.append(str(out["why_this_matters"]))
        out["answer"] = "\n\n".join([p for p in parts if str(p).strip()])[:MAX_CHARS_ANSWER]

    return out

# --- Backward compatibility for router.py ---

async def solve(
    question: str,
    *,
    context: dict | None = None,
    answer_mode: str = "tutor",
    **kwargs
):
    """
    Compatibility wrapper.
    Router expects `solve()`, but new engine uses run_orchestrator().
    """
    return await run_orchestrator(
        question=question,
        context=context or {},
        answer_mode=answer_mode,
        **kwargs
    )


def get_orchestrator_stats():
    return {
        "engine": "one-brain",
        "status": "ok"
    }