from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

# IMPORTANT:
# learning_router imports RequestContext + generate_learning_answer from here.
# Keep these names stable.

from ai_router import generate_json  # type: ignore


@dataclass
class RequestContext:
    # Minimal context needed by learning_router + our routing.
    question: str
    answer_mode: str = "tutor"          # lite|tutor|mastery (frontend may send these)
    language: str = "en"

    # Optional academic context (may be empty / unknown)
    class_level: str = ""
    board: str = ""
    subject: str = ""
    chapter: str = ""
    exam_mode: str = ""
    study_mode: str = ""


def _normalize_mode(mode: str) -> str:
    m = (mode or "").strip().lower()
    if m in ("lite", "luma_lite", "luma lite"):
        return "lite"
    if m in ("tutor", "luma_tutor", "luma tutor"):
        return "tutor"
    if m in ("mastery", "luma_mastery", "luma mastery"):
        return "mastery"
    return "tutor"


def _generate_json_safe(prompt: str, timeout_s: int) -> Dict[str, Any]:
    """Call ai_router.generate_json in a backward-compatible way.

    We previously passed timeout_s, but some ai_router versions expose different kwargs.
    This wrapper tries common variants and finally calls without a timeout kwarg.
    """
    # Try the kwarg we used earlier
    try:
        return generate_json(prompt, timeout_s=timeout_s)  # type: ignore
    except TypeError:
        pass

    # Try other common names
    for kw in ("timeout_seconds", "timeout", "request_timeout", "timeout_sec"):
        try:
            return generate_json(prompt, **{kw: timeout_s})  # type: ignore
        except TypeError:
            continue

    # Final fallback (no timeout kw)
    return generate_json(prompt)  # type: ignore


def solve(
    question: str,
    answer_mode: str = "tutor",
    language: str = "en",
    class_level: str = "",
    board: str = "",
    subject: str = "",
    chapter: str = "",
    exam_mode: str = "",
    study_mode: str = "",
) -> Dict[str, Any]:
    """Main solver used by /v1/ai/answer (router.py).

    Returns:
      {
        ok: bool,
        answer_object: {...},   # Answer-as-Learning-Object schema
        meta: {...}
      }
    """
    t0 = time.time()
    mode = _normalize_mode(answer_mode)

    # Model routing (env-driven so you can tune without code)
    # IMPORTANT: These are MODEL NAMES as expected by your provider wrappers.
    # If a model name is wrong for the provider SDK, ai_router should fallback.
    # Defaults are conservative + cheap.
    default_writer = {
        "lite": os.getenv("WRITER_MODEL_LITE", "gemini-1.5-flash"),
        "tutor": os.getenv("WRITER_MODEL_TUTOR", "claude-3-5-sonnet"),
        "mastery": os.getenv("WRITER_MODEL_MASTERY", "claude-3-5-sonnet"),
    }.get(mode, "claude-3-5-sonnet")

    verifier_model = os.getenv("VERIFIER_MODEL", "gpt-4o-mini")

    # Timeouts: keep within Render free limits. You can raise later.
    timeout_s = int(os.getenv("AI_TIMEOUT_SECONDS", "45"))

    prompt = f"""You are KnowEasy (Luma) — a calm, premium AI teacher for Indian students.

OUTPUT FORMAT:
Return ONLY valid JSON matching this schema:
{{
  "title": string,
  "mode": "{mode}",
  "language": "{language}",
  "sections": [
    {{
      "type": "concept" | "steps" | "example" | "visual" | "mistakes" | "practice" | "exam_footer",
      "heading": string,
      "content_markdown": string
    }}
  ],
  "visuals": [
    {{
      "kind": "diagram" | "flow" | "table" | "graph",
      "title": string,
      "spec": string   // ASCII/mermaid-like spec; NO external links; keep short
    }}
  ],
  "references": [string],
  "meta": {{
    "class_level": "{class_level}",
    "board": "{board}",
    "subject": "{subject}",
    "chapter": "{chapter}",
    "exam_mode": "{exam_mode}",
    "study_mode": "{study_mode}",
    "writer_model": "{default_writer}",
    "verifier_model": "{verifier_model}"
  }}
}}

RULES:
- Be exam-safe and avoid hallucinations. If unsure, state assumption + safest explanation.
- For JEE/NEET/CET/Olympiad tone: include multiple methods + common traps in Mastery.
- Always include at least 1 visual in Tutor/Mastery (ASCII/mermaid spec).
- Keep Lite short (1-3 lines + maybe one tiny visual).
- Use simple, clear English by default. If language != "en", write in that language with English key-term anchors.
QUESTION:
{question}
"""

    try:
        # Writer pass
        data = _generate_json_safe(prompt, timeout_s=timeout_s)

        # Basic sanity: ensure dict
        if not isinstance(data, dict):
            raise ValueError("generate_json did not return a JSON object")

        # Ensure required keys
        data.setdefault("title", "Answer")
        data.setdefault("mode", mode)
        data.setdefault("language", language)
        data.setdefault("sections", [])
        data.setdefault("visuals", [])
        data.setdefault("references", [])
        data.setdefault("meta", {})
        data["meta"] = {**data.get("meta", {}), "writer_model": default_writer, "verifier_model": verifier_model}

        meta = {
            "mode": mode,
            "ms": int((time.time() - t0) * 1000),
        }
        return {"ok": True, "answer_object": data, "meta": meta}
    except Exception as e:
        # Never crash the API. Return a safe error payload.
        return {
            "ok": False,
            "error": "AI_SOLVE_FAILED",
            "message": str(e),
            "answer_object": {
                "title": "We hit a temporary issue",
                "mode": mode,
                "language": language,
                "sections": [
                    {
                        "type": "concept",
                        "heading": "Try again",
                        "content_markdown": "The server could not generate the answer right now. Please retry in 10–20 seconds. If it keeps failing, share your Render logs.",
                    }
                ],
                "visuals": [],
                "references": [],
                "meta": {"writer_model": default_writer, "verifier_model": verifier_model},
            },
            "meta": {"mode": mode, "ms": int((time.time() - t0) * 1000)},
        }


def generate_learning_answer(ctx: RequestContext) -> Dict[str, Any]:
    """Compatibility wrapper used by learning_router (/learning/answer)."""
    return solve(
        question=ctx.question,
        answer_mode=ctx.answer_mode,
        language=ctx.language,
        class_level=ctx.class_level,
        board=ctx.board,
        subject=ctx.subject,
        chapter=ctx.chapter,
        exam_mode=ctx.exam_mode,
        study_mode=ctx.study_mode,
    )
