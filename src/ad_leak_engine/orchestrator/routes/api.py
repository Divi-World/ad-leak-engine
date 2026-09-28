"""Frontend-facing API routes for Ad-Leak-Engine [SEED: 2399]."""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class ScanRequest(BaseModel):
    keyword: str
    country: str = "US"
    limit: int = 5

@router.post("/scan/trigger")
def trigger_scan(request: ScanRequest) -> dict:
    """
    Trigger a backend scan from the frontend dashboard.
    In Phase 29, this will enqueue the job and return a job_id for polling.
    """
    return {
        "status": "accepted",
        "message": f"Scan initiated for '{request.keyword}' in {request.country}",
        "limit": request.limit,
        "note": "Backend execution queued. WebSocket/Polling integration coming in Phase 29."
    }

@router.get("/scan/status/{job_id}")
def get_scan_status(job_id: str) -> dict:
    """Check the status of a running scan."""
    return {"job_id": job_id, "status": "pending", "progress": 0}

@router.post("/outreach/send")
async def send_outreach(request: dict) -> dict:
    """Dispatch personalized outreach email via Resend."""
    from ...outreach.dispatcher import send_outreach_email
    result = await send_outreach_email(
        to_email=request.get("email", "prospect@example.com"),
        subject=request.get("subject", "Ad Audit"),
        message_text=request.get("message_text", "")
    )
    return result


@router.post("/outreach/send")
async def send_outreach(request: dict) -> dict:
    """Dispatch personalized outreach email via Resend."""
    from ...outreach.dispatcher import send_outreach_email
    result = await send_outreach_email(
        to_email=request.get("email", "prospect@example.com"),
        subject=request.get("subject", "Ad Audit"),
        message_text=request.get("message_text", "")
    )
    return result

