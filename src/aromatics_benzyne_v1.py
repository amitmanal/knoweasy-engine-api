# src/aromatics_benzyne_v1.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re


def _lc(s: str) -> str:
    return (s or "").lower().strip()


@dataclass(frozen=True)
class BenzyneResult:
    reaction: str
    product: str
    notes: str = ""


_NANH2 = re.compile(r"(nanh2|na\s*nh2|sodamide)", re.IGNORECASE)
_LIQ_NH3 = re.compile(r"(liq(?:uid)?\s*nh3|liquid\s*ammonia|nh3\s*\(l\)|nh3\s*liq)", re.IGNORECASE)
_ARYL_HALIDE = re.compile(r"(chlorobenzene|bromobenzene|fluorobenzene|iodobenzene|aryl\s*halide|c6h5cl|c6h5br)", re.IGNORECASE)
_BENZYNE_WORD = re.compile(r"(benzyne|elimination\s*addition|elimination–addition)", re.IGNORECASE)


def detect_benzyne_v1(text: str) -> bool:
    t = _lc(text)
    if _BENZYNE_WORD.search(t):
        return True
    # Classic conditions: aryl halide + NaNH2 + liquid NH3
    if _ARYL_HALIDE.search(t) and _NANH2.search(t) and (_LIQ_NH3.search(t) or "nh3" in t):
        return True
    return False


def solve_benzyne_v1(question: str) -> Optional[BenzyneResult]:
    t = _lc(question)
    if not detect_benzyne_v1(t):
        return None

    # Exam-safe default: chlorobenzene + NaNH2/NH3(l) -> aniline
    # Works similarly for bromobenzene in classic problems.
    return BenzyneResult(
        reaction="Benzyne mechanism (elimination–addition)",
        product="Aniline (C6H5NH2).",
        notes="Strong base (NaNH2 in liquid NH3) replaces aryl halide by –NH2 via benzyne intermediate.",
    )
