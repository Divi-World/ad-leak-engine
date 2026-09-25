"""L1 Scanner: Detects creative and strategy leaks from RawAd data."""
from datetime import datetime, timezone
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner
from ..shared.constants import (
    CREATIVE_FATIGUE_DAYS, MIN_AB_VARIATION_ADS, 
    SPEND_WITHOUT_TESTING_USD, SPEND_WITHOUT_TESTING_MIN_ADS
)

class L1CreativeScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L1"

    def scan(self, page: Page) -> list[Leak]:
        leaks = []
        active_ads = page.active_ads
        if not active_ads:
            return leaks

        now = datetime.now(timezone.utc)
        
        # 1. Creative fatigue
        oldest_ad = min(active_ads, key=lambda a: a.start_date)
        days_running = (now - oldest_ad.start_date).days
        if days_running > CREATIVE_FATIGUE_DAYS:
            severity = min(0.9, 0.7 + (days_running - CREATIVE_FATIGUE_DAYS) / 100)
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="creative_fatigue",
                severity=severity,
                evidence={"days_running": days_running, "oldest_ad_id": oldest_ad.id},
                recommendation=f"Oldest ad has run {days_running} days. Refresh creative."
            ))

        # 2. No A/B variation
        if len(active_ads) < MIN_AB_VARIATION_ADS:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="no_ab_variation",
                severity=0.6,
                evidence={"active_ad_count": len(active_ads)},
                recommendation=f"Only {len(active_ads)} active ads. Launch variants."
            ))

        # 3. No video creative
        if not any(a.media_type == "VIDEO" for a in active_ads):
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="no_video_creative",
                severity=0.5,
                evidence={"media_types": list(set(a.media_type for a in active_ads))},
                recommendation="No video ads detected. Add video creatives."
            ))

        # 4. Spend without testing
        lower_spend, _ = page.total_estimated_spend
        if lower_spend > SPEND_WITHOUT_TESTING_USD and len(active_ads) < SPEND_WITHOUT_TESTING_MIN_ADS:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="spend_without_testing",
                severity=0.8,
                evidence={"lower_spend": lower_spend, "active_ad_count": len(active_ads)},
                recommendation="High spend with low ad variation. A/B test immediately."
            ))

        # 5. Missing CTA
        missing_cta_count = sum(1 for a in active_ads if not a.cta or a.cta.lower() in ["learn more", ""])
        if missing_cta_count == len(active_ads) and len(active_ads) > 0:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="missing_cta",
                severity=0.5,
                evidence={"missing_cta_count": missing_cta_count},
                recommendation="All ads use weak or missing CTAs. Use action-oriented CTAs."
            ))
            
        # [SEED: 2399] Advanced L1 Signals
        for ad in active_ads:
            if 'detect_generic_hook' in globals() and detect_generic_hook(ad):
                leaks.append(Leak(page_id=page.id, tier="L1", signal="generic_hook", severity=0.6, recommendation="Add specific geo or pain point to copy", evidence={"ad_id": ad.id}))
        if 'detect_no_retargeting' in globals() and detect_no_retargeting(page):
            leaks.append(Leak(page_id=page.id, tier="L1", signal="no_retargeting", severity=0.7, recommendation="Implement custom audience retargeting", evidence={}))

        return leaks



def detect_generic_hook(ad) -> bool:
    body = (ad.body or "").lower()
    # Heuristic: lacks specific geo or pain point
    cities = ["new york", "london", "tokyo", "los angeles", "miami"]
    pain_points = ["struggle", "tired of", "frustrated", "hate"]
    has_city = any(city in body for city in cities)
    has_pain = any(pain in body for pain in pain_points)
    return not has_city and not has_pain and len(body) > 20

def detect_no_retargeting(page) -> bool:
    # Heuristic: All ads target broad, no custom audience indicators in raw data
    return True # Placeholder for broad targeting heuristic

