"""Unit tests for Phase 3: L3 Site Scanner."""
from datetime import datetime, timezone
import pytest
from ad_leak_engine.leak_scan.l3_scanner import L3SiteScanner
from ad_leak_engine.shared.schemas import Page

def _make_page_with_telemetry(telemetry: dict) -> Page:
    return Page(
        id="page_l3", name="Test L3",
        first_seen=datetime.now(timezone.utc),
        raw={"telemetry": telemetry}
    )

def test_slow_lcp_mobile():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"lcp_mobile_ms": 3500})
    leaks = scanner.scan(page)
    assert any(l.signal == "slow_lcp_mobile" for l in leaks)
    assert next(l for l in leaks if l.signal == "slow_lcp_mobile").severity == 0.8

def test_slow_ttfb():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"ttfb_ms": 1200})
    leaks = scanner.scan(page)
    assert any(l.signal == "slow_ttfb" for l in leaks)

def test_small_tap_targets():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"min_tap_target_px": 30})
    leaks = scanner.scan(page)
    assert any(l.signal == "small_tap_targets" for l in leaks)

def test_checkout_friction():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"checkout_steps": 6})
    leaks = scanner.scan(page)
    assert any(l.signal == "checkout_friction" for l in leaks)

def test_pixel_blocking_scripts():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"scripts_before_pixel": 10})
    leaks = scanner.scan(page)
    assert any(l.signal == "pixel_blocking_scripts" for l in leaks)

def test_healthy_l3_performance():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({
        "lcp_mobile_ms": 1500,
        "ttfb_ms": 400,
        "min_tap_target_px": 50,
        "checkout_steps": 2,
        "scripts_before_pixel": 2
    })
    leaks = scanner.scan(page)
    assert len(leaks) == 0
