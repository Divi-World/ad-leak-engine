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

    # --- HYBRID TIMEOUT GUARDS (INDUSTRIAL GRADE - ADJUSTED) ---
    # Increased limits to accommodate heavy Playwright launches on Windows.
    # Direct Mode: ~60-120s typical. Niche Mode: Can take 5-10 mins per batch.
    
    # Soft limit: Warns task at 300s (5 mins) - allows graceful logging
    task_soft_time_limit=300,

    # Hard limit: Kills task at 360s (6 mins) - prevents infinite hang/zombies
    task_time_limit=360,

    # --- TRACKING ---
    task_track_started=True,
    
    # --- BROKER RESILIENCE ---
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 360, # Must match task_time_limit
    }
)