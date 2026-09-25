#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 10 PATCH
# Fixes camoufox binary download + writes all Phase 10 files
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 10 PATCH"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Download camoufox binary via CLI
echo "[SEED:2399] Downloading camoufox binary (this may take a minute)..."
python -m camoufox fetch || camoufox fetch

# 2. human_browser.py
cat << 'EOF' > src/ad_leak_engine/self_heal/human_browser.py
"""Human-grade browser using camoufox (stealth Firefox fork) [SEED: 2399]."""
from __future__ import annotations

import random
import time
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Page

VIEWPORTS = [(1366, 768), (1920, 1080), (1536, 864), (1440, 900)]
VIEWPORT_WEIGHTS = [0.35, 0.30, 0.20, 0.15]
LOCALES = ["en-US", "en-GB", "en-CA"]
LOCALE_WEIGHTS = [0.80, 0.10, 0.10]

def _bezier_curve(p0, p1, p2, p3, t: float):
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )

class HumanBrowser:
    def __init__(self, headless: bool = True):
        self.headless = headless

    @contextmanager
    def session(self) -> Iterator[Page]:
        import camoufox.sync_api
        viewport = random.choices(VIEWPORTS, weights=VIEWPORT_WEIGHTS, k=1)[0]
        locale = random.choices(LOCALES, weights=LOCALE_WEIGHTS, k=1)[0]

        with camoufox.sync_api.Camoufox(
            headless=self.headless,
            geoip=True,
            humanize=True,
        ) as browser:
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                locale=locale,
                timezone_id="America/New_York",
            )
            page = context.new_page()
            try:
                yield page
            finally:
                context.close()

    @staticmethod
    def human_pause(low: float = 0.8, high: float = 2.5):
        time.sleep(random.uniform(low, high))

    @staticmethod
    def human_scroll(page: Page, distance: int = 600, steps: int = 8):
        step_size = distance / steps
        for i in range(steps):
            factor = 1 - (i / steps) ** 2
            page.mouse.wheel(0, step_size * factor)
            time.sleep(random.uniform(0.05, 0.15))

    @staticmethod
    def prime_facebook_session(page: Page, timeout_ms: int = 30000) -> bool:
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=timeout_ms)
            HumanBrowser.human_pause(1.5, 3.0)
            consent_selectors = [
                'button:has-text("Allow all")',
                'button:has-text("Allow essential and optional cookies")',
                'button:has-text("Decline optional cookies")',
                '[data-cookiebanner="accept_button"]',
                'button:has-text("Accept")',
                'button[data-testid="cookie-policy-manage-dialog-accept-button"]',
            ]
            for sel in consent_selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=1200):
                        loc.click()
                        HumanBrowser.human_pause(0.5, 1.0)
                        break
                except Exception:
                    continue
            HumanBrowser.human_pause(2.0, 4.0)
            return True
        except Exception:
            return False
EOF

# 3. playwright_source.py (using camoufox)
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HUMAN-GRADE Meta Ad Library scraper using camoufox [SEED: 2399]."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .field_mapper import AdLibraryFieldMapper

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

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        payloads = []

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
                hb.human_pause(2.0, 4.0)

                if self._dismiss_consent(page):
                    hb.human_pause(1.5, 3.0)

                for _ in range(3):
                    hb.human_scroll(page, distance=800, steps=10)
                    hb.human_pause(1.5, 3.5)
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

