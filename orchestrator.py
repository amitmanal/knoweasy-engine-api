"""
KnowEasy Premium - World-Class AI Orchestrator v2
CEO/CTO Decision: Production-grade multi-AI system

Features:
- Smart subject-specific AI routing (Organic Chemistry → Claude, Math → GPT)
- Exam-aware intelligence (JEE/NEET → deeper reasoning)
- Circuit breaker with proper cooldown
- Request tracing and comprehensive logging
- Cost transparency per request
- Premium structured output for Luma mode
- Multi-language support (EN/HI/MR)

Author: KnowEasy AI Architecture Team
Version: 2.0.0
"""

import asyncio
import os
import time
import uuid
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import google.generativeai as genai
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import logging
from datetime import datetime, timedelta

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("knoweasy.orchestrator")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Production configuration - CEO decisions encoded here"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    
    # Model Selection
    GEMINI_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash-exp")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # Timeouts (seconds)
    TIMEOUT_FAST = 15      # Simple questions
    TIMEOUT_NORMAL = 25    # Medium questions
    TIMEOUT_DEEP = 40      # Complex/multi-AI questions
    
    # Circuit Breaker
    CB_FAILURE_THRESHOLD = 3      # Failures before circuit opens
    CB_COOLDOWN_SECONDS = 60      # How long circuit stays open
    CB_HALF_OPEN_REQUESTS = 2     # Test requests in half-open state
    
    # Cost tracking (INR per 1K tokens)
    COST_PER_1K_TOKENS = {
        "gemini": 0.05,
        "openai": 0.15,
        "claude": 0.30
    }
    
    # Credits per AI strategy
    CREDITS_BY_STRATEGY = {
        "gemini_only": 80,
        "gemini_simple": 80,
        "gemini_gpt": 120,
        "triple_ai": 180,
        "claude_deep": 150,
        "gpt_math": 100,
        "fallback": 80
    }


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


class Complexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class AIProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"


@dataclass
class RequestContext:
    """Structured context for AI requests"""
    request_id: str
    question: str
    board: str = "CBSE"
    class_level: str = "11"
    subject: str = ""
    chapter: str = ""
    exam_mode: str = "BOARD"
    language: str = "en"
    study_mode: str = "chat"
    visible_text: str = ""
    anchor_example: str = ""
    user_tier: str = "free"
    
    def __post_init__(self):
        # Normalize values
        self.board = (self.board or "CBSE").upper().strip()
        self.class_level = str(self.class_level or "11").strip()
        self.subject = (self.subject or "").strip().lower()
        self.chapter = (self.chapter or "").strip()
        self.exam_mode = (self.exam_mode or "BOARD").upper().strip()
        self.language = (self.language or "en").lower().strip()
        self.study_mode = (self.study_mode or "chat").lower().strip()
        self.user_tier = (self.user_tier or "free").lower().strip()


