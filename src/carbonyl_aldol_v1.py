# src/carbonyl_aldol_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class AldolResult:
    reaction: str
    product: str
    notes: str = ""


def _is_acetaldehyde(t: str) -> bool:
    return ("acetaldehyde" in t) or ("ethanal" in t) or ("ch3cho" in t)


def _is_acetone(t: str) -> bool:
    return ("acetone" in t) or ("propanone" in t) or ("ch3coch3" in t)


def detect_aldol_v1(text: str) -> bool:
    t = _lc(text)

    # reagent triggers
    base = ("dil" in t or "dilute" in t or "cold" in t) and ("naoh" in t or "koh" in t or "oh-" in t)
    heat = ("heat" in t or "hot" in t or "Δ" in t or "delta" in t)

    # explicit word
    if "aldol" in t:
        return True

    # common exam phrasing: carbonyl + dil NaOH (cold/heat)
    if (("naoh" in t or "koh" in t) and ("aldehyde" in t or "ketone" in t or "carbonyl" in t)):
        return True

    # specific known substrates under base
    if (base or heat) and (_is_acetaldehyde(t) or _is_acetone(t)):
        return True

    return False


def solve_aldol_v1(question: str) -> Optional[AldolResult]:
    t = _lc(question)
    if not detect_aldol_v1(t):
        return None

    heat = ("heat" in t) or ("hot" in t) or ("Δ" in t) or ("delta" in t)

    # 2 acetaldehyde -> aldol / crotonaldehyde (on heating)
    if _is_acetaldehyde(t):
        if heat:
            return AldolResult(
                reaction="Aldol condensation",
                product="Crotonaldehyde (CH3CH=CHCHO) (after dehydration).",
                notes="2 ethanal → β-hydroxy aldehyde (aldol) → dehydration on heating gives α,β-unsaturated aldehyde.",
            )
        return AldolResult(
            reaction="Aldol addition",
            product="3-Hydroxybutanal (aldol) (CH3CH(OH)CH2CHO).",
            notes="2 ethanal in dilute base (cold) gives β-hydroxy aldehyde (aldol).",
        )

    # 2 acetone -> diacetone alcohol / mesityl oxide (on heating)
    if _is_acetone(t):
        if heat:
            return AldolResult(
                reaction="Aldol condensation",
                product="Mesityl oxide (CH3COCH=C(CH3)2) (after dehydration).",
                notes="2 acetone → diacetone alcohol → dehydration on heating gives α,β-unsaturated ketone.",
            )
        return AldolResult(
            reaction="Aldol addition",
            product="Diacetone alcohol (4-hydroxy-4-methyl-2-pentanone).",
            notes="2 acetone in dilute base (cold) gives β-hydroxy ketone.",
        )

    # Default safe output if detected but substrate not one of the guaranteed ones
    return AldolResult(
        reaction="Aldol reaction",
        product="β-hydroxy carbonyl compound (aldol product).",
        notes="If heated, dehydration gives α,β-unsaturated carbonyl compound.",
    )
