# src/iupac_v1.py
# KnowEasy Engine — IUPAC v1 compatibility layer
#
# Unit tests expect:
#   ans.final_answer.lower()
# so we must return an object with attribute .final_answer (NOT a dict).
#
# This file delegates to src.iupac_naming_v1 (your actual implementation)
# and wraps its dict output into a dataclass.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class IUPACAnswer:
    final_answer: str
    answer: str = ""
    steps: list[str] = None
    error: Optional[str] = None
    topic: str = "IUPAC_V1"


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def answer_iupac_question(question: str, *args: Any, **kwargs: Any) -> IUPACAnswer:
    """
    Primary entrypoint used by tests.
    Always returns IUPACAnswer (attribute-based), never dict.
    """
    try:
        from src import iupac_naming_v1 as impl
    except Exception as e:
        return IUPACAnswer(final_answer="", answer="", steps=[], error=f"ImportError: {e}")

    out: Dict[str, Any] = impl.solve(question)

    # Standard expected field in your naming module is "answer"
    ans = _safe_str(out.get("answer", ""))

    notes = out.get("notes", [])
    steps = [str(x) for x in notes] if isinstance(notes, list) else []

    return IUPACAnswer(
        final_answer=ans,
        answer=ans,
        steps=steps,
        error=None,
        topic="IUPAC_V1",
    )


# Back-compat aliases in case the tests call these names:
solve_iupac_v1 = answer_iupac_question
solve = answer_iupac_question
