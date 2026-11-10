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
        """[SEED: 2399] SELF-HEALING TELEMETRY ENGINE WITH ADVANCED WAF BYPASS
        
        Strategy:
        1. Attempt Full Dynamic Probe (Playwright).
        2. If Fail/Empty, Retry once with extended timeout.
        3. If Still Fail, Fall back to Multi-Profile Stealth Fetch (curl_cffi).
           - Tries Chrome, Safari, Firefox impersonations.
           - Parses Static HTML for Pixel IDs to prevent 'False Negative' on L2.
        4. Never return empty dict unless URL is totally unreachable.
        """
        max_retries = 2
        last_error = None

        # --- ATTEMPT 1 & 2: Dynamic Probing (Playwright) ---
        for attempt in range(max_retries):
            try:
                network_log = self.l2_probe.probe(url)

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

        # --- FALLBACK: Advanced Stealth Static Analysis (WAF Bypass Mode) ---
        # We try multiple browser fingerprints to evade basic bot detection
        try:
            from curl_cffi import requests as cffi_requests
            import re as _re_static
            
            html = ""
            resp_status = 0
            
            # Profiles to try: Chrome, Safari, Edge, Firefox
            profiles = ["chrome120", "safari17_0", "edge101", "firefox133"]
            
            for profile in profiles:
                try:
                    resp = cffi_requests.get(
                        url, 
                        impersonate=profile, 
                        timeout=15,
                        allow_redirects=True
                    )
                    if resp.status_code == 200:
                        # Check if we got a challenge page instead of real content
                        body_preview = resp.text[:500].lower()
                        if "cloudflare" in body_preview or "captcha" in body_preview or "just a moment" in body_preview:
                            continue # Skip this profile, try next
                        
                        html = resp.text
                        resp_status = 200
                        break # Got clean HTML
                except Exception:
                    continue

            if not html:
                raise Exception("All stealth profiles failed or returned challenge pages.")

            # Construct minimal valid structure
            minimal_network_log = {
                "requests": [],
                "pixel_fired": False,
                "waf_blocked": True, # Mark as WAF Blocked so L2 knows context
                "fallback_mode": True,
                "error_context": str(last_error) if last_error else "Dynamic probe returned empty; using static fallback."
            }

            # [SEED: 2399] CRITICAL UPGRADE: Extract Pixel ID from Static HTML
            detected_pixel_id = None
            if html:
                # Regex for fbq('init', 'ID')
                m = _re_static.search(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]\s*\)""", html)
                if m:
                    detected_pixel_id = m.group(1)
                
                # Add this to network_log so L2 Scanner can find it
                if detected_pixel_id:
                    minimal_network_log["static_pixel_detected"] = True
                    minimal_network_log["detected_pixel_id"] = detected_pixel_id

            perf_data = self.perf.measure_static(html) if hasattr(self.perf, 'measure_static') else {}

            return {
                "network_log": minimal_network_log,
                "telemetry": perf_data,
                "collection_status": "FALLBACK_STEALTH_STATIC_SUCCESS"
            }

        except Exception as final_e:
            # Absolute worst case: Return structured error so pipeline continues
            return {
                "network_log": {},
                "telemetry": {},
                "collection_status": "TOTAL_FAILURE",
                "final_error": str(final_e)
            }