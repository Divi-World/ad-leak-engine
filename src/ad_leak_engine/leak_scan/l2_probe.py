"""L2 Live Probe: Playwright network interception [SEED: 2399].

Loads landing page via stealth browser, intercepts network requests,
returns network_log dict consumed by L2TrackingScanner and TelemetryCollector.
"""
from typing import Any


def on_request(request, requests_log: list, network_log: dict):
    """Intercept handler: captures all requests and detects pixel/CAPI activity."""
    req_url = request.url
    requests_log.append({"url": req_url, "method": request.method, "status": None})

    if "facebook.com/tr" in req_url:
        network_log["pixel_fired"] = True

    if "graph.facebook.com" in req_url and "/events" in req_url:
        network_log["capi_events"].append({"url": req_url, "event_name": "server_event"})


def detect_capi_dedup_failure(telemetry) -> bool:
    """Check if browser and server events lack shared event_id."""
    return not telemetry.get("has_shared_event_id", True)


def detect_missing_initiate_checkout(telemetry) -> bool:
    return not telemetry.get("has_initiate_checkout", False)


def detect_missing_add_to_cart(telemetry) -> bool:
    return not telemetry.get("has_add_to_cart", False)


def detect_attribution_gap(page, telemetry) -> bool:
    """Ad Library shows spend but no conversion signals."""
    has_spend = page.total_estimated_spend[1] > 0 if page.total_estimated_spend else False
    has_conversions = telemetry.get("has_purchase_event", False)
    return has_spend and not has_conversions


class L2LiveProbe:
    """Probes a live landing page for Meta Pixel and CAPI network activity."""

    def probe(self, url: str) -> dict:
        """Load url, intercept network, return network_log dict."""
        network_log = {
            "pixel_fired": False,
            "requests": [],
            "capi_events": [],
            "has_unhashed_pii": False,
            "has_initiate_checkout": False,
            "has_add_to_cart": False,
            "has_shared_event_id": True,
            "has_purchase_event": False,
            "is_checkout_page": False,
        }

        try:
            from ..self_heal.human_browser import HumanBrowser
        except ImportError:
            return network_log

        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                requests_log = []

                def _on_request(request):
                    on_request(request, requests_log, network_log)

                page.on("request", _on_request)
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                content = page.content()
                if "fbevents.js" in content or "fbq(" in content:
                    network_log["pixel_fired"] = True

                network_log["requests"] = requests_log

                # Detect checkout page
                url_lower = url.lower()
                network_log["is_checkout_page"] = any(
                    k in url_lower for k in ["checkout", "thank", "order", "confirm"]
                )

                # Detect event types in intercepted requests
                for req in requests_log:
                    req_url_lower = req.get("url", "").lower()
                    if "initiatecheckout" in req_url_lower:
                        network_log["has_initiate_checkout"] = True
                    if "addtocart" in req_url_lower:
                        network_log["has_add_to_cart"] = True
                    if "purchase" in req_url_lower:
                        network_log["has_purchase_event"] = True

        except Exception:
            pass

        return network_log
