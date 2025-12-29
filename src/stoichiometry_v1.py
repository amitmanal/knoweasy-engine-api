# src/stoichiometry_v1.py
# Physical Chemistry v1 – Stoichiometry
# LOCKED MODE: additive only

def limiting_reagent_general(stoichiometry, given_moles):
    """
    stoichiometry: dict like {"A": 2, "B": 1, "C": 3}
    given_moles: dict like {"A": 1.0, "B": 2.0, "C": 1.5}
    Returns the limiting reactant key.
    """
    ratios = {}
    for reactant, coeff in stoichiometry.items():
        if coeff <= 0:
            raise ValueError("Stoichiometric coefficients must be positive")
        if reactant not in given_moles:
            raise KeyError(f"Missing moles for reactant: {reactant}")
        ratios[reactant] = given_moles[reactant] / coeff
    return min(ratios, key=ratios.get)


def extent_of_reaction(stoichiometry, given_moles):
    """
    Returns the maximum extent (xi_max) based on limiting reagent.
    """
    ratios = []
    for reactant, coeff in stoichiometry.items():
        ratios.append(given_moles[reactant] / coeff)
    return min(ratios)


def theoretical_yield(product_coeff, extent):
    """
    product_coeff: stoichiometric coefficient of product
    extent: extent of reaction (xi)
    Returns moles of product formed.
    """
    if product_coeff <= 0:
        raise ValueError("Product coefficient must be positive")
    return product_coeff * extent


def percent_yield(actual_yield, theoretical_yield_value):
    """
    Returns percentage yield.
    """
    if theoretical_yield_value <= 0:
        raise ValueError("Theoretical yield must be positive")
    return (actual_yield / theoretical_yield_value) * 100.0
