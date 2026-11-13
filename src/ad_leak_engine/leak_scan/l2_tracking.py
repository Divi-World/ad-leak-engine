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
        capi_detected_dynamic = False
        capi_pixel_id_dynamic = None
        capi_events_found = []
        capi_forensic_evidence = []

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
                body = r.get("post_data") or r.get("body") or ""
            else:
                continue

            match = _capi_pattern.search(url)
            if match and method == "POST":
                capi_detected_dynamic = True
                capi_pixel_id_dynamic = match.group(1)

                try:
                    data = _json_l2.loads(body) if body else {}
                    events_list = data.get("data", [])
                    if isinstance(events_list, list):
                        for ev in events_list:
                            if isinstance(ev, dict):
                                name = ev.get("event_name", "").strip()
                                if name:
                                    capi_events_found.append(name.lower())
                    elif "event_name" in data:
                         capi_events_found.append(str(data["event_name"]).lower())
                except Exception:
                    pass

                sample_ev = capi_events_found[-1] if capi_events_found else "UNKNOWN"
                capi_forensic_evidence.append(f"CAPISniff: {url} | Pixel: {capi_pixel_id_dynamic} | Events: [{sample_ev}]")

        # --- [SEED: 2399] STATIC CAPI INFERENCE (NEW FEATURE) ---
        # If dynamic CAPI wasn't caught (common on Homepages), check JS Bundles for CAPI Config
        capi_detected_static = False
        capi_pixel_id_static = None

        # Common patterns in Shopify/WooCommerce Customer Events bundles
        _static_capi_patterns = [
            r'"capi_enabled"\s*:\s*true',
            r'shopify\.analytics\.sendEvent\s*\(\s*[\'"]Purchase[\'"]',
            r'window\.fbq\s*\(\s*[\'"]track[\'"],\s*[\'"]InitiateCheckout[\'"]',
            r'/v\d+\.\d+/\d+/events', # Generic Graph API path in JS strings
        ]

        combined_js_source = html + "".join([str(r.get("response_body", "") or r.get("body", "")) for r in reqs if isinstance(r, dict)])

        for pattern in _static_capi_patterns:
            if _re_l2.search(pattern, combined_js_source, _re_l2.IGNORECASE):
                capi_detected_static = True
                break

        # Extract Static Pixel ID if available in config objects
        if capi_detected_static:
            m_static_id = _re_l2.search(r'"pixelId"\s*:\s*"(\d{8,})"', combined_js_source)
            if m_static_id:
                capi_pixel_id_static = m_static_id.group(1)

        # Merge Dynamic and Static Findings
        capi_detected = capi_detected_dynamic or capi_detected_static
        capi_pixel_id = capi_pixel_id_dynamic or capi_pixel_id_static

        # [SEED: 2399] ROBUST PIXEL ID EXTRACTION (MULTI-SOURCE)
        detected_browser_pixel_id = None

        browser_pixel_active = pixel_fired or any("fbevents.js" in str(r.get("url","")).lower() for r in reqs if isinstance(r, dict))

        if browser_pixel_active:
            # Strategy 1: HTML Source
            if html:
                m_html = _re_l2.search(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]\s*\)""", html)
                if m_html:
                    detected_browser_pixel_id = m_html.group(1)

            # Strategy 2: Network Body
            if not detected_browser_pixel_id:
                for r in reqs:
                    if not isinstance(r, dict): continue
                    body = str(r.get("response_body", "") or r.get("body", ""))
                    if "fbq('init'" in body or 'fbq("init"' in body:
                        m_body = _re_l2.search(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]\s*\)""", body)
                        if m_body:
                            detected_browser_pixel_id = m_body.group(1)
                            break

        server_capi_active = capi_detected

        # [FIX-2399] Primary pixel ID resolution — trust the probe's own extraction first.
        # The probe's probe()/probe_funnel() captures the pixel from the live browser
        # session (checkout / cart pages). This is authoritative. CAPI parsing and
        # HTML parsing remain fallbacks for the blocked case.
        primary_pixel_id = (
            net_log.get("detected_pixel_id")
            or raw.get("detected_pixel_id")
            or capi_pixel_id
            or detected_browser_pixel_id
        )

        # [FIX-2399] Surface the probe's Meta-side validation and tracking-mode
        # inference. Both are produced by probe()/probe_funnel() and are None-safe.
        _probe_pixel_validation = (
            net_log.get("pixel_validation")
            or raw.get("pixel_validation")
            or {}
        )
        _probe_tracking_mode = (
            net_log.get("tracking_mode_inferred")
            or raw.get("tracking_mode_inferred")
            or None
        )
        # [FIX-2399] Observed browser events from funnel (AddToCart, InitiateCheckout, Purchase, PageView, etc.)
        _probe_fbq_events = (
            net_log.get("fbq_events_observed")
            or raw.get("fbq_events_observed")
            or []
        )
        # [FIX-2399] Funnel step telemetry (list of 5 steps) — provides ground truth
        # that the probe actually walked the funnel.
        _probe_funnel_steps = (
            net_log.get("funnel_steps")
            or raw.get("funnel_steps")
            or []
        )

        # Determine Tracking Architecture
        tracking_architecture = "NONE"

        # Check for GTM presence as an indicator of managed tracking
        has_gtm = bool(net_log.get("gtm_id"))

        if browser_pixel_active and server_capi_active:
            tracking_architecture = "HYBRID"
        elif browser_pixel_active:
            tracking_architecture = "BROWSER_ONLY"
        elif server_capi_active:
            tracking_architecture = "SERVER_ONLY"
        elif has_gtm and req_count > 50:
            # If we see GTM and lots of traffic but no direct pixel, it's likely wrapped
            tracking_architecture = "MANAGED_VIA_TAG_MANAGER"

        # [FIX-2399] If the probe confirmed the pixel via Meta config and no browser
        # pixel fired, the store is at least CAPI-only even though we didn't see a
        # server-side request from the browser (CAPI is out-of-band). Override NONE.
        if tracking_architecture == "NONE" and _probe_pixel_validation.get("verdict") == "real_pixel_confirmed_by_config":
            if _probe_tracking_mode == "capi_only_likely":
                tracking_architecture = "SERVER_ONLY"
            elif _probe_tracking_mode == "browser_pixel_active":
                tracking_architecture = "BROWSER_ONLY"

        # Early Exit for Blocked/WAF scenarios
        if fetch_blocked or waf_blocked or (req_count < 5 and not browser_pixel_active and not server_capi_active):

            # [SEED: 2399] DISTINGUISH BETWEEN TOTAL BLOCK AND PARTIAL SUCCESS
            if net_log.get("blocked_status") == "ENTERPRISE_WAF_BLOCKED":
                 return [Leak(
                    page_id=page.id,
                    tier="L2",
                    signal="enterprise_security_wall",
                    severity=0.40, # Lower severity, it's a feature not a bug
                    recommendation="INTELLIGENCE: Your site utilizes advanced Enterprise-grade bot protection (Cloudflare/DataDome). Automated third-party audits may be restricted. Recommend manual verification via Meta Pixel Helper.",
                    evidence={
                        "network_requests": f"Analyzed {req_count} network requests.",
                        "waf_blocked": True,
                        "security_vendor": "Cloudflare Enterprise / Advanced WAF",
                        "telemetry_reason_code": "enterprise_block",
                        "prospect_intent": intent.get("primary"),
                        "tracking_architecture": "UNKNOWN_SECURED",
                        "capi_sniffer_status": "BLOCKED_BY_WALL",
                        "detected_pixel_id": primary_pixel_id,
                        "pixel_validation": _probe_pixel_validation,          # [FIX-2399]
                        "tracking_mode_inferred": _probe_tracking_mode,       # [FIX-2399]
                        "observed_events": _probe_fbq_events,                 # [FIX-2399]
                        "funnel_steps": _probe_funnel_steps,                  # [FIX-2399]
                    },
                )]

            # Existing logic for other blocks...
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
                    "capi_sniffer_status": "ACTIVE_SNIFFING_FAILED_BLOCKED",
                    "detected_pixel_id": primary_pixel_id,
                    "pixel_validation": _probe_pixel_validation,          # [FIX-2399]
                    "tracking_mode_inferred": _probe_tracking_mode,       # [FIX-2399]
                    "observed_events": _probe_fbq_events,                 # [FIX-2399]
                    "funnel_steps": _probe_funnel_steps,                  # [FIX-2399]
                },
            )]

        leaks = []

        # Case 1: No Tracking At All (Or Blocked/Cloaked)
        if tracking_architecture == "NONE":
            # Heuristic: High traffic (>50 reqs) but ZERO analytics signals suggests Bot Cloaking
            is_likely_cloaked = req_count > 50

            if is_likely_cloaked:
                leaks.append(Leak(
                    page_id=page.id,
                    tier="L2",
                    signal="enterprise_bot_cloaking_detected",
                    severity=0.40, # Informational, not critical failure
                    evidence={
                        "browser_pixel_detected": False,
                        "server_capi_detected": False,
                        "analyzed_requests_count": req_count,
                        "forensic_note": f"{req_count} network requests captured, but zero Meta Pixel/CAPI signatures found. High probability of Enterprise-grade Bot Cloaking serving sanitized HTML to automated probes.",
                        "detected_pixel_id": primary_pixel_id,                # [FIX-2399] was None
                        "pixel_validation": _probe_pixel_validation,          # [FIX-2399]
                        "tracking_mode_inferred": _probe_tracking_mode,       # [FIX-2399]
                        "observed_events": _probe_fbq_events,                 # [FIX-2399]
                        "funnel_steps": _probe_funnel_steps,                  # [FIX-2399]
                    },
                    recommendation="INTELLIGENCE: Your site employs advanced bot protection that hides analytics from automated scanners. This is standard for high-security brands. Verify manually using Chrome Extension."
                ))
            else:
                leaks.append(Leak(
                    page_id=page.id,
                    tier="L2",
                    signal="no_tracking_infrastructure",
                    severity=0.95,
                    evidence={
                        "browser_pixel_detected": False,
                        "server_capi_detected": False,
                        "analyzed_requests_count": req_count,
                        "forensic_note": "Low request volume (<50) and zero FB/Meta API calls observed. Likely true absence of tracking.",
                        "detected_pixel_id": primary_pixel_id,                # [FIX-2399] was None
                        "pixel_validation": _probe_pixel_validation,          # [FIX-2399]
                        "tracking_mode_inferred": _probe_tracking_mode,       # [FIX-2399]
                        "observed_events": _probe_fbq_events,                 # [FIX-2399]
                        "funnel_steps": _probe_funnel_steps,                  # [FIX-2399]
                    },
                    recommendation="CRITICAL: Install Meta Pixel (Client) AND configure Server-Side CAPI (Backend)."
                ))

        # NEW CASE: Managed via Tag Manager (Partial Visibility)
        elif tracking_architecture == "MANAGED_VIA_TAG_MANAGER":
            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="tag_manager_wrapped_tracking",
                severity=0.45, # Lower severity than missing entirely
                evidence={
                    "browser_pixel_detected": False,
                    "server_capi_detected": False,
                    "gtm_container_detected": net_log.get("gtm_id"),
                    "analyzed_requests_count": req_count,
                    "forensic_note": f"GTM Container ({net_log.get('gtm_id')}) detected. Pixel likely injected dynamically. Static analysis cannot confirm active firing without executing tags.",
                    "detected_pixel_id": primary_pixel_id,                    # [FIX-2399] was None
                    "pixel_validation": _probe_pixel_validation,              # [FIX-2399]
                    "tracking_mode_inferred": _probe_tracking_mode,           # [FIX-2399]
                    "observed_events": _probe_fbq_events,                     # [FIX-2399]
                    "funnel_steps": _probe_funnel_steps,                      # [FIX-2399]
                },
                recommendation="VERIFY: Open your GTM container and ensure the Facebook Pixel tag is active and firing on PageView. Automated audits may miss dynamic injections."
            ))

        # Case 2: Browser Only (On Homepage)
        elif tracking_architecture == "BROWSER_ONLY":
            # Enhanced Note: Explain WHY CAPI isn't seen (Scope Limitation)
            scope_note = "Server-Side CAPI events (Purchase/AddToCart) typically fire on Checkout/Confirmation pages. Since this audit covers the Homepage only, CAPI status is inferred as 'Unverified' unless static bundle analysis confirms its presence."

            leaks.append(Leak(
                page_id=page.id,
                tier="L2",
                signal="homepage_browser_only_observation",
                severity=0.60,
                evidence={
                    "browser_pixel_detected": True,
                    "server_capi_detected": False,
                    "risk_factor": "Potential Data Loss if CAPI is missing on Checkout",
                    "forensic_note": f"Meta Pixel ({primary_pixel_id}) detected on Homepage. {scope_note}",
                    "detected_pixel_id": primary_pixel_id,
                    "pixel_label": "Primary Conversion Pixel", # NEW CONTEXT
                    "pixel_validation": _probe_pixel_validation,              # [FIX-2399]
                    "tracking_mode_inferred": _probe_tracking_mode,           # [FIX-2399]
                    "observed_events": _probe_fbq_events,                     # [FIX-2399]
                    "funnel_steps": _probe_funnel_steps,                      # [FIX-2399]
                },
                recommendation="VERIFY: Confirm Server-Side CAPI is active on your Checkout flow. If missing, implement CAPI to prevent AdBlocker data loss."
            ))

        # Case 3: Server Only
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
                    "forensic_note": "; ".join(capi_forensic_evidence[:3]) if capi_forensic_evidence else "Static Bundle Analysis Confirmed CAPI Presence.",
                    "detected_pixel_id": primary_pixel_id,
                    "pixel_label": "Server-Side Only Pixel",
                    "pixel_validation": _probe_pixel_validation,              # [FIX-2399]
                    "tracking_mode_inferred": _probe_tracking_mode,           # [FIX-2399]
                    "observed_events": _probe_fbq_events,                     # [FIX-2399]
                    "funnel_steps": _probe_funnel_steps,                      # [FIX-2399]
                },
                recommendation="WARNING: CAPI is active but Browser Pixel is missing. Ensure GTM/Pixel base code is loaded for full-funnel attribution."
            ))

        # Case 4: Hybrid
        elif tracking_architecture == "HYBRID":
            pass

        # Event Depth Analysis
        # [FIX-2399] Include the probe's observed fbq track events when computing
        # which expected events are missing. Previously only CAPI events counted,
        # which underreported coverage on browser-active setups.
        all_observed_events = set(capi_events_found)
        for e in (net_log.get("capi_events", []) or []):
            if isinstance(e, dict):
                all_observed_events.add(str(e.get("event_name", "")).lower())
            else:
                all_observed_events.add(str(e).lower())
        for ev_name in _probe_fbq_events or []:
            all_observed_events.add(str(ev_name).lower())

        # [SEED: 2399] MULTI-VERTICAL EVENT DEPTH ANALYSIS
        # Now checks ALL intents (School, Hospital, Finance, etc.), not just Ecommerce.
        primary_intent = intent.get("primary")

        # Exclude Brand Awareness (no specific conversion events expected usually)
        if primary_intent != "brand_awareness":
            expected = expected_events_for_intent(primary_intent)

            # Only proceed if we actually expect events for this vertical
            if expected:
                missing_expected = [ev for ev in expected if ev.lower() not in all_observed_events]

                # Threshold: Flag if >50% of expected events are missing OR at least 2 missing
                threshold_met = len(missing_expected) >= max(2, int(len(expected) * 0.5))

                if threshold_met:
                    leaks.append(Leak(
                        page_id=page.id,
                        tier="L2",
                        signal=f"{primary_intent}_event_depth_gap", # Dynamic Signal Name
                        severity=0.65,
                        recommendation=(
                            f"Intent: {primary_intent.replace('_', ' ').title()}. "
                            f"Expected Events: {', '.join(expected)}. "
                            f"Missing/Observed Gap: {', '.join(missing_expected)}. "
                            "Configure Pixel/CAPI to capture these specific funnel stages."
                        ),
                        evidence={
                            "intent": primary_intent,
                            "expected_events": expected,
                            "missing_events": missing_expected,
                            "observed_events": list(all_observed_events)[:20],
                            "tracking_architecture": tracking_architecture,
                            "capi_sniffer_status": "ACTIVE_PARSED" if capi_events_found else ("STATIC_INFERRED" if capi_detected_static else "ACTIVE_URL_ONLY"),
                            "detected_pixel_id": primary_pixel_id,
                            "pixel_validation": _probe_pixel_validation,          # [FIX-2399]
                            "tracking_mode_inferred": _probe_tracking_mode,       # [FIX-2399]
                            "probe_observed_events": _probe_fbq_events,           # [FIX-2399]
                            "funnel_steps": _probe_funnel_steps,                  # [FIX-2399]
                        }
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