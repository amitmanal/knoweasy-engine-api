import json
"""Luma API Router
try:
    from auth_router import require_user
except Exception:
    require_user = None


FastAPI endpoints for Luma learning platform.

Endpoints:
- GET /api/luma/content/{id} - Get content by ID
- GET /api/luma/content - List content with filters
- POST /api/luma/progress/save - Save user progress
- GET /api/luma/progress/{content_id} - Get user progress
- POST /api/luma/ai/ask - Simple AI chatbox

All endpoints require authentication except content listing.
"""

from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header

from luma_store import list_catalog, create_catalog_item, delete_catalog_item
from luma_schemas import (
    LumaContentResponse,
    LumaProgressSaveRequest,
    LumaProgressResponse,
    LumaAIAskRequest,
    LumaAIResponse,
)
from luma_config import calculate_credits, validate_mode

logger = logging.getLogger("knoweasy-engine-api")

router = APIRouter(prefix="/api/luma", tags=["luma"])

# Ensure tables on module load (non-blocking)
try:
    ensure_tables()
except Exception as e:
    logger.warning(f"luma_router: table setup failed: {e}")


# ============================================================================
# AUTHENTICATION HELPER
# ============================================================================

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

@router.get("/content/{content_id}", response_model=LumaContentResponse)
async def get_content_endpoint(content_id: str):
    """Get learning content by ID.
    
    Public endpoint - no auth required.
    Content must be published to be accessible.
    
    Args:
        content_id: Content identifier (e.g., "photosynthesis-neet-001")
        
    Returns:
        Content with Answer Blueprint structure
        
    Example:
        GET /api/luma/content/photosynthesis-neet-001
    """
    try:
        content = get_content(content_id)
        
        if not content:
            return LumaContentResponse(
                ok=False,
                error="CONTENT_NOT_FOUND"
            )
        
        return LumaContentResponse(
            ok=True,
            content=content
        )
    
    except Exception as e:
        logger.exception(f"luma_router: get_content failed: {e}")
        return LumaContentResponse(
            ok=False,
            error="INTERNAL_ERROR"
        )


@router.get("/content", response_model=dict)
async def list_content_endpoint(
    class_level: Optional[int] = None,
    subject: Optional[str] = None,
    board: Optional[str] = None,
    limit: int = 50
):
    """List published content with optional filters.
    
    Public endpoint - no auth required.
    
    Query Parameters:
        class_level: Filter by class (5-12)
        subject: Filter by subject (Physics/Chemistry/Biology/Math)
        board: Filter by board (CBSE/ICSE/Maharashtra/JEE/NEET)
        limit: Maximum results (default: 50, max: 100)
        
    Returns:
        List of content items
        
    Example:
        GET /api/luma/content?class_level=11&subject=Biology&board=NEET
    """
    try:
        # Cap limit to prevent abuse
        limit = min(limit, 100)
        
        contents = list_content(
            class_level=class_level,
            subject=subject,
            board=board,
            limit=limit
        )
        
        return {
            "ok": True,
            "contents": contents,
            "total": len(contents)
        }
    
    except Exception as e:
        logger.exception(f"luma_router: list_content failed: {e}")
        return {
            "ok": False,
            "error": "INTERNAL_ERROR"
        }


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
def catalog_list(limit: int = 50, offset: int = 0, user=Depends(require_user)):
    """List current user's saved library items."""
    if require_user is None:
        return {"ok": False, "error": "auth_not_configured"}
    return {"ok": True, "items": list_catalog(user_id=user["id"], limit=limit, offset=offset)}

@router.post("/catalog")
def catalog_create(payload: dict, user=Depends(require_user)):
    """Create a library item for current user."""
    if require_user is None:
        return {"ok": False, "error": "auth_not_configured"}
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
def catalog_delete(item_id: int, user=Depends(require_user)):
    if require_user is None:
        return {"ok": False, "error": "auth_not_configured"}
    delete_catalog_item(user_id=user["id"], item_id=item_id)
    return {"ok": True}

