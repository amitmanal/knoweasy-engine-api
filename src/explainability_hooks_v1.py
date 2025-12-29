# src/explainability_hooks_v1.py
"""
KnowEasy Engine — Explainability Hooks v1 (LOCKED)

Purpose:
- Attach deterministic explainability metadata to EngineOutputV1
- NO AI generation
- NO chemistry logic
- Pure tagging + trace utilities

This module prepares the ground for:
- "Why was this answer chosen?"
- Rule firing visibility
- Student-facing explanations
- Analytics & audits
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.output_schema_v1 import EngineOutputV1


# -------------------------
# Deterministic trace model
# -------------------------

@dataclass(frozen=True)
class DecisionTraceV1:
    """
    A single deterministic decision trace entry.
    """
    rule_id: str                 # e.g., "SN1_MAJOR_PRODUCT"
    description: str             # human-readable, deterministic
    inputs: Dict[str, Any]       # key inputs used
    outcome: Any                 # what this rule concluded


@dataclass(frozen=True)
class ExplainabilityBundleV1:
    """
    Explainability bundle attached alongside EngineOutputV1.
    """
    traces: List[DecisionTraceV1] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)  # e.g., "CONCEPT_SN1", "TREND_OXIDATION"
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "traces": [
                {
                    "rule_id": t.rule_id,
                    "description": t.description,
                    "inputs": dict(t.inputs),
                    "outcome": t.outcome,
                }
                for t in self.traces
            ],
            "tags": list(self.tags),
            "assumptions": list(self.assumptions),
        }


# -------------------------
# Hook utilities
# -------------------------

def attach_explainability(
    output: EngineOutputV1,
    *,
    traces: Optional[List[DecisionTraceV1]] = None,
    tags: Optional[List[str]] = None,
    assumptions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Returns a merged payload:
      {
        ...EngineOutputV1 fields,
        "explainability": { ...ExplainabilityBundleV1 }
      }

    Does NOT modify EngineOutputV1 (immutable).
    """
    bundle = ExplainabilityBundleV1(
        traces=traces or [],
        tags=tags or [],
        assumptions=assumptions or [],
    )
    payload = output.to_dict()
    payload["explainability"] = bundle.to_dict()
    return payload


def make_trace(
    *,
    rule_id: str,
    description: str,
    inputs: Dict[str, Any],
    outcome: Any,
) -> DecisionTraceV1:
    """
    Factory with minimal validation.
    """
    if not rule_id or not isinstance(rule_id, str):
        raise ValueError("rule_id must be a non-empty string")
    if not description or not isinstance(description, str):
        raise ValueError("description must be a non-empty string")
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be a dict")
    return DecisionTraceV1(
        rule_id=rule_id,
        description=description,
        inputs=inputs,
        outcome=outcome,
    )


def default_explainability_for_legacy(
    *,
    tags: Optional[List[str]] = None,
) -> ExplainabilityBundleV1:
    """
    For engines that do not yet emit traces.
    """
    return ExplainabilityBundleV1(
        traces=[],
        tags=tags or [],
        assumptions=[],
    )
