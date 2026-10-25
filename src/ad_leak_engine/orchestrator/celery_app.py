"""Celery Application Configuration for Ad-Leak-Engine [SEED: 2399]."""
import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# [SEED: 2399] Namespace consistency guard:
# Load tasks from the same package namespace that loaded this Celery app.
# This prevents mixed src.ad_leak_engine / ad_leak_engine duplicate module state.
_tasks_module = f"{__package__}.tasks" if __package__ else "ad_leak_engine.orchestrator.tasks"

app = Celery(
    "ad_leak_engine",
    broker=redis_url,
    backend=redis_url,
    include=[_tasks_module]
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
