"""
Chemical Equilibrium v1 — Core deterministic utilities

Scope (LOCKED):
- Law of mass action
- Equilibrium constant (Kc, Kp)
- Reaction quotient (Qc)
- Degree of dissociation (simple cases)
- Kp–Kc relation
- Le Chatelier qualitative prediction (logic-only)

No numerical solvers, no iteration, no ICE-table solving.
Pure algebraic helpers only.
"""

from __future__ import annotations

from typing import Dict


R_IDEAL_DEFAULT = 0.082057  # L·atm / (mol·K), exam-standard for Kp–Kc


class ChemicalEquilibriumError(ValueError):
    """Raised when invalid inputs are provided to chemical equilibrium helpers."""


def _ensure_finite_number(x: float, name: str) -> None:
    if x is None:
        raise ChemicalEquilibriumError(f"{name} must not be None.")
    if isinstance(x, float) and x != x:
        raise ChemicalEquilibriumError(f"{name} must be a finite number (not NaN).")


def equilibrium_constant_from_concentrations(
    concentrations: Dict[str, float],
    stoichiometric_powers: Dict[str, int],
) -> float:
    """
    Law of mass action:
        Kc = Π [C_i]^{ν_i}

    Inputs:
    - concentrations: species -> concentration (mol/L)
    - stoichiometric_powers: species -> power (positive for products,
                               negative for reactants already encoded)

    Example:
      aA + bB ⇌ cC + dD
      powers = {"A": -a, "B": -b, "C": c, "D": d}
    """
    if not concentrations or not stoichiometric_powers:
        raise ChemicalEquilibriumError("concentrations and powers must not be empty.")

    kc = 1.0
    for species, power in stoichiometric_powers.items():
        if species not in concentrations:
            raise ChemicalEquilibriumError(f"Missing concentration for {species}.")
        c = concentrations[species]
        _ensure_finite_number(c, f"[{species}]")
        if c < 0:
            raise ChemicalEquilibriumError("Concentrations must be >= 0.")
        kc *= c ** power
    return kc


def reaction_quotient_qc(
    concentrations: Dict[str, float],
    stoichiometric_powers: Dict[str, int],
) -> float:
    """
    Reaction quotient Qc has the same form as Kc.
    """
    return equilibrium_constant_from_concentrations(concentrations, stoichiometric_powers)


def compare_qc_kc(qc: float, kc: float) -> str:
    """
    Compares Qc with Kc.

    Returns:
    - "forward"  if Qc < Kc
    - "backward" if Qc > Kc
    - "equilibrium" if Qc == Kc
    """
    _ensure_finite_number(qc, "qc")
    _ensure_finite_number(kc, "kc")

    if qc < kc:
        return "forward"
    if qc > kc:
        return "backward"
    return "equilibrium"


def kp_from_kc(kc: float, delta_n_gas: int, temperature_k: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    Kp = Kc (RT)^{Δn}

    Δn = moles(gaseous products) − moles(gaseous reactants)
    """
    _ensure_finite_number(kc, "kc")
    _ensure_finite_number(temperature_k, "temperature_k")
    _ensure_finite_number(r, "r")

    if kc < 0:
        raise ChemicalEquilibriumError("Kc must be >= 0.")
    if temperature_k <= 0:
        raise ChemicalEquilibriumError("temperature_k must be > 0.")
    if r <= 0:
        raise ChemicalEquilibriumError("r must be > 0.")

    return kc * (r * temperature_k) ** delta_n_gas


def kc_from_kp(kp: float, delta_n_gas: int, temperature_k: float, r: float = R_IDEAL_DEFAULT) -> float:
    """
    Kc = Kp (RT)^{-Δn}
    """
    _ensure_finite_number(kp, "kp")
    _ensure_finite_number(temperature_k, "temperature_k")
    _ensure_finite_number(r, "r")

    if kp < 0:
        raise ChemicalEquilibriumError("Kp must be >= 0.")
    if temperature_k <= 0:
        raise ChemicalEquilibriumError("temperature_k must be > 0.")
    if r <= 0:
        raise ChemicalEquilibriumError("r must be > 0.")

    return kp * (r * temperature_k) ** (-delta_n_gas)


def degree_of_dissociation_alpha(k: float) -> float:
    """
    Simple weak electrolyte approximation (exam-safe toy model):
        α ≈ sqrt(K)   (for very dilute solutions)

    This is NOT a solver — only a deterministic approximation helper.
    """
    _ensure_finite_number(k, "k")
    if k < 0:
        raise ChemicalEquilibriumError("Equilibrium constant must be >= 0.")
    return k ** 0.5


def le_chatelier_prediction(
    change: str,
    effect: str,
) -> str:
    """
    Qualitative Le Chatelier prediction (logic-only).

    change: "increase" or "decrease"
    effect: "concentration", "pressure", or "temperature"

    Returns:
    - "shift_forward"
    - "shift_backward"
    - "no_change"
    """
    c = (change or "").strip().lower()
    e = (effect or "").strip().lower()

    if c not in ("increase", "decrease"):
        raise ChemicalEquilibriumError("change must be 'increase' or 'decrease'.")
    if e not in ("concentration", "pressure", "temperature"):
        raise ChemicalEquilibriumError("effect must be concentration/pressure/temperature.")

    if e == "concentration":
        return "shift_backward" if c == "increase" else "shift_forward"

    if e == "pressure":
        return "shift_forward" if c == "increase" else "shift_backward"

    # temperature (assuming forward reaction is exothermic)
    return "shift_backward" if c == "increase" else "shift_forward"
