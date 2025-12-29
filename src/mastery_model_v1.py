# src/mastery_model_v1.py
"""
KnowEasy OS — Mastery Model v1 (LOCKED)

Patch v1.1:
- Exclude policy/system tags from mastery:
  * 'ADVANCED_ALLOWED'
  * tags starting with 'EXAM_' or 'DEPTH_'
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple


ALLOWED_STATES = ("NOT_STARTED", "LEARNING", "MASTERED")
ALLOWED_EXAM_MODES = ("BOARD", "NEET", "JEE")

ERROR_PENALTIES = {
    "CONCEPT_GAP": 12,
    "FORMULA_MISUSE": 10,
    "TREND_CONFUSION": 8,
    "CONDITION_OMISSION": 6,
    "UNIT_MISTAKE": 8,
    "SIGN_MISTAKE": 5,
    "CALCULATION_ERROR": 5,
    "MISREAD_QUESTION": 4,
    "AMBIGUITY_EXAM_DEPENDENT": 2,
    "DATA_RECALL": 4,
}

CLEAN_BONUS = 6

EXAM_SCALE = {
    "BOARD": 1.0,
    "NEET": 1.1,
    "JEE": 1.2,
}

# ---- NEW: policy/system tag filter ----
def _is_concept_tag(tag: str) -> bool:
    t = tag.strip()
    if not t:
        return False
    if t == "ADVANCED_ALLOWED":
        return False
    if t.startswith("EXAM_") or t.startswith("DEPTH_"):
        return False
    return True


def _clamp(v: int, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(v)))


def _state_from_score(score: int) -> str:
    if score >= 80:
        return "MASTERED"
    if score >= 30:
        return "LEARNING"
    return "NOT_STARTED"


def _collect_tags(attempt: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    t1 = attempt.get("topic_tags", []) or []
    t2 = attempt.get("explainability_tags", []) or []
    for t in list(t1) + list(t2):
        s = str(t).strip()
        if _is_concept_tag(s):
            tags.append(s)
    # stable unique
    seen = set()
    out: List[str] = []
    for x in tags:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _error_penalty(error_summary: Dict[str, int]) -> int:
    penalty = 0
    for cat, cnt in (error_summary or {}).items():
        if cat in ERROR_PENALTIES:
            try:
                penalty += ERROR_PENALTIES[cat] * int(cnt)
            except Exception:
                penalty += ERROR_PENALTIES[cat]
    return penalty


def update_mastery_from_attempts_v1(
    *,
    previous_mastery: Dict[str, Dict[str, Any]],
    attempts: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    mastery: Dict[str, Dict[str, Any]] = {}

    for tag, rec in (previous_mastery or {}).items():
        mastery[tag] = {
            "score": int(rec.get("score", 0)),
            "state": rec.get("state", "NOT_STARTED"),
            "attempts": int(rec.get("attempts", 0)),
            "last_updated": rec.get("last_updated"),
        }

    for a in attempts or []:
        exam_mode = str(a.get("exam_mode", "BOARD")).strip().upper()
        if exam_mode not in ALLOWED_EXAM_MODES:
            exam_mode = "BOARD"
        scale = EXAM_SCALE[exam_mode]

        tags = _collect_tags(a)
        if not tags:
            continue

        penalty = _error_penalty(a.get("error_summary", {}) or {})
        is_clean = penalty == 0

        for tag in tags:
            rec = mastery.get(tag)
            if not rec:
                score = 50
                rec = {
                    "score": score,
                    "state": _state_from_score(score),
                    "attempts": 0,
                    "last_updated": a.get("timestamp_utc"),
                }

            rec["attempts"] += 1

            if is_clean:
                delta = int(round(CLEAN_BONUS * scale))
                rec["score"] = _clamp(rec["score"] + delta)
            else:
                delta = int(round(penalty * scale))
                rec["score"] = _clamp(rec["score"] - delta)

            rec["state"] = _state_from_score(rec["score"])
            rec["last_updated"] = a.get("timestamp_utc")
            mastery[tag] = rec

    return mastery
