"""
Inorganic Chemistry v1 — Atomic Structure (Deterministic)

Scope:
- Bohr model (H-like species):
    * Energy levels
    * Radius of nth orbit
    * Velocity of electron
- de Broglie wavelength
- Heisenberg uncertainty (minimum Δx·Δp)
- Photoelectric effect (Einstein equation)
- Rydberg formula (wavenumber)

All formulas are closed-form, exam-safe.
"""

from __future__ import annotations

import math


class AtomicStructureError(ValueError):
    """Invalid inputs for atomic structure helpers."""


# Physical constants (exam-standard)
PLANCK_H = 6.626e-34          # J·s
PLANCK_HBAR = PLANCK_H / (2 * math.pi)
C_LIGHT = 3.0e8              # m/s
ELECTRON_MASS = 9.109e-31    # kg
ELECTRON_CHARGE = 1.602e-19  # C
EPSILON_0 = 8.854e-12        # C^2/(N·m^2)
RYDBERG = 1.097e7            # m^-1


def _pos(x: float, name: str):
    if x <= 0:
        raise AtomicStructureError(f"{name} must be > 0")


# -------------------------
# Bohr model (H-like)
# -------------------------

def bohr_energy_n(n: int, z: int = 1) -> float:
    """
    Energy of electron in nth orbit (J):
      En = -13.6 eV * (Z^2 / n^2)
    """
    if n <= 0 or z <= 0:
        raise AtomicStructureError("n and z must be >= 1")
    energy_ev = -13.6 * (z ** 2) / (n ** 2)
    return energy_ev * ELECTRON_CHARGE


def bohr_radius_n(n: int, z: int = 1) -> float:
    """
    Radius of nth orbit (m):
      rn = a0 * (n^2 / Z)
    where a0 = 0.529 Å
    """
    if n <= 0 or z <= 0:
        raise AtomicStructureError("n and z must be >= 1")
    a0 = 0.529e-10
    return a0 * (n ** 2) / z


def bohr_velocity_n(n: int, z: int = 1) -> float:
    """
    Velocity of electron in nth orbit (m/s):
      vn = (Z / n) * 2.18e6
    """
    if n <= 0 or z <= 0:
        raise AtomicStructureError("n and z must be >= 1")
    return (z / n) * 2.18e6


# -------------------------
# de Broglie
# -------------------------

def de_broglie_wavelength(momentum: float = None, *, mass: float = None, velocity: float = None) -> float:
    """
    λ = h / p  OR  λ = h / (m v)
    """
    if momentum is not None:
        _pos(momentum, "momentum")
        return PLANCK_H / momentum

    if mass is not None and velocity is not None:
        _pos(mass, "mass")
        _pos(velocity, "velocity")
        return PLANCK_H / (mass * velocity)

    raise AtomicStructureError("Provide momentum OR (mass and velocity)")


# -------------------------
# Heisenberg uncertainty
# -------------------------

def heisenberg_min_delta_p(delta_x: float) -> float:
    """
    Minimum uncertainty in momentum:
      Δp >= h / (4π Δx)
    """
    _pos(delta_x, "delta_x")
    return PLANCK_H / (4 * math.pi * delta_x)


# -------------------------
# Photoelectric effect
# -------------------------

def photoelectric_max_ke(frequency: float, work_function: float) -> float:
    """
    Einstein equation:
      KE_max = hν − φ
    """
    _pos(frequency, "frequency")
    _pos(work_function, "work_function")
    ke = PLANCK_H * frequency - work_function
    return max(0.0, ke)


def threshold_frequency(work_function: float) -> float:
    """
    ν0 = φ / h
    """
    _pos(work_function, "work_function")
    return work_function / PLANCK_H


# -------------------------
# Rydberg formula
# -------------------------

def rydberg_wavenumber(n1: int, n2: int, z: int = 1) -> float:
    """
    Wavenumber:
      1/λ = R Z^2 (1/n1^2 − 1/n2^2),  n2 > n1
    """
    if n1 <= 0 or n2 <= 0 or z <= 0:
        raise AtomicStructureError("n1, n2, z must be >= 1")
    if n2 <= n1:
        raise AtomicStructureError("n2 must be > n1")
    return RYDBERG * (z ** 2) * ((1 / (n1 ** 2)) - (1 / (n2 ** 2)))
