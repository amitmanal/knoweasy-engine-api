# src/alkyl_halides_sn1_sn2_e1_e2_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class AlkylHalideResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_alkyl_halide_context(t: str) -> bool:
    # Strong triggers
    if _has_any(t, ["alkyl halide", "haloalkane", "halogenoalkane"]):
        return True

    # Named reactions directly
    if _has_any(t, ["wurtz", "finkelstein", "swarts"]):
        return True

    # SN/E labels
    if _has_any(t, ["sn1", "sn2", "e1", "e2", "substitution", "elimination", "dehydrohalogenation"]):
        return True

    # Common reagents/conditions used specifically with alkyl halides in Class 11
    if _has_any(t, ["aq koh", "aqueous koh", "alc koh", "alcoholic koh", "ethanolic koh", "dry ether", "acetone"]) and _has_any(
        t, ["br", "cl", "iod", "bromo", "chloro", "iodo", "rx", "r-x", "r–x"]
    ):
        return True

    # Some explicit formulas
    if re.search(r"\bc2h5br\b|\bc2h5cl\b|\bch3br\b|\bch3cl\b|\bch3ch2br\b|\bch3ch2cl\b", t):
        return True

    return False


def _is_finkelstein(t: str) -> bool:
    return ("finkelstein" in t) or (("nai" in t) and ("acetone" in t))


def _is_swarts(t: str) -> bool:
    return ("swarts" in t) or _has_any(t, ["agf", "sbf3"]) or (("hf" in t) and ("alkyl" in t))


def _is_wurtz(t: str) -> bool:
    return ("wurtz" in t) or (("dry ether" in t or "ether" in t) and ("na" in t or "sodium" in t))


def _is_aqueous_oh(t: str) -> bool:
    return _has_any(t, ["aq", "aqueous", "water", "h2o"]) and _has_any(t, ["koh", "naoh", "oh-"])


def _is_alcoholic_base_heat(t: str) -> bool:
    return _has_any(t, ["alc koh", "alcoholic koh", "ethanolic koh", "heat", "Δ", "delta"]) and _has_any(t, ["koh", "naoh", "base", "oh-"])


def _has_cyanide(t: str) -> bool:
    return _has_any(t, ["nacn", "kcn", "cn-", "cyanide"])


def _substrate_hint(t: str) -> str:
    if _has_any(t, ["tert-butyl bromide", "t-butyl bromide", "2-bromo-2-methylpropane", "(ch3)3cbr"]):
        return "tertiary"
    if _has_any(t, ["2-bromopropane", "isopropyl bromide", "2-bromobutane", "sec-butyl"]):
        return "secondary"
    if _has_any(t, ["bromoethane", "ethyl bromide", "c2h5br", "ch3ch2br", "1-bromopropane"]):
        return "primary"
    return "unknown"


