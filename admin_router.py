from fastapi import APIRouter, Header, HTTPException
import os
import study_store
from seed_loader import load_seed_rows

router = APIRouter()

@router.post("/admin/syllabus/seed")
def seed(reset: int = 0, x_admin_key: str = Header(...)):
    if x_admin_key != os.getenv("ADMIN_API_KEY"):
        raise HTTPException(status_code=401)

    rows = load_seed_rows()

    if reset == 1:
        study_store.reset_syllabus()

    inserted = study_store.seed_syllabus(rows)

    return {
        "ok": True,
        "inserted": inserted,
        "total_rows": len(rows)
    }
