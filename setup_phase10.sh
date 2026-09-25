#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 10: HUMAN-GRADE BROWSER
# camoufox (state-of-the-art stealth) + session priming +
# human behavior simulation + rich HTML/screenshot diagnostic
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 10 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ============================================================
# 1. Install camoufox (stealth Firefox fork)
# ============================================================
echo "[SEED:2399] Installing camoufox (adversarial-grade stealth browser)..."
python -m pip install -q "camoufox[geoip]"
echo "[SEED:2399] Downloading camoufox binary (one-time, ~200MB)..."
python -c "import camoufox; camoufox.install()"

# ============================================================
# 2. human_browser.py — camoufox wrapper with human behavior
# ============================================================
mkdir -p src/ad_leak_engine/self_heal
cat << 'EOF' > src/ad_leak_engine/self_heal/human_browser.py
"""Human-grade browser using camoufox (stealth Firefox fork) [SEED: 2399].

This replaces vanilla Playwright for adversarial targets (Meta Ad Library,
Akamai/DataDome). Includes session priming, realistic fingerprint, and
human-behavior simulation (Bezier-curve mouse, randomized pauses,
realistic scroll velocity).
"""
from __future__ import annotations

import math
import random
import time
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Page, BrowserContext


# Realistic desktop viewport distribution (weighted by global usage)
VIEWPORTS = [
    (1366, 768), (1920, 1080), (1536, 864), (1440, 900), (1280, 720),
]
VIEWPORT_WEIGHTS = [0.35, 0.30, 0.15, 0.10, 0.10]

# Realistic locales
LOCALES = ["en-US", "en-GB", "en-CA", "en-AU"]
LOCALE_WEIGHTS = [0.70, 0.15, 0.08, 0.07]


def _bezier_curve(p0, p1, p2, p3, t: float):
    """Cubic Bezier curve for natural mouse movement."""
    u = 1 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


class HumanBrowser:
    """camoufox-based browser with human-grade behavior simulation."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._browser = None
        self._cm = None

    @contextmanager
    def session(self) -> Iterator[Page]:
        """Yields a fresh camoufox Page with realistic fingerprint."""
        import camoufox.sync_api

        viewport = random.choices(VIEWPORTS, weights=VIEWPORT_WEIGHTS, k=1)[0]
        locale = random.choices(LOCALES, weights=LOCALE_WEIGHTS, k=1)[0]

        with camoufox.sync_api.Camoufox(
            headless=self.headless,
            geoip=True,
            humanize=True,  # camoufox's built-in humanization
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

    # ---------- Human behavior primitives ----------
    @staticmethod
    def human_pause(low: float = 0.8, high: float = 2.5):
        """Random pause with jitter mimicking human reading time."""
        time.sleep(random.uniform(low, high))

    @staticmethod
    def human_scroll(page: Page, distance: int = 600, steps: int = 8):
        """Scroll with realistic velocity curve (fast start, slow end)."""
        step_size = distance / steps
        for i in range(steps):
            # Ease-out curve: faster at top, slower at bottom
            factor = 1 - (i / steps) ** 2
            page.mouse.wheel(0, step_size * factor)
            time.sleep(random.uniform(0.05, 0.15))

    @staticmethod
    def human_mouse_move(page: Page, target_x: int, target_y: int, steps: int = 25):
        """Move mouse along a Bezier curve for natural motion."""
        try:
            current = page.evaluate("() => ({x: 0, y: 0})")
        except Exception:
            current = {"x": 0, "y": 0}
        start = (current["x"], current["y"])
        end = (target_x, target_y)
        # Control points for natural arc
        ctrl1 = (start[0] + (end[0] - start[0]) * 0.3, start[1] + random.randint(-50, 50))
        ctrl2 = (start[0] + (end[0] - start[0]) * 0.7, end[1] + random.randint(-50, 50))
        for i in range(steps + 1):
            t = i / steps
            x, y = _bezier_curve(start, ctrl1, ctrl2, end, t)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.005, 0.02))

    @staticmethod
    def human_type(page: Page, selector: str, text: str):
        """Type text with variable inter-keystroke delay."""
        page.click(selector)
        for ch in text:
            page.keyboard.type(ch, delay=random.randint(50, 180))

    # ---------- Session priming ----------
    @staticmethod
    def prime_facebook_session(page: Page, timeout_ms: int = 30000) -> bool:
        """Visit facebook.com first to earn real session cookies [SEED: 2399].

        Returns True if priming completed, False if blocked.
        After priming, the same page context has legitimate cookies
        for subsequent Ad Library requests.
        """
        try:
            page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=timeout_ms)
            HumanBrowser.human_pause(1.5, 3.0)

            # Dismiss any consent/cookie banner on facebook.com
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

# ============================================================
# 3. Updated playwright_source.py using camoufox + session priming
# ============================================================
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HUMAN-GRADE Meta Ad Library scraper using camoufox [SEED: 2399].

Uses camoufox (stealth Firefox fork) instead of vanilla Playwright.
Includes session priming (visit facebook.com first) + human behavior
simulation to defeat DataDome/Akamai bot detection.
"""
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
                # Step 1: Session priming on facebook.com
                hb.prime_facebook_session(page)

                def on_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "json" in ct or "javascript" in ct:
                            payloads.append(response.json())
                    except Exception:
                        pass

                page.on("response", on_response)

                # Step 2: Navigate to Ad Library with human-like pacing
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                hb.human_pause(2.0, 4.0)

                # Step 3: Dismiss consent if present
                if self._dismiss_consent(page):
                    hb.human_pause(1.5, 3.0)

                # Step 4: Human-like scroll to trigger lazy loading
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

