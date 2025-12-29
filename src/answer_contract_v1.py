# src/answer_contract_v1.py
from __future__ import annotations
from typing import Any, Dict, List, Optional


class AnswerDict(dict):
    """
    Dict that also supports attribute access.
    Example:
      a["final_answer"] and a.final_answer both work.
    """
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    try:
        return str(x)
    except Exception:
        return ""


def _safe_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x]
    # allow already-string steps
    if isinstance(x, str):
        s = x.strip()
        return [s] if s else []
    return [str(x)]


def normalize_answer(out: Any) -> AnswerDict:
    """
    Convert ANY solver output into a stable AnswerDict with:
      - attributes: final_answer, exam_tip, common_mistake, ncert_status, error
      - dict keys: same
      - nested: out["final"]["sections"]["..."]
    """
    # If solver returned None / empty
    if out is None:
        out = {}

    # If it is already AnswerDict
    if isinstance(out, AnswerDict):
        base = out
    elif isinstance(out, dict):
        base = AnswerDict(out)
    else:
        # Unknown type -> wrap as error
        base = AnswerDict({
            "answer": "",
            "final_answer": "",
            "exam_tip": "",
            "common_mistake": "",
            "ncert_status": "",
            "steps": [],
            "error": f"RuntimeError: SOLVER_BAD_OUTPUT_TYPE:{type(out).__name__}",
        })

    # --- canonical fields (flat) ---
    # prefer final_answer, else answer, else final, else empty
    fa = _safe_str(base.get("final_answer") or base.get("final") or base.get("answer") or "")
    ans = _safe_str(base.get("answer") or fa)

    exam_tip = _safe_str(base.get("exam_tip") or "")
    common_mistake = _safe_str(base.get("common_mistake") or "")
    ncert_status = base.get("ncert_status")  # can be bool/str
    err = base.get("error", None)

    steps_raw = base.get("steps", [])
    steps_list = _safe_list(steps_raw)

    # Some tests expect steps to be a STRING in the rendered sections:
    steps_text = "\n".join([s for s in steps_list if s.strip()])

    # enforce flat keys
    base["final_answer"] = fa
    base["answer"] = ans
    base["exam_tip"] = exam_tip
    base["common_mistake"] = common_mistake
    base["ncert_status"] = ncert_status if ncert_status is not None else ""
    base["steps"] = steps_list  # keep list at top-level (many solvers use it)

    # Ensure error is either None or string
    if err is None:
        base["error"] = None
    else:
        base["error"] = _safe_str(err)

    # --- nested "final" contract ---
    # Many tests do: out["final"]["sections"]["exam_tip"]
    final_obj = base.get("final")
    if not isinstance(final_obj, dict):
        final_obj = {}

    sections = final_obj.get("sections")
    if not isinstance(sections, dict):
        sections = {}

    sections.setdefault("final_answer", fa)
    sections.setdefault("answer", ans)
    sections.setdefault("exam_tip", exam_tip)
    sections.setdefault("common_mistake", common_mistake)
    sections.setdefault("ncert_status", base["ncert_status"])
    sections.setdefault("steps", steps_text)  # IMPORTANT: string, not list

    final_obj["sections"] = sections
    base["final"] = final_obj

    return base
