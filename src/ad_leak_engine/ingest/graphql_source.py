"""REAL Meta Ad Library ingestion via curl_cffi TLS fingerprinting [SEED: 2399].

Logged-out public data only. Attempts the Ad Library search endpoint with a
Chrome TLS fingerprint. This endpoint is adversarial; on any failure a typed
exception is raised so HybridRouter falls back to Playwright.
"""
from typing import Iterator

from curl_cffi import requests

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..shared.exceptions import BlockedError, RateLimitError, EmptyResponseError
from .normalizer import normalize_meta_ad
try:
    from ..shared.advanced_headers import get_random_headers
except ImportError:
    get_random_headers = None

AD_LIBRARY_SEARCH_URL = "https://www.facebook.com/ads/library/async/search_ads/"


class GraphQLSource(AbstractAdSource):
    def __init__(self, impersonate: str = "chrome120"):
        self.impersonate = impersonate

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        session = requests.Session(impersonate=self.impersonate)
        params = {
            "q": query,
            "country": country,
            "active_status": "active",
            "ad_type": "all",
            "count": str(max_results),
        }
        try:
            headers = get_random_headers() if get_random_headers else {}
            resp = session.get(AD_LIBRARY_SEARCH_URL, params=params, headers=headers, timeout=20)
        except Exception as e:
            raise EmptyResponseError(f"GraphQL request failed: {e}")

        if resp.status_code == 403:
            raise BlockedError("Meta returned 403 (blocked)")
        if resp.status_code == 429:
            raise RateLimitError("Meta returned 429 (rate limited)")
        if resp.status_code != 200:
            raise EmptyResponseError(f"Unexpected status {resp.status_code}")

        try:
            payload = resp.json()
        except Exception:
            raise EmptyResponseError("Response was not valid JSON")

        ads = self._extract(payload, country)
        if not ads:
            raise EmptyResponseError("No ads parsed from GraphQL payload")
        for ad in ads[:max_results]:
            yield ad

    def _extract(self, payload, country):
        ads = []
        self._walk(payload, ads, country)
        return ads

    def _walk(self, node, ads, country):
        if isinstance(node, dict):
            if "id" in node and "page" in node:
                try:
                    ads.append(normalize_meta_ad(node, country))
                except Exception:
                    pass
            for v in node.values():
                self._walk(v, ads, country)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, ads, country)

    def health_check(self) -> bool:
        return True
