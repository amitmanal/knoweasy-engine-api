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

    Phase-4 stabilization:
    - If missing/None, default to 11 (auto-detect can override later).
    """
    if v is None:
        n = 11
    elif isinstance(v, int):
        n = v
    else:
        s = str(v).strip()
        m = re.search(r"(\d{1,2})", s)
        if not m:
            n = 11
        else:
            n = int(m.group(1))

    # Clamp
    if n < 5:
        n = 5
    if n > 12:
        n = 12
    return n



class LumaContext(BaseModel):
    section: Optional[str] = Field(None, max_length=160, description="Current Luma section title")
    card_type: Optional[str] = Field(None, max_length=40, description="Current Luma card type")
    visible_text: Optional[str] = Field(
        None,
        max_length=1400,
        description="Best-effort visible text from the current card (sanitized, truncated).",
    )

    @field_validator("section", "card_type", "visible_text", mode="before")
    @classmethod
    def _clean_optional(cls, v):
        if v is None:
            return None
        s = _clean_text(str(v))
        return s or None


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
    class_: Optional[Union[int, str]] = Field(
        11,
        alias="class",
        validation_alias=AliasChoices("class", "class_level"),
        description="Student class. Optional (auto-detect). Defaults to 11 if missing.",
    )

    board: str = Field("CBSE", max_length=40)
    subject: str = Field("", max_length=40)
    chapter: Optional[str] = Field(None, max_length=120)
    exam_mode: ExamMode = "BOARD"
    language: str = Field("en", description="en / hi / mr etc.")
    answer_mode: str = Field(
        "step_by_step",
        description="one_liner / cbse_board / step_by_step / hint_only",
    )

    # Luma Focused Assist (optional). If provided, orchestrator can keep answers short
    # and strictly contextual to the current lesson card.
    study_mode: Optional[str] = Field(None, max_length=40, description="e.g. 'luma'")
    mode: Optional[str] = Field(None, max_length=40, description="e.g. 'focused_assist'")
    context: Optional[LumaContext] = Field(None, description="Context for focused assist")


    # Chat history + learning memory controls (trust-first)
    private_session: bool = Field(
        False,
        description="If true, the server must not store chat history or learning memory for this request.",
    )
    memory_opt_in: bool = Field(
        False,
        description="If true, the server may update compressed learning memory cards for this user.",
    )
    surface: Optional[str] = Field(
        None,
        max_length=20,
        description="chat_ai | luma (optional; used for history storage).",
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

    # Phase-4: Answer-as-Learning-Object (optional for back-compat)
    learning_object: Optional[dict] = None
