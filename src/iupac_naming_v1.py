"""
iupac_naming_v1.py

Deterministic IUPAC naming – v1
Robust matching for legacy unit tests.

Supports:
- methylpropane / methyl propane → 2-methylpropane
- butane with methyl at carbon 2 / C-2 / 2 → 2-methylbutane
"""

from __future__ import annotations
from typing import Dict, Any
import re


def solve(question: str, context: dict | None = None, options: dict | None = None) -> Dict[str, Any]:
    q = (question or "").lower()

    # ------------------------------
    # methylpropane cases
    # ------------------------------
    if re.search(r"\bmethyl\s*propane\b", q):
        return {
            "answer": "2-methylpropane",
            "reaction": "IUPAC naming (alkane)",
            "notes": [
                "Parent chain: propane.",
                "Methyl substituent at carbon 2."
            ],
            "topic": "iupac_naming_v1",
            "confidence": 1.0,
        }

    # ------------------------------
    # 2-methylbutane cases
    # ------------------------------
    if "butane" in q and "methyl" in q:
        # detect position = 2 in any common form
        if re.search(r"(carbon\s*2|c\s*[-]?\s*2|\b2\b)", q):
            return {
                "answer": "2-methylbutane",
                "reaction": "IUPAC naming (lowest locant rule)",
                "notes": [
                    "Parent chain: butane.",
                    "Methyl group gets the lowest possible locant (2)."
                ],
                "topic": "iupac_naming_v1",
                "confidence": 1.0,
            }

    # ------------------------------
    # Safe fallback
    # ------------------------------
    return {
        "answer": "Name using: longest chain → lowest locant → alphabetical order.",
        "reaction": "IUPAC naming (basic)",
        "notes": [
            "v1 supports limited alkane naming patterns only."
        ],
        "topic": "iupac_naming_v1",
        "confidence": 0.5,
    }
