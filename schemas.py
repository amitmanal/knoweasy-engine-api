from typing import List, Optional, Literal, Union
import re
from pydantic import BaseModel, Field, field_validator

ExamMode = Literal["BOARD", "JEE", "NEET", "CET", "OTHER"]

def _normalize_class(v) -> int:
    """Accept int or strings like '11', '11+12', 'Integrated (11+12)' and return a safe int 5..12."""
    if v is None:
        raise ValueError("class is required")
    if isinstance(v, int):
        n = v
    else:
        s = str(v).strip()
        m = re.search(r"(\d{1,2})", s)
        if not m:
            raise ValueError("class must contain a number like 5..12")
        n = int(m.group(1))
    if n < 5 or n > 12:
        raise ValueError("class must be between 5 and 12")
    return n

class SolveRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)
    class_: Union[int, str] = Field(..., alias="class")
    board: str = Field(..., min_length=2, max_length=40)
    subject: str = Field(..., min_length=2, max_length=40)
    chapter: Optional[str] = Field(None, max_length=120)
    exam_mode: ExamMode = "BOARD"
    language: str = Field("en", description="en / hi / mr etc.")
    answer_mode: str = Field("step_by_step", description="one_liner / cbse_board / step_by_step / hint_only")

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
