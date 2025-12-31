from typing import List, Optional, Dict, Any

def format_for_frontend(
    decision: str,
    answer: str,
    steps: List[str],
    exam_tip: str,
    confidence: float,
    flags: List[str],
    *,
    subject: Optional[str] = None,
    source: Optional[str] = None,
    verified_chemistry: Optional[bool] = None,
) -> dict:
    """
    Keep EXACT compatibility with Hostinger UI:
    - Existing keys remain unchanged.
    - Extra keys are additive and safe to ignore by older frontends.
    """
    out: Dict[str, Any] = {
        "answer": answer,
        "confidence": round(float(confidence), 2),
        "flags": flags + [f"DECISION_{decision}"],
        "explanation_v1": {
            "title": "Explanation",
            "steps": steps[:12],
            "final": exam_tip
        },
        "decision": decision
    }

    meta: Dict[str, Any] = {}
    if subject is not None:
        meta["subject"] = subject
    if source is not None:
        meta["source"] = source
    if verified_chemistry is not None:
        meta["verified_chemistry"] = bool(verified_chemistry)

    if meta:
        out["meta"] = meta

    return out
