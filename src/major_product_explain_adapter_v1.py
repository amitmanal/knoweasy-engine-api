"""
Major Product Engine — Explainability Adapter v1 (SAFE MODE, additive)

Goal:
- Provide a small adapter that can be OPTIONALY used by Major Product Engine v1
  (or Answer Generator) to attach Organic v2 reasoning metadata:
  * mechanism decision + reasons + confidence
  * rearrangement decision + reasons + confidence

Hard constraints:
- Do NOT modify Major Product Engine v1
- Do NOT modify governor/normalizer/output formats
- This adapter returns a sidecar dict that can be attached under a new key
  (e.g., "explain_v2") without breaking existing consumers.

This module does NOT call the major product engine. It only generates explain metadata
from already-known context inputs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from src.organic_reasoning_v2 import (
    explain_mechanism_decision,
    explain_rearrangement_decision,
    OrganicReasoningError,
)


class MajorProductExplainAdapterError(ValueError):
    """Raised when adapter inputs are invalid or Organic v2 reasoning fails."""


def build_mechanism_explain_v2(
    *,
    substrate_degree: str,
    nucleophile_strength: str,
    base_strength: str,
    solvent: str,
    temperature_high: bool = False,
) -> Dict[str, Any]:
    """
    Returns a deterministic explain dict for SN1/SN2/E1/E2 decision.

    Output schema (stable):
      {
        "type": "mechanism_explain_v2",
        "mechanism": ...,
        "confidence": ...,
        "reasons": [...],
        "summary": ...
      }
    """
    try:
        out = explain_mechanism_decision(
            substrate_degree=substrate_degree,
            nucleophile_strength=nucleophile_strength,
            base_strength=base_strength,
            solvent=solvent,
            temperature_high=temperature_high,
        )
    except OrganicReasoningError as e:
        raise MajorProductExplainAdapterError(str(e)) from e

    return {
        "type": "mechanism_explain_v2",
        "mechanism": out["mechanism"],
        "confidence": out["confidence"],
        "reasons": out["reasons"],
        "summary": out["summary"],
    }


def build_rearrangement_explain_v2(
    *,
    initial_kind: str,
    hydride_shift_kind: str,
    methyl_shift_kind: str,
    initial_inductive: str = "none",
    initial_resonance: str = "none",
    initial_alpha_h: int = 0,
    hydride_inductive: str = "none",
    hydride_resonance: str = "none",
    hydride_alpha_h: int = 0,
    methyl_inductive: str = "none",
    methyl_resonance: str = "none",
    methyl_alpha_h: int = 0,
    min_improvement: int = 1,
) -> Dict[str, Any]:
    """
    Returns a deterministic explain dict for rearrangement preference.

    Output schema (stable):
      {
        "type": "rearrangement_explain_v2",
        "decision": ...,
        "confidence": ...,
        "reasons": [...],
        "summary": ...,
        "debug": {... scores ...}
      }
    """
    try:
        out = explain_rearrangement_decision(
            initial_kind=initial_kind,
            hydride_shift_kind=hydride_shift_kind,
            methyl_shift_kind=methyl_shift_kind,
            initial_inductive=initial_inductive,
            initial_resonance=initial_resonance,
            initial_alpha_h=initial_alpha_h,
            hydride_inductive=hydride_inductive,
            hydride_resonance=hydride_resonance,
            hydride_alpha_h=hydride_alpha_h,
            methyl_inductive=methyl_inductive,
            methyl_resonance=methyl_resonance,
            methyl_alpha_h=methyl_alpha_h,
            min_improvement=min_improvement,
        )
    except OrganicReasoningError as e:
        raise MajorProductExplainAdapterError(str(e)) from e

    return {
        "type": "rearrangement_explain_v2",
        "decision": out["decision"],
        "confidence": out["confidence"],
        "reasons": out["reasons"],
        "summary": out["summary"],
        "debug": out.get("debug", {}),
    }


def build_explain_v2_bundle(
    *,
    mechanism_context: Optional[Dict[str, Any]] = None,
    rearrangement_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a sidecar explain bundle.

    mechanism_context keys expected:
      substrate_degree, nucleophile_strength, base_strength, solvent, temperature_high(optional)

    rearrangement_context keys expected:
      initial_kind, hydride_shift_kind, methyl_shift_kind, plus optional effects args

    Returns:
      {
        "type": "explain_v2_bundle",
        "mechanism": <mechanism explain dict or None>,
        "rearrangement": <rearrangement explain dict or None>
      }
    """
    mech_out = None
    rear_out = None

    if mechanism_context is not None:
        mech_out = build_mechanism_explain_v2(
            substrate_degree=mechanism_context["substrate_degree"],
            nucleophile_strength=mechanism_context["nucleophile_strength"],
            base_strength=mechanism_context["base_strength"],
            solvent=mechanism_context["solvent"],
            temperature_high=bool(mechanism_context.get("temperature_high", False)),
        )

    if rearrangement_context is not None:
        rear_out = build_rearrangement_explain_v2(
            initial_kind=rearrangement_context["initial_kind"],
            hydride_shift_kind=rearrangement_context["hydride_shift_kind"],
            methyl_shift_kind=rearrangement_context["methyl_shift_kind"],
            initial_inductive=rearrangement_context.get("initial_inductive", "none"),
            initial_resonance=rearrangement_context.get("initial_resonance", "none"),
            initial_alpha_h=int(rearrangement_context.get("initial_alpha_h", 0)),
            hydride_inductive=rearrangement_context.get("hydride_inductive", "none"),
            hydride_resonance=rearrangement_context.get("hydride_resonance", "none"),
            hydride_alpha_h=int(rearrangement_context.get("hydride_alpha_h", 0)),
            methyl_inductive=rearrangement_context.get("methyl_inductive", "none"),
            methyl_resonance=rearrangement_context.get("methyl_resonance", "none"),
            methyl_alpha_h=int(rearrangement_context.get("methyl_alpha_h", 0)),
            min_improvement=int(rearrangement_context.get("min_improvement", 1)),
        )

    return {
        "type": "explain_v2_bundle",
        "mechanism": mech_out,
        "rearrangement": rear_out,
    }


def attach_explain_v2_sidecar(answer_payload: Dict[str, Any], explain_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    SAFE ATTACHMENT:
- Does NOT mutate input answer_payload
- Adds a new top-level key "explain_v2" (sidecar)
- Leaves original output shape intact for existing consumers

    Returns new dict.
    """
    if not isinstance(answer_payload, dict):
        raise MajorProductExplainAdapterError("answer_payload must be a dict.")
    if not isinstance(explain_bundle, dict):
        raise MajorProductExplainAdapterError("explain_bundle must be a dict.")

    new_payload = deepcopy(answer_payload)
    new_payload["explain_v2"] = deepcopy(explain_bundle)
    return new_payload
