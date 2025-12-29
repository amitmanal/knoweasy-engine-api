"""
Solver for directing effects in electrophilic aromatic substitution on substituted benzenes.

This module covers a small set of representative directing-effect questions
commonly encountered in entrance exams.  It returns which positions (ortho,
meta, para) are favoured for the substitution and briefly explains why.

Supported triggers:

* Toluene nitration → o/p-nitrotoluene (activating, ortho/para)
* Nitrobenzene nitration → meta-nitrobenzene (strong deactivator, meta)
* Chlorobenzene nitration → ortho/para nitrochlorobenzene (weakly deactivating but o,p directing)
* Anisole halogenation with Br₂/FeBr₃ → o/p-bromoanisole (strongly activating, o,p)

The solver returns ``None`` for questions outside these specific patterns, leaving
other modules free to answer more general aromatic questions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DirectingResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, keywords: list[str]) -> bool:
    return any(k in t for k in keywords)


def solve_benzene_directing_v1(text: str) -> Optional[DirectingResult]:
    """
    Determine directing effects for substituted benzene electrophilic substitution.

    Parameters
    ----------
    text : str
        The user question text.

    Returns
    -------
    Optional[DirectingResult]
        Information about the reaction and major product orientation, or ``None``
        if no recognised pattern is detected.
    """
    t = _lc(text)
    # Basic check to avoid misfiring; require nitration/halogenation with substituted benzene
    if not _has_any(t, ["nitration", "hno3", "hno₃", "halogenation", "br2"]):
        return None

    # Toluene (methylbenzene) nitration
    if _has_any(t, ["toluene", "methylbenzene", "c6h5ch3", "ch3"]) and _has_any(t, ["hno3", "nitration"]):
        return DirectingResult(
            reaction="Nitration of toluene (activating, o/p directing)",
            product="Ortho- and para-nitrotoluene (major)",
            notes="CH3 group is electron donating (+I/+H); this activation of the ring directs nitration to the ortho and para positions.",
        )

    # Nitrobenzene nitration
    if _has_any(t, ["nitrobenzene", "c6h5no2"]):
        return DirectingResult(
            reaction="Nitration of nitrobenzene (deactivating, meta)",
            product="Meta-nitrobenzene is the major product",
            notes="NO2 group is strongly -M/-I; nitrobenzene is deactivated and meta directing.",
        )

    # Chlorobenzene nitration
    if _has_any(t, ["chlorobenzene", "c6h5cl", "c6h5 cl"]):
        return DirectingResult(
            reaction="Nitration of chlorobenzene (deactivating but o,p directing)",
            product="Ortho- and para-nitrochlorobenzene (major)",
            notes="Cl is deactivating (-I) but has lone pairs for resonance; overall o,p directing though deactivating.",
        )

    # Anisole halogenation
    if _has_any(t, ["anisole", "methoxybenzene", "c6h5och3"]) and _has_any(t, ["br2", "bromination", "halogenation"]):
        return DirectingResult(
            reaction="Halogenation of anisole (strongly activating, o/p)",
            product="Ortho- and para-bromoanisole (major)",
            notes="OMe group donates electrons by resonance; anisole is strongly o,p directing.",
        )

    return None