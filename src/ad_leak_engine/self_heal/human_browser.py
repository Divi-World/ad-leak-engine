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
