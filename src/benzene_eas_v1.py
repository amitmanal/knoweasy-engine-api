"""
Specialised solver for simple electrophilic aromatic substitution (EAS) on benzene.

This module implements a deterministic mapping for classic benzene reactions
that repeatedly appear in exam questions.  The aim is to return the final
product name along with a short description of the reaction mechanism.

Supported reaction types include:

* Nitration of benzene with concentrated HNO₃/H₂SO₄ → nitrobenzene
* Halogenation (bromination) of benzene with Br₂/FeBr₃ → bromobenzene
* Friedel–Crafts alkylation (e.g. CH₃Cl/AlCl₃) → alkylbenzene
* Friedel–Crafts acylation (e.g. CH₃COCl/AlCl₃) → acylbenzene

The solver returns ``None`` for texts that do not obviously describe one of
the above reactions.  It performs only simple substring checks and does not
attempt to parse the full reaction; it is therefore deliberately
conservative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BenzeneEASResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, keywords: list[str]) -> bool:
    return any(k in t for k in keywords)


def solve_benzene_eas_v1(text: str) -> Optional[BenzeneEASResult]:
    """
    Detect and answer basic EAS reactions on benzene.

    Parameters
    ----------
    text : str
        The user question text.

    Returns
    -------
    Optional[BenzeneEASResult]
        A populated result if a recognised reaction is detected, else ``None``.
    """
    t = _lc(text)
    # Basic trigger: look for benzene or a substituted benzene name (toluene, nitrobenzene, aniline, etc.)
    if not _has_any(t, [
        "benzene", "toluene", "methylbenzene", "nitrobenzene", "aniline", "phenyl", "c6h5", "anisole", "chlorobenzene", "c6h5ch3", "c6h5cl"
    ]):
        # If none of these core aromatic terms are present, avoid misfiring
        return None

    # Nitration: conc. HNO3 + conc. H2SO4
    if _has_any(t, ["hno3", "hno₃", "nitric acid", "nitration"]):
        return BenzeneEASResult(
            reaction="Nitration of benzene (electrophilic substitution)",
            product="Nitrobenzene",
            notes="Benzene + conc. HNO3/conc. H2SO4 → nitrobenzene (NO2 substitution).",
        )

    # Halogenation: Br2/FeBr3 or Cl2/FeCl3
    if _has_any(t, ["br2", "bromine"]) and _has_any(t, ["febr3", "fecl3", "alcl3", "lewis acid"]):
        # Default to bromination for typical exam examples; FeBr3 is common
        return BenzeneEASResult(
            reaction="Halogenation of benzene (electrophilic substitution)",
            product="Bromobenzene",
            notes="Benzene + Br2/FeBr3 → bromobenzene (substitution of H by Br).",
        )

    # Friedel–Crafts limitations/activations before generic patterns
    # Nitrobenzene: strongly deactivated — no FC reaction
    if _has_any(t, ["nitrobenzene", "c6h5no2"]) and _has_any(t, ["friedel", "friedel–crafts", "friedel-crafts", "ch3cl", "c2h5cl", "cocl", "acylation", "alkylation"]):
        return BenzeneEASResult(
            reaction="Friedel–Crafts on nitrobenzene (not possible)",
            product="Reaction does not occur",
            notes="NO2 group is strongly deactivating and meta directing; nitrobenzene does not undergo Friedel–Crafts alkylation or acylation.",
        )
    # Aniline (amine) forms Lewis acid–base adduct with AlCl3, blocking FC
    if _has_any(t, ["aniline", "c6h5nh2", "c6h5 nh2", "anilide", "amine"]) and _has_any(t, ["friedel", "friedel–crafts", "friedel-crafts", "cocl", "ch3cl", "acylation", "alkylation"]):
        return BenzeneEASResult(
            reaction="Friedel–Crafts on aniline (not possible)",
            product="Reaction does not occur",
            notes="Aniline (NH2) coordinates with AlCl3 forming a non-reactive complex; FC reactions do not proceed.",
        )
    # Toluene Friedel–Crafts alkylation (activating; o,p directing)
    if _has_any(t, ["toluene", "methylbenzene", "c6h5ch3"]) and _has_any(t, ["ch3cl", "friedel", "friedel–crafts", "friedel-crafts", "alkylation"]):
        return BenzeneEASResult(
            reaction="Friedel–Crafts alkylation of toluene (o,p directing)",
            product="Ortho- and para-xylene (major)",
            notes="CH3 group activates the ring and directs electrophiles to ortho and para positions. Alkylation gives o- and p-xylene.",
        )

    # Friedel–Crafts acylation: acyl chloride + AlCl3
    # Check for acylation before alkylation to avoid misclassification, since reagents
    # like CH3COCl/AlCl3 contain both "cocl" and "cl/alcl3" patterns.
    if _has_any(t, ["acylation", "cocl", "cococl", "coohcl", "acyl chloride", "ch3cocl", "acocl"]):
        return BenzeneEASResult(
            reaction="Friedel–Crafts acylation of benzene",
            product="Acylbenzene",
            notes="Benzene + RCOCl/AlCl3 → acylbenzene (benzophenone derivative). Exam tip: no polyacylation occurs because the acyl group deactivates the ring.",
        )

    # Friedel–Crafts alkylation: alkyl halide + AlCl3
    if _has_any(t, ["alkylation", "friedel", "friedel–crafts", "friedel-crafts", "ch3cl", "c2h5cl"]):
        return BenzeneEASResult(
            reaction="Friedel–Crafts alkylation of benzene",
            product="Alkylbenzene",
            notes="Benzene + R–Cl/AlCl3 → alkylbenzene (R group attaches to ring). Exam tip: polyalkylation can occur because the alkyl group activates the ring; control by using excess benzene.",
        )

    return None