from typing import List, Optional, Literal
from pydantic import BaseModel, Field

ExamMode = Literal["BOARD", "JEE", "NEET", "CET", "OTHER"]

class SolveRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=4000)
    class_: int = Field(..., alias="class", ge=5, le=12)
    board: str = Field(..., min_length=2, max_length=40)
    subject: str = Field(..., min_length=2, max_length=40)
    chapter: Optional[str] = Field(None, max_length=120)
    exam_mode: ExamMode = "BOARD"
    language: str = Field("en", description="en / hi / mr etc.")
    answer_mode: str = Field("step_by_step", description="one_liner / cbse_board / step_by_step / hint_only")

class SolveResponse(BaseModel):
    final_answer: str
    steps: List[str] = []
    assumptions: List[str] = []
    confidence: float = Field(..., ge=0.0, le=1.0)
    flags: List[str] = []
    safe_note: Optional[str] = None
    meta: dict = {}
