#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 11.1 PATCH
# Fixes Playwright Context Destroyed error + Windows encoding
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 11.1 PATCH"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Fix human_browser.py (Resilient Scrolling)
cat << 'EOF' > src/ad_leak_engine/self_heal/human_browser.py
"""Human-grade browser using camoufox (stealth Firefox fork) [SEED: 2399]."""
from __future__ import annotations

import random
import time
from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Page, Error as PlaywrightError

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
        """Scroll with realistic velocity. Catches SPA context destruction."""
        step_size = distance / steps
        for i in range(steps):
            factor = 1 - (i / steps) ** 2
            try:
                page.mouse.wheel(0, step_size * factor)
            except PlaywrightError as e:
                # Meta's SPA changes history state during scroll, destroying context briefly
                if "context was destroyed" in str(e).lower() or "navigation" in str(e).lower():
                    pass 
                else:
                    raise
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

# 2. Fix cli.py (Windows Encoding + ASCII Arrows)
cat << 'EOF' > src/ad_leak_engine/cli.py
"""Ad-Leak-Engine Master CLI [SEED: 2399].
Usage:
  ./scripts/ale diagnose <keyword> <country>
"""
import sys
import re
import os
from pathlib import Path

# Force UTF-8 on Windows to prevent cp1252 encoding crashes
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

from .self_heal.human_browser import HumanBrowser

def cmd_diagnose(keyword: str, country: str):
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&q={keyword}&search_type=keyword_unordered"
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
        
        print("[ALE] Scrolling to trigger lazy loading...")
        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)
            
        html = page.content()
        page.screenshot(path=str(debug_dir / "screenshot.png"), full_page=True)
        
    # Save HTML for inspection
    (debug_dir / "page.html").write_text(html, encoding="utf-8")
    
    # Analyze the HTML for embedded ad data
    ad_ids = set(re.findall(r'"ad_archive_id":"(\d+)"', html))
    page_ids = set(re.findall(r'"page_id":"(\d+)"', html))
    
    print("")
    print("=" * 50)
    print(f"[ALE] HTML Size: {len(html):,} chars")
    print(f"[ALE] Unique Ad IDs found in DOM: {len(ad_ids)}")
    print(f"[ALE] Unique Page IDs found in DOM: {len(page_ids)}")
    print("=" * 50)
    
    if len(ad_ids) > 0:
        print("[ALE] VERDICT: SUCCESS. Ads are fully rendered in the HTML.")
        print(f"[ALE] Sample Ad IDs: {list(ad_ids)[:5]}")
        print("[ALE] Next step: The field mapper will parse this HTML into RawAd contracts.")
    else:
        print("[ALE] VERDICT: HTML loaded but no ad_archive_id markers found.")
        print("[ALE] Check data/debug/screenshot.png to see what Meta rendered.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ad-Leak-Engine Master CLI [SEED: 2399]")
        print("Usage: ./scripts/ale <command> [args]")
        print("Commands:")
        print("  diagnose <keyword> <country>  - Run human-grade diagnostic")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "diagnose":
        kw = sys.argv[2] if len(sys.argv) > 2 else "shoes"
        co = sys.argv[3] if len(sys.argv) > 3 else "US"
        cmd_diagnose(kw, co)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
EOF

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 11.1 PATCH COMPLETE"
echo "=========================================================="
echo "  NOW RUN THE MASTER COMMAND AGAIN:"
echo "    ./scripts/ale diagnose shoes US"
echo "=========================================================="