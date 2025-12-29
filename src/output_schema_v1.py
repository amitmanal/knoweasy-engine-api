# src/output_schema_v1.py
"""
KnowEasy Engine — Output Schema v1 (LOCKED)

Purpose:
- Provide a universal, deterministic response contract
- Wrap existing engine outputs WITHOUT changing logic
- Prepare safe hooks for explainability, exam modes, analytics

STRICT RULES:
- No chemistry logic here
- No inference or AI reasoning
- Pure data normalization + validation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ALLOWED_EXAM_MODES = ("BOARD", "JEE", "NEET")
ALLOWED_CONFIDENCE = ("high", "medium", "low")


@dataclass(frozen=True)
class EngineOutputV1:
    """
    Canonical response object for KnowEasy Engine v1.0

    This is a WRAPPER only.
    """
    answer: Any
    reason: str
    exam_mode: str = "BOARD"
    confidence: str = "high"
    flags: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "reason": self.reason,
            "exam_mode": self.exam_mode,
            "confidence": self.confidence,
            "flags": list(self.flags),
            "assumptions": list(self.assumptions),
        }


def validate_exam_mode(exam_mode: str) -> str:
    if exam_mode not in ALLOWED_EXAM_MODES:
        raise ValueError(f"Invalid exam_mode: {exam_mode!r}")
    return exam_mode


def validate_confidence(confidence: str) -> str:
    if confidence not in ALLOWED_CONFIDENCE:
        raise ValueError(f"Invalid confidence: {confidence!r}")
    return confidence


def build_engine_output(
    *,
    answer: Any,
    reason: str,
    exam_mode: str = "BOARD",
    confidence: str = "high",
    flags: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
) -> EngineOutputV1:
    """
    Factory function to create a validated EngineOutputV1 object.
    """
    validate_exam_mode(exam_mode)
    validate_confidence(confidence)

    if not isinstance(reason, str) or reason.strip() == "":
        raise ValueError("reason must be a non-empty string")

    return EngineOutputV1(
        answer=answer,
        reason=reason,
        exam_mode=exam_mode,
        confidence=confidence,
        flags=flags or [],
        assumptions=assumptions or [],
    )


def upgrade_legacy_output(
    legacy_answer: Any,
    legacy_reason: str,
    *,
    flags: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
) -> EngineOutputV1:
    """
    Adapter for existing engines that already return (answer, reason).

    SAFE DEFAULTS:
    - exam_mode = BOARD
    - confidence = high
    """
    return build_engine_output(
        answer=legacy_answer,
        reason=legacy_reason,
        exam_mode="BOARD",
        confidence="high",
        flags=flags,
        assumptions=assumptions,
    )