# ============================================================
# 4. diagnose_ingest_v2.py — captures HTML + screenshot
# ============================================================
cat << 'EOF' > scripts/diagnose_ingest_v2.py
"""Rich diagnostic v2: captures HTML + screenshot to reveal what Meta actually serves [SEED: 2399].

Run this when vanilla Playwright returns 0 ads. Shows us the raw HTML
and takes a screenshot so we can see EXACTLY what's being served.
"""
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

        # Try dismissing consent
        dismissed = False
        for sel in [
            'button:has-text("Allow all")',
            'button:has-text("Decline optional cookies")',
            'button:has-text("Accept")',
        ]:
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

        # Human-like scroll
        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)

        # Capture everything
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

    # Save artifacts
    (debug_dir / "page.html").write_text(html, encoding="utf-8")
    (debug_dir / "responses.json").write_text(
        json.dumps(response_urls[:50], indent=2), encoding="utf-8"
    )
    if json_payloads:
        for i, p in enumerate(json_payloads[:5]):
            (debug_dir / f"payload_{i}.json").write_text(
                json.dumps(p, indent=2, default=str), encoding="utf-8"
            )

    # Verdict logic
    html_lower = html.lower()
    has_graphql = "graphql" in html_lower or "relay" in html_lower
    has_ad_cards = any(x in html_lower for x in ["ad-archive", "ads-library-ad", "ad_creative"])
    has_login_wall = "login" in html_lower and "password" in html_lower
    has_challenge = any(x in html_lower for x in ["checking your browser", "just a moment", "security check"])

    print("")
    print("[DIAG-v2] VERDICT:")
    if has_login_wall:
        print("  → LOGIN WALL detected. Meta requires authentication from your IP region.")
    elif has_challenge:
        print("  → CHALLENGE PAGE detected. Meta is running an active anti-bot challenge.")
    elif has_graphql or has_ad_cards:
        print(f"  → AD LIBRARY HTML PRESENT. {len(json_payloads)} payloads captured.")
        if len(json_payloads) == 0:
            print("  → HTML loaded but no JSON intercepted — inspect page.html for schema.")
    elif len(json_payloads) > 0:
        print(f"  → {len(json_payloads)} JSON payloads captured. Inspect payload_*.json.")
    else:
        print("  → BARE SKELETON served. Meta detected automation despite camoufox.")
        print("    Open data/debug/diag_v2/screenshot.png to see what was actually rendered.")
    print("")
    print(f"[DIAG-v2] Artifacts saved to: {debug_dir}/")


if __name__ == "__main__":
    main()
EOF

# ============================================================
# 5. Tests
# ============================================================
cat << 'EOF' > tests/unit/test_human_browser.py
"""Tests for human_browser primitives [SEED: 2399]."""
import math

from ad_leak_engine.self_heal.human_browser import HumanBrowser, _bezier_curve


def test_bezier_curve_endpoints():
    """Bezier curve must start at p0 and end at p3."""
    p0, p1, p2, p3 = (0, 0), (10, 10), (20, 5), (30, 30)
    sx, sy = _bezier_curve(p0, p1, p2, p3, 0.0)
    ex, ey = _bezier_curve(p0, p1, p2, p3, 1.0)
    assert (sx, sy) == (0, 0)
    assert (ex, ey) == (30, 30)


def test_bezier_curve_midpoint_in_bounds():
    p0, p1, p2, p3 = (0, 0), (10, 10), (20, 5), (30, 30)
    mx, my = _bezier_curve(p0, p1, p2, p3, 0.5)
    assert 0 <= mx <= 30
    assert 0 <= my <= 30


def test_human_browser_initializes():
    hb = HumanBrowser(headless=True)
    assert hb.headless is True
    assert hb._browser is None


def test_human_browser_session_context_manager():
    """Smoke test: session() context manager yields a Page without crashing."""
    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        assert page is not None
        # Basic capability check
        assert page.title() is not None or page.title() == ""


def test_human_pause_does_not_raise():
    """human_pause must complete without exception."""
    HumanBrowser.human_pause(0.01, 0.02)  # short for test speed
EOF

# ============================================================
# 6. Run tests
# ============================================================
echo "[SEED:2399] Running Phase 10 test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 10 COMPLETE"
echo "  Human-grade browser (camoufox) + session priming installed."
echo ""
echo "  NOW — run the RICH diagnostic with camoufox:"
echo "    python scripts/diagnose_ingest_v2.py shoes US"
echo ""
echo "  This will produce:"
echo "    - data/debug/diag_v2/screenshot.png  (what Meta actually rendered)"
echo "    - data/debug/diag_v2/page.html       (raw HTML)"
echo "    - data/debug/diag_v2/responses.json  (all network requests)"
echo ""
echo "  Paste the [DIAG-v2] output here so I can read the verdict."
echo "=========================================================="