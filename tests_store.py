"""tests_store.py - Phase-2 Test Engine persistence (isolated).

NON-NEGOTIABLES
--------------
* Additive only (new tables only)
* No coupling to AI / credits / payments
* Server-side scoring (anti-tamper)
* Parent access is read-only and only for linked students
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    and_,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine


logger = logging.getLogger(__name__)


# -------------------------
# Engine / metadata
# -------------------------

_ENGINE: Optional[Engine] = None
metadata = MetaData()


def _clean_sslmode(value: str | None) -> str | None:
    if not value:
        return None
    v = str(value).strip().strip('"').strip("'").strip()
    allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    return v if v in allowed else None


def _get_engine() -> Optional[Engine]:
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        return None

    connect_args: Dict[str, Any] = {}
    if "sslmode=" not in db_url.lower():
        sslmode = _clean_sslmode(os.getenv("DB_SSLMODE"))
        if sslmode:
            connect_args["sslmode"] = sslmode

    try:
        _ENGINE = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
        return _ENGINE
    except Exception as e:
        logger.exception("tests_store: Failed to create DB engine: %s", e)
        _ENGINE = None
        return None


# -------------------------
# Tables
# -------------------------

tests = Table(
    "tests",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("title", String(200), nullable=False),
    Column("description", Text, nullable=True),
    Column("cls", Integer, nullable=True),
    Column("board", String(100), nullable=True),
    Column("subject_slug", String(120), nullable=True),
    Column("chapter_slug", String(160), nullable=True),
    Column("time_limit_sec", Integer, nullable=True),
    Column("total_marks", Integer, nullable=False, default=0),
    Column("is_published", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
)

test_questions = Table(
    "test_questions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("test_id", Integer, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("qno", Integer, nullable=False),
    Column("question_text", Text, nullable=False),
    Column("option_a", Text, nullable=False),
    Column("option_b", Text, nullable=False),
    Column("option_c", Text, nullable=False),
    Column("option_d", Text, nullable=False),
    Column("correct_option", String(1), nullable=False),
    Column("marks", Integer, nullable=False, default=1),
    Column("negative_marks", Integer, nullable=False, default=0),
    Column("explanation", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

test_attempts = Table(
    "test_attempts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("test_id", Integer, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("status", String(16), nullable=False, default="STARTED"),
    Column("started_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("submitted_at", DateTime(timezone=True), nullable=True),
    Column("time_taken_sec", Integer, nullable=True),
    Column("score", Integer, nullable=True),
    Column("max_score", Integer, nullable=True),
    Column("correct_count", Integer, nullable=True),
    Column("wrong_count", Integer, nullable=True),
    Column("skipped_count", Integer, nullable=True),
)

test_attempt_answers = Table(
    "test_attempt_answers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("attempt_id", Integer, ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("question_id", Integer, ForeignKey("test_questions.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("selected_option", String(1), nullable=True),
    Column("is_correct", Boolean, nullable=False, default=False),
    Column("marks_awarded", Integer, nullable=False, default=0),
)


def ensure_tables() -> bool:
    """Ensure Phase-2 tables exist. Returns False if DB is unavailable."""
    eng = _get_engine()
    if eng is None:
        return False
    try:
        metadata.create_all(eng)
        return True
    except Exception as e:
        logger.exception("tests_store.ensure_tables failed: %s", e)
        return False


# -------------------------
# Helpers
# -------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_tests_catalog(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return published tests list (lightweight)."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return []

    where = [tests.c.is_published.is_(True)]
    if filters.get("cls") not in (None, ""):
        try:
            where.append(tests.c.cls == int(filters["cls"]))
        except Exception:
            pass
    if filters.get("board"):
        where.append(tests.c.board == str(filters["board"]).strip())
    if filters.get("subject_slug"):
        where.append(tests.c.subject_slug == str(filters["subject_slug"]).strip())
    if filters.get("chapter_slug"):
        where.append(tests.c.chapter_slug == str(filters["chapter_slug"]).strip())

    q = (
        select(
            tests.c.id,
            tests.c.title,
            tests.c.description,
            tests.c.cls,
            tests.c.board,
            tests.c.subject_slug,
            tests.c.chapter_slug,
            tests.c.time_limit_sec,
            tests.c.total_marks,
            tests.c.updated_at,
        )
        .where(and_(*where))
        .order_by(tests.c.updated_at.desc())
        .limit(50)
    )

    with eng.begin() as conn:
        rows = conn.execute(q).mappings().all()
    return [dict(r) for r in rows]


def get_test_public(test_id: int) -> Optional[Dict[str, Any]]:
    """Return test with questions for student attempt (no answers)."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return None

    with eng.begin() as conn:
        t = conn.execute(
            select(
                tests.c.id,
                tests.c.title,
                tests.c.description,
                tests.c.cls,
                tests.c.board,
                tests.c.subject_slug,
                tests.c.chapter_slug,
                tests.c.time_limit_sec,
                tests.c.total_marks,
            ).where(and_(tests.c.id == test_id, tests.c.is_published.is_(True)))
        ).mappings().first()
        if not t:
            return None
        qs = conn.execute(
            select(
                test_questions.c.id,
                test_questions.c.qno,
                test_questions.c.question_text,
                test_questions.c.option_a,
                test_questions.c.option_b,
                test_questions.c.option_c,
                test_questions.c.option_d,
                test_questions.c.marks,
                test_questions.c.negative_marks,
            )
            .where(test_questions.c.test_id == test_id)
            .order_by(test_questions.c.qno.asc())
        ).mappings().all()

    out = dict(t)
    out["questions"] = [dict(r) for r in qs]
    return out


