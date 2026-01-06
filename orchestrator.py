from __future__ import annotations

from schemas import SolveRequest, SolveResponse
from verifier import basic_verify
from models import get_gemini_client


def build_prompt(req: SolveRequest) -> str:
    # Minimal, exam-safe prompt (Phase-1)
    lines = [
        "You are KnowEasy Engine (Phase-1).",
        "You must be accurate, exam-safe, and concise.",
        "If the question is unclear, ask a single clarifying question.",
        "",
        f"Board: {req.board}",
        f"Class: {req.clazz}",
        f"Subject: {req.subject}",
    ]
    if req.chapter:
        lines.append(f"Chapter: {req.chapter}")
    lines += [
        f"Mode: {req.exam_mode}",
        f"Answer mode: {req.answer_mode}",
        "",
        "Question:",
        req.question.strip(),
        "",
        "Return:",
        "- Final answer",
        "- 3-8 key steps (bullet points) if applicable",
    ]
    return "\n".join(lines)


def solve(req: SolveRequest) -> SolveResponse:
    # Guard rails
    verdict = basic_verify(req.question, req.exam_mode)
    if not verdict.ok:
        return SolveResponse(ok=False, answer=verdict.message, steps=[])

    prompt = build_prompt(req)
    client = get_gemini_client()

    try:
        text = client.generate(prompt)
        if not text:
            return SolveResponse(ok=False, answer="Empty response from model.", steps=[])
        # naive split into answer + steps
        steps = []
        # Extract bullets if present
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(("-", "•")):
                steps.append(s.lstrip("-• ").strip())
        return SolveResponse(
            ok=True,
            answer=text.strip(),
            steps=steps[:12],
            model=client.model,
        )
    except Exception as e:
        return SolveResponse(
            ok=False,
            answer=f"Server error: {e}",
            steps=[],
            model=getattr(client, "model", None),
        )
