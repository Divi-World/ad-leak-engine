"""Tests for the FixForge custom-platform confidence rule [SEED: 2399]."""
import pytest

from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.shared.schemas import Leak
from ad_leak_engine.shared.exceptions import PlatformAmbiguousError


@pytest.fixture
def forge():
    return FixForge()


@pytest.fixture
def leak():
    return Leak(page_id="p", tier="L2", signal="pixel_not_firing",
                severity=0.95, recommendation="install pixel")


def test_custom_low_confidence_still_generates(forge, leak):
    # custom confidence 0.3 must NOT raise — generic fixes are always safe
    fix = forge.generate(leak, "custom", 0.3)
    assert fix.platform == "custom"
    assert len(fix.code_blocks) >= 1


def test_shopify_low_confidence_raises(forge, leak):
    with pytest.raises(PlatformAmbiguousError):
        forge.generate(leak, "shopify", 0.3)


def test_unknown_platform_routes_to_custom(forge, leak):
    fix = forge.generate(leak, "mystery_platform", 0.6)
    assert fix.platform == "custom"
