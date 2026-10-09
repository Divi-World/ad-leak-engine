"""Celery Tasks for Ad-Leak-Engine [SEED: 2399]."""
from .celery_app import app

@app.task(bind=True, name="ad_leak_engine.run_scan_pipeline")
def run_scan_pipeline_task(self, job_id: str, keyword: str, country: str, limit: int):
    from .routes.api import run_scan_pipeline
    try:
        run_scan_pipeline(job_id, keyword, country, limit)
        return {"status": "completed", "job_id": job_id}
    except Exception as e:
        import json
        from pathlib import Path
        status_file = Path(f"output/{job_id}/status.json")
        status_file.parent.mkdir(parents=True, exist_ok=True)
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "message": str(e)}, f)
        return {"status": "error", "job_id": job_id, "error": str(e)}
