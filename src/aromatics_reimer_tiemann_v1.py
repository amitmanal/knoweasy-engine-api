# src/aromatics_reimer_tiemann_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class ReimerTiemannResult:
    reaction: str
    product: str
    notes: str = ""


_PHENOL = re.compile(r"(phenol|c6h5oh)", re.IGNORECASE)
_CHCL3 = re.compile(r"(chcl3|chloroform)", re.IGNORECASE)
_BASE = re.compile(r"(naoh|koh|alkaline|basic|oh\-)", re.IGNORECASE)


def detect_reimer_tiemann_v1(text: str) -> bool:
    t = _lc(text)
    # Classic conditions: phenol + CHCl3 + base
    return bool(_PHENOL.search(t) and _CHCL3.search(t) and _BASE.search(t))


def solve_reimer_tiemann_v1(question: str) -> Optional[ReimerTiemannResult]:
    t = _lc(question)
    if not detect_reimer_tiemann_v1(t):
        return None

    return ReimerTiemannResult(
        reaction="Reimer–Tiemann reaction",
        product="o-Hydroxybenzaldehyde (salicylaldehyde) (ortho major; para minor).",
        notes="CHCl3/NaOH generates :CCl2 (dichlorocarbene); formylation occurs mainly at ortho position.",
    )
