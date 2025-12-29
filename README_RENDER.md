# Deploy on Render (simple)

## Build & Start
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Test after deploy
Open these in browser:
- `/health` should show `{ ok: true ... }`
- `/docs` should open Swagger UI

## Endpoints
- `POST /solve` body:
```json
{ "question": "Predict the major product when 2-bromopropane reacts with alcoholic KOH." }
```