@dataclass
class AIResponse:
    """Structured AI response"""
    answer: str
    provider: str
    providers_used: List[str] = field(default_factory=list)
    ai_strategy: str = "unknown"
    complexity: str = "medium"
    tokens_used: int = 0
    response_time_ms: int = 0
    credits_used: int = 100
    cost_inr: float = 0.0
    success: bool = True
    error: Optional[str] = None
    cached: bool = False
    premium_formatting: bool = False
    sections: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "final_answer": self.answer,  # Compatibility
            "provider": self.provider,
            "providers_used": self.providers_used,
            "ai_strategy": self.ai_strategy,
            "complexity": self.complexity,
            "tokens": self.tokens_used,
            "response_time_ms": self.response_time_ms,
            "credits_used": self.credits_used,
            "cost_inr": self.cost_inr,
            "success": self.success,
            "error": self.error,
            "cached": self.cached,
            "premium_formatting": self.premium_formatting,
            "sections": self.sections
        }


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Production-grade circuit breaker for AI providers"""
    
    def __init__(self, name: str):
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_successes = 0
    
    def can_execute(self) -> bool:
        """Check if request can proceed"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if cooldown expired
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= Config.CB_COOLDOWN_SECONDS:
                    logger.info(f"🔄 Circuit {self.name}: OPEN → HALF_OPEN (cooldown expired)")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_successes = 0
                    return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests to test recovery
            return self.half_open_successes < Config.CB_HALF_OPEN_REQUESTS
        
        return False
    
    def record_success(self):
        """Record successful request"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            if self.half_open_successes >= Config.CB_HALF_OPEN_REQUESTS:
                logger.info(f"✅ Circuit {self.name}: HALF_OPEN → CLOSED (recovered)")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        else:
            self.failure_count = 0
        
        self.success_count += 1
    
    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"⚠️ Circuit {self.name}: HALF_OPEN → OPEN (test failed)")
            self.state = CircuitState.OPEN
        elif self.failure_count >= Config.CB_FAILURE_THRESHOLD:
            logger.warning(f"🔴 Circuit {self.name}: CLOSED → OPEN (threshold reached)")
            self.state = CircuitState.OPEN
    
    def get_status(self) -> Dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failure_count,
            "successes": self.success_count
        }


# ============================================================================
# AI CLIENTS
# ============================================================================

class BaseAIClient:
    """Base class with circuit breaker integration"""
    
    def __init__(self, name: str):
        self.name = name
        self.circuit = CircuitBreaker(name)
        self.total_calls = 0
        self.total_tokens = 0
        self.total_errors = 0
    
    async def ask(self, prompt: str, system: str = "", timeout: int = 25) -> Dict[str, Any]:
        raise NotImplementedError
    
    def get_stats(self) -> Dict:
        return {
            "provider": self.name,
            "calls": self.total_calls,
            "tokens": self.total_tokens,
            "errors": self.total_errors,
            "circuit": self.circuit.get_status()
        }


class GeminiClient(BaseAIClient):
    """Google Gemini - Primary AI (fast, cost-effective)"""
    
    def __init__(self):
        super().__init__("gemini")
        self.model = None
        self.configured = False
        
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
                self.configured = True
                logger.info(f"✅ Gemini initialized: {Config.GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"❌ Gemini init failed: {e}")
    
    async def ask(self, prompt: str, system: str = "", timeout: int = 25) -> Dict[str, Any]:
        if not self.configured:
            return {"answer": "", "error": "Gemini not configured", "success": False, "provider": "gemini"}
        
        if not self.circuit.can_execute():
            return {"answer": "", "error": "Gemini circuit open", "success": False, "provider": "gemini"}
        
        try:
            self.total_calls += 1
            start = time.time()
            
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.model.generate_content,
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    )
                ),
                timeout=timeout
            )
            
            answer = response.text if response.text else ""
            elapsed_ms = int((time.time() - start) * 1000)
            tokens = len(full_prompt.split()) + len(answer.split())
            self.total_tokens += tokens
            
            self.circuit.record_success()
            logger.info(f"✅ Gemini: {len(answer)} chars, {elapsed_ms}ms, ~{tokens} tokens")
            
            return {
                "answer": answer,
                "provider": "gemini",
                "tokens": tokens,
                "time_ms": elapsed_ms,
                "success": True
            }
            
        except asyncio.TimeoutError:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ Gemini timeout ({timeout}s)")
            return {"answer": "", "error": f"Timeout after {timeout}s", "success": False, "provider": "gemini"}
            
        except Exception as e:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ Gemini error: {e}")
            return {"answer": "", "error": str(e), "success": False, "provider": "gemini"}


class OpenAIClient(BaseAIClient):
    """OpenAI GPT - Best for math and logical reasoning"""
    
    def __init__(self):
        super().__init__("openai")
        self.client = None
        self.configured = False
        
        if Config.OPENAI_API_KEY:
            try:
                self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
                self.configured = True
                logger.info(f"✅ OpenAI initialized: {Config.OPENAI_MODEL}")
            except Exception as e:
                logger.error(f"❌ OpenAI init failed: {e}")
    
    async def ask(self, prompt: str, system: str = "", timeout: int = 25) -> Dict[str, Any]:
        if not self.configured:
            return {"answer": "", "error": "OpenAI not configured", "success": False, "provider": "openai"}
        
        if not self.circuit.can_execute():
            return {"answer": "", "error": "OpenAI circuit open", "success": False, "provider": "openai"}
        
        try:
            self.total_calls += 1
            start = time.time()
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048
                ),
                timeout=timeout
            )
            
            answer = response.choices[0].message.content or ""
            elapsed_ms = int((time.time() - start) * 1000)
            tokens = response.usage.total_tokens if response.usage else 0
            self.total_tokens += tokens
            
            self.circuit.record_success()
            logger.info(f"✅ OpenAI: {len(answer)} chars, {elapsed_ms}ms, {tokens} tokens")
            
            return {
                "answer": answer,
                "provider": "openai",
                "tokens": tokens,
                "time_ms": elapsed_ms,
                "success": True
            }
            
        except asyncio.TimeoutError:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ OpenAI timeout ({timeout}s)")
            return {"answer": "", "error": f"Timeout after {timeout}s", "success": False, "provider": "openai"}
            
        except Exception as e:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ OpenAI error: {e}")
            return {"answer": "", "error": str(e), "success": False, "provider": "openai"}


class ClaudeClient(BaseAIClient):
    """Claude - Best for chemistry, biology, deep reasoning"""
    
    def __init__(self):
        super().__init__("claude")
        self.client = None
        self.configured = False
        
        if Config.CLAUDE_API_KEY:
            try:
                self.client = AsyncAnthropic(api_key=Config.CLAUDE_API_KEY)
                self.configured = True
                logger.info(f"✅ Claude initialized: {Config.CLAUDE_MODEL}")
            except Exception as e:
                logger.error(f"❌ Claude init failed: {e}")
    
    async def ask(self, prompt: str, system: str = "", timeout: int = 30) -> Dict[str, Any]:
        if not self.configured:
            return {"answer": "", "error": "Claude not configured", "success": False, "provider": "claude"}
        
        if not self.circuit.can_execute():
            return {"answer": "", "error": "Claude circuit open", "success": False, "provider": "claude"}
        
        try:
            self.total_calls += 1
            start = time.time()
            
            response = await asyncio.wait_for(
                self.client.messages.create(
                    model=Config.CLAUDE_MODEL,
                    max_tokens=2048,
                    system=system if system else "You are a helpful AI tutor.",
                    messages=[{"role": "user", "content": prompt}]
                ),
                timeout=timeout
            )
            
            answer = response.content[0].text if response.content else ""
            elapsed_ms = int((time.time() - start) * 1000)
            tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
            self.total_tokens += tokens
            
            self.circuit.record_success()
            logger.info(f"✅ Claude: {len(answer)} chars, {elapsed_ms}ms, {tokens} tokens")
            
            return {
                "answer": answer,
                "provider": "claude",
                "tokens": tokens,
                "time_ms": elapsed_ms,
                "success": True
            }
            
        except asyncio.TimeoutError:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ Claude timeout ({timeout}s)")
            return {"answer": "", "error": f"Timeout after {timeout}s", "success": False, "provider": "claude"}
            
        except Exception as e:
            self.total_errors += 1
            self.circuit.record_failure()
            logger.error(f"❌ Claude error: {e}")
            return {"answer": "", "error": str(e), "success": False, "provider": "claude"}


# ============================================================================
# SMART ROUTING ENGINE
# ============================================================================

class SmartRouter:
    """
    CEO Decision: Intelligent AI routing based on:
    - Subject (Chemistry → Claude, Math → GPT, General → Gemini)
    - Exam (JEE/NEET → deeper reasoning)
    - Complexity (Simple → fast, Complex → multi-AI)
    - User tier (Free → Gemini only, Pro → smart routing, Max → full power)
    """
    
    # Subject → Preferred AI mapping
    SUBJECT_PREFERENCES = {
        # Chemistry - Claude excels at mechanisms and organic reactions
        "chemistry": ["claude", "gemini", "openai"],
        "organic chemistry": ["claude", "openai", "gemini"],
        "inorganic chemistry": ["claude", "gemini", "openai"],
        "physical chemistry": ["openai", "gemini", "claude"],
        
        # Physics - GPT good at derivations, Gemini good at concepts
        "physics": ["openai", "gemini", "claude"],
        
        # Mathematics - GPT excels at step-by-step proofs
        "mathematics": ["openai", "gemini", "claude"],
        "maths": ["openai", "gemini", "claude"],
        "math": ["openai", "gemini", "claude"],
        
        # Biology - Claude good at explanations, Gemini for quick facts
        "biology": ["claude", "gemini", "openai"],
        "botany": ["gemini", "claude", "openai"],
        "zoology": ["gemini", "claude", "openai"],
        
        # Default
        "default": ["gemini", "openai", "claude"]
    }
    
    # Exam → Reasoning depth
    EXAM_DEPTH = {
        "JEE": "deep",      # Multi-AI for complex problems
        "NEET": "deep",     # Multi-AI for detailed biology
        "CET": "medium",    # State-level, moderate depth
        "BOARD": "standard" # CBSE boards, standard depth
    }
    
    # Class level adjustment
    CLASS_COMPLEXITY = {
        "5": 0.5, "6": 0.5, "7": 0.6, "8": 0.7,
        "9": 0.8, "10": 0.9,
        "11": 1.0, "12": 1.0
    }
    
    @classmethod
    def get_subject_preference(cls, subject: str) -> List[str]:
        """Get preferred AI order for subject"""
        subject_lower = subject.lower().strip()
        
        # Check exact match first
        if subject_lower in cls.SUBJECT_PREFERENCES:
            return cls.SUBJECT_PREFERENCES[subject_lower]
        
        # Check partial matches
        for key, prefs in cls.SUBJECT_PREFERENCES.items():
            if key in subject_lower or subject_lower in key:
                return prefs
        
        return cls.SUBJECT_PREFERENCES["default"]
    
    @classmethod
    def should_use_multi_ai(cls, ctx: RequestContext, complexity: Complexity) -> bool:
        """Determine if multi-AI is beneficial"""
        
        # Free tier never gets multi-AI
        if ctx.user_tier == "free":
            return False
        
        # Always multi-AI for complex + premium
        if complexity == Complexity.COMPLEX and ctx.user_tier in ("pro", "max"):
            return True
        
        # JEE/NEET medium+ questions
        if ctx.exam_mode in ("JEE", "NEET") and complexity != Complexity.SIMPLE:
            return ctx.user_tier in ("pro", "max")
        
        # Max tier medium questions in Luma mode
        if ctx.user_tier == "max" and ctx.study_mode == "luma" and complexity == Complexity.MEDIUM:
            return True
        
        return False
    
    @classmethod
    def get_strategy(cls, ctx: RequestContext, complexity: Complexity) -> Tuple[str, List[str], int]:
        """
        Returns: (strategy_name, ai_providers_to_use, timeout)
        """
        prefs = cls.get_subject_preference(ctx.subject)
        exam_depth = cls.EXAM_DEPTH.get(ctx.exam_mode, "standard")
        
        # Free tier: Gemini only, always
        if ctx.user_tier == "free":
            return ("gemini_only", ["gemini"], Config.TIMEOUT_FAST)
        
        # Simple questions: Single best AI
        if complexity == Complexity.SIMPLE:
            return ("gemini_simple", [prefs[0]], Config.TIMEOUT_FAST)
        
        # Medium questions
        if complexity == Complexity.MEDIUM:
            if ctx.user_tier == "max" or (ctx.user_tier == "pro" and exam_depth == "deep"):
                return ("gemini_gpt", prefs[:2], Config.TIMEOUT_NORMAL)
            return ("gemini_simple", [prefs[0]], Config.TIMEOUT_NORMAL)
        
        # Complex questions
        if complexity == Complexity.COMPLEX:
            if ctx.user_tier == "max":
                # Full triple AI for max tier complex
                if exam_depth == "deep":
                    return ("triple_ai", prefs[:3], Config.TIMEOUT_DEEP)
                return ("gemini_gpt", prefs[:2], Config.TIMEOUT_DEEP)
            elif ctx.user_tier == "pro":
                return ("gemini_gpt", prefs[:2], Config.TIMEOUT_NORMAL)
        
        # Default fallback
        return ("gemini_only", ["gemini"], Config.TIMEOUT_NORMAL)


# ============================================================================
# COMPLEXITY ANALYZER
# ============================================================================

class ComplexityAnalyzer:
    """Analyzes question complexity for smart routing"""
    
    SIMPLE_PATTERNS = [
        "what is", "define", "meaning of", "full form", "formula for",
        "value of", "who is", "when was", "which is", "where is",
        "state the", "name the", "list", "mention",
        "क्या है", "परिभाषा दें", "काय आहे", "व्याख्या"
    ]
    
    COMPLEX_PATTERNS = [
        "explain in detail", "step by step", "derive", "prove", "derivation",
        "compare and contrast", "analyze", "evaluate", "why and how",
        "mechanism", "reaction mechanism", "solve", "calculate", "numerical",
        "prove that", "show that", "justify", "reason why",
        "विस्तार से समझाएं", "सिद्ध करें", "सोडवा"
    ]
    
    EXAM_KEYWORDS = [
        "jee", "neet", "pyq", "previous year", "exam", "board exam",
        "competitive", "entrance", "mcq pattern"
    ]
    
    @classmethod
    def analyze(cls, question: str, ctx: RequestContext) -> Complexity:
        """Determine question complexity"""
        q_lower = question.lower()
        word_count = len(question.split())
        
        # Check for simple patterns
        if any(p in q_lower for p in cls.SIMPLE_PATTERNS):
            if word_count < 15:
                return Complexity.SIMPLE
        
        # Check for complex patterns
        if any(p in q_lower for p in cls.COMPLEX_PATTERNS):
            return Complexity.COMPLEX
        
        # Exam keywords boost complexity
        if any(k in q_lower for k in cls.EXAM_KEYWORDS):
            if word_count > 10:
                return Complexity.COMPLEX
            return Complexity.MEDIUM
        
        # JEE/NEET questions tend to be more complex
        if ctx.exam_mode in ("JEE", "NEET") and word_count > 15:
            return Complexity.COMPLEX
        
        # Length-based heuristic
        if word_count < 10:
            return Complexity.SIMPLE
        elif word_count > 30:
            return Complexity.COMPLEX
        else:
            return Complexity.MEDIUM


# ============================================================================
# PROMPT BUILDER
# ============================================================================

class PromptBuilder:
    """Builds intelligent, context-aware prompts"""
    
    LUMA_TEMPLATE = """You are Luma, a patient and encouraging AI tutor designed for Indian students.

