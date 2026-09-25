"""HTML ad extractor for Meta Ad Library [SEED: 2399].

Uses regex windows around ad_archive_id anchors to extract fields
from Meta's embedded Relay/GraphQL data. Context window looks FORWARD
from each anchor to prevent cross-contamination between adjacent ads.
"""
import re
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad

class HtmlAdExtractor:
    def extract_ads(self, html: str, country: str) -> list[RawAd]:
        if not html: return []
        
        matches = list(re.finditer(r'"ad_archive_id":"(\d+)"', html))
        if not matches:
            matches = list(re.finditer(r'"id":"(\d{10,20})"', html))
            
        seen = set()
        ads = []
        
        for m in matches:
            ad_id = m.group(1)
            if ad_id in seen: continue
            
            # FORWARD-ONLY context window prevents capturing previous ad's data
            start = match_start = m.start()
            end = min(len(html), m.end() + 2000)
            ctx = html[start:end]
            
            page_name = self._extract(ctx, [
                r'"page_name":"([^"]+)"',
                r'"page":\s*\{[^}]*"name":"([^"]+)"',
                r'"page":\s*\{[^}]*"id":"\d+"[^}]*"name":"([^"]+)"'
            ], "Unknown Page")
            
            page_id = self._extract(ctx, [
                r'"page_id":"(\d+)"',
                r'"page":\s*\{[^}]*"id":"(\d+)"'
            ], "unknown")
            
            body = self._extract(ctx, [
                r'"body":"([^"]*)"',
                r'"ad_creative_bodies":\["([^"]*)"',
                r'"snapshot":\{[^}]*"body":"([^"]*)"'
            ])
            
            link_url = self._extract(ctx, [
                r'"link_url":"([^"]+)"',
                r'"ad_creative_link_urls":\["([^"]+)"',
                r'"snapshot":\{[^}]*"link_url":"([^"]+)"'
            ])
            
            cta = self._extract(ctx, [
                r'"cta_text":"([^"]+)"',
                r'"call_to_action":"([^"]+)"'
            ])
            
            start_time = self._extract(ctx, [
                r'"ad_delivery_start_time":"?(\d+)"?',
                r'"creation_time":"?(\d+)"?'
            ])
            
            # Quality gate: skip ads with no identifiable page data
            if page_id == "unknown" and page_name == "Unknown Page":
                continue
            
            raw_node = {
                "id": ad_id,
                "ad_archive_id": ad_id,
                "page": {"id": page_id, "name": page_name},
                "snapshot": {"body": body, "link_url": link_url, "cta_text": cta},
                "body": body,
                "ad_delivery_start_time": start_time
            }
            
            try:
                ad = normalize_meta_ad(raw_node, country)
                ads.append(ad)
                seen.add(ad_id)
            except Exception:
                continue
                
        return ads

    def _extract(self, text: str, patterns: list[str], default=None):
        for p in patterns:
            m = re.search(p, text)
            if m: return m.group(1)
        return default
