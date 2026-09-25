#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 12: REAL PROSPECT EXTRACTION
# HTML ad extraction + self-healing scraper + full live pipeline CLI
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 12 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ============================================================
# 1. HtmlAdExtractor — string-aware balanced-brace JSON parser
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/html_extractor.py
"""HTML ad extractor for Meta Ad Library [SEED: 2399].

Meta embeds the full ad dataset as JSON inside the hydrated SPA HTML
(Relay cache / require() calls). This extractor pulls those JSON objects
out using a string-aware balanced-brace scanner, so braces inside string
values do not break parsing. This is the self-healing 'DOM extraction'
fallback tier that runs when network interception misses the payloads.
"""
from __future__ import annotations

import json

from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad

AD_MARKER = '"ad_archive_id"'
MAX_CANDIDATE_LEN = 1_000_000  # reject runaway matches
MAX_BACKWARD_SEARCH = 60       # bounded brace search


class HtmlAdExtractor:
    """Extracts full ad objects from raw Ad Library HTML."""

    def extract_ads(self, html: str, country: str) -> list[RawAd]:
        if not html:
            return []
        ads_by_id: dict[str, RawAd] = {}
        search_from = 0
        while True:
            pos = html.find(AD_MARKER, search_from)
            if pos == -1:
                break
            obj = self._extract_object_around(html, pos)
            if obj is not None:
                try:
                    ad = normalize_meta_ad(obj, country)
                    if ad.id != "unknown" and ad.id not in ads_by_id:
                        ads_by_id[ad.id] = ad
                except Exception:
                    pass
            search_from = pos + len(AD_MARKER)
        return list(ads_by_id.values())

    def _extract_object_around(self, html: str, marker_pos: int) -> dict | None:
        """Walk outward from the marker to find the enclosing JSON object."""
        brace_pos = marker_pos
        for _ in range(MAX_BACKWARD_SEARCH):
            brace_pos = html.rfind("{", 0, brace_pos)
            if brace_pos == -1:
                return None
            end = self._match_brace(html, brace_pos)
            if end == -1:
                continue
            candidate = html[brace_pos:end + 1]
            if len(candidate) > MAX_CANDIDATE_LEN or len(candidate) < 40:
                continue
            try:
                obj = json.loads(candidate)
            except Exception:
                continue
            if isinstance(obj, dict) and self._looks_like_ad(obj):
                return obj
        return None

    @staticmethod
    def _match_brace(html: str, start: int) -> int:
        """Forward scan to the matching '}', correctly ignoring braces in strings."""
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(html)):
            c = html[i]
            if in_str:
                if escape:
                    escape = False
                elif c == "\\":
                    escape = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return i
        return -1

    @staticmethod
    def _looks_like_ad(node: dict) -> bool:
        has_id = any(k in node for k in ("ad_archive_id", "id", "ad_id"))
        has_hint = any(k in node for k in ("snapshot", "page", "ad_delivery_start_time"))
        return has_id and has_hint
EOF

# ============================================================
# 2. Self-healing PlaywrightSource — merge network + HTML extraction
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HUMAN-GRADE, SELF-HEALING Meta Ad Library scraper [SEED: 2399].

Uses camoufox (stealth Firefox) with session priming + human behavior.
Extracts ads from TWO independent paths and merges them:
  1. Network-intercepted GraphQL/JSON payloads (field_mapper)
  2. Embedded JSON in the hydrated HTML (html_extractor)
If one path is blocked or drifts, the other still yields ads.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .field_mapper import AdLibraryFieldMapper
from .html_extractor import HtmlAdExtractor

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

CONSENT_SELECTORS = [
    'button:has-text("Allow all")',
    'button:has-text("Allow essential and optional cookies")',
    'button:has-text("Decline optional cookies")',
    '[data-cookiebanner="accept_button"]',
    'button:has-text("Accept")',
    'button[data-testid="cookie-policy-manage-dialog-accept-button"]',
]


