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
    scanner = L2TrackingScanner()
    page = _make_page_with_network({"pixel_fired": False})
    leaks = scanner.scan(page)
    assert any(l.signal == "pixel_not_firing" for l in leaks)
    assert next(l for l in leaks if l.signal == "pixel_not_firing").severity == 0.95

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
    leaks = scanner.scan(page)
    assert len(leaks) == 0
