from fastapi import APIRouter
router = APIRouter()
@router.post("/scan")
def scan(keyword: str, country: str = "US", limit: int = 10):
    return {"status": "dispatched", "keyword": keyword, "limit": limit}
