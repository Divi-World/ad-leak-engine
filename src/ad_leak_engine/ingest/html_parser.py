"""HTML Parser: Extracts RawAd contracts from Meta's embedded HTML [SEED: 2399].

When Meta embeds the GraphQL data directly into the HTML for React hydration,
the network interceptor may miss it. This parser uses regex to reliably
extract ad_archive_id, page_id, page_name, and body from the raw HTML.
"""
import re
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad

def parse_html_to_ads(html: str, country: str) -> list[RawAd]:
    """Extracts ads from the raw HTML using regex markers."""
    ads = []
    seen = set()
    
    # Find all ad_archive_ids in the HTML
    matches = re.finditer(r'"ad_archive_id":"(\d+)"', html)
    
    for match in matches:
        ad_id = match.group(1)
        if ad_id in seen:
            continue
        seen.add(ad_id)
        
        # Extract surrounding context (approx 3000 chars around the match)
        start = max(0, match.start() - 1500)
        end = min(len(html), match.end() + 1500)
        context = html[start:end]
        
        # Extract page_id
        page_id_match = re.search(r'"page":\s*\{\s*"id":"(\d+)"', context)
        page_id = page_id_match.group(1) if page_id_match else "unknown"
        
        # Extract page_name
        page_name_match = re.search(r'"page":\s*\{\s*"id":"\d+",\s*"name":"([^"]+)"', context)
        page_name = page_name_match.group(1) if page_name_match else "Unknown Page"
        
        # Extract snapshot/body
        body_match = re.search(r'"body":\s*"([^"]{0,1000})"', context)
        body = body_match.group(1) if body_match else None
        
        # Extract creation_time (unix timestamp)
        time_match = re.search(r'"ad_delivery_start_time":\s*"?(\d+)"?', context)
        creation_time = int(time_match.group(1)) if time_match else None
        
        raw_node = {
            "id": ad_id,
            "ad_archive_id": ad_id,
            "page": {"id": page_id, "name": page_name},
            "snapshot": {"body": body},
            "creation_time": creation_time
        }
        
        try:
            ad = normalize_meta_ad(raw_node, country)
            ads.append(ad)
        except Exception:
            continue
            
    return ads
