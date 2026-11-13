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

# [SEED: 2399] REALISTIC USER AGENTS FOR DESKTOP CHROME/FIREFOX
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # macOS Chrome
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

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
        ua = random.choice(USER_AGENTS)

        with camoufox.sync_api.Camoufox(
            headless=self.headless,
            geoip=True,      # Maps IP to Geo
            humanize=True,   # Simulates human input
            os="windows",    # Force Windows fingerprint
        ) as browser:
            context = browser.new_context(
                viewport={"width": viewport[0], "height": viewport[1]},
                locale=locale,
                timezone_id="America/New_York",
                user_agent=ua, # <--- INJECT REAL UA
            )
            
            # [SEED: 2399] ANTI-DETECTION SCRIPTS
            # Hide webdriver, plugins, languages inconsistencies
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                
                // Fake WebGL Vendor
                const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                    return originalGetParameter.call(this, parameter);
                };
            """)

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
        """Scroll with realistic velocity."""
        step_size = distance / steps
        for i in range(steps):
            factor = 1 - (i / steps) ** 2
            try:
                page.mouse.wheel(0, step_size * factor)
            except PlaywrightError as e:
                if "context was destroyed" in str(e).lower():
                    pass
                else:
                    raise
            time.sleep(random.uniform(0.05, 0.15))

    @staticmethod
    def solve_cloudflare_turnstile(page: Page) -> bool:
        """Attempts to click the Turnstile checkbox if present."""
        try:
            # Look for the iframe containing the turnstile
            frames = page.frames
            for frame in frames:
                if "challenges.cloudflare.com" in frame.url:
                    # Try to find the checkbox inside the frame
                    checkbox = frame.locator("input[type='checkbox']").first
                    if checkbox.is_visible(timeout=2000):
                        checkbox.click()
                        page.wait_for_timeout(3000) # Wait for verification
                        return True
        except Exception:
            pass
        return False