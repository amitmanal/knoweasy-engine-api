# src/carboxy_acid_derivatives_ester_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class EsterResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _has_acid(t: str) -> bool:
    # Carboxylic acid cues
    return _has_any(t, ["carboxylic acid", "acid", "cooh", "rcooh", "acetic acid", "ethanoic acid", "benzoic acid"]) or bool(
        re.search(r"\bch3cooh\b|\bc6h5cooh\b|\brcooh\b", t)
    )


def _has_alcohol(t: str) -> bool:
    return _has_any(t, ["alcohol", "roh", "methanol", "ethanol", "propanol", "butanol"]) or bool(
        re.search(r"\bch3oh\b|\bc2h5oh\b|\bc3h7oh\b|\broh\b", t)
    )


def _has_ester(t: str) -> bool:
    return _has_any(t, ["ester", "rcoor", "coor", "ethyl acetate", "methyl acetate", "ethyl benzoate", "acetate"]) or bool(
        re.search(r"\bch3cooc2h5\b|\bch3cooch3\b|\bc6h5cooc2h5\b|\brcoor\b", t)
    )


def _is_fischer_conditions(t: str) -> bool:
    # acid catalyzed, reflux, conc. H2SO4, etc.
    if _has_any(t, ["fischer", "conc h2so4", "concentrated h2so4", "h2so4", "h+", "acid catalyst", "reflux"]):
        return True
    return False


def _is_acidic_hydrolysis(t: str) -> bool:
    return _has_any(t, ["acidic hydrolysis", "h+", "h3o", "h₃o", "dil. hcl", "dilute hcl", "dil. h2so4", "dilute h2so4"])


def _is_basic_hydrolysis(t: str) -> bool:
    return _has_any(t, ["naoh", "koh", "base hydrolysis", "alkaline hydrolysis", "saponification"])


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bethanol\b|\bc2h5oh\b", t) and re.search(r"\bacetic acid\b|\bethanoic acid\b|\bch3cooh\b", t):
        return "acetic_acid_ethanol"
    if re.search(r"\bethyl acetate\b|\bch3cooc2h5\b", t):
        return "ethyl_acetate"
    if re.search(r"\bmethyl acetate\b|\bch3cooch3\b", t):
        return "methyl_acetate"
    if re.search(r"\bethyl benzoate\b|\bc6h5cooc2h5\b", t):
        return "ethyl_benzoate"
    return None


def solve_ester_v1(text: str) -> Optional[EsterResult]:
    """
    Ester v1 (exam-safe):
      - Fischer esterification: RCOOH + ROH (conc. H2SO4, heat) ⇌ RCOOR + H2O (reversible)
      - Acidic hydrolysis: RCOOR + H2O/H+ ⇌ RCOOH + ROH (reversible)
      - Basic hydrolysis (saponification): RCOOR + NaOH -> RCOO-Na+ + ROH (irreversible in exam)
    """
    t = _lc(text)

    # Trigger if ester topic is present
    trig = _has_any(t, ["esterification", "fischer", "saponification", "ester hydrolysis", "hydrolysis of ester", "rcoor"])
    if not trig and not (_has_ester(t) or (_has_acid(t) and _has_alcohol(t))):
        return None

    key = _substrate_key(t)

    # 1) Fischer esterification (acid + alcohol + acid catalyst)
    if (_has_acid(t) and _has_alcohol(t)) and (_is_fischer_conditions(t) or "esterification" in t or "fischer" in t):
        if key == "acetic_acid_ethanol":
            return EsterResult(
                reaction="Fischer esterification (reversible)",
                product="CH3COOH (acetic acid) + C2H5OH (ethanol)  --(conc. H2SO4, heat)⇌  **CH3COOC2H5 (ethyl acetate)** + H2O.",
                notes="Exam trap: Fischer is reversible; conc. H2SO4 removes water and pushes equilibrium to ester.",
            )
        return EsterResult(
            reaction="Fischer esterification (reversible)",
            product="General: RCOOH + ROH  --(conc. H2SO4, heat)⇌  **RCOOR (ester)** + H2O.",
            notes="Reversible equilibrium (push forward by removing water / excess reactant).",
        )

    # 2) Hydrolysis of ester
    if _has_ester(t) and ("hydrolysis" in t or _is_acidic_hydrolysis(t) or _is_basic_hydrolysis(t)):
        if _is_basic_hydrolysis(t):
            # saponification: carboxylate salt + alcohol
            if key == "ethyl_acetate":
                return EsterResult(
                    reaction="Base hydrolysis (saponification) — irreversible (exam)",
                    product="CH3COOC2H5 (ethyl acetate) + NaOH → **CH3COO⁻Na⁺ (sodium acetate)** + C2H5OH (ethanol).",
                    notes="Exam key: basic hydrolysis gives carboxylate salt; effectively irreversible.",
                )
            return EsterResult(
                reaction="Base hydrolysis (saponification) — irreversible (exam)",
                product="General: RCOOR' + NaOH → **RCOO⁻Na⁺ (carboxylate salt)** + R'OH.",
                notes="Trap: product is carboxylate salt (not free acid) in basic medium.",
            )

        # acidic hydrolysis
        if key == "ethyl_acetate":
            return EsterResult(
                reaction="Acidic hydrolysis of ester (reversible)",
                product="CH3COOC2H5 + H2O/H+ ⇌ **CH3COOH (acetic acid)** + C2H5OH (ethanol).",
                notes="Acidic hydrolysis is reversible (equilibrium).",
            )
        if key == "ethyl_benzoate":
            return EsterResult(
                reaction="Acidic hydrolysis of ester (reversible)",
                product="C6H5COOC2H5 + H2O/H+ ⇌ **C6H5COOH (benzoic acid)** + C2H5OH.",
                notes="Reversible; compare with saponification (irreversible).",
            )

        return EsterResult(
            reaction="Ester hydrolysis",
            product="Acidic: RCOOR' + H2O/H+ ⇌ RCOOH + R'OH (reversible). Basic: RCOOR' + NaOH → RCOO⁻Na⁺ + R'OH (irreversible in exam).",
            notes="Big trap: acidic hydrolysis is reversible, basic hydrolysis gives salt (drives reaction).",
        )

    # If only ester mentioned, give overview
    if _has_ester(t):
        return EsterResult(
            reaction="Ester reactions (overview)",
            product="Esterification: RCOOH + ROH (conc. H2SO4, heat) ⇌ RCOOR + H2O. Hydrolysis: acidic (reversible) vs basic (saponification, gives RCOO⁻Na⁺).",
            notes="Do not confuse acid chloride ester formation (fast, not equilibrium) with Fischer esterification (equilibrium).",
        )

    # If asked generally about making ester from acid + alcohol
    if _has_acid(t) and _has_alcohol(t):
        return EsterResult(
            reaction="Fischer esterification (reversible)",
            product="General: RCOOH + ROH  --(conc. H2SO4, heat)⇌  RCOOR + H2O.",
            notes="Push forward by removing water / excess alcohol or acid catalyst.",
        )

    return None
