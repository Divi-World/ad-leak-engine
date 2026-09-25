"""Chaos testing: Resilience under failure [SEED: 2399]."""
import pytest
from ad_leak_engine.self_heal.circuit_breaker import CircuitBreaker, CircuitState
from ad_leak_engine.shared.exceptions import BlockedError, SchemaDriftError, EmptyResponseError
from ad_leak_engine.ingest.hybrid_router import HybridRouter
from ad_leak_engine.shared.schemas import RawAd
from datetime import datetime, timezone

class ChaosSource:
    def __init__(self, error_to_raise=None, ads=None):
        self.error = error_to_raise
        self.ads = ads or []

    def search(self, query, country, max_results=50):
        if self.error:
            raise self.error
        yield from self.ads

    def health_check(self): return True

def _ad(id="1"):
    return RawAd(id=id, page_id="p1", page_name="Test", start_date=datetime.now(timezone.utc), media_type="IMAGE")

def test_chaos_circuit_breaker_opens_and_fallbacks():
    """Simulates primary source failing, forcing circuit open and fallback."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=BlockedError("DataDome Block")),
        playwright=ChaosSource(ads=[_ad("fallback_ad")]),
        breaker=CircuitBreaker(failure_threshold=1, recovery_timeout=60),
    )
    ads = list(router.search("shoes", "US"))
    assert len(ads) == 1
    assert ads[0].id == "fallback_ad"
    assert router.breaker.state == CircuitState.OPEN

def test_chaos_schema_drift_triggers_fallback():
    """Simulates Meta changing GraphQL schema, system must auto-fallback."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=SchemaDriftError("Keys changed")),
        playwright=ChaosSource(ads=[_ad("drift_fallback")]),
        breaker=CircuitBreaker(failure_threshold=1, recovery_timeout=60),
    )
    ads = list(router.search("shoes", "US"))
    assert ads[0].id == "drift_fallback"

def test_chaos_total_system_failure():
    """Simulates both sources failing. Router must not crash, just yield empty."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=EmptyResponseError("Timeout")),
        playwright=ChaosSource(error_to_raise=BlockedError("IP Ban")),
        breaker=CircuitBreaker(failure_threshold=1, recovery_timeout=60),
    )
    ads = list(router.search("shoes", "US"))
    assert len(ads) == 0

def test_chaos_empty_response_triggers_fallback():
    """Simulates GraphQL returning empty/blocked, system falls to Playwright."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=EmptyResponseError("No data")),
        playwright=ChaosSource(ads=[_ad("empty_fallback")]),
        breaker=CircuitBreaker(failure_threshold=1, recovery_timeout=60),
    )
    ads = list(router.search("shoes", "US"))
    assert len(ads) == 1
    assert ads[0].id == "empty_fallback"