class PlaywrightSource(AbstractAdSource):
    def __init__(self, debug_dir: str | None = None, headless: bool = True):
        self.debug_dir = debug_dir
        self.headless = headless
        self.field_mapper = AdLibraryFieldMapper()
        self.html_extractor = HtmlAdExtractor()

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        payloads: list = []
        html = ""

        hb = HumanBrowser(headless=self.headless)
        try:
            with hb.session() as page:
                hb.prime_facebook_session(page)

                def on_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "javascript" in ct:
                            payloads.append(response.json())
                    except Exception:
                        pass

                page.on("response", on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                hb.human_pause(3.0, 5.0)

                if self._dismiss_consent(page):
                    hb.human_pause(1.5, 3.0)

                for _ in range(3):
                    hb.human_scroll(page, distance=800, steps=10)
                    hb.human_pause(1.5, 3.0)

                try:
                    html = page.content()
                except Exception:
                    html = ""
        except Exception:
            return

        if self.debug_dir:
            self._dump(payloads, html)

        # Merge both extraction paths, deduped by ad id
        ads_by_id: dict[str, RawAd] = {}
        for payload in payloads:
            for ad in self.field_mapper.extract_ads(payload, country):
                ads_by_id[ad.id] = ad
        if html:
            for ad in self.html_extractor.extract_ads(html, country):
                ads_by_id.setdefault(ad.id, ad)

        count = 0
        for ad in ads_by_id.values():
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

    def _dump(self, payloads, html):
        d = Path(self.debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        stamp = int(datetime.now(timezone.utc).timestamp())
        for i, p in enumerate(payloads):
            (d / f"payload_{stamp}_{i}.json").write_text(
                json.dumps(p, indent=2, default=str), encoding="utf-8"
            )
        if html:
            (d / f"page_{stamp}.html").write_text(html, encoding="utf-8")

    def health_check(self) -> bool:
        return True
EOF

# ============================================================
# 3. FixForge — custom/generic fixes bypass the ambiguity gate
# ============================================================
cat << 'EOF' > src/ad_leak_engine/fix_forge/forge.py
"""Fix Forge orchestrator [SEED: 2399]. Routes leaks to platform generators."""
from ..shared.schemas import Leak, Fix
from ..shared.exceptions import PlatformAmbiguousError
from .platforms.shopify import ShopifyFixGenerator
from .platforms.woocommerce import WooCommerceFixGenerator
from .platforms.bigcommerce import BigCommerceFixGenerator
from .platforms.custom import CustomFixGenerator


class FixForge:
    def __init__(self):
        self.generators = {
            "shopify": ShopifyFixGenerator(),
            "woocommerce": WooCommerceFixGenerator(),
            "bigcommerce": BigCommerceFixGenerator(),
            "custom": CustomFixGenerator(),
        }

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        # Platform-specific code injection requires confidence >= 0.5.
        # Custom/generic fixes (GTM, server-side) are safe for ANY platform,
        # so they bypass the gate — a 'custom' site still gets working fixes.
        if platform != "custom" and confidence < 0.5:
            raise PlatformAmbiguousError(
                f"Platform confidence {confidence} too low for {platform} codegen"
            )
        generator = self.generators.get(platform, self.generators["custom"])
        return generator.generate(leak, platform, confidence)
EOF

# ============================================================
# 4. Master CLI — diagnose / scan / test (single clean entrypoint)
# ============================================================
cat << 'EOF' > src/ad_leak_engine/cli.py
"""Ad-Leak-Engine Master CLI [SEED: 2399].

Usage:
  ./scripts/ale diagnose [keyword] [country]
  ./scripts/ale scan [keyword] [country] [--limit N] [--skip-crawl]
  ./scripts/ale test
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

from .self_heal.human_browser import HumanBrowser
from .ingest.html_extractor import HtmlAdExtractor

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")
DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _fetch_html(url: str) -> str | None:
    import httpx
    try:
        r = httpx.get(url, headers={"User-Agent": DESKTOP_UA}, timeout=20, follow_redirects=True)
        return r.text if r.status_code == 200 else None
    except Exception:
        return None


def cmd_diagnose(keyword: str, country: str):
    url = AD_LIBRARY_URL.format(country=country, query=keyword.replace(" ", "%20"))
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)

    print(f"[ALE] Target: {url}")
    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        print("[ALE] Priming session on facebook.com...")
        hb.prime_facebook_session(page)
        print("[ALE] Navigating to Ad Library with human behavior...")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        hb.human_pause(3.0, 5.0)
        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)
        html = page.content()
        page.screenshot(path=str(debug_dir / "screenshot.png"), full_page=True)

    (debug_dir / "page.html").write_text(html, encoding="utf-8")

    extractor = HtmlAdExtractor()
    ads = extractor.extract_ads(html, country)
    ad_ids = set(re.findall(r'"ad_archive_id":"(\d+)"', html))

    print("")
    print("=" * 55)
    print(f"[ALE] HTML size: {len(html):,} chars")
    print(f"[ALE] Ad IDs in DOM: {len(ad_ids)}")
    print(f"[ALE] Full ad objects extracted: {len(ads)}")
    print("=" * 55)
    for ad in ads[:8]:
        print(f"[ALE]   - {ad.id} | {ad.page_name} | {ad.media_type} | {ad.landing_url}")
    if ads:
        print("[ALE] VERDICT: SUCCESS. Full ad objects extracted from live HTML.")
    else:
        print("[ALE] VERDICT: HTML loaded but extraction found nothing. See data/debug/screenshot.png")


def cmd_scan(keyword: str, country: str, limit: int, skip_crawl: bool):
    from .ingest.playwright_source import PlaywrightSource
    from .leak_scan.l1_creative import L1CreativeScanner
    from .leak_scan.l2_tracking import L2TrackingScanner
    from .leak_scan.l3_scanner import L3SiteScanner
    from .platform_fingerprint.detector import PlatformDetector
    from .fix_forge.forge import FixForge
    from .outreach.bundle import OutreachBuilder
    from .persistence.db import init_db
    from .persistence.repository import AdRepository
    from .shared.schemas import Page

    print(f"[ALE] Scraping REAL ads for '{keyword}' in {country}...")
    ads = list(PlaywrightSource().search(keyword, country, max_results=50))
    print(f"[ALE] Collected {len(ads)} real ads.")
    if not ads:
        print("[ALE] No ads collected. Run './scripts/ale diagnose' to inspect.")
        return

    init_db()
    inserted = AdRepository().upsert_ads(ads)
    print(f"[ALE] Persisted {inserted} new ads to SQLite.")

    by_page: dict[str, list] = defaultdict(list)
    for ad in ads:
        by_page[ad.page_id].append(ad)

    l1, l2, l3 = L1CreativeScanner(), L2TrackingScanner(), L3SiteScanner()
    detector, forge = PlatformDetector(), FixForge()
    builder = OutreachBuilder(output_dir="output")

    processed = 0
    for page_id, page_ads in by_page.items():
        if processed >= limit:
            break
        page_name = page_ads[0].page_name
        landing = next((a.landing_url for a in page_ads if a.landing_url), None)
        page = Page(id=page_id, name=page_name, url=landing, ads=page_ads,
                    first_seen=datetime.now(timezone.utc))
        print(f"\n[ALE] Auditing: {page_name} ({len(page_ads)} ads) -> {landing}")
        try:
            l1_leaks = list(l1.scan(page))
            leaks = list(l1_leaks)
            l23 = 0
            if landing and not skip_crawl:
                try:
                    from .leak_scan.telemetry_collector import TelemetryCollector
                    page.raw = TelemetryCollector().collect(landing)
                    l2_leaks, l3_leaks = l2.scan(page), l3.scan(page)
                    leaks += l2_leaks + l3_leaks
                    l23 = len(l2_leaks) + len(l3_leaks)
                except Exception as e:
                    print(f"[ALE]   L2/L3 crawl skipped: {e}")
            print(f"[ALE]   Leaks: L1={len(l1_leaks)} L2/L3={l23} total={len(leaks)}")

            platform, conf = "custom", 0.3
            if landing:
                html = _fetch_html(landing)
                if html:
                    platform, conf = detector.detect(landing, html)
                page.fingerprint = platform
            print(f"[ALE]   Platform: {platform} (confidence {conf:.2f})")

            fixes = []
            for leak in leaks:
                try:
                    fixes.append(forge.generate(leak, platform, conf))
                except Exception:
                    continue
            print(f"[ALE]   Fixes generated: {len(fixes)}")

            pack = builder.build(page, leaks, fixes)
            print(f"[ALE]   Outreach pack saved: output/{page_id}/")
            print(f"[ALE]   Estimated recovery: {pack.estimated_recovery}")
            processed += 1
        except Exception as e:
            print(f"[ALE]   ERROR auditing {page_name}: {e}")
            continue

    print(f"\n[ALE] SCAN COMPLETE. {processed} pages audited. Packs in output/")


def cmd_test():
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "--tb=short"])


def main():
    parser = argparse.ArgumentParser(prog="ale", description="Ad-Leak-Engine [SEED: 2399]")
    sub = parser.add_subparsers(dest="command")

    p_diag = sub.add_parser("diagnose", help="Human-grade diagnostic of Ad Library access")
    p_diag.add_argument("keyword", nargs="?", default="shoes")
    p_diag.add_argument("country", nargs="?", default="US")

    p_scan = sub.add_parser("scan", help="Full pipeline: scrape -> detect -> fix -> bundle")
    p_scan.add_argument("keyword", nargs="?", default="shoes")
    p_scan.add_argument("country", nargs="?", default="US")
    p_scan.add_argument("--limit", type=int, default=3)
    p_scan.add_argument("--skip-crawl", action="store_true",
                        help="Skip slow L2/L3 live crawl (L1 + fingerprint + fixes only)")

    sub.add_parser("test", help="Run the test suite")

    args = parser.parse_args()
    if args.command == "diagnose":
        cmd_diagnose(args.keyword, args.country)
    elif args.command == "scan":
        cmd_scan(args.keyword, args.country, args.limit, args.skip_crawl)
    elif args.command == "test":
        cmd_test()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
EOF

# ============================================================
# 5. Test fixture — mimics Meta's embedded Relay JSON
# ============================================================
cat << 'EOF' > tests/fixtures/sample_meta_ads.html
<!DOCTYPE html>
<html><head><title>Ad Library</title></head><body>
<div id="root"></div>
<script>
requireLazy(["AdLibraryResults"],function(m){m.handle({"__bbox":{"result":{"data":{"ad_library":{"nodes":[
{"ad_archive_id":"111","page":{"id":"p1","name":"Store One"},"start_date":1700000000,"snapshot":{"title":"Sale","body":"Buy shoes with { special } braces","link_url":"storeone.com","cta_text":"Shop Now"}},
{"ad_archive_id":"222","page":{"id":"p2","name":"Store Two"},"start_date":1700000001,"snapshot":{"title":"Deal","body":"Best sneakers","link_url":"https://storetwo.com","cta_text":"Buy"}}
]}}}})});
</script>
</body></html>
EOF

# ============================================================
# 6. Tests — html_extractor
# ============================================================
cat << 'EOF' > tests/unit/test_html_extractor.py
"""Tests for the HTML ad extractor [SEED: 2399]."""
from pathlib import Path

import pytest

from ad_leak_engine.ingest.html_extractor import HtmlAdExtractor

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "sample_meta_ads.html").read_text(encoding="utf-8")


@pytest.fixture
def extractor():
    return HtmlAdExtractor()


def test_extracts_ads_from_html(extractor):
    ads = extractor.extract_ads(FIXTURE, "US")
    assert len(ads) == 2


def test_extracts_correct_fields(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    assert ads["111"].page_name == "Store One"
    assert ads["111"].landing_url == "https://storeone.com"
    assert ads["222"].body == "Best sneakers"
    assert ads["222"].country == "US"


def test_handles_braces_in_strings(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    # Body contains literal "{ special }" — must not break JSON parsing
    assert "special" in ads["111"].body


def test_handles_unix_timestamp(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    assert ads["111"].start_date.year >= 2023


def test_dedupes_by_id(extractor):
    doubled = FIXTURE + FIXTURE
    ads = extractor.extract_ads(doubled, "US")
    assert len(ads) == 2


def test_empty_html(extractor):
    assert extractor.extract_ads("", "US") == []


def test_no_ads_html(extractor):
    assert extractor.extract_ads("<html><body>nothing here</body></html>", "US") == []


def test_invalid_json_returns_empty(extractor):
    bad = '<script>{"ad_archive_id":"9","page":{broken json,,,</script>'
    assert extractor.extract_ads(bad, "US") == []
EOF

# ============================================================
# 7. Tests — forge custom-confidence rule
# ============================================================
cat << 'EOF' > tests/unit/test_forge_custom.py
"""Tests for the FixForge custom-platform confidence rule [SEED: 2399]."""
import pytest

from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.shared.schemas import Leak
from ad_leak_engine.shared.exceptions import PlatformAmbiguousError


@pytest.fixture
def forge():
    return FixForge()


@pytest.fixture
def leak():
    return Leak(page_id="p", tier="L2", signal="pixel_not_firing",
                severity=0.95, recommendation="install pixel")


def test_custom_low_confidence_still_generates(forge, leak):
    # custom confidence 0.3 must NOT raise — generic fixes are always safe
    fix = forge.generate(leak, "custom", 0.3)
    assert fix.platform == "custom"
    assert len(fix.code_blocks) >= 1


def test_shopify_low_confidence_raises(forge, leak):
    with pytest.raises(PlatformAmbiguousError):
        forge.generate(leak, "shopify", 0.3)


def test_unknown_platform_routes_to_custom(forge, leak):
    fix = forge.generate(leak, "mystery_platform", 0.6)
    assert fix.platform == "custom"
EOF

# ============================================================
# 8. Run full test suite
# ============================================================
echo "[SEED:2399] Running Phase 12 test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 12 COMPLETE"
echo "  Real prospect extraction + full live pipeline installed."
echo ""
echo "  FAST FIRST RUN (L1 + fingerprint + fixes from REAL ads):"
echo "    ./scripts/ale scan shoes US --limit 3 --skip-crawl"
echo ""
echo "  FULL RUN (adds live L2/L3 landing-page crawl):"
echo "    ./scripts/ale scan shoes US --limit 3"
echo "=========================================================="