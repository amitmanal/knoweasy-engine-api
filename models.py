import json
from google import genai
from config import GEMINI_API_KEY, GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL

class GeminiClient:
    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is missing. Set it in Render env vars.")
        self.client = genai.Client(api_key=GEMINI_API_KEY)

    def generate_json(self, prompt: str, model: str | None = None) -> dict:
        use_model = model or GEMINI_PRIMARY_MODEL
        resp = self.client.models.generate_content(
            model=use_model,
            contents=prompt,
        )
        text = (resp.text or "").strip()

        # Hard defense: extract JSON if the model wraps it.
        # We look for first '{' and last '}'.
        if "{" in text and "}" in text:
            text = text[text.find("{"):text.rfind("}") + 1]

        try:
            return json.loads(text)
        except Exception:
            # fallback model attempt
            if use_model != GEMINI_FALLBACK_MODEL:
                resp2 = self.client.models.generate_content(
                    model=GEMINI_FALLBACK_MODEL,
                    contents=prompt,
                )
                text2 = (resp2.text or "").strip()
                if "{" in text2 and "}" in text2:
                    text2 = text2[text2.find("{"):text2.rfind("}") + 1]
                return json.loads(text2)
            raise
