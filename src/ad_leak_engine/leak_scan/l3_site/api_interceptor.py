"""Public API Interception for Inventory/Dependency Analysis [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class ApiInterceptor:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                
                # Count third-party API calls/scripts
                third_party_calls = page.evaluate("""() => {
                    const scripts = Array.from(document.querySelectorAll('script[src]'));
                    return scripts.filter(s => !s.src.includes(window.location.hostname)).length;
                }""")
                telemetry["third_party_script_count"] = int(third_party_calls) if third_party_calls else 0
                
                # Check for known heavy third-party apps
                has_heavy_apps = page.evaluate("""() => {
                    const html = document.documentElement.innerHTML.toLowerCase();
                    return html.includes('klaviyo') || html.includes('yotpo') || html.includes('loox') || html.includes('privy');
                }""")
                telemetry["has_heavy_third_party_apps"] = bool(has_heavy_apps)
        except Exception as e:
            telemetry["api_intercept_error"] = str(e)
        return telemetry
