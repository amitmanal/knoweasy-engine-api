# src/pipeline_v1.py
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

        decision = (gov.get("decision") or gov.get("DECISION") or "").upper() or "FULL"
        assumptions_list = gov.get("assumptions") or []

        # ---------- 2.5) Answer Generator (v1) ----------
        from src.answer_generator_v1 import generate_answer_v1

        draft = generate_answer_v1(normalized, gov)

        understanding = draft.understanding
        concept = draft.concept
        steps = draft.steps
        final_answer = draft.final_answer
        exam_tip = draft.exam_tip

        # ---------- 3) Renderer (STRICT: render_response) ----------
        from src import renderer as _renderer

        if not hasattr(_renderer, "render_response"):
            raise AttributeError("renderer.render_response not found")

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

        # ---------- 4) Structure Validator ----------
        from src import structure_validator as _validator

        if hasattr(_validator, "validate_structure"):
            ok, msg = _validator.validate_structure(rendered)
        elif hasattr(_validator, "validate"):
            ok, msg = _validator.validate(rendered)
        else:
            raise AttributeError("Structure Validator entry function not found")

        result.structure_validation = {"is_valid": bool(ok), "message": str(msg)}

        # ---------- 5) Final JSON ----------
        result.final = rendered
        return asdict(result)

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        return asdict(result)
