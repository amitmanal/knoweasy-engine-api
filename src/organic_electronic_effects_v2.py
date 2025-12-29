"""
Organic Chemistry v2 — Phase 2: Electronic Effects Scoring (Deterministic)

Goal:
- Provide deterministic, exam-safe "stability scoring" building blocks for:
  * carbocations
  * carbanions
  * radicals

This module DOES NOT simulate mechanisms or predict products.
It only provides normalized scoring helpers based on:
- Inductive effect (+I / -I)
- Resonance effect (+R / -R)
- Hyperconjugation (relative count proxy)

Design principles:
- Minimal, stable, deterministic mapping
- Only coarse-grained signals used in JEE/NEET
- Scores are relative; higher score = more stabilizing for the given intermediate type

Important:
- Do NOT refactor existing Organic v1 or mechanism v2 modules.
- This module is additive and can be optionally used later by major-product logic.
"""

from __future__ import annotations


class OrganicElectronicEffectsError(ValueError):
    """Invalid inputs for electronic-effects helpers."""


# Coarse maps (exam-safe)
# Inductive effect strength (absolute magnitude proxy)
_INDUCTIVE_STRENGTH = {
    "plus": 1,    # +I
    "minus": 1,   # -I
    "none": 0,
}

# Resonance effect strength
_RESONANCE_STRENGTH = {
    "plus": 2,    # +R
    "minus": 2,   # -R
    "none": 0,
}


def _norm_effect(effect: str) -> str:
    e = (effect or "").strip().lower()
    if e in ("+i", "plus_i", "plus-i", "plus"):
        return "plus"
    if e in ("-i", "minus_i", "minus-i", "minus"):
        return "minus"
    if e in ("0", "none", "neutral", ""):
        return "none"
    raise OrganicElectronicEffectsError(f"Unknown effect: {effect}")


def _norm_resonance(effect: str) -> str:
    e = (effect or "").strip().lower()
    if e in ("+r", "+m", "plus_r", "plus-m", "plus"):
        return "plus"
    if e in ("-r", "-m", "minus_r", "minus-m", "minus"):
        return "minus"
    if e in ("0", "none", "neutral", ""):
        return "none"
    raise OrganicElectronicEffectsError(f"Unknown resonance effect: {effect}")


# -------------------------
# Hyperconjugation proxy
# -------------------------

def hyperconjugation_score(alpha_h_count: int) -> int:
    """
    Deterministic proxy:
      more alpha hydrogens => more hyperconjugation => more stabilization
    Score equals alpha_h_count, capped at reasonable exam range.

    alpha_h_count must be >= 0.
    """
    if not isinstance(alpha_h_count, int):
        raise OrganicElectronicEffectsError("alpha_h_count must be int.")
    if alpha_h_count < 0:
        raise OrganicElectronicEffectsError("alpha_h_count must be >= 0.")
    # cap to avoid absurd numbers; still deterministic
    return min(alpha_h_count, 18)


# -------------------------
# Effect scoring by intermediate type
# -------------------------

def inductive_stabilization_score(intermediate: str, effect: str) -> int:
    """
    Returns an integer score contribution for inductive effect.

    Convention:
    - Carbocation / Radical: +I stabilizes, -I destabilizes
    - Carbanion: -I stabilizes, +I destabilizes

    Scores:
      stabilizing => +1
      destabilizing => -1
      none => 0
    """
    t = (intermediate or "").strip().lower()
    e = _norm_effect(effect)

    if t not in ("carbocation", "carbanion", "radical"):
        raise OrganicElectronicEffectsError("intermediate must be carbocation/carbanion/radical.")

    if e == "none":
        return 0

    if t in ("carbocation", "radical"):
        return +_INDUCTIVE_STRENGTH[e] if e == "plus" else -_INDUCTIVE_STRENGTH[e]

    # carbanion
    return +_INDUCTIVE_STRENGTH[e] if e == "minus" else -_INDUCTIVE_STRENGTH[e]


def resonance_stabilization_score(intermediate: str, effect: str) -> int:
    """
    Resonance effects:
    - Carbocation / Radical: +R stabilizes, -R destabilizes
    - Carbanion: -R stabilizes, +R destabilizes

    Strength is 2 (stronger than inductive, exam-safe).
    """
    t = (intermediate or "").strip().lower()
    e = _norm_resonance(effect)

    if t not in ("carbocation", "carbanion", "radical"):
        raise OrganicElectronicEffectsError("intermediate must be carbocation/carbanion/radical.")

    if e == "none":
        return 0

    if t in ("carbocation", "radical"):
        return +_RESONANCE_STRENGTH[e] if e == "plus" else -_RESONANCE_STRENGTH[e]

    # carbanion
    return +_RESONANCE_STRENGTH[e] if e == "minus" else -_RESONANCE_STRENGTH[e]


def total_stability_score(
    intermediate: str,
    inductive_effect: str = "none",
    resonance_effect: str = "none",
    alpha_h_count: int = 0,
) -> int:
    """
    Total stability score (relative):
      Score = inductive_score + resonance_score + hyperconjugation_score(for carbocation/radical only)

    Hyperconjugation is generally:
    - stabilizing for carbocations and radicals
    - not stabilizing for carbanions in simple exam heuristics (often opposite trend)

    Therefore:
    - for carbanion, hyperconjugation contribution is 0 in this deterministic model.
    """
    t = (intermediate or "").strip().lower()
    if t not in ("carbocation", "carbanion", "radical"):
        raise OrganicElectronicEffectsError("intermediate must be carbocation/carbanion/radical.")

    ind = inductive_stabilization_score(t, inductive_effect)
    res = resonance_stabilization_score(t, resonance_effect)

    hyp = 0
    if t in ("carbocation", "radical"):
        hyp = hyperconjugation_score(alpha_h_count)

    return int(ind + res + hyp)
