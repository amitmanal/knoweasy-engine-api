import os
import json
import requests

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
SOLVER_MODEL = os.getenv("GEMINI_SOLVER_MODEL", "gemini-2.5-flash").strip()
VERIFIER_MODEL = os.getenv("GEMINI_VERIFIER_MODEL", "gemini-2.5-flash-lite").strip()

def _endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"

def gemini_generate(model: str, text: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing in environment.")

    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.9,
            "maxOutputTokens": 900
        }
    }

    r = requests.post(_endpoint(model), json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini API error {r.status_code}: {r.text}")

    data = r.json()
    # Extract first candidate text
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(data)[:1000]}")
