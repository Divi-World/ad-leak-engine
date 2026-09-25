"""Meta Ad Library API source — the BULLETPROOF ad-collection path [SEED: 2399].

Uses Meta's official Ad Library API. It is FREE (not a paid API) but requires
a free access token from developers.facebook.com. Far more reliable than
scraping. Configure via META_AD_LIBRARY_TOKEN in .env. The HybridRouter
automatically prefers this source when a token is present.
"""
import os
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..shared.exceptions import BlockedError, EmptyResponseError
from .normalizer import _parse_date

API_URL = "https://graph.facebook.com/v19.0/ads_archive"
FIELDS = ("ad_creative_bodies,ad_creative_link_titles,ad_creative_link_urls,"
          "page_id,page_name,ad_delivery_start_time,ad_snapshot_url,publisher_platforms")


class AdLibraryAPISource(AbstractAdSource):
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.getenv("META_AD_LIBRARY_TOKEN")

    def available(self) -> bool:
        return bool(self.access_token)

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        if not self.available():
            raise EmptyResponseError("No META_AD_LIBRARY_TOKEN configured")
        import httpx

        params = {
            "search_terms": query,
            "ad_reached_countries": f"['{country}']",
            "fields": FIELDS,
            "limit": str(min(max_results, 100)),
            "access_token": self.access_token,
        }
        try:
            resp = httpx.get(API_URL, params=params, timeout=30)
        except Exception as e:
            raise EmptyResponseError(f"API request failed: {e}")

        if resp.status_code == 401 or "Invalid OAuth" in resp.text:
            raise BlockedError("Invalid/expired Ad Library API access token")
        if resp.status_code != 200:
            raise EmptyResponseError(f"API returned status {resp.status_code}")

        for ad in self.parse_api_response(resp.json(), country):
            yield ad

    def parse_api_response(self, data: dict, country: str) -> list[RawAd]:
        ads = []
        for item in data.get("data", []):
            try:
                ads.append(self._map_api_ad(item, country))
            except Exception:
                continue
        return ads

    def _map_api_ad(self, item: dict, country: str) -> RawAd:
        bodies = item.get("ad_creative_bodies") or []
        titles = item.get("ad_creative_link_titles") or []
        urls = item.get("ad_creative_link_urls") or []
        platforms = item.get("publisher_platforms") or []
        return RawAd(
            id=str(item.get("id")),
            page_id=str(item.get("page_id", "unknown")),
            page_name=item.get("page_name", "Unknown"),
            start_date=_parse_date(item.get("ad_delivery_start_time")),
            media_type="IMAGE",
            body=bodies[0] if bodies else None,
            title=titles[0] if titles else None,
            landing_url=urls[0] if urls else None,
            platforms=platforms,
            country=country,
            raw=item,
        )

    def health_check(self) -> bool:
        return self.available()
