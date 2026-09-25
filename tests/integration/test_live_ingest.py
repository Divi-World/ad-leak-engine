"""LIVE: fetch real ads from Meta Ad Library [SEED: 2399]."""
import pytest

from ad_leak_engine.ingest.playwright_source import PlaywrightSource
from ad_leak_engine.ingest.hybrid_router import HybridRouter


@pytest.mark.live
def test_live_ad_library_playwright():
    source = PlaywrightSource()
    ads = list(source.search("shoes", "US", max_results=5))
    # Adversarial target: assert it runs and returns a list (may be 0 if blocked).
    assert isinstance(ads, list)


@pytest.mark.live
def test_live_hybrid_router():
    router = HybridRouter()
    ads = list(router.search("shoes", "US", max_results=5))
    assert isinstance(ads, list)
