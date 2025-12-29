# src/coordination_compounds_v1.py
"""
KnowEasy Engine v1 — Coordination Compounds — v1 (Deterministic)

Scope (LOCKED):
1) Werner’s theory (core postulates)
2) Coordination number
3) Ligand classification: mono / bi / ambidentate
4) Oxidation state vs coordination number (basic)
5) Isomerism:
   - Structural: ionisation, hydrate, linkage, coordination isomerism (intro)
   - Stereoisomerism: geometrical (cis/trans; fac/mer), optical (intro)
6) Basic nomenclature rules (deterministic; no NLP)

Design constraints:
- Deterministic outputs only
- No refactors to existing codebase
- Minimal parsing (simple bracket complexes)
- Exam-safe: focus on common patterns used in JEE/NEET

NOTE:
This is v1 foundation. Later versions can add:
- CFT/weak-strong field, pairing, magnetic moment calculation
- Isomer counting engines in full generality
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# -------------------------
# Werner theory (facts)
# -------------------------

def werners_theory_postulates() -> List[str]:
    return [
        "Metal shows two types of valencies: primary and secondary",
        "Primary valency is ionisable and corresponds to oxidation state",
        "Secondary valency is non-ionisable and corresponds to coordination number",
        "Secondary valencies are directed in space giving definite geometry",
        "Ions/ligands satisfying secondary valency are inside coordination sphere (brackets)",
        "Ions satisfying primary valency remain outside coordination sphere and are ionisable",
    ]


# -------------------------
# Ligands (classification)
# -------------------------

MONODENTATE_LIGANDS = {
    "NH3", "H2O", "CO", "NO", "Cl-", "Br-", "I-", "F-",
    "CN-", "SCN-", "NO2-", "OH-", "NCS-"
}

BIDENTATE_LIGANDS = {
    "en",         # ethylenediamine (neutral bidentate)
    "ox",         # oxalate (C2O4^2-)
    "acac",       # acetylacetonate (common shorthand)
}

AMBIDENTATE_LIGANDS = {
    "CN-",        # (C-bonded) cyanide; also considered ambidentate conceptually in some texts
    "SCN-",       # thiocyanate (S or N)
    "NCS-",       # same as SCN- but written as N-bonded
    "NO2-",       # nitro (N) / nitrito (O)
}

# Typical charges for quick oxidation state calculations.
# (Exam-safe limited set; can expand later.)
LIGAND_CHARGES: Dict[str, int] = {
    "NH3": 0,
    "H2O": 0,
    "CO": 0,
    "NO": 0,
    "en": 0,
    "Cl-": -1,
    "Br-": -1,
    "I-": -1,
    "F-": -1,
    "CN-": -1,
    "SCN-": -1,
    "NCS-": -1,
    "NO2-": -1,
    "OH-": -1,
    "ox": -2,
    # acac often treated as -1 in many complexes
    "acac": -1,
}


def ligand_denticity(ligand: str) -> int:
    """
    Returns denticity for supported ligands.
    """
    lig = ligand.strip()
    if lig in BIDENTATE_LIGANDS:
        return 2
    if lig in MONODENTATE_LIGANDS or lig in AMBIDENTATE_LIGANDS:
        return 1
    raise ValueError(f"Unsupported ligand for v1 denticity: {ligand!r}")


def ligand_type(ligand: str) -> str:
    """
    Returns ligand classification: monodentate / bidentate / ambidentate.
    Note: Some ligands can be considered in multiple categories in textbooks;
    v1 provides a deterministic classification for exam use.
    """
    lig = ligand.strip()
    if lig in BIDENTATE_LIGANDS:
        return "bidentate"
    if lig in AMBIDENTATE_LIGANDS:
        return "ambidentate"
    if lig in MONODENTATE_LIGANDS:
        return "monodentate"
    raise ValueError(f"Unsupported ligand for v1 classification: {ligand!r}")


# -------------------------
# Complex representation
# -------------------------

@dataclass(frozen=True)
class ComplexSpec:
    """
    Minimal deterministic representation.

    Example:
      [Co(NH3)6]Cl3  -> complex_charge = +3, outside_ions = ["Cl-","Cl-","Cl-"]
      [Fe(CN)6]4-    -> complex_charge = -4, outside_ions = []
    """
    metal: str
    ligands: Tuple[Tuple[str, int], ...]  # (ligand, count)
    complex_charge: int
    outside_ions: Tuple[str, ...]         # normalized ion strings like "Cl-"

    def total_ligand_count(self) -> int:
        return sum(n for _, n in self.ligands)

    def coordination_number(self) -> int:
        cn = 0
        for lig, n in self.ligands:
            cn += ligand_denticity(lig) * n
        return cn


# -------------------------
# Parsing (very small)
# -------------------------

def _parse_outside_ions(formula_tail: str) -> Tuple[str, ...]:
    """
    Very small parser for outside ions like 'Cl3' or 'SO4' not implemented.
    v1 supports only halide outside ions in simple salts: Cl, Br, I, F with numeric suffix.
    Examples:
      "Cl3" -> ("Cl-","Cl-","Cl-")
      ""    -> ()
    """
    tail = formula_tail.strip()
    if tail == "":
        return ()

    # Support: Cl3, Br2, I, F, Cl
    # Normalize to "Cl-" etc.
    # Determine element symbol (Cl/Br/I/F) and count
    symbols = ("Cl", "Br", "I", "F")
    sym = None
    for s in symbols:
        if tail.startswith(s):
            sym = s
            rest = tail[len(s):]
            count = int(rest) if rest else 1
            ion = f"{s}-"
            return tuple([ion] * count)

    raise ValueError(f"Unsupported outside ion tail for v1: {formula_tail!r}")


def parse_simple_complex_formula(formula: str) -> ComplexSpec:
    """
    Parses limited set:
      [M(L)x(L)y]charge  OR  [M(L)x]Cl3

    Supported:
    - One metal symbol: Co, Fe, Cr, Ni, Cu, Pt, Pd, etc. (no validation list)
    - Ligands: those in LIGAND_CHARGES
    - Ligand counts as integers directly after ligand token: NH3)6, CN)6 etc.
    - Charge formats:
        ...]3+ , ...]2- , ...]4-  OR no explicit bracket charge in salts
    - Outside ions: only halide tails (Cl3, Br2, etc.)

    This is deterministic and intentionally limited for v1 tests.
    """
    s = formula.strip()

    if not s.startswith("[") or "]" not in s:
        raise ValueError(f"Unsupported complex format (missing brackets): {formula!r}")

    inside, after = s[1:].split("]", 1)
    after = after.strip()

    # Parse metal: first 1-2 chars (capital + optional lowercase)
    if len(inside) < 1 or not inside[0].isalpha() or not inside[0].isupper():
        raise ValueError(f"Invalid metal in complex: {formula!r}")
    metal = inside[0]
    idx = 1
    if idx < len(inside) and inside[idx].islower():
        metal += inside[idx]
        idx += 1

    lig_part = inside[idx:].strip()
    if lig_part == "":
        raise ValueError(f"No ligands found: {formula!r}")

    # Very simple ligand parsing:
    # Expect pattern like "(NH3)6" repeated, or "(CN)6"
    ligands: List[Tuple[str, int]] = []
    i = 0
    while i < len(lig_part):
        if lig_part[i].isspace():
            i += 1
            continue
        if lig_part[i] != "(":
            raise ValueError(f"Unsupported ligand formatting (expected '('): {formula!r}")
        j = lig_part.find(")", i)
        if j == -1:
            raise ValueError(f"Unclosed ligand bracket: {formula!r}")
        lig = lig_part[i + 1:j].strip()
        k = j + 1
        # read count digits if present
        digits = ""
        while k < len(lig_part) and lig_part[k].isdigit():
            digits += lig_part[k]
            k += 1
        count = int(digits) if digits else 1
        if lig not in LIGAND_CHARGES:
            raise ValueError(f"Unsupported ligand in v1: {lig!r}")
        ligands.append((lig, count))
        i = k

    # Determine bracket charge if explicitly given like "3+" or "4-"
    complex_charge = 0
    outside_ions: Tuple[str, ...] = ()

    if after == "":
        # no charge, no outside ions -> treat as neutral complex
        complex_charge = 0
        outside_ions = ()
    else:
        # If after begins with digits followed by +/-, it's bracket charge
        if after[-1] in ("+", "-") and any(ch.isdigit() for ch in after[:-1]):
            sign = +1 if after[-1] == "+" else -1
            mag_str = after[:-1].strip()
            if not mag_str.isdigit():
                raise ValueError(f"Unsupported charge format: {formula!r}")
            complex_charge = sign * int(mag_str)
            outside_ions = ()
        else:
            # treat as salt tail of outside ions (halides)
            outside_ions = _parse_outside_ions(after)
            # if salt tail exists, bracket charge equals opposite of total outside charge
            # only halides -1 each
            complex_charge = len(outside_ions)  # positive to balance -1 ions

    return ComplexSpec(
        metal=metal,
        ligands=tuple(ligands),
        complex_charge=complex_charge,
        outside_ions=outside_ions,
    )


# -------------------------
# Oxidation state (basic)
# -------------------------

def oxidation_state_of_metal(spec: ComplexSpec) -> int:
    """
    Computes oxidation state using:
      oxidation_state + sum(ligand_charges * count) = complex_charge
    """
    total_ligand_charge = 0
    for lig, n in spec.ligands:
        total_ligand_charge += LIGAND_CHARGES[lig] * n
    return spec.complex_charge - total_ligand_charge


# -------------------------
# Isomerism helpers (deterministic)
# -------------------------

def possible_geometrical_isomerism(geometry: str, coordination_number: int) -> bool:
    """
    Very exam-safe rule-of-thumb:
    - Square planar CN=4 => geometrical isomerism possible (cis/trans) in MA2B2 type, etc.
    - Octahedral CN=6 => geometrical possible (cis/trans, fac/mer) depending on ligand sets.
    v1 only decides 'possible in principle' by CN + geometry label.
    """
    g = geometry.strip().lower()
    if g == "square_planar" and coordination_number == 4:
        return True
    if g == "octahedral" and coordination_number == 6:
        return True
    return False


def possible_optical_isomerism(geometry: str, coordination_number: int, has_bidentate: bool) -> bool:
    """
    Simplified exam-safe trigger:
    - Octahedral CN=6 with bidentate ligands can show optical isomerism (e.g., [Co(en)3]3+).
    - Tetrahedral CN=4 with four different ligands can be optical, but v1 does not parse that.
    So v1 focuses on common JEE/NEET pattern: octahedral + bidentate.
    """
    g = geometry.strip().lower()
    if g == "octahedral" and coordination_number == 6 and has_bidentate:
        return True
    return False


# -------------------------
# Nomenclature (minimal deterministic)
# -------------------------

def ligand_name_token(ligand: str) -> str:
    """
    Deterministic ligand name tokens (minimal list).
    """
    lig = ligand.strip()
    mapping = {
        "NH3": "ammine",
        "H2O": "aqua",
        "CO": "carbonyl",
        "NO": "nitrosyl",
        "Cl-": "chloro",
        "Br-": "bromo",
        "I-": "iodo",
        "F-": "fluoro",
        "CN-": "cyano",
        "OH-": "hydroxo",
        "NO2-": "nitro",   # linkage to nitrito is handled separately conceptually
        "SCN-": "thiocyanato",
        "NCS-": "isothiocyanato",
        "en": "ethane-1,2-diamine",
        "ox": "oxalato",
        "acac": "acetylacetonato",
    }
    if lig not in mapping:
        raise ValueError(f"Unsupported ligand for v1 naming: {ligand!r}")
    return mapping[lig]


def multiplicative_prefix(count: int, is_polydentate_name: bool) -> str:
    """
    Prefix rules:
    - mono often omitted
    - di, tri, tetra... for simple ligands
    - bis, tris, tetrakis... for polydentate or complex ligand names like en, ox, acac
    """
    if count <= 0:
        raise ValueError("count must be positive")
    if count == 1:
        return ""

    simple = {2: "di", 3: "tri", 4: "tetra", 5: "penta", 6: "hexa"}
    poly = {2: "bis", 3: "tris", 4: "tetrakis", 5: "pentakis", 6: "hexakis"}
    if is_polydentate_name:
        if count not in poly:
            raise ValueError(f"Unsupported count for v1 poly prefix: {count}")
        return poly[count]
    if count not in simple:
        raise ValueError(f"Unsupported count for v1 simple prefix: {count}")
    return simple[count]


def build_basic_complex_name(spec: ComplexSpec) -> str:
    """
    Very minimal deterministic naming:
    - Ligands listed in alphabetical order of name token
    - Apply prefixes
    - Metal name as symbol (not full IUPAC metal name set)
    - Oxidation state in Roman numerals

    Example:
      [Co(NH3)6]Cl3 -> "hexaammine cobalt(III) chloride"
    This is simplified but exam-usable for many questions.
    """
    # Expand ligands into name tokens with counts
    ligand_items = []
    for lig, n in spec.ligands:
        token = ligand_name_token(lig)
        is_poly = lig in BIDENTATE_LIGANDS or lig == "acac"
        pref = multiplicative_prefix(n, is_poly)
        if pref == "":
            ligand_items.append(f"{token}")
        else:
            # bis/tris require parentheses in strict IUPAC; v1 keeps deterministic readable form
            if is_poly:
                ligand_items.append(f"{pref}({token})")
            else:
                ligand_items.append(f"{pref}{token}")

    ligand_items_sorted = sorted(ligand_items)
    ox = oxidation_state_of_metal(spec)
    roman = int_to_roman(ox)

    # Outside ions (only halides supported in parser)
    outside = ""
    if spec.outside_ions:
        # all same
        outside_ion = spec.outside_ions[0]
        outside_name = ligand_name_token(outside_ion)  # chloro/bromo/iodo/fluoro
        # as counter-ion use -ide in English; keep deterministic simple:
        # chloro -> chloride, bromo -> bromide...
        outside_map = {"chloro": "chloride", "bromo": "bromide", "iodo": "iodide", "fluoro": "fluoride"}
        outside = outside_map.get(outside_name, "counterion")

    core = " ".join(ligand_items_sorted + [f"{spec.metal.lower()}({roman})"])
    if outside:
        return f"{core} {outside}"
    return core


def int_to_roman(n: int) -> str:
    """
    Supports typical oxidation states in coordination chemistry.
    """
    if n <= 0:
        # oxidation states for metals in complexes are positive typically (v1),
        # keep strict for deterministic output
        raise ValueError(f"Unsupported non-positive oxidation state for roman: {n}")
    vals = [
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")
    ]
    out = ""
    x = n
    for v, sym in vals:
        while x >= v:
            out += sym
            x -= v
    return out