def solve_alkyl_halides_v1(text: str) -> Optional[AlkylHalideResult]:
    """
    Alkyl halides v1 (exam-safe):
      - Named reactions: Wurtz, Finkelstein, Swarts
      - SN1/SN2/E1/E2 based on conditions (aq vs alc, heat, solvent)
    """
    t = _lc(text)
    if not _is_alkyl_halide_context(t):
        return None

    # 1) Named reactions (deterministic)
    if _is_finkelstein(t):
        return AlkylHalideResult(
            reaction="Finkelstein reaction (halide exchange)",
            product=(
                "R-Cl / R-Br + NaI (acetone) → **R-I (alkyl iodide)** + NaCl/NaBr (ppt). "
                "ASCII: R-I."
            ),
            notes="Exam key: acetone used; NaCl/NaBr precipitates driving reaction forward.",
        )

    if _is_swarts(t):
        return AlkylHalideResult(
            reaction="Swarts reaction (fluorination)",
            product=(
                "R-Cl / R-Br + AgF (or SbF3) → **R-F (alkyl fluoride)**. "
                "ASCII: R-F."
            ),
            notes="Exam key: Swarts converts alkyl chlorides/bromides to alkyl fluorides using metal fluorides.",
        )

    if _is_wurtz(t):
        return AlkylHalideResult(
            reaction="Wurtz reaction (coupling)",
            product=(
                "2 R-X + 2 Na (dry ether) → **R-R (higher alkane)** + 2 NaX. "
                "ASCII: R-R."
            ),
            notes="Trap: best for symmetric alkanes; mixture forms if two different halides used.",
        )

    # 2) Cyanide SN2 (common exam)
    if _has_cyanide(t):
        # If solvent is not specified, return a partial answer (gated by governor)
        if not _has_any(t, ["acetone", "dmso", "dmf", "ethanol", "water", "aqueous", "alcoholic", "protic", "aprotic"]):
            return AlkylHalideResult(
                reaction="SN2 substitution (cyanide, solvent unspecified)",
                product="Partial: solvent conditions unspecified. In polar aprotic solvent, R-X + CN− → **R-CN (nitrile)**.",
                notes="CN− favors SN2 in polar aprotic solvents such as acetone/DMF/DMSO; without solvent details the exact product conditions cannot be determined.",
            )
        if _has_any(t, ["bromoethane", "ethyl bromide", "c2h5br", "ch3ch2br"]):
            return AlkylHalideResult(
                reaction="SN2 substitution (cyanide)",
                product="CH3CH2Br + NaCN (acetone) → **CH3CH2CN (propionitrile / ethyl cyanide)** + NaBr.",
                notes="Exam key: CN− is strong nucleophile; polar aprotic (acetone) favors SN2; nitrile adds one carbon.",
            )
        return AlkylHalideResult(
            reaction="SN2 substitution (cyanide)",
            product="General: R-X + CN− (polar aprotic) → **R-CN (nitrile)** (SN2).",
            notes="Trap: CN− gives nitrile (R-C≡N).",
        )

    # 3) Aqueous OH− → substitution to alcohol
    sub = _substrate_hint(t)
    if _is_aqueous_oh(t):
        if sub == "tertiary":
            return AlkylHalideResult(
                reaction="SN1 substitution (aq. OH−)",
                product="Tertiary R-X + aq. KOH/NaOH → **ROH (alcohol)** (SN1).",
                notes="SN1 possible rearrangement (concept).",
            )
        return AlkylHalideResult(
            reaction="Substitution to alcohol (aq. OH−)",
            product="R-X + aq. KOH/NaOH → **ROH (alcohol)** (SN2 for 1°, mixed for 2°).",
            notes="Exam key: aqueous → substitution.",
        )

    # 4) Alcoholic base + heat → elimination (E2 major)
    if _is_alcoholic_base_heat(t):
        if _has_any(t, ["2-bromopropane", "isopropyl bromide"]):
            return AlkylHalideResult(
                reaction="E2 elimination (dehydrohalogenation)",
                product="2-bromopropane + alcoholic KOH, heat → **propene (alkene)** + KBr + H2O.",
                notes="Exam key: alc KOH + heat → elimination; alkene major.",
            )
        return AlkylHalideResult(
            reaction="E2 elimination (dehydrohalogenation)",
            product="R-X + alcoholic KOH (heat) → **alkene** + KX + H2O.",
            notes="Exam key: alc KOH + heat → elimination (E2).",
        )

    # 5) If explicitly asking SN1/SN2/E1/E2: give decision sheet
    if _has_any(t, ["sn1", "sn2", "e1", "e2", "substitution", "elimination"]):
        return AlkylHalideResult(
            reaction="SN1 vs SN2 vs E1 vs E2 (decision sheet)",
            product=(
                "**SN2:** 1° > 2° (3° no); strong nucleophile; polar aprotic (acetone/DMF/DMSO).  "
                "**SN1:** 3° > 2°; polar protic; rearrangements possible.  "
                "**E2:** strong base + heat (alc KOH, t-BuOK); Zaitsev major (bulky base → Hofmann).  "
                "**E1:** SN1-like + heat gives alkene; rearrangements possible."
            ),
            notes="Key trap: aq OH− → substitution; alc KOH + heat → elimination.",
        )

    # Fallback safe
    return AlkylHalideResult(
        reaction="Alkyl halides (default exam-safe)",
        product="If **aq. KOH** → ROH (substitution). If **alc. KOH + heat** → alkene (elimination). Primary → SN2; tertiary → SN1/E1; strong base → E2.",
        notes="Give medium + heat in question to remove ambiguity.",
    )
