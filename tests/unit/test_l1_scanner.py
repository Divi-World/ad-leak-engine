"""Unit tests for Phase 2: L1 Scanner."""
from datetime import datetime, timezone, timedelta
import pytest
from ad_leak_engine.leak_scan.l1_creative import L1CreativeScanner
from ad_leak_engine.shared.schemas import Page, RawAd

def _make_page(ads: list[RawAd]) -> Page:
    return Page(
        id="page_test", name="Test Page",
        ads=ads, first_seen=datetime.now(timezone.utc)
    )

def _make_ad(days_ago: int, media="IMAGE", cta="Shop Now", spend=(0.0, 0.0)) -> RawAd:
    return RawAd(
        id=f"ad_{days_ago}", page_id="page_test", page_name="Test",
        start_date=datetime.now(timezone.utc) - timedelta(days=days_ago),
        media_type=media, cta=cta, spend=spend, status="ACTIVE"
    )

def test_creative_fatigue_detected():
    scanner = L1CreativeScanner()
    page = _make_page([_make_ad(45)])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "creative_fatigue" in signals
    fatigue_leak = next(l for l in leaks if l.signal == "creative_fatigue")
    assert fatigue_leak.severity >= 0.7

def test_no_ab_variation_detected():
    scanner = L1CreativeScanner()
    page = _make_page([_make_ad(5)])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "no_ab_variation" in signals

def test_no_video_detected():
    scanner = L1CreativeScanner()
    page = _make_page([_make_ad(5, media="IMAGE"), _make_ad(2, media="IMAGE"), _make_ad(1, media="CAROUSEL")])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "no_video_creative" in signals

def test_spend_without_testing_detected():
    scanner = L1CreativeScanner()
    page = _make_page([_make_ad(5, spend=(1500.0, 2000.0)), _make_ad(2, spend=(500.0, 800.0))])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "spend_without_testing" in signals

def test_missing_cta_detected():
    scanner = L1CreativeScanner()
    page = _make_page([
        _make_ad(5, cta="Learn More"), 
        _make_ad(2, cta=None), 
        _make_ad(1, cta="learn more")
    ])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "missing_cta" in signals

def test_healthy_page_no_l1_leaks():
    scanner = L1CreativeScanner()
    page = _make_page([
        _make_ad(10, media="VIDEO", cta="Shop Now", spend=(100.0, 200.0)),
        _make_ad(5, media="IMAGE", cta="Buy Now", spend=(100.0, 200.0)),
        _make_ad(2, media="CAROUSEL", cta="Get Offer", spend=(100.0, 200.0))
    ])
    leaks = scanner.scan(page)
    signals = [l.signal for l in leaks]
    assert "creative_fatigue" not in signals
    assert "no_ab_variation" not in signals
    assert "no_video_creative" not in signals
    assert "spend_without_testing" not in signals
    assert "missing_cta" not in signals
