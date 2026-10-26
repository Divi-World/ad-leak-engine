"""Aggressive Email Discovery Module [SEED: 2399].

OPTIMIZED FOR SPEED:
- Uses curl_cffi for fast HTTP checks (skip 404s instantly).
- Limits probes to top 3 high-value paths.
- Shortens Playwright timeout to 10s for email hunting.
- Falls back to Playwright ONLY if curl_cffi hits WAF.
"""
import re
import logging
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

def _fast_http_fetch(url: str) -> tuple[int, str | None]:
    """Fast fetch using curl_cffi. Returns (status_code, html_or_none)."""
    try:
        from curl_cffi import requests as cffi_requests
        
        resp = cffi_requests.get(
            url, 
            impersonate="chrome120", 
            timeout=5, # Short timeout for speed
            allow_redirects=True
        )
        return resp.status_code, resp.text if resp.status_code == 200 else None
    except Exception:
        return 0, None

def _playwright_fast_fetch(url: str) -> str | None:
    """Fallback: Use Playwright with SHORT timeout for email discovery."""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            # Reduced timeout: 10s instead of 45s
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        logger.debug(f"Playwright fast fetch failed for {url}: {e}")
    return None

def discover_emails_from_page(html: str, base_url: str = "") -> list[str]:
    """Extract emails from HTML content using regex and mailto links."""
    if not html:
        return []
        
    emails = set()
    
    # 1. Regex extraction
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(pattern, html)
    for e in found:
        e = e.strip().lower()
        if _is_valid_business_email(e):
            emails.add(e)
            
    # 2. Mailto links
    mailto_pattern = r'href=["\']mailto:([^"\']+)'
    mailto_found = re.findall(mailto_pattern, html, re.IGNORECASE)
    for e in mailto_found:
        e = e.split('?')[0].strip().lower()
        if _is_valid_business_email(e):
            emails.add(e)
            
    return list(emails)[:10]

def _is_valid_business_email(email: str) -> bool:
    """Filter out noise, assets, and suspicious domains."""
    if not email or '@' not in email:
        return False
        
    local, domain = email.rsplit('@', 1)
    
    # Reject common noise
    noise_domains = ["example.com", "test.com", "localhost", "sentry.io", "bugsnag", "newrelic", "datadome"]
    if any(nd in domain for nd in noise_domains):
        return False
        
    # Reject asset extensions
    if local.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css')):
        return False
        
    return True

def crawl_contact_pages_smart(landing_url: str) -> list[str]:
    """
    SMART CRAWLER:
    1. Try top 3 paths with fast HTTP.
    2. If 404/403, skip immediately.
    3. If 200, extract emails.
    4. If WAF detected, retry once with Playwright (short timeout).
    """
    if not landing_url:
        return []
        
    parsed = urlparse(landing_url)
    if not parsed.scheme or not parsed.netloc:
        return []
        
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    
    # Top 3 highest probability paths only
    candidate_paths = [
        "/contact", 
        "/contact-us", 
        "/pages/contact-us"
    ]
    
    all_emails = set()
    
    def _probe_path(path: str) -> list[str]:
        url = base_domain + path
        status, html = _fast_http_fetch(url)
        
        if status == 200 and html:
            # Check for WAF markers in HTML
            if any(waf in html.lower() for waf in ["cloudflare", "just a moment", "turnstile", "datadome"]):
                # WAF hit, try Playwright fallback
                pw_html = _playwright_fast_fetch(url)
                if pw_html:
                    return discover_emails_from_page(pw_html, url)
            else:
                return discover_emails_from_page(html, url)
                
        elif status == 404 or status == 403:
            # Page doesn't exist or forbidden, skip fast
            return []
            
        return []

    # Parallelize probes for speed
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_probe_path, p): p for p in candidate_paths}
        for future in as_completed(futures):
            try:
                emails = future.result(timeout=15) # Max 15s per thread group
                all_emails.update(emails)
                if len(all_emails) >= 3: # Found enough, stop early
                    break
            except Exception:
                continue
                
    return list(all_emails)[:10]

def parse_sitemap_for_contacts(landing_url: str) -> list[str]:
    """Parse sitemap.xml to find high-value contact URLs."""
    if not landing_url:
        return []
        
    parsed = urlparse(landing_url)
    if not parsed.scheme or not parsed.netloc:
        return []
        
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url = base_domain + "/sitemap.xml"
    
    contact_urls = []
    
    # Fast check sitemap first
    status, sm_content = _fast_http_fetch(sitemap_url)
    
    if status == 200 and sm_content and "<urlset" in sm_content.lower():
        try:
            root = ET.fromstring(sm_content)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc_elem in root.findall(".//sm:loc", ns):
                if loc_elem.text:
                    full_url = loc_elem.text.strip()
                    low = full_url.lower()
                    if any(kw in low for kw in ["contact", "about", "team", "staff", "policy", "legal"]):
                        contact_urls.append(full_url)
        except Exception as e:
            logger.debug(f"Sitemap parsing failed: {e}")
            
    return contact_urls[:5] # Limit further

def discover_emails_aggressively(landing_url: str, initial_html: str | None = None) -> list[str]:
    """
    Main Entry Point for Phase 5.1 (Optimized).
    Combines quick scan, smart crawling, and sitemap probing.
    Returns deduplicated list of up to 10 candidate emails.
    """
    discovered = set()
    
    # 1. Quick scan of provided HTML (if any)
    if initial_html:
        quick_emails = discover_emails_from_page(initial_html, landing_url)
        discovered.update(quick_emails)
        
    # 2. If sparse, use SMART crawler (fast HTTP + limited PW)
    if len(discovered) < 3:
        crawled = crawl_contact_pages_smart(landing_url)
        discovered.update(crawled)
        
    # 3. If still sparse, check sitemap for hidden URLs (max 5 probes)
    if len(discovered) < 3:
        sitemap_contacts = parse_sitemap_for_contacts(landing_url)
        for su in sitemap_contacts[:3]: # Limit to 3 more
            status, s_html = _fast_http_fetch(su)
            if status == 200 and s_html:
                # Check WAF
                if any(waf in s_html.lower() for waf in ["cloudflare", "just a moment", "turnstile"]):
                    s_html = _playwright_fast_fetch(su)
                    
                if s_html:
                    s_emails = discover_emails_from_page(s_html, su)
                    discovered.update(s_emails)
                    if len(discovered) >= 5:
                        break
                    
    # Final Dedupe & Cap
    result = sorted(list(discovered))[:10]
    logger.info(f"[EMAIL-DISCOVERY] Found {len(result)} candidates for {landing_url}")
    return result
