#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 4: Platform Fingerprint
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 4 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ---------- 2. Platform Signatures Database ----------
cat << 'EOF' > src/ad_leak_engine/platform_fingerprint/signatures.py
"""Platform detection markers for Ad-Leak-Engine [SEED: 2399].

Each platform has primary markers (high confidence) and secondary
markers (supporting evidence). Detection requires at least 2 primary
markers for high confidence.
"""

PLATFORM_SIGNATURES = {
    "shopify": {
        "primary": [
            "cdn.shopify.com",
            "Shopify.theme",
            "/cart.js",
        ],
        "secondary": [
            "myshopify.com",
            "X-ShopId",
            "shopify-checkout",
            "ShopifyAnalytics",
        ],
    },
    "woocommerce": {
        "primary": [
            "wp-content/plugins/woocommerce",
            "wc-ajax",
        ],
        "secondary": [
            "woocommerce",
            "wp-json/wc/",
            "wc-store-api",
            "woocommerce_session",
        ],
    },
    "bigcommerce": {
        "primary": [
            "cdn11.bigcommerce.com",
            "stencil",
        ],
        "secondary": [
            "bigcommerce.com",
            "X-Bc-",
            "bc-cart",
        ],
    },
    "webflow": {
        "primary": [
            "webflow.com",
            "w-webflow-badge",
        ],
        "secondary": [
            "data-w-id",
            "wf-page",
            "webflow.js",
        ],
    },
}

# Custom platform is the fallback when no signatures match
CUSTOM_PLATFORM = "custom"
CUSTOM_CONFIDENCE = 0.3
EOF

# ---------- 3. Confidence Scoring Logic ----------
cat << 'EOF' > src/ad_leak_engine/platform_fingerprint/confidence.py
"""Confidence scoring for platform fingerprint detection."""
from .signatures import CUSTOM_CONFIDENCE


def calculate_confidence(primary_hits: int, secondary_hits: int) -> float:
    """Calculate detection confidence based on marker hits.

    Rules:
    - 3+ primary markers: 0.95 (near-certain)
    - 2 primary markers: 0.90 + 0.02 per secondary hit
    - 1 primary marker: 0.60 + 0.10 per secondary hit
    - Only secondary markers: 0.40
    - No markers: 0.30 (custom fallback)
    """
    if primary_hits == 0 and secondary_hits == 0:
        return CUSTOM_CONFIDENCE

    if primary_hits >= 3:
        return 0.95
    elif primary_hits == 2:
        return min(0.94, 0.90 + secondary_hits * 0.02)
    elif primary_hits == 1:
        return min(0.70, 0.60 + secondary_hits * 0.10)
    else:
        # Only secondary hits
        return 0.40
EOF

# ---------- 4. Platform Detector ----------
cat << 'EOF' > src/ad_leak_engine/platform_fingerprint/detector.py
"""Multi-signal platform detector for Ad-Leak-Engine [SEED: 2399]."""
from ..shared.interfaces import AbstractPlatformDetector
from .signatures import PLATFORM_SIGNATURES, CUSTOM_PLATFORM, CUSTOM_CONFIDENCE
from .confidence import calculate_confidence


class PlatformDetector(AbstractPlatformDetector):
    """Detects e-commerce platform from HTML content and HTTP headers."""

    def detect(self, url: str, html: str | None = None, headers: dict | None = None) -> tuple[str, float]:
        """Return (platform_name, confidence_score).

        Scans HTML content and HTTP headers for platform-specific
        markers. Returns the platform with the highest confidence.
        Falls back to 'custom' if no markers match.
        """
        html = html or ""
        headers = headers or {}

        best_platform = CUSTOM_PLATFORM
        best_confidence = CUSTOM_CONFIDENCE

        for platform, sigs in PLATFORM_SIGNATURES.items():
            primary_hits = self._count_primary_hits(sigs["primary"], html, headers)
            secondary_hits = self._count_secondary_hits(sigs["secondary"], html, headers)

            confidence = calculate_confidence(primary_hits, secondary_hits)

            if confidence > best_confidence:
                best_confidence = confidence
                best_platform = platform

        return (best_platform, best_confidence)

    def _count_primary_hits(self, markers: list[str], html: str, headers: dict) -> int:
        """Count primary marker hits in HTML and headers."""
        hits = 0
        for marker in markers:
            if marker.lower() in html.lower():
                hits += 1
            # Check headers (e.g., X-ShopId)
            for header_key, header_value in headers.items():
                if marker.lower() in header_key.lower() or marker.lower() in str(header_value).lower():
                    hits += 1
                    break  # Count each marker only once
        return hits

    def _count_secondary_hits(self, markers: list[str], html: str, headers: dict) -> int:
        """Count secondary marker hits in HTML and headers."""
        hits = 0
        for marker in markers:
            if marker.lower() in html.lower():
                hits += 1
            for header_key, header_value in headers.items():
                if marker.lower() in header_key.lower() or marker.lower() in str(header_value).lower():
                    hits += 1
                    break
        return hits
EOF

# ---------- 5. Test Fixtures: Shopify HTML ----------
mkdir -p tests/fixtures
cat << 'EOF' > tests/fixtures/sample_html_shopify.html
<!DOCTYPE html>
<html>
<head>
    <title>Test Shopify Store</title>
    <link rel="stylesheet" href="https://cdn.shopify.com/s/files/1/0000/0001/themes/theme.css">
    <script>
        var Shopify = Shopify || {};
        Shopify.theme = {"name": "dawn", "id": 12345678};
        Shopify.shop = "test-store.myshopify.com";
    </script>
</head>
<body>
    <a href="/cart.js">View Cart</a>
    <div class="shopify-checkout-api">Checkout</div>
</body>
</html>
EOF

# ---------- 6. Test Fixtures: WooCommerce HTML ----------
cat << 'EOF' > tests/fixtures/sample_html_woo.html
<!DOCTYPE html>
<html>
<head>
    <title>Test WooCommerce Store</title>
    <link rel="stylesheet" href="https://example.com/wp-content/plugins/woocommerce/assets/css/woocommerce.min.css">
</head>
<body class="woocommerce woocommerce-page">
    <script>
        var wc_ajax_url = "https://example.com/?wc-ajax=checkout";
        var wc_store_api_url = "https://example.com/wp-json/wc/store/v1/";
    </script>
    <div class="products">Products here</div>
</body>
</html>
EOF

# ---------- 7. Tests: Platform Fingerprint ----------
cat << 'EOF' > tests/unit/test_fingerprint.py
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
EOF

# ---------- 8. Execute Tests ----------
echo "[SEED:2399] Running Phase 4 test suite..."
python -m pytest tests/unit/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 4 COMPLETE"
echo "  Platform Fingerprint Built. Detection Accuracy Verified."
echo "=========================================================="