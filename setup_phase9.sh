#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 9: QUALITY AD PULL
# Diagnostic + hardened scraper + bulletproof API source
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 9 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ============================================================
# 1. RICH DIAGNOSTIC — reveals exactly why 0 ads
# ============================================================
cat << 'EOF' > scripts/diagnose_ingest.py
"""Rich diagnostic: reveals exactly what Meta serves and why ads do/don't extract [SEED: 2399]."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from playwright.sync_api import sync_playwright

from ad_leak_engine.ingest.field_mapper import AdLibraryFieldMapper

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CONSENT_SELECTORS = [
    'button:has-text("Allow all")',
    'button:has-text("Allow")',
    '[data-cookiebanner="accept_button"]',
    'button:has-text("Only allow essential cookies")',
    'button:has-text("Accept")',
    'button:has-text("Decline optional")',
]


def dismiss_consent(page):
    for sel in CONSENT_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.click()
                return True
        except Exception:
            continue
    return False


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "shoes"
    country = sys.argv[2] if len(sys.argv) > 2 else "US"
    url = ("https://www.facebook.com/ads/library/?active_status=active"
           f"&ad_type=all&country={country}&q={keyword}&search_type=keyword_unordered")

    print(f"[DIAG] Target: {url}")
    json_payloads = []
    response_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent=DESKTOP_UA, viewport={"width": 1366, "height": 900}, locale="en-US")
        context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = context.new_page()

        def on_response(response):
            nonlocal response_count
            response_count += 1
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "javascript" in ct:
                    json_payloads.append(response.json())
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(6000)

        consent = dismiss_consent(page)
        if consent:
            print("[DIAG] Consent dialog dismissed; waiting for results to load...")
            page.wait_for_timeout(5000)
            for _ in range(3):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(2000)

        final_url = page.url
        title = page.title()
        dom_ad_cards = 0
        for sel in ['[data-pagelet]', 'a[href*="/ads/library/?id="]', 'div[class*="x1ja2uzv"]']:
            try:
                dom_ad_cards = max(dom_ad_cards, page.locator(sel).count())
            except Exception:
                pass

        browser.close()

    print(f"[DIAG] Final URL: {final_url}")
    print(f"[DIAG] Page title: {title}")
    print(f"[DIAG] Consent dismissed: {consent}")
    print(f"[DIAG] Total network responses: {response_count}")
    print(f"[DIAG] JSON/JS payloads captured: {len(json_payloads)}")
    print(f"[DIAG] DOM ad-card-like elements: {dom_ad_cards}")

    mapper = AdLibraryFieldMapper()
    total_ads = 0
    for i, pl in enumerate(json_payloads[:15]):
        ads = mapper.extract_ads(pl, country)
        total_ads += len(ads)
        keys = list(pl.keys())[:6] if isinstance(pl, dict) else "(list)"
        print(f"[DIAG] Payload {i}: keys={keys} ads_found={len(ads)}")

    print(f"[DIAG] TOTAL ADS EXTRACTED: {total_ads}")

    dump_dir = Path("data/debug/payloads")
    dump_dir.mkdir(parents=True, exist_ok=True)
    for i, pl in enumerate(json_payloads[:10]):
        (dump_dir / f"diag_{i}.json").write_text(json.dumps(pl, indent=2, default=str), encoding="utf-8")
    print(f"[DIAG] Dumped {min(len(json_payloads), 10)} payloads to {dump_dir}/")

    low = final_url.lower()
    if "login" in low or "checkpoint" in low:
        print("[DIAG] VERDICT: Redirected to login/checkpoint -> Meta blocked headless access.")
    elif total_ads > 0:
        print(f"[DIAG] VERDICT: SUCCESS -> {total_ads} ads are extractable.")
    elif consent and total_ads == 0:
        print("[DIAG] VERDICT: Consent handled but 0 ads parsed -> inspect dumped payloads for Meta's schema.")
    elif len(json_payloads) == 0:
        print("[DIAG] VERDICT: No JSON intercepted -> consent wall or block page was served.")
    else:
        print("[DIAG] VERDICT: Payloads captured but none matched -> field_mapper needs schema tuning.")


if __name__ == "__main__":
    main()
EOF

# ============================================================
# 2. HARDENED PLAYWRIGHT SCRAPER (consent + stealth + broad capture)
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HARDENED Meta Ad Library scraper [SEED: 2399].

Improvements over the base scraper:
  - Consent-dialog dismissal (the most common blocker)
  - navigator.webdriver stealth removal
  - Broad JSON response capture (not URL-filtered)
  - Schema-drift-tolerant field mapping
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from playwright.sync_api import sync_playwright

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from .field_mapper import AdLibraryFieldMapper

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

CONSENT_SELECTORS = [
    'button:has-text("Allow all")',
    'button:has-text("Allow")',
    '[data-cookiebanner="accept_button"]',
    'button:has-text("Only allow essential cookies")',
    'button:has-text("Accept")',
    'button:has-text("Decline optional")',
]


class PlaywrightSource(AbstractAdSource):
    def __init__(self, debug_dir: str | None = None):
        self.debug_dir = debug_dir
        self.field_mapper = AdLibraryFieldMapper()

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        payloads = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
                context = browser.new_context(
                    user_agent=DESKTOP_UA,
                    viewport={"width": 1366, "height": 900},
                    locale="en-US",
                )
                context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
                page = context.new_page()

                def on_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "javascript" in ct:
                            payloads.append(response.json())
                    except Exception:
                        pass

                page.on("response", on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(6000)

                if self._dismiss_consent(page):
                    page.wait_for_timeout(4000)

                for _ in range(3):
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(2000)

                browser.close()
        except Exception:
            return

        if self.debug_dir:
            self._dump_payloads(payloads)

        seen = set()
        count = 0
        for payload in payloads:
            for ad in self.field_mapper.extract_ads(payload, country):
                if ad.id not in seen:
                    seen.add(ad.id)
                    yield ad
                    count += 1
                    if count >= max_results:
                        return

    def _dismiss_consent(self, page) -> bool:
        for sel in CONSENT_SELECTORS:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    loc.click()
                    return True
            except Exception:
                continue
        return False

    def _dump_payloads(self, payloads):
        d = Path(self.debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        stamp = int(datetime.now(timezone.utc).timestamp())
        for i, p in enumerate(payloads):
            (d / f"payload_{stamp}_{i}.json").write_text(
                json.dumps(p, indent=2, default=str), encoding="utf-8"
            )

    def health_check(self) -> bool:
        return True
EOF

# ============================================================
# 3. BULLETPROOF API SOURCE (free official Ad Library API)
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/api_source.py
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
EOF

# ============================================================
# 4. HYBRID ROUTER — API-first when token present
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/hybrid_router.py
"""Orchestrates the full fallback chain [SEED: 2399].

Priority order:
  0. Official Ad Library API  (bulletproof; needs free token)
  1. GraphQL via curl_cffi    (fast, structured)
  2. Playwright stealth       (consent-aware, broad capture)
"""
import logging
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.exceptions import SchemaDriftError, BlockedError, RateLimitError
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
            except (SchemaDriftError, BlockedError, RateLimitError) as e:
                logger.warning("GraphQL failed (%s), engaging fallback.", type(e).__name__)
                self.breaker.record_failure()

        # Tier 2: Playwright
        logger.info("Routing to Playwright fallback.")
        yield from self.playwright.search(query, country, max_results)
EOF

# ============================================================
# 5. .env.example — add API token slot
# ============================================================
cat << 'EOF' > .env.example
SEED_NUMBER=2399
ENVIRONMENT=development
DB_PATH=data/db/adleak.db
CACHE_DIR=data/cache
LOG_DIR=logs
OUTPUT_DIR=output
LOG_LEVEL=INFO
# Meta Ad Library API — FREE token from developers.facebook.com (enables bulletproof ingestion)
META_AD_LIBRARY_TOKEN=
EOF

# ============================================================
# 6. TESTS
# ============================================================
cat << 'EOF' > tests/unit/test_api_source.py
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
EOF

# ============================================================
# 7. RUN OFFLINE TESTS
# ============================================================
echo "[SEED:2399] Running Phase 9 offline test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 9 COMPLETE"
echo "  Diagnostic + hardened scraper + bulletproof API installed."
echo ""
echo "  NEXT — run the diagnostic and PASTE THE [DIAG] OUTPUT:"
echo "    python scripts/diagnose_ingest.py shoes US"
echo "=========================================================="