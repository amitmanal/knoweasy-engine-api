"""knoweasy-engine-api orchestrator (Phase-1, production-stable)

This module is the single source of truth for how `/solve` turns a request
payload into a tutor-style answer.

Why this file exists:
- `router.py` calls `solve(payload)` from this module.
- Therefore `solve` MUST be synchronous and MUST accept a dict payload.
- The previous async/multi-provider orchestrator caused production to return
  the fallback message because the router called an async function without
  awaiting it.

This implementation keeps the system stable:
- Uses `ai_router.generate_json()` which already supports Gemini (default)
  and is future-ready for OpenAI/Claude.
- Produces a strict, UI-friendly response shape:
  {final_answer, steps, assumptions, confidence, flags, safe_note}
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ai_router import generate_json

logger = logging.getLogger("knoweasy.orchestrator")


def _coerce_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _normalize_out(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize model JSON into the API contract expected by frontends."""
    if not isinstance(raw, dict):
        raise RuntimeError("AI returned non-dict JSON")

    final_answer = (
        raw.get("final_answer")
        or raw.get("answer")
        or raw.get("final")
        or raw.get("response")
        or raw.get("text")
    )
    final_answer = _safe_str(final_answer).strip()

    steps = raw.get("steps") or raw.get("key_steps") or raw.get("work") or []
    assumptions = raw.get("assumptions") or raw.get("notes") or []
    confidence = raw.get("confidence")

    try:
        confidence_f = float(confidence) if confidence is not None else 0.6
    except Exception:
        confidence_f = 0.6
    # clamp
    if confidence_f < 0:
        confidence_f = 0.0
    if confidence_f > 1:
        confidence_f = 1.0

    out: Dict[str, Any] = {
        "final_answer": final_answer,
        "steps": [
            _safe_str(s).strip()
            for s in _coerce_list(steps)
            if _safe_str(s).strip()
        ][:12],
        "assumptions": [
            _safe_str(a).strip()
            for a in _coerce_list(assumptions)
            if _safe_str(a).strip()
        ][:8],
        "confidence": confidence_f,
        "flags": [],
        "safe_note": raw.get("safe_note")
        or raw.get("note")
        or "Try adding chapter/topic or any given options/conditions.",
    }

    if not out["final_answer"]:
        raise RuntimeError("AI JSON missing final_answer")

    return out


def _build_prompt(payload: Dict[str, Any]) -> str:
    """Create a single prompt that always returns strict JSON."""
    q = _safe_str(payload.get("question") or payload.get("q")).strip()
    if not q:
        raise ValueError("Missing question")

    board = _safe_str(payload.get("board")).strip()
    klass = _safe_str(payload.get("class_") or payload.get("class") or payload.get("klass") or payload.get("class_level")).strip()
    subject = _safe_str(payload.get("subject")).strip()
    chapter = _safe_str(payload.get("chapter")).strip()
    language = (_safe_str(payload.get("language")) or "en").strip() or "en"
    study_mode = (_safe_str(payload.get("study_mode")) or "chat").strip() or "chat"
    mode = (_safe_str(payload.get("mode")) or "").strip()
    answer_mode = (_safe_str(payload.get("answer_mode")) or "").strip()
    exam_mode = (_safe_str(payload.get("exam_mode")) or "").strip()
    explain_like = (_safe_str(payload.get("explain_like")) or "").strip()
    assist_level = (_safe_str(payload.get("assist_level")) or "").strip()

    ctx = payload.get("context")
    if not isinstance(ctx, dict):
        ctx = {}

    # Keep prompt short and stable; avoid leaking long lesson text.
    ctx_min = {
        "section": _safe_str(ctx.get("section"))[:120],
        "card_type": _safe_str(ctx.get("card_type"))[:120],
        "visible_text": _safe_str(ctx.get("visible_text"))[:900],
        "anchor_example": _safe_str(ctx.get("anchor_example"))[:240],
    }

    # Output contract must be stable across the entire product.
    schema = {
        "final_answer": "string (student-friendly answer)",
        "steps": ["string"],
        "assumptions": ["string"],
        "confidence": "number 0..1",
        "safe_note": "string",
    }

    # Tutor instructions: keep it correct + short.
    style = (
        "You are KnowEasy Tutor. Answer for Indian school students. "
        "Be clear, correct, and concise. Avoid fluff. "
        "If question is too vague, ask 1 clarifying question and give a best-effort short answer."
    )

    lang_hint = (
        "Respond in English." if language.lower().startswith("en") else
        "Respond in Hindi (हिन्दी)." if language.lower().startswith("hi") else
        "Respond in Marathi (मराठी)." if language.lower().startswith("mr") else
        f"Respond in language='{language}'."
    )

    mode_hint = ""
    if study_mode == "luma":
        mode_hint = (
            "This is Luma Focused Assist inside a lesson. "
            "Use the given lesson context if helpful. "
            "Keep the answer under 8 lines unless steps are necessary."
        )

    meta = {
        "board": board,
        "class": klass,
        "subject": subject,
        "chapter": chapter,
        "study_mode": study_mode,
        "mode": mode,
        "answer_mode": answer_mode,
        "exam_mode": exam_mode,
        "explain_like": explain_like,
        "assist_level": assist_level,
    }

    prompt_obj = {
        "instructions": {
            "style": style,
            "language": lang_hint,
            "mode": mode_hint,
            "must": [
                "Return ONLY valid JSON.",
                "Do NOT include markdown.",
                "Do NOT include any keys other than the schema keys.",
            ],
            "schema": schema,
        },
        "context": {k: v for k, v in meta.items() if v},
        "lesson_context": {k: v for k, v in ctx_min.items() if v},
        "question": q,
    }

    # Many models behave better when the JSON prompt is inside code-free text.
    return "Return ONLY JSON for this object:\n" + json.dumps(prompt_obj, ensure_ascii=False)


def solve(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Main entrypoint used by router.py.

    Raises on failure so router can return a proper 5xx with meta.error.
    """
    if not isinstance(payload, dict):
        raise TypeError("solve(payload) expects a dict")

    prompt = _build_prompt(payload)
    logger.info(
        "[solve] q_len=%s board=%s class=%s subject=%s chapter=%s study_mode=%s",
        len(_safe_str(payload.get("question") or "")),
        _safe_str(payload.get("board"))[:20],
        _safe_str(payload.get("class") or payload.get("class_") or payload.get("klass"))[:10],
        _safe_str(payload.get("subject"))[:20],
        _safe_str(payload.get("chapter"))[:24],
        _safe_str(payload.get("study_mode"))[:10],
    )

    raw = generate_json(prompt)
    out = _normalize_out(raw)
    return out
