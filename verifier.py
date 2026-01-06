from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VerifyVerdict:
    ok: bool
    message: str = ""


def basic_verify(question: str, exam_mode: str = "BOARD") -> VerifyVerdict:
    q = (question or "").strip()
    if not q:
        return VerifyVerdict(ok=False, message="Please type a question.")
    # Phase-1 minimal safety: block obvious harmful content (keep simple)
    lowered = q.lower()
    blocked = ["how to make a bomb", "buy drugs", "kill myself"]
    if any(b in lowered for b in blocked):
        return VerifyVerdict(ok=False, message="Sorry, I can't help with that.")
    return VerifyVerdict(ok=True)
