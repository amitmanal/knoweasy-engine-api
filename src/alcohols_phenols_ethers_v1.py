# src/alcohols_phenols_ethers_v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class APE_Result:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_context(t: str) -> bool:
    # Broad triggers
    if _has_any(t, ["alcohol", "phenol", "ether", "roh", "phoh", "williamson", "pcc", "soCl2", "pbr3", "lucas", "dehydration"]):
        return True
    if _has_any(t, ["ethanol", "propanol", "butanol", "t-butanol", "tert-butanol", "phenol", "anisole", "diethyl ether"]):
        return True
    if _has_any(t, ["conc. h2so4", "conc h2so4", "h2so4", "kmno4", "k2cr2o7", "pcc", "cro3", "jones", "acidified"]):
        return True
    return False


def _is_phenol(t: str) -> bool:
    return _has_any(t, ["phenol", "phoh", "c6h5oh"])


def _is_alcohol(t: str) -> bool:
    return _has_any(t, ["alcohol", "roh", "ethanol", "propanol", "butanol", "t-butanol", "tert-butanol", "isopropyl alcohol"])


def _is_ether(t: str) -> bool:
    return _has_any(t, ["ether", "ror", "williamson", "diethyl ether", "anisole"])


def solve_alcohols_phenols_ethers_v1(text: str) -> Optional[APE_Result]:
    """
    Alcohols / Phenols / Ethers v1 (exam-safe):
      - Alcohol dehydration (conc H2SO4, heat) → alkene
      - Alcohol → alkyl halide (SOCl2 / PBr3 / HX)
      - Alcohol oxidation: PCC vs strong oxidants (K2Cr2O7/H+, KMnO4)
      - Williamson ether synthesis
      - Phenol: acidity mention; bromination with Br2 water → 2,4,6-tribromophenol
    """
    t = _lc(text)
    if not _is_context(t):
        return None

    # 1) Phenol bromination (very exam-standard)
    if _is_phenol(t) and _has_any(t, ["br2", "bromine water", "br2 water", "aqueous br2"]):
        return APE_Result(
            reaction="Bromination of phenol (Br2 water)",
            product="Phenol + Br2 (water) → **2,4,6-tribromophenol (white ppt)**.",
            notes="Exam key: phenol is strongly activating; aqueous Br2 gives 2,4,6 substitution without catalyst.",
        )

    # 2) Alcohol dehydration to alkene
    # Specific case: butan-1-ol dehydration gives but-2-ene (major) via Zaitsev elimination
    # Dehydration should not trigger when a carboxylic acid is present (Fischer esterification conditions).
    if _has_any(t, ["butan-1-ol", "1-butanol", "butanol", "ch3ch2ch2ch2oh"]) and _has_any(t, ["conc. h2so4", "conc h2so4", "h2so4"]) and _has_any(t, ["heat", "170", "dehydration", "alkene"]):
        return APE_Result(
            reaction="Dehydration of butan-1-ol",
            product="But-1-ol + conc. H2SO4/heat → **but-2-ene (major)** + but-1-ene (minor) + H2O.",
            notes="Major product follows Zaitsev’s rule (more substituted alkene).",
        )
    # Generic dehydration. Skip if a carboxylic acid is also present (RCOOH), which instead undergoes esterification.
    if _is_alcohol(t) and _has_any(t, ["conc. h2so4", "conc h2so4", "h2so4"]) and _has_any(t, ["heat", "170", "dehydration", "alkene"]):
        # Avoid dehydration if text also contains carboxylic acid keywords (cooh, acetic acid, carboxylic acid)
        if not _has_any(t, ["cooh", "carboxylic acid", "acetic acid", "ethanoic acid", "benzoic acid"]):
            return APE_Result(
                reaction="Dehydration of alcohol (elimination)",
                product="ROH + conc. H2SO4 (heat) → **alkene** + H2O (dehydration).",
                notes="Exam key: higher substituted alkene (Zaitsev) usually major; 3° alcohol dehydrates easiest.",
            )

    # 3) Alcohol → alkyl halide
    if _is_alcohol(t) and _has_any(t, ["socl2", "thionyl chloride"]):
        return APE_Result(
            reaction="Alcohol → alkyl chloride (SOCl2)",
            product="ROH + SOCl2 → **RCl** + SO2 + HCl.",
            notes="Exam key: SOCl2 is preferred (gaseous byproducts drive reaction).",
        )

    if _is_alcohol(t) and _has_any(t, ["pbr3"]):
        return APE_Result(
            reaction="Alcohol → alkyl bromide (PBr3)",
            product="ROH + PBr3 → **RBr** (substitution).",
            notes="Exam key: good for 1°/2° alcohols; avoids rearrangement compared to HX in some cases.",
        )

    if _is_alcohol(t) and _has_any(t, ["hcl", "hbr", "hi", "hx"]) and _has_any(t, ["zncl2", "lucas"]):
        return APE_Result(
            reaction="Lucas reagent (classification)",
            product="ROH + conc. HCl/ZnCl2 → **RCl** (rate: 3° fast > 2° > 1° slow).",
            notes="Exam key: Lucas test distinguishes 1°, 2°, 3° alcohols by turbidity time.",
        )

    # 4) Alcohol oxidation (PCC vs strong oxidants)
    if _is_alcohol(t) and _has_any(t, ["pcc"]):
        return APE_Result(
            reaction="Oxidation of alcohol (PCC)",
            product="1° alcohol + PCC → **aldehyde** (stops). 2° alcohol + PCC → **ketone**. 3° alcohol → no oxidation (no α-H).",
            notes="Exam trap: PCC stops at aldehyde for primary alcohol (does not over-oxidize to acid).",
        )

    if _is_alcohol(t) and _has_any(t, ["kmno4", "k2cr2o7", "acidified", "jones", "cro3", "h2so4"]) and _has_any(t, ["oxidation", "oxidize", "oxida"]):
        return APE_Result(
            reaction="Oxidation of alcohol (strong oxidants)",
            product="1° alcohol + (KMnO4 or K2Cr2O7/H+) → **carboxylic acid**. 2° alcohol → **ketone**. 3° alcohol → generally no oxidation.",
            notes="Exam key: strong oxidants over-oxidize primary alcohols to acids.",
        )

    # 5) Williamson ether synthesis
    if _is_ether(t) and _has_any(t, ["williamson"]) or (_has_any(t, ["ron", "ro-", "alkoxide"]) and _has_any(t, ["rx", "r-x", "alkyl halide", "haloalkane"])):
        return APE_Result(
            reaction="Williamson ether synthesis (SN2)",
            product="RONa + R'X (1°) → **R–O–R' (ether)** + NaX (SN2).",
            notes="Exam trap: best with primary halides; tertiary gives elimination.",
        )

    # 6) Phenol acidity (concept)
    if _is_phenol(t) and _has_any(t, ["acidity", "acidic", "more acidic", "pka"]):
        return APE_Result(
            reaction="Phenol acidity (resonance-stabilized phenoxide)",
            product="Phenol is **more acidic than alcohols** because phenoxide ion is resonance-stabilized.",
            notes="Exam key: -I/-M groups on ring affect acidity; EWG increase acidity.",
        )

    return None
