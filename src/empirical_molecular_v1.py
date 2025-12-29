# src/empirical_molecular_v1.py
# Physical Chemistry v1 – Empirical & Molecular Formula (Advanced)
# LOCKED MODE: additive only

def empirical_formula_advanced(percent_composition, atomic_masses):
    """
    percent_composition: dict like {"C": 54.5, "H": 9.1, "O": 36.4}
    atomic_masses: dict like {"C": 12, "H": 1, "O": 16}

    Returns simplified integer ratio dict.
    """
    # Step 1: convert % to moles
    mole_ratios = {}
    for element, percent in percent_composition.items():
        mole_ratios[element] = percent / atomic_masses[element]

    # Step 2: divide by smallest
    smallest = min(mole_ratios.values())
    normalized = {
        element: moles / smallest
        for element, moles in mole_ratios.items()
    }

    # Step 3: remove fractional ratios by multiplying
    # Typical exam-safe multipliers
    multipliers = [1, 2, 3, 4, 5, 6]
    for factor in multipliers:
        candidate = {
            element: round(value * factor)
            for element, value in normalized.items()
        }
        # Check if close to integer ratios
        if all(abs((value * factor) - round(value * factor)) < 0.1
               for value in normalized.values()):
            return candidate

    # Fallback (should not happen in standard exam questions)
    return {element: round(value) for element, value in normalized.items()}


def molecular_formula(empirical_formula, empirical_molar_mass, actual_molar_mass):
    """
    empirical_formula: dict like {"C": 2, "H": 6}
    empirical_molar_mass: float
    actual_molar_mass: float

    Returns molecular formula dict.
    """
    if empirical_molar_mass <= 0:
        raise ValueError("Empirical molar mass must be positive")

    multiplier = round(actual_molar_mass / empirical_molar_mass)

    if multiplier <= 0:
        raise ValueError("Invalid molecular mass ratio")

    return {
        element: count * multiplier
        for element, count in empirical_formula.items()
    }
