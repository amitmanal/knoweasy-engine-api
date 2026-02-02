from __future__ import annotations

"""Luma API Router

FastAPI endpoints for Luma learning platform.

Endpoints:
- GET /api/luma/content/{id} - Get content by ID
- GET /api/luma/content - List content with filters
- POST /api/luma/progress/save - Save user progress
- GET /api/luma/progress/{content_id} - Get user progress
- POST /api/luma/ai/ask - Simple AI chatbox

Auth:
- Public: content listing + content by id
- Protected: progress + catalog + ai ask
"""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header

from luma_store import (, resolve_content_id
    list_catalog,
    create_catalog_item,
    delete_catalog_item,
    get_content,
    list_content,
)
from luma_schemas import (
    CanonicalLumaListResponse,
    CanonicalLumaSingleResponse,
    CanonicalLumaErrorResponse,
    LumaContentResponse,
    LumaProgressSaveRequest,
    LumaProgressResponse,
    LumaAIAskRequest,
    LumaAIResponse,
)
from luma_config import calculate_credits, validate_mode

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api/luma", tags=["luma"])

# Ensure Luma tables on module load (non-blocking)
try:
    import luma_store
    luma_store.ensure_tables()
except Exception as e:
    logger.warning(f"luma_router: table setup failed: {e}")


# ============================================================================
# AUTHENTICATION HELPER
# ============================================================================


async def require_user(authorization: str = Header(None)) -> int:
    """Require a logged-in user (Bearer token)."""
    user_id = await get_current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id

async def get_current_user_id(authorization: str = Header(None)) -> Optional[int]:
    """Extract user ID from Bearer token.
    
    Uses existing KnowEasy auth system.
    Returns None if not authenticated (for public endpoints).
    """
    if not authorization:
        return None
    
    try:
        # Import auth utilities (same as other routers)
        from auth_utils import decode_token
        
        if not authorization.startswith("Bearer "):
            return None
        
        token = authorization.split(" ", 1)[1]
        payload = decode_token(token)
        
        if not payload or "sub" not in payload:
            return None
        
        return int(payload["sub"])
    
    except Exception as e:
        logger.warning(f"luma_router: auth failed: {e}")
        return None


# ============================================================================
# CONTENT ENDPOINTS
# ============================================================================
# ============================================================================
# CONTENT ENDPOINTS
# ============================================================================

@router.get(
    "/content/{content_id}",
    response_model=CanonicalLumaSingleResponse,
    responses={404: {"model": CanonicalLumaErrorResponse}, 500: {"model": CanonicalLumaErrorResponse}},
)
async def get_content_endpoint(content_id: str):
    """Get learning content by ID (public).

    Returns canonical LumaContent contract for frontend consumption.
    """
    try:
        content = get_content(content_id)

        if not content:
            raise HTTPException(status_code=404, detail={"ok": False, "error": "CONTENT_NOT_FOUND"})

        return {"ok": True, "content": content}

    except HTTPException:
        raise
    except Exception as e:
        # TEMP: do not mask catalog errors until stable
        logger.exception(f"luma_router: get_content failed: {e}")
        raise HTTPException(status_code=500, detail={"ok": False, "error": f"{e.__class__.__name__}: {str(e)}"})


@router.get(
    "/content",
    response_model=CanonicalLumaListResponse,
    responses={500: {"model": CanonicalLumaErrorResponse}},
)
async def list_content_endpoint(
    class_level: Optional[int] = None,
    subject: Optional[str] = None,
    board: Optional[str] = None,
    fallback: bool = False,
    limit: int = 50
):
    """List published content with optional filters (public)."""
    try:
        limit = min(limit, 100)

        contents = list_content(
            class_level=class_level,
            subject=subject,
            board=board,
            fallback=fallback,
            limit=limit
        )

        return {"ok": True, "contents": contents}

    except Exception as e:
        # TEMP: do not mask catalog errors until stable
        logger.exception(f"luma_router: list_content failed: {e}")
        raise HTTPException(status_code=500, detail={"ok": False, "error": f"{e.__class__.__name__}: {str(e)}"})
# ============================================================================
# PROGRESS ENDPOINTS (Auth Required)
# ============================================================================

