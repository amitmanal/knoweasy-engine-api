"""
KnowEasy Premium - Enhanced AI Orchestrator
CEO Decision: Production-ready multi-AI system
Integrates: Gemini + GPT-4o-mini + Claude Sonnet

This file REPLACES your existing orchestrator.py
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional, List
import httpx
import google.generativeai as genai
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import json


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
    GEMINI_MODEL = "gemini-2.0-flash-exp"  # Fastest for free/simple
    OPENAI_MODEL = "gpt-4o-mini"  # Best value
    CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Best quality
    
    # Timeouts
    TIMEOUT = 25
    
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
    """Google Gemini client"""
    
    def __init__(self):
        super().__init__("gemini")
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        else:
            self.model = None
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask Gemini"""
        if not self.model:
            return {"answer": "", "error": "Gemini not configured"}
        
        try:
            self.calls_made += 1
            start = time.time()
            
            # Combine system + prompt
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            
            # Call Gemini
            response = await asyncio.to_thread(
                self.model.generate_content,
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2000,
                )
            )
            
            answer = response.text
            elapsed = time.time() - start
            
            # Estimate tokens
            tokens = len(full_prompt.split()) + len(answer.split())
            self.tokens_used += tokens
            
            return {
                "answer": answer,
                "provider": "gemini",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
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
        if Config.OPENAI_API_KEY:
            self.client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)
        else:
            self.client = None
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask GPT"""
        if not self.client:
            return {"answer": "", "error": "OpenAI not configured"}
        
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
            
            answer = response.choices[0].message.content
            tokens = response.usage.total_tokens
            elapsed = time.time() - start
            
            self.tokens_used += tokens
            
            return {
                "answer": answer,
                "provider": "openai",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
            return {
                "answer": "",
                "error": str(e),
                "provider": "openai",
                "success": False
            }


class ClaudeClient(AIClient):
    """Anthropic Claude client"""
    
    def __init__(self):
        super().__init__("claude")
        if Config.CLAUDE_API_KEY:
            self.client = AsyncAnthropic(api_key=Config.CLAUDE_API_KEY)
        else:
            self.client = None
    
    async def ask(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Ask Claude"""
        if not self.client:
            return {"answer": "", "error": "Claude not configured"}
        
        try:
            self.calls_made += 1
            start = time.time()
            
            response = await self.client.messages.create(
                model=Config.CLAUDE_MODEL,
                max_tokens=2000,
                system=system if system else "You are a helpful AI tutor.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                timeout=Config.TIMEOUT
            )
            
            answer = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            elapsed = time.time() - start
            
            self.tokens_used += tokens
            
            return {
                "answer": answer,
                "provider": "claude",
                "tokens": tokens,
                "time": elapsed,
                "success": True
            }
            
        except Exception as e:
            self.errors += 1
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
        
        # Context
        if context.get("class"):
            parts.append(f"\nTeaching: Class {context['class']} {context.get('board', 'CBSE').upper()}")
        
        if context.get("subject"):
            parts.append(f"Subject: {context['subject'].title()}")
        
        if context.get("chapter"):
            chapter = context['chapter'].replace('_', ' ').title()
            parts.append(f"Chapter: {chapter}")
        
        # Mode-specific instructions
        study_mode = context.get("study_mode", "chat")
        
        if study_mode == "luma":
            parts.append("\n📚 TEACHING STYLE:")
            parts.append("- Provide structured, step-by-step explanations")
            parts.append("- Break complex concepts into simple parts")
            parts.append("- Use examples relatable to Indian students")
            parts.append("- Encourage and build confidence")
            parts.append("- Add practice questions when appropriate")
        else:
            parts.append("\n💬 CHAT STYLE:")
            parts.append("- Provide direct, helpful answers")
            parts.append("- Be concise but clear")
            parts.append("- Friendly and encouraging tone")
        
        # Language
        language = context.get("language", "en")
        if language == "hi":
            parts.append("\n🇮🇳 भाषा: हिंदी में उत्तर दें जब उपयुक्त हो")
        elif language == "mr":
            parts.append("\n🇮🇳 भाषा: मराठीमध्ये उत्तर द्या")
        
        return "\n".join(parts)
    
    @staticmethod
    def build_user_prompt(question: str, context: Dict[str, Any]) -> str:
        """Build user prompt with lesson context"""
        
        parts = [f"Student's question: {question}"]
        
        # Add visible lesson content if available (Luma mode)
        if context.get("visible_text"):
            visible = context["visible_text"][:600]  # Limit context size
            parts.append(f"\n📖 Current lesson content:\n{visible}")
        
        # Add anchor example if available
        if context.get("anchor_example"):
            example = context["anchor_example"][:300]
            parts.append(f"\n📌 Example from lesson:\n{example}")
        
        return "\n".join(parts)


