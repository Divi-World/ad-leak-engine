"""FastAPI orchestrator for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from ..shared.constants import ENGINE_NAME, ENGINE_VERSION, SEED_NUMBER
from .routes import scan, leads, feedback

app = FastAPI(
    title=ENGINE_NAME,
    version=ENGINE_VERSION,
    description=f"Top 1 Global Ad Infrastructure Audit Engine [SEED: {SEED_NUMBER}]",
)

app.include_router(scan.router)
app.include_router(leads.router)
app.include_router(feedback.router)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Must return SEED: 2399."""
    return {
        "status": "healthy",
        "engine": ENGINE_NAME,
        "seed": SEED_NUMBER,
        "version": ENGINE_VERSION,
        "phase": "0-foundation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
