from fastapi import APIRouter
import study_store

router = APIRouter()

@router.get("/api/syllabus")
def syllabus(track: str,
             program: str,
             class_level: int,
             subject_code: str):

    items = study_store.get_syllabus(
        track, program, class_level, subject_code
    )

    return {
        "ok": True,
        "items": items
    }
