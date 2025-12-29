"""
Deterministic solver for epoxidation of alkenes with peracids.

This simple module recognises when an alkene is treated with a peracid
(such as mCPBA or a generic RCO₃H).  It returns the corresponding epoxide
(oxirane) name for a few common substrates and falls back to a generic
epoxide description for unspecified alkenes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EpoxidationResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, kws: list[str]) -> bool:
    return any(k in t for k in kws)


def solve_epoxidation_v1(text: str) -> Optional[EpoxidationResult]:
    """
    Answer epoxidation questions for simple alkenes.

    Parameters
    ----------
    text : str
        The user question text.

    Returns
    -------
    Optional[EpoxidationResult]
        Populated result if a known substrate + peracid is detected, else ``None``.
    """
    t = _lc(text)
    # Only trigger if peracid/mCPBA/epoxidation is mentioned
    if not _has_any(t, ["mcpba", "peracid", "rco3h", "peroxy acid", "peroxyacid", "epoxidation"]):
        return None

    # Specific named substrates
    if _has_any(t, ["propene", "propylene", "ch3ch=ch2", "c3h6"]):
        return EpoxidationResult(
            reaction="Epoxidation of propene",
            product="Propylene oxide (epoxypropane)",
            notes="Peracid adds across C=C giving an epoxide; stereochemistry retained (syn addition).",
        )

    if _has_any(t, ["cyclohexene", "c6h10", "cyclohexene on treatment"]):
        return EpoxidationResult(
            reaction="Epoxidation of cyclohexene",
            product="Cyclohexene oxide",
            notes="Peracid converts the double bond into an epoxide ring.",
        )

    # Generic alkene + peracid → epoxide
    if _has_any(t, ["alkene", "olefin", "double bond"]):
        return EpoxidationResult(
            reaction="Epoxidation of alkene",
            product="Epoxide",
            notes="Peracid (RCO₃H) converts C=C into an epoxide (oxirane).",
        )

    return None