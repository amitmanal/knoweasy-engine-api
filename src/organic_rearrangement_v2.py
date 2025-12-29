"""
Organic Chemistry v2 — Phase 3: Rearrangement Likelihood (Deterministic)

Goal:
- Decide whether carbocation rearrangement is likely
- Decide which shift is preferred: hydride vs methyl

This module DOES NOT simulate steps or migrations.
It compares "before vs after" relative stability using:
- Carbocation stability rank (phase-1)
- Electronic effects stability score (phase-2)

Deterministic outputs:
- "hydride_shift_preferred"
- "methyl_shift_preferred"
- "no_rearrangement_likely"

Notes (exam-safe heuristics):
- Rearrangement is likely only if it leads to a MORE stable carbocation.
- If both hydride and methyl shift increase stability, choose the larger improvement.
- If improvements tie, prefer hydride shift (more common/rapid heuristic).
"""

from __future__ import annotations

from src.organic_mechanism_v2 import carbocation_stability_rank
from src.organic_electronic_effects_v2 import total_stability_score


class OrganicRearrangementError(ValueError):
    """Invalid inputs for rearrangement helpers."""


def _validate_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    # carbocation_stability_rank will validate exact allowed set:
    # methyl, primary, secondary, tertiary, allylic, benzylic
    _ = carbocation_stability_rank(k)
    return k


def carbocation_overall_score(
    kind: str,
    inductive_effect: str = "none",
    resonance_effect: str = "none",
    alpha_h_count: int = 0,
) -> int:
    """
    Overall deterministic score for comparing two carbocations.
    Higher score = more stable.

    We weight the base carbocation rank strongly, then add electronic effects score:
      overall = rank*100 + electronic_total

    This preserves the canonical order (benzylic > allylic > 3° > 2° > 1° > methyl)
    while still allowing small adjustments via electronic effects/hyperconjugation.
    """
    k = _validate_kind(kind)
    base_rank = carbocation_stability_rank(k)
    elec = total_stability_score(
        "carbocation",
        inductive_effect=inductive_effect,
        resonance_effect=resonance_effect,
        alpha_h_count=alpha_h_count,
    )
    return int(base_rank * 100 + elec)


def decide_carbocation_rearrangement(
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
) -> str:
    """
    Decide rearrangement preference based on relative stability improvements.

    min_improvement:
      Minimum score increase required to consider a shift "likely".
      Default 1 ensures strictly better stability triggers rearrangement.

    Returns:
      "hydride_shift_preferred" | "methyl_shift_preferred" | "no_rearrangement_likely"
    """
    if not isinstance(min_improvement, int) or min_improvement < 1:
        raise OrganicRearrangementError("min_improvement must be an int >= 1.")

    s0 = carbocation_overall_score(initial_kind, initial_inductive, initial_resonance, initial_alpha_h)
    sh = carbocation_overall_score(hydride_shift_kind, hydride_inductive, hydride_resonance, hydride_alpha_h)
    sm = carbocation_overall_score(methyl_shift_kind, methyl_inductive, methyl_resonance, methyl_alpha_h)

    dh = sh - s0
    dm = sm - s0

    hydride_ok = dh >= min_improvement
    methyl_ok = dm >= min_improvement

    if not hydride_ok and not methyl_ok:
        return "no_rearrangement_likely"

    if hydride_ok and not methyl_ok:
        return "hydride_shift_preferred"

    if methyl_ok and not hydride_ok:
        return "methyl_shift_preferred"

    # both are "ok" => choose larger improvement; tie => hydride preference
    if dh > dm:
        return "hydride_shift_preferred"
    if dm > dh:
        return "methyl_shift_preferred"
    return "hydride_shift_preferred"


def is_rearrangement_likely(
    initial_kind: str,
    best_shift_kind: str,
    *,
    initial_inductive: str = "none",
    initial_resonance: str = "none",
    initial_alpha_h: int = 0,
    best_inductive: str = "none",
    best_resonance: str = "none",
    best_alpha_h: int = 0,
    min_improvement: int = 1,
) -> bool:
    """
    Boolean helper: does the "best shift" improve stability enough to be considered likely?
    """
    if not isinstance(min_improvement, int) or min_improvement < 1:
        raise OrganicRearrangementError("min_improvement must be an int >= 1.")

    s0 = carbocation_overall_score(initial_kind, initial_inductive, initial_resonance, initial_alpha_h)
    sb = carbocation_overall_score(best_shift_kind, best_inductive, best_resonance, best_alpha_h)
    return (sb - s0) >= min_improvement
