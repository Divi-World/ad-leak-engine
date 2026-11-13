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
import logging # <--- FIX: Import logging module

# Initialize module-level logger
logger = logging.getLogger(__name__)

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
        """[SEED: 2399] SELF-HEALING TELEMETRY ENGINE (NO ARCHIVE RELIANCE)

        Strategy:
        1. Run L2LiveProbe (Stealth Chromium + DOM Injection).
        2. If Blocked/Empty, Fall back to Multi-Profile Stealth Fetch (curl_cffi).
        3. If STILL Fail, Return Structured WAF_BLOCKED Result.
        """
        max_retries = 2
        last_error = None

        # --- ATTEMPT 1 & 2: Dynamic Probing (Stealth Chromium) ---
        for attempt in range(max_retries):
            try:
                network_log = self.l2_probe.probe(url)

                req_count = len(network_log.get("requests", [])) if isinstance(network_log, dict) else 0
                waf_blocked = bool(network_log.get("waf_blocked", False))

                # [FIX-2399] Success gate — trust the probe's own success signals.
                # Previously this was `req_count > 0 and not waf_blocked`, which would
                # discard a valid probe result when the funnel caught the pixel from
                # fbq_captures with zero HTTP requests (rare service-worker setups).
                # Now we also accept the case where the probe found a pixel AND its
                # Meta-side validation confirmed the pixel is real.
                probe_found_pixel = bool(network_log.get("detected_pixel_id")) if isinstance(network_log, dict) else False
                probe_has_validation = bool(
                    network_log.get("pixel_validation", {}).get("verdict") == "real_pixel_confirmed_by_config"
                ) if isinstance(network_log, dict) else False

                probe_success = (
                    (req_count > 0 and not waf_blocked)
                    or (probe_found_pixel and probe_has_validation)
                    or (probe_found_pixel and req_count > 0)
                )

                if probe_success:
                    telemetry = self.perf.measure(url)
                    telemetry.update(self.mobile_ux.measure(url))
                    telemetry.update(self.cart.measure(url))
                    telemetry.update(self.api.measure(url))
                    telemetry.update(self.saas.measure(url))
                    telemetry.update(self.pricing.measure(url))
                    return {"network_log": network_log, "telemetry": telemetry}

                # If blocked or empty, log and proceed to fallback
                if waf_blocked:
                    logger.warning(f"Primary Probe Blocked for {url}. Engaging Fallback.")
                else:
                    logger.warning(f"Primary Probe Empty for {url}. Engaging Fallback.")

            except Exception as e:
                last_error = e
                logger.error(f"Primary Probe Failed: {e}")

        # --- FALLBACK: Advanced Stealth Static Analysis (curl_cffi) ---
        try:
            from curl_cffi import requests as cffi_requests
            import re as _re_static

            html = ""
            profiles = ["chrome131", "chrome120", "safari17_0", "edge101", "firefox133"]

            for profile in profiles:
                try:
                    resp = cffi_requests.get(
                        url,
                        impersonate=profile,
                        timeout=10,
                        allow_redirects=True,
                        headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "Referer": "https://www.google.com/",
                            "Sec-Fetch-Dest": "document",
                            "Sec-Fetch-Mode": "navigate",
                            "Sec-Fetch-Site": "cross-site",
                            "Upgrade-Insecure-Requests": "1",
                        }
                    )
                    if resp.status_code == 200:
                        body_preview = resp.text[:1000].lower()
                        if any(marker in body_preview for marker in ["cloudflare", "captcha", "just a moment", "access denied"]):
                            continue
                        html = resp.text
                        break
                except Exception:
                    continue

            if html:
                minimal_network_log = {
                    "requests": [],
                    "pixel_fired": False,
                    "waf_blocked": False, # We got HTML, so technically not blocked by WAF *for this fetch*
                    "fallback_mode": True,
                    "source": "CURL_CFFI_STEALTH",
                    "error_context": str(last_error) if last_error else "Static Fallback."
                }

                detected_pixel_id = None
                m = _re_static.search(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]\s*\)""", html)
                if m:
                    detected_pixel_id = m.group(1)
                    minimal_network_log["static_pixel_detected"] = True
                    minimal_network_log["detected_pixel_id"] = detected_pixel_id
                    minimal_network_log["pixel_fired"] = True # Mark as fired since we found init code

                perf_data = self.perf.measure_static(html) if hasattr(self.perf, 'measure_static') else {}
                return {
                    "network_log": minimal_network_log,
                    "telemetry": perf_data,
                    "collection_status": "FALLBACK_STEALTH_STATIC_SUCCESS"
                }

        except Exception as static_e:
            logger.debug(f"Static Fallback failed: {static_e}")

        # Absolute worst case: Return Clean Block Status
        return {
            "network_log": {
                "requests": [],
                "pixel_fired": False,
                "waf_blocked": True,
                "fallback_mode": True,
                "error_context": "All methods failed. Site protected by aggressive WAF."
            },
            "telemetry": {},
            "collection_status": "TOTAL_FAILURE_WAF"
        }