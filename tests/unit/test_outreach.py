"""Unit tests for Phase 6: Outreach Bundle Assembly."""
import pytest
from pathlib import Path
from datetime import datetime, timezone

from ad_leak_engine.outreach.bundle import OutreachBuilder
from ad_leak_engine.outreach.compliance import ComplianceChecker, ComplianceError
from ad_leak_engine.shared.schemas import Page, Leak, Fix


@pytest.fixture
def builder(tmp_path):
    return OutreachBuilder(output_dir=str(tmp_path))


@pytest.fixture
def sample_page():
    return Page(id="p_outreach", name="Test Store", url="https://test.com",
                first_seen=datetime.now(timezone.utc))


@pytest.fixture
def sample_leaks():
    return [
        Leak(page_id="p_outreach", tier="L2", signal="pixel_not_firing",
             severity=0.95, recommendation="Install pixel"),
        Leak(page_id="p_outreach", tier="L1", signal="creative_fatigue",
             severity=0.7, recommendation="Refresh ads"),
    ]


@pytest.fixture
def sample_fixes():
    return [
        Fix(leak_id="l1", platform="shopify", platform_confidence=0.95,
            markdown_guide="# Guide", expected_outcome="Pixel fires",
            confidence=0.9, verification_steps=["Check Events Manager"]),
    ]


def test_bundle_creates_files(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert pack.page_id == "p_outreach"
    assert len(pack.evidence_paths) == 2
    for p in pack.evidence_paths:
        assert Path(p).exists()


def test_message_contains_compliance_footer(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert "UNSUBSCRIBE" in pack.message_text
    assert "[Physical Address]" in pack.message_text


def test_teardown_contains_leaks(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert "Pixel Not Firing" in pack.teardown_markdown
    assert "Creative Fatigue" in pack.teardown_markdown


def test_estimated_recovery_calculation(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    # 1 high sev (0.95) = $1000, 1 med sev (0.7) = $300 -> $1,300
    assert "$1,300" in pack.estimated_recovery


def test_compliance_checker_rejects_missing_unsub():
    checker = ComplianceChecker()
    with pytest.raises(ComplianceError):
        checker.validate("Hi, buy my stuff. [Physical Address]")
