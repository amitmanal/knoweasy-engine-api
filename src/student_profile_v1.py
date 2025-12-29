# src/student_profile_v1.py
"""
KnowEasy OS — Student Profile Schema v1 (LOCKED)

Purpose:
- Deterministic, validated student profile contract for platform layer
- Used by DSDE, analytics, and UI routing
- NO chemistry logic

Design:
- Dataclass + strict validation
- Stable to_dict()/from_dict()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


ALLOWED_GROUPS: Tuple[str, ...] = ("pcm", "pcb", "pcmb")
ALLOWED_BOARDS: Tuple[str, ...] = ("CBSE", "MH", "ICSE")
ALLOWED_CLASS_LEVELS: Tuple[int, ...] = (11, 12)


def _norm_board(board: str) -> str:
    b = (board or "").strip().upper()
    if b in ("MAHARASHTRA", "MSBSHSE", "MH_BOARD"):
        b = "MH"
    if b not in ALLOWED_BOARDS:
        raise ValueError(f"Invalid board: {board!r}")
    return b


def _norm_group(group: str) -> str:
    g = (group or "").strip().lower()
    if g not in ALLOWED_GROUPS:
        raise ValueError(f"Invalid group: {group!r}")
    return g


def _validate_class_level(class_level: int) -> int:
    if class_level not in ALLOWED_CLASS_LEVELS:
        raise ValueError(f"Invalid class_level (allowed 11/12 only in engine v1): {class_level!r}")
    return class_level


def _validate_exam_targets(exam_targets: List[str]) -> List[str]:
    # Keep it deterministic and flexible; do not hard-block future exams.
    # But normalize common ones for consistency.
    norm_map = {
        "JEE MAIN": "JEE_MAIN",
        "JEE": "JEE_MAIN",
        "JEE ADV": "JEE_ADVANCED",
        "JEE ADVANCED": "JEE_ADVANCED",
        "NEET": "NEET",
        "CET": "CET",
        "CET ENG": "CET_ENGINEERING",
        "CET ENGINEERING": "CET_ENGINEERING",
        "CET MED": "CET_MEDICAL",
        "CET MEDICAL": "CET_MEDICAL",
        "BOARDS": "BOARD",
        "BOARD": "BOARD",
    }
    out: List[str] = []
    for x in (exam_targets or []):
        t = (x or "").strip().upper()
        if not t:
            continue
        out.append(norm_map.get(t, t))
    # Deduplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for t in out:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


@dataclass(frozen=True)
class StudentProfileV1:
    """
    Minimal profile needed to drive:
    - syllabus overlay selection
    - exam mode routing
    - DSDE personalization
    """
    user_id: str
    class_level: int                   # 11 or 12
    board: str                         # CBSE / MH / ICSE (ICSE won't be used for 11-12 in your app, but schema remains generic)
    group: str                         # pcm / pcb / pcmb
    exam_targets: List[str] = field(default_factory=list)

    # optional platform fields
    active_year_mode: str = "single"   # "single" or "integrated_11_12" (platform can use this)
    timezone: str = "Asia/Kolkata"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "class_level": self.class_level,
            "board": self.board,
            "group": self.group,
            "exam_targets": list(self.exam_targets),
            "active_year_mode": self.active_year_mode,
            "timezone": self.timezone,
            "version": "student_profile_v1",
        }


def build_student_profile_v1(
    *,
    user_id: str,
    class_level: int,
    board: str,
    group: str,
    exam_targets: Optional[List[str]] = None,
    active_year_mode: str = "single",
    timezone: str = "Asia/Kolkata",
) -> StudentProfileV1:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id must be non-empty")

    cl = _validate_class_level(int(class_level))
    b = _norm_board(board)
    g = _norm_group(group)
    exams = _validate_exam_targets(exam_targets or [])

    mode = (active_year_mode or "").strip().lower()
    if mode not in ("single", "integrated_11_12"):
        raise ValueError(f"Invalid active_year_mode: {active_year_mode!r}")

    tz = (timezone or "").strip()
    if not tz:
        raise ValueError("timezone must be non-empty")

    return StudentProfileV1(
        user_id=uid,
        class_level=cl,
        board=b,
        group=g,
        exam_targets=exams,
        active_year_mode=mode,
        timezone=tz,
    )


def student_profile_from_dict(d: Dict[str, Any]) -> StudentProfileV1:
    if not isinstance(d, dict):
        raise ValueError("profile payload must be a dict")
    return build_student_profile_v1(
        user_id=str(d.get("user_id", "")).strip(),
        class_level=int(d.get("class_level")),
        board=str(d.get("board", "")),
        group=str(d.get("group", "")),
        exam_targets=list(d.get("exam_targets") or []),
        active_year_mode=str(d.get("active_year_mode", "single")),
        timezone=str(d.get("timezone", "Asia/Kolkata")),
    )
