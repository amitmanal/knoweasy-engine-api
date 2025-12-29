# src/carbonyl_cannizzaro_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class CannizzaroResult:
    reaction: str
    product: str
    notes: str = ""


def _is_formaldehyde(t: str) -> bool:
    return ("formaldehyde" in t) or ("methanal" in t) or ("hcho" in t)


def _is_benzaldehyde(t: str) -> bool:
    return ("benzaldehyde" in t) or ("c6h5cho" in t)


def detect_cannizzaro_v1(text: str) -> bool:
    t = _lc(text)

    has_base = ("naoh" in t or "koh" in t) and ("conc" in t or "concentrated" in t)
    aldehyde = ("aldehyde" in t) or _is_formaldehyde(t) or _is_benzaldehyde(t)

    if "cannizzaro" in t:
        return True

    return has_base and aldehyde


def solve_cannizzaro_v1(question: str) -> Optional[CannizzaroResult]:
    t = _lc(question)
    if not detect_cannizzaro_v1(t):
        return None

    # Formaldehyde
    if _is_formaldehyde(t):
        return CannizzaroResult(
            reaction="Cannizzaro reaction",
            product="Methanol (CH3OH) and sodium formate (→ formic acid on acidification).",
            notes="Formaldehyde has no α-hydrogen; undergoes Cannizzaro in conc. base.",
        )

    # Benzaldehyde
    if _is_benzaldehyde(t):
        return CannizzaroResult(
            reaction="Cannizzaro reaction",
            product="Benzyl alcohol (C6H5CH2OH) and sodium benzoate (→ benzoic acid on acidification).",
            notes="Aromatic aldehydes without α-hydrogen undergo Cannizzaro reaction.",
        )

    # Generic safe output
    return CannizzaroResult(
        reaction="Cannizzaro reaction",
        product="Alcohol + carboxylate salt (from disproportionation of aldehyde).",
        notes="Occurs for aldehydes lacking α-hydrogen in strong base.",
    )
