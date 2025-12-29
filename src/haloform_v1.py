# src/haloform_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class HaloformResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _looks_like_haloform_trigger(t: str) -> bool:
    # Direct named triggers
    if _has_any(t, ["haloform", "iodoform", "iodoform test", "chi3", "yellow ppt", "yellow precipitate"]):
        return True

    # Reagent pattern (exam-friendly)
    # i2/naoh, iodine + naoh, alkaline iodine
    if ("i2" in t or "iodine" in t) and _has_any(t, ["naoh", "koh", "alkaline", "alkali"]):
        return True

    return False


def _is_ethanol(t: str) -> bool:
    return bool(re.search(r"\bethanol\b|\bethyl alcohol\b|\bc2h5oh\b", t))


def _is_methyl_ketone_by_name(t: str) -> Optional[str]:
    # returns a "key" for deterministic product naming
    if re.search(r"\bacetone\b|\bpropanone\b|\bpropan-2-one\b|\b2-propanone\b|\bch3coch3\b", t):
        return "acetone"
    if re.search(r"\bacetophenone\b|\b1-phenylethanone\b|\bc6h5coch3\b", t):
        return "acetophenone"
    if re.search(r"\bbutan-2-one\b|\b2-butanone\b|\bmethyl ethyl ketone\b|\bch3coc2h5\b", t):
        return "2-butanone"
    return None


def _is_generic_methyl_ketone(t: str) -> bool:
    # Generic motif words/symbols
    if _has_any(t, ["methyl ketone", "rcoch3", "ch3co–", "ch3co-", "ch3co "]):
        return True
    # Some users write "CH3CO group"
    if _has_any(t, ["ch3co group", "ch3co- group", "ch3co– group"]):
        return True
    return False


def _is_methyl_secondary_alcohol(t: str) -> bool:
    # CH3-CH(OH)-R family, common exam examples
    if re.search(r"\bpropan-2-ol\b|\bisopropyl alcohol\b|\bisopropanol\b|\b2-propanol\b|\bch3chohch3\b", t):
        return True
    # Generic wording hints
    if "secondary alcohol" in t and _has_any(t, ["ch3-ch(oh)", "ch3ch(oh)", "methyl carbinol", "ch3choh"]):
        return True
    return False


def solve_haloform_v1(text: str) -> Optional[HaloformResult]:
    """
    Returns HaloformResult if detected, else None.
    Exam-safe: emphasizes CHI3 yellow ppt + carboxylate (salt) in base.
    """
    t = _lc(text)
    if not _looks_like_haloform_trigger(t):
        return None

    # Ethanol special trap: gives formate (not acetate)
    if _is_ethanol(t):
        return HaloformResult(
            reaction="Haloform (Iodoform) reaction / Iodoform test",
            product="Products: CHI₃ (yellow ppt) + HCOONa (sodium formate).",
            notes=(
                "Ethanol is first oxidized to acetaldehyde, then undergoes haloform. "
                "Common trap: writing sodium acetate for ethanol (wrong)."
            ),
        )

    # Secondary alcohol CH3-CH(OH)-R -> oxidizes to methyl ketone -> haloform
    if _is_methyl_secondary_alcohol(t):
        return HaloformResult(
            reaction="Iodoform test (alcohol → oxidation → haloform)",
            product="Products: CHI₃ (yellow ppt) + corresponding carboxylate salt (RCOO⁻ Na⁺).",
            notes="Secondary alcohol of type CH₃–CH(OH)–R gives positive iodoform test because it oxidizes to a methyl ketone.",
        )

    # Named methyl ketones
    key = _is_methyl_ketone_by_name(t)
    if key == "acetone":
        return HaloformResult(
            reaction="Haloform (Iodoform) reaction of methyl ketone",
            product="Products: CHI₃ (yellow ppt) + CH₃COONa (sodium acetate).",
            notes="Acetone (CH₃COCH₃) is a classic positive iodoform test substrate.",
        )

    if key == "acetophenone":
        return HaloformResult(
            reaction="Haloform (Iodoform) reaction of methyl ketone",
            product="Products: CHI₃ (yellow ppt) + C₆H₅COONa (sodium benzoate).",
            notes="In NaOH medium, the acid is present as benzoate salt (exam preference).",
        )

    if key == "2-butanone":
        return HaloformResult(
            reaction="Haloform (Iodoform) reaction of methyl ketone",
            product="Products: CHI₃ (yellow ppt) + CH₃CH₂COONa (sodium propionate).",
            notes="CH₃CO– group cleavage gives carboxylate of the R-part.",
        )

    # Generic methyl ketone scope
    if _is_generic_methyl_ketone(t):
        return HaloformResult(
            reaction="Haloform (Iodoform) reaction of methyl ketone",
            product="General: R–CO–CH₃ + I₂/NaOH → CHI₃ (yellow ppt) + RCOONa.",
            notes="Exam trap: product is carboxylate (RCOONa) in alkaline medium, not free acid.",
        )

    # If triggered by reagents but substrate not clear: return scope-based safe answer
    return HaloformResult(
        reaction="Haloform (Iodoform) reaction / Iodoform test",
        product=(
            "✅ Positive: methyl ketones (R–CO–CH₃), ethanol, and secondary alcohols of type CH₃–CH(OH)–R.\n"
            "→ gives CHI₃ (yellow ppt) + carboxylate (RCOONa).\n"
            "❌ Negative: non-methyl ketones, methanol, tertiary alcohols."
        ),
        notes="Common mistake: assuming all ketones/alcohols give iodoform; only the above set does.",
    )
