"""FastAPI orchestrator for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..shared.constants import ENGINE_NAME, ENGINE_VERSION, SEED_NUMBER
from .routes import scan, leads, feedback, api, oauth

app = FastAPI(
    title=ENGINE_NAME,
    version=ENGINE_VERSION,
    description=f"Top 1 Global Ad Infrastructure Audit Engine [SEED: {SEED_NUMBER}]",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permissive for DevTunnels & Localhost
    allow_credentials=True,
    allow_methods=["*"],  # Explicitly allows OPTIONS preflight
    allow_headers=["*"],  # Explicitly allows X-API-Key and Content-Type
)

# Top 1 Global CORS Configuration for Frontend Integration

app.include_router(scan.router)
app.include_router(leads.router)
app.include_router(feedback.router)
app.include_router(api.router, prefix="/api/v1", tags=["Frontend API"])
app.include_router(oauth.router, prefix="/api/v1/auth", tags=["OAuth"])


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
