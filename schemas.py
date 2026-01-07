from typing import List, Optional, Literal, Union
import re

from pydantic import BaseModel, Field, field_validator, AliasChoices

ExamMode = Literal["BOARD", "JEE", "NEET", "CET", "OTHER"]


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

    if n < 5:
        n = 5
    if n > 12:
        n = 12
    return n


class SolveRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)

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

    @field_validator("class_")
    @classmethod
    def validate_class(cls, v):
        return _normalize_class(v)


class SolveResponse(BaseModel):
    final_answer: str
    steps: List[str] = []
    assumptions: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = []
    safe_note: Optional[str] = None
    meta: dict = {}
