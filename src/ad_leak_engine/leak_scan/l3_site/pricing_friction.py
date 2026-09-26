"""Pricing Friction Analysis [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class PricingFrictionAnalyzer:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                
                friction_score = 0
                has_forced_account = page.evaluate("""() => {
                    const text = document.body.innerText.toLowerCase();
                    return text.includes('create account to see price') || text.includes('login required to view pricing');
                }""")
                if has_forced_account:
                    friction_score += 1
                    
                telemetry["pricing_friction_score"] = friction_score
                telemetry["has_forced_account_for_pricing"] = bool(has_forced_account)
        except Exception as e:
            telemetry["pricing_friction_error"] = str(e)
        return telemetry
