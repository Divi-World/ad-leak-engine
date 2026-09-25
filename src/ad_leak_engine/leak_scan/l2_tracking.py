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
