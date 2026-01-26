"""
KnowEasy Premium - Enhanced AI Orchestrator
CEO Decision: Production-ready multi-AI system
Integrates: Gemini + GPT-4o-mini + Claude Sonnet

FIXED VERSION: Proper response format, robust error handling
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Production configuration"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    
    # Model Selection (CEO Decision)
    GEMINI_MODEL = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-2.0-flash-exp")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    
    # Timeouts
    TIMEOUT = int(os.getenv("AI_TIMEOUT", "25"))
    
    # Cost per question (in rupees) - for billing calculation
    COST_PER_CREDIT = {
        "gemini_simple": 0.03,
        "gemini_gpt": 0.50,
        "triple_ai": 2.00
    }
    
    # Credits per question type
    CREDITS_PER_QUESTION = {
        "simple": 80,
        "medium": 100,
        "complex": 150
    }


# ============================================================================
# AI CLIENTS
# ============================================================================

class AIClient:
    """Base class for all AI providers"""
    
    def __init__(self, name: str):
        self.name = name
        self.calls_made = 0
        self.tokens_used = 0
        self.errors = 0
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Override in subclasses"""
        raise NotImplementedError
    
    def get_stats(self) -> Dict:
        """Return usage statistics"""
        return {
            "provider": self.name,
            "calls": self.calls_made,
            "tokens": self.tokens_used,
            "errors": self.errors
        }


