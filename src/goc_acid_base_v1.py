"""
Compatibility wrapper for the general organic chemistry (GOC) acid/base concept solver.

The original answer generator v1 expects to import a module named
``src.goc_acid_base_v1`` with a ``solve_acid_base_v1`` function.  In this
repository, the corresponding implementation lives in
``src.goc_stability_acidbase_v1`` under the name ``solve_goc_v1``.

This thin wrapper simply re-exports ``solve_goc_v1`` under the expected
name so that legacy code continues to function correctly without
modification.
"""

from __future__ import annotations

from src.goc_stability_acidbase_v1 import solve_goc_v1


def solve_acid_base_v1(text: str):
    """
    Delegate to the actual GOC solver implemented in
    ``src.goc_stability_acidbase_v1.solve_goc_v1``.
    The signature matches the expectations of the original answer
    generator: it accepts a single text argument and returns an
    optional GOCResult.
    """
    return solve_goc_v1(text)