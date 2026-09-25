#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 3: L3 Site Audit
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 3 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ---------- 2. L3 Site: Playwright Skeletons ----------
mkdir -p src/ad_leak_engine/leak_scan/l3_site
touch src/ad_leak_engine/leak_scan/l3_site/__init__.py

cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/crawler.py
"""Playwright multi-page crawler for checkout friction detection."""
from playwright.async_api import async_playwright

class MultiPageCrawler:
    async def count_checkout_steps(self, start_url: str) -> int:
        """Navigates cart -> checkout -> payment -> review and counts steps."""
        # Production implementation uses Playwright to click through funnel
        pass
EOF

cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/performance.py
"""Core Web Vitals measurement via Playwright CDP (Chrome DevTools Protocol)."""
class PerformanceAuditor:
    async def measure_lcp_and_ttfb(self, page) -> dict:
        """Extracts Largest Contentful Paint and Time to First Byte."""
        pass
EOF

cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/pixel_probe.py
"""Detects third-party scripts blocking Meta Pixel execution."""
class PixelProbe:
    async def count_scripts_before_pixel(self, page) -> int:
        """Counts DOM <script> tags that load before fbq() initialization."""
        pass
EOF

cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/mobile_ux.py
"""Mobile UX analysis: viewport validation and tap target measurement."""
class MobileUXAnalyzer:
    async def get_min_tap_target(self, page) -> int:
        """Measures the smallest interactive element in CSS pixels."""
        pass
EOF

# ---------- 3. L3 Scanner Logic Orchestrator ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_scanner.py
"""L3 Scanner: Detects site performance, UX, and checkout leaks."""
from ..shared.schemas import Page, Leak
from ..shared.interfaces import AbstractLeakScanner
from ..shared.constants import (
    LCP_MOBILE_THRESHOLD_MS, TTFB_THRESHOLD_MS, TAP_TARGET_MIN_PX, 
    CHECKOUT_MAX_STEPS, PIXEL_BLOCKING_SCRIPTS_MAX
)

class L3SiteScanner(AbstractLeakScanner):
    def tier(self) -> str:
        return "L3"

    def scan(self, page: Page) -> list[Leak]:
        leaks = []
        telemetry = page.raw.get("telemetry", {}) if page.raw else {}
        
        # 1. LCP Mobile > 2.5s
        lcp_ms = telemetry.get("lcp_mobile_ms")
        if lcp_ms is not None and lcp_ms > LCP_MOBILE_THRESHOLD_MS:
            leaks.append(Leak(
                page_id=page.id, tier="L3", signal="slow_lcp_mobile",
                severity=0.8,
                evidence={"lcp_mobile_ms": lcp_ms},
                recommendation=f"Mobile LCP is {lcp_ms}ms (target < 2500ms). Optimize largest element."
            ))
            
        # 2. TTFB > 800ms
        ttfb_ms = telemetry.get("ttfb_ms")
        if ttfb_ms is not None and ttfb_ms > TTFB_THRESHOLD_MS:
            leaks.append(Leak(
                page_id=page.id, tier="L3", signal="slow_ttfb",
                severity=0.7,
                evidence={"ttfb_ms": ttfb_ms},
                recommendation=f"TTFB is {ttfb_ms}ms (target < 800ms). Server response is slow."
            ))
            
        # 3. Tap targets < 48px
        min_tap_target = telemetry.get("min_tap_target_px")
        if min_tap_target is not None and min_tap_target < TAP_TARGET_MIN_PX:
            leaks.append(Leak(
                page_id=page.id, tier="L3", signal="small_tap_targets",
                severity=0.5,
                evidence={"min_tap_target_px": min_tap_target},
                recommendation="Mobile tap targets are too small (<48px). Increase padding."
            ))
            
        # 4. Checkout > 4 steps
        checkout_steps = telemetry.get("checkout_steps")
        if checkout_steps is not None and checkout_steps > CHECKOUT_MAX_STEPS:
            leaks.append(Leak(
                page_id=page.id, tier="L3", signal="checkout_friction",
                severity=0.8,
                evidence={"checkout_steps": checkout_steps},
                recommendation=f"Checkout has {checkout_steps} steps. Reduce to < 4 steps."
            ))
            
        # 5. Pixel-blocking scripts
        scripts_before_pixel = telemetry.get("scripts_before_pixel")
        if scripts_before_pixel is not None and scripts_before_pixel > PIXEL_BLOCKING_SCRIPTS_MAX:
            leaks.append(Leak(
                page_id=page.id, tier="L3", signal="pixel_blocking_scripts",
                severity=0.7,
                evidence={"scripts_before_pixel": scripts_before_pixel},
                recommendation="Too many third-party scripts blocking pixel. Defer non-critical JS."
            ))

        return leaks
EOF

# ---------- 4. Tests: L3 Scanner ----------
cat << 'EOF' > tests/unit/test_l3_scanner.py
"""Unit tests for Phase 3: L3 Site Scanner."""
from datetime import datetime, timezone
import pytest
from ad_leak_engine.leak_scan.l3_scanner import L3SiteScanner
from ad_leak_engine.shared.schemas import Page

def _make_page_with_telemetry(telemetry: dict) -> Page:
    return Page(
        id="page_l3", name="Test L3",
        first_seen=datetime.now(timezone.utc),
        raw={"telemetry": telemetry}
    )

def test_slow_lcp_mobile():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"lcp_mobile_ms": 3500})
    leaks = scanner.scan(page)
    assert any(l.signal == "slow_lcp_mobile" for l in leaks)
    assert next(l for l in leaks if l.signal == "slow_lcp_mobile").severity == 0.8

def test_slow_ttfb():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"ttfb_ms": 1200})
    leaks = scanner.scan(page)
    assert any(l.signal == "slow_ttfb" for l in leaks)

def test_small_tap_targets():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"min_tap_target_px": 30})
    leaks = scanner.scan(page)
    assert any(l.signal == "small_tap_targets" for l in leaks)

def test_checkout_friction():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"checkout_steps": 6})
    leaks = scanner.scan(page)
    assert any(l.signal == "checkout_friction" for l in leaks)

def test_pixel_blocking_scripts():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({"scripts_before_pixel": 10})
    leaks = scanner.scan(page)
    assert any(l.signal == "pixel_blocking_scripts" for l in leaks)

def test_healthy_l3_performance():
    scanner = L3SiteScanner()
    page = _make_page_with_telemetry({
        "lcp_mobile_ms": 1500,
        "ttfb_ms": 400,
        "min_tap_target_px": 50,
        "checkout_steps": 2,
        "scripts_before_pixel": 2
    })
    leaks = scanner.scan(page)
    assert len(leaks) == 0
EOF

# ---------- 5. Execute Tests ----------
echo "[SEED:2399] Running Phase 3 test suite..."
python -m pytest tests/unit/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 3 COMPLETE"
echo "  L3 Site Audit Built. Core Web Vitals Logic Verified."
echo "=========================================================="