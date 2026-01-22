from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator

GoalOverlay = Literal["NONE","BOARD","JEE_PCM","NEET_PCB","CET_PCM","CET_PCB"]
Difficulty = Literal["easy","medium","hard","mixed"]
TestKind = Literal["quiz","boards","entrance"]

class TestGenerateRequest(BaseModel):
    class_n: int = Field(..., ge=5, le=12, description="Class/grade number (5-12)")
    board: str = Field(..., min_length=2, max_length=32, description="Board slug: cbse/maharashtra/icse etc")
    subject: str = Field(..., min_length=1, max_length=64)
    chapters: List[str] = Field(default_factory=list, description="Chapter slugs or names")
    goal: GoalOverlay = Field(default="NONE", description="11-12 entrance overlay (does not change base syllabus)")
    kind: TestKind = Field(default="quiz", description="quiz/boards/entrance")
    n_questions: int = Field(default=15, ge=5, le=120)
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=240)
    difficulty: Difficulty = Field(default="mixed")
    language: str = Field(default="en", description="en/hi/mr etc")
    request_id: Optional[str] = Field(default=None, description="Idempotency key from client")

    @field_validator("board","subject", mode="before")
    @classmethod
    def _clean(cls, v):
        if v is None:
            return v
        return str(v).strip().lower()

    @field_validator("chapters", mode="before")
    @classmethod
    def _clean_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip()]
        return [str(x).strip() for x in list(v) if str(x).strip()]

class TestQuestion(BaseModel):
    id: int
    question: str
    options: List[str]
    answer_index: int
    explanation: Optional[str] = None

class GeneratedTest(BaseModel):
    title: str
    class_n: int
    board: str
    subject: str
    chapters: List[str] = Field(default_factory=list)
    kind: TestKind
    goal: GoalOverlay = "NONE"
    duration_minutes: int = 20
    questions: List[TestQuestion]

class TestGenerateResponse(BaseModel):
    ok: bool = True
    test: GeneratedTest
    meta: dict = Field(default_factory=dict)
