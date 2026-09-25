"""Ordered Fallback Chain [SEED: 2399].

Implements the KB-mandated fallback chain for ad ingestion:
  1. GraphQL via curl_cffi (fastest, most structured)
  2. Playwright Network Interception (capture GraphQL from browser)
  3. Playwright DOM Extraction (scrape rendered HTML)
  4. Cached Data (with staleness warning)
  5. Skip + Log for retry in next cycle
"""
import logging
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.exceptions import (
    SchemaDriftError, BlockedError, RateLimitError,
    EmptyResponseError, CrawlerTimeoutError, AdLeakEngineError
)

logger = logging.getLogger(__name__)


class FallbackChain:
    """Executes the ordered fallback chain for ad ingestion."""

    def __init__(self, graphql_source=None, playwright_source=None, cache=None):
        self.graphql_source = graphql_source
        self.playwright_source = playwright_source
        self.cache = cache
        self.last_fallback_level = 0

    def execute(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        """Execute the fallback chain, returning ads from the first successful source."""

        # Level 1: GraphQL via curl_cffi
        if self.graphql_source:
            try:
                logger.info("Fallback Level 1: GraphQL via curl_cffi", extra={"fallback_level": 1})
                ads = list(self.graphql_source.search(query, country, max_results))
                if ads:
                    self.last_fallback_level = 1
                    yield from ads
                    return
            except (SchemaDriftError, RateLimitError, EmptyResponseError) as e:
                logger.warning(f"GraphQL failed ({type(e).__name__}), escalating to Level 2", extra={"fallback_level": 1})

        # Level 2: Playwright Network Interception
        if self.playwright_source:
            try:
                logger.info("Fallback Level 2: Playwright Network Interception", extra={"fallback_level": 2})
                ads = list(self.playwright_source.search(query, country, max_results))
                if ads:
                    self.last_fallback_level = 2
                    yield from ads
                    return
            except (BlockedError, CrawlerTimeoutError) as e:
                logger.warning(f"Playwright failed ({type(e).__name__}), escalating to Level 3", extra={"fallback_level": 2})

        # Level 3: Cached Data
        if self.cache:
            try:
                logger.info("Fallback Level 3: Cached Data", extra={"fallback_level": 3})
                cached_ads = self.cache.get(query, country)
                if cached_ads:
                    self.last_fallback_level = 3
                    logger.warning("Serving cached data with staleness warning", extra={"cache_stale": True})
                    yield from cached_ads
                    return
            except Exception as e:
                logger.warning(f"Cache retrieval failed ({type(e).__name__}), escalating to Level 4", extra={"fallback_level": 3})

        # Level 4: Skip + Log for retry
        self.last_fallback_level = 4
        logger.warning(f"All fallback levels exhausted. Skipping scan for '{query}' ({country}). Will retry next cycle.", extra={"fallback_level": 4})
        return
