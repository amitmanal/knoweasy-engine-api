"""
Inorganic Chemistry v1 — Chemical Bonding (Phase 1, Deterministic)

Scope (LOCKED):
- VSEPR (AXmEn) mapping to:
    * electron-domain geometry
    * molecular shape
    * ideal/typical bond angle (approx)
- Hybridization mapping from steric number (m + n):
    2 -> sp
    3 -> sp2
    4 -> sp3
    5 -> sp3d
    6 -> sp3d2
- Symmetry-based dipole moment (very coarse, exam-safe):
    - linear AX2 (E0) symmetric => zero
    - trigonal planar AX3 (E0) symmetric => zero
    - tetrahedral AX4 (E0) symmetric => zero
    - square planar AX4 (E2) symmetric => zero
    - octahedral AX6 (E0) symmetric => zero
    Otherwise generally non-zero (heuristic).

Notes:
- This module does NOT validate real molecules.
- It expects generic VSEPR descriptors like "AX4E0", "AX3E1", etc.
"""

from __future__ import annotations

from dataclasses import dataclass


class ChemicalBondingError(ValueError):
    """Invalid inputs for bonding helpers."""


@dataclass(frozen=True)
class VSEPRResult:
    descriptor: str
    steric_number: int
    electron_geometry: str
    molecular_shape: str
    ideal_bond_angle_deg: float | None  # None when not meaningful / variable


def parse_vsepr_descriptor(descriptor: str) -> tuple[int, int]:
    """
    Parses strings like:
      "AX4E0", "AX3E1", "AX2E2", "AX5E0", "AX6E0", "AX4E2"

    Returns:
      (m, n) where m = bonded atoms, n = lone pairs on central atom
    """
    d = (descriptor or "").strip().upper()
    if not d.startswith("AX") or "E" not in d:
        raise ChemicalBondingError("Invalid descriptor format. Use like 'AX4E0'.")

    try:
        # crude parse: AX<m>E<n>
        ax_part, e_part = d.split("E", 1)
        m_str = ax_part.replace("AX", "")
        m = int(m_str)
        n = int(e_part)
    except Exception as e:
        raise ChemicalBondingError("Failed to parse descriptor. Use like 'AX4E0'.") from e

    if m < 0 or n < 0:
        raise ChemicalBondingError("m and n must be >= 0.")
    if m == 0:
        raise ChemicalBondingError("m must be >= 1 for typical VSEPR.")
    return (m, n)


def steric_number(m: int, n: int) -> int:
    if m < 0 or n < 0:
        raise ChemicalBondingError("m and n must be >= 0.")
    return m + n


def hybridization_from_steric_number(sn: int) -> str:
    if not isinstance(sn, int) or sn <= 0:
        raise ChemicalBondingError("steric number must be a positive int.")
    mapping = {
        2: "sp",
        3: "sp2",
        4: "sp3",
        5: "sp3d",
        6: "sp3d2",
    }
    if sn not in mapping:
        raise ChemicalBondingError("Unsupported steric number for v1.")
    return mapping[sn]


def vsepr_predict(descriptor: str) -> VSEPRResult:
    """
    Deterministic mapping for common NCERT/JEE cases.
    """
    m, n = parse_vsepr_descriptor(descriptor)
    sn = steric_number(m, n)

    # Electron geometry by steric number
    eg_map = {
        2: "linear",
        3: "trigonal_planar",
        4: "tetrahedral",
        5: "trigonal_bipyramidal",
        6: "octahedral",
    }
    if sn not in eg_map:
        raise ChemicalBondingError("Unsupported steric number for v1.")
    electron_geom = eg_map[sn]

    # Molecular shape mapping (common)
    # Key by (m, n)
    shape_map = {
        (2, 0): ("linear", 180.0),
        (3, 0): ("trigonal_planar", 120.0),
        (2, 1): ("bent", 120.0),        # SO2-like (approx)
        (4, 0): ("tetrahedral", 109.5),
        (3, 1): ("trigonal_pyramidal", 107.0),  # NH3-like (approx)
        (2, 2): ("bent", 104.5),        # H2O-like (approx)
        (5, 0): ("trigonal_bipyramidal", 90.0),  # has 90 & 120; choose 90 as representative
        (4, 1): ("see_saw", 90.0),
        (3, 2): ("t_shaped", 90.0),
        (2, 3): ("linear", 180.0),
        (6, 0): ("octahedral", 90.0),
        (5, 1): ("square_pyramidal", 90.0),
        (4, 2): ("square_planar", 90.0),
    }

    if (m, n) not in shape_map:
        # Deterministic fallback: use electron geometry name, no fixed angle
        return VSEPRResult(
            descriptor=descriptor,
            steric_number=sn,
            electron_geometry=electron_geom,
            molecular_shape=electron_geom,
            ideal_bond_angle_deg=None,
        )

    mol_shape, angle = shape_map[(m, n)]
    return VSEPRResult(
        descriptor=descriptor,
        steric_number=sn,
        electron_geometry=electron_geom,
        molecular_shape=mol_shape,
        ideal_bond_angle_deg=angle,
    )


def dipole_moment_zero_by_symmetry(descriptor: str) -> bool:
    """
    Very coarse symmetry heuristic (exam-safe for standard symmetric cases).

    Returns True if dipole moment is expected to be zero due to symmetry.
    """
    m, n = parse_vsepr_descriptor(descriptor)

    # Symmetric, no lone pairs: generally zero dipole if identical outer atoms.
    if (m, n) in {(2, 0), (3, 0), (4, 0), (6, 0)}:
        return True

    # Square planar symmetric case (e.g., XeF4): AX4E2
    if (m, n) == (4, 2):
        return True

    return False
