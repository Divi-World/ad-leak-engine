"""LIVE: crawl a real landing page and produce telemetry [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.leak_scan.telemetry_collector import TelemetryCollector
from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
from ad_leak_engine.leak_scan.l3_scanner import L3SiteScanner
from ad_leak_engine.shared.schemas import Page

LIVE_URL = "https://example.com"


@pytest.mark.live
def test_live_landing_page_audit():
    collector = TelemetryCollector()
    data = collector.collect(LIVE_URL)
    assert "network_log" in data
    assert "telemetry" in data

    page = Page(id="live_crawl", name="Live Crawl", url=LIVE_URL,
                first_seen=datetime.now(timezone.utc), raw=data)
    l2_leaks = L2TrackingScanner().scan(page)
    l3_leaks = L3SiteScanner().scan(page)
    assert isinstance(l2_leaks, list)
    assert isinstance(l3_leaks, list)
