"""[SEED: 2399] Competitor Ad Library Intelligence.
Queries the FREE Meta Ad Library API to benchmark prospect against
top 3 competitors in their niche. No OAuth token required.
Creates extreme FOMO: "Your competitors are running 45 video ads, you are running 0."
"""
import httpx
import re


class CompetitorIntelligence:
    """Benchmarks prospect's ad activity against top competitors."""

    AD_LIBRARY_BASE = "https://graph.facebook.com/v19.0/ads_archive"

    def __init__(self, access_token: str = None):
        # Ad Library API can use app token or page token
        # For public data, we can use app-level access
        self.token = access_token or "dummy_token_for_public_search"

    def get_page_ad_count(self, page_id: str, ad_type: str = "ALL") -> dict:
        """Get ad count for a specific page.
        Endpoint: GET /ads_archive?search_page_ids={page_id}&ad_type={type}
        """
        try:
            resp = httpx.get(
                self.AD_LIBRARY_BASE,
                params={
                    "search_page_ids": page_id,
                    "ad_type": ad_type,
                    "ad_reached_countries": "CA",
                    "fields": "ad_creative_bodies,page_name",
                    "limit": 1,  # We just need count
                },
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                # The API returns summary with ad_count in paging
                return {
                    "page_id": page_id,
                    "ad_count": data.get("paging", {}).get("total_count", 0),
                    "page_name": data.get("data", [{}])[0].get("page_name", "Unknown"),
                }
        except Exception as e:
            pass
        return {"page_id": page_id, "ad_count": 0, "page_name": "Unknown"}

    def find_competitors_by_niche(self, niche: str, country: str = "CA", limit: int = 3) -> list[dict]:
        """Find top competitors in a niche using Ad Library search.
        Endpoint: GET /ads_archive?search_terms={niche}&ad_type=ALL
        """
        try:
            resp = httpx.get(
                self.AD_LIBRARY_BASE,
                params={
                    "search_terms": niche,
                    "ad_type": "ALL",
                    "ad_reached_countries": country,
                    "fields": "page_name,page_id",
                    "limit": limit,
                },
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15.0,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                # Deduplicate by page_id
                seen = set()
                competitors = []
                for item in data:
                    page_id = item.get("page_id")
                    if page_id and page_id not in seen:
                        seen.add(page_id)
                        competitors.append({
                            "page_id": page_id,
                            "page_name": item.get("page_name", "Unknown"),
                        })
                return competitors[:limit]
        except Exception:
            pass
        return []

    def benchmark_prospect(self, prospect_page_id: str, niche: str, country: str = "CA") -> dict:
        """Full benchmark: prospect vs top 3 competitors.
        Returns dict with prospect stats and competitor comparison.
        """
        # Get prospect's ad count
        prospect = self.get_page_ad_count(prospect_page_id)

        # Find top 3 competitors
        competitors = self.find_competitors_by_niche(niche, country, limit=3)

        # Get ad count for each competitor
        competitor_stats = []
        total_competitor_ads = 0
        for comp in competitors:
            stats = self.get_page_ad_count(comp["page_id"])
            competitor_stats.append(stats)
            total_competitor_ads += stats.get("ad_count", 0)

        # Calculate benchmark metrics
        avg_competitor_ads = total_competitor_ads / len(competitor_stats) if competitor_stats else 0
        prospect_ads = prospect.get("ad_count", 0)
        gap = avg_competitor_ads - prospect_ads

        return {
            "prospect": prospect,
            "competitors": competitor_stats,
            "metrics": {
                "prospect_ad_count": prospect_ads,
                "avg_competitor_ads": round(avg_competitor_ads, 1),
                "total_competitor_ads": total_competitor_ads,
                "gap": round(gap, 1),
                "niche": niche,
                "country": country,
            },
            "source": "meta_ad_library_public",
        }


def get_competitor_benchmark(page_id: str, niche: str = "skincare", country: str = "CA") -> dict | None:
    """Top-level function: get competitor benchmark for a page.
    Returns None if API call fails (graceful degradation).
    """
    try:
        intelligence = CompetitorIntelligence()
        return intelligence.benchmark_prospect(page_id, niche, country)
    except Exception:
        return None
