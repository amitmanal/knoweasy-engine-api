import os
import json
import re
import google.generativeai as genai

class GeminiClient:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    def generate_text(self, prompt: str) -> str:
        resp = self.model.generate_content(prompt)
        return (resp.text or "").strip()

    def generate_json(self, prompt: str) -> dict:
        text = self.generate_text(prompt)

        # Direct JSON attempt
        try:
            return json.loads(text)
        except Exception:
            pass

        # Extract first JSON object
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return {}

        return {}
