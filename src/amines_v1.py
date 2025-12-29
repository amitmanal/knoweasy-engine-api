# src/amines_v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class AmineResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_context(t: str) -> bool:
    if _has_any(t, ["amine", "aniline", "benzylamine", "methylamine", "ethylamine", "nh2", "nr2", "diazotization", "nitrous acid", "na no2", "nanoid", "carbylamine", "isocyanide", "gabriel", "hofmann", "basicity"]):
        return True
    if _has_any(t, ["sncl2", "reduction of nitro", "nitro to amine", "h2/pd", "fe/hcl", "sn/hcl"]):
        return True
    if _has_any(t, ["c6h5nh2", "c6h5-nh2", "c6h5nh3"]):
        return True
    return False


def solve_amines_v1(text: str) -> Optional[AmineResult]:
    """
    Amines v1 (exam-safe):
      - Basicity order (aliphatic vs aromatic; effect of resonance)
      - Carbylamine test (1° amine only)
      - Diazotization concept trigger (links to existing diazonium module)
      - Gabriel phthalimide synthesis (1° alkyl amine)
      - Hofmann bromamide (amide -> 1° amine with one carbon less) rule-level
      - Nitro reduction to aniline (rule-level)
    """
    t = _lc(text)
    if not _is_context(t):
        return None

    # 1) Carbylamine test
    if _has_any(t, ["carbylamine", "isocyanide", "foul smell"]) or (_has_any(t, ["chcl3"]) and _has_any(t, ["koh", "alc koh", "alcoholic koh"])):
        return AmineResult(
            reaction="Carbylamine test (isocyanide test)",
            product="Only **1° amines** give: RNH2 + CHCl3 + alc KOH → **R-NC (isocyanide)** (foul smell).",
            notes="Exam key: 1° amine only; 2°/3° do NOT give carbylamine test.",
        )

    # 2) Basicity order
    if _has_any(t, ["basicity", "more basic", "most basic", "least basic", "order of basic strength", "arrange", "pkb", "pKb"]):
        if _has_any(t, ["aniline", "aryl", "c6h5nh2", "aromatic amine"]):
            return AmineResult(
                reaction="Basicity of amines (aryl vs alkyl)",
                product="**Aliphatic amines > NH3 > aniline (aryl amine)** (aniline is less basic due to resonance delocalization of lone pair).",
                notes="EWG on ring decreases basicity; EDG increases. In water: solvation can affect 1°/2°/3° order.",
            )
        return AmineResult(
            reaction="Basicity of aliphatic amines (aqueous, rule-level)",
            product="In water (common exam): **2° > 1° > 3° > NH3** (balance of +I effect and solvation).",
            notes="Gas phase often follows 3° > 2° > 1° > NH3 (no solvation).",
        )

    # 3) Nitro reduction to amine (rule-level)
    if _has_any(t, ["nitro", "no2"]) and _has_any(t, ["reduction", "reduce", "sn/hcl", "fe/hcl", "sncl2", "h2/pd", "h2/ni"]):
        return AmineResult(
            reaction="Reduction of nitro compounds to amines",
            product="Ar-NO2 (or R-NO2) + reducing agent (Sn/HCl or Fe/HCl or H2/Pd) → **Ar-NH2 / R-NH2 (amine)**.",
            notes="Exam key: nitro → amine (aniline from nitrobenzene).",
        )

    # 4) Gabriel phthalimide synthesis
    if _has_any(t, ["gabriel", "phthalimide"]):
        return AmineResult(
            reaction="Gabriel phthalimide synthesis",
            product="Phthalimide (K salt) + 1° R-X → N-alkyl phthalimide → hydrolysis → **1° alkyl amine (RNH2)**.",
            notes="Exam trap: gives primary alkyl amines; not for aryl halides; not for 2°/3° amines.",
        )

    # 5) Hofmann bromamide (amide -> amine, one carbon less)
    if _has_any(t, ["hofmann", "bromamide"]) or (_has_any(t, ["br2"]) and _has_any(t, ["naoh"]) and _has_any(t, ["amide", "rconh2"])):
        return AmineResult(
            reaction="Hofmann bromamide (Hofmann rearrangement)",
            product="RCONH2 + Br2/NaOH → **RNH2 (1° amine, one carbon less)** + CO2.",
            notes="Exam key: carbon chain shortens by 1.",
        )

    # 6) Diazotization concept
    if _has_any(t, ["diazotization", "na no2", "nano2", "hno2", "nitrous acid", "0-5", "0 to 5"]) and _has_any(t, ["aniline", "aryl amine", "primary aromatic amine"]):
        return AmineResult(
            reaction="Diazotization (primary aromatic amine)",
            product="ArNH2 + NaNO2/HCl (0–5 °C) → **ArN2+Cl− (diazonium salt)**.",
            notes="Exam key: keep 0–5 °C; aromatic diazonium is stable at low temperature.",
        )

    return None
