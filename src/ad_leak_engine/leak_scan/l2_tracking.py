"""L2 Scanner: Detects tracking and measurement leaks via network logs."""
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner

class L2TrackingScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L2"

    def scan(self, page: Page) -> list[Leak]:
        from ..shared.intent import classify_intent_from_page, has_strong_ecommerce_evidence, expected_events_for_intent
        from ..shared.telemetry_language import waf_markers_in_text, telemetry_reason, precise_telemetry_recommendation
        import re as _re_l2
        import json as _json_l2

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

        # --- [SEED: 2399] DEEP PACKET INSPECTION (CAPI PAYLOAD PARSER) ---
        capi_detected = False
        capi_pixel_id = None
        capi_events_found = []  # List of event names extracted from bodies
        capi_forensic_evidence = [] # List of strings for report
        
        _capi_pattern = _re_l2.compile(r'graph\.facebook\.com/v\d+\.\d+/(\d+)/events', _re_l2.IGNORECASE)

        for r in reqs:
            url = ""
            method = ""
            status = 0
            body = ""
            
            if isinstance(r, dict):
                url = str(r.get("url", ""))
                method = str(r.get("method", "")).upper()
                status = int(r.get("status_code", 0))
                # Attempt to get body/post_data
                body = r.get("post_data") or r.get("body") or ""
            else:
                continue
            
            match = _capi_pattern.search(url)
            if match and method == "POST":
                capi_detected = True
                capi_pixel_id = match.group(1)
                
                # Parse Body for Event Names
                try:
                    # Try JSON parse first
                    data = _json_l2.loads(body) if body else {}
                    
                    # Meta CAPI structure: {"data": [{"event_name": "..."}, ...]}
                    events_list = data.get("data", [])
                    if isinstance(events_list, list):
                        for ev in events_list:
                            if isinstance(ev, dict):
                                name = ev.get("event_name", "").strip()
                                if name:
                                    capi_events_found.append(name.lower())
                                    
                    # Fallback: Check top level if structure varies
                    elif "event_name" in data:
                         capi_events_found.append(str(data["event_name"]).lower())
                         
                except Exception:
                    pass # Ignore malformed JSON, rely on URL detection only
                
                # Construct Forensic String
                sample_ev = capi_events_found[-1] if capi_events_found else "UNKNOWN"
                capi_forensic_evidence.append(f"CAPISniff: {url} | Pixel: {capi_pixel_id} | Events: [{sample_ev}]")

        # Determine Tracking Architecture
        browser_pixel_active = pixel_fired or any("fbevents.js" in str(r.get("url","")).lower() for r in reqs if isinstance(r, dict))
        server_capi_active = capi_detected

        tracking_architecture = "NONE"
        if browser_pixel_active and server_capi_active:
            tracking_architecture = "HYBRID"
        elif browser_pixel_active:
            tracking_architecture = "BROWSER_ONLY"
        elif server_capi_active:
            tracking_architecture = "SERVER_ONLY"

        # Early Exit for Blocked/WAF scenarios
        if fetch_blocked or waf_blocked or (req_count < 5 and not browser_pixel_active and not server_capi_active):
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
                    "tracking_architecture": tracking_architecture,
                    "capi_sniffer_status": "ACTIVE_SNIFFING_FAILED_BLOCKED"
                },
            )]

        leaks = []

        # --- LEAK GENERATION BASED ON ARCHITECTURE ---

        # Case 1: No Tracking At All
        if tracking_architecture == "NONE":
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="no_tracking_infrastructure",
                severity=0.95,
                evidence={
                    "browser_pixel_detected": False,
                    "server_capi_detected": False,
                    "analyzed_requests_count": req_count,
                    "forensic_note": "Zero FB/Meta API calls observed in network trace."
                },
                recommendation="CRITICAL: Install Meta Pixel (Client) AND configure Server-Side CAPI (Backend)."
            ))
            
        # Case 2: Browser Only (Vulnerable to AdBlockers/iOS14+)
        elif tracking_architecture == "BROWSER_ONLY":
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="client_side_only_risk",
                severity=0.75,
                evidence={
                    "browser_pixel_detected": True,
                    "server_capi_detected": False,
                    "risk_factor": "AdBlocker/Ios14+ Data Loss (~30-40%)",
                    "forensic_note": "Pixel fires in browser, but NO server-side backup detected."
                },
                recommendation="HIGH RISK: Implement Server-Side CAPI to deduplicate and recover lost events from ad-blocked users."
            ))

        # Case 3: Server Only (Rare, usually means broken client setup)
        elif tracking_architecture == "SERVER_ONLY":
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="server_side_orphan_risk",
                severity=0.60,
                evidence={
                    "browser_pixel_detected": False,
                    "server_capi_detected": True,
                    "capi_pixel_id": capi_pixel_id,
                    "forensic_note": "; ".join(capi_forensic_evidence[:3])
                },
                recommendation="WARNING: CAPI is active but Browser Pixel is missing. Ensure GTM/Pixel base code is loaded for full-funnel attribution."
            ))

        # Case 4: Hybrid (Ideal State) - Check for Depth Gaps
        elif tracking_architecture == "HYBRID":
            pass # Proceed to depth check below

        # --- EVENT DEPTH ANALYSIS (Uses PARSED EVENTS) ---
        
        # Combine parsed CAPI events with legacy net_log events
        all_observed_events = set(capi_events_found)
        
        # Add legacy structured events if available
        for e in (net_log.get("capi_events", []) or []):
            if isinstance(e, dict):
                all_observed_events.add(str(e.get("event_name", "")).lower())
            else:
                all_observed_events.add(str(e).lower())

        allow_ecom_leaks = bool(
            strong_ecom
            or net_log.get("is_checkout_page")
            or intent.get("primary") == "ecommerce_store"
            or intent.get("primary") == "unknown"
        )

        if allow_ecom_leaks:
            expected = expected_events_for_intent(intent.get("primary"))
            missing_expected = [ev for ev in expected if ev.lower() not in all_observed_events]

            if len(missing_expected) >= 2:
                leaks.append(Leak(
                    page_id=page.id,
                    tier="L2",
                    signal="retargeting_event_depth_gap",
                    severity=0.65,
                    recommendation=(
                        f"Architecture: {tracking_architecture}. Key events missing: "
                        + ", ".join(missing_expected[:6])
                        + ". Retargeting audiences will be thin without these events."
                    ),
                    evidence={
                        "intent": intent.get("primary"),
                        "expected_events": expected,
                        "missing_events": missing_expected,
                        "observed_events": list(all_observed_events)[:20],
                        "tracking_architecture": tracking_architecture,
                        "capi_sniffer_status": "ACTIVE_PARSED" if capi_events_found else "ACTIVE_URL_ONLY"
                    },
                ))

        # Remove Legacy Checks that cause False Positives when CAPI is active but unparsed previously
        # We now rely on the parsed `all_observed_events` above.
        
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

