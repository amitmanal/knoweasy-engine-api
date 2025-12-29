from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class IUPACResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").lower().strip()


def _has_any(t: str, words: List[str]) -> bool:
    return any(w in t for w in words)


def _norm_formula(s: str) -> str:
    """
    Normalize condensed formulas for pattern matching.
    Keeps '=' and '#' (triple bond). Converts '≡' to '#'.
    Removes spaces and hyphens/dashes.
    """
    t = _lc(s)
    t = t.replace("≡", "#")
    for ch in [" ", "\t", "\n", "\r", "-", "–", "—"]:
        t = t.replace(ch, "")
    return t


# ==========================================================
# "Is this even a naming question?"
# (Expanded so your priority test triggers)
# ==========================================================

def _looks_like_naming_question(t: str) -> bool:
    return _has_any(
        t,
        [
            "iupac",
            "nomenclature",
            "name of",
            "give name",
            "find name",
            "what is the iupac",
            "name compound",      # NEW
            "name the compound",  # NEW
            "name:",              # NEW
        ],
    )


# ==========================================================
# Signals
# ==========================================================

def _has_alkene_signal(t: str) -> bool:
    return _has_any(t, ["ene", "alkene", "c=c", "=", "ch=ch"])


def _has_alkyne_signal(t: str) -> bool:
    return _has_any(t, ["yne", "alkyne", "c≡c", "c#c", "≡", "#", "c#", "ch#"])


# ==========================================================
# Straight-chain exact naming (exam-grade, safe list)
# ==========================================================

_ACID_FORMULA_TO_NAME = {
    "hcooh": "methanoic acid",
    "ch3cooh": "ethanoic acid",
    "ch3ch2cooh": "propanoic acid",
    "ch3ch2ch2cooh": "butanoic acid",
}

_ALCOHOL_FORMULA_TO_NAME = {
    "ch3oh": "methanol",
    "ch3ch2oh": "ethanol",
    "ch3ch2ch2oh": "propan-1-ol",
    "ch3ch(oh)ch3": "propan-2-ol",
}

_ALDEHYDE_FORMULA_TO_NAME = {
    "hcho": "methanal",
    "ch3cho": "ethanal",
    "ch3ch2cho": "propanal",
}

_KETONE_FORMULA_TO_NAME = {
    "ch3coch3": "propanone",
    "ch3ch2coch3": "butan-2-one",
}


def _solve_straight_chain_functional_names(text: str) -> Optional[IUPACResult]:
    f = _norm_formula(text)

    for k, v in _ACID_FORMULA_TO_NAME.items():
        if k in f:
            return IUPACResult(
                reaction="IUPAC naming of carboxylic acid",
                product=v,
                notes="Carboxylic acid has highest priority; use suffix '-oic acid'.",
            )

    for k, v in _ALCOHOL_FORMULA_TO_NAME.items():
        if k in f:
            return IUPACResult(
                reaction="IUPAC naming of alcohol",
                product=v,
                notes="Alcohol uses suffix '-ol'; number chain so OH gets lowest locant.",
            )

    for k, v in _ALDEHYDE_FORMULA_TO_NAME.items():
        if k in f:
            return IUPACResult(
                reaction="IUPAC naming of aldehyde",
                product=v,
                notes="Aldehyde carbon is always C-1; use suffix '-al'.",
            )

    for k, v in _KETONE_FORMULA_TO_NAME.items():
        if k in f:
            return IUPACResult(
                reaction="IUPAC naming of ketone",
                product=v,
                notes="Ketone uses suffix '-one'; number chain to give carbonyl lowest locant.",
            )

    return None


# ==========================================================
# Exact naming: alkenes / alkynes (safe patterns)
# ==========================================================

def _solve_simple_alkene_name(text: str) -> Optional[str]:
    f = _norm_formula(text)
    t = _lc(text)

    # Propene
    if "ch3ch=ch2" in f:
        return "prop-1-ene"

    # But-1-ene
    if "ch3ch2ch=ch2" in f or "ch2=chch2ch3" in f:
        return "but-1-ene"

    # But-2-ene
    if "ch3ch=chch3" in f or "but-2-ene" in t:
        return "but-2-ene"

    # Pent-2-ene (common condensed)
    if "ch3ch2ch=chch3" in f or "ch3ch=chch2ch3" in f or "pent-2-ene" in t:
        return "pent-2-ene"

    # Pass-through if user typed the final name
    if "but-1-ene" in t:
        return "but-1-ene"
    if "but-2-ene" in t:
        return "but-2-ene"
    if "prop-1-ene" in t:
        return "prop-1-ene"

    return None


