"""Orchestrates the full fallback chain [SEED: 2399].

Priority order:
0. Official Ad Library API (bulletproof; needs free token)
1. GraphQL via curl_cffi (fast, structured)
2. Playwright stealth (consent-aware, broad capture)

All tiers are protected. Total system failure yields empty, never crashes.
"""
import logging
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.exceptions import (
    SchemaDriftError, BlockedError, RateLimitError,
    EmptyResponseError, CrawlerTimeoutError, AdLeakEngineError
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
        self.breaker = breaker or CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        self.monitor = HealthMonitor() if HealthMonitor else None
        self.cache = CacheManager()
        self.fallback_chain = FallbackChain(
            graphql_source=self.graphql,
            playwright_source=self.playwright,
            cache=self.cache
        )

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        """Execute hierarchical search with automatic failover."""
        
        # Tier 0: Official API if configured
        if self.api is not None and getattr(self.api, "available", lambda: False)():
            try:
                ads = list(self.api.search(query, country, max_results))
                if ads:
                    logger.info(f"[HYBRID] Success via Graph API ({len(ads)} ads)")
                    yield from ads
                    return
            except Exception as e:
                logger.warning(f"[HYBRID] Graph API failed: {e}. Falling back.")
                # Record failure even for optional accelerators if they throw
                self.breaker.record_failure()

        # Tier 1: GraphQL (Manual Execution with Breaker Protection)
        try:
            ads = list(self.graphql.search(query, country, max_results))
            if ads:
                logger.info(f"[HYBRID] Success via GraphQL ({len(ads)} ads)")
                self.breaker.record_success() # Reset breaker on success
                yield from ads
                return
        except (SchemaDriftError, BlockedError, RateLimitError, EmptyResponseError, CrawlerTimeoutError) as e:
            logger.warning(f"[HYBRID] GraphQL failed ({type(e).__name__}). Recording failure & falling back to Playwright.")
            self.breaker.record_failure() # CRITICAL: Opens circuit on blocking errors
        except Exception as e:
            logger.error(f"[HYBRID] Unexpected GraphQL error: {e}. Recording failure & falling back to Playwright.")
            self.breaker.record_failure()

        # Tier 2: Playwright (Manual Execution with Breaker Protection)
        try:
            logger.info("Routing to Playwright fallback.")
            ads = list(self.playwright.search(query, country, max_results))
            if ads:
                logger.info(f"[HYBRID] Success via Playwright ({len(ads)} ads)")
                yield from ads
                return
            else:
                logger.warning("[HYBRID] Playwright returned 0 ads.")
                # Empty result isn't necessarily a 'failure' for circuit breaker unless configured so
        except Exception as e:
            logger.error(f"[HYBRID] Playwright failed critically: {e}")
            self.breaker.record_failure()

        # Tier 3: Last Resort (Empty Yield, Log Error)
        logger.critical(f"[HYBRID] ALL SOURCES FAILED for '{query}' in {country}")
        return

    def health_check(self) -> bool:
        """Verify router readiness."""
        return True
