"""
Solid State v1 — Deterministic utilities (JEE + NEET)

Scope (LOCKED):
- Unit cell volume (cubic)
- Density of unit cell:  ρ = (Z * M) / (N_A * a^3)
- Edge length relations:
    SC:  a = 2r
    BCC: a = 4r/√3
    FCC: a = 2√2 r
- Atoms per unit cell (Z): SC=1, BCC=2, FCC=4
- Packing efficiency (hard-sphere model):
    SC  ≈ 52.36%
    BCC ≈ 68.02%
    FCC ≈ 74.05%

No crystallography solvers, no geometry engines.
Pure algebraic helpers only.

Units:
- a in cm (if you want density in g/cm^3)
- r in cm (to match a)
- M in g/mol
- N_A default in mol^-1
"""

from __future__ import annotations

import math


class SolidStateError(ValueError):
    """Raised when invalid inputs are provided to solid state helpers."""


AVOGADRO_DEFAULT = 6.022e23  # mol^-1


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise SolidStateError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise SolidStateError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise SolidStateError(f"{name} must be > 0.")


def unit_cell_volume_cubic(a: float) -> float:
    """Volume of cubic unit cell: V = a^3"""
    _validate_positive(a, "a")
    return a ** 3


def density_unit_cell_cubic(z: int, molar_mass_g_per_mol: float, a_cm: float, avogadro: float = AVOGADRO_DEFAULT) -> float:
    """
    Density of a cubic unit cell:
      ρ = (Z * M) / (N_A * a^3)

    Args:
      z: number of atoms per unit cell (Z), must be >= 1
      molar_mass_g_per_mol: M > 0
      a_cm: edge length a in cm > 0 (for density in g/cm^3)
    """
    if z <= 0:
        raise SolidStateError("z must be >= 1.")
    _validate_positive(molar_mass_g_per_mol, "molar_mass_g_per_mol")
    _validate_positive(a_cm, "a_cm")
    _validate_positive(avogadro, "avogadro")

    return (z * molar_mass_g_per_mol) / (avogadro * (a_cm ** 3))


# -------------------------
# Edge length vs radius
# -------------------------

def a_from_r_sc(r: float) -> float:
    """Simple cubic: a = 2r"""
    _validate_positive(r, "r")
    return 2.0 * r


def a_from_r_bcc(r: float) -> float:
    """BCC: a = 4r/√3"""
    _validate_positive(r, "r")
    return (4.0 * r) / math.sqrt(3.0)


def a_from_r_fcc(r: float) -> float:
    """FCC: a = 2√2 r"""
    _validate_positive(r, "r")
    return 2.0 * math.sqrt(2.0) * r


def z_sc() -> int:
    return 1


def z_bcc() -> int:
    return 2


def z_fcc() -> int:
    return 4


# -------------------------
# Packing efficiency
# -------------------------

def packing_efficiency_sc() -> float:
    """SC packing efficiency ≈ 0.5236"""
    return math.pi / 6.0


def packing_efficiency_bcc() -> float:
    """BCC packing efficiency ≈ 0.6802"""
    return (math.sqrt(3.0) * math.pi) / 8.0


def packing_efficiency_fcc() -> float:
    """FCC packing efficiency ≈ 0.7405"""
    return math.pi / (3.0 * math.sqrt(2.0))
