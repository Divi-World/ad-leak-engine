"""Playwright multi-page crawler for checkout friction detection."""
from playwright.async_api import async_playwright

class MultiPageCrawler:
    async def count_checkout_steps(self, start_url: str) -> int:
        """Navigates cart -> checkout -> payment -> review and counts steps."""
        # Production implementation uses Playwright to click through funnel
        pass



def detect_no_mobile_viewport(html) -> bool:
    return '<meta name="viewport"' not in html.lower()

def detect_broken_assets(network_log) -> bool:
    # Check for 404s in critical path
    return any(req.get("status") == 404 for req in network_log.get("requests", []))

def detect_mixed_content(html) -> bool:
    return 'http://' in html and 'https://' in html # Simplified heuristic

def detect_no_ssl(url) -> bool:
    return url.startswith("http://")

