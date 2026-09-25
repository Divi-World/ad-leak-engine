"""Tests for Phase 7 polish: ranked leaks + data-backed message [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.outreach.bundle import OutreachBuilder
from ad_leak_engine.shared.schemas import Page, Leak


@pytest.fixture
def builder(tmp_path):
    return OutreachBuilder(output_dir=str(tmp_path))


@pytest.fixture
def page():
    return Page(id="p_polish", name="Polish Store", url="https://polish.com",
                first_seen=datetime.now(timezone.utc))


def test_leaks_ranked_by_severity(builder, page):
    leaks = [
        Leak(page_id="p_polish", tier="L1", signal="no_video_creative", severity=0.5, recommendation="add video"),
        Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel"),
        Leak(page_id="p_polish", tier="L1", signal="creative_fatigue", severity=0.7, recommendation="refresh"),
    ]
    pack = builder.build(page, leaks, [])
    severities = [l.severity for l in pack.leaks_found]
    assert severities == sorted(severities, reverse=True)
    assert pack.leaks_found[0].signal == "pixel_not_firing"


def test_teardown_marks_ranked(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")]
    pack = builder.build(page, leaks, [])
    assert "Ranked by Severity" in pack.teardown_markdown


def test_message_has_specific_observation_for_fatigue(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L1", signal="creative_fatigue", severity=0.8,
                  recommendation="refresh", evidence={"days_running": 47})]
    pack = builder.build(page, leaks, [])
    assert "47 days" in pack.message_text


def test_message_has_specific_observation_for_pixel(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")]
    pack = builder.build(page, leaks, [])
    assert "Pixel" in pack.message_text


def test_message_has_specific_observation_for_lcp(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L3", signal="slow_lcp_mobile", severity=0.8,
                  recommendation="optimize", evidence={"lcp_mobile_ms": 4200})]
    pack = builder.build(page, leaks, [])
    assert "4.2s" in pack.message_text
