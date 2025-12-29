from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ConversionResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: List[str]) -> bool:
    return any(w in t for w in words)


def _is_conversion_question(t: str) -> bool:
    return _has_any(
        t,
        [
            "convert",
            "conversion",
            "prepare",
            "synthesize",
            "how to obtain",
            "how would you obtain",
            "how will you prepare",
            "from",
            "to",
            "→",
            "->",
        ],
    )


def _fmt_chain(lines: List[str]) -> str:
    return "\n".join(lines).strip()


def solve_conversions_v2(question: str) -> Optional[ConversionResult]:
    """
    Conversions v2:
    - multi-step, exam-standard chains
    - conservative matching by presence of source+target keywords
    - returns a clean reagent chain suitable for NEET/JEE answers
    """
    t = _lc(question)
    if not _is_conversion_question(t):
        return None

    # ---------- Benzene / Aromatics chains ----------
    # Benzene -> Nitrobenzene
    if ("benzene" in t) and ("nitrobenzene" in t):
        chain = _fmt_chain([
            "Benzene",
            "→ (conc. HNO3 / conc. H2SO4) Nitrobenzene",
        ])
        return ConversionResult(
            reaction="Conversion (Aromatics): benzene → nitrobenzene",
            product=chain,
            notes="Nitration of benzene using mixed acid.",
        )

    # Nitrobenzene -> Aniline
    if ("nitrobenzene" in t) and ("aniline" in t):
        chain = _fmt_chain([
            "Nitrobenzene",
            "→ (Sn/HCl, then NaOH) Aniline",
        ])
        return ConversionResult(
            reaction="Conversion (Aromatics): nitrobenzene → aniline",
            product=chain,
            notes="Reduction of nitro group to amine (acidic reduction, then basification).",
        )

    # Benzene -> Aniline (via Nitrobenzene)
    if ("benzene" in t) and ("aniline" in t):
        chain = _fmt_chain([
            "Benzene",
            "→ (conc. HNO3 / conc. H2SO4) Nitrobenzene",
            "→ (Sn/HCl, then NaOH) Aniline",
        ])
        return ConversionResult(
            reaction="Conversion (Aromatics): benzene → aniline",
            product=chain,
            notes="Standard NCERT route: nitration then reduction.",
        )

    # Aniline -> Phenol (Diazotization + hydrolysis)
    if ("aniline" in t) and ("phenol" in t):
        chain = _fmt_chain([
            "Aniline",
            "→ (NaNO2/HCl, 0–5°C) Benzene diazonium chloride",
            "→ (H2O, warm) Phenol",
        ])
        return ConversionResult(
            reaction="Conversion (Diazonium): aniline → phenol",
            product=chain,
            notes="Diazotization at 0–5°C, then hydrolysis to phenol.",
        )

    # Benzene -> Phenol (via aniline + diazonium)
    if ("benzene" in t) and ("phenol" in t):
        chain = _fmt_chain([
            "Benzene",
            "→ (conc. HNO3 / conc. H2SO4) Nitrobenzene",
            "→ (Sn/HCl, then NaOH) Aniline",
            "→ (NaNO2/HCl, 0–5°C) Benzene diazonium chloride",
            "→ (H2O, warm) Phenol",
        ])
        return ConversionResult(
            reaction="Conversion (Aromatics): benzene → phenol",
            product=chain,
            notes="Exam-standard chain: nitration → reduction → diazotization → hydrolysis.",
        )

    # Chlorobenzene -> Phenol (Dow process)
    if ("chlorobenzene" in t) and ("phenol" in t):
        chain = _fmt_chain([
            "Chlorobenzene",
            "→ (NaOH, 623 K, 300 atm) Sodium phenoxide",
            "→ (H+) Phenol",
        ])
        return ConversionResult(
            reaction="Conversion (Aromatics): chlorobenzene → phenol",
            product=chain,
            notes="Dow process: harsh NaOH conditions, then acidification.",
        )

    # ---------- Aliphatic chains ----------
    # Ethanol -> Ethene (dehydration)
    if ("ethanol" in t) and ("ethene" in t):
        chain = _fmt_chain([
            "Ethanol",
            "→ (conc. H2SO4, 443 K) Ethene",
        ])
        return ConversionResult(
            reaction="Conversion (Alcohol → Alkene): ethanol → ethene",
            product=chain,
            notes="Dehydration of alcohol to alkene.",
        )

    # Ethanol -> Ethanoic acid (oxidation)
    if ("ethanol" in t) and ("ethanoic acid" in t):
        chain = _fmt_chain([
            "Ethanol",
            "→ (K2Cr2O7/H+, or KMnO4/H+) Ethanoic acid",
        ])
        return ConversionResult(
            reaction="Conversion (Alcohol → Acid): ethanol → ethanoic acid",
            product=chain,
            notes="Strong oxidation converts primary alcohol to carboxylic acid.",
        )

    # Ethanol -> Propanoic acid (chain extension via CN-)
    if ("ethanol" in t) and ("propanoic acid" in t):
        chain = _fmt_chain([
            "Ethanol",
            "→ (PBr3 or HBr) Bromoethane",
            "→ (alc. KCN) Propanenitrile (ethyl cyanide)",
            "→ (H+/H2O, heat) Propanoic acid",
        ])
        return ConversionResult(
            reaction="Conversion (Chain extension): ethanol → propanoic acid",
            product=chain,
            notes="Increase chain length by 1 carbon using CN−, then hydrolysis to acid.",
        )

    return None
