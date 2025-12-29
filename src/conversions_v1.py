from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import re


@dataclass
class ConversionResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _clean_entity(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .;:,")
    return s


def _canonicalize(name: str) -> str:
    """
    Map common variants to a canonical key.
    Keep it conservative and exam-oriented.
    """
    t = _lc(name)

    # normalize arrows or punctuation already removed upstream
    t = t.replace("phenylamine", "aniline")
    t = t.replace("methylbenzene", "toluene")
    t = t.replace("hydroxybenzene", "phenol")

    # common formula aliases
    if t in ["c6h6"]:
        return "benzene"
    if t in ["c6h5nh2"]:
        return "aniline"
    if t in ["c6h5oh"]:
        return "phenol"

    # common alcohol names
    if t in ["isopropyl alcohol", "isopropanol", "2-propanol", "propan-2-ol"]:
        return "propan-2-ol"
    if t in ["n-propyl alcohol", "1-propanol", "propan-1-ol"]:
        return "propan-1-ol"
    if t in ["ethyl alcohol", "ethanol"]:
        return "ethanol"
    if t in ["ethene", "ethylene"]:
        return "ethene"

    # carbonyl common
    if t in ["acetone", "propanone", "propan-2-one"]:
        return "propanone"
    if t in ["acetic acid", "ethanoic acid"]:
        return "ethanoic acid"
    if t in ["acetyl chloride", "ethanoyl chloride"]:
        return "ethanoyl chloride"

    return t


def _extract_conversion_pair(question: str) -> Optional[Tuple[str, str]]:
    """
    Extract (from, to) from typical conversion questions.
    Supports:
    - "Convert A to B"
    - "Prepare B from A"
    - "A -> B"
    """
    q = question or ""
    t = _lc(q)

    # Arrow format
    m = re.search(r"(.+?)\s*(?:->|→|⇒|⟶|⟶)\s*(.+)", q)
    if m:
        a = _clean_entity(m.group(1))
        b = _clean_entity(m.group(2))
        if a and b:
            return a, b

    # Convert A to/into B
    m = re.search(r"\bconvert\s+(.+?)\s+(?:to|into)\s+(.+?)(?:[.?\n]|$)", t)
    if m:
        a = _clean_entity(m.group(1))
        b = _clean_entity(m.group(2))
        if a and b:
            return a, b

    # Prepare B from A
    m = re.search(r"\bprepare\s+(.+?)\s+from\s+(.+?)(?:[.?\n]|$)", t)
    if m:
        # note order: prepare TARGET from START
        b = _clean_entity(m.group(1))
        a = _clean_entity(m.group(2))
        if a and b:
            return a, b

    # How to obtain B from A
    m = re.search(r"\bobtain\s+(.+?)\s+from\s+(.+?)(?:[.?\n]|$)", t)
    if m:
        b = _clean_entity(m.group(1))
        a = _clean_entity(m.group(2))
        if a and b:
            return a, b

    return None


def _route_map() -> Dict[Tuple[str, str], str]:
    """
    Canonical (from, to) -> route text.
    Keep routes NCERT-aligned and exam standard.
    """
    R: Dict[Tuple[str, str], str] = {}

    # Aromatic core conversions (high-frequency)
    R[("benzene", "aniline")] = (
        "Benzene → Nitrobenzene (conc. HNO3/H2SO4) → Aniline (Sn/HCl then NaOH) "
        "[or H2/Ni/Pd]."
    )
    R[("aniline", "phenol")] = (
        "Aniline → Benzene diazonium chloride (NaNO2/HCl, 0–5°C) → Phenol (warm water)."
    )
    R[("aniline", "iodobenzene")] = (
        "Aniline → Benzene diazonium chloride (NaNO2/HCl, 0–5°C) → Iodobenzene (KI)."
    )
    R[("benzene", "benzoic acid")] = (
        "Benzene → Toluene (Friedel–Crafts alkylation: CH3Cl/AlCl3) → Benzoic acid (hot KMnO4, then acidify)."
    )
    R[("toluene", "benzoic acid")] = (
        "Toluene → Benzoic acid (hot KMnO4, then acidify)."
    )

    # Simple alkene/alcohol interconversions
    R[("ethanol", "ethene")] = "Ethanol → Ethene (conc. H2SO4, 170°C) [dehydration]."
    R[("ethene", "ethanol")] = "Ethene → Ethanol (steam/H3PO4 or H2O/H+) [hydration]."
    R[("propan-2-ol", "propene")] = "Propan-2-ol → Propene (conc. H2SO4, heat) [dehydration]."
    R[("propene", "propan-2-ol")] = "Propene → Propan-2-ol (H2O/H+; Markovnikov hydration)."

    # Alkyl halide ↔ alcohol
    R[("1-bromopropane", "propan-1-ol")] = "1-Bromopropane → Propan-1-ol (aq KOH) [SN2]."
    R[("propan-1-ol", "1-bromopropane")] = "Propan-1-ol → 1-Bromopropane (PBr3) [or HBr/ZnCl2]."

    # Acid derivatives
    R[("ethanoic acid", "ethanoyl chloride")] = "Ethanoic acid → Ethanoyl chloride (SOCl2) [or PCl5]."
    R[("ethanoyl chloride", "acetamide")] = "Ethanoyl chloride → Acetamide (NH3, excess)."

    # Carbonyl reductions
    R[("propanone", "propan-2-ol")] = "Propanone → Propan-2-ol (NaBH4) [then H3O+ workup]."

    return R


def solve_conversions_v1(question: str) -> Optional[ConversionResult]:
    """
    Return a ConversionResult if the question is a conversion/preparation type.
    """
    pair = _extract_conversion_pair(question)
    if not pair:
        # Also detect if question explicitly mentions "conversion" word
        if "conversion" not in _lc(question):
            return None
        return None

    a_raw, b_raw = pair
    a = _canonicalize(a_raw)
    b = _canonicalize(b_raw)

    routes = _route_map()

    # Direct hit
    route = routes.get((a, b))
    if route:
        return ConversionResult(
            reaction="Organic conversion (A → B)",
            product=route,
            notes="Use standard NCERT/JEE/NEET reagents and conditions; write key conditions (0–5°C, heat, etc.).",
        )

    # Sometimes question uses "bromopropane" without locant
    if a == "bromopropane":
        # default to 1-bromopropane for SN2 conversions
        route = routes.get(("1-bromopropane", b))
        if route:
            return ConversionResult("Organic conversion (A → B)", route, "Assuming 1-bromopropane (primary) for SN2.")

    return None
