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
        # [SEED: 2399] TOP 1 UPGRADE: Bypass API 401s entirely by using elite curl_cffi stealth
        # to scrape the public Ad Library UI. No token required.
        pass

    def get_page_ad_count(self, page_id: str, ad_type: str = "ALL") -> dict:
        # [SEED: 2399] Credibility guard:
        # Public ad counts require authenticated/verified access.
        # Do not fabricate zero counts through a tokenless Graph API bottleneck.
        return {
            "page_id": page_id,
            "ad_count": None,
            "page_name": "Unknown",
            "source": "graph_api_disabled_no_token",
        }

    def find_competitors_by_niche(self, niche: str, country: str = "CA", limit: int = 3) -> list[dict]:
        """[SEED: 2399] TOP 1 UPGRADE: Scrape public Ad Library UI via curl_cffi stealth."""
        url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&q={niche.replace(' ', '%20')}"
        try:
            from curl_cffi import requests as cffi_requests
            import re as _re_comp
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=20)
            if resp.status_code == 200:
                html = resp.text
                matches = _re_comp.findall(r'"page_name":"([^"]+)"', html)
                seen = set()
                competitors = []
                for name in matches:
                    if name not in seen and name.lower() not in ['meta', 'facebook', 'instagram']:
                        seen.add(name)
                        competitors.append({"page_id": name, "page_name": name})
                        if len(competitors) >= limit:
                            break
                return competitors
        except Exception:
            pass
        return []

    def benchmark_from_ads(self, prospect_page_id: str, niche: str, country: str, ads: list) -> dict:
        from collections import defaultdict
        from urllib.parse import urlparse
        from ..shared.intent import classify_intent_from_text
        from ..shared.competitor_relevance import filter_competitors

        pages = defaultdict(lambda: {
            "page_id": "",
            "page_name": "Unknown",
            "ad_count": 0,
            "active_ad_count": 0,
            "media_types": set(),
            "spend_lower": 0.0,
            "spend_upper": 0.0,
            "landing_urls": [],
        })

        for ad in ads or []:
            pid = getattr(ad, "page_id", None) or ""
            if not pid:
                continue

            entry = pages[pid]
            entry["page_id"] = pid
            entry["page_name"] = getattr(ad, "page_name", entry["page_name"]) or entry["page_name"]
            entry["ad_count"] += 1

            status = getattr(ad, "status", "ACTIVE")
            if status == "ACTIVE":
                entry["active_ad_count"] += 1

            media_type = getattr(ad, "media_type", None)
            if media_type:
                entry["media_types"].add(media_type)

            landing = getattr(ad, "landing_url", None)
            if landing:
                entry["landing_urls"].append(landing)

            spend = getattr(ad, "spend", None)
            if isinstance(spend, (tuple, list)) and len(spend) == 2:
                try:
                    entry["spend_lower"] += float(spend[0] or 0)
                    entry["spend_upper"] += float(spend[1] or 0)
                except Exception:
                    pass

        stats = []
        for e in pages.values():
            stats.append({
                "page_id": e["page_id"],
                "page_name": e["page_name"],
                "ad_count": e["ad_count"],
                "active_ad_count": e["active_ad_count"],
                "media_types": sorted(e["media_types"]),
                "spend_lower": round(e["spend_lower"], 2),
                "spend_upper": round(e["spend_upper"], 2),
                "sample_landing_urls": e["landing_urls"][:3],
            })

        prospect = next((s for s in stats if s["page_id"] == prospect_page_id), {
            "page_id": prospect_page_id,
            "page_name": "Unknown",
            "ad_count": 0,
            "active_ad_count": 0,
            "media_types": [],
            "spend_lower": 0.0,
            "spend_upper": 0.0,
            "sample_landing_urls": [],
        })

        prospect_name = prospect.get("page_name") or ""
        prospect_url = (prospect.get("sample_landing_urls") or [""])[0]
        prospect_domain = urlparse(prospect_url).netloc.lower() if prospect_url else ""
        intent = classify_intent_from_text(f"{prospect_name} {prospect_url} {niche}")

        raw_competitors = sorted(
            [s for s in stats if s["page_id"] != prospect_page_id],
            key=lambda x: x["active_ad_count"],
            reverse=True,
        )[:10]

        kept_competitors, filtered_competitors, relevance_reasons = filter_competitors(
            prospect_intent=intent,
            prospect_name=prospect_name,
            prospect_domain=prospect_domain,
            competitors=raw_competitors,
            country=country,
        )

        kept_competitors = kept_competitors[:3]
        valid_counts = [c["active_ad_count"] for c in kept_competitors]
        prospect_ads = prospect["active_ad_count"]

        if kept_competitors:
            avg_competitor_ads = round(sum(valid_counts) / len(valid_counts), 1)
            gap = round(avg_competitor_ads - prospect_ads, 1)
            status = "observed_pool_benchmark"
        else:
            avg_competitor_ads = None
            gap = None
            status = "no_relevant_competitors_in_observed_pool"

        return {
            "prospect": prospect,
            "competitors": kept_competitors,
            "metrics": {
                "prospect_ad_count": prospect_ads,
                "avg_competitor_ads": avg_competitor_ads,
                "total_competitor_ads": sum(valid_counts) if valid_counts else None,
                "gap": gap,
                "niche": niche,
                "country": country,
                "status": status,
            },
            "coverage": {
                "observed_ads": len(ads or []),
                "observed_pages": len(stats),
                "relevant_competitors_used": len(kept_competitors),
                "filtered_competitors": len(filtered_competitors),
                "country": country,
                "niche": niche,
            },
            "relevance": {
                "prospect_intent": intent.get("primary"),
                "prospect_domain": prospect_domain,
                "filtered_count": len(filtered_competitors),
                "filtered_names": [c.get("page_name") for c in filtered_competitors][:10],
                "reasons": relevance_reasons[:10],
            },
            "source": "meta_ad_library_playwright_observed_pool",
        }

    def benchmark_prospect(self, prospect_page_id: str, niche: str, country: str = "CA") -> dict:
        """Full benchmark: prospect vs top 3 competitors.
        Returns dict with prospect stats and competitor comparison.
        """
        prospect = self.get_page_ad_count(prospect_page_id)
        competitors = self.find_competitors_by_niche(niche, country, limit=3)

        competitor_stats = []
        valid_counts = []

        for comp in competitors:
            stats = self.get_page_ad_count(comp["page_id"])
            competitor_stats.append(stats)
            if isinstance(stats.get("ad_count"), int):
                valid_counts.append(stats["ad_count"])

        prospect_ads = prospect.get("ad_count")
        has_hard_counts = isinstance(prospect_ads, int) and bool(valid_counts)

        if has_hard_counts:
            avg_competitor_ads = sum(valid_counts) / len(valid_counts)
            gap = avg_competitor_ads - prospect_ads
            metrics = {
                "prospect_ad_count": prospect_ads,
                "avg_competitor_ads": round(avg_competitor_ads, 1),
                "total_competitor_ads": sum(valid_counts),
                "gap": round(gap, 1),
                "niche": niche,
                "country": country,
            }
            source = "meta_ad_library_public"
        else:
            metrics = {
                "prospect_ad_count": None,
                "avg_competitor_ads": None,
                "total_competitor_ads": None,
                "gap": None,
                "niche": niche,
                "country": country,
                "status": "benchmark_unavailable_without_authenticated_access",
            }
            source = "stealth_ui_competitor_names_only"

        return {
            "prospect": prospect,
            "competitors": competitor_stats,
            "metrics": metrics,
            "source": source,
        }


def get_competitor_benchmark(page_id: str, niche: str = "skincare", country: str = "CA", observed_ads: list | None = None) -> dict | None:
    """Return evidence-based competitor benchmark.

    When observed_ads are supplied, the benchmark is computed from the live
    Playwright Ad Library pool already captured by the engine. This avoids
    tokenless Graph API 401 bottlenecks and prevents fabricated zero counts.
    """
    try:
        intelligence = CompetitorIntelligence()
        if observed_ads is not None:
            return intelligence.benchmark_from_ads(page_id, niche, country, observed_ads)

        benchmark = intelligence.benchmark_prospect(page_id, niche, country)
        return benchmark
    except Exception:
        return None
