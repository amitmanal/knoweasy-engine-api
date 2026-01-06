from __future__ import annotations
from typing import Any, Dict, List

from models import GeminiClient
from schemas import SolveRequest, SolveResponse
from verifier import basic_verify

_SYSTEM_RULES = """You are Luma from KnowEasy.
Return ONLY valid JSON with keys:
final_answer (string),
steps (array of strings),
assumptions (array of strings),
confidence (number 0..1),
safe_note (string or null).
No extra text. No markdown.
"""

def _build_prompt(req: SolveRequest) -> str:
    return f"""{_SYSTEM_RULES}

Context:
- Class: {req.clazz}
- Board: {req.board}
- Subject: {req.subject}
- Chapter: {req.chapter or "N/A"}
- Exam mode: {req.exam_mode}
- Language: {req.language}
- Answer mode: {req.answer_mode}

User question:
{req.question}

Now return JSON only.
"""

def _normalize_list(x: Any) -> List[str]:
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    if isinstance(x, str) and x.strip():
        return [x.strip()]
    return []

def _clamp01(v: Any, default: float = 0.5) -> float:
    try:
        f = float(v)
    except Exception:
        return default
    if f < 0: return 0.0
    if f > 1: return 1.0
    return f

async def solve(req: SolveRequest) -> SolveResponse:
    client = GeminiClient()

    prompt = _build_prompt(req)
    data: Dict[str, Any] = client.generate_json(prompt) or {}

    final_answer = str(data.get("final_answer", "")).strip()
    steps = _normalize_list(data.get("steps"))
    assumptions = _normalize_list(data.get("assumptions"))
    confidence = _clamp01(data.get("confidence", 0.6), default=0.6)
    safe_note = data.get("safe_note", None)
    safe_note = str(safe_note).strip() if safe_note not in (None, "") else None

    # Verification
    adj, flags, verify_assumptions = basic_verify(req.question, final_answer, steps)
    confidence = _clamp01(confidence + adj, default=0.5)
    assumptions.extend([a for a in verify_assumptions if a not in assumptions])

    # Fallback if model returned nothing
    if not final_answer:
        flags = list(set(flags + ["MODEL_EMPTY_OUTPUT"]))
        final_answer = "Sorry, I could not generate an answer right now. Please try again."
        confidence = min(confidence, 0.4)

    return SolveResponse(
        final_answer=final_answer,
        steps=steps,
        assumptions=assumptions,
        confidence=confidence,
        flags=sorted(list(set(flags))),
        safe_note=safe_note,
        meta={
            "engine": "knoweasy-orchestrator-phase1",
            "model": "gemini-1.5-flash",
        },
    )
