# src/ui_contracts_v1.py
"""
KnowEasy OS — UI Contracts v1 (LOCKED)

Purpose:
- Define stable JSON contracts for frontend wiring
- Validate required keys and minimal types
- No business logic, no chemistry logic

Contracts:
1) Today Screen payload (DSDE output + mastery feedback)
2) Study Result payload (engine packet + explanation)
3) Progress payload (mastery map summary)
4) Parent payload (read-only overview)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


def _req(d: Dict[str, Any], key: str) -> Any:
    if key not in d:
        raise ValueError(f"Missing required key: {key}")
    return d[key]


def _is_str_list(x: Any) -> bool:
    return isinstance(x, list) and all(isinstance(i, str) for i in x)


# -------------------------
# 1) Today Screen Contract
# -------------------------

def validate_today_payload_v1(payload: Dict[str, Any]) -> None:
    _req(payload, "version")
    _req(payload, "exam_mode")
    _req(payload, "total_minutes")
    blocks = _req(payload, "blocks")
    if not isinstance(blocks, list) or len(blocks) < 1:
        raise ValueError("blocks must be a non-empty list")

    for b in blocks:
        if not isinstance(b, dict):
            raise ValueError("each block must be a dict")
        _req(b, "subject")
        _req(b, "mode")
        _req(b, "minutes")
        ft = b.get("focus_tags", [])
        if ft is not None and not _is_str_list(ft):
            raise ValueError("focus_tags must be list[str]")
        if not isinstance(b.get("minutes"), int):
            raise ValueError("minutes must be int")

    # Optional keys
    if "reason" in payload and not isinstance(payload["reason"], str):
        raise ValueError("reason must be str")


# -------------------------
# 2) Study Result Contract
# -------------------------

def validate_study_result_payload_v1(packet: Dict[str, Any]) -> None:
    # Minimal engine packet fields
    _req(packet, "answer")
    _req(packet, "reason")
    _req(packet, "exam_mode")
    _req(packet, "confidence")
    _req(packet, "version")

    # Explanation is required for UI
    exp = _req(packet, "explanation_v1")
    if not isinstance(exp, dict):
        raise ValueError("explanation_v1 must be dict")
    _req(exp, "title")
    steps = _req(exp, "steps")
    _req(exp, "final")
    if not isinstance(steps, list):
        raise ValueError("explanation_v1.steps must be list")

    # Explainability optional but recommended
    if "explainability" in packet:
        ex = packet["explainability"]
        if not isinstance(ex, dict):
            raise ValueError("explainability must be dict")
        if "tags" in ex and not _is_str_list(ex["tags"]):
            raise ValueError("explainability.tags must be list[str]")


# -------------------------
# 3) Progress Screen Contract
# -------------------------

def build_progress_payload_v1(
    *,
    mastery_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Produces a UI-friendly progress payload:
    - totals
    - buckets
    - top weak tags
    """
    if not isinstance(mastery_map, dict):
        raise ValueError("mastery_map must be dict")

    total = 0
    mastered = 0
    learning = 0
    not_started = 0

    weak: List[Tuple[int, str]] = []

    for tag, rec in mastery_map.items():
        if not isinstance(tag, str) or not isinstance(rec, dict):
            continue
        try:
            score = int(rec.get("score", 0))
        except Exception:
            score = 0
        state = str(rec.get("state", "NOT_STARTED")).strip().upper()
        total += 1
        if state == "MASTERED":
            mastered += 1
        elif state == "LEARNING":
            learning += 1
        else:
            not_started += 1
        weak.append((score, tag))

    weak.sort(key=lambda x: (x[0], x[1]))
    weak_tags = [t for _, t in weak[:10]]

    return {
        "version": "progress_payload_v1",
        "total_tags": total,
        "counts": {
            "MASTERED": mastered,
            "LEARNING": learning,
            "NOT_STARTED": not_started,
        },
        "weak_tags": weak_tags,
    }


def validate_progress_payload_v1(payload: Dict[str, Any]) -> None:
    _req(payload, "version")
    _req(payload, "total_tags")
    counts = _req(payload, "counts")
    if not isinstance(counts, dict):
        raise ValueError("counts must be dict")
    for k in ("MASTERED", "LEARNING", "NOT_STARTED"):
        if k not in counts:
            raise ValueError(f"counts missing {k}")
        if not isinstance(counts[k], int):
            raise ValueError("counts values must be int")
    wt = _req(payload, "weak_tags")
    if not _is_str_list(wt):
        raise ValueError("weak_tags must be list[str]")


# -------------------------
# 4) Parent Dashboard Contract
# -------------------------

def build_parent_payload_v1(
    *,
    student_profile: Dict[str, Any],
    progress_payload: Dict[str, Any],
    today_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Read-only snapshot for parents:
    - profile summary
    - today plan summary
    - progress stats
    """
    if not isinstance(student_profile, dict):
        raise ValueError("student_profile must be dict")
    if not isinstance(progress_payload, dict):
        raise ValueError("progress_payload must be dict")
    if not isinstance(today_payload, dict):
        raise ValueError("today_payload must be dict")

    # minimal safe fields
    uid = str(student_profile.get("user_id", "")).strip()
    cl = student_profile.get("class_level")
    board = str(student_profile.get("board", "")).strip()
    group = str(student_profile.get("group", "")).strip()

    blocks = today_payload.get("blocks", []) or []
    minutes = 0
    for b in blocks:
        if isinstance(b, dict):
            try:
                minutes += int(b.get("minutes", 0))
            except Exception:
                pass

    return {
        "version": "parent_payload_v1",
        "student": {
            "user_id": uid,
            "class_level": cl,
            "board": board,
            "group": group,
        },
        "today": {
            "total_minutes": minutes,
            "block_count": len(blocks),
            "exam_mode": today_payload.get("exam_mode"),
        },
        "progress": progress_payload,
    }


def validate_parent_payload_v1(payload: Dict[str, Any]) -> None:
    _req(payload, "version")
    student = _req(payload, "student")
    today = _req(payload, "today")
    progress = _req(payload, "progress")
    if not isinstance(student, dict) or not isinstance(today, dict) or not isinstance(progress, dict):
        raise ValueError("student/today/progress must be dict")
