"""
Electrochemistry v1 — Core deterministic utilities (JEE + NEET)

Scope (LOCKED):
- Cell EMF from standard electrode potentials
- Identify anode/cathode from standard reduction potentials
- Nernst equation (base-10 form, exam standard)
- Gibbs relation: ΔG° = -n F E°
- Reaction quotient Q handling (expects caller provides Q)

No simulations, no balancing, no solvers.
Pure algebraic helpers only.

Conventions:
- Standard potentials are standard reduction potentials (E°red).
- E°cell = E°cathode - E°anode (both reduction potentials)
- Nernst (base-10):
    E = E° - (0.0591 / n) * log10(Q)   at 298 K
  General form:
    E = E° - (2.303 R T / (n F)) * log10(Q)

Units:
- E in Volts (V)
- ΔG° in J/mol
- T in Kelvin
"""

from __future__ import annotations

import math
from typing import Tuple


class ElectrochemistryError(ValueError):
    """Raised when invalid inputs are provided to electrochemistry helpers."""


R_GAS_DEFAULT = 8.314  # J/mol·K
FARADAY_DEFAULT = 96485.0  # C/mol (J/V·mol)


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ElectrochemistryError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ElectrochemistryError(f"{name} must be a finite number (not NaN).")


def _validate_positive(x: float, name: str) -> None:
    _ensure_finite_number(x, name)
    if x <= 0:
        raise ElectrochemistryError(f"{name} must be > 0.")


def ecell_standard(e_cathode_red: float, e_anode_red: float) -> float:
    """
    Standard EMF:
      E°cell = E°cathode - E°anode
    Inputs are standard reduction potentials (E°red).
    """
    _ensure_finite_number(e_cathode_red, "e_cathode_red")
    _ensure_finite_number(e_anode_red, "e_anode_red")
    return e_cathode_red - e_anode_red


def identify_cathode_anode_from_reduction_potentials(
    e1_red: float,
    e2_red: float,
) -> Tuple[str, str]:
    """
    Given two standard reduction potentials, identify which acts as cathode/anode
    in a spontaneous galvanic cell under standard conditions.

    Rule:
      Higher E°red => cathode (reduction)
      Lower  E°red => anode (oxidation)

    Returns:
      ("electrode1" or "electrode2" as cathode, then anode)
    """
    _ensure_finite_number(e1_red, "e1_red")
    _ensure_finite_number(e2_red, "e2_red")

    if e1_red > e2_red:
        return ("electrode1", "electrode2")
    if e2_red > e1_red:
        return ("electrode2", "electrode1")
    # equal potentials => no driving force; define deterministic ordering
    return ("electrode1", "electrode2")


def nernst_potential(
    e0_cell: float,
    n_electrons: int,
    reaction_quotient_q: float,
    temperature_k: float = 298.0,
    r_gas: float = R_GAS_DEFAULT,
    faraday: float = FARADAY_DEFAULT,
) -> float:
    """
    Nernst equation (base-10):
      E = E° - (2.303 R T / (n F)) * log10(Q)

    Notes:
    - Q must be > 0
    - n must be >= 1 (integer)
    - T must be > 0
    """
    _ensure_finite_number(e0_cell, "e0_cell")
    _ensure_finite_number(reaction_quotient_q, "reaction_quotient_q")
    _ensure_finite_number(temperature_k, "temperature_k")
    _ensure_finite_number(r_gas, "r_gas")
    _ensure_finite_number(faraday, "faraday")

    if n_electrons <= 0:
        raise ElectrochemistryError("n_electrons must be >= 1.")
    _validate_positive(reaction_quotient_q, "reaction_quotient_q")
    _validate_positive(temperature_k, "temperature_k")
    _validate_positive(r_gas, "r_gas")
    _validate_positive(faraday, "faraday")

    factor = (2.303 * r_gas * temperature_k) / (n_electrons * faraday)
    return e0_cell - factor * math.log10(reaction_quotient_q)


def nernst_potential_298k(
    e0_cell: float,
    n_electrons: int,
    reaction_quotient_q: float,
) -> float:
    """
    Exam shortcut at 298K:
      E = E° - (0.0591 / n) * log10(Q)
    """
    _ensure_finite_number(e0_cell, "e0_cell")
    _ensure_finite_number(reaction_quotient_q, "reaction_quotient_q")
    if n_electrons <= 0:
        raise ElectrochemistryError("n_electrons must be >= 1.")
    _validate_positive(reaction_quotient_q, "reaction_quotient_q")

    return e0_cell - (0.0591 / n_electrons) * math.log10(reaction_quotient_q)


def delta_g_standard_from_e0(e0_cell: float, n_electrons: int, faraday: float = FARADAY_DEFAULT) -> float:
    """
    ΔG° = -n F E°
    Returns ΔG° in J/mol.
    """
    _ensure_finite_number(e0_cell, "e0_cell")
    if n_electrons <= 0:
        raise ElectrochemistryError("n_electrons must be >= 1.")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")

    return -n_electrons * faraday * e0_cell


def e0_from_delta_g_standard(delta_g_j_per_mol: float, n_electrons: int, faraday: float = FARADAY_DEFAULT) -> float:
    """
    Inverse of ΔG° relation:
      E° = -ΔG° / (nF)
    """
    _ensure_finite_number(delta_g_j_per_mol, "delta_g_j_per_mol")
    if n_electrons <= 0:
        raise ElectrochemistryError("n_electrons must be >= 1.")
    _ensure_finite_number(faraday, "faraday")
    _validate_positive(faraday, "faraday")

    return -delta_g_j_per_mol / (n_electrons * faraday)
