from dataclasses import dataclass
from typing import List, Literal
from src.normalizer import NormalizedInput

Decision = Literal["FULL", "PARTIAL", "REFUSE"]

@dataclass
class GovernanceResult:
    decision: Decision
    assumptions: List[str]
    refusal_reason: str
    notes: str

def decide(normalized: NormalizedInput) -> GovernanceResult:
    """
    Week-1/Week-3 behavior rules:
    - No silent assumptions
    - If ambiguity affects outcome: PARTIAL or REFUSE
    - Prefer REFUSE when result cannot be uniquely determined
    """
    flags = set(normalized.ambiguity_flags)
    assumptions: List[str] = []

    # Hard refusal patterns (underdetermined)
    # (We keep this minimal and conservative for v1)
    if "POSSIBLE_SOLVENT_MISSING" in flags and ("cn" in normalized.cleaned_text.lower() or "nacn" in normalized.cleaned_text.lower()):
        return GovernanceResult(
            decision="PARTIAL",
            assumptions=[],
            refusal_reason="",
            notes="CN-/NaCN question with missing solvent/conditions; concept is safe but final product may be exam-convention dependent."
        )

    # KOH medium missing: allow assumption only if exam-standard (but must be explicit)
    if "KOH_MEDIUM_NOT_SPECIFIED" in flags:
        assumptions.append("Assuming alcoholic KOH (ethanolic medium) when 'KOH' is given without medium, which typically favors elimination in exam settings.")

    # Dehydration temp missing: must be explicit
    if "DEHYDRATION_TEMP_NOT_SPECIFIED" in flags:
        assumptions.append("Assuming standard dehydration conditions (high temperature) for concentrated H2SO4 unless otherwise specified.")

    # Major product missing conditions: must be explicit
    if "MAJOR_PRODUCT_MISSING_CONDITIONS" in flags and not assumptions:
        assumptions.append("Assuming standard exam conditions where not specified, since 'major product' depends on reaction medium/conditions.")

    # Decision policy:
    # If we have assumptions, we can still answer FULL later, but the solver must honor assumptions.
    # If we flagged POSSIBLE_SOLVENT_MISSING for CN-/NaCN we already returned PARTIAL.
    # Otherwise, allow FULL with explicit assumptions.
    if assumptions:
        return GovernanceResult(
            decision="FULL",
            assumptions=assumptions,
            refusal_reason="",
            notes="Ambiguity present; allowed via explicit assumptions."
        )

    return GovernanceResult(
        decision="FULL",
        assumptions=[],
        refusal_reason="",
        notes="No ambiguity requiring gating."
    )
