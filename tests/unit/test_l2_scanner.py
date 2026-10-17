"""Unit tests for Phase 2: L2 Scanner."""
from datetime import datetime, timezone
import pytest
from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
from ad_leak_engine.shared.schemas import Page

def _make_page_with_network(net_log: dict) -> Page:
    return Page(
        id="page_l2", name="Test L2",
        first_seen=datetime.now(timezone.utc),
        raw={"network_log": net_log}
    )

def test_pixel_not_firing():
    """
    [SEED: 2399] Evidence-based missing pixel test.

    This test proves that L2 only claims pixel_not_firing when there is
    sufficient network evidence and no pixel script is observed.
    """
    class FakePage:
        id = "forensic-pixel-missing"
        raw = {
            "network_log": {
                "pixel_fired": False,
                "requests": [
                    {"url": f"https://example.com/asset-{i}", "method": "GET", "status": 200}
                    for i in range(10)
                ],
                "capi_events": [],
                "has_unhashed_pii": False,
                "has_initiate_checkout": False,
                "has_add_to_cart": False,
                "has_shared_event_id": True,
                "has_purchase_event": False,
                "is_checkout_page": False,
            }
        }
        total_estimated_spend = (0, 0)
        active_ads = []

    try:
        from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
    except ImportError:
        from src.ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner

    leaks = L2TrackingScanner().scan(FakePage())
    assert any(getattr(l, "signal", None) == "pixel_not_firing" for l in leaks)


def test_l2_telemetry_blind_spot_when_requests_sparse():
    """
    [SEED: 2399] Sparse telemetry must not produce a definitive missing-pixel claim.
    """
    class FakePage:
        id = "forensic-telemetry-blind"
        raw = {
            "network_log": {
                "pixel_fired": False,
                "requests": [
                    {"url": "https://example.com/", "method": "GET", "status": 200}
                ],
                "capi_events": [],
                "has_unhashed_pii": False,
                "has_initiate_checkout": False,
                "has_add_to_cart": False,
                "has_shared_event_id": True,
                "has_purchase_event": False,
                "is_checkout_page": False,
            }
        }
        total_estimated_spend = (0, 0)
        active_ads = []

    try:
        from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
    except ImportError:
        from src.ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner

    leaks = L2TrackingScanner().scan(FakePage())
    assert any(getattr(l, "signal", None) == "telemetry_blind_spot" for l in leaks)


def test_l2_pixel_script_detected_but_not_firing():
    """
    [SEED: 2399] Pixel script presence without PageView must be reported as a
    firing/consent/trigger issue, not as a missing pixel.
    """
    class FakePage:
        id = "forensic-pixel-script-no-pageview"
        raw = {
            "network_log": {
                "pixel_fired": False,
                "requests": [
                    {"url": "https://connect.facebook.net/en_US/fbevents.js", "method": "GET", "status": 200},
                    {"url": "https://example.com/app.js", "method": "GET", "status": 200},
                ]
                + [
                    {"url": f"https://example.com/asset-{i}", "method": "GET", "status": 200}
                    for i in range(8)
                ],
                "capi_events": [],
                "has_unhashed_pii": False,
                "has_initiate_checkout": False,
                "has_add_to_cart": False,
                "has_shared_event_id": True,
                "has_purchase_event": False,
                "is_checkout_page": False,
            }
        }
        total_estimated_spend = (0, 0)
        active_ads = []

    try:
        from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
    except ImportError:
        from src.ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner

    leaks = L2TrackingScanner().scan(FakePage())
    assert any(getattr(l, "signal", None) == "pixel_script_detected_but_not_firing" for l in leaks)


def test_unhashed_pii():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({"pixel_fired": True, "has_unhashed_pii": True})
    leaks = scanner.scan(page)
    assert any(l.signal == "unhashed_pii" for l in leaks)

def test_missing_purchase_event():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({
        "pixel_fired": True, 
        "is_checkout_page": True, 
        "capi_events": [{"event_name": "InitiateCheckout"}]
    })
    leaks = scanner.scan(page)
    assert any(l.signal == "missing_purchase_event" for l in leaks)

def test_healthy_tracking():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({
        "pixel_fired": True,
        "has_unhashed_pii": False,
        "is_checkout_page": True,
        "capi_events": [{"event_name": "Purchase"}, {"event_name": "InitiateCheckout"}]
    })
    page.raw["network_log"].update({"has_initiate_checkout": True, "has_add_to_cart": True, "has_shared_event_id": True})
    leaks = scanner.scan(page)
    assert len(leaks) == 0
