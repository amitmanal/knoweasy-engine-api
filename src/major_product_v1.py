from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class MajorProductResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: List[str]) -> bool:
    return any(w in t for w in words)


def _is_major_product_question(t: str) -> bool:
    return _has_any(
        t,
        [
            "major product",
            "predict the major product",
            "predict major product",
            "major product when",
            "main product",
        ],
    )


def _substrate_hint(t: str) -> str:
    if _has_any(t, ["tert", "tertiary", "t-"]):
        return "tertiary"
    if _has_any(t, ["sec", "secondary"]):
        return "secondary"
    if _has_any(t, ["primary", "1°", "1 degree", "1-degree"]):
        return "primary"
    return ""


HALIDE_WORDS = [
    "bromo",
    "bromide",
    "chloro",
    "chloride",
    "iodo",
    "iodide",
    "alkyl halide",
    "halide",
    "rx",
    "r-x",
]


# ==========================================================
# 1) KOH (aq vs alc)
# ==========================================================


def _solve_koh(t: str) -> Optional[MajorProductResult]:
    if "koh" not in t or not _has_any(t, HALIDE_WORDS):
        return None

    aq = _has_any(t, ["aq", "aqueous", "water", "h2o"])
    alc = _has_any(t, ["alc", "alcoholic", "ethanolic", "etoh"])

    if "2-bromopropane" in t:
        if aq:
            return MajorProductResult(
                "KOH (aqueous)",
                "propan-2-ol",
                "Aqueous KOH favors substitution.",
            )
        return MajorProductResult(
            "KOH (alcoholic / exam convention)",
            "propene",
            "Alcoholic KOH favors elimination.",
        )

    if aq:
        return MajorProductResult(
            "KOH (aqueous)",
            "Alcohol (substitution product)",
            "Substitution favored in aqueous medium.",
        )

    if alc:
        return MajorProductResult(
            "KOH (alcoholic)",
            "Alkene (elimination product)",
            "Elimination favored in alcoholic medium.",
        )

    return None


# ==========================================================
# 2) CN− (SN2)
# ==========================================================


def _solve_cn(t: str) -> Optional[MajorProductResult]:
    if not _has_any(t, ["nacn", "kcn", "cn-"]) or not _has_any(t, HALIDE_WORDS):
        return None

    if _substrate_hint(t) == "tertiary":
        return MajorProductResult(
            "Tertiary halide + CN−",
            "Elimination / SN1 products",
            "SN2 not possible on tertiary carbon.",
        )

    return MajorProductResult(
        "CN− (SN2)",
        "Nitrile (R–CN)",
        "Primary/secondary alkyl halides undergo SN2.",
    )


# ==========================================================
# 3) HBr (peroxide effect)  ✅ HARDENED NEGATION HANDLING
# ==========================================================


_NEG_PEROXIDE_PATTERNS = [
    r"\bno\s+peroxide\b",
    r"\bwithout\s+peroxide\b",
    r"\bin\s+absence\s+of\s+peroxide\b",
    r"\babsence\s+of\s+peroxide\b",
    r"\bno\s+h2o2\b",
    r"\bwithout\s+h2o2\b",
    r"\bno\s+hydrogen\s+peroxide\b",
    r"\bwithout\s+hydrogen\s+peroxide\b",
]


def _mentions_no_peroxide(t: str) -> bool:
    # regex-based so punctuation/extra spaces still match safely
    for pat in _NEG_PEROXIDE_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def _mentions_peroxide_positive(t: str) -> bool:
    # True ONLY if peroxide is mentioned and NOT negated
    if _mentions_no_peroxide(t):
        return False
    return _has_any(t, ["peroxide", "h2o2", "hydrogen peroxide"])


