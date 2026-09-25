from fastapi import APIRouter
router = APIRouter()
@router.get("/leads")
def get_leads(score_min: int = 60):
    return {"status": "query_ready", "score_min": score_min}
