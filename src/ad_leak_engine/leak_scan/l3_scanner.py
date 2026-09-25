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
