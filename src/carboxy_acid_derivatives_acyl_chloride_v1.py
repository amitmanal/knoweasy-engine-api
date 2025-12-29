# src/carboxy_acid_derivatives_acyl_chloride_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class AcylChlorideResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_acyl_chloride_present(t: str) -> bool:
    # names + formula cues
    if _has_any(t, ["acid chloride", "acyl chloride", "alkanoyl chloride", "aroyl chloride"]):
        return True
    if _has_any(t, ["cocl", "co cl", "co-cl", "co–cl", "co—cl"]):
        return True
    if re.search(r"\bch3cocl\b|\bacetyl chloride\b|\bethanoyl chloride\b", t):
        return True
    if re.search(r"\bc6h5cocl\b|\bbenzoyl chloride\b", t):
        return True
    if re.search(r"\bc2h5cocl\b|\bpropanoyl chloride\b|\bpropionyl chloride\b", t):
        return True
    return False


def _is_hydrolysis(t: str) -> bool:
    return _has_any(t, ["h2o", "water", "hydrolysis", "moist", "aq", "aqueous"])


def _is_alcoholysis(t: str) -> bool:
    # alcohol / ROH / ethanol / methanol etc.
    if _has_any(t, ["alcohol", "roh", "methanol", "ethanol", "propanol", "butanol"]):
        return True
    if re.search(r"\bch3oh\b|\bc2h5oh\b|\bc3h7oh\b", t):
        return True
    return False


def _is_ammonolysis(t: str) -> bool:
    # NH3 or amines
    return _has_any(t, ["nh3", "ammonia", "amine", "rnh2", "aniline", "methylamine", "ethylamine"])


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bacetyl chloride\b|\bethanoyl chloride\b|\bch3cocl\b", t):
        return "acetyl_chloride"
    if re.search(r"\bbenzoyl chloride\b|\bc6h5cocl\b", t):
        return "benzoyl_chloride"
    if re.search(r"\bpropanoyl chloride\b|\bpropionyl chloride\b|\bc2h5cocl\b", t):
        return "propanoyl_chloride"
    return None


def solve_acyl_chloride_v1(text: str) -> Optional[AcylChlorideResult]:
    """
    Acid chloride (RCOCl) reactions (exam-safe):
      - Hydrolysis: RCOCl + H2O -> RCOOH + HCl
      - Alcoholysis: RCOCl + ROH (pyridine/base) -> RCOOR + HCl
      - Ammonolysis: RCOCl + NH3 / RNH2 -> amide + HCl (base helps)
    """
    t = _lc(text)
    if not _is_acyl_chloride_present(t):
        return None

    hydro = _is_hydrolysis(t)
    alco = _is_alcoholysis(t)
    ammo = _is_ammonolysis(t)

    # if no reagent clue, still answer general behavior
    key = _substrate_key(t)

    # Specific deterministic common examples
    if key == "acetyl_chloride":
        if hydro:
            return AcylChlorideResult(
                reaction="Acid chloride hydrolysis",
                product="CH3COCl (acetyl chloride) + H2O → **CH3COOH (acetic acid)** + HCl.",
                notes="Very fast; acid chloride is most reactive acyl derivative. HCl is formed.",
            )
        if alco:
            return AcylChlorideResult(
                reaction="Acid chloride alcoholysis (ester formation)",
                product="CH3COCl + ROH (often pyridine/base) → **CH3COOR (ester)** + HCl.",
                notes="Exam trap: base (pyridine) used to neutralize HCl.",
            )
        if ammo:
            return AcylChlorideResult(
                reaction="Acid chloride ammonolysis (amide formation)",
                product="CH3COCl + NH3 → **CH3CONH2 (acetamide)** + HCl (often captured by excess NH3/base).",
                notes="Amide formation is very fast; HCl byproduct must be neutralized.",
            )

    if key == "benzoyl_chloride":
        if hydro:
            return AcylChlorideResult(
                reaction="Acid chloride hydrolysis",
                product="C6H5COCl (benzoyl chloride) + H2O → **C6H5COOH (benzoic acid)** + HCl.",
                notes="Fast nucleophilic acyl substitution.",
            )
        if alco:
            return AcylChlorideResult(
                reaction="Acid chloride alcoholysis (ester formation)",
                product="C6H5COCl + C2H5OH (ethanol) → **C6H5COOC2H5 (ethyl benzoate)** + HCl (base/pyridine helps).",
                notes="Esterification from acid chloride is easier than from acid (no equilibrium issue).",
            )
        if ammo:
            return AcylChlorideResult(
                reaction="Acid chloride ammonolysis (amide formation)",
                product="C6H5COCl + NH3 → **C6H5CONH2 (benzamide)** + HCl.",
                notes="Schotten–Baumann conditions: base present to neutralize HCl (exam phrase).",
            )

    # Generic rules
    if hydro:
        return AcylChlorideResult(
            reaction="Acid chloride hydrolysis",
            product="General: RCOCl + H2O → **RCOOH (carboxylic acid)** + HCl.",
            notes="Exam key: acid chlorides hydrolyze very rapidly; HCl is produced.",
        )

    if alco:
        return AcylChlorideResult(
            reaction="Acid chloride alcoholysis (ester formation)",
            product="General: RCOCl + ROH (pyridine/base) → **RCOOR (ester)** + HCl.",
            notes="Exam trap: include base (pyridine) to trap HCl; product is ester.",
        )

    if ammo:
        return AcylChlorideResult(
            reaction="Acid chloride ammonolysis (amide formation)",
            product="General: RCOCl + NH3 / RNH2 → **amide** (RCONH2 / RCONHR) + HCl.",
            notes="Use excess NH3/base to neutralize HCl; otherwise amine gets protonated.",
        )

    return AcylChlorideResult(
        reaction="Acid chloride reactions (overview)",
        product="RCOCl is highly reactive: +H2O → acid; +ROH → ester; +NH3/RNH2 → amide (HCl formed).",
        notes="Common mistake: forgetting HCl byproduct / missing base (pyridine).",
    )
