"""REAL mobile UX analysis via camoufox [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class MobileUXAnalyzer:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 3.0)

                min_tap = page.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('a,button,input,select,[role=button]'));"
                    " const sizes = els.map(e => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height); }).filter(s => s > 0);"
                    " return sizes.length ? Math.min(...sizes) : null; }"
                )
                if min_tap is not None: telemetry["min_tap_target_px"] = min_tap
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