def _solve_hbr(t: str) -> Optional[MajorProductResult]:
    if "hbr" not in t:
        return None

    # Determine peroxide effect deterministically
    no_peroxide = _mentions_no_peroxide(t)
    peroxide = _mentions_peroxide_positive(t)

    if "propene" in t:
        if peroxide:
            return MajorProductResult(
                "HBr + peroxide",
                "1-bromopropane",
                "Anti-Markovnikov (peroxide effect).",
            )
        # default (and explicit no peroxide) => Markovnikov
        return MajorProductResult(
            "HBr (no peroxide)" if no_peroxide else "HBr (no peroxide / normal conditions)",
            "2-bromopropane",
            "Markovnikov addition.",
        )

    return None


# ==========================================================
# 4) Acid hydration
# ==========================================================


def _solve_hydration(t: str) -> Optional[MajorProductResult]:
    if not _has_any(t, ["h2o", "water"]) or not _has_any(t, ["h2so4", "acid", "h+"]):
        return None

    if "propene" in t:
        return MajorProductResult(
            "Acid-catalyzed hydration",
            "propan-2-ol",
            "Markovnikov hydration.",
        )

    return None


# ==========================================================
# 5) KMnO4
# ==========================================================


def _solve_kmno4(t: str) -> Optional[MajorProductResult]:
    if "kmno4" not in t:
        return None

    cold = _has_any(t, ["cold", "dilute", "alkaline"])
    hot = _has_any(t, ["hot", "heated"])

    if "propene" in t:
        if cold:
            return MajorProductResult(
                "Cold dilute KMnO4",
                "propane-1,2-diol",
                "Vicinal diol formation.",
            )
        if hot:
            return MajorProductResult(
                "Hot KMnO4",
                "ethanoic acid + carbon dioxide",
                "Oxidative cleavage: propene splits into ethanoic acid and CO2.",
            )
    # 2-butene oxidation: hot KMnO4 gives two acetic acid molecules
    if _has_any(t, ["2-butene", "but-2-ene", "butene-2", "ch3ch=chch3", "c4h8"]) and hot:
        return MajorProductResult(
            "Hot KMnO4",
            "2 ethanoic acid",
            "Oxidative cleavage of symmetrical internal alkene gives two molecules of ethanoic acid.",
        )

    return None


# ==========================================================
# 6) Ozonolysis
# ==========================================================


def _solve_ozonolysis(t: str) -> Optional[MajorProductResult]:
    if not _has_any(t, ["ozone", "o3"]):
        return None

    reductive = _has_any(t, ["zn", "zn/h2o", "dms"])
    oxidative = _has_any(t, ["h2o2"])

    if "propene" in t:
        if reductive:
            return MajorProductResult(
                "Ozonolysis (reductive)",
                "ethanal + methanal",
                "Aldehydes preserved: ethanal and methanal (from propene).",
            )
        if oxidative:
            return MajorProductResult(
                "Ozonolysis (oxidative)",
                "ethanoic acid + methanoic acid",
                "Oxidative workup oxidizes aldehydes to acids: ethanal → ethanoic acid; methanal → methanoic acid.",
            )

    return None


# ==========================================================
# 7) Alkyne hydration
# ==========================================================


def _solve_alkyne(t: str) -> Optional[MajorProductResult]:
    if not _has_any(t, ["alkyne", "c#c", "≡", "propyne", "ethyne"]):
        return None

    if "propyne" in t:
        if "hgso4" in t:
            return MajorProductResult(
                "HgSO4 hydration",
                "propanone",
                "Methyl ketone formation.",
            )
        if _has_any(t, ["bh3", "hydroboration"]):
            return MajorProductResult(
                "Hydroboration-oxidation",
                "propanal",
                "Anti-Markovnikov aldehyde.",
            )

    return None


# ==========================================================
# PUBLIC ENTRY
# ==========================================================


def solve_major_product_v1(question: str) -> Optional[MajorProductResult]:
    t = _lc(question)
    if not _is_major_product_question(t):
        return None

    for fn in (
        _solve_koh,
        _solve_cn,
        _solve_hbr,
        _solve_hydration,
        _solve_kmno4,
        _solve_ozonolysis,
        _solve_alkyne,
    ):
        r = fn(t)
        if r:
            return r

    return None
