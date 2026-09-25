"""Tests for the Ad Library API source + API-first routing [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.ingest.api_source import AdLibraryAPISource
from ad_leak_engine.ingest.hybrid_router import HybridRouter
from ad_leak_engine.shared.schemas import RawAd

SAMPLE_API_RESPONSE = {
    "data": [
        {
            "id": "98765",
            "page_id": "p1",
            "page_name": "API Store",
            "ad_creative_bodies": ["Best shoes ever"],
            "ad_creative_link_titles": ["Buy Shoes"],
            "ad_creative_link_urls": ["https://apistore.com"],
            "ad_delivery_start_time": "2026-01-15",
            "publisher_platforms": ["facebook", "instagram"],
        }
    ]
}


class MockAPISource:
    def __init__(self, ads):
        self._ads = ads

    def available(self):
        return True

    def search(self, query, country, max_results=50):
        yield from self._ads


class MockAdSource:
    def __init__(self, ads=None):
        self._ads = ads or []

    def search(self, query, country, max_results=50):
        yield from self._ads

    def health_check(self):
        return True


def _ad(id="1"):
    return RawAd(id=id, page_id="p1", page_name="Test",
                 start_date=datetime.now(timezone.utc), media_type="IMAGE")


def test_api_source_maps_response():
    src = AdLibraryAPISource(access_token="fake")
    ads = src.parse_api_response(SAMPLE_API_RESPONSE, "US")
    assert len(ads) == 1
    assert ads[0].page_name == "API Store"
    assert ads[0].body == "Best shoes ever"
    assert ads[0].landing_url == "https://apistore.com"
    assert ads[0].id == "98765"


def test_api_source_available_with_token():
    src = AdLibraryAPISource(access_token="abc")
    assert src.available() is True


def test_api_source_unavailable_without_token(monkeypatch):
    monkeypatch.delenv("META_AD_LIBRARY_TOKEN", raising=False)
    src = AdLibraryAPISource(access_token=None)
    assert src.available() is False


def test_hybrid_router_prefers_api():
    router = HybridRouter(
        graphql=MockAdSource(ads=[_ad("g")]),
        playwright=MockAdSource(),
        api=MockAPISource([_ad("api")]),
    )
    ads = list(router.search("x", "US"))
    assert len(ads) == 1
    assert ads[0].id == "api"
