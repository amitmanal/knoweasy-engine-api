# src/exam_mode_hooks_v1.py
"""
KnowEasy Engine — Exam Mode Hooks v1 (READ-ONLY, LOCKED)

Purpose:
- Provide deterministic exam-mode policies for wrappers/UI
- DOES NOT change the answer (logic stays frozen)
- Only influences metadata: confidence defaults, assumption tolerance, explanation depth tags

Exam modes:
- BOARD: strict NCERT, minimal assumptions, conservative confidence
- NEET : NCERT-first with applied focus, moderate assumptions
- JEE  : deeper reasoning allowed, more assumptions acceptable (but still explicit)

This module is safe to use by adapters around deterministic engines.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

from src.output_schema_v1 import validate_exam_mode


@dataclass(frozen=True)
class ExamPolicyV1:
    exam_mode: str
    default_confidence: str
    max_assumptions: int
    explanation_depth: str  # "short" | "medium" | "deep"
    strict_ncert: bool
    allow_advanced_context: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "exam_mode": self.exam_mode,
            "default_confidence": self.default_confidence,
            "max_assumptions": self.max_assumptions,
            "explanation_depth": self.explanation_depth,
            "strict_ncert": self.strict_ncert,
            "allow_advanced_context": self.allow_advanced_context,
        }


def get_exam_policy(exam_mode: str) -> ExamPolicyV1:
    """
    Deterministic policy lookup.
    """
    validate_exam_mode(exam_mode)

    if exam_mode == "BOARD":
        return ExamPolicyV1(
            exam_mode="BOARD",
            default_confidence="high",
            max_assumptions=0,
            explanation_depth="short",
            strict_ncert=True,
            allow_advanced_context=False,
        )

    if exam_mode == "NEET":
        return ExamPolicyV1(
            exam_mode="NEET",
            default_confidence="high",
            max_assumptions=1,
            explanation_depth="medium",
            strict_ncert=True,
            allow_advanced_context=False,
        )

    # JEE
    return ExamPolicyV1(
        exam_mode="JEE",
        default_confidence="high",
        max_assumptions=2,
        explanation_depth="deep",
        strict_ncert=False,
        allow_advanced_context=True,
    )


def clamp_assumptions(exam_mode: str, assumptions: List[str]) -> List[str]:
    """
    Read-only helper:
    - Does NOT create assumptions
    - If assumptions exceed policy limit, truncates deterministically
    """
    policy = get_exam_policy(exam_mode)
    if not assumptions:
        return []
    return assumptions[: policy.max_assumptions]


def add_exam_mode_tags(exam_mode: str) -> List[str]:
    """
    Deterministic tags for explainability/UI.
    """
    policy = get_exam_policy(exam_mode)
    tags = [f"EXAM_{policy.exam_mode}", f"DEPTH_{policy.explanation_depth.upper()}"]
    if policy.strict_ncert:
        tags.append("NCERT_STRICT")
    if policy.allow_advanced_context:
        tags.append("ADVANCED_ALLOWED")
    return tags
