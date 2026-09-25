"""SQLModel ORM tables for Ad-Leak-Engine [SEED: 2399]."""
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow():
    return datetime.now(timezone.utc)


class AdRecord(SQLModel, table=True):
    ad_id: str = Field(primary_key=True)
    page_id: str = Field(index=True)
    page_name: str
    media_type: str
    landing_url: str | None = None
    country: str
    raw_json: str
    collected_at: datetime = Field(default_factory=_utcnow)