def start_attempt(user_id: int, test_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Create a STARTED attempt if not already active for this user+test."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return False, "DB unavailable", None

    now = _now()
    with eng.begin() as conn:
        # Ensure test exists and is published
        t = conn.execute(select(tests.c.id).where(and_(tests.c.id == test_id, tests.c.is_published.is_(True)))).first()
        if not t:
            return False, "Test not found", None

        existing = conn.execute(
            select(
                test_attempts.c.id,
                test_attempts.c.status,
                test_attempts.c.started_at,
                test_attempts.c.submitted_at,
            ).where(and_(test_attempts.c.user_id == user_id, test_attempts.c.test_id == test_id, test_attempts.c.status == "STARTED"))
            .order_by(test_attempts.c.id.desc())
            .limit(1)
        ).mappings().first()
        if existing:
            return True, "ok", dict(existing)

        res = conn.execute(
            test_attempts.insert().values(
                user_id=user_id,
                test_id=test_id,
                status="STARTED",
                started_at=now,
            )
        )
        attempt_id = int(res.inserted_primary_key[0])
        row = conn.execute(
            select(test_attempts.c.id, test_attempts.c.status, test_attempts.c.started_at, test_attempts.c.submitted_at).where(test_attempts.c.id == attempt_id)
        ).mappings().first()
        return True, "ok", dict(row) if row else {"id": attempt_id, "status": "STARTED"}


def submit_attempt(user_id: int, attempt_id: int, answers: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Submit attempt with selected answers. Computes score server-side.

    answers: { "answers": [ {"question_id": 12, "selected": "A"}, ... ] }
    """
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return False, "DB unavailable", None

    payload_list = answers.get("answers") if isinstance(answers, dict) else None
    if not isinstance(payload_list, list):
        return False, "Invalid payload", None

    norm: Dict[int, Optional[str]] = {}
    for item in payload_list:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        sel = item.get("selected")
        try:
            qid_int = int(qid)
        except Exception:
            continue
        if sel is None:
            norm[qid_int] = None
        else:
            s = str(sel).strip().upper()
            norm[qid_int] = s if s in ("A", "B", "C", "D") else None

    now = _now()
    with eng.begin() as conn:
        att = conn.execute(
            select(
                test_attempts.c.id,
                test_attempts.c.user_id,
                test_attempts.c.test_id,
                test_attempts.c.status,
                test_attempts.c.started_at,
                test_attempts.c.submitted_at,
            ).where(test_attempts.c.id == attempt_id)
        ).mappings().first()
        if not att:
            return False, "Attempt not found", None
        if int(att["user_id"]) != int(user_id):
            return False, "Forbidden", None
        if (att.get("status") or "").upper() == "SUBMITTED":
            # Idempotent: return existing result
            return True, "already_submitted", get_attempt_result(user_id, attempt_id)
        if (att.get("status") or "").upper() != "STARTED":
            return False, "Invalid attempt status", None

        test_id = int(att["test_id"])
        qs = conn.execute(
            select(
                test_questions.c.id,
                test_questions.c.correct_option,
                test_questions.c.marks,
                test_questions.c.negative_marks,
            ).where(test_questions.c.test_id == test_id)
        ).mappings().all()
        if not qs:
            return False, "Test has no questions", None

        # clear any prior answers (defensive)
        conn.execute(test_attempt_answers.delete().where(test_attempt_answers.c.attempt_id == attempt_id))

        score = 0
        max_score = 0
        correct = 0
        wrong = 0
        skipped = 0

        for q in qs:
            qid = int(q["id"])
            correct_opt = (q["correct_option"] or "").strip().upper()
            marks = int(q["marks"] or 0)
            neg = int(q["negative_marks"] or 0)
            max_score += marks

            sel = norm.get(qid, None)
            if sel is None:
                skipped += 1
                awarded = 0
                is_corr = False
            elif sel == correct_opt:
                correct += 1
                awarded = marks
                is_corr = True
                score += awarded
            else:
                wrong += 1
                awarded = -neg if neg > 0 else 0
                is_corr = False
                score += awarded

            conn.execute(
                test_attempt_answers.insert().values(
                    attempt_id=attempt_id,
                    question_id=qid,
                    selected_option=sel,
                    is_correct=is_corr,
                    marks_awarded=awarded,
                )
            )

        started_at = att.get("started_at")
        time_taken_sec = None
        try:
            if started_at:
                if getattr(started_at, "tzinfo", None) is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                time_taken_sec = int((now - started_at).total_seconds())
        except Exception:
            time_taken_sec = None

        conn.execute(
            test_attempts.update()
            .where(test_attempts.c.id == attempt_id)
            .values(
                status="SUBMITTED",
                submitted_at=now,
                time_taken_sec=time_taken_sec,
                score=score,
                max_score=max_score,
                correct_count=correct,
                wrong_count=wrong,
                skipped_count=skipped,
            )
        )

    return True, "ok", get_attempt_result(user_id, attempt_id)


def list_user_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return []
    q = (
        select(
            test_attempts.c.id.label("attempt_id"),
            test_attempts.c.test_id,
            test_attempts.c.status,
            test_attempts.c.started_at,
            test_attempts.c.submitted_at,
            test_attempts.c.score,
            test_attempts.c.max_score,
            test_attempts.c.correct_count,
            test_attempts.c.wrong_count,
            test_attempts.c.skipped_count,
            test_attempts.c.time_taken_sec,
            tests.c.title,
            tests.c.cls,
            tests.c.board,
            tests.c.subject_slug,
            tests.c.chapter_slug,
        )
        .select_from(test_attempts.join(tests, tests.c.id == test_attempts.c.test_id))
        .where(and_(test_attempts.c.user_id == user_id, test_attempts.c.status == "SUBMITTED"))
        .order_by(test_attempts.c.submitted_at.desc().nullslast(), test_attempts.c.id.desc())
        .limit(int(limit))
    )
    with eng.begin() as conn:
        rows = conn.execute(q).mappings().all()
    return [dict(r) for r in rows]


def get_attempt_result(user_id: int, attempt_id: int) -> Optional[Dict[str, Any]]:
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return None
    with eng.begin() as conn:
        att = conn.execute(
            select(
                test_attempts.c.id,
                test_attempts.c.user_id,
                test_attempts.c.test_id,
                test_attempts.c.status,
                test_attempts.c.started_at,
                test_attempts.c.submitted_at,
                test_attempts.c.time_taken_sec,
                test_attempts.c.score,
                test_attempts.c.max_score,
                test_attempts.c.correct_count,
                test_attempts.c.wrong_count,
                test_attempts.c.skipped_count,
                tests.c.title,
                tests.c.description,
                tests.c.time_limit_sec,
            )
            .select_from(test_attempts.join(tests, tests.c.id == test_attempts.c.test_id))
            .where(test_attempts.c.id == attempt_id)
        ).mappings().first()
        if not att:
            return None
        if int(att["user_id"]) != int(user_id):
            return None

        # full question view (with correct answers + explanation) for review
        qs = conn.execute(
            select(
                test_questions.c.id,
                test_questions.c.qno,
                test_questions.c.question_text,
                test_questions.c.option_a,
                test_questions.c.option_b,
                test_questions.c.option_c,
                test_questions.c.option_d,
                test_questions.c.correct_option,
                test_questions.c.marks,
                test_questions.c.negative_marks,
                test_questions.c.explanation,
            )
            .where(test_questions.c.test_id == int(att["test_id"]))
            .order_by(test_questions.c.qno.asc())
        ).mappings().all()

        ans = conn.execute(
            select(
                test_attempt_answers.c.question_id,
                test_attempt_answers.c.selected_option,
                test_attempt_answers.c.is_correct,
                test_attempt_answers.c.marks_awarded,
            ).where(test_attempt_answers.c.attempt_id == attempt_id)
        ).mappings().all()
        ans_by_qid = {int(a["question_id"]): dict(a) for a in ans}

    out = dict(att)
    out["questions"] = []
    for q in qs:
        qd = dict(q)
        a = ans_by_qid.get(int(qd["id"]))
        if a:
            qd["selected_option"] = a.get("selected_option")
            qd["is_correct"] = a.get("is_correct")
            qd["marks_awarded"] = a.get("marks_awarded")
        else:
            qd["selected_option"] = None
            qd["is_correct"] = False
            qd["marks_awarded"] = 0
        out["questions"].append(qd)
    return out


def parent_summary(student_user_id: int) -> Dict[str, Any]:
    """Light summary for parent dashboards (read-only)."""
    ensure_tables()
    eng = _get_engine()
    if eng is None:
        return {"attempted": 0, "avg_percent": 0, "latest_percent": None}
    with eng.begin() as conn:
        rows = conn.execute(
            select(test_attempts.c.score, test_attempts.c.max_score)
            .where(and_(test_attempts.c.user_id == student_user_id, test_attempts.c.status == "SUBMITTED"))
            .order_by(test_attempts.c.submitted_at.desc().nullslast(), test_attempts.c.id.desc())
            .limit(50)
        ).mappings().all()
    attempted = len(rows)
    if attempted == 0:
        return {"attempted": 0, "avg_percent": 0, "latest_percent": None}
    percents: List[float] = []
    for r in rows:
        mx = int(r.get("max_score") or 0)
        sc = int(r.get("score") or 0)
        if mx > 0:
            percents.append((sc / mx) * 100.0)
    avg_percent = round(sum(percents) / max(1, len(percents)), 1) if percents else 0
    latest_percent = round(percents[0], 1) if percents else None
    return {"attempted": attempted, "avg_percent": avg_percent, "latest_percent": latest_percent}
