# src/error_taxonomy_v1.py
"""
KnowEasy Engine — Error Pattern Taxonomy v1 (LOCKED)

Purpose:
- Deterministically classify potential error/risk patterns for an attempt or an output
- Used for analytics, revision planning, and UI warnings
- NO chemistry logic here
- NO AI inference

This taxonomy is intentionally small and stable.
Later versions can expand without breaking v1.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# Canonical error categories (v1)
ERROR_CATEGORIES_V1: Tuple[str, ...] = (
    "CONCEPT_GAP",
    "FORMULA_MISUSE",
    "TREND_CONFUSION",
    "CONDITION_OMISSION",
    "UNIT_MISTAKE",
    "SIGN_MISTAKE",
    "CALCULATION_ERROR",
    "DATA_RECALL",
    "AMBIGUITY_EXAM_DEPENDENT",
    "MISREAD_QUESTION",
)


# Common engine flags -> taxonomy mapping (v1, deterministic)
FLAG_TO_ERROR_V1: Dict[str, str] = {
    # Condition-related
    "MAJOR_PRODUCT_MISSING_CONDITIONS": "CONDITION_OMISSION",
    "KOH_MEDIUM_NOT_SPECIFIED": "CONDITION_OMISSION",
    "POSSIBLE_SOLVENT_MISSING": "CONDITION_OMISSION",

    # Ambiguity / exam conventions
    "AMBIGUOUS_CONDITIONS": "AMBIGUITY_EXAM_DEPENDENT",
    "MULTIPLE_PRODUCTS_POSSIBLE": "AMBIGUITY_EXAM_DEPENDENT",

    # Generic / knowledge
    "UNKNOWN_REAGENT": "DATA_RECALL",
    "UNKNOWN_CHAPTER": "DATA_RECALL",
}


@dataclass(frozen=True)
class ErrorSignalV1:
    """
    A deterministic error signal produced by analysis.
    """
    category: str
    evidence: str  # short deterministic explanation
    severity: str  # "low" | "medium" | "high"

    def to_dict(self) -> Dict[str, str]:
        return {
            "category": self.category,
            "evidence": self.evidence,
            "severity": self.severity,
        }


def validate_category(category: str) -> str:
    if category not in ERROR_CATEGORIES_V1:
        raise ValueError(f"Invalid error category: {category!r}")
    return category


def validate_severity(severity: str) -> str:
    if severity not in ("low", "medium", "high"):
        raise ValueError(f"Invalid severity: {severity!r}")
    return severity


def map_flags_to_error_signals(
    flags: List[str],
    *,
    default_severity: str = "medium",
) -> List[ErrorSignalV1]:
    """
    Deterministically maps engine flags to error signals.
    Unknown flags are ignored (safe, non-breaking).
    """
    validate_severity(default_severity)

    out: List[ErrorSignalV1] = []
    for f in flags or []:
        if f in FLAG_TO_ERROR_V1:
            cat = FLAG_TO_ERROR_V1[f]
            validate_category(cat)
            # severity heuristic (v1):
            # - condition omission tends to be medium/high depending on context; use medium default
            # - ambiguity exam dependent usually low/medium
            if cat == "AMBIGUITY_EXAM_DEPENDENT":
                sev = "low" if default_severity == "medium" else default_severity
            else:
                sev = default_severity
            out.append(
                ErrorSignalV1(
                    category=cat,
                    evidence=f"Mapped from flag: {f}",
                    severity=sev,
                )
            )
    return out


def infer_error_signals_from_attempt(
    *,
    student_answer: Optional[str],
    correct_answer: Optional[str],
    units_mismatch: bool = False,
    sign_mismatch: bool = False,
    computation_mismatch: bool = False,
    concept_hint: Optional[str] = None,
) -> List[ErrorSignalV1]:
    """
    Deterministic attempt-based signal inference.
    This does NOT compute correctness; it only tags obvious mismatch patterns
    when those booleans are provided by upstream evaluators.
    """
    signals: List[ErrorSignalV1] = []

    if units_mismatch:
        signals.append(ErrorSignalV1(
            category="UNIT_MISTAKE",
            evidence="Units mismatch detected by evaluator",
            severity="high",
        ))

    if sign_mismatch:
        signals.append(ErrorSignalV1(
            category="SIGN_MISTAKE",
            evidence="Sign mismatch detected by evaluator",
            severity="medium",
        ))

    if computation_mismatch:
        signals.append(ErrorSignalV1(
            category="CALCULATION_ERROR",
            evidence="Arithmetic mismatch detected by evaluator",
            severity="medium",
        ))

    # If student answer is empty but correct exists, likely misread / omission
    if (student_answer is None or str(student_answer).strip() == "") and (correct_answer is not None and str(correct_answer).strip() != ""):
        signals.append(ErrorSignalV1(
            category="MISREAD_QUESTION",
            evidence="No attempt/blank answer while a definite answer exists",
            severity="medium",
        ))

    if concept_hint:
        signals.append(ErrorSignalV1(
            category="CONCEPT_GAP",
            evidence=f"Concept hint: {concept_hint}",
            severity="medium",
        ))

    # validate categories
    for s in signals:
        validate_category(s.category)
        validate_severity(s.severity)

    return signals


def summarize_error_signals(signals: List[ErrorSignalV1]) -> Dict[str, int]:
    """
    Deterministic count summary by category.
    """
    summary: Dict[str, int] = {}
    for s in signals or []:
        validate_category(s.category)
        summary[s.category] = summary.get(s.category, 0) + 1
    return summary
