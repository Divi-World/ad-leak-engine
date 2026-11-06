"""Celery Application Configuration for Ad-Leak-Engine [SEED: 2399]."""
import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# [SEED: 2399] Namespace consistency guard:
_tasks_module = f"{__package__}.tasks" if __package__ else "ad_leak_engine.orchestrator.tasks"

app = Celery(
    "ad_leak_engine",
    broker=redis_url,
    backend=redis_url,
    include=[_tasks_module]
)

app.conf.update(
    # --- SERIALIZATION & TIMEZONE ---
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # --- RELIABILITY & ACKNOWLEDGMENT ---
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # --- HYBRID TIMEOUT GUARDS (INDUSTRIAL GRADE) ---
    # Niche Mode (Scraping) can take up to 3 minutes. 
    # Direct Mode relies on INTERNAL code timeouts (concurrent.futures) to finish in <10s.
    # Therefore, the GLOBAL Celery limit must be high enough for Niche, 
    # but low enough to prevent zombie processes.
    
    # Soft limit: Warns task at 170s (allows graceful shutdown/logging)
    task_soft_time_limit=170,
    
    # Hard limit: Kills task at 180s (prevents infinite hang)
    task_time_limit=180,

    # --- TRACKING ---
    task_track_started=True,
)