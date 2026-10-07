"""HTML Parser: Extracts ad data from raw HTML using BeautifulSoup [SEED: 2399].

Complementary to html_extractor.py. Uses DOM parsing for structured extraction.
"""
from typing import Any


def parse_html_to_ads(html: str, country: str = "US") -> list[dict]:
    """Parse raw HTML and extract ad-like structures.
    
    Returns list of dicts with ad_archive_id, page info, and snapshot data.
    Used as fallback when html_extractor.py regex approach yields no results.
    """
    if not html:
        return []

    ads = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Look for ad archive ID markers in data attributes or scripts
        for script in soup.find_all("script"):
            if script.string and "ad_archive_id" in script.string:
                # Delegate to html_extractor for the actual parsing
                from .html_extractor import HtmlAdExtractor
                extractor = HtmlAdExtractor()
                return [ad.__dict__ for ad in extractor.extract_ads(html, country)]

        # Look for structured ad cards in DOM
        ad_cards = soup.find_all(attrs={"data-ad-archive-id": True})
        for card in ad_cards:
            ad_data = {
                "id": card.get("data-ad-archive-id", ""),
                "page_id": card.get("data-page-id", "unknown"),
                "page_name": card.get("data-page-name", "Unknown Page"),
                "body": card.get_text(strip=True)[:500] if card.get_text(strip=True) else None,
                "landing_url": card.get("data-link-url"),
                "country": country,
            }
            if ad_data["id"]:
                ads.append(ad_data)

    except Exception:
        pass

    return ads
