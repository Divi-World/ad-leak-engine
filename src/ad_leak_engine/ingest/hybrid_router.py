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
import time
from ..self_heal.circuit_breaker import CircuitBreaker
from ..self_heal.retry_policy import get_backoff
from ..self_heal.fallback_chain import FallbackChain
from ..persistence.cache import CacheManager
from .graphql_source import GraphQLSource
from .playwright_source import PlaywrightSource
try:
    from ..self_heal.health_monitor import HealthMonitor
except ImportError:
    HealthMonitor = None

logger = logging.getLogger(__name__)


class HybridRouter:
    def __init__(self, graphql=None, playwright=None, breaker=None, api=None):
        self.api = api
        self.graphql = graphql or GraphQLSource()
        self.playwright = playwright or PlaywrightSource()
        self.breaker = breaker or CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        self.monitor = HealthMonitor() if HealthMonitor else None
        self.cache = CacheManager()
        self.fallback_chain = FallbackChain(graphql_source=self.graphql, playwright_source=self.playwright, cache=self.cache)

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
                if self.monitor: self.monitor.log_fallback()
                backoff = get_backoff(type(e).__name__, 1)
                logger.info(f"Applying retry backoff: {backoff:.1f}s")
                time.sleep(min(backoff, 2.0))

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