class GeminiClient(AIClient):
    """Google Gemini client - Primary AI for KnowEasy"""
    
    def __init__(self):
        super().__init__("gemini")
        self.model = None
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
                logger.info(f"✅ Gemini client initialized with model: {Config.GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"❌ Gemini initialization failed: {e}")
                self.model = None
        else:
            logger.warning("⚠️ GEMINI_API_KEY not configured")
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask Gemini"""
        if not self.model:
            return {"answer": "", "error": "Gemini not configured", "success": False, "provider": "gemini"}
        
        try:
            self.calls_made += 1
            start = time.time()
            
            # Combine system + prompt
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            
            # Call Gemini (in thread for async compatibility)
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2000,
                )
            )
            
            answer = response.text if response.text else ""
            elapsed = time.time() - start
            
            # Estimate tokens
            tokens = len(full_prompt.split()) + len(answer.split())
            self.tokens_used += tokens
            
            logger.info(f"✅ Gemini response: {len(answer)} chars in {elapsed:.2f}s")
            
            return {
                "answer": answer,
                "provider": "gemini",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
            logger.error(f"❌ Gemini error: {e}")
            return {
                "answer": "",
                "error": str(e),
                "provider": "gemini",
                "success": False
            }


class OpenAIClient(AIClient):
    """OpenAI GPT client"""
    
    def __init__(self):
        super().__init__("openai")
        self.client = None
        if Config.OPENAI_API_KEY:
            try:
                self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
                logger.info(f"✅ OpenAI client initialized with model: {Config.OPENAI_MODEL}")
            except Exception as e:
                logger.error(f"❌ OpenAI initialization failed: {e}")
                self.client = None
        else:
            logger.warning("⚠️ OPENAI_API_KEY not configured")
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask GPT"""
        if not self.client:
            return {"answer": "", "error": "OpenAI not configured", "success": False, "provider": "openai"}
        
        try:
            self.calls_made += 1
            start = time.time()
            
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            
            response = await self.client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=Config.TIMEOUT
            )
            
            answer = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            elapsed = time.time() - start
            
            self.tokens_used += tokens
            
            logger.info(f"✅ OpenAI response: {len(answer)} chars in {elapsed:.2f}s")
            
            return {
                "answer": answer,
                "provider": "openai",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
            logger.error(f"❌ OpenAI error: {e}")
            return {
                "answer": "",
                "error": str(e),
                "provider": "openai",
                "success": False
            }


class ClaudeClient(AIClient):
    """Anthropic Claude client - Premium AI"""
    
    def __init__(self):
        super().__init__("claude")
        self.client = None
        if Config.CLAUDE_API_KEY:
            try:
                self.client = AsyncAnthropic(api_key=Config.CLAUDE_API_KEY)
                logger.info(f"✅ Claude client initialized with model: {Config.CLAUDE_MODEL}")
            except Exception as e:
                logger.error(f"❌ Claude initialization failed: {e}")
                self.client = None
        else:
            logger.warning("⚠️ CLAUDE_API_KEY not configured")
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask Claude"""
        if not self.client:
            return {"answer": "", "error": "Claude not configured", "success": False, "provider": "claude"}
        
        try:
            self.calls_made += 1
            start = time.time()
            
            response = await self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=2000,
                system=system if system else "You are a helpful AI tutor.",
                messages=[{"role": "user", "content": prompt}],
                timeout=Config.TIMEOUT
            )
            
            answer = response.content[0].text if response.content else ""
            tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
            elapsed = time.time() - start
            
            self.tokens_used += tokens
            
            logger.info(f"✅ Claude response: {len(answer)} chars in {elapsed:.2f}s")
            
            return {
                "answer": answer,
                "provider": "claude",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
            logger.error(f"❌ Claude error: {e}")
            return {
                "answer": "",
                "error": str(e),
                "provider": "claude",
                "success": False
            }


# ============================================================================
# PROMPT BUILDER
# ============================================================================

class PromptBuilder:
    """Builds smart prompts based on context"""
    
    @staticmethod
    def build_system_prompt(context: Dict[str, Any]) -> str:
        """Build system prompt from context"""
        
        parts = []
        
        # Identity
        parts.append("You are Luma, a patient and encouraging AI tutor for Indian students.")
        parts.append("You explain concepts clearly, use relatable examples, and build confidence.")
        
        # Context
        class_level = context.get("class", "11")
        board = context.get("board", "CBSE").upper()
        parts.append(f"\n📚 Teaching: Class {class_level} {board}")
        
        if context.get("subject"):
            parts.append(f"📖 Subject: {context['subject'].title()}")
        
        if context.get("chapter"):
            chapter = context['chapter'].replace('_', ' ').title()
            parts.append(f"📝 Chapter: {chapter}")
        
        # Mode-specific instructions
        study_mode = context.get("study_mode", "chat")
        
        if study_mode == "luma":
            parts.append("\n🎓 TEACHING MODE (Focused Assist):")
            parts.append("- Provide structured, step-by-step explanations")
            parts.append("- Break complex concepts into digestible parts")
            parts.append("- Use examples relatable to Indian students")
            parts.append("- Be encouraging and build confidence")
            parts.append("- Connect to the current lesson context when provided")
            parts.append("- Add a practice question at the end if appropriate")
        else:
            parts.append("\n💬 CHAT MODE (Quick Help):")
            parts.append("- Provide direct, helpful answers")
            parts.append("- Be concise but clear")
            parts.append("- Friendly and encouraging tone")
            parts.append("- Offer to explain more if needed")
        
        # Exam mode adjustments
        exam_mode = context.get("exam_mode", "BOARD")
        if exam_mode in ("JEE", "NEET", "CET"):
            parts.append(f"\n🎯 Exam Focus: {exam_mode}")
            parts.append("- Include exam-relevant tips when appropriate")
            parts.append("- Point out common mistakes in exams")
        
        # Language
        language = context.get("language", "en")
        if language == "hi":
            parts.append("\n🇮🇳 भाषा: हिंदी में उत्तर दें जब उपयुक्त हो। Technical terms in English.")
        elif language == "mr":
            parts.append("\n🇮🇳 भाषा: मराठीमध्ये उत्तर द्या. Technical terms in English.")
        
        return "\n".join(parts)
    
    @staticmethod
    def build_user_prompt(question: str, context: Dict[str, Any]) -> str:
        """Build user prompt with lesson context"""
        
        parts = [f"Student's question: {question}"]
        
        # Add visible lesson content if available (Luma mode)
        if context.get("visible_text"):
            visible = str(context["visible_text"])[:600]
            parts.append(f"\n📖 Current lesson content:\n{visible}")
        
        # Add anchor example if available
        if context.get("anchor_example"):
            example = str(context["anchor_example"])[:300]
            parts.append(f"\n📌 Example from lesson:\n{example}")
        
        # Add section context
        if context.get("section"):
            parts.append(f"\n📍 Current section: {context['section']}")
        
        return "\n".join(parts)


# ============================================================================
# COMPLEXITY ANALYZER
# ============================================================================

class ComplexityAnalyzer:
    """Determines question complexity for smart routing"""
    
    SIMPLE_TRIGGERS = [
        "what is", "define", "meaning of", "full form",
        "formula for", "value of", "who is", "when was",
        "which is", "where is", "state the", "name the",
        "क्या है", "परिभाषा", "काय आहे"
    ]
    
    COMPLEX_TRIGGERS = [
        "explain in detail", "step by step", "derive", "prove",
        "compare and contrast", "analyze", "evaluate",
        "why and how", "reasoning", "solve", "calculate",
        "mechanism", "reaction", "numerical", "derivation",
        "विस्तार से", "साबित करें", "सिद्ध करा"
    ]
    
    @classmethod
    def analyze(cls, question: str) -> str:
        """
        Returns: "simple", "medium", or "complex"
        """
        q_lower = question.lower()
        word_count = len(question.split())
        
        # Simple questions
        if any(trigger in q_lower for trigger in cls.SIMPLE_TRIGGERS):
            if word_count < 12:
                return "simple"
        
        # Complex questions
        if any(trigger in q_lower for trigger in cls.COMPLEX_TRIGGERS):
            return "complex"
        
        # Length-based
        if word_count < 8:
            return "simple"
        elif word_count > 25:
            return "complex"
        else:
            return "medium"


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class EnhancedOrchestrator:
    """
    CEO Decision: Smart AI orchestration for premium experience
    Routes questions to appropriate AI(s) based on complexity and user tier
    """
    
    def __init__(self):
        self.gemini = GeminiClient()
        self.openai = OpenAIClient()
        self.claude = ClaudeClient()
        self.prompt_builder = PromptBuilder()
        self.analyzer = ComplexityAnalyzer()
        logger.info("🚀 EnhancedOrchestrator initialized")
    
    async def solve(
        self,
        question: str,
        context: Dict[str, Any],
        user_tier: str = "free",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main solving function
        Returns structured response with answer, metadata, and billing info
        """
        
        logger.info(f"📥 Solve request: tier={user_tier}, mode={context.get('study_mode', 'chat')}")
        
        # Validate inputs
        if not question or len(question.strip()) < 3:
            return {
                "answer": "Please provide a valid question.",
                "error": "Question too short",
                "success": False,
                "provider": None
            }
        
        # Analyze complexity
        complexity = self.analyzer.analyze(question)
        logger.info(f"📊 Question complexity: {complexity}")
        
        # Build prompts
        system_prompt = self.prompt_builder.build_system_prompt(context)
        user_prompt = self.prompt_builder.build_user_prompt(question, context)
        
        # Route based on tier and complexity
        study_mode = context.get("study_mode", "chat")
        
        try:
            # ================================================================
            # CHAT AI MODE (Simple, fast)
            # ================================================================
            if study_mode == "chat":
                result = await self._chat_mode(user_prompt, system_prompt, complexity, user_tier)
            
            # ================================================================
            # LUMA AI MODE (Premium, structured)
            # ================================================================
            else:
                result = await self._luma_mode(user_prompt, system_prompt, complexity, user_tier)
            
            # Add metadata
            result["complexity"] = complexity
            result["study_mode"] = study_mode
            result["credits_used"] = Config.CREDITS_PER_QUESTION.get(complexity, 100)
            
            logger.info(f"✅ Solve complete: provider={result.get('provider')}, strategy={result.get('ai_strategy')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Solve error: {e}")
            return {
                "answer": "I encountered an error processing your question. Please try again.",
                "error": str(e),
                "success": False,
                "provider": None,
                "complexity": complexity,
                "study_mode": study_mode
            }
    
    async def _chat_mode(
        self,
        prompt: str,
        system: str,
        complexity: str,
        user_tier: str
    ) -> Dict[str, Any]:
        """
        Chat AI: Fast responses using primarily Gemini
        Pro/Max can get GPT enhancement on medium+ questions
        """
        
        # Free tier: Gemini only
        if user_tier == "free":
            result = await self.gemini.ask(prompt, system)
            result["ai_strategy"] = "gemini_only"
            result["tier"] = "free"
            return result
        
        # Pro/Max: Smart enhancement
        if complexity == "simple":
            result = await self.gemini.ask(prompt, system)
            result["ai_strategy"] = "gemini_simple"
            result["tier"] = user_tier
            return result
        else:
            # Use Gemini + GPT for better quality
            try:
                responses = await asyncio.gather(
                    self.gemini.ask(prompt, system),
                    self.openai.ask(prompt, system),
                    return_exceptions=True
                )
                
                result = self._merge_two(responses[0], responses[1])
                result["ai_strategy"] = "gemini_gpt"
                result["tier"] = user_tier
                return result
            except Exception as e:
                logger.warning(f"Multi-AI failed, falling back to Gemini: {e}")
                result = await self.gemini.ask(prompt, system)
                result["ai_strategy"] = "gemini_fallback"
                return result
    
    async def _luma_mode(
        self,
        prompt: str,
        system: str,
        complexity: str,
        user_tier: str
    ) -> Dict[str, Any]:
        """
        Luma AI: Premium teaching mode
        Pro gets Gemini + GPT
        Max gets all 3 AIs on complex questions
        """
        
        # Free tier shouldn't reach here, but just in case
        if user_tier == "free":
            result = await self.gemini.ask(prompt, system)
            result["ai_strategy"] = "gemini_only"
            return result
        
        # Pro tier
        if user_tier == "pro":
            if complexity == "simple":
                result = await self.gemini.ask(prompt, system)
                result["ai_strategy"] = "gemini_simple"
            else:
                try:
                    responses = await asyncio.gather(
                        self.gemini.ask(prompt, system),
                        self.openai.ask(prompt, system),
                        return_exceptions=True
                    )
                    result = self._merge_two(responses[0], responses[1])
                    result["ai_strategy"] = "gemini_gpt"
                except Exception as e:
                    logger.warning(f"Pro multi-AI failed: {e}")
                    result = await self.gemini.ask(prompt, system)
                    result["ai_strategy"] = "gemini_fallback"
            
            result["tier"] = "pro"
            result["premium_formatting"] = True
            return result
        
        # Max/Family tier - FULL POWER
        if complexity == "simple":
            result = await self.gemini.ask(prompt, system)
            result["ai_strategy"] = "gemini_simple"
        
        elif complexity == "medium":
            try:
                responses = await asyncio.gather(
                    self.gemini.ask(prompt, system),
                    self.openai.ask(prompt, system),
                    return_exceptions=True
                )
                result = self._merge_two(responses[0], responses[1])
                result["ai_strategy"] = "gemini_gpt"
            except Exception as e:
                logger.warning(f"Max medium multi-AI failed: {e}")
                result = await self.gemini.ask(prompt, system)
                result["ai_strategy"] = "gemini_fallback"
        
        else:  # complex - USE ALL THREE!
            try:
                responses = await asyncio.gather(
                    self.gemini.ask(prompt, system),
                    self.openai.ask(prompt, system),
                    self.claude.ask(prompt, system),
                    return_exceptions=True
                )
                result = self._fusion_three(responses[0], responses[1], responses[2])
                result["ai_strategy"] = "triple_ai"
                result["premium_badge"] = True  # Show "Powered by 3 AIs" badge
            except Exception as e:
                logger.warning(f"Max triple-AI failed: {e}")
                result = await self.claude.ask(prompt, system)
                if not result.get("success"):
                    result = await self.gemini.ask(prompt, system)
                result["ai_strategy"] = "fallback"
        
        result["tier"] = user_tier
        result["premium_formatting"] = True
        return result
    
    def _merge_two(self, resp1: Dict, resp2: Dict) -> Dict:
        """Merge two AI responses - pick better one"""
        
        # Handle exceptions from gather
        if isinstance(resp1, Exception):
            resp1 = {"answer": "", "success": False, "provider": "unknown"}
        if isinstance(resp2, Exception):
            resp2 = {"answer": "", "success": False, "provider": "unknown"}
        
        if not resp1.get("success"):
            return resp2
        if not resp2.get("success"):
            return resp1
        
        # Use longer/more detailed response
        answer1 = resp1.get("answer", "")
        answer2 = resp2.get("answer", "")
        
        if len(answer2) > len(answer1) * 1.2:
            chosen = resp2
            providers = [resp2.get("provider", "unknown"), resp1.get("provider", "unknown")]
        else:
            chosen = resp1
            providers = [resp1.get("provider", "unknown"), resp2.get("provider", "unknown")]
        
        return {
            "answer": chosen["answer"],
            "providers_used": providers,
            "provider": chosen.get("provider"),
            "tokens": resp1.get("tokens", 0) + resp2.get("tokens", 0),
            "time": max(resp1.get("time", 0), resp2.get("time", 0)),
            "success": True
        }
    
    def _fusion_three(self, gemini: Dict, gpt: Dict, claude: Dict) -> Dict:
        """Fusion of all 3 AIs - premium experience"""
        
        # Handle exceptions from gather
        responses = []
        for r in [gemini, gpt, claude]:
            if isinstance(r, Exception):
                continue
            if r.get("success"):
                responses.append(r)
        
        if len(responses) == 0:
            return {"answer": "All AI services unavailable", "error": True, "success": False}
        elif len(responses) == 1:
            return responses[0]
        elif len(responses) == 2:
            return self._merge_two(responses[0], responses[1])
        
        # All 3 valid - use Claude's answer (best quality) but note all 3 used
        claude_resp = claude if isinstance(claude, dict) and claude.get("success") else None
        gpt_resp = gpt if isinstance(gpt, dict) and gpt.get("success") else None
        gemini_resp = gemini if isinstance(gemini, dict) and gemini.get("success") else None
        
        answer = ""
        if claude_resp:
            answer = claude_resp.get("answer", "")
        elif gpt_resp:
            answer = gpt_resp.get("answer", "")
        elif gemini_resp:
            answer = gemini_resp.get("answer", "")
        
        return {
            "answer": answer,
            "provider": "claude" if claude_resp else ("openai" if gpt_resp else "gemini"),
            "providers_used": ["claude", "openai", "gemini"],
            "tokens": sum(r.get("tokens", 0) for r in responses),
            "time": max(r.get("time", 0) for r in responses),
            "success": True
        }
    
    def get_stats(self) -> Dict:
        """Get usage statistics for all providers"""
        return {
            "gemini": self.gemini.get_stats(),
            "openai": self.openai.get_stats(),
            "claude": self.claude.get_stats()
        }


# ============================================================================
# SINGLETON INSTANCE (for import)
# ============================================================================

# Create single instance to be imported
orchestrator = EnhancedOrchestrator()


# ============================================================================
# MAIN SOLVE FUNCTION (Called by router.py)
# ============================================================================

async def solve(
    question: str,
    context: dict,
    user_tier: str = "free",
    **kwargs
) -> Dict[str, Any]:
    """
    Main solve function for router.py compatibility.
    This is what router.py imports and calls.
    
    Args:
        question: The student's question (string)
        context: Dictionary with board, class, subject, chapter, study_mode, etc.
        user_tier: 'free', 'pro', or 'max'
    
    Returns:
        Dictionary with answer, provider info, and metadata
    """
    return await orchestrator.solve(question, context, user_tier, **kwargs)


# Legacy function name support
async def solve_question(question: str, context: Dict, user_tier: str = "free") -> Dict:
    """Legacy function name support"""
    return await orchestrator.solve(question, context, user_tier)
