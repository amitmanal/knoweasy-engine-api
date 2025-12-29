# src/mole_concept_v1.py
# Physical Chemistry v1 – Mole Concept
# LOCKED MODE: additive only, no shared logic changes

AVOGADRO_NUMBER = 6.022e23


def mass_to_moles(mass, molar_mass):
    if molar_mass <= 0:
        raise ValueError("Molar mass must be positive")
    return mass / molar_mass


def moles_to_mass(moles, molar_mass):
    if molar_mass <= 0:
        raise ValueError("Molar mass must be positive")
    return moles * molar_mass


def moles_to_particles(moles):
    return moles * AVOGADRO_NUMBER


def particles_to_moles(particles):
    return particles / AVOGADRO_NUMBER


def empirical_formula(percent_composition, atomic_masses):
    """
    percent_composition: dict like {"C": 40.0, "H": 6.7, "O": 53.3}
    atomic_masses: dict like {"C": 12, "H": 1, "O": 16}
    """
    mole_ratios = {}
    for element, percent in percent_composition.items():
        mole_ratios[element] = percent / atomic_masses[element]

    smallest = min(mole_ratios.values())
    simplified = {
        element: round(moles / smallest)
        for element, moles in mole_ratios.items()
    }
    return simplified


def limiting_reagent(reaction_stoichiometry, given_moles):
    """
    reaction_stoichiometry: dict like {"A": 2, "B": 1}
    given_moles: dict like {"A": 1.0, "B": 1.0}
    """
    ratios = {}
    for reactant, coeff in reaction_stoichiometry.items():
        ratios[reactant] = given_moles[reactant] / coeff

    return min(ratios, key=ratios.get)
