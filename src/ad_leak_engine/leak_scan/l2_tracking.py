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
            
        # [SEED: 2399] Advanced L2 Signals
        if 'detect_capi_dedup_failure' in globals() and detect_capi_dedup_failure(net_log):
            leaks.append(Leak(page_id=page.id, tier="L2", signal="capi_dedup_failure", severity=0.85, recommendation="Sync event_id between pixel and CAPI", evidence={}))
        if 'detect_missing_initiate_checkout' in globals() and detect_missing_initiate_checkout(net_log):
            leaks.append(Leak(page_id=page.id, tier="L2", signal="missing_initiate_checkout", severity=0.7, recommendation="Add InitiateCheckout event", evidence={}))
        if 'detect_missing_add_to_cart' in globals() and detect_missing_add_to_cart(net_log):
            leaks.append(Leak(page_id=page.id, tier="L2", signal="missing_add_to_cart", severity=0.6, recommendation="Add AddToCart event", evidence={}))

        # [SEED: 2399] Attribution Gap Signal
        if detect_attribution_gap(page, net_log):
            leaks.append(Leak(page_id=page.id, tier="L2", signal="attribution_gap", severity=0.9, recommendation="Ad Library shows spend but no conversion signals. Flying blind on ROAS.", evidence={}))

        return leaks



def detect_capi_dedup_failure(telemetry) -> bool:
    # Check if browser and server events lack shared event_id
    return not telemetry.get("has_shared_event_id", True)

def detect_missing_initiate_checkout(telemetry) -> bool:
    return not telemetry.get("has_initiate_checkout", False)

def detect_missing_add_to_cart(telemetry) -> bool:
    return not telemetry.get("has_add_to_cart", False)

def detect_attribution_gap(page, telemetry) -> bool:
    # Ad Library shows spend but no conversion signals
    has_spend = page.total_estimated_spend[1] > 0 if page.total_estimated_spend else False
    has_conversions = telemetry.get("has_purchase_event", False)
    return has_spend and not has_conversions

