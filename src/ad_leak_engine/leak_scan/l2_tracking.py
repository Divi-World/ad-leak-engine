"""L2 Scanner: Detects tracking and measurement leaks via network logs."""
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner

class L2TrackingScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L2"

    def scan(self, page: Page) -> list[Leak]:
        from ..shared.intent import classify_intent_from_page, has_strong_ecommerce_evidence, expected_events_for_intent
        from ..shared.telemetry_language import waf_markers_in_text, telemetry_reason, precise_telemetry_recommendation

        raw = getattr(page, "raw", None) or {}
        if not isinstance(raw, dict):
            raw = {}

        html = raw.get("html") or ""
        net_log = raw.get("network_log", {}) or {}
        if not isinstance(net_log, dict):
            net_log = {}

        reqs = net_log.get("requests", []) or []
        if not isinstance(reqs, list):
            reqs = []

        req_count = len(reqs)
        pixel_fired = bool(net_log.get("pixel_fired", False))
        fetch_blocked = bool(raw.get("fetch_blocked", False))
        waf_markers = waf_markers_in_text(html)
        waf_blocked = bool(net_log.get("waf_blocked", False)) or bool(waf_markers)

        intent = classify_intent_from_page(page)
        strong_ecom, ecommerce_hits = has_strong_ecommerce_evidence(page, intent)
        reason = telemetry_reason(
            waf_blocked=waf_blocked,
            request_count=req_count,
            fetch_blocked=fetch_blocked,
            pixel_fired=pixel_fired,
        )

        if fetch_blocked or waf_blocked or (req_count < 5 and not pixel_fired):
            return [Leak(
                page_id=page.id,
                tier="L2",
                signal="telemetry_blind_spot",
                severity=0.60,
                recommendation=precise_telemetry_recommendation(reason),
                evidence={
                    "network_requests": f"Analyzed {req_count} network requests.",
                    "waf_blocked": waf_blocked,
                    "waf_markers": waf_markers,
                    "fetch_blocked": fetch_blocked,
                    "telemetry_reason_code": reason.get("code"),
                    "possible_causes": reason.get("causes", []),
                    "prospect_intent": intent.get("primary"),
                },
            )]

        leaks = []

        pixel_in_urls = False
        request_urls = []
        for r in reqs:
            url = ""
            if isinstance(r, dict):
                url = str(r.get("url", ""))
            else:
                url = str(r)
            request_urls.append(url)
            low = url.lower()
            if "fbevents.js" in low or "facebook.com/tr" in low or "connect.facebook.net" in low:
                pixel_in_urls = True

        if not pixel_fired and not pixel_in_urls:
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="pixel_not_firing",
                severity=0.95,
                evidence={
                    "network_requests": request_urls[:20],
                    "request_count": req_count,
                    "pixel_script_detected": False,
                    "pixel_pageview_observed": False,
                },
                recommendation="Meta Pixel not detected on landing page. Install base code.",
            ))
        elif not pixel_fired and pixel_in_urls:
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="pixel_script_detected_but_not_firing",
                severity=0.75,
                evidence={
                    "network_requests": request_urls[:20],
                    "request_count": req_count,
                    "pixel_script_detected": True,
                    "pixel_pageview_observed": False,
                },
                recommendation="Meta Pixel scripts were detected, but a PageView event was not observed. Check consent mode, GTM triggers, or delayed script loading.",
            ))

        if net_log.get("has_unhashed_pii", False):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="unhashed_pii",
                severity=0.8,
                evidence={"capi_payload_sample": net_log.get("capi_sample", {})},
                recommendation="CAPI payload contains unhashed PII. Hash em/ph/fn/ln via SHA-256.",
            ))

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

        if net_log.get("is_checkout_page") and not has_event("Purchase"):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="missing_purchase_event",
                severity=0.9,
                recommendation="No Purchase event fired on checkout page.",
                evidence={"is_checkout_page": True, "observed_events": capi_events[:20]},
            ))

        if "detect_capi_dedup_failure" in globals() and detect_capi_dedup_failure(net_log):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="capi_dedup_failure",
                severity=0.85,
                recommendation="Sync event_id between pixel and CAPI",
                evidence={},
            ))

        allow_ecom_leaks = bool(
            strong_ecom
            or net_log.get("is_checkout_page")
            or intent.get("primary") == "ecommerce_store"
            or intent.get("primary") == "unknown"
        )

        if allow_ecom_leaks and "detect_missing_initiate_checkout" in globals() and detect_missing_initiate_checkout(net_log):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="missing_initiate_checkout",
                severity=0.7,
                recommendation="Add InitiateCheckout event",
                evidence={"ecommerce_evidence": ecommerce_hits[:10], "intent": intent.get("primary")},
            ))

        if allow_ecom_leaks and "detect_missing_add_to_cart" in globals() and detect_missing_add_to_cart(net_log):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="missing_add_to_cart",
                severity=0.6,
                recommendation="Add AddToCart event",
                evidence={"ecommerce_evidence": ecommerce_hits[:10], "intent": intent.get("primary")},
            ))

        if "detect_attribution_gap" in globals() and detect_attribution_gap(page, net_log):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="attribution_gap",
                severity=0.9,
                recommendation="Ad Library shows spend but no conversion signals. Flying blind on ROAS.",
                evidence={},
            ))

        pixel_integrity_signals = {"pixel_not_firing", "pixel_script_detected_but_not_firing"}
        if any(getattr(l, "signal", None) in pixel_integrity_signals for l in leaks):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="retargeting_pool_integrity_risk",
                severity=0.75,
                recommendation="Pixel/CAPI telemetry is missing or unreliable, so retargeting pools cannot be trusted. Restore browser and server-side event flow before scaling retargeting.",
                evidence={
                    "pixel_fired": pixel_fired,
                    "pixel_script_detected": pixel_in_urls,
                    "request_count": req_count,
                    "prospect_intent": intent.get("primary"),
                },
            ))

        expected = expected_events_for_intent(intent.get("primary"))
        missing_expected = [ev for ev in expected if not has_event(ev)]

        if (
            intent.get("primary") not in ("unknown", "brand_awareness")
            and req_count >= 8
            and pixel_fired
            and len(missing_expected) >= 2
        ):
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="retargeting_event_depth_gap",
                severity=0.65,
                recommendation=(
                    f"This prospect appears {intent.get('primary').replace('_', ' ')}-oriented, but key events were not observed: "
                    + ", ".join(missing_expected[:6])
                    + ". Retargeting and attribution audiences will be thin without these events."
                ),
                evidence={
                    "intent": intent.get("primary"),
                    "expected_events": expected,
                    "missing_events": missing_expected,
                    "observed_events": capi_events[:20],
                    "request_count": req_count,
                },
            ))

        return leaks



def detect_capi_dedup_failure(telemetry) -> bool:
    # Check if browser and server events lack shared event_id
    return not telemetry.get("has_shared_event_id", True)

def detect_missing_initiate_checkout(telemetry) -> bool:
    return not telemetry.get("has_initiate_checkout", False)

def detect_missing_add_to_cart(telemetry) -> bool:
    return not telemetry.get("has_add_to_cart", False)

def detect_attribution_gap(page, telemetry) -> bool:
    # Ad Library shows spend but no conversion signals
    has_spend = page.total_estimated_spend[1] > 0 if page.total_estimated_spend else False
    has_conversions = telemetry.get("has_purchase_event", False)
    return has_spend and not has_conversions

