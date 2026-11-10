"""Collects REAL telemetry from a live landing page [SEED: 2399].

This is the reality bridge: it runs live Playwright probes and returns the
{'network_log': ..., 'telemetry': ...} dict that the L2/L3 scanners consume.
"""
from .l2_probe import L2LiveProbe
from .l3_site.performance import PerformanceAuditor
from .l3_site.mobile_ux import MobileUXAnalyzer
from .l3_site.cart_analysis import CartAnalyzer
from .l3_site.api_interceptor import ApiInterceptor
from .l3_site.saas_waste import SaasWasteAnalyzer
from .l3_site.pricing_friction import PricingFrictionAnalyzer


class TelemetryCollector:
    def __init__(self):
        self.l2_probe = L2LiveProbe()
        self.perf = PerformanceAuditor()
        self.mobile_ux = MobileUXAnalyzer()
        self.cart = CartAnalyzer()
        self.api = ApiInterceptor()
        self.saas = SaasWasteAnalyzer()
        self.pricing = PricingFrictionAnalyzer()

    def collect(self, url: str) -> dict:
        """[SEED: 2399] SELF-HEALING TELEMETRY ENGINE
        
        Strategy:
        1. Attempt Full Dynamic Probe (Playwright).
        2. If Fail/Empty, Retry once with extended timeout.
        3. If Still Fail, Fall back to Static HTML Fetch (curl_cffi) to ensure 
           at least basic fingerprinting/performance data exists.
        4. Never return empty dict unless URL is totally unreachable.
        """
        max_retries = 2
        last_error = None
        
        # --- ATTEMPT 1 & 2: Dynamic Probing ---
        for attempt in range(max_retries):
            try:
                network_log = self.l2_probe.probe(url)
                
                # Validate Quality: Did we actually get requests?
                req_count = len(network_log.get("requests", [])) if isinstance(network_log, dict) else 0
                
                if req_count > 0 or network_log.get("pixel_fired"):
                    # Success! Gather remaining telemetry
                    telemetry = self.perf.measure(url)
                    telemetry.update(self.mobile_ux.measure(url))
                    telemetry.update(self.cart.measure(url))
                    telemetry.update(self.api.measure(url))
                    telemetry.update(self.saas.measure(url))
                    telemetry.update(self.pricing.measure(url))
                    
                    return {"network_log": network_log, "telemetry": telemetry}
                else:
                    # Partial Failure: Empty logs but no crash. Retry.
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(2) # Cool down before retry
                        continue
                    
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2)
                    continue

        # --- FALLBACK: Static Analysis (If Dynamic Failed Completely) ---
        # This ensures we never leave the scanner blind due to tool failure.
        try:
            from curl_cffi import requests as cffi_requests
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=10)
            html = resp.text if resp.status_code == 200 else ""
            
            # Construct minimal valid structure so L2/L3 don't crash
            minimal_network_log = {
                "requests": [],
                "pixel_fired": False,
                "waf_blocked": False,
                "fallback_mode": True,
                "error_context": str(last_error) if last_error else "Dynamic probe returned empty"
            }
            
            # Run lightweight static checks
            perf_data = self.perf.measure_static(html) if hasattr(self.perf, 'measure_static') else {}
            
            return {
                "network_log": minimal_network_log,
                "telemetry": perf_data,
                "collection_status": "FALLBACK_STATIC_ONLY"
            }
            
        except Exception as final_e:
            # Absolute worst case: Return structured error so pipeline continues
            return {
                "network_log": {},
                "telemetry": {},
                "collection_status": "TOTAL_FAILURE",
                "final_error": str(final_e)
            }