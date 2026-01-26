"""
KnowEasy AI Orchestrator - ULTRA STABLE VERSION
Version: 2.2.0 (Production Stable)

CRITICAL FIX: This version uses SYNCHRONOUS functions
- solve() is synchronous (no async/await needed in router.py)
- Compatible with both sync and async routers
- Proper error handling with fallbacks
- Multi-AI support (Gemini → OpenAI → Claude)

DROP-IN REPLACEMENT: Just replace orchestrator.py on Render
"""

import os
import time
import traceback
from typing import Dict, Any, Optional, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("knoweasy.orchestrator")


# ============================================================================
# AI SDK IMPORTS (with graceful fallbacks)
# ============================================================================

# Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    logger.warning("Gemini SDK not available")

# OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    logger.warning("OpenAI SDK not available")

# Claude/Anthropic
try:
    from anthropic import Anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    Anthropic = None
    logger.warning("Anthropic SDK not available")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Production configuration from environment variables"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", os.getenv("CLAUDE_API_KEY", ""))
    
    # Model Selection
    GEMINI_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"))
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # Timeouts (seconds)
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "30"))
    
    # Debug mode
    DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
    
    # Credits
    CREDITS_GEMINI = int(os.getenv("CREDITS_GEMINI", "80"))
    CREDITS_OPENAI = int(os.getenv("CREDITS_OPENAI", "100"))
    CREDITS_CLAUDE = int(os.getenv("CREDITS_CLAUDE", "120"))


# ============================================================================
# INITIALIZE AI CLIENTS (at module load)
# ============================================================================

_gemini_model = None
_openai_client = None
_claude_client = None

def _init_clients():
    """Initialize AI clients once at startup"""
    global _gemini_model, _openai_client, _claude_client
    
    # Gemini
    if GEMINI_AVAILABLE and Config.GEMINI_API_KEY:
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            _gemini_model = genai.GenerativeModel(Config.GEMINI_MODEL)
            logger.info(f"✅ Gemini initialized: {Config.GEMINI_MODEL}")
        except Exception as e:
            logger.error(f"❌ Gemini init failed: {e}")
    
    # OpenAI
    if OPENAI_AVAILABLE and Config.OPENAI_API_KEY:
        try:
            _openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
            logger.info(f"✅ OpenAI initialized: {Config.OPENAI_MODEL}")
        except Exception as e:
            logger.error(f"❌ OpenAI init failed: {e}")
    
    # Claude
    if CLAUDE_AVAILABLE and Config.CLAUDE_API_KEY:
        try:
            _claude_client = Anthropic(api_key=Config.CLAUDE_API_KEY)
            logger.info(f"✅ Claude initialized: {Config.CLAUDE_MODEL}")
        except Exception as e:
            logger.error(f"❌ Claude init failed: {e}")

# Initialize on import
_init_clients()


# ============================================================================
# AI PROVIDER FUNCTIONS (All Synchronous)
# ============================================================================

def _call_gemini(prompt: str, system_prompt: str = "") -> Dict[str, Any]:
    """Call Gemini API - SYNCHRONOUS"""
    if not _gemini_model:
        return {"answer": "", "error": "Gemini not configured", "provider": "gemini"}
    
    try:
        start = time.time()
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        response = _gemini_model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        
        answer = ""
        if response and response.text:
            answer = response.text.strip()
        elif response and hasattr(response, 'parts') and response.parts:
            answer = "".join(p.text for p in response.parts if hasattr(p, 'text')).strip()
        
        latency = int((time.time() - start) * 1000)
        logger.info(f"Gemini responded in {latency}ms, {len(answer)} chars")
        
        return {
            "answer": answer,
            "provider": "gemini",
            "model": Config.GEMINI_MODEL,
            "latency_ms": latency
        }
        
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return {"answer": "", "error": str(e), "provider": "gemini"}


def _call_openai(prompt: str, system_prompt: str = "") -> Dict[str, Any]:
    """Call OpenAI API - SYNCHRONOUS"""
    if not _openai_client:
        return {"answer": "", "error": "OpenAI not configured", "provider": "openai"}
    
    try:
        start = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = _openai_client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
            timeout=Config.AI_TIMEOUT
        )
        
        answer = response.choices[0].message.content.strip() if response.choices else ""
        latency = int((time.time() - start) * 1000)
        logger.info(f"OpenAI responded in {latency}ms, {len(answer)} chars")
        
        return {
            "answer": answer,
            "provider": "openai",
            "model": Config.OPENAI_MODEL,
            "latency_ms": latency
        }
        
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return {"answer": "", "error": str(e), "provider": "openai"}


