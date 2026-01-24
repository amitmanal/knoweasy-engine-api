from typing import List, Optional, Literal, Union
import re

from pydantic import BaseModel, Field, field_validator, AliasChoices

ExamMode = Literal["BOARD", "JEE", "NEET", "CET", "OTHER"]


_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def _clean_text(s: str) -> str:
    # Remove control chars, trim, collapse whitespace.
    s = _CONTROL_RE.sub("", s)
    s = s.strip()
    s = _WHITESPACE_RE.sub(" ", s)
    return s


def _normalize_class(v) -> int:
    """
    Accept int or strings like:
    - "11"
    - "11+12"
    - "Integrated (11+12)"
    Return safe int 5..12. For 11+12 we map to 11.
    """
    if v is None:
        raise ValueError("class is required")

    if isinstance(v, int):
        n = v
    else:
        s = str(v).strip()
        m = re.search(r"(\d{1,2})", s)
        if not m:
            raise ValueError("invalid class")
        n = int(m.group(1))

    # Clamp
    if n < 5:
        n = 5
    if n > 12:
        n = 12
    return n


class SolveRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)

    # Optional idempotency key (trust-safe retries). If provided, backend will
    # ensure the same request_id returns the same response without double-charging.
    request_id: Optional[str] = Field(
        None,
        max_length=80,
        description="Client-generated idempotency key for retries (UUID recommended).",
    )

    # ✅ Accept BOTH keys:
    # - "class"      (official API)
    # - "class_level" (current frontend payload)
    class_: Union[int, str] = Field(
        ...,
        alias="class",
        validation_alias=AliasChoices("class", "class_level"),
    )

    board: str = Field(..., min_length=2, max_length=40)
    subject: str = Field(..., min_length=2, max_length=40)
    chapter: Optional[str] = Field(None, max_length=120)
    exam_mode: ExamMode = "BOARD"
    language: str = Field("en", description="en / hi / mr etc.")
    answer_mode: str = Field(
        "step_by_step",
        description="one_liner / cbse_board / step_by_step / hint_only",
    )

    # Ignore extra fields for forward-compat (stability)
    model_config = {"extra": "ignore"}

    @field_validator("request_id", mode="before")
    @classmethod
    def validate_request_id(cls, v):
        if v is None:
            return None
        v = _clean_text(str(v))
        if not v:
            return None
        # Keep this strict but not fragile (no regex hard requirement).
        if len(v) > 80:
            return v[:80]
        return v

    @field_validator("class_")
    @classmethod
    def validate_class(cls, v):
        return _normalize_class(v)

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str):
        v = _clean_text(v)
        if len(v) < 3:
            raise ValueError("question too short")
        return v

    @field_validator("board", "subject", "chapter", mode="before")
    @classmethod
    def validate_text_fields(cls, v):
        if v is None:
            return v
        v = _clean_text(str(v))
        return v


class SolveResponse(BaseModel):
    final_answer: str
    steps: List[str] = []
    assumptions: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = []
    safe_note: Optional[str] = None
    meta: dict = {}
