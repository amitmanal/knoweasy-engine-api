# src/carboxy_acid_derivatives_amide_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class AmideResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _has_amide(t: str) -> bool:
    # amide keyword or common cues
    if _has_any(t, ["amide", "carboxamide", "conh2", "conhr", "conr2"]):
        return True
    # common names/formula
    if re.search(r"\bacetamide\b|\bch3conh2\b|\bbenzamide\b|\bc6h5conh2\b", t):
        return True
    return False


def _is_hydrolysis(t: str) -> bool:
    return _has_any(t, ["hydrolysis", "h2o", "water", "aq", "aqueous"])


def _is_acidic(t: str) -> bool:
    return _has_any(t, ["h+", "h3o", "h₃o", "dil. hcl", "dilute hcl", "dil. h2so4", "dilute h2so4", "acidic"])


def _is_basic(t: str) -> bool:
    return _has_any(t, ["naoh", "koh", "base", "alkaline"])


def _is_dehydration(t: str) -> bool:
    # dehydration reagents: P2O5, SOCl2, POCl3
    return _has_any(t, ["p2o5", "p2o₅", "phosphorus pentoxide", "pocl3", "thionyl chloride", "socl2", "dehydration", "dehydrate"])


def _is_hofmann(t: str) -> bool:
    # Hofmann bromamide reagents: Br2/NaOH
    if _has_any(t, ["hofmann", "bromamide"]):
        return True
    if _has_any(t, ["br2", "bromine"]) and _has_any(t, ["naoh", "koh", "base"]):
        return True
    return False


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bacetamide\b|\bch3conh2\b", t):
        return "acetamide"
    if re.search(r"\bbenzamide\b|\bc6h5conh2\b", t):
        return "benzamide"
    return None


def solve_amide_v1(text: str) -> Optional[AmideResult]:
    """
    Amide v1 (exam-safe):
      - Hydrolysis:
          Acidic: RCONH2 + H2O/H+ -> RCOOH + NH4+ (or NH4Cl etc.)
          Basic:  RCONH2 + NaOH -> RCOO-Na+ + NH3 (salt in base)
      - Dehydration: RCONH2 --(P2O5 / SOCl2 / POCl3)--> RCN (nitrile)
      - Hofmann bromamide: RCONH2 + Br2/NaOH -> RNH2 (one carbon less) + byproducts
    """
    t = _lc(text)
    if not _has_amide(t) and not _has_any(t, ["hofmann", "bromamide"]) and not ("conh2" in t):
        return None

    key = _substrate_key(t)

    # 1) Hofmann bromamide (priority because reagents unique and exam-high)
    if _is_hofmann(t):
        if key == "acetamide":
            return AmideResult(
                reaction="Hofmann bromamide (amide → amine, one carbon less)",
                product="CH3CONH2 (acetamide) + Br2/NaOH → **CH3NH2 (methylamine)** (one C less than acid) + byproducts.",
                notes="Exam trap: carbon chain decreases by 1 (loss of carbonyl carbon).",
            )
        if key == "benzamide":
            return AmideResult(
                reaction="Hofmann bromamide (amide → amine, one carbon less)",
                product="C6H5CONH2 (benzamide) + Br2/NaOH → **C6H5NH2 (aniline)** + byproducts.",
                notes="Key: one-carbon shorter amine (carbonyl carbon removed).",
            )
        return AmideResult(
            reaction="Hofmann bromamide (amide → amine, one carbon less)",
            product="General: RCONH2 + Br2/NaOH → **RNH2** (one carbon less) + byproducts.",
            notes="Trap: do NOT write nitrile; do NOT keep same carbon count.",
        )

    # 2) Dehydration to nitrile
    if _is_dehydration(t):
        if key == "acetamide":
            return AmideResult(
                reaction="Dehydration of amide → nitrile",
                product="CH3CONH2 --(P2O5 / SOCl2 / POCl3)→ **CH3CN (acetonitrile)**.",
                notes="Exam key: dehydration converts amide to nitrile.",
            )
        if key == "benzamide":
            return AmideResult(
                reaction="Dehydration of amide → nitrile",
                product="C6H5CONH2 --(P2O5 / SOCl2 / POCl3)→ **C6H5CN (benzonitrile)**.",
                notes="Amide dehydration gives nitrile.",
            )
        return AmideResult(
            reaction="Dehydration of amide → nitrile",
            product="General: RCONH2 --(P2O5 / SOCl2 / POCl3)→ **RCN (nitrile)**.",
            notes="Trap: dehydration gives nitrile (not amine).",
        )

    # 3) Hydrolysis (acidic vs basic)
    if _is_hydrolysis(t) or _is_acidic(t) or _is_basic(t) or "hydrolysis" in t:
        if _is_basic(t) and not _is_acidic(t):
            # base hydrolysis gives carboxylate salt + NH3
            if key == "acetamide":
                return AmideResult(
                    reaction="Basic hydrolysis of amide",
                    product="CH3CONH2 + NaOH → **CH3COO⁻Na⁺ (sodium acetate)** + NH3.",
                    notes="In base, product is carboxylate salt (not free acid).",
                )
            return AmideResult(
                reaction="Basic hydrolysis of amide",
                product="General: RCONH2 + NaOH → **RCOO⁻Na⁺ (carboxylate salt)** + NH3.",
                notes="Trap: do not write RCOOH in basic medium.",
            )

        # acidic hydrolysis (default if acidic mentioned or mixed)
        if key == "acetamide":
            return AmideResult(
                reaction="Acidic hydrolysis of amide",
                product="CH3CONH2 + H2O/H+ → **CH3COOH (acetic acid)** + NH4+ (e.g., NH4Cl).",
                notes="Acidic hydrolysis gives free acid; ammonia becomes ammonium salt.",
            )
        return AmideResult(
            reaction="Acidic hydrolysis of amide",
            product="General: RCONH2 + H2O/H+ → **RCOOH** + NH4+ (ammonium salt).",
            notes="Trap: acidic hydrolysis gives carboxylic acid; basic gives carboxylate salt.",
        )

    # If only “amide” asked, give overview
    return AmideResult(
        reaction="Amide reactions (overview)",
        product="Hydrolysis: acidic → RCOOH + NH4+; basic → RCOO⁻Na⁺ + NH3. Dehydration (P2O5/SOCl2/POCl3) → nitrile (RCN). Hofmann (Br2/NaOH) → amine (one C less).",
        notes="Key traps: Hofmann shortens chain by 1; dehydration gives nitrile; base hydrolysis gives salt.",
    )
