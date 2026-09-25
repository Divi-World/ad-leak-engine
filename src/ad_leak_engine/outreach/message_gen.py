"""Data-backed outreach text generation [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..shared.schemas import Page, Leak, Fix

TEMPLATE_DIR = Path(__file__).parent / "templates"


class MessageGenerator:
    """Generates personalized, data-backed outreach messages."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_message(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> str:
        template = self.env.get_template("message.txt.j2")
        top_leak = max(leaks, key=lambda l: l.severity) if leaks else None
        observation = self._extract_observation(top_leak) if top_leak else "your ad tracking is incomplete"
        return template.render(
            page=page, top_leak=top_leak, leak_count=len(leaks), observation=observation
        )

    def generate_executive_summary(self, page: Page, leaks: list[Leak]) -> str:
        template = self.env.get_template("executive_summary.txt.j2")
        return template.render(page=page, leak_count=len(leaks))

    def _extract_observation(self, leak: Leak) -> str:
        """Pull a specific, data-backed observation from the leak's evidence."""
        sig = leak.signal
        ev = leak.evidence or {}
        if sig == "creative_fatigue":
            days = ev.get("days_running")
            return f"your oldest active ad has been running {days} days without a refresh" if days else "your creative shows signs of fatigue"
        if sig == "slow_lcp_mobile":
            lcp = ev.get("lcp_mobile_ms")
            return f"your landing page takes {lcp/1000:.1f}s to render on mobile" if lcp else "your landing page loads slowly on mobile"
        if sig == "slow_ttfb":
            ttfb = ev.get("ttfb_ms")
            return f"your server takes {ttfb}ms to respond" if ttfb else "your server response is slow"
        if sig == "pixel_not_firing":
            return "your Meta Pixel is not firing on the landing page"
        if sig == "unhashed_pii":
            return "your Conversions API is sending unhashed customer data"
        if sig == "missing_purchase_event":
            return "your checkout is not sending the Purchase event to Meta"
        if sig == "checkout_friction":
            steps = ev.get("checkout_steps")
            return f"your checkout requires {steps} steps" if steps else "your checkout has too many steps"
        if sig == "no_ab_variation":
            count = ev.get("active_ad_count")
            return f"you are running only {count} active ad(s) with no A/B variation" if count else "you have no A/B ad variation"
        return f"we detected a {sig.replace('_', ' ')} issue"
