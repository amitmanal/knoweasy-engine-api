# src/aromatics_gattermann_koch_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class GKResult:
    reaction: str
    product: str
    notes: str = ""


_BENZENE = re.compile(r"\bbenzene\b|c6h6", re.IGNORECASE)
_CO = re.compile(r"\bco\b|carbon\s*monoxide", re.IGNORECASE)
_HCL = re.compile(r"\bhcl\b|hydrogen\s*chloride", re.IGNORECASE)
_ALCL3 = re.compile(r"\balcl3\b", re.IGNORECASE)
_CUCL = re.compile(r"\bcucl\b|\bcucl2\b|cu\s*cl", re.IGNORECASE)

_GK = re.compile(r"gattermann[-\s]*koch", re.IGNORECASE)


def detect_gattermann_koch_v1(text: str) -> bool:
    t = _lc(text)
    if _GK.search(t):
        return True
    # Typical reagent set
    return bool(_BENZENE.search(t) and _CO.search(t) and _HCL.search(t) and _ALCL3.search(t) and _CUCL.search(t))


def solve_gattermann_koch_v1(question: str) -> Optional[GKResult]:
    t = _lc(question)
    if not detect_gattermann_koch_v1(t):
        return None

    return GKResult(
        reaction="Gattermann–Koch reaction",
        product="Benzaldehyde (C6H5CHO).",
        notes="Formylation of benzene using CO + HCl in presence of AlCl3/CuCl.",
    )
