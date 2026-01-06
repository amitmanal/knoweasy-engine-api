import os
import json
import re
import google.generativeai as genai

class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def generate_text(self, prompt: str) -> str:
        resp = self.model.generate_content(prompt)
        return (resp.text or "").strip()

    def generate_json(self, prompt: str) -> dict:
        """
        Forces JSON parsing. If model returns extra text, we try to extract JSON object safely.
        """
        text = self.generate_text(prompt)

        # Try direct JSON first
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try to extract first {...} block
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}

        return {}
