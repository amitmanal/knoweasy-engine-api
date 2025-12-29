# src/engine_entrypoint_adapter_v1.py

from __future__ import annotations

from typing import Any, Dict, Optional

from src.answer_generator_v1 import generate_answer_v1


def _extract_text(prompt: Any) -> str:
    """
    Accepts:
      - str
      - dict like {"cleaned_text": "..."} or {"question": "..."} etc.
    Returns a best-effort string for emptiness checking.
    """
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, dict):
        # common shapes used across your tests
        for k in ("cleaned_text", "question", "text", "prompt"):
            v = prompt.get(k)
            if isinstance(v, str):
                return v
        # fallback: string repr
        return str(prompt)
    return str(prompt)


def solve(
    prompt: Any,
    context: Optional[Dict[str, Any]] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    FastAPI wrapper expects this exact callable name: solve

    NOTE: Some unit tests require that empty prompt raises ValueError.
    """
    text = _extract_text(prompt).strip()
    if not text:
        raise ValueError("Empty question")

    context = context or {}
    options = options or {}

    # generate_answer_v1 returns a dataclass; convert to a dictionary for API
    result = generate_answer_v1(prompt, context, **options)
    # If result is a dataclass-like object, convert it to a plain dict.
    from dataclasses import asdict, is_dataclass
    if is_dataclass(result):
        data = asdict(result)
        # Extract tag fields into top-level keys for convenience
        tags = data.pop("tags", {}) or {}
        data.update({
            "ncert_status": tags.get("ncert"),
            "exam_footprint": tags.get("exam_footprint"),
            "exam_safety": tags.get("safety"),
        })
        # Provide the expected 'answer' key mapping to the final answer
        data["answer"] = data.get("final_answer")
        return data
    # If it's already a dict, ensure 'answer' key exists when 'final_answer' is present
    if isinstance(result, dict):
        if "answer" not in result and "final_answer" in result:
            result = dict(result)
            result["answer"] = result.get("final_answer")
        return result
    # Fallback: return the raw result
    return result


class EngineEntrypointAdapterV1:
    """
    Backward compatibility class.
    """

    def solve(
        self,
        prompt: Any,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return solve(prompt, context=context, options=options)
