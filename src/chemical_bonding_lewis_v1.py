"""
Inorganic Chemistry v1 — Chemical Bonding (Lewis helpers, Deterministic)

Scope (LOCKED):
- Formal charge calculation:
    FC = valence_electrons - (nonbonding_electrons + bonding_electrons/2)
- Bond order helpers:
    * MO-theory bond order from (Nb, Na): BO = (Nb - Na)/2
    * Simple average bond order from resonance (sum bond orders / number of equivalent bonds)

Notes:
- This module does NOT generate Lewis structures.
- It provides deterministic arithmetic utilities used in many exam problems.
"""

from __future__ import annotations


class LewisBondingError(ValueError):
    """Invalid inputs for Lewis bonding helpers."""


def formal_charge(valence_electrons: int, nonbonding_electrons: int, bonding_electrons: int) -> int:
    """
    Formal charge:
      FC = V - (N + B/2)

    Args:
      valence_electrons (V) >= 0
      nonbonding_electrons (N) >= 0
      bonding_electrons (B) >= 0 (should be even in typical Lewis counts, but we allow any non-negative int)

    Returns integer FC (can be negative).
    """
    if not all(isinstance(x, int) for x in (valence_electrons, nonbonding_electrons, bonding_electrons)):
        raise LewisBondingError("All inputs must be integers.")
    if valence_electrons < 0 or nonbonding_electrons < 0 or bonding_electrons < 0:
        raise LewisBondingError("Inputs must be >= 0.")
    # FC is integer if bonding_electrons is even; if odd, we still compute using integer division? No.
    # Use exact half as float then cast safely if it is whole.
    fc = valence_electrons - (nonbonding_electrons + bonding_electrons / 2.0)
    # In exam settings FC should be integer; enforce near-integer.
    if abs(fc - round(fc)) > 1e-9:
        raise LewisBondingError("Formal charge is not an integer; check bonding electron count.")
    return int(round(fc))


def mo_bond_order(nb: int, na: int) -> float:
    """
    MO bond order:
      BO = (Nb - Na)/2

    Args:
      nb, na >= 0 integers
    """
    if not isinstance(nb, int) or not isinstance(na, int):
        raise LewisBondingError("nb and na must be integers.")
    if nb < 0 or na < 0:
        raise LewisBondingError("nb and na must be >= 0.")
    return (nb - na) / 2.0


def average_bond_order_from_resonance(bond_orders: list[float]) -> float:
    """
    Average bond order for equivalent bonds across resonance structures.

    Example:
      O3 (two equivalent O-O bonds): bond orders [1.5, 1.5] => avg 1.5
      NO2- (two equivalent N-O bonds): [1.5, 1.5] => avg 1.5

    Args:
      bond_orders: non-empty list of positive floats
    """
    if not isinstance(bond_orders, list) or len(bond_orders) == 0:
        raise LewisBondingError("bond_orders must be a non-empty list.")
    s = 0.0
    for bo in bond_orders:
        if not isinstance(bo, (int, float)):
            raise LewisBondingError("bond order must be numeric.")
        if bo <= 0:
            raise LewisBondingError("bond order must be > 0.")
        s += float(bo)
    return s / len(bond_orders)
