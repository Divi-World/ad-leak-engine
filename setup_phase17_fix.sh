#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 17 FIX
# Fixes chaos test failures: breaker threshold + error catching
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 17 FIX"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Fix hybrid_router.py — catch EmptyResponseError + protect Playwright fallback
cat << 'EOF' > src/ad_leak_engine/ingest/hybrid_router.py
"""Orchestrates the full fallback chain [SEED: 2399].

Priority order:
  0. Official Ad Library API  (bulletproof; needs free token)
  1. GraphQL via curl_cffi    (fast, structured)
  2. Playwright stealth       (consent-aware, broad capture)

All tiers are protected. Total system failure yields empty, never crashes.
"""
import logging
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.exceptions import (
    SchemaDriftError, BlockedError, RateLimitError,
    EmptyResponseError, AdLeakEngineError
)
from ..self_heal.circuit_breaker import CircuitBreaker
from .graphql_source import GraphQLSource
from .playwright_source import PlaywrightSource

logger = logging.getLogger(__name__)


class HybridRouter:
    def __init__(self, graphql=None, playwright=None, breaker=None, api=None):
        self.api = api
        self.graphql = graphql or GraphQLSource()
        self.playwright = playwright or PlaywrightSource()
        self.breaker = breaker or CircuitBreaker(failure_threshold=3, recovery_timeout=60)

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        # Tier 0: Official API if configured
        if self.api is not None and getattr(self.api, "available", lambda: False)():
            try:
                ads = list(self.api.search(query, country, max_results))
                if ads:
                    yield from ads
                    return
            except Exception:
                logger.warning("Ad Library API failed; falling back to scraping.")

        # Tier 1: GraphQL
        if self.breaker.can_execute():
            try:
                ads = list(self.graphql.search(query, country, max_results))
                self.breaker.record_success()
                yield from ads
                return
            except (SchemaDriftError, BlockedError, RateLimitError, EmptyResponseError) as e:
                logger.warning("GraphQL failed (%s), engaging fallback.", type(e).__name__)
                self.breaker.record_failure()

        # Tier 2: Playwright (protected — never crashes the pipeline)
        logger.info("Routing to Playwright fallback.")
        try:
            yield from self.playwright.search(query, country, max_results)
        except AdLeakEngineError as e:
            logger.error("Playwright fallback also failed (%s). Yielding empty.", type(e).__name__)
            return
        except Exception as e:
            logger.error("Unexpected Playwright error (%s). Yielding empty.", type(e).__name__)
            return
EOF

# 2. Fix test_chaos.py — proper breaker threshold + error types
cat << 'EOF' > tests/integration/test_chaos.py
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
EOF

# 3. Run the fixed chaos tests
echo "[SEED:2399] Running fixed Chaos test suite..."
python -m pytest tests/integration/test_chaos.py -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 17 FIX COMPLETE"
echo "  Chaos tests fixed. Router is now bulletproof."
echo ""
echo "  RUN FULL SUITE TO CONFIRM:"
echo "  ./scripts/ale test"
echo "=========================================================="