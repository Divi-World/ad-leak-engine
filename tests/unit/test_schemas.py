"""Contract validation tests for [SEED: 2399] data schemas."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ad_leak_engine.shared.schemas import Fix, Leak, OutreachPack, Page, RawAd


def _ad(**overrides) -> RawAd:
    base = dict(
        id="ad_1",
        page_id="page_1",
        page_name="Test Page",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        media_type="IMAGE",
    )
    base.update(overrides)
    return RawAd(**base)


def test_raw_ad_minimal_defaults():
    ad = _ad()
    assert ad.status == "ACTIVE"
    assert ad.country == "US"
    assert ad.raw == {}
    assert ad.platforms == []


def test_raw_ad_url_normalization():
    ad = _ad(landing_url="example.com/landing")
    assert ad.landing_url == "https://example.com/landing"


def test_raw_ad_url_preserves_https():
    ad = _ad(landing_url="https://example.com/x")
    assert ad.landing_url == "https://example.com/x"


def test_raw_ad_rejects_bad_media_type():
    with pytest.raises(ValidationError):
        _ad(media_type="HOLOGRAM")


def test_page_active_ads_filter():
    a1 = _ad(id="a1", status="ACTIVE")
    a2 = _ad(id="a2", status="INACTIVE")
    page = Page(id="page_1", name="Test", ads=[a1, a2],
                first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(page.active_ads) == 1
    assert page.active_ads[0].id == "a1"


def test_page_total_estimated_spend():
    a1 = _ad(id="a1", spend=(100.0, 200.0))
    a2 = _ad(id="a2", spend=(50.0, 150.0))
    page = Page(id="page_1", name="Test", ads=[a1, a2],
                first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert page.total_estimated_spend == (150.0, 350.0)


def test_leak_severity_bounds():
    with pytest.raises(ValidationError):
        Leak(page_id="p", tier="L1", signal="x", severity=1.5, recommendation="r")


def test_leak_auto_id():
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing",
                severity=0.9, recommendation="Install pixel")
    assert leak.id
    assert leak.confidence == 0.8


def test_fix_round_trip():
    fix = Fix(leak_id="leak_1", platform="shopify", platform_confidence=0.95,
              markdown_guide="# Fix", expected_outcome="Pixel fires", confidence=0.9)
    assert fix.platform == "shopify"
    assert fix.code_blocks == []


def test_outreach_pack_structure(sample_ad):
    leak = Leak(page_id="page_1", tier="L1", signal="creative_fatigue",
                severity=0.8, recommendation="Refresh creative")
    pack = OutreachPack(page_id="page_1", page_name="Test",
                        teardown_markdown="# Teardown",
                        executive_summary="You are leaking money.",
                        leaks_found=[leak], message_text="Hi, found a leak.",
                        estimated_recovery="$1,500/month")
    assert len(pack.leaks_found) == 1
    assert pack.estimated_recovery == "$1,500/month"
