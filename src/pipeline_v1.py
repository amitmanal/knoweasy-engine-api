from __future__ import annotations

from dataclasses import dataclass, asdict, is_dataclass
from typing import Any, Dict, Optional


@dataclass
class PipelineResult:
    input_question: str
    normalized: Optional[Dict[str, Any]] = None
    governor: Optional[Dict[str, Any]] = None
    rendered: Optional[Dict[str, Any]] = None
    structure_validation: Optional[Dict[str, Any]] = None
    final: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return obj


# ==============================
# REACTION HARD ROUTING (LOCKED)
# ==============================
#
# Note on REACTION_KEYWORDS:
# These tokens are matched against the normalized question text to
# identify when the input clearly references a named reagent or test.
# When detected, the pipeline short‑circuits to the reaction pathway
# rather than falling back to concept/isomerism handlers.  To cover
# common phrasing used in organic qualitative tests, we include both
# base reagent names and typical descriptor phrases (e.g., "tollens reagent",
# "silver mirror").  All entries should be lower‑case for case‑insensitive
# matching and can include spaces or parentheses as required.  See
# _force_reaction_route for how these are applied.
REACTION_KEYWORDS = {
    # common bases/acids and simple reagents
    "koh", "naoh", "h2so4", "hno3", "kmno4", "o3",
    "nacn", "kcn", "agno3", "nh3",
    "lialh4", "nabh4", "pcc",
    # named oxidation/reduction and other organic test reagents
    "tollens", "fehling", "iodoform",
    "rosenmund", "stephen", "clemmensen",
    "wolff", "cleavage", "oxidation", "reduction",
    # additional synonyms and descriptive phrases for qualitative tests
    "tollens reagent", "fehling solution", "silver mirror", "silver mirror test",
    "ag(nh3)", "cu2o"
}


def _force_reaction_route(normalized: Dict[str, Any]) -> None:
    """
    HARD SAFETY GATE (DO NOT REMOVE):

    If the question contains any reagent name or
    named chemical test, FORCE REACTION routing.

    This prevents fallback to isomerism / theory modules
    for Tollens, Fehling, Iodoform, etc.
    """
    # Attempt to obtain the question text from a variety of
    # normalized fields.  The normalizer currently exposes
    # ``cleaned_text`` as its canonical string, but earlier versions
    # (or other modes) may use ``cleaned_question``, ``question`` or
    # ``raw_question``.  We walk these keys in priority order and
    # default to an empty string if none are present.
    text_fields = [
        normalized.get("cleaned_text"),
        normalized.get("cleaned_question"),
        normalized.get("question"),
        normalized.get("raw_question"),
    ]
    # Pick the first non‑empty value and normalize to lower case
    text = next((t for t in text_fields if isinstance(t, str) and t), "").lower()

    # If any keyword appears in the question, force reaction routing
    if any(k in text for k in REACTION_KEYWORDS):
        normalized["__force_reaction__"] = True
        normalized["question_type"] = "REACTION"
        # Provide a hint that this was triggered by a reagent/test keyword
        normalized["topic_hint"] = "REACTION_TEST"


def run_pipeline_v1(question: str) -> Dict[str, Any]:
    result = PipelineResult(input_question=question)

    try:
        # ---------- 1) Normalizer ----------
        from src import normalizer as _normalizer

        if hasattr(_normalizer, "normalize"):
            normalized_obj = _normalizer.normalize(question, mode="exam")
        elif hasattr(_normalizer, "normalize_question"):
            normalized_obj = _normalizer.normalize_question(question, mode="exam")
        else:
            raise AttributeError("Normalizer entry function not found")

        normalized = _to_dict(normalized_obj)

        # 🔒 APPLY HARD REACTION GATE
        _force_reaction_route(normalized)

        result.normalized = normalized

        # ---------- 2) Governor ----------
        from src import governor as _governor

        if hasattr(_governor, "decide"):
            gov_obj = _governor.decide(normalized_obj)
        elif hasattr(_governor, "govern"):
            gov_obj = _governor.govern(normalized_obj)
        else:
            raise AttributeError("Governor entry function not found")

        gov = _to_dict(gov_obj)
        result.governor = gov

        decision = (gov.get("decision") or gov.get("DECISION") or "FULL").upper()
        assumptions_list = gov.get("assumptions") or []

        # ---------- 3) Answer Generator ----------
        from src.answer_generator_v1 import generate_answer_v1

        draft = generate_answer_v1(normalized, gov)

        understanding = getattr(draft, "understanding", "")
        concept = getattr(draft, "concept", "")
        steps = getattr(draft, "steps", "")
        final_answer = getattr(draft, "final_answer", "")
        exam_tip = getattr(draft, "exam_tip", "")

        # ---------- 4) Renderer ----------
        from src import renderer as _renderer

        rendered_obj = _renderer.render_response(
            decision=decision,
            understanding=understanding,
            concept=concept,
            steps=steps,
            final_answer=final_answer,
            exam_tip=exam_tip,
            assumptions=assumptions_list,
        )

        rendered = _to_dict(rendered_obj)
        result.rendered = rendered

        # ---------- 5) Structure Validator ----------
        from src import structure_validator as _validator

        if hasattr(_validator, "validate_structure"):
            ok, msg = _validator.validate_structure(rendered)
        elif hasattr(_validator, "validate"):
            ok, msg = _validator.validate(rendered)
        else:
            raise AttributeError("Structure Validator entry function not found")

        result.structure_validation = {"is_valid": bool(ok), "message": str(msg)}

        # ---------- 6) Final ----------
        result.final = rendered
        return asdict(result)

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        return asdict(result)
