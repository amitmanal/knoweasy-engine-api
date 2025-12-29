"""
Solid State v1 — Voids & Radius Ratio Rules (deterministic)

Scope (LOCKED):
- Counts of tetrahedral and octahedral voids in close packing
- Radius ratio rules (r/R limits) for coordination sites
- Simple r (void) vs R (host sphere) relations (standard NCERT/JEE values)
- Occupancy helper: number of voids filled given number of spheres

Definitions:
- For N spheres in close packing (hcp/ccp):
    tetrahedral voids = 2N
    octahedral voids  = N
- Radius ratio limits (r/R):
    tetrahedral site: 0.225
    octahedral site : 0.414
    cubic site      : 0.732

These are standard approximations used in exam settings.
"""

from __future__ import annotations


class SolidStateVoidsError(ValueError):
    """Raised when invalid inputs are provided to void helpers."""


def _ensure_int_non_negative(x: int, name: str) -> None:
    if x is None:
        raise SolidStateVoidsError(f"{name} must not be None.")
    if not isinstance(x, int):
        raise SolidStateVoidsError(f"{name} must be an int.")
    if x < 0:
        raise SolidStateVoidsError(f"{name} must be >= 0.")


def tetrahedral_voids_count(n_spheres: int) -> int:
    """In close packing: tetrahedral voids = 2N"""
    _ensure_int_non_negative(n_spheres, "n_spheres")
    return 2 * n_spheres


def octahedral_voids_count(n_spheres: int) -> int:
    """In close packing: octahedral voids = N"""
    _ensure_int_non_negative(n_spheres, "n_spheres")
    return n_spheres


def radius_ratio_tetrahedral() -> float:
    """r/R for tetrahedral void (approx)"""
    return 0.225


def radius_ratio_octahedral() -> float:
    """r/R for octahedral void (approx)"""
    return 0.414


def radius_ratio_cubic() -> float:
    """r/R for cubic void (approx)"""
    return 0.732


def can_fit_in_tetrahedral_site(r_small: float, r_host: float) -> bool:
    """True if r_small/r_host <= 0.225"""
    if r_small < 0 or r_host <= 0:
        raise SolidStateVoidsError("r_small must be >=0 and r_host must be >0.")
    return (r_small / r_host) <= radius_ratio_tetrahedral()


def can_fit_in_octahedral_site(r_small: float, r_host: float) -> bool:
    """True if r_small/r_host <= 0.414"""
    if r_small < 0 or r_host <= 0:
        raise SolidStateVoidsError("r_small must be >=0 and r_host must be >0.")
    return (r_small / r_host) <= radius_ratio_octahedral()


def can_fit_in_cubic_site(r_small: float, r_host: float) -> bool:
    """True if r_small/r_host <= 0.732"""
    if r_small < 0 or r_host <= 0:
        raise SolidStateVoidsError("r_small must be >=0 and r_host must be >0.")
    return (r_small / r_host) <= radius_ratio_cubic()


def filled_voids(n_spheres: int, void_type: str, fraction_filled: float) -> float:
    """
    Returns number of voids filled when a fraction is occupied.

    void_type: "tetrahedral" or "octahedral"
    fraction_filled: between 0 and 1 inclusive
    """
    _ensure_int_non_negative(n_spheres, "n_spheres")
    vt = (void_type or "").strip().lower()
    if vt not in ("tetrahedral", "octahedral"):
        raise SolidStateVoidsError("void_type must be 'tetrahedral' or 'octahedral'.")
    if fraction_filled < 0 or fraction_filled > 1:
        raise SolidStateVoidsError("fraction_filled must be in [0,1].")

    total = tetrahedral_voids_count(n_spheres) if vt == "tetrahedral" else octahedral_voids_count(n_spheres)
    return total * fraction_filled
