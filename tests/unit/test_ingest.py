"""Offline unit tests for ingestion: contracts, breaker, router logic [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.ingest.hybrid_router import HybridRouter
from ad_leak_engine.ingest.normalizer import normalize_meta_ad
from ad_leak_engine.ingest.deduplicator import Deduplicator
from ad_leak_engine.self_heal.circuit_breaker import CircuitBreaker, CircuitState
from ad_leak_engine.shared.exceptions import BlockedError
from ad_leak_engine.shared.schemas import RawAd


class MockAdSource:
    """Test double for AbstractAdSource."""

    def __init__(self, ads=None, raise_error=None):
        self._ads = ads or []
        self._raise = raise_error

    def search(self, query, country, max_results=50):
        if self._raise:
            raise self._raise
        yield from self._ads

    def health_check(self):
        return True


def _ad(id="1"):
    return RawAd(id=id, page_id="p1", page_name="Test Page",
                 start_date=datetime.now(timezone.utc), media_type="IMAGE")


def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    assert cb.state == CircuitState.CLOSED
    cb.record_failure(); cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute()


def test_circuit_breaker_half_open_transition():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN


def test_normalizer_produces_rawad():
    raw = {
        "id": "ad_1",
        "page": {"id": "p1", "name": "Test Page"},
        "creation_time": "2026-01-01T00:00:00Z",
        "media_type": "IMAGE",
    }
    ad = normalize_meta_ad(raw, "US")
    assert ad.id == "ad_1"
    assert ad.page_name == "Test Page"
    assert ad.country == "US"


def test_hybrid_router_primary_path():
    router = HybridRouter(graphql=MockAdSource(ads=[_ad("a")]), playwright=MockAdSource())
    ads = list(router.search("x", "US"))
    assert len(ads) == 1
    assert ads[0].id == "a"


def test_hybrid_router_fallback_on_blocked():
    router = HybridRouter(
        graphql=MockAdSource(raise_error=BlockedError("blocked")),
        playwright=MockAdSource(ads=[_ad("b")]),
    )
    ads = list(router.search("x", "US"))
    assert len(ads) == 1
    assert ads[0].id == "b"


def test_deduplicator_filters_correctly():
    dedup = Deduplicator()
    a1 = _ad("1"); a2 = _ad("2"); a1_dup = _ad("1")
    result = dedup.filter_new([a1, a2, a1_dup])
    assert len(result) == 2
