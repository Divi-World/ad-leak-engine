"""Cart and Checkout Friction Analysis [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class CartAnalyzer:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                # Check for forced account creation before viewing cart/pricing
                has_forced_login = page.evaluate("""() => {
                    const text = document.body.innerText.toLowerCase();
                    return text.includes('must log in') || text.includes('create an account to checkout') || text.includes('login required');
                }""")
                telemetry["has_forced_login_friction"] = bool(has_forced_login)
        except Exception as e:
            telemetry["cart_analysis_error"] = str(e)
        return telemetry
