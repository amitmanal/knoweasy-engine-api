from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

ExamMode = Literal["BOARD", "JEE", "NEET", "CET"]

class SolveRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    clazz: str = Field(..., alias="class")  # frontend sends "class"
    board: str = Field(..., min_length=2, max_length=50)
    subject: str = Field(..., min_length=2, max_length=50)
    chapter: Optional[str] = Field(default=None, max_length=200)

    exam_mode: ExamMode = "BOARD"
    language: str = Field(default="en", max_length=10)
    answer_mode: str = Field(default="step_by_step", max_length=50)

    meta: Optional[Dict[str, Any]] = None

class SolveResponse(BaseModel):
    final_answer: str
    steps: List[str] = []
    assumptions: List[str] = []
    confidence: float = 0.5
    flags: List[str] = []
    safe_note: Optional[str] = None
    meta: Dict[str, Any] = {"engine": "knoweasy-orchestrator-phase1"}
