"""Ad persistence repository [SEED: 2399]."""
import json

from sqlmodel import Session

from ..shared.schemas import RawAd
from .db import engine
from .models import AdRecord


class AdRepository:
    def upsert_ads(self, ads: list[RawAd]) -> int:
        """Insert new ads, skip duplicates. Returns count inserted."""
        count = 0
        with Session(engine) as session:
            for ad in ads:
                if session.get(AdRecord, ad.id):
                    continue
                session.add(AdRecord(
                    ad_id=ad.id,
                    page_id=ad.page_id,
                    page_name=ad.page_name,
                    media_type=ad.media_type,
                    landing_url=ad.landing_url,
                    country=ad.country,
                    raw_json=json.dumps(ad.raw, default=str),
                ))
                count += 1
            session.commit()
        return count

    def count_ads(self) -> int:
        with Session(engine) as session:
            return len(session.query(AdRecord).all())
