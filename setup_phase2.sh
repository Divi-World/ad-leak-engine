#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 2: L1 + L2 Leak Detection
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 2 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ---------- 2. L1 Scanner (Creative & Strategy) ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l1_creative.py
"""L1 Scanner: Detects creative and strategy leaks from RawAd data."""
from datetime import datetime, timezone
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner
from ..shared.constants import (
    CREATIVE_FATIGUE_DAYS, MIN_AB_VARIATION_ADS, 
    SPEND_WITHOUT_TESTING_USD, SPEND_WITHOUT_TESTING_MIN_ADS
)

class L1CreativeScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L1"

    def scan(self, page: Page) -> list[Leak]:
        leaks = []
        active_ads = page.active_ads
        if not active_ads:
            return leaks

        now = datetime.now(timezone.utc)
        
        # 1. Creative fatigue
        oldest_ad = min(active_ads, key=lambda a: a.start_date)
        days_running = (now - oldest_ad.start_date).days
        if days_running > CREATIVE_FATIGUE_DAYS:
            severity = min(0.9, 0.7 + (days_running - CREATIVE_FATIGUE_DAYS) / 100)
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="creative_fatigue",
                severity=severity,
                evidence={"days_running": days_running, "oldest_ad_id": oldest_ad.id},
                recommendation=f"Oldest ad has run {days_running} days. Refresh creative."
            ))

        # 2. No A/B variation
        if len(active_ads) < MIN_AB_VARIATION_ADS:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="no_ab_variation",
                severity=0.6,
                evidence={"active_ad_count": len(active_ads)},
                recommendation=f"Only {len(active_ads)} active ads. Launch variants."
            ))

        # 3. No video creative
        if not any(a.media_type == "VIDEO" for a in active_ads):
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="no_video_creative",
                severity=0.5,
                evidence={"media_types": list(set(a.media_type for a in active_ads))},
                recommendation="No video ads detected. Add video creatives."
            ))

        # 4. Spend without testing
        lower_spend, _ = page.total_estimated_spend
        if lower_spend > SPEND_WITHOUT_TESTING_USD and len(active_ads) < SPEND_WITHOUT_TESTING_MIN_ADS:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="spend_without_testing",
                severity=0.8,
                evidence={"lower_spend": lower_spend, "active_ad_count": len(active_ads)},
                recommendation="High spend with low ad variation. A/B test immediately."
            ))

        # 5. Missing CTA
        missing_cta_count = sum(1 for a in active_ads if not a.cta or a.cta.lower() in ["learn more", ""])
        if missing_cta_count == len(active_ads) and len(active_ads) > 0:
            leaks.append(Leak(
                page_id=page.id, tier="L1", signal="missing_cta",
                severity=0.5,
                evidence={"missing_cta_count": missing_cta_count},
                recommendation="All ads use weak or missing CTAs. Use action-oriented CTAs."
            ))
            
        return leaks
EOF

# ---------- 3. L2 Scanner (Tracking & Measurement) ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l2_tracking.py
"""L2 Scanner: Detects tracking and measurement leaks via network logs."""
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner

class L2TrackingScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L2"

    def scan(self, page: Page) -> list[Leak]:
        leaks = []
        # In production, Playwright intercepts network requests and injects this into page.raw
        net_log = page.raw.get("network_log", {}) if page.raw else {}
        
        # 1. Pixel not firing
        if not net_log.get("pixel_fired", False):
            leaks.append(Leak(
                page_id=page.id, tier="L2", signal="pixel_not_firing",
                severity=0.95,
                evidence={"network_requests": net_log.get("requests", [])},
                recommendation="Meta Pixel not detected on landing page. Install base code."
            ))
            
        # 2. Unhashed PII in CAPI
        if net_log.get("has_unhashed_pii", False):
            leaks.append(Leak(
                page_id=page.id, tier="L2", signal="unhashed_pii",
                severity=0.8,
                evidence={"capi_payload_sample": net_log.get("capi_sample", {})},
                recommendation="CAPI payload contains unhashed PII. Hash em/ph/fn/ln via SHA-256."
            ))
            
        # 3. Missing Purchase event on checkout
        capi_events = [e.get("event_name") for e in net_log.get("capi_events", [])]
        if net_log.get("is_checkout_page") and "Purchase" not in capi_events:
            leaks.append(Leak(
                page_id=page.id, tier="L2", signal="missing_purchase_event",
                severity=0.9,
                recommendation="No Purchase event fired on checkout page."
            ))
            
        return leaks
EOF

# ---------- 4. Scoring Utility ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/scoring.py
"""Scoring and weighting logic for leak prioritization."""
from ..shared.schemas import Leak

def calculate_priority_score(leak: Leak, weight: float = 1.0) -> float:
    """Calculates final priority score (0.0 to 1.0)."""
    return min(1.0, leak.severity * leak.confidence * weight)
EOF

# ---------- 5. Tests: L1 Scanner ----------
cat << 'EOF' > tests/unit/test_l1_scanner.py
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
EOF

# ---------- 6. Tests: L2 Scanner ----------
cat << 'EOF' > tests/unit/test_l2_scanner.py
"""Unit tests for Phase 2: L2 Scanner."""
from datetime import datetime, timezone
import pytest
from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
from ad_leak_engine.shared.schemas import Page

def _make_page_with_network(net_log: dict) -> Page:
    return Page(
        id="page_l2", name="Test L2",
        first_seen=datetime.now(timezone.utc),
        raw={"network_log": net_log}
    )

def test_pixel_not_firing():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({"pixel_fired": False})
    leaks = scanner.scan(page)
    assert any(l.signal == "pixel_not_firing" for l in leaks)
    assert next(l for l in leaks if l.signal == "pixel_not_firing").severity == 0.95

def test_unhashed_pii():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({"pixel_fired": True, "has_unhashed_pii": True})
    leaks = scanner.scan(page)
    assert any(l.signal == "unhashed_pii" for l in leaks)

def test_missing_purchase_event():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({
        "pixel_fired": True, 
        "is_checkout_page": True, 
        "capi_events": [{"event_name": "InitiateCheckout"}]
    })
    leaks = scanner.scan(page)
    assert any(l.signal == "missing_purchase_event" for l in leaks)

def test_healthy_tracking():
    scanner = L2TrackingScanner()
    page = _make_page_with_network({
        "pixel_fired": True,
        "has_unhashed_pii": False,
        "is_checkout_page": True,
        "capi_events": [{"event_name": "Purchase"}, {"event_name": "InitiateCheckout"}]
    })
    leaks = scanner.scan(page)
    assert len(leaks) == 0
EOF

# ---------- 7. Execute Tests ----------
echo "[SEED:2399] Running Phase 2 test suite..."
python -m pytest tests/unit/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 2 COMPLETE"
echo "  L1 + L2 Scanners Built. Boundary Tests Passing."
echo "=========================================================="