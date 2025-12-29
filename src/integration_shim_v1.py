# src/integration_shim_v1.py
"""
KnowEasy Engine — Integration Shim v1 (LOCKED)

Purpose:
- Provide ONE entrypoint to produce UI-ready payloads deterministically.
- Does NOT solve chemistry itself.
- It standardizes and packages outputs from any deterministic solver.

Pipeline (read-only):
1) Accept legacy engine outputs:
     - (answer, reason)  OR
     - dict with keys: answer, reason, flags?, assumptions?
2) Convert to EngineOutputV1
3) Build response packet (policy + errors + explainability merge)
4) Attach safe explanation (trace/tag-based, no AI, no answer generation)

This is the final glue for app integration.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union

from src.output_schema_v1 import build_engine_output, upgrade_legacy_output, EngineOutputV1
from src.response_packager_v1 import build_response_packet
from src.safe_explanations_v1 import attach_explanation_to_packet
from src.explainability_hooks_v1 import DecisionTraceV1


LegacyOutput = Union[
    Tuple[Any, str],                 # (answer, reason)
    Dict[str, Any],                  # {"answer":..., "reason":..., "flags":..., "assumptions":...}
    EngineOutputV1,                  # already standardized
]


def _to_engine_output_v1(legacy: LegacyOutput, *, exam_mode: str) -> EngineOutputV1:
    if isinstance(legacy, EngineOutputV1):
        # keep as is, but enforce exam_mode externally in packet stage
        return legacy

    if isinstance(legacy, tuple) and len(legacy) == 2:
        ans, rea = legacy
        return upgrade_legacy_output(
            legacy_answer=ans,
            legacy_reason=rea,
            flags=[],
            assumptions=[],
        )

    if isinstance(legacy, dict):
        if "answer" not in legacy or "reason" not in legacy:
            raise ValueError("Legacy dict must include 'answer' and 'reason'")
        return build_engine_output(
            answer=legacy.get("answer"),
            reason=str(legacy.get("reason")),
            exam_mode=exam_mode,  # stored, but packet will also carry exam_mode explicitly
            confidence="high",
            flags=list(legacy.get("flags") or []),
            assumptions=list(legacy.get("assumptions") or []),
        )

    raise ValueError(f"Unsupported legacy output type: {type(legacy).__name__}")


def solve_and_package_v1(
    *,
    legacy_output: LegacyOutput,
    exam_mode: str,
    traces: Optional[List[DecisionTraceV1]] = None,
    explainability_tags: Optional[List[str]] = None,
    attempt_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Final UI payload:
    - response_packager output
    - + explanation_v1 attached

    NOTE: This function does not compute an answer.
    It packages an answer produced by existing deterministic solvers.
    """
    out = _to_engine_output_v1(legacy_output, exam_mode=exam_mode)

    packet = build_response_packet(
        output=out,
        exam_mode=exam_mode,
        traces=traces or [],
        explainability_tags=explainability_tags or [],
        error_flags=list(out.flags),
        attempt_context=attempt_context,
    )

    packet_with_exp = attach_explanation_to_packet(packet)
    return packet_with_exp
