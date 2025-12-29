# src/aromatics_sidechain_v1.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = t.replace("→", "->").replace("⟶", "->").replace("⇒", "->")
    t = re.sub(r"\s+", " ", t).strip()
    return t


@dataclass(frozen=True)
class SidechainResult:
    reaction: str
    product: str
    notes: str = ""


# -------------------------
# Benzylic oxidation (hot KMnO4)
# -------------------------

_OX_RE = re.compile(
    r"(hot\s*kmno4|kmno4\s*[,/ ]*\s*heat|kmno4\s*[,/ ]*\s*hot|alkaline\s*kmno4\s*[,/ ]*\s*heat|oxidative\s*kmno4)",
    re.IGNORECASE,
)

_ARALKYL_HINT_RE = re.compile(
    r"(toluene|methylbenzene|ethylbenzene|propylbenzene|isopropylbenzene|cumene|alkylbenzene|side\s*chain)",
    re.IGNORECASE,
)

_NO_BENZYLIC_H_RE = re.compile(
    r"(tert[- ]butylbenzene|t[- ]butylbenzene|tbu[- ]?benzene)",
    re.IGNORECASE,
)


def detect_benzylic_oxidation_v1(question: str) -> bool:
    """
    Exam-safe detector:
    - Requires KMnO4 + heat/hot/oxidative AND aromatic alkyl/side-chain context.
    """
    t = _norm(question)
    if not _OX_RE.search(t):
        return False
    if not _ARALKYL_HINT_RE.search(t) and "benzene" not in t:
        return False
    # If it's explicitly ring oxidation (rare) ignore; we only do side-chain.
    return True


def solve_benzylic_oxidation_v1(question: str) -> Optional[SidechainResult]:
    if not detect_benzylic_oxidation_v1(question):
        return None

    t = _norm(question)

    # Hard exam rule: needs at least one benzylic H.
    if _NO_BENZYLIC_H_RE.search(t):
        return SidechainResult(
            reaction="Benzylic oxidation (hot KMnO4)",
            product="No reaction (no benzylic H on the side-chain carbon attached to ring).",
            notes="tert-Butylbenzene has no benzylic hydrogen, so KMnO4 cannot oxidize it to benzoic acid.",
        )

    # Default exam-safe major product:
    # Any alkylbenzene with ≥1 benzylic H → benzoic acid.
    return SidechainResult(
        reaction="Benzylic oxidation (hot KMnO4)",
        product="Benzoic acid (C6H5COOH).",
        notes="Any alkyl side-chain on benzene with at least one benzylic H oxidizes fully to –COOH (ring unchanged).",
    )


# -------------------------
# Benzylic (side-chain) halogenation (hv / NBS)
# -------------------------

_HV_RE = re.compile(r"(\bhv\b|h\nu|sunlight|uv|light)", re.IGNORECASE)
_BENZYLIC_HAL_RE = re.compile(
    r"(cl2|br2|nbs)\s*[,/ ]*\s*(hv|h\nu|uv|light|sunlight)",
    re.IGNORECASE,
)

_TOLUENE_RE = re.compile(r"(toluene|methylbenzene|c6h5ch3)", re.IGNORECASE)
_ETHYLBZ_RE = re.compile(r"(ethylbenzene|c6h5ch2ch3)", re.IGNORECASE)
_CUMENE_RE = re.compile(r"(cumene|isopropylbenzene|c6h5ch\(ch3\)2)", re.IGNORECASE)


def detect_benzylic_halogenation_v1(question: str) -> bool:
    """
    Exam-safe detector:
    - Must have Cl2/Br2/NBS AND hv/light/UV.
    - Aromatic/benzylic context.
    """
    t = _norm(question)
    if not (_BENZYLIC_HAL_RE.search(t) or (("nbs" in t or "cl2" in t or "br2" in t) and _HV_RE.search(t))):
        return False
    if "benz" not in t and not _ARALKYL_HINT_RE.search(t):
        return False
    return True


def solve_benzylic_halogenation_v1(question: str) -> Optional[SidechainResult]:
    if not detect_benzylic_halogenation_v1(question):
        return None

    t = _norm(question)
    uses_cl = "cl2" in t
    uses_br = "br2" in t or "nbs" in t  # NBS -> benzylic bromination (exam convention)

    if uses_cl and not uses_br:
        X = "Cl"
        name = "chloride"
    else:
        X = "Br"
        name = "bromide"

    # Substrate-specific (high scoring, very common)
    if _TOLUENE_RE.search(t):
        return SidechainResult(
            reaction=f"Benzylic (side-chain) halogenation ({'Cl2' if X=='Cl' else ('Br2/NBS')} , hv)",
            product=f"Benzyl {name} (C6H5CH2{X}).",
            notes="Under hv, halogenation occurs at the benzylic position (side-chain), not on the ring.",
        )

    if _ETHYLBZ_RE.search(t):
        return SidechainResult(
            reaction=f"Benzylic (side-chain) halogenation ({'Cl2' if X=='Cl' else ('Br2/NBS')} , hv)",
            product=f"1-Phenylethyl {name} (C6H5CH({X})CH3) (major).",
            notes="Benzylic C–H is most reactive; gives benzylic substitution product as major.",
        )

    if _CUMENE_RE.search(t):
        return SidechainResult(
            reaction=f"Benzylic (side-chain) halogenation ({'Cl2' if X=='Cl' else ('Br2/NBS')} , hv)",
            product=f"Cumyl {name} (C6H5C({X})(CH3)2) (major).",
            notes="Tertiary benzylic radical is very stable → major benzylic substitution at the side chain.",
        )

    # Generic exam-safe fallback
    return SidechainResult(
        reaction=f"Benzylic (side-chain) halogenation ({'Cl2' if X=='Cl' else ('Br2/NBS')} , hv)",
        product=f"Benzylic {name} at side-chain (replace a benzylic H with {X}).",
        notes="With hv/UV, substitution happens at the benzylic position (side chain) if benzylic H is present.",
    )
