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
                leaks.append(Leak(
                    page_id=page.id,
                    tier="L1",
                    signal="generic_hook",
                    severity=0.6,
                    recommendation="Add specific geo or pain point to copy",
                    evidence={"ad_id": ad.id, "ad_body": ad.body or ""}
                ))

        # [SEED: 2399] Evidence-based retargeting intelligence.
        # This does not claim private audience knowledge. It reports absence of
        # retargeting/BOFU markers in the observed public Meta Ad Library pool.
        retarget_gap, retarget_evidence = detect_retargeting_gap(page)
        if retarget_gap:
            leaks.append(Leak(
                page_id=page.id,
                tier="L1",
                signal="retargeting_gap_not_observed",
                severity=0.55,
                recommendation=(
                    "No retargeting/BOFU audience markers were observed in the sampled "
                    "Meta Ad Library pool. Implement or verify cart/view/video/purchase "
                    "retargeting sequences using pixel and CAPI custom audiences."
                ),
                evidence=retarget_evidence
            ))

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
    # [SEED: 2399] Legacy compatibility guard.
    # The old boolean claim was hallucination-prone. Real evidence is now handled
    # by detect_retargeting_gap(), which returns observed-pool evidence.
    return False


def detect_retargeting_gap(page) -> tuple[bool, dict]:
    from ..shared.intent import classify_intent_from_page, expected_events_for_intent
    from urllib.parse import urlparse, parse_qs

    ads = getattr(page, "active_ads", []) or []
    if not ads:
        return False, {}

    raw = getattr(page, "raw", None) or {}
    if not isinstance(raw, dict):
        raw = {}

    net_log = raw.get("network_log", {}) or {}
    if not isinstance(net_log, dict):
        net_log = {}

    intent = classify_intent_from_page(page)

    retarget_terms = (
        "retarget", "remarket", "rt", "cart", "abandon", "view", "video",
        "purchase", "lead", "warm", "engaged", "visitor", "sequence", "seq",
        "funnel", "bofu", "mofu", "bottom", "mid",
    )

    prospecting_terms = (
        "prospect", "prospecting", "cold", "new", "broad", "interest",
        "lookalike", "lal", "tofu", "top", "acquisition", "general",
    )

    sampled_urls = []
    retarget_hits = []
    prospecting_hits = []
    request_urls = []

    for r in (net_log.get("requests", []) or []):
        if isinstance(r, dict):
            request_urls.append(str(r.get("url", "")))
        else:
            request_urls.append(str(r))

    capi_events = []
    for e in (net_log.get("capi_events", []) or []):
        if isinstance(e, dict):
            capi_events.append(str(e.get("event_name", "")))
        else:
            capi_events.append(str(e))

    event_blob = " ".join(capi_events + request_urls).lower()

    def has_event(name: str) -> bool:
        n = (name or "").lower().replace(" ", "")
        aliases = {
            "initiatecheckout": "initiate_checkout",
            "addtocart": "add_to_cart",
            "pageview": "page_view",
            "viewcontent": "view_content",
        }
        key = "has_" + aliases.get(n, n)
        if net_log.get(key, False):
            return True
        if n in event_blob:
            return True
        if aliases.get(n) and aliases[n] in event_blob:
            return True
        return False

    for ad in ads[:50]:
        url = getattr(ad, "landing_url", "") or ""
        title = getattr(ad, "title", "") or ""
        body = getattr(ad, "body", "") or ""
        cta = getattr(ad, "cta", "") or ""

        blob = " ".join([url, title, body, cta]).lower()

        utm_blob = ""
        if url:
            sampled_urls.append(url)
            try:
                q = parse_qs(urlparse(url).query)
                utm_parts = [
                    (q.get("utm_campaign", [""])[0] or "").lower(),
                    (q.get("utm_content", [""])[0] or "").lower(),
                    (q.get("utm_term", [""])[0] or "").lower(),
                ]
                utm_blob = " ".join(utm_parts)
            except Exception:
                utm_blob = ""

        full_blob = f"{blob} {utm_blob}".lower()

        for term in retarget_terms:
            if term in full_blob and term not in retarget_hits:
                retarget_hits.append(term)

        for term in prospecting_terms:
            if term in full_blob and term not in prospecting_hits:
                prospecting_hits.append(term)

    expected = expected_events_for_intent(intent.get("primary"))
    event_coverage = {ev: has_event(ev) for ev in expected}

    evidence = {
        "sampled_active_ads": len(ads),
        "sampled_urls": sampled_urls[:10],
        "retarget_markers_observed": retarget_hits,
        "prospecting_markers_observed": prospecting_hits,
        "prospect_intent": intent.get("primary"),
        "expected_events": expected,
        "event_coverage": event_coverage,
        "interpretation": (
            "No retargeting/BOFU markers were observed in the sampled public "
            "Meta Ad Library pool for this prospect."
        ),
    }

    if retarget_hits:
        return False, evidence

    return True, evidence


