from fastapi import APIRouter
router = APIRouter()
@router.post("/feedback/reply")
def log_reply(page_id: str, message: str):
    return {"status": "logged", "page_id": page_id}
