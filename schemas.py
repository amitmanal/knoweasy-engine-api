from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, AliasChoices, ConfigDict


class SolveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    question: str = Field(..., min_length=1, max_length=2000)
    clazz: str = Field(
        ...,
        validation_alias=AliasChoices("class", "class_level", "clazz"),
        serialization_alias="class",
        description="Class level like '11', '12', or '11+12'.",
    )
    board: str = Field(..., min_length=2, max_length=50)
    subject: str = Field(..., min_length=2, max_length=50)

    chapter: Optional[str] = None
    exam_mode: str = "BOARD"          # BOARD / JEE / NEET etc (overlay)
    language: str = "en"
    answer_mode: str = "step_by_step" # step_by_step / direct / key_points
    meta: Dict[str, Any] = Field(default_factory=dict)


class SolveResponse(BaseModel):
    ok: bool = True
    answer: str
    steps: list[str] = Field(default_factory=list)
    model: str | None = None
    usage: Dict[str, Any] = Field(default_factory=dict)
