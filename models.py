from __future__ import annotations

from dataclasses import dataclass

from google import genai

from config import GEMINI_API_KEY, GENAI_MODEL


@dataclass
class GeminiClient:
    api_key: str
    model: str = GENAI_MODEL

    def __post_init__(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY / GOOGLE_API_KEY. Set it in Render Environment."
            )
        self.client = genai.Client(api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        # google-genai: https://ai.google.dev/
        resp = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        # SDK returns .text convenience
        text = getattr(resp, "text", None)
        return (text or "").strip()


def get_gemini_client() -> GeminiClient:
    return GeminiClient(api_key=GEMINI_API_KEY, model=GENAI_MODEL)
