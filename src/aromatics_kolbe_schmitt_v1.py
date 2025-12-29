# src/aromatics_kolbe_schmitt_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class KolbeSchmittResult:
    reaction: str
    product: str
    notes: str = ""


_PHENOL = re.compile(r"(phenol|c6h5oh)", re.IGNORECASE)
_SODIUM_PHENOXIDE = re.compile(r"(sodium\s*phenoxide|c6h5ona|phenoxide|nao\-)", re.IGNORECASE)
_CO2 = re.compile(r"(co2|carbon\s*dioxide|dry\s*ice)", re.IGNORECASE)
_PRESSURE = re.compile(r"(pressure|high\s*pressure|under\s*pressure)", re.IGNORECASE)
_ACID_WORKUP = re.compile(r"(h\+|acidification|hcl|dil\.?\s*hcl|acid\s*workup)", re.IGNORECASE)


def detect_kolbe_schmitt_v1(text: str) -> bool:
    t = _lc(text)
    # typical: sodium phenoxide + CO2 (pressure) + acidification
    has_phenol_system = bool(_SODIUM_PHENOXIDE.search(t) or (_PHENOL.search(t) and "naoh" in t))
    has_co2 = bool(_CO2.search(t))
    has_pressure = bool(_PRESSURE.search(t)) or "pressure" in t
    # acid workup is often implied; we'll accept if present or not
    return has_phenol_system and has_co2 and has_pressure


def solve_kolbe_schmitt_v1(question: str) -> Optional[KolbeSchmittResult]:
    t = _lc(question)
    if not detect_kolbe_schmitt_v1(t):
        return None

    return KolbeSchmittResult(
        reaction="Kolbe–Schmitt reaction",
        product="Salicylic acid (o-hydroxybenzoic acid) (ortho major).",
        notes="Sodium phenoxide reacts with CO2 under pressure to give salicylate; acidification gives salicylic acid.",
    )