def _call_claude(prompt: str, system_prompt: str = "") -> Dict[str, Any]:
    """Call Claude API - SYNCHRONOUS"""
    if not _claude_client:
        return {"answer": "", "error": "Claude not configured", "provider": "claude"}
    
    try:
        start = time.time()
        
        response = _claude_client.messages.create(
            model=Config.CLAUDE_MODEL,
            max_tokens=2048,
            system=system_prompt or "You are Luma, a helpful AI tutor for Indian students.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = ""
        if response.content:
            answer = "".join(b.text for b in response.content if hasattr(b, 'text')).strip()
        
        latency = int((time.time() - start) * 1000)
        logger.info(f"Claude responded in {latency}ms, {len(answer)} chars")
        
        return {
            "answer": answer,
            "provider": "claude", 
            "model": Config.CLAUDE_MODEL,
            "latency_ms": latency
        }
        
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return {"answer": "", "error": str(e), "provider": "claude"}


# ============================================================================
# PROMPT BUILDER
# ============================================================================

def _build_system_prompt(context: Dict) -> str:
    """Build system prompt based on student context"""
    
    board = str(context.get("board", "")).upper()
    klass = str(context.get("class", context.get("klass", context.get("class_", ""))))
    subject = str(context.get("subject", ""))
    chapter = str(context.get("chapter", ""))
    language = str(context.get("language", "en"))
    study_mode = str(context.get("study_mode", ""))
    
    prompt = f"""You are Luma, a patient and encouraging AI tutor for Indian students.

📚 STUDENT CONTEXT:
- Class: {klass}
- Board: {board}
- Subject: {subject}
{f'- Chapter: {chapter}' if chapter else ''}

🎯 YOUR TEACHING STYLE:
1. Start with a clear, simple explanation
2. Use everyday examples relatable to Indian students
3. Break complex topics into digestible parts
4. Be encouraging: "Great question!", "Let's solve this together!"
5. Include memory tricks or mnemonics when helpful

📝 RESPONSE FORMAT:
- Use bullet points for steps
- Use **bold** for key terms
- Include formulas clearly
- Add a "💡 Remember:" tip at the end

🌐 LANGUAGE: Respond in English. If student uses Hindi/Marathi, you may mix."""

    # Add exam-specific guidance
    exam_mode = str(context.get("exam_mode", "")).upper()
    if exam_mode in ("JEE", "JEE_MAIN", "JEE_ADV", "JEE_ADVANCED"):
        prompt += """

🎯 JEE FOCUS:
- Include numerical problem-solving approach
- Cover conceptual depth for competitive exams
- Mention common JEE patterns"""
    
    elif exam_mode == "NEET":
        prompt += """

🎯 NEET FOCUS:
- Focus on NCERT-aligned explanations
- Include diagram descriptions
- Emphasize biological applications"""
    
    return prompt


def _build_user_prompt(question: str, context: Dict) -> str:
    """Build user prompt with question and context"""
    
    # Check for Luma focused assist mode
    extra_context = context.get("context", {})
    if isinstance(extra_context, dict):
        section = extra_context.get("section", "")
        visible_text = extra_context.get("visible_text", "")
        
        if section or visible_text:
            return f"""Current Lesson Section: {section}

Student's Question: {question}

{f'Context from lesson: {visible_text[:500]}' if visible_text else ''}

Please answer concisely, focusing on this specific question."""
    
    return question


# ============================================================================
# MAIN SOLVE FUNCTION - SYNCHRONOUS
# ============================================================================

def solve(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main solve function - SYNCHRONOUS
    
    This is called by router.py as: out = solve(payload)
    No await needed!
    
    Args:
        payload: Dict with question, board, class, subject, etc.
    
    Returns:
        Dict with final_answer, steps, confidence, flags, meta, etc.
    """
    
    start_time = time.time()
    
    # Extract question
    question = str(payload.get("question", "")).strip()
    if not question:
        return _error_response("No question provided", "EMPTY_QUESTION")
    
    logger.info(f"Processing: {question[:80]}...")
    
    # Build context
    context = {
        "board": payload.get("board", ""),
        "class": payload.get("class", payload.get("klass", payload.get("class_", ""))),
        "subject": payload.get("subject", ""),
        "chapter": payload.get("chapter", ""),
        "study_mode": payload.get("study_mode", payload.get("mode", "")),
        "exam_mode": payload.get("exam_mode", ""),
        "language": payload.get("language", "en"),
        "context": payload.get("context", {})
    }
    
    # Build prompts
    system_prompt = _build_system_prompt(context)
    user_prompt = _build_user_prompt(question, context)
    
    # Try AI providers in order
    providers_tried = []
    providers_used = []
    answer = ""
    credits = 0
    
    # 1. Gemini first (fastest, cheapest)
    if _gemini_model and not answer:
        providers_tried.append("gemini")
        result = _call_gemini(user_prompt, system_prompt)
        if result.get("answer"):
            answer = result["answer"]
            providers_used.append("gemini")
            credits = Config.CREDITS_GEMINI
    
    # 2. OpenAI fallback
    if _openai_client and not answer:
        providers_tried.append("openai")
        result = _call_openai(user_prompt, system_prompt)
        if result.get("answer"):
            answer = result["answer"]
            providers_used.append("openai")
            credits = Config.CREDITS_OPENAI
    
    # 3. Claude fallback
    if _claude_client and not answer:
        providers_tried.append("claude")
        result = _call_claude(user_prompt, system_prompt)
        if result.get("answer"):
            answer = result["answer"]
            providers_used.append("claude")
            credits = Config.CREDITS_CLAUDE
    
    # No answer from any provider
    if not answer:
        logger.error(f"All providers failed: {providers_tried}")
        return _error_response(
            "Our AI is temporarily busy. Please try again in a moment.",
            "AI_UNAVAILABLE"
        )
    
    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Build successful response
    return {
        "final_answer": answer,
        "answer": answer,  # Alias
        "steps": [],
        "assumptions": [],
        "confidence": 0.85,
        "flags": ["AI_RESPONSE"],
        "safe_note": None,
        "meta": {
            "engine": "knoweasy-orchestrator-v2.2",
            "providers_tried": providers_tried,
            "providers_used": providers_used,
            "latency_ms": latency_ms,
            "question_length": len(question),
            "answer_length": len(answer),
            "board": context.get("board", ""),
            "class": context.get("class", ""),
            "subject": context.get("subject", "")
        },
        # Frontend compatibility fields
        "providers_used": providers_used,
        "ai_strategy": "_".join(providers_used) if providers_used else "none",
        "credits_used": credits,
        "response_time_ms": latency_ms
    }


def _error_response(message: str, code: str) -> Dict[str, Any]:
    """Build error response"""
    return {
        "final_answer": f"I'm sorry: {message}",
        "answer": f"I'm sorry: {message}",
        "steps": [],
        "assumptions": [],
        "confidence": 0.0,
        "flags": ["ERROR", code],
        "safe_note": message,
        "meta": {"engine": "knoweasy-orchestrator-v2.2", "error": message, "error_code": code},
        "providers_used": [],
        "ai_strategy": "error",
        "credits_used": 0,
        "response_time_ms": 0
    }


# ============================================================================
# HEALTH CHECK & STATS
# ============================================================================

def health_check() -> Dict[str, Any]:
    """Return orchestrator health"""
    return {
        "status": "ok",
        "version": "2.2.0",
        "providers": {
            "gemini": {"available": _gemini_model is not None, "model": Config.GEMINI_MODEL},
            "openai": {"available": _openai_client is not None, "model": Config.OPENAI_MODEL},
            "claude": {"available": _claude_client is not None, "model": Config.CLAUDE_MODEL}
        }
    }

def get_orchestrator_stats() -> Dict[str, Any]:
    """Return stats for monitoring"""
    return health_check()


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

def solve_question(question: str, context: Dict = None, user_tier: str = "free") -> Dict[str, Any]:
    """Legacy function signature"""
    payload = context or {}
    payload["question"] = question
    return solve(payload)


# For async callers (optional)
async def solve_async(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Async wrapper - just calls sync solve()"""
    return solve(payload)
