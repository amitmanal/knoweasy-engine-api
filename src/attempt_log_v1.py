# src/attempt_log_v1.py
"""
KnowEasy OS — Attempt Log Schema v1 (LOCKED)

Purpose:
- Deterministic attempt logging contract
- Stores:
  - question metadata (subject/topic tags)
  - user answer (optional)
  - engine packet (optional)
  - derived analytics hooks (error_summary, tags)
- NO chemistry logic

Notes:
- Uses stable SHA1 key generation for dedupe (deterministic).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import hashlib
import json
from datetime import datetime


ALLOWED_SUBJECTS = ("CHEMISTRY", "PHYSICS", "MATHS", "BIOLOGY")


def _iso_now() -> str:
    # Deterministic format; real-time acceptable for runtime logs.
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def stable_attempt_id_v1(payload: Dict[str, Any]) -> str:
    """
    Deterministic ID: SHA1 of canonical JSON (sorted keys).
    """
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _validate_subject(subject: str) -> str:
    s = (subject or "").strip().upper()
    if s not in ALLOWED_SUBJECTS:
        raise ValueError(f"Invalid subject: {subject!r}")
    return s


@dataclass(frozen=True)
class AttemptLogV1:
    attempt_id: str
    user_id: str
    timestamp_utc: str

    subject: str
    topic_tags: List[str] = field(default_factory=list)

    exam_mode: str = "BOARD"
    question_text: str = ""
    student_answer: Optional[str] = None

    # full engine response packet (optional but recommended)
    engine_packet: Optional[Dict[str, Any]] = None

    # quick analytics extracts (optional)
    error_summary: Dict[str, int] = field(default_factory=dict)
    explainability_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "user_id": self.user_id,
            "timestamp_utc": self.timestamp_utc,
            "subject": self.subject,
            "topic_tags": list(self.topic_tags),
            "exam_mode": self.exam_mode,
            "question_text": self.question_text,
            "student_answer": self.student_answer,
            "engine_packet": self.engine_packet,
            "error_summary": dict(self.error_summary),
            "explainability_tags": list(self.explainability_tags),
            "version": "attempt_log_v1",
        }


def build_attempt_log_v1(
    *,
    user_id: str,
    subject: str,
    exam_mode: str,
    question_text: str,
    topic_tags: Optional[List[str]] = None,
    student_answer: Optional[str] = None,
    engine_packet: Optional[Dict[str, Any]] = None,
    timestamp_utc: Optional[str] = None,
) -> AttemptLogV1:
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id must be non-empty")

    subj = _validate_subject(subject)
    em = (exam_mode or "").strip().upper()
    if em not in ("BOARD", "JEE", "NEET"):
        raise ValueError(f"Invalid exam_mode: {exam_mode!r}")

    q = (question_text or "").strip()
    if not q:
        raise ValueError("question_text must be non-empty")

    ts = (timestamp_utc or "").strip() or _iso_now()

    tags = [str(t).strip() for t in (topic_tags or []) if str(t).strip()]
    # dedupe preserve order
    seen = set()
    uniq = []
    for t in tags:
        if t not in seen:
            uniq.append(t)
            seen.add(t)

    # Extract quick analytics if packet supplied
    error_summary: Dict[str, int] = {}
    explainability_tags: List[str] = []
    if isinstance(engine_packet, dict):
        es = engine_packet.get("error_summary")
        if isinstance(es, dict):
            for k, v in es.items():
                try:
                    error_summary[str(k)] = int(v)
                except Exception:
                    continue
        exp = engine_packet.get("explainability", {})
        if isinstance(exp, dict):
            tgs = exp.get("tags", [])
            if isinstance(tgs, list):
                explainability_tags = [str(x) for x in tgs if str(x).strip()]

    # attempt payload used for id
    id_payload = {
        "user_id": uid,
        "timestamp_utc": ts,
        "subject": subj,
        "exam_mode": em,
        "question_text": q,
        "student_answer": student_answer,
        "topic_tags": uniq,
    }
    attempt_id = stable_attempt_id_v1(id_payload)

    return AttemptLogV1(
        attempt_id=attempt_id,
        user_id=uid,
        timestamp_utc=ts,
        subject=subj,
        topic_tags=uniq,
        exam_mode=em,
        question_text=q,
        student_answer=student_answer,
        engine_packet=engine_packet,
        error_summary=error_summary,
        explainability_tags=explainability_tags,
    )


def attempt_log_from_dict(d: Dict[str, Any]) -> AttemptLogV1:
    if not isinstance(d, dict):
        raise ValueError("attempt log payload must be a dict")

    attempt_id = str(d.get("attempt_id", "")).strip()
    if not attempt_id:
        tmp = build_attempt_log_v1(
            user_id=str(d.get("user_id", "")),
            subject=str(d.get("subject", "")),
            exam_mode=str(d.get("exam_mode", "")),
            question_text=str(d.get("question_text", "")),
            topic_tags=list(d.get("topic_tags") or []),
            student_answer=d.get("student_answer"),
            engine_packet=d.get("engine_packet"),
            timestamp_utc=str(d.get("timestamp_utc", "")),
        )
        return tmp

    return AttemptLogV1(
        attempt_id=attempt_id,
        user_id=str(d.get("user_id", "")).strip(),
        timestamp_utc=str(d.get("timestamp_utc", "")).strip(),
        subject=_validate_subject(str(d.get("subject", ""))),
        topic_tags=[str(x) for x in (d.get("topic_tags") or [])],
        exam_mode=str(d.get("exam_mode", "BOARD")).strip().upper(),
        question_text=str(d.get("question_text", "")).strip(),
        student_answer=d.get("student_answer"),
        engine_packet=d.get("engine_packet"),
        error_summary=dict(d.get("error_summary") or {}),
        explainability_tags=[str(x) for x in (d.get("explainability_tags") or [])],
    )
