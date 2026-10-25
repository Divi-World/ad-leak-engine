"""Standalone Email Discovery Module [SEED: 2399]."""
import re
import logging
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def discover_emails_from_page(html: str, base_url: str) -> list[str]:
    """Extract emails from HTML content using regex and mailto links."""
    emails = set()
    
    # 1. Regex extraction
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    found = re.findall(pattern, html or "")
    for e in found:
        e = e.strip().lower()
        if _is_valid_business_email(e):
            emails.add(e)
            
    # 2. Mailto links
    mailto_pattern = r'href=["\']mailto:([^"\']+)'
    mailto_found = re.findall(mailto_pattern, html or "", re.IGNORECASE)
    for e in mailto_found:
        e = e.split('?')[0].strip().lower()
        if _is_valid_business_email(e):
            emails.add(e)
            
    return list(emails)[:10] # Limit to top 10

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

def crawl_contact_pages(fetcher_func, landing_url: str, max_probes: int = 10) -> list[str]:
    """Crawl standard contact/about pages for emails."""
    parsed = urlparse(landing_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    
    candidate_paths = [
        "/contact", "/contact-us", "/pages/contact-us",
        "/about", "/about-us", "/company/about",
        "/team", "/our-team", "/staff", "/leadership",
        "/policies/privacy-policy", "/imprint", "/legal"
    ]
    
    all_emails = set()
    probes_done = 0
    
    for path in candidate_paths:
        if probes_done >= max_probes:
            break
            
        url = base_domain + path
        try:
            html = fetcher_func(url)
            if html and len(html) > 500:
                emails = discover_emails_from_page(html, url)
                all_emails.update(emails)
                probes_done += 1
                if len(all_emails) >= 5:
                    break
        except Exception as e:
            logger.debug(f"Failed to probe {url}: {e}")
            continue
            
    return list(all_emails)[:10]

def parse_sitemap_for_contacts(fetcher_func, landing_url: str) -> list[str]:
    """Parse sitemap.xml to find high-value contact URLs."""
    parsed = urlparse(landing_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url = base_domain + "/sitemap.xml"
    
    contact_urls = []
    try:
        sm_content = fetcher_func(sitemap_url)
        if sm_content and "<urlset" in sm_content.lower():
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
        
    return contact_urls[:20] # Cap at 20 to prevent overload
