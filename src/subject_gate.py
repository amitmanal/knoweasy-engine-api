from __future__ import annotations

import re
from typing import Literal

Subject = Literal["chemistry", "non_chemistry"]

# Very lightweight gate (NOT ML, NOT perfect).
# Conservative behavior:
# - If we are unsure, we default to NON_CHEMISTRY.
# - Chemistry that slips through still gets Gemini safely.
_CHEM_KEYWORDS = {
    # General chemistry / organic anchors
    "organic", "inorganic", "physical chemistry", "chemistry",
    "alkane", "alkene", "alkyne", "aromatic", "benzene", "phenyl",
    "aldehyde", "ketone", "carboxylic", "acid", "ester", "amide", "amine",
    "alcohol", "phenol", "ether", "haloalkane", "halide", "grignard",
    "sn1", "sn2", "e1", "e2", "eas", "nitration", "sulfonation",

    # Core reagents in v2 safety kernel
    "hbr", "peroxide", "kmno4", "pcc", "k2cr2o7", "dichromate",
    "tollens", "fehling", "iodoform", "chi3",
    "ozonolysis", "o3", "zn", "dms", "h2so4", "h+", "acidic", "alkaline",

    # Lewis acids / catalysts
    "fecl3", "febr3", "alcl3", "br2", "cl2",

    # Common inorganic terms (still chemistry)
    "oxidation", "reduction", "redox", "electrochemistry", "mole", "molarity",
}

# Rough formula heuristic: e.g., H2SO4, KMnO4, Cu2O, NaOH
_FORMULA_RE = re.compile(r"\b(?:[A-Z][a-z]?\d*){2,}\b")

def detect_subject(question: str) -> Subject:
    q = (question or "").strip().lower()
    if not q:
        return "non_chemistry"

    for kw in _CHEM_KEYWORDS:
        if kw in q:
            return "chemistry"

    if _FORMULA_RE.search(question):
        return "chemistry"

    return "non_chemistry"
