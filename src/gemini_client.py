import os
import requests

SOLVER_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def gemini_generate(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY_MISSING")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{SOLVER_MODEL}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        }
    }

    r = requests.post(url, json=payload, timeout=25)
    if r.status_code != 200:
        raise RuntimeError(f"GEMINI_HTTP_{r.status_code}: {r.text[:200]}")

    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError("GEMINI_BAD_RESPONSE")
