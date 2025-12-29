# src/response_packager_v1.py
"""
KnowEasy Engine — Unified Response Packager v1 (LOCKED)

Purpose:
- Produce ONE canonical payload for UI / analytics / storage
- Merge:
  • EngineOutputV1
  • Explainability bundle
  • Exam-mode policy tags
  • Error taxonomy signals

STRICT RULES:
- Read-only
- No chemistry logic
- Deterministic only
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from src.output_schema_v1 import EngineOutputV1
from src.explainability_hooks_v1 import (
    DecisionTraceV1,
    ExplainabilityBundleV1,
    attach_explainability,
)
from src.exam_mode_hooks_v1 import (
    get_exam_policy,
    add_exam_mode_tags,
    clamp_assumptions,
)
from src.error_taxonomy_v1 import (
    ErrorSignalV1,
    map_flags_to_error_signals,
    infer_error_signals_from_attempt,
    summarize_error_signals,
)


def build_response_packet(
    *,
    output: EngineOutputV1,
    exam_mode: str,
    traces: Optional[List[DecisionTraceV1]] = None,
    explainability_tags: Optional[List[str]] = None,
    error_flags: Optional[List[str]] = None,
    attempt_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds the final unified response payload.

    attempt_context (optional) may include:
      - student_answer
      - correct_answer
      - units_mismatch
      - sign_mismatch
      - computation_mismatch
      - concept_hint
    """
    # 1) Exam policy (read-only)
    policy = get_exam_policy(exam_mode)

    # 2) Clamp assumptions deterministically
    assumptions = clamp_assumptions(
        exam_mode,
        list(output.assumptions),
    )

    # 3) Explainability
    explain_payload = attach_explainability(
        output,
        traces=traces or [],
        tags=(explainability_tags or []) + add_exam_mode_tags(exam_mode),
        assumptions=assumptions,
    )

    # 4) Error taxonomy — from flags
    error_signals: List[ErrorSignalV1] = []
    if error_flags:
        error_signals.extend(
            map_flags_to_error_signals(
                error_flags,
                default_severity="medium",
            )
        )

    # 5) Error taxonomy — from attempt context
    if attempt_context:
        error_signals.extend(
            infer_error_signals_from_attempt(
                student_answer=attempt_context.get("student_answer"),
                correct_answer=attempt_context.get("correct_answer"),
                units_mismatch=bool(attempt_context.get("units_mismatch")),
                sign_mismatch=bool(attempt_context.get("sign_mismatch")),
                computation_mismatch=bool(attempt_context.get("computation_mismatch")),
                concept_hint=attempt_context.get("concept_hint"),
            )
        )

    # 6) Summarize errors
    error_summary = summarize_error_signals(error_signals)

    # 7) Final payload
    return {
        "answer": explain_payload["answer"],
        "reason": explain_payload["reason"],
        "exam_mode": exam_mode,
        "confidence": policy.default_confidence,
        "flags": list(output.flags),
        "assumptions": assumptions,
        "explainability": explain_payload["explainability"],
        "exam_policy": policy.to_dict(),
        "errors": [e.to_dict() for e in error_signals],
        "error_summary": error_summary,
        "version": "chemistry_v1.0",
    }
