# src/dsde_v1.py
"""
KnowEasy OS — DSDE v1 (LOCKED)

Patch v1.3:
- Match DSDE v1 unit-test contract exactly
- Keep policy/system tag filtering:
  * 'ADVANCED_ALLOWED'
  * tags starting with 'EXAM_' or 'DEPTH_'
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple


ALLOWED_EXAM_MODES = ("BOARD", "NEET", "JEE")


def _validate_exam_mode(exam_mode: str) -> str:
    em = (exam_mode or "").strip().upper()
    if em not in ALLOWED_EXAM_MODES:
        raise ValueError(f"Invalid exam_mode: {exam_mode!r}")
    return em


def _validate_total_minutes(total_minutes: int) -> int:
    # DSDE v1 contract (from tests): 30..240
    if not isinstance(total_minutes, int):
        raise ValueError("total_minutes must be int")
    if total_minutes < 30 or total_minutes > 240:
        raise ValueError("total_minutes must be between 30 and 240 for v1")
    return total_minutes


def _is_concept_tag(tag: str) -> bool:
    t = str(tag).strip()
    if not t:
        return False
    if t == "ADVANCED_ALLOWED":
        return False
    if t.startswith("EXAM_") or t.startswith("DEPTH_"):
        return False
    return True


def _stable_unique(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in seq:
        s = str(x).strip()
        if not s:
            continue
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out


def _score_attempt(attempt: Dict[str, Any]) -> int:
    # DSDE v1 scoring (matches earlier DSDE tests/behavior)
    weights = {
        "CONCEPT_GAP": 5,
        "FORMULA_MISUSE": 4,
        "TREND_CONFUSION": 3,
        "CONDITION_OMISSION": 3,
        "UNIT_MISTAKE": 4,
        "SIGN_MISTAKE": 2,
        "CALCULATION_ERROR": 2,
        "MISREAD_QUESTION": 2,
        "AMBIGUITY_EXAM_DEPENDENT": 1,
        "DATA_RECALL": 2,
    }
    es = attempt.get("error_summary", {}) or {}
    if not isinstance(es, dict):
        return 0
    score = 0
    for k, v in es.items():
        cat = str(k).strip()
        if cat in weights:
            try:
                score += weights[cat] * int(v)
            except Exception:
                score += weights[cat]
    return score


def _attempt_tags(attempt: Dict[str, Any]) -> List[str]:
    t1 = attempt.get("topic_tags", []) or []
    t2 = attempt.get("explainability_tags", []) or []
    tags: List[str] = []
    if isinstance(t1, list):
        tags += [str(x).strip() for x in t1]
    if isinstance(t2, list):
        tags += [str(x).strip() for x in t2]
    tags = [t for t in tags if _is_concept_tag(t)]
    return _stable_unique(tags)


def _sorted_attempts_recent_first(attempts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(a: Dict[str, Any]) -> Tuple[int, str]:
        ts = str(a.get("timestamp_utc", "")).strip()
        present = 1 if ts else 0
        return (present, ts)
    return sorted(attempts, key=key, reverse=True)


def build_dsde_plan_v1(
    *,
    profile: Dict[str, Any],
    recent_attempts: List[Dict[str, Any]],
    exam_mode: str,
    total_minutes: int = 90,
) -> Dict[str, Any]:
    em = _validate_exam_mode(exam_mode)
    total_minutes = _validate_total_minutes(total_minutes)

    subject = "CHEMISTRY"

    # Minutes split by exam mode (deterministic)
    if em == "BOARD":
        split = (40, 30, 20)  # learn, revise, test for cold start
    elif em == "NEET":
        split = (35, 35, 20)
    else:  # JEE
        split = (30, 40, 20)

    # Normalize split to total_minutes (deterministic scaling)
    base_total = sum(split)
    scale = total_minutes / base_total
    mins = [int(round(x * scale)) for x in split]
    drift = total_minutes - sum(mins)
    mins[0] += drift  # fix rounding drift deterministically

    # -------------------------
    # NO ATTEMPTS → 3 blocks, first is LEARN (per tests)
    # -------------------------
    if not (recent_attempts or []):
        blocks = [
            {
                "subject": subject,
                "mode": "LEARN",
                "minutes": mins[0],
                "focus_tags": ["FOUNDATION"],
                "reason": "No recent error data found; start with structured learning.",
            },
            {
                "subject": subject,
                "mode": "REVISE",
                "minutes": mins[1],
                "focus_tags": ["RECAP"],
                "reason": "Reinforce what was learned.",
            },
            {
                "subject": subject,
                "mode": "TEST",
                "minutes": mins[2],
                "focus_tags": ["MINI_TEST"],
                "reason": "Quick check to detect gaps early.",
            },
        ]
        return {
            "exam_mode": em,
            "total_minutes": total_minutes,
            "blocks": blocks,
            "reason": "Plan built without attempt history: learn → revise → test.",
            "version": "dsde_v1",
        }

    # -------------------------
    # WITH ATTEMPTS → prioritize highest-need, include need_score in reason
    # -------------------------
    chem_attempts = []
    for a in recent_attempts or []:
        if isinstance(a, dict) and str(a.get("subject", "")).strip().upper() == "CHEMISTRY":
            chem_attempts.append(a)
    chem_attempts = _sorted_attempts_recent_first(chem_attempts)

    scored = [(_score_attempt(a), a) for a in chem_attempts]
    scored_sorted = sorted(
        scored,
        key=lambda x: (x[0], str(x[1].get("timestamp_utc", "")), str(x[1].get("question_text", ""))),
        reverse=True,
    )

    top_need_score = 0
    top_need_attempt: Dict[str, Any] | None = None
    for sc, a in scored_sorted:
        if sc > 0:
            top_need_score = sc
            top_need_attempt = a
            break

    focus = _attempt_tags(top_need_attempt) if top_need_attempt else []
    focus = focus[:6]

    # For attempt-based plan, keep the classic structure: REVISE → TEST → LEARN
    if em == "BOARD":
        split2 = (40, 30, 20)  # revise, test, learn
    elif em == "NEET":
        split2 = (35, 35, 20)
    else:
        split2 = (30, 40, 20)

    base_total2 = sum(split2)
    scale2 = total_minutes / base_total2
    m2 = [int(round(x * scale2)) for x in split2]
    drift2 = total_minutes - sum(m2)
    m2[0] += drift2

    blocks = [
        {
            "subject": subject,
            "mode": "REVISE",
            "minutes": m2[0],
            "focus_tags": focus or ["WEAK_AREA"],
            "reason": f"Fix highest-need area based on recent errors (need_score={top_need_score}).",
        },
        {
            "subject": subject,
            "mode": "TEST",
            "minutes": m2[1],
            "focus_tags": (focus or ["PRACTICE"])[:6],
            "reason": "Practice to convert understanding into exam performance.",
        },
        {
            "subject": subject,
            "mode": "LEARN",
            "minutes": m2[2],
            "focus_tags": ["NEXT_CONCEPT"],
            "reason": "Build forward momentum with a new/next concept after revision + practice.",
        },
    ]

    return {
        "exam_mode": em,
        "total_minutes": total_minutes,
        "blocks": blocks,
        "reason": "Plan built from recent attempts: prioritize fixing errors, then testing, then learning.",
        "version": "dsde_v1",
    }