@router.post("/progress/save", response_model=LumaProgressResponse)
async def save_progress_endpoint(
    request: LumaProgressSaveRequest,
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """Save user learning progress.
    
    Requires authentication.
    
    Request Body:
        content_id: Content ID
        completed: Marked as completed (boolean)
        time_spent_seconds: Time spent (incremental)
        notes: User notes (optional)
        bookmarked: Bookmark status
        
    Returns:
        Progress save result
        
    Example:
        POST /api/luma/progress/save
        {
            "content_id": "photosynthesis-neet-001",
            "completed": true,
            "time_spent_seconds": 300,
            "bookmarked": true
        }
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        result = save_progress(
            user_id=user_id,
            content_id=request.content_id,
            completed=request.completed,
            time_spent_seconds=request.time_spent_seconds,
            notes=request.notes,
            bookmarked=request.bookmarked
        )
        
        # Log analytics event
        event_type = "complete" if request.completed else "progress"
        log_event(user_id, event_type, request.content_id)
        
        if not result.get("ok"):
            return LumaProgressResponse(
                ok=False,
                error=result.get("error", "SAVE_FAILED")
            )
        
        return LumaProgressResponse(ok=True)
    
    except Exception as e:
        logger.exception(f"luma_router: save_progress failed: {e}")
        return LumaProgressResponse(
            ok=False,
            error="INTERNAL_ERROR"
        )


@router.get("/progress/{content_id}", response_model=LumaProgressResponse)
async def get_progress_endpoint(
    content_id: str,
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """Get user progress for specific content.
    
    Requires authentication.
    
    Args:
        content_id: Content identifier
        
    Returns:
        User progress data
        
    Example:
        GET /api/luma/progress/photosynthesis-neet-001
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        progress = get_progress(user_id, content_id)
        
        # Log view event
        log_event(user_id, "view", content_id)
        
        return LumaProgressResponse(
            ok=True,
            progress=progress
        )
    
    except Exception as e:
        logger.exception(f"luma_router: get_progress failed: {e}")
        return LumaProgressResponse(
            ok=False,
            error="INTERNAL_ERROR"
        )


# ============================================================================
# LUMA AI CHATBOX (Auth Required, Uses Credits)
# ============================================================================

@router.post("/ai/ask", response_model=LumaAIResponse)
async def luma_ai_ask(
    request: LumaAIAskRequest,
    user_id: Optional[int] = Depends(get_current_user_id)
):
    """Simple Luma AI chatbox endpoint.
    
    This is a simplified AI chat specifically for Luma learning.
    - Context-aware (knows current content)
    - Simple text-only (no images/PDFs)
    - Uses credit system
    
    Requires authentication.
    
    Request Body:
        question: User question (max 1000 chars)
        content_id: Current content ID for context (optional)
        mode: Answer mode (lite/tutor/mastery, default: tutor)
        
    Returns:
        AI answer, credits used, remaining credits
        
    Example:
        POST /api/luma/ai/ask
        {
            "question": "Why does oxygen come from water?",
            "content_id": "photosynthesis-neet-001",
            "mode": "tutor"
        }
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Validate mode
        mode = validate_mode(request.mode)
        
        # Calculate credit cost
        credits_needed = calculate_credits(
            mode=mode,
            is_luma_simple=True
        )
        
        # Check and consume credits
        from billing_store import consume_credits, get_wallet
        
        # Get user's plan (from existing auth/billing system)
        # For this slice, we'll assume "pro" - in production, fetch from user profile
        user_plan = "pro"  # TODO: Get from user profile
        
        # Try to consume credits
        try:
            credit_result = consume_credits(
                user_id=user_id,
                plan=user_plan,
                units=credits_needed,
                meta={
                    "feature": "luma_ai",
                    "mode": mode,
                    "content_id": request.content_id
                }
            )
            
            if not credit_result.get("ok"):
                raise HTTPException(
                    status_code=402,
                    detail="INSUFFICIENT_CREDITS"
                )
        
        except ValueError as e:
            # Insufficient credits
            raise HTTPException(
                status_code=402,
                detail="INSUFFICIENT_CREDITS"
            )
        
        # Call AI (use existing orchestrator)
        from orchestrator import ask_ai
        
        # Build context-aware prompt
        prompt = request.question
        if request.content_id:
            content = get_content(request.content_id)
            if content:
                # Add content context to prompt
                topic = content["metadata"].get("topic", "")
                prompt = f"Context: Student is learning about {topic}.\n\nQuestion: {prompt}"
        
        # Get AI answer
        ai_response = ask_ai(
            prompt=prompt,
            mode=mode,
            user_id=user_id
        )
        
        # Log analytics
        log_event(
            user_id=user_id,
            event_type="ai_ask",
            content_id=request.content_id,
            metadata={"mode": mode, "credits": credits_needed}
        )
        
        # Get remaining credits
        wallet = get_wallet(user_id, user_plan)
        remaining = wallet.get("included_credits_balance", 0) + wallet.get("booster_credits_balance", 0)
        
        return LumaAIResponse(
            answer=ai_response.get("answer", "Sorry, I couldn't generate an answer."),
            credits_used=credits_needed,
            credits_remaining=remaining,
            mode=mode
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.exception(f"luma_router: ai_ask failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="AI_REQUEST_FAILED"
        )


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def luma_health():
    """Health check for Luma system.
    
    Returns:
        Status of Luma components
    """
    return {
        "ok": True,
        "service": "luma",
        "endpoints": [
            "GET /api/luma/content/{id}",
            "GET /api/luma/content",
            "POST /api/luma/progress/save",
            "GET /api/luma/progress/{id}",
            "POST /api/luma/ai/ask"
        ]
    }


# -------------------- User Catalog (Library) --------------------
@router.get("/catalog")
def catalog_list(limit: int = 50, offset: int = 0, user: dict = Depends(require_user)):
    """List current user's saved library items."""
    return {"ok": True, "items": list_catalog(user_id=user["id"], limit=limit, offset=offset)}

@router.post("/catalog")
def catalog_create(payload: dict, user: dict = Depends(require_user)):
    """Create a library item for current user."""
    item = {
        "user_id": user["id"],
        "title": payload.get("title") or "Untitled",
        "doc_type": payload.get("doc_type") or "link",
        "source": payload.get("source") or "user",
        "file_url": payload.get("file_url") or "",
        "file_key": payload.get("file_key"),
        "metadata_json": json.dumps(payload.get("metadata", {})) if not isinstance(payload.get("metadata"), str) else payload.get("metadata"),
    }
    create_catalog_item(item)
    return {"ok": True}

@router.delete("/catalog/{item_id}")
def catalog_delete(item_id: int, user: dict = Depends(require_user)):
    delete_catalog_item(user_id=user["id"], item_id=item_id)
    return {"ok": True}


@router.get("/resolve")
async def resolve_content_endpoint(
    board: str | None = None,
    class_level: int | None = None,
    subject: str | None = None,
    chapter: str | None = None,
):
    """Resolve a luma content_id for the given study context."""
    content_id = resolve_content_id(board=board, class_level=class_level, subject=subject, chapter=chapter)
    return {"ok": True, "content_id": content_id}


