"""Data contracts for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _short_id(prefix: str = "") -> str:
    seed = f"{prefix}{datetime.now(timezone.utc).isoformat()}"
    return hashlib.md5(seed.encode()).hexdigest()[:12]


class RawAd(BaseModel):
    """Canonical ad object flowing from Ingest -> Leak Scan."""
    id: str
    page_id: str
    page_name: str
    start_date: datetime
    end_date: datetime | None = None
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    media_type: Literal["IMAGE", "VIDEO", "CAROUSEL", "DYNAMIC", "UNKNOWN"]
    title: str | None = None
    body: str | None = None
    cta: str | None = None
    landing_url: str | None = None
    impressions: tuple[int, int] | None = None
    spend: tuple[float, float] | None = None
    platforms: list[str] = Field(default_factory=list)
    country: str = "US"
    raw: dict = Field(default_factory=dict)

    @field_validator("landing_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class Page(BaseModel):
    """Page-level aggregate containing all ads for a business."""
    id: str
    name: str
    url: str | None = None
    ads: list[RawAd] = Field(default_factory=list)
    first_seen: datetime
    last_scanned: datetime | None = None
    fingerprint: str | None = None
    # Added raw dict to hold network logs, DOM snapshots, and L3 telemetry
    raw: dict = Field(default_factory=dict)

    @property
    def active_ads(self) -> list[RawAd]:
        return [ad for ad in self.ads if ad.status == "ACTIVE"]

    @property
    def total_estimated_spend(self) -> tuple[float, float]:
        lower = sum(ad.spend[0] for ad in self.active_ads if ad.spend)
        upper = sum(ad.spend[1] for ad in self.active_ads if ad.spend)
        return (lower, upper)


class Leak(BaseModel):
    """A detected revenue leak with evidence and severity."""
    id: str = Field(default_factory=lambda: _short_id("leak_"))
    page_id: str
    tier: Literal["L1", "L2", "L3"]
    signal: str
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    evidence: dict = Field(default_factory=dict)
    recommendation: str
    revenue_impact: str | None = None
    detected_at: datetime = Field(default_factory=_utcnow)


class Fix(BaseModel):
    """Platform-specific implementation guide with executable code."""
    id: str = Field(default_factory=lambda: _short_id("fix_"))
    leak_id: str
    platform: Literal["shopify", "woocommerce", "bigcommerce", "custom"]
    platform_confidence: float
    markdown_guide: str
    code_blocks: list[dict] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    expected_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)


class OutreachPack(BaseModel):
    """Complete client-facing package."""
    page_id: str
    page_name: str
    prospect_url: str | None = None
    teardown_markdown: str
    executive_summary: str
    leaks_found: list[Leak] = Field(default_factory=list)
    fixes: list[Fix] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    message_text: str
    estimated_recovery: str
    generated_at: datetime = Field(default_factory=_utcnow)
