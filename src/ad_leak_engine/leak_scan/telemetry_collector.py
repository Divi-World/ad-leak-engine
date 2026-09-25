"""Collects REAL telemetry from a live landing page [SEED: 2399].

This is the reality bridge: it runs live Playwright probes and returns the
{'network_log': ..., 'telemetry': ...} dict that the L2/L3 scanners consume.
"""
from .l2_probe import L2LiveProbe
from .l3_site.performance import PerformanceAuditor
from .l3_site.mobile_ux import MobileUXAnalyzer


class TelemetryCollector:
    def __init__(self):
        self.l2_probe = L2LiveProbe()
        self.perf = PerformanceAuditor()
        self.mobile_ux = MobileUXAnalyzer()

    def collect(self, url: str) -> dict:
        """Run all live probes against url, return injectable page.raw data."""
        network_log = self.l2_probe.probe(url)
        telemetry = self.perf.measure(url)
        telemetry.update(self.mobile_ux.measure(url))
        return {"network_log": network_log, "telemetry": telemetry}
