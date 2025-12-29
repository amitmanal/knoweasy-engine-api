"""
Organic Chemistry v2 — Phase 4: Reason Strings + Confidence Flags (Deterministic)

Purpose:
- Provide explainability hooks for mechanism and rearrangement decisions.
- Does NOT change any existing engine logic.
- Produces deterministic "reason strings" + confidence flags.

Outputs are meant to be optionally consumed by UI / answer generator later.

Confidence flags:
- "high_confidence"
- "medium_confidence"
- "low_confidence"
"""

from __future__ import annotations

from typing import Dict, List, Literal

from src.organic_mechanism_v2 import decide_substitution_elimination_mechanism, OrganicMechanismError
from src.organic_rearrangement_v2 import (
    decide_carbocation_rearrangement,
    carbocation_overall_score,
    OrganicRearrangementError,
)


class OrganicReasoningError(ValueError):
    """Invalid inputs for organic reasoning helpers."""


Confidence = Literal["high_confidence", "medium_confidence", "low_confidence"]


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _confidence_for_mechanism(
    substrate_degree: str,
    nucleophile_strength: str,
    base_strength: str,
    solvent: str,
    temperature_high: bool,
    decided: str,
) -> Confidence:
    sd = _norm(substrate_degree)
    nu = _norm(nucleophile_strength)
    bs = _norm(base_strength)
    sol = _norm(solvent)

    # High-confidence archetypes (exam-classic)
    if decided == "SN2" and sd == "primary" and nu == "strong" and sol == "polar aprotic" and bs != "strong":
        return "high_confidence"
    if decided == "SN1" and sd == "tertiary" and nu == "weak" and sol == "polar protic" and bs != "strong" and not temperature_high:
        return "high_confidence"
    if decided == "E2" and bs == "strong":
        return "high_confidence"

    # Secondary substrate decisions are often borderline
    if sd == "secondary":
        return "medium_confidence"

    # Temperature-driven E1 is a heuristic; treat as medium
    if decided == "E1" and temperature_high:
        return "medium_confidence"

    return "low_confidence"


def explain_mechanism_decision(
    substrate_degree: str,
    nucleophile_strength: str,
    base_strength: str,
    solvent: str,
    temperature_high: bool = False,
) -> Dict[str, object]:
    """
    Returns:
      {
        "mechanism": "SN1"/"SN2"/"E1"/"E2",
        "confidence": "high_confidence"/"medium_confidence"/"low_confidence",
        "reasons": [ ... list of short exam-style reasons ... ],
        "summary": "single-line summary"
      }
    """
    try:
        mech = decide_substitution_elimination_mechanism(
            substrate_degree=substrate_degree,
            nucleophile_strength=nucleophile_strength,
            base_strength=base_strength,
            solvent=solvent,
            temperature_high=temperature_high,
        )
    except OrganicMechanismError as e:
        raise OrganicReasoningError(str(e)) from e

    sd = _norm(substrate_degree)
    nu = _norm(nucleophile_strength)
    bs = _norm(base_strength)
    sol = _norm(solvent)

    reasons: List[str] = []

    # Common rule reasons
    if bs == "strong":
        reasons.append("Strong base favors elimination over substitution (E2 preferred).")

    if sol == "polar protic":
        reasons.append("Polar protic solvent stabilizes ions and supports carbocation pathways (SN1/E1).")
    elif sol == "polar aprotic":
        reasons.append("Polar aprotic solvent enhances nucleophilicity and supports backside attack (SN2).")

    if sd == "tertiary":
        reasons.append("Tertiary substrate is sterically hindered for SN2 and forms more stable carbocations (SN1/E1).")
    elif sd == "primary":
        reasons.append("Primary substrate does not form stable carbocation; SN2 is favored with strong nucleophile.")
    elif sd == "secondary":
        reasons.append("Secondary substrate is borderline; outcome depends on nucleophile/base strength and solvent.")

    if temperature_high:
        reasons.append("Higher temperature increases entropy contribution and biases elimination over substitution.")

    # Mechanism-specific focus
    if mech == "SN1":
        reasons.append("SN1 favored due to carbocation formation under ionizing conditions.")
        summary = "SN1 selected: carbocation pathway favored under given substrate/solvent conditions."
    elif mech == "SN2":
        reasons.append("SN2 favored due to strong nucleophile and minimal steric hindrance.")
        summary = "SN2 selected: strong nucleophile + suitable solvent favors one-step substitution."
    elif mech == "E1":
        reasons.append("E1 favored due to carbocation pathway with elimination bias (often at higher temperature).")
        summary = "E1 selected: carbocation pathway with temperature-driven elimination preference."
    elif mech == "E2":
        reasons.append("E2 favored due to concerted elimination with strong base.")
        summary = "E2 selected: strong base drives concerted elimination."
    else:
        # Should never happen
        raise OrganicReasoningError(f"Unexpected mechanism: {mech}")

    confidence = _confidence_for_mechanism(sd, nu, bs, sol, temperature_high, mech)

    return {
        "mechanism": mech,
        "confidence": confidence,
        "reasons": reasons,
        "summary": summary,
    }


def _confidence_for_rearrangement(
    initial_score: int,
    best_score: int,
    decision: str,
) -> Confidence:
    delta = best_score - initial_score

    if decision == "no_rearrangement_likely":
        # If there's no improvement, this is usually high confidence.
        return "high_confidence" if delta <= 0 else "medium_confidence"

    # If rearrangement improves stability clearly, high confidence.
    if delta >= 100:
        return "high_confidence"
    if delta >= 1:
        return "medium_confidence"
    return "low_confidence"


def explain_rearrangement_decision(
    initial_kind: str,
    hydride_shift_kind: str,
    methyl_shift_kind: str,
    *,
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
) -> Dict[str, object]:
    """
    Returns:
      {
        "decision": "hydride_shift_preferred"/"methyl_shift_preferred"/"no_rearrangement_likely",
        "confidence": ...,
        "reasons": [...],
        "summary": ...
      }
    """
    try:
        decision = decide_carbocation_rearrangement(
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
    except (OrganicRearrangementError, ValueError) as e:
        raise OrganicReasoningError(str(e)) from e

    s0 = carbocation_overall_score(initial_kind, initial_inductive, initial_resonance, initial_alpha_h)
    sh = carbocation_overall_score(hydride_shift_kind, hydride_inductive, hydride_resonance, hydride_alpha_h)
    sm = carbocation_overall_score(methyl_shift_kind, methyl_inductive, methyl_resonance, methyl_alpha_h)

    best_score = max(sh, sm)
    confidence = _confidence_for_rearrangement(s0, best_score, decision)

    reasons: List[str] = []
    reasons.append("Carbocation rearrangement is favored only if it leads to a more stable carbocation.")
    reasons.append("Decision compares relative stability of possible post-shift carbocations (no step simulation).")

    if decision == "hydride_shift_preferred":
        reasons.append("Hydride shift gives the larger stability improvement (or ties are resolved in favor of hydride).")
        summary = "Hydride shift preferred: leads to more stable carbocation."
    elif decision == "methyl_shift_preferred":
        reasons.append("Methyl shift gives the larger stability improvement compared to hydride shift.")
        summary = "Methyl shift preferred: leads to more stable carbocation."
    else:
        reasons.append("No shift provides sufficient stability gain; rearrangement is unlikely.")
        summary = "No rearrangement likely: no sufficient stability gain."

    return {
        "decision": decision,
        "confidence": confidence,
        "reasons": reasons,
        "summary": summary,
        "debug": {
            "initial_score": s0,
            "hydride_score": sh,
            "methyl_score": sm,
        },
    }