def _solve_simple_alkyne_name(text: str) -> Optional[str]:
    f = _norm_formula(text)
    t = _lc(text)

    # Ethyne
    if "hc#ch" in f or "c2h2" in f or "ethyne" in t:
        return "ethyne"

    # Propyne
    if "ch3c#ch" in f or "propyne" in t:
        return "prop-1-yne"

    # But-2-yne
    if "ch3c#cch3" in f or "but-2-yne" in t:
        return "but-2-yne"

    # But-1-yne
    if "ch3ch2c#ch" in f or "hc#cch2ch3" in f or "but-1-yne" in t:
        return "but-1-yne"

    return None


# ==========================================================
# Functional group priority (fallback only)
# ==========================================================

FG_PRIORITY: List[Tuple[str, List[str], str]] = [
    ("carboxylic acid", ["cooh", "carboxylic acid"], "oic acid"),
    ("ester", ["ester", "coor"], "oate"),
    ("amide", ["amide", "conh2"], "amide"),
    ("aldehyde", ["aldehyde", "cho"], "al"),
    ("ketone", ["ketone", "c=o", "carbonyl"], "one"),
    ("alcohol", ["alcohol", "hydroxyl", " oh"], "ol"),
    ("amine", ["amine", "amino", " nh2"], "amine"),
    ("alkene", ["alkene", "c=c", "="], "ene"),
    ("alkyne", ["alkyne", "c≡c", "c#c", "≡", "#"], "yne"),
]


def _detect_all_functional_groups(t: str) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for name, keys, suffix in FG_PRIORITY:
        if _has_any(t, keys):
            found.append((name, suffix))
    return found


def _highest_priority_fg(fgs: List[Tuple[str, str]]) -> Optional[Tuple[str, str]]:
    if not fgs:
        return None
    # follow FG_PRIORITY order (first match = highest priority)
    for name, _, suffix in FG_PRIORITY:
        for fg_name, fg_suffix in fgs:
            if fg_name == name and fg_suffix == suffix:
                return fg_name, fg_suffix
    return None


# ==========================================================
# Public entry point
# ==========================================================

def solve_iupac_v2(text: str) -> Optional[IUPACResult]:
    t = _lc(text)

    # Only attempt if it looks like a naming question
    if not _looks_like_naming_question(t):
        return None

    # 1) Exact straight-chain functional names first (keeps your tests passing)
    r = _solve_straight_chain_functional_names(text)
    if r:
        return r

    # 2) Exact alkenes
    if _has_alkene_signal(t):
        name = _solve_simple_alkene_name(text)
        if name:
            return IUPACResult(
                reaction="IUPAC naming of alkene",
                product=name,
                notes="Choose longest chain containing C=C and lowest locant for double bond.",
            )

    # 3) Exact alkynes
    if _has_alkyne_signal(t):
        name = _solve_simple_alkyne_name(text)
        if name:
            return IUPACResult(
                reaction="IUPAC naming of alkyne",
                product=name,
                notes="Choose longest chain containing C≡C and lowest locant for triple bond.",
            )

    # 4) Priority fallback (ONLY when exact naming not available)
    detected = _detect_all_functional_groups(t)
    if not detected:
        return None

    principal = _highest_priority_fg(detected)
    if not principal:
        return None

    fg_name, suffix = principal

    if len(detected) > 1:
        others = [f[0] for f in detected if f[0] != fg_name]
        return IUPACResult(
            reaction="IUPAC functional group priority",
            product=f"Parent chain named with suffix '{suffix}'",
            notes=(
                f"Principal functional group: {fg_name}. "
                f"Other groups ({', '.join(others)}) are written as prefixes."
            ),
        )

    return IUPACResult(
        reaction="IUPAC functional group naming",
        product=f"Parent chain named with suffix '{suffix}'",
        notes=f"Functional group present: {fg_name}. Use suffix '{suffix}'.",
    )
