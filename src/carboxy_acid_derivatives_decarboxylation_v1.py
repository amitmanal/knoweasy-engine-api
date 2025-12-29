# src/carboxy_acid_derivatives_decarboxylation_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class DecarbResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_carboxylate(t: str) -> bool:
    return _has_any(t, ["rcoona", "rcoo-na", "sodium salt", "carboxylate"]) or bool(
        re.search(r"\bch3coona\b|\bc6h5coona\b", t)
    )


def _is_soda_lime(t: str) -> bool:
    return _has_any(t, ["soda lime", "naoh/cao", "naoh + cao", "cao", "sodalime"])


def _is_kolbe(t: str) -> bool:
    return _has_any(t, ["kolbe", "electrolysis"]) or _has_any(t, ["electrolytic", "electrolyse"])


def _is_hvz(t: str) -> bool:
    return _has_any(t, ["hvz", "hell-volhard-zelinsky", "hell volhard zelinsky"]) or (
        _has_any(t, ["br2", "cl2"]) and _has_any(t, ["p", "red p", "pbr3"])
    )


def solve_decarboxylation_v1(text: str) -> Optional[DecarbResult]:
    """
    Decarboxylation & HVZ (exam-safe):
      - Soda lime decarboxylation: RCOO-Na+ --(NaOH/CaO, heat)--> RH (one C less)
      - Kolbe electrolysis: 2 RCOO- -> R–R (symmetrical alkane)
      - HVZ: RCH2COOH --(Br2/P or Cl2/P)--> RCHXCOOH (alpha-halogen acid)
    """
    t = _lc(text)

    # 1) Soda lime decarboxylation
    if _is_carboxylate(t) and _is_soda_lime(t):
        return DecarbResult(
            reaction="Soda lime decarboxylation",
            product="RCOO⁻Na⁺ --(NaOH/CaO, heat)→ **RH** + Na2CO3  (one carbon less).",
            notes="Exam trap: product is alkane with one carbon less than acid.",
        )

    # 2) Kolbe electrolysis
    if _is_carboxylate(t) and _is_kolbe(t):
        return DecarbResult(
            reaction="Kolbe electrolysis",
            product="2 RCOO⁻Na⁺ --(electrolysis)→ **R–R (symmetrical alkane)** + 2 CO2.",
            notes="Exam trap: only symmetrical alkanes form; odd chains do not mix.",
        )

    # 3) HVZ reaction
    if _has_any(t, ["cooh", "carboxylic acid", "acid"]) and _is_hvz(t):
        return DecarbResult(
            reaction="HVZ reaction (α-halogenation of carboxylic acids)",
            product="RCH2COOH --(X2 / red P)→ **RCHXCOOH (α-halo acid)**.",
            notes="HVZ requires α-hydrogen; product is α-halogenated acid.",
        )

    return None
