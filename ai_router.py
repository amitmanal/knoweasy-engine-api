from __future__ import annotations
import json, logging, os
from typing import Any, Dict
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from config import GEMINI_API_KEY, AI_PROVIDER

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/solve-question")
async def solve_question(
    prompt: str,
    subject: str = "",
    board: str = "",
    class_level: int = 9,
    timeout_s: int = 15,
    authorization: str = Header(None)
) -> Dict[str, Any]:
    """Solve a student question using AI"""
    try:
        if not authorization:
            return JSONResponse({"ok": False, "error": "Unauthorized"}, status_code=401)
        
        prompt = prompt.strip()
        if not prompt:
            return JSONResponse({"ok": False, "error": "Empty question"}, status_code=400)
        
        provider = AI_PROVIDER or "gemini"
        
        if provider == "gemini":
            if not GEMINI_API_KEY:
                return JSONResponse({"ok": False, "error": "Gemini API key not configured", "hint": "Set GEMINI_API_KEY environment variable"}, status_code=503)
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt, request_options={"timeout": timeout_s})
                answer = response.text
            except Exception as e:
                logger.error(f"Gemini error: {e}")
                return JSONResponse({"ok": False, "error": f"AI error: {str(e)}"}, status_code=503)
        else:
            return JSONResponse({"ok": False, "error": f"Provider {provider} not supported yet"}, status_code=501)
        
        return {"ok": True, "answer": answer, "provider": provider}
    except Exception as e:
        logger.error(f"Solve question error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check AI service health"""
    provider = AI_PROVIDER or "gemini"
    return {"ok": True, "provider": provider, "configured": bool(GEMINI_API_KEY if provider == "gemini" else True)}


def generate_json(content: str, response_format: str = 'json') -> Dict:
    """Generate JSON response from content"""
    try:
        if isinstance(content, dict):
            return content
        return {"content": content, "format": response_format}
    except:
        return {"content": str(content), "format": response_format}
