# src/carbonyl_stephen_v1.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class StephenResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_nitrile_present(t: str) -> bool:
    if _has_any(t, ["nitrile", "cyanide", "alkyl cyanide", "aryl cyanide"]):
        return True
    if _has_any(t, ["rcn", "r-cn", "c≡n", "c#n", "-cn", " cn"]):
        return True
    if re.search(r"\bacetonitrile\b|\bmethyl cyanide\b|\bch3cn\b", t):
        return True
    if re.search(r"\bbenzonitrile\b|\bc6h5cn\b", t):
        return True
    if re.search(r"\bpropionitrile\b|\bethyl cyanide\b|\bc2h5cn\b", t):
        return True
    return False


def _is_stephen_reagents(t: str) -> bool:
    # IMPORTANT: recognize both ASCII and unicode versions users might type
    has_sncl2 = _has_any(t, ["sncl2", "sn cl2", "stannous chloride", "sncl₂", "sn cl₂"])
    has_hcl = _has_any(t, ["hcl", "hydrochloric"])
    has_hydrolysis = _has_any(t, ["h2o", "water", "hydrolysis", "h3o", "acidic hydrolysis"])

    if "stephen" in t:
        return True
    if has_sncl2 and has_hcl:
        return True
    if has_sncl2 and has_hydrolysis:
        return True
    return False


def _substrate_key(t: str) -> Optional[str]:
    if re.search(r"\bacetonitrile\b|\bmethyl cyanide\b|\bch3cn\b", t):
        return "acetonitrile"
    if re.search(r"\bbenzonitrile\b|\bc6h5cn\b", t):
        return "benzonitrile"
    if re.search(r"\bpropionitrile\b|\bethyl cyanide\b|\bc2h5cn\b", t):
        return "propionitrile"
    return None


def solve_stephen_v1(text: str) -> Optional[StephenResult]:
    """
    Stephen aldehyde synthesis:
      R–C≡N  --(SnCl2/HCl)--> iminium salt  --(H2O)-->  R–CHO
    Deterministic, exam-safe. Returns None if not detected.
    """
    t = _lc(text)

    if not ("stephen" in t or (_is_nitrile_present(t) and _is_stephen_reagents(t))):
        return None

    reagent_ascii = "SnCl2/HCl (stannous chloride + HCl), then H2O"

    if not _is_nitrile_present(t):
        return StephenResult(
            reaction="Stephen aldehyde synthesis",
            product=f"Converts **nitriles (R–C≡N)** to **aldehydes (R–CHO)** using **{reagent_ascii}**.",
            notes="Scope trap: requires a nitrile substrate. Product is aldehyde (not alcohol).",
        )

    key = _substrate_key(t)

    if key == "acetonitrile":
        return StephenResult(
            reaction="Stephen aldehyde synthesis (nitrile → aldehyde)",
            product=f"CH3CN (acetonitrile) → CH3CHO (**ethanal**) using {reagent_ascii}.",
            notes="Mechanism: nitrile → iminium salt (with SnCl2/HCl) → hydrolysis → aldehyde.",
        )

    if key == "benzonitrile":
        return StephenResult(
            reaction="Stephen aldehyde synthesis (nitrile → aldehyde)",
            product=f"C6H5CN / C₆H₅CN (benzonitrile) → C6H5CHO / C₆H₅CHO (**benzaldehyde**) using {reagent_ascii}.",
            notes="Classic aromatic nitrile → aromatic aldehyde (exam favorite).",
        )

    if key == "propionitrile":
        return StephenResult(
            reaction="Stephen aldehyde synthesis (nitrile → aldehyde)",
            product=f"C2H5CN (propionitrile) → C2H5CHO (**propanal**) using {reagent_ascii}.",
            notes="Hydrolysis step is required to reveal the aldehyde.",
        )

    return StephenResult(
        reaction="Stephen aldehyde synthesis (nitrile → aldehyde)",
        product=f"General: R–C≡N  --({reagent_ascii})-->  R–CHO (aldehyde).",
        notes="Exam traps: needs nitrile substrate; includes hydrolysis; aldehyde (not alcohol).",
    )
