import re
from dataclasses import dataclass
from typing import List, Literal

Mode = Literal["JEE_MAIN", "JEE_ADV", "NEET"]

FILLER_PATTERNS = [
    r"\bplease\b",
    r"\bsolve\b",
    r"\bcan you\b",
    r"\bexplain\b",
    r"\bi think\b",
    r"\bkindly\b",
]

@dataclass
class NormalizedInput:
    cleaned_text: str
    mode: Mode
    subject: str
    ambiguity_flags: List[str]


def _strip_filler(text: str) -> str:
    t = text.strip()
    for pat in FILLER_PATTERNS:
        t = re.sub(pat, "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _detect_ambiguity(text: str) -> List[str]:
    flags: List[str] = []
    low = text.lower()

    # Major product without conditions
    if "major product" in low or "predict the major product" in low:
        if not any(
            k in low
            for k in ["alcoholic", "aqueous", "ethanol", "water", "heat", "temperature"]
        ):
            flags.append("MAJOR_PRODUCT_MISSING_CONDITIONS")

    # NaCN / CN- solvent ambiguity
    if "nacn" in low or " cn" in low:
        if not any(
            k in low
            for k in [
                "dmso",
                "dmf",
                "acetone",
                "ethanol",
                "water",
                "aqueous",
                "alcoholic",
                "protic",
                "aprotic",
            ]
        ):
            flags.append("POSSIBLE_SOLVENT_MISSING")

    # KOH medium ambiguity
    if "koh" in low:
        if not any(k in low for k in ["alcoholic", "aqueous", "ethanol", "water"]):
            flags.append("KOH_MEDIUM_NOT_SPECIFIED")

    # Dehydration: alcohol (-ol) + H2SO4 without temperature
    has_h2so4 = any(k in low for k in ["h2so4", "h₂so₄"])
    has_alcohol = "-ol" in low or " alcohol" in low or low.endswith("ol")

    if has_h2so4 and has_alcohol:
        if not any(
            k in low
            for k in ["heat", "heated", "temperature", "170", "140", "∆", "delta"]
        ):
            flags.append("DEHYDRATION_TEMP_NOT_SPECIFIED")

    # Explicit concentrated H2SO4 without temperature
    if "concentrated h2so4" in low or "concentrated h₂so₄" in low:
        if not any(
            k in low
            for k in ["heat", "heated", "temperature", "170", "140", "∆", "delta"]
        ):
            flags.append("DEHYDRATION_TEMP_NOT_SPECIFIED")

    return flags


def normalize(question_text: str, mode: Mode) -> NormalizedInput:
    cleaned = _strip_filler(question_text)
    flags = _detect_ambiguity(cleaned)
    return NormalizedInput(
        cleaned_text=cleaned,
        mode=mode,
        subject="ORGANIC_CHEMISTRY",
        ambiguity_flags=flags,
    )