# ============================================================================
# COMPLEXITY ANALYZER
# ============================================================================

class ComplexityAnalyzer:
    """Determines question complexity for smart routing"""
    
    SIMPLE_TRIGGERS = [
        "what is", "define", "meaning of", "full form",
        "formula for", "value of", "who is", "when was",
        "which is", "where is"
    ]
    
    COMPLEX_TRIGGERS = [
        "explain in detail", "step by step", "derive", "prove",
        "compare and contrast", "analyze", "evaluate",
        "why and how", "reasoning", "solve", "calculate"
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
            if word_count < 10:
                return "simple"
        
        # Complex questions
        if any(trigger in q_lower for trigger in cls.COMPLEX_TRIGGERS):
            return "complex"
        
        # Length-based
        if word_count < 8:
            return "simple"
        elif word_count > 20:
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
        
        # Analyze complexity
        complexity = self.analyzer.analyze(question)
        
        # Build prompts
        system_prompt = self.prompt_builder.build_system_prompt(context)
        user_prompt = self.prompt_builder.build_user_prompt(question, context)
        
        # Route based on tier and complexity
        study_mode = context.get("study_mode", "chat")
        
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
        
        return result
    
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
            except:
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
                except:
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
            except:
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
            except:
                result = await self.claude.ask(prompt, system)
                if not result.get("success"):
                    result = await self.gemini.ask(prompt, system)
                result["ai_strategy"] = "fallback"
        
        result["tier"] = user_tier
        result["premium_formatting"] = True
        return result
    
    def _merge_two(self, resp1: Dict, resp2: Dict) -> Dict:
        """Merge two AI responses - pick better one"""
        
        if not resp1.get("success"):
            return resp2
        if not resp2.get("success"):
            return resp1
        
        # Use longer/more detailed response
        answer1 = resp1.get("answer", "")
        answer2 = resp2.get("answer", "")
        
        if len(answer2) > len(answer1) * 1.2:
            chosen = resp2
            providers = [resp2["provider"], resp1["provider"]]
        else:
            chosen = resp1
            providers = [resp1["provider"], resp2["provider"]]
        
        return {
            "answer": chosen["answer"],
            "providers_used": providers,
            "tokens": resp1.get("tokens", 0) + resp2.get("tokens", 0),
            "time": max(resp1.get("time", 0), resp2.get("time", 0)),
            "success": True
        }
    
    def _fusion_three(self, gemini: Dict, gpt: Dict, claude: Dict) -> Dict:
        """Fusion of all 3 AIs - premium experience"""
        
        valid = [r for r in [gemini, gpt, claude] if r.get("success")]
        
        if len(valid) == 0:
            return {"answer": "All AI services unavailable", "error": True, "success": False}
        elif len(valid) == 1:
            return valid[0]
        elif len(valid) == 2:
            return self._merge_two(valid[0], valid[1])
        
        # All 3 valid - use Claude's answer (best quality) but note all 3 used
        answer = claude.get("answer", "") or gpt.get("answer", "") or gemini.get("answer", "")
        
        return {
            "answer": answer,
            "providers_used": ["claude", "openai", "gemini"],
            "tokens": sum(r.get("tokens", 0) for r in [gemini, gpt, claude]),
            "time": max(r.get("time", 0) for r in [gemini, gpt, claude]),
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
# LEGACY COMPATIBILITY
# ============================================================================

# For backward compatibility with existing code
async def solve_question(question: str, context: Dict, user_tier: str = "free") -> Dict:
    """Legacy function name support"""
    return await orchestrator.solve(question, context, user_tier)
# ============================================================================
# COMPATIBILITY WITH EXISTING ROUTER.PY
# ============================================================================

async def solve(
    question: str,
    context: dict,
    user_tier: str = "free",
    **kwargs
):
    """
    Main solve function for router.py compatibility
    This is what router.py imports and calls
    """
    return await orchestrator.solve(question, context, user_tier, **kwargs)
