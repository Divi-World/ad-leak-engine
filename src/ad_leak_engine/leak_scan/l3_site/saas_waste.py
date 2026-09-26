"""SaaS Waste Detection: Identifies paid apps that are broken or misconfigured [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class SaasWasteAnalyzer:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                
                # Detect presence of known paid SaaS apps for audit reporting
                detected_apps = page.evaluate("""() => {
                    const html = document.documentElement.innerHTML.toLowerCase();
                    const paidApps = ['klaviyo', 'yotpo', 'loox', 'privy', 'justuno', 'recharge'];
                    return paidApps.filter(app => html.includes(app));
                }""")
                telemetry["detected_paid_saas_apps"] = detected_apps if detected_apps else []
        except Exception as e:
            telemetry["saas_waste_error"] = str(e)
        return telemetry
