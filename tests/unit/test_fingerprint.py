"""Unit tests for Phase 4: Platform Fingerprint Detection."""
from pathlib import Path
import pytest
from ad_leak_engine.platform_fingerprint.detector import PlatformDetector
from ad_leak_engine.platform_fingerprint.confidence import calculate_confidence

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def detector():
    return PlatformDetector()


def test_shopify_detection(detector):
    """Shopify HTML with 3+ primary markers should return 0.95 confidence."""
    html = (FIXTURES_DIR / "sample_html_shopify.html").read_text()
    platform, confidence = detector.detect("https://test-store.myshopify.com", html)
    assert platform == "shopify"
    assert confidence >= 0.95


def test_woocommerce_detection(detector):
    """WooCommerce HTML with 2 primary + secondary markers should return 0.92."""
    html = (FIXTURES_DIR / "sample_html_woo.html").read_text()
    platform, confidence = detector.detect("https://example.com", html)
    assert platform == "woocommerce"
    assert confidence >= 0.92


def test_custom_fallback(detector):
    """Unknown HTML should return custom with 0.3 confidence."""
    html = "<html><body><h1>Generic Custom Site</h1></body></html>"
    platform, confidence = detector.detect("https://example.com", html)
    assert platform == "custom"
    assert confidence == 0.3


def test_bigcommerce_detection(detector):
    """BigCommerce markers should be detected."""
    html = """
    <html>
    <head><script src="https://cdn11.bigcommerce.com/s-abc123/stencil/bundle.js"></script></head>
    <body><div class="bc-cart">Cart</div></body>
    </html>
    """
    platform, confidence = detector.detect("https://store.com", html)
    assert platform == "bigcommerce"
    assert confidence >= 0.90


def test_webflow_detection(detector):
    """Webflow markers should be detected."""
    html = """
    <html>
    <head><script src="https://assets.webflow.com/webflow.js"></script></head>
    <body><a class="w-webflow-badge" href="https://webflow.com">Built with Webflow</a></body>
    </html>
    """
    platform, confidence = detector.detect("https://site.com", html)
    assert platform == "webflow"
    assert confidence >= 0.90


def test_header_based_detection(detector):
    """Platform can be detected from HTTP headers alone."""
    html = "<html><body>Minimal</body></html>"
    headers = {"X-ShopId": "12345678", "X-Shopify-Theme": "dawn"}
    platform, confidence = detector.detect("https://store.com", html, headers)
    assert platform == "shopify"
    assert confidence > 0.3


def test_confidence_scoring_rules():
    """Verify confidence calculation follows the defined rules."""
    assert calculate_confidence(0, 0) == 0.3
    assert calculate_confidence(3, 0) == 0.95
    assert calculate_confidence(2, 0) == 0.90
    assert calculate_confidence(2, 2) == 0.94
    assert calculate_confidence(1, 0) == 0.60
    assert calculate_confidence(1, 1) == 0.70
    assert calculate_confidence(0, 2) == 0.40


def test_empty_html_returns_custom(detector):
    """Empty or None HTML should return custom fallback."""
    platform, confidence = detector.detect("https://example.com", None)
    assert platform == "custom"
    assert confidence == 0.3
