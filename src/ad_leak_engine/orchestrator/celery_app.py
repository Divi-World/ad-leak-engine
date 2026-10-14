"""Celery Application Configuration for Ad-Leak-Engine [SEED: 2399]."""
import os
from pathlib import Path
from dotenv import load_dotenv
from celery import Celery

# [SEED: 2399] CRITICAL: Load .env file for the Celery worker process.
# This ensures META_ACCESS_TOKEN and other secrets are available, 
# matching the behavior of the main Uvicorn process and preventing 401 errors.
project_root = Path(__file__).resolve().parents[3]
load_dotenv(project_root / '.env')


redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "ad_leak_engine",
    broker=redis_url,
    backend=redis_url,
    include=["ad_leak_engine.orchestrator.tasks"]
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)
