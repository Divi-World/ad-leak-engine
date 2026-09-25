"""Unit tests for Phase 5: Fix Forge code generation."""
import pytest
from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.shared.schemas import Leak
from ad_leak_engine.shared.exceptions import PlatformAmbiguousError


@pytest.fixture
def forge():
    return FixForge()


@pytest.fixture
def pixel_leak():
    return Leak(
        page_id="p1", tier="L2", signal="pixel_not_firing",
        severity=0.95, recommendation="Install Meta Pixel base code",
    )


def test_shopify_pixel_fix_generates_valid_liquid(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "shopify", 0.95)
    assert fix.platform == "shopify"
    assert len(fix.code_blocks) == 1
    code = fix.code_blocks[0]["code"]
    assert "fbq('init'" in code
    assert "YOUR_PIXEL_ID_HERE" in code
    assert fix.code_blocks[0]["filename"] == "theme.liquid"
    assert fix.markdown_guide
    assert len(fix.verification_steps) > 0
    assert len(fix.rollback_steps) > 0


def test_shopify_capi_fix_generates_customer_events(forge):
    leak = Leak(page_id="p1", tier="L2", signal="missing_purchase_event",
                severity=0.9, recommendation="Add Purchase event")
    fix = forge.generate(leak, "shopify", 0.95)
    code = fix.code_blocks[0]["code"]
    assert "analytics.subscribe" in code
    assert "checkout_completed" in code


def test_woocommerce_capi_fix_generates_valid_php(forge):
    leak = Leak(page_id="p2", tier="L2", signal="unhashed_pii",
                severity=0.8, recommendation="Hash PII with SHA-256")
    fix = forge.generate(leak, "woocommerce", 0.92)
    assert fix.platform == "woocommerce"
    code = fix.code_blocks[0]["code"]
    assert "woocommerce_thankyou" in code
    assert "hash('sha256'" in code
    assert fix.markdown_guide


def test_bigcommerce_fix_generates_script_manager(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "bigcommerce", 0.90)
    assert fix.platform == "bigcommerce"
    code = fix.code_blocks[0]["code"]
    assert "fbq('init'" in code


def test_custom_gtm_fix(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "custom", 0.6)
    assert fix.platform == "custom"
    code = fix.code_blocks[0]["code"]
    assert "Google Tag Manager" in code


def test_custom_server_side_fix(forge):
    leak = Leak(page_id="p4", tier="L2", signal="unhashed_pii",
                severity=0.8, recommendation="Hash PII")
    fix = forge.generate(leak, "custom", 0.6)
    code = fix.code_blocks[0]["code"]
    assert "sha256_hash" in code
    assert "/orders/create" in code


def test_low_confidence_raises_ambiguous(forge, pixel_leak):
    with pytest.raises(PlatformAmbiguousError):
        forge.generate(pixel_leak, "shopify", 0.3)


def test_fix_schema_completeness(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "shopify", 0.95)
    assert fix.leak_id == pixel_leak.id
    assert fix.expected_outcome
    assert 0.0 <= fix.confidence <= 1.0
    assert 0.0 <= fix.platform_confidence <= 1.0


def test_unknown_platform_falls_back_to_custom(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "unknown_platform", 0.6)
    assert fix.platform == "custom"
