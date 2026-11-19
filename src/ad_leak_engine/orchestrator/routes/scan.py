from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid, os, json

from ..tasks import run_scan_pipeline_task

router = APIRouter()


class ScanBody(BaseModel):
    keyword: str = ""
    country: str = "US"
    limit: int = 10
    direct_url: Optional[str] = None
    page_id: Optional[str] = None


@router.post("/scan")
def scan(body: ScanBody):
    """[SEED:2399] Real dispatch. Previously returned a fake 'dispatched'."""
    job_id = str(uuid.uuid4())
    os.makedirs(f"output/{job_id}", exist_ok=True)
    with open(f"output/{job_id}/status.json", "w", encoding="utf-8") as f:
        json.dump({"status": "pending", "progress": 0, "job_id": job_id}, f)
    task = run_scan_pipeline_task.delay(
        job_id, body.keyword, body.country, body.limit, body.direct_url, body.page_id
    )
    with open(f"output/{job_id}/status.json", "w", encoding="utf-8") as f:
        json.dump({"status": "queued", "progress": 5, "job_id": job_id,
                   "celery_task_id": str(getattr(task, "id", ""))}, f)
    return {"status": "accepted", "job_id": job_id,
            "celery_task_id": str(getattr(task, "id", "")),
            "mode": "direct" if (body.direct_url or body.page_id) else "niche"}
