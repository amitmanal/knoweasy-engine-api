from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

class SolveRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    mode: Optional[str] = "doubt"          # doubt / explain / quiz etc (future)
    meta: Optional[Dict[str, Any]] = None  # optional client metadata

class SolveResponse(BaseModel):
    ok: bool = True
    answer: str
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
