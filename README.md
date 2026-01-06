# KnowEasy Engine API (Phase-1 Clean)

FastAPI backend service for KnowEasy OS Phase-1.
- `/health` : service health
- `/solve`  : main orchestration endpoint (Gemini-backed, safe guards, verified output)

## Local run
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
set GEMINI_API_KEY=your_key
uvicorn main:app --reload --port 8000
```

## Render
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Set env var: `GEMINI_API_KEY`


## Env
- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional, default `gemini-2.5-flash`)
- `GEMINI_API_VERSION` (optional, default `v1`)

## Endpoints
- `GET /health`
- `POST /solve`