# 4. diagnose_ingest_v2.py
cat << 'EOF' > scripts/diagnose_ingest_v2.py
"""Rich diagnostic v2: captures HTML + screenshot using camoufox [SEED: 2399]."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.self_heal.human_browser import HumanBrowser

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "shoes"
    country = sys.argv[2] if len(sys.argv) > 2 else "US"
    url = AD_LIBRARY_URL.format(country=country, query=keyword.replace(" ", "%20"))

    debug_dir = Path("data/debug/diag_v2")
    debug_dir.mkdir(parents=True, exist_ok=True)

    print(f"[DIAG-v2] Using camoufox (stealth Firefox fork)")
    print(f"[DIAG-v2] Target: {url}")

    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        print("[DIAG-v2] Priming session on facebook.com...")
        primed = hb.prime_facebook_session(page)
        print(f"[DIAG-v2] Session primed: {primed}")

        json_payloads = []
        response_urls = []

        def on_response(response):
            response_urls.append({"url": response.url, "status": response.status})
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct or "javascript" in ct:
                    json_payloads.append(response.json())
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        hb.human_pause(2.0, 4.0)

        dismissed = False
        for sel in ['button:has-text("Allow all")', 'button:has-text("Decline optional cookies")', 'button:has-text("Accept")']:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1500):
                    loc.click()
                    dismissed = True
                    hb.human_pause(1.0, 2.0)
                    break
            except Exception:
                continue

        print(f"[DIAG-v2] Consent dismissed: {dismissed}")

        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)

        final_url = page.url
        title = page.title()
        html = page.content()
        screenshot_path = debug_dir / "screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=True)

    print(f"[DIAG-v2] Final URL: {final_url}")
    print(f"[DIAG-v2] Page title: {title}")
    print(f"[DIAG-v2] HTML length: {len(html)} chars")
    print(f"[DIAG-v2] Screenshot: {screenshot_path}")
    print(f"[DIAG-v2] Total network responses: {len(response_urls)}")
    print(f"[DIAG-v2] JSON/JS payloads captured: {len(json_payloads)}")

    (debug_dir / "page.html").write_text(html, encoding="utf-8")
    (debug_dir / "responses.json").write_text(json.dumps(response_urls[:50], indent=2), encoding="utf-8")
    if json_payloads:
        for i, p in enumerate(json_payloads[:5]):
            (debug_dir / f"payload_{i}.json").write_text(json.dumps(p, indent=2, default=str), encoding="utf-8")

    html_lower = html.lower()
    has_graphql = "graphql" in html_lower or "relay" in html_lower
    has_ad_cards = any(x in html_lower for x in ["ad-archive", "ads-library-ad", "ad_creative"])
    has_login_wall = "login" in html_lower and "password" in html_lower
    has_challenge = any(x in html_lower for x in ["checking your browser", "just a moment", "security check"])

    print("")
    print("[DIAG-v2] VERDICT:")
    if has_login_wall:
        print("  → LOGIN WALL detected.")
    elif has_challenge:
        print("  → CHALLENGE PAGE detected.")
    elif has_graphql or has_ad_cards:
        print(f"  → AD LIBRARY HTML PRESENT. {len(json_payloads)} payloads captured.")
    elif len(json_payloads) > 0:
        print(f"  → {len(json_payloads)} JSON payloads captured.")
    else:
        print("  → BARE SKELETON served.")
    print(f"[DIAG-v2] Artifacts saved to: {debug_dir}/")

if __name__ == "__main__":
    main()
EOF

# 5. Tests
cat << 'EOF' > tests/unit/test_human_browser.py
"""Tests for human_browser primitives [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser, _bezier_curve

def test_bezier_curve_endpoints():
    p0, p1, p2, p3 = (0, 0), (10, 10), (20, 5), (30, 30)
    sx, sy = _bezier_curve(p0, p1, p2, p3, 0.0)
    ex, ey = _bezier_curve(p0, p1, p2, p3, 1.0)
    assert (sx, sy) == (0, 0)
    assert (ex, ey) == (30, 30)

def test_human_browser_initializes():
    hb = HumanBrowser(headless=True)
    assert hb.headless is True

def test_human_browser_session_context_manager():
    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        assert page is not None

def test_human_pause_does_not_raise():
    HumanBrowser.human_pause(0.01, 0.02)
EOF

# 6. Run tests
echo "[SEED:2399] Running Phase 10 test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 10 PATCH COMPLETE"
echo "=========================================================="