"""Luma Pydantic Schemas

Data models for Answer Blueprint, content, progress, and analytics.
All models follow the Answer Blueprint v1 specification from Strategic Lock.

Design Principles:
- Immutable data structures (Pydantic BaseModel)
- Type-safe (Python 3.10+ type hints)
- Validation at API boundary
- Documentation inline
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# ANSWER BLUEPRINT MODELS (Strategic Lock v1.0 Spec)
# ============================================================================

class VisualSpec(BaseModel):
    """Specification for a visual element (diagram, graph, etc)"""
    
    type: Literal["mermaid", "svg", "graph", "table", "equation"]
    code: str = Field(..., description="Mermaid code, SVG markup, or data spec")
    caption: Optional[str] = Field(None, description="One-line purpose caption")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "mermaid",
                "code": "flowchart LR\n  A[Light] --> B[Chlorophyll]",
                "caption": "Light absorption in photosynthesis"
            }
        }


class ReasoningStep(BaseModel):
    """One step in step-by-step reasoning"""
    
    number: int = Field(..., ge=1, description="Step number (1-indexed)")
    title: Optional[str] = Field(None, description="Step title/summary")
    content: str = Field(..., description="Step explanation")
    equation: Optional[str] = Field(None, description="Math equation (LaTeX)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "number": 1,
                "title": "Photoexcitation",
                "content": "Chlorophyll absorbs photons...",
                "equation": "2H_2O \\rightarrow 4H^+ + 4e^- + O_2"
            }
        }


class PracticeQuestion(BaseModel):
    """Practice question for student to try"""
    
    text: str = Field(..., description="Question text")
    difficulty: Literal["easy", "medium", "hard"] = Field(..., description="Difficulty level")
    hint: Optional[str] = Field(None, description="Optional hint")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Calculate ΔG for the reaction at 298K...",
                "difficulty": "medium",
                "hint": "Use ΔG = ΔG° + RT ln Q"
            }
        }


class AnswerBlueprint(BaseModel):
    """Complete Answer Blueprint v1 structure
    
    This is the core IP of KnowEasy - a structured learning object
    that replaces video explanations with clarity and precision.
    """
    
    # Metadata
    title: str = Field(..., description="Context-aware title")
    why_it_matters: str = Field(..., description="Exam signal (1-2 lines)")
    
    # Core content
    conceptual_foundation: str = Field(..., description="Definitions, assumptions, scope")
    visual: Optional[VisualSpec] = Field(None, description="Visual mental model (mandatory for Tutor/Mastery)")
    steps: List[ReasoningStep] = Field(..., description="Step-by-step reasoning")
    
    # Competitive edge
    alternative_method: Optional[str] = Field(None, description="Shortcut or alternative approach (Competitive Mentor)")
    common_mistakes: List[str] = Field(..., description="Exam traps (1-3 high-value)")
    
    # Practice
    practice: List[PracticeQuestion] = Field(..., description="Practice questions")
    
    # Meta
    exam_relevance: str = Field(..., description="Importance level + usage")
    mode: Literal["lite", "tutor", "mastery"] = Field(..., description="Answer mode used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Photosynthesis — NEET High-Yield",
                "why_it_matters": "Foundation of food chains; repeatedly tested via Calvin cycle",
                "conceptual_foundation": "Anabolic endergonic process...",
                "visual": {
                    "type": "mermaid",
                    "code": "flowchart LR...",
                    "caption": "Chloroplast functional unit"
                },
                "steps": [...],
                "alternative_method": "Energy method vs equations of motion",
                "common_mistakes": ["Oxygen comes from H2O, not CO2"],
                "practice": [...],
                "exam_relevance": "High | MCQs + A-R questions",
                "mode": "tutor"
            }
        }


# ============================================================================
# LUMA CONTENT MODELS
# ============================================================================

class LumaContentMetadata(BaseModel):
    """Metadata for a learning content piece"""
    
    class_level: int = Field(..., ge=5, le=12, description="Class (5-12)")
    board: str = Field(..., description="Board/Exam (CBSE/ICSE/Maharashtra/JEE/NEET/CET)")
    subject: str = Field(..., description="Subject (Physics/Chemistry/Biology/Math)")
    chapter: str = Field(..., description="Chapter name")
    topic: str = Field(..., description="Topic name")
    difficulty: Literal["easy", "medium", "hard", "extreme"] = Field(..., description="Difficulty level")
    engine: Literal["foundation_builder", "competitive_mentor"] = Field(..., description="Academic engine")
    tags: List[str] = Field(default_factory=list, description="Search tags")


class LumaContent(BaseModel):
    """Complete learning content with Answer Blueprint"""
    
    id: Optional[str] = Field(None, description="Content ID (auto-generated)")
    metadata: LumaContentMetadata = Field(..., description="Content metadata")
    blueprint: AnswerBlueprint = Field(..., description="Answer Blueprint structure")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    published: bool = Field(default=False, description="Published status")


# ============================================================================
# USER PROGRESS MODELS
# ============================================================================

class LumaProgressSaveRequest(BaseModel):
    """Request to save user progress"""
    
    content_id: str = Field(..., description="Content ID")
    completed: bool = Field(default=False, description="Marked as completed")
    time_spent_seconds: int = Field(default=0, ge=0, description="Time spent on content")
    notes: Optional[str] = Field(None, description="User notes")
    bookmarked: bool = Field(default=False, description="Bookmarked status")


class LumaProgressRecord(BaseModel):
    """User progress record"""
    
    user_id: int = Field(..., description="User ID")
    content_id: str = Field(..., description="Content ID")
    completed: bool = Field(default=False, description="Completion status")
    time_spent_seconds: int = Field(default=0, ge=0, description="Total time spent")
    last_visited_at: datetime = Field(..., description="Last visit timestamp")
    notes: Optional[str] = Field(None, description="User notes")
    bookmarked: bool = Field(default=False, description="Bookmarked")


# ============================================================================
# LUMA AI MODELS
# ============================================================================

class LumaAIAskRequest(BaseModel):
    """Request to Luma AI chatbox"""
    
    question: str = Field(..., min_length=1, max_length=1000, description="User question")
    content_id: Optional[str] = Field(None, description="Current content ID (for context)")
    mode: Literal["lite", "tutor", "mastery"] = Field(default="tutor", description="Answer mode")


class LumaAIResponse(BaseModel):
    """Response from Luma AI"""
    
    answer: str = Field(..., description="AI answer text")
    credits_used: float = Field(..., description="Credits consumed")
    credits_remaining: float = Field(..., description="Credits remaining")
    mode: str = Field(..., description="Mode used")


# ============================================================================
# ANALYTICS MODELS
# ============================================================================

class LumaAnalyticsEvent(BaseModel):
    """Analytics event for Luma usage"""
    
    user_id: int = Field(..., description="User ID")
    event_type: str = Field(..., description="Event type (view/complete/ai_ask/bookmark)")
    content_id: Optional[str] = Field(None, description="Content ID if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")


# ============================================================================
# API RESPONSE MODELS
# ============================================================================

class LumaContentResponse(BaseModel):
    """API response for content retrieval"""
    
    ok: bool = Field(default=True)
    content: Optional[LumaContent] = None
    error: Optional[str] = None


class LumaProgressResponse(BaseModel):
    """API response for progress operations"""
    
    ok: bool = Field(default=True)
    progress: Optional[LumaProgressRecord] = None
    error: Optional[str] = None


class LumaListResponse(BaseModel):
    """API response for content listing"""
    
    ok: bool = Field(default=True)
    contents: List[LumaContent] = Field(default_factory=list)
    total: int = Field(default=0)
    error: Optional[str] = None


# ============================================================================
# CANONICAL LUMA CATALOG CONTRACT (Production lock)
# ============================================================================
# This is the ONLY contract used by:
# - GET /api/luma/content
# - GET /api/luma/content/{id}
#
# It is intentionally minimal and stable for frontend + production.
from pydantic import ConfigDict

class CanonicalLumaContent(BaseModel):
    """Canonical Luma catalog item contract (locked)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    blueprint: Dict[str, Any] = Field(default_factory=dict)
    published: bool = Field(default=False)
    created_at: datetime
    updated_at: datetime


class CanonicalLumaListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    contents: List[CanonicalLumaContent]


class CanonicalLumaSingleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = True
    content: CanonicalLumaContent


class CanonicalLumaErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool = False
    error: str
