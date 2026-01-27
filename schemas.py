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

    # Luma Focused Assist (optional). If provided, orchestrator can keep answers short
    # and strictly contextual to the current lesson card.
    study_mode: Optional[str] = Field(None, max_length=40, description="e.g. 'luma'")
    mode: Optional[str] = Field(None, max_length=40, description="e.g. 'focused_assist'")
    context: Optional[LumaContext] = Field(None, description="Context for focused assist")

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


# ============================================================================
# AI HUB (Chat AI) — Structured Learning Object response (v1)
# ============================================================================

AIHubMode = Literal["lite", "tutor", "mastery"]
AIHubLanguage = Literal["auto", "en", "hi", "mr"]

class AIHubFile(BaseModel):
    name: str = Field(default="", max_length=200)
    mime: str = Field(default="", max_length=120)
    b64: str = Field(default="", max_length=5_000_000)

class AIHubAttachments(BaseModel):
    image: Optional[AIHubFile] = None
    pdf: Optional[AIHubFile] = None

class AIHubClientMeta(BaseModel):
    tz: Optional[str] = None
    ua: Optional[str] = None

class AIHubRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=6000)
    mode: AIHubMode = "tutor"
    language: AIHubLanguage = "auto"
    attachments: Optional[AIHubAttachments] = None
    client: Optional[AIHubClientMeta] = None

    @field_validator("question")
    @classmethod
    def _clean_question_aihub(cls, v: str):
        v = _clean_text(v)
        return v

class AIHubResponse(BaseModel):
    title: str
    why_matters: str
    explanation_sections: List[str] = Field(default_factory=list)
    visual: str = ""
    misconception: str = ""
    concept_terms: List[str] = Field(default_factory=list)
    # internal-only, may be logged but frontend doesn't need it
    confidence_label: Optional[str] = None
