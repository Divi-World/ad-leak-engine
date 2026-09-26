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
        """Run all live probes against url, return injectable page.raw data."""
        network_log = self.l2_probe.probe(url)
        telemetry = self.perf.measure(url)
        telemetry.update(self.mobile_ux.measure(url))
        telemetry.update(self.cart.measure(url))
        telemetry.update(self.api.measure(url))
        telemetry.update(self.saas.measure(url))
        telemetry.update(self.pricing.measure(url))
        return {"network_log": network_log, "telemetry": telemetry}
