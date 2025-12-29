# src/purity_composition_v1.py
# Physical Chemistry v1 – Purity & Percentage Composition
# LOCKED MODE: additive only

def pure_mass_from_impure_sample(sample_mass, purity_percent):
    """
    Returns mass of pure substance present in an impure sample.

    sample_mass: total mass of impure sample (g)
    purity_percent: purity in % (0 to 100)
    """
    if sample_mass < 0:
        raise ValueError("Sample mass cannot be negative")
    if purity_percent < 0 or purity_percent > 100:
        raise ValueError("Purity percent must be between 0 and 100")
    return sample_mass * (purity_percent / 100.0)


def impure_sample_needed_for_pure_mass(required_pure_mass, purity_percent):
    """
    Returns required impure sample mass to obtain required pure mass.

    required_pure_mass: desired pure mass (g)
    purity_percent: purity in % (0 < purity <= 100)
    """
    if required_pure_mass < 0:
        raise ValueError("Required pure mass cannot be negative")
    if purity_percent <= 0 or purity_percent > 100:
        raise ValueError("Purity percent must be > 0 and <= 100")
    return required_pure_mass / (purity_percent / 100.0)


def percent_composition_from_masses(element_masses):
    """
    element_masses: dict like {"C": 12.0, "H": 2.0, "O": 16.0}
    Returns % composition dict (values sum to 100.0 within rounding tolerance).
    """
    if not element_masses:
        raise ValueError("Element masses cannot be empty")

    total = 0.0
    for el, m in element_masses.items():
        if m < 0:
            raise ValueError("Element mass cannot be negative")
        total += m

    if total <= 0:
        raise ValueError("Total mass must be positive")

    return {el: (m / total) * 100.0 for el, m in element_masses.items()}


def effective_yield_with_purity(theoretical_yield, purity_percent):
    """
    If reactant/product is impure, effective obtainable yield reduces.

    theoretical_yield: theoretical yield (any unit, consistent)
    purity_percent: purity in % (0 to 100)
    """
    if theoretical_yield < 0:
        raise ValueError("Theoretical yield cannot be negative")
    if purity_percent < 0 or purity_percent > 100:
        raise ValueError("Purity percent must be between 0 and 100")
    return theoretical_yield * (purity_percent / 100.0)
