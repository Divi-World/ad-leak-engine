"""Advanced WAF Bypass Engine [SEED: 2399].

Multi-layer stealth fetching strategy:
1. Curl-CFFI with Randomized Fingerprints.
2. Playwright with Anti-Detection Flags.
3. Retry Logic with Exponential Backoff.
"""
import logging
import time
import random
from typing import Optional

logger = logging.getLogger(__name__)

def _get_random_user_agent() -> str:
    """Rotate between common desktop UAs."""
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]
    return random.choice(uas)

def stealth_fetch(url: str, max_retries: int = 3) -> Optional[str]:
    """
    Attempt to fetch URL using escalating stealth techniques.
    Returns HTML string or None if all methods fail.
    """
    
    # Layer 1: Curl-CFFI (Fastest)
    try:
        from curl_cffi import requests as cffi_requests
        
        ua = _get_random_user_agent()
        resp = cffi_requests.get(
            url,
            impersonate="chrome120",
            timeout=10,
            headers={"User-Agent": ua},
            allow_redirects=True
        )
        
        if resp.status_code == 200 and len(resp.text) > 500:
            # Basic WAF check
            if not any(marker in resp.text.lower() for marker in ["cloudflare", "just a moment", "turnstile"]):
                logger.debug(f"[WAF-BYPASS] Success via Curl-CFFI: {url}")
                return resp.text
    except Exception as e:
        logger.debug(f"[WAF-BYPASS] Curl-CFFI failed for {url}: {e}")

    # Layer 2: Playwright with Anti-Detection (Slower but Smarter)
    for attempt in range(max_retries):
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                # Launch with stealth args
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-web-security",
                        f"--user-agent={_get_random_user_agent()}"
                    ]
                )
                
                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=_get_random_user_agent(),
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                # Inject Stealth Scripts
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                """)
                
                page = context.new_page()
                
                # Navigate with generous timeout
                response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                
                # Wait slightly for JS challenges to resolve
                page.wait_for_timeout(2000)
                
                html = page.content()
                browser.close()
                
                if html and len(html) > 500:
                    if not any(marker in html.lower() for marker in ["cloudflare", "just a moment", "turnstile"]):
                        logger.info(f"[WAF-BYPASS] Success via Playwright (Attempt {attempt+1}): {url}")
                        return html
                        
        except Exception as e:
            logger.warning(f"[WAF-BYPASS] Playwright attempt {attempt+1} failed for {url}: {e}")
            time.sleep(2 * (attempt + 1)) # Exponential backoff

    logger.error(f"[WAF-BYPASS] All layers failed for {url}")
    return None
