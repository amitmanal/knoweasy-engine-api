# KnowEasy Engine API (Render-ready)

FastAPI wrapper around the deterministic KnowEasy Engine (`src/`).

## Quick deploy settings (Render)
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Endpoints
- `GET /health`
- `POST /solve`

## Local run
```bash
pip install -r requirements.txt
uvicorn main:app --reload
```