📚 CONTEXT:
- Class: {class_level} | Board: {board}
- Subject: {subject}
- Chapter: {chapter}
- Exam Focus: {exam_mode}

🎓 YOUR TEACHING STYLE:
1. Start with a simple hook or relatable example
2. Explain the core concept in 2-3 clear paragraphs
3. Use bullet points for key facts
4. Include a formula box if relevant (use proper notation)
5. Add 1-2 memory tips or mnemonics
6. End with a quick check question

💡 RULES:
- Use simple language suitable for Class {class_level}
- Avoid jargon; explain technical terms when first used
- Be encouraging: "Great question!" "Let's explore this together!"
- If the student seems confused, offer to break it down further

{language_instruction}"""

    CHAT_TEMPLATE = """You are Luma, a friendly AI tutor for Indian students.

📋 Context: Class {class_level} {board}, {subject}
🎯 Mode: Quick help / doubt solving

Be concise, clear, and encouraging. Answer directly but completely.
If it's a complex topic, offer to explain more.

{language_instruction}"""

    LANGUAGE_INSTRUCTIONS = {
        "en": "Respond in clear English.",
        "hi": "आप हिंदी में जवाब दे सकते हैं। Technical terms अंग्रेज़ी में रखें।",
        "mr": "तुम्ही मराठीत उत्तर देऊ शकता. Technical terms इंग्रजीत ठेवा."
    }
    
    @classmethod
    def build_system_prompt(cls, ctx: RequestContext) -> str:
        """Build system prompt based on context"""
        
        lang_inst = cls.LANGUAGE_INSTRUCTIONS.get(ctx.language, cls.LANGUAGE_INSTRUCTIONS["en"])
        
        if ctx.study_mode == "luma":
            return cls.LUMA_TEMPLATE.format(
                class_level=ctx.class_level,
                board=ctx.board,
                subject=ctx.subject.title() if ctx.subject else "General",
                chapter=ctx.chapter.replace("_", " ").title() if ctx.chapter else "Not specified",
                exam_mode=ctx.exam_mode,
                language_instruction=lang_inst
            )
        else:
            return cls.CHAT_TEMPLATE.format(
                class_level=ctx.class_level,
                board=ctx.board,
                subject=ctx.subject.title() if ctx.subject else "General",
                language_instruction=lang_inst
            )
    
    @classmethod
    def build_user_prompt(cls, ctx: RequestContext) -> str:
        """Build user prompt with lesson context"""
        
        parts = [f"Student's question: {ctx.question}"]
        
        if ctx.visible_text:
            parts.append(f"\n📖 Current lesson content:\n{ctx.visible_text[:500]}")
        
        if ctx.anchor_example:
            parts.append(f"\n📌 Example from lesson:\n{ctx.anchor_example[:250]}")
        
        return "\n".join(parts)


# ============================================================================
# RESPONSE FORMATTER
# ============================================================================

class ResponseFormatter:
    """Formats AI responses for premium display"""
    
    @classmethod
    def create_premium_sections(cls, answer: str, ctx: RequestContext) -> List[Dict]:
        """Parse answer into structured sections for premium rendering"""
        
        # Only for Luma mode
        if ctx.study_mode != "luma":
            return None
        
        sections = []
        lines = answer.split("\n")
        current_section = {"type": "text", "content": []}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect section headers
            if line.startswith("##") or line.startswith("**") and line.endswith("**"):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {
                    "type": "heading",
                    "title": line.strip("#* "),
                    "content": []
                }
            # Detect bullet points
            elif line.startswith("-") or line.startswith("•") or line.startswith("*"):
                if current_section.get("type") != "list":
                    if current_section["content"]:
                        sections.append(current_section)
                    current_section = {"type": "list", "content": []}
                current_section["content"].append(line.lstrip("-•* "))
            # Detect formulas (lines with mathematical notation)
            elif any(c in line for c in ["=", "→", "⇌", "∫", "∑", "Δ"]):
                sections.append({"type": "formula", "content": line})
            # Regular text
            else:
                if current_section.get("type") == "list":
                    sections.append(current_section)
                    current_section = {"type": "text", "content": []}
                current_section["content"].append(line)
        
        # Add last section
        if current_section.get("content"):
            sections.append(current_section)
        
        return sections if sections else None
    
    @classmethod
    def estimate_cost(cls, tokens: int, providers: List[str]) -> float:
        """Estimate cost in INR"""
        total = 0.0
        for provider in providers:
            rate = Config.COST_PER_1K_TOKENS.get(provider, 0.1)
            total += (tokens / 1000) * rate
        return round(total, 4)


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class WorldClassOrchestrator:
    """
    Production-grade AI orchestrator for KnowEasy
    
    Features:
    - Smart routing based on subject, exam, complexity
    - Circuit breakers for reliability
    - Request tracing for debugging
    - Cost transparency
    - Premium formatting for Luma
    """
    
    def __init__(self):
        self.gemini = GeminiClient()
        self.openai = OpenAIClient()
        self.claude = ClaudeClient()
        self.request_count = 0
        self.start_time = time.time()
        logger.info("🚀 WorldClassOrchestrator v2 initialized")
    
    def _get_client(self, provider: str) -> BaseAIClient:
        """Get AI client by name"""
        clients = {
            "gemini": self.gemini,
            "openai": self.openai,
            "claude": self.claude
        }
        return clients.get(provider, self.gemini)
    
    async def solve(
        self,
        question: str,
        context: dict,
        user_tier: str = "free",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main entry point for solving questions.
        
        Args:
            question: The student's question
            context: Dict with board, class, subject, chapter, study_mode, etc.
            user_tier: 'free', 'pro', or 'max'
        
        Returns:
            Structured response dict
        """
        
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        self.request_count += 1
        
        logger.info(f"📥 [{request_id}] New request | tier={user_tier} | mode={context.get('study_mode', 'chat')}")
        
        # Build request context
        ctx = RequestContext(
            request_id=request_id,
            question=question,
            board=context.get("board", "CBSE"),
            class_level=str(context.get("class", context.get("class_level", "11"))),
            subject=context.get("subject", ""),
            chapter=context.get("chapter", ""),
            exam_mode=context.get("exam_mode", "BOARD"),
            language=context.get("language", "en"),
            study_mode=context.get("study_mode", "chat"),
            visible_text=context.get("visible_text", ""),
            anchor_example=context.get("anchor_example", ""),
            user_tier=user_tier
        )
        
        try:
            # Analyze complexity
            complexity = ComplexityAnalyzer.analyze(question, ctx)
            logger.info(f"📊 [{request_id}] Complexity: {complexity.value}")
            
            # Get routing strategy
            strategy, providers, timeout = SmartRouter.get_strategy(ctx, complexity)
            logger.info(f"🔀 [{request_id}] Strategy: {strategy} | Providers: {providers}")
            
            # Build prompts
            system_prompt = PromptBuilder.build_system_prompt(ctx)
            user_prompt = PromptBuilder.build_user_prompt(ctx)
            
            # Execute AI call(s)
            if len(providers) == 1:
                result = await self._single_ai_call(providers[0], user_prompt, system_prompt, timeout)
            else:
                result = await self._multi_ai_call(providers, user_prompt, system_prompt, timeout)
            
            # Calculate metrics
            elapsed_ms = int((time.time() - start_time) * 1000)
            credits = Config.CREDITS_BY_STRATEGY.get(strategy, 100)
            cost = ResponseFormatter.estimate_cost(result.get("tokens", 0), result.get("providers_used", providers[:1]))
            
            # Create premium sections for Luma mode
            sections = None
            if ctx.study_mode == "luma" and result.get("success"):
                sections = ResponseFormatter.create_premium_sections(result.get("answer", ""), ctx)
            
            # Build response
            response = AIResponse(
                answer=result.get("answer", ""),
                provider=result.get("provider", providers[0] if providers else "unknown"),
                providers_used=result.get("providers_used", [result.get("provider")] if result.get("provider") else []),
                ai_strategy=strategy,
                complexity=complexity.value,
                tokens_used=result.get("tokens", 0),
                response_time_ms=elapsed_ms,
                credits_used=credits,
                cost_inr=cost,
                success=result.get("success", False),
                error=result.get("error"),
                premium_formatting=ctx.study_mode == "luma",
                sections=sections
            )
            
            logger.info(f"✅ [{request_id}] Complete | {elapsed_ms}ms | {credits} credits | strategy={strategy}")
            
            return response.to_dict()
            
        except Exception as e:
            logger.error(f"❌ [{request_id}] Error: {e}")
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return AIResponse(
                answer="I encountered an error processing your question. Please try again.",
                provider="error",
                providers_used=[],
                ai_strategy="error",
                complexity="unknown",
                response_time_ms=elapsed_ms,
                credits_used=0,
                success=False,
                error=str(e)
            ).to_dict()
    
    async def _single_ai_call(
        self,
        provider: str,
        prompt: str,
        system: str,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute single AI provider call"""
        
        client = self._get_client(provider)
        result = await client.ask(prompt, system, timeout)
        result["providers_used"] = [provider] if result.get("success") else []
        return result
    
    async def _multi_ai_call(
        self,
        providers: List[str],
        prompt: str,
        system: str,
        timeout: int
    ) -> Dict[str, Any]:
        """Execute multiple AI providers in parallel and merge results"""
        
        # Create tasks for all providers
        tasks = []
        for provider in providers:
            client = self._get_client(provider)
            tasks.append(client.ask(prompt, system, timeout))
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful results
        successful = []
        providers_used = []
        total_tokens = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Provider {providers[i]} failed: {result}")
                continue
            if result.get("success"):
                successful.append(result)
                providers_used.append(providers[i])
                total_tokens += result.get("tokens", 0)
        
        if not successful:
            # All failed - try single Gemini as fallback
            logger.warning("All multi-AI calls failed, trying Gemini fallback")
            return await self._single_ai_call("gemini", prompt, system, timeout)
        
        # Merge results - pick best answer
        best = max(successful, key=lambda x: len(x.get("answer", "")))
        
        return {
            "answer": best.get("answer", ""),
            "provider": best.get("provider", "unknown"),
            "providers_used": providers_used,
            "tokens": total_tokens,
            "time_ms": max(r.get("time_ms", 0) for r in successful),
            "success": True
        }
    
    def get_stats(self) -> Dict:
        """Get orchestrator statistics"""
        uptime = time.time() - self.start_time
        return {
            "version": "2.0.0",
            "uptime_seconds": int(uptime),
            "total_requests": self.request_count,
            "providers": {
                "gemini": self.gemini.get_stats(),
                "openai": self.openai.get_stats(),
                "claude": self.claude.get_stats()
            }
        }


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

orchestrator = WorldClassOrchestrator()


# ============================================================================
# PUBLIC API (Called by router.py)
# ============================================================================

async def solve(
    question: str,
    context: dict,
    user_tier: str = "free",
    **kwargs
) -> Dict[str, Any]:
    """
    Main solve function for router.py
    
    Args:
        question: Student's question (string)
        context: Dict with board, class, subject, chapter, study_mode, language, etc.
        user_tier: 'free', 'pro', or 'max'
    
    Returns:
        Dict with answer, ai_strategy, providers_used, credits_used, etc.
    """
    return await orchestrator.solve(question, context, user_tier, **kwargs)


async def solve_question(question: str, context: Dict, user_tier: str = "free") -> Dict:
    """Legacy function name support"""
    return await orchestrator.solve(question, context, user_tier)


def get_orchestrator_stats() -> Dict:
    """Get orchestrator statistics for monitoring"""
    return orchestrator.get_stats()
