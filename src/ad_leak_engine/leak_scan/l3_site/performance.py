"""REAL Core Web Vitals measurement via camoufox [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class PerformanceAuditor:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 4.0)

                ttfb = page.evaluate(
                    "() => { const n = performance.getEntriesByType('navigation')[0];"
                    " return n ? n.responseStart - n.requestStart : null; }"
                )
                if ttfb and ttfb > 0: telemetry["ttfb_ms"] = ttfb

                lcp = page.evaluate(
                    "() => { const e = performance.getEntriesByType('largest-contentful-paint');"
                    " return e.length ? e[e.length-1].startTime : null; }"
                )
                if lcp: telemetry["lcp_mobile_ms"] = lcp
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
