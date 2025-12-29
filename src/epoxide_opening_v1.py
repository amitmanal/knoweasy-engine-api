"""
Epoxide opening v1
This solver handles ring-opening reactions of epoxides (oxiranes).  It specifically
recognizes propylene oxide and generic epoxide ring opening under acidic or basic
conditions and provides the resulting diol along with a note on the regioselectivity.

Exam conventions:
  - Under acidic conditions (H⁺/H₂O), the nucleophile attacks the more substituted
    carbon of the epoxide ring, leading to a trans diol.  For propylene oxide,
    both acidic and basic hydrolysis ultimately yield propane‑1,2‑diol.
  - Under basic conditions (OH⁻), the nucleophile attacks the less substituted
    carbon.  Again, propylene oxide hydrolysis gives propane‑1,2‑diol.
  - If conditions are not specified, we prompt the student to specify acidic or
    basic conditions, as the regiochemical outcome depends on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EpoxideOpeningResult:
    reaction: str
    product: str
    notes: str = ""
    tip: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def solve_epoxide_opening_v1(text: str) -> Optional[EpoxideOpeningResult]:
    t = _lc(text)
    # Only trigger if epoxide/oxide words present.  Exclude 'peroxide' which contains 'oxide' but refers to hydroperoxides, not epoxides.
    if "peroxide" in t:
        return None
    if not _has_any(t, ["epoxide", "oxide", "oxirane"]):
        return None

    # Check for acidic vs basic conditions
    acidic = _has_any(t, ["h+", "h3o+", "acid", "acidic", "h2so4", "hydronium", "hcl", "h2o/acid"])
    basic = _has_any(t, ["oh-", "naoh", "koh", "base", "basic", "alcoholate"])

    # Specific substrate: propylene oxide (also called propene oxide)
    if _has_any(t, ["propylene oxide", "propene oxide", "epoxide of propene", "c3h6o"]):
        # Both acidic and basic hydrolysis of propylene oxide give the same diol
        if acidic:
            return EpoxideOpeningResult(
                reaction="Propylene oxide ring opening (acidic)",
                product="propane-1,2-diol",
                notes="In acidic conditions, nucleophilic attack occurs at the more substituted carbon of the epoxide, yielding propane-1,2-diol.",
                tip="Under acidic conditions, nucleophilic attack occurs at the more substituted carbon of the epoxide.",
            )
        if basic:
            return EpoxideOpeningResult(
                reaction="Propylene oxide ring opening (basic)",
                product="propane-1,2-diol",
                notes="In basic conditions, nucleophilic attack occurs at the less substituted carbon of the epoxide, yielding propane-1,2-diol.",
                tip="Under basic conditions, nucleophilic attack occurs at the less substituted carbon of the epoxide.",
            )
        # Ambiguous conditions
        return EpoxideOpeningResult(
            reaction="Propylene oxide ring opening",
            product="Please specify acidic or basic conditions for epoxide ring opening.",
            notes="Regioselectivity depends on the reaction medium (acidic vs basic).",
            tip="Specify whether conditions are acidic or basic.",
        )

    # Generic epoxide ring opening if no specific substrate identified
    if acidic:
        return EpoxideOpeningResult(
            reaction="Epoxide ring opening (acidic)",
            product="trans‑diol",
            notes="In acidic conditions, nucleophilic attack occurs at the more substituted carbon, giving a trans diol.",
            tip="Acidic conditions favour attack at the more substituted carbon.",
        )
    if basic:
        return EpoxideOpeningResult(
            reaction="Epoxide ring opening (basic)",
            product="trans‑diol",
            notes="In basic conditions, nucleophilic attack occurs at the less substituted carbon, giving a trans diol.",
            tip="Basic conditions favour attack at the less substituted carbon.",
        )
    # Ambiguous generic query
    return EpoxideOpeningResult(
        reaction="Epoxide ring opening",
        product="Need to specify acidic or basic conditions",
        notes="The regiochemical outcome depends on whether the medium is acidic or basic.",
        tip="Specify whether conditions are acidic or basic.",
    )