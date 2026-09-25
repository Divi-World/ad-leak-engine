"""Tests proving generated fix code is syntactically valid [SEED: 2399]."""
import pytest

from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.fix_forge.validation import validate_fix, validate_python
from ad_leak_engine.shared.schemas import Leak


@pytest.fixture
def forge():
    return FixForge()


def test_python_webhook_compiles(forge):
    leak = Leak(page_id="p", tier="L2", signal="unhashed_pii", severity=0.8, recommendation="hash PII")
    fix = forge.generate(leak, "custom", 0.6)
    py_blocks = [b for b in fix.code_blocks if b["language"] == "python"]
    assert len(py_blocks) == 1
    assert validate_python(py_blocks[0]["code"]) is True


def test_shopify_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "shopify", 0.95)
    assert validate_fix(fix) is True


def test_woocommerce_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="unhashed_pii", severity=0.8, recommendation="hash PII")
    fix = forge.generate(leak, "woocommerce", 0.92)
    assert validate_fix(fix) is True


def test_bigcommerce_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "bigcommerce", 0.90)
    assert validate_fix(fix) is True


def test_custom_gtm_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "custom", 0.6)
    assert validate_fix(fix) is True


def test_invalid_python_rejected():
    assert validate_python("def broken(:") is False
