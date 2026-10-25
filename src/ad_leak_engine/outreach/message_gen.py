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

    def _extract_observation(self, leak) -> str:
        sig = getattr(leak, "signal", "") or ""
        ev = getattr(leak, "evidence", {}) or {}
        if not isinstance(ev, dict):
            ev = {}

        def _ms_to_human(value, unit="s"):
            try:
                ms = float(value)
            except Exception:
                return None
            if ms <= 0:
                return None
            if ms >= 1000:
                return f"{ms / 1000.0:.1f}{unit}"
            return f"{int(ms)}ms"

        if sig == "creative_fatigue":
            days = ev.get("days_running")
            if days:
                return f"your oldest active ad has been running for {days} days without refresh"
            return "your creative portfolio shows fatigue risk"

        if sig == "no_ab_variation":
            count = ev.get("active_ad_count")
            if count is not None:
                return f"you are running only {count} active ad(s) with no A/B variation"
            return "you have too few active ad variations for reliable learning"

        if sig == "no_video_creative":
            return "no video creatives are active in the sampled ad pool"

        if sig == "spend_without_testing":
            spend = ev.get("lower_spend")
            count = ev.get("active_ad_count")
            if spend is not None and count is not None:
                return f"estimated spend is high ({spend}) while only {count} active ad variant(s) are observed"
            return "spend is running without enough creative testing"

        if sig == "missing_cta":
            return "your active ads use weak or missing call-to-action buttons"

        if sig == "generic_hook":
            return "your ad copy uses generic hooks without enough specific geo, pain point, or offer clarity"

        if sig == "pixel_not_firing":
            return "your Meta Pixel is not firing on the landing page"

        if sig == "pixel_script_detected_but_not_firing":
            return "your Meta Pixel scripts are present but not firing a PageView event"

        if sig == "telemetry_blind_spot":
            code = ev.get("telemetry_reason_code") or ""
            if code == "waf_blocked":
                return "automated telemetry was blocked by bot protection/WAF"
            if code == "no_telemetry_captured":
                return "automated telemetry captured no usable network requests"
            if code == "insufficient_telemetry":
                count = ev.get("network_requests") or "low"
                return f"automated telemetry was insufficient ({count}) and may be affected by timeout, SPA delay, consent gating, or bot protection"
            return "automated telemetry was incomplete, so conversion signals cannot be verified"

        if sig == "no_retargeting":
            return "no retargeting markers were observed in the sampled public ad pool"

        if sig == "retargeting_gap_not_observed":
            sampled = ev.get("sampled_active_ads")
            if sampled:
                return f"we observed {sampled} active ads but no retargeting/BOFU audience markers in the sampled Meta Ad Library pool"
            return "no retargeting/BOFU audience markers were observed in the sampled Meta Ad Library pool"

        if sig == "retargeting_event_depth_gap":
            intent = (ev.get("intent") or "unknown").replace("_", " ")
            missing = ev.get("missing_events") or []
            missing_text = ", ".join(missing[:4]) if missing else "key conversion events"
            return f"your site appears {intent}-oriented, but {missing_text} were not observed, so retargeting audiences will be thin"

        if sig == "retargeting_pool_integrity_risk":
            return "pixel/CAPI telemetry is missing or unreliable, so retargeting pools cannot be trusted"

        if sig == "missing_initiate_checkout":
            return "InitiateCheckout events were not observed on a page with checkout/cart intent"

        if sig == "missing_add_to_cart":
            return "AddToCart events were not observed on a page with product/cart intent"

        if sig == "missing_purchase_event":
            return "Purchase events were not observed on checkout"

        if sig == "unhashed_pii":
            return "CAPI payloads contain unhashed PII, reducing event match quality and compliance posture"

        if sig == "capi_dedup_failure":
            return "browser and server events are not deduplicated by event_id, causing inflated or ambiguous conversion signals"

        if sig == "attribution_gap":
            return "ad spend is observable but conversion signals are missing, making ROAS optimization unreliable"

        if sig == "slow_lcp_mobile":
            raw = ev.get("lcp_mobile_ms") or ev.get("lcp_ms") or ev.get("mobile_lcp_ms")
            human = _ms_to_human(raw)
            if human:
                return f"mobile Largest Contentful Paint is slow at {human}"
            return "mobile Largest Contentful Paint is slow"

        if sig == "slow_ttfb":
            raw = ev.get("ttfb_ms") or ev.get("ttfb")
            human = _ms_to_human(raw)
            if human:
                return f"server response time is slow at {human} TTFB"
            return "server response time is slow"

        if sig == "small_tap_targets":
            min_px = ev.get("min_tap_target_px")
            if min_px:
                return f"mobile tap targets are too small, with minimum observed target around {min_px}px"
            return "mobile tap targets are smaller than the 48px usability threshold"

        if sig == "checkout_friction":
            steps = ev.get("checkout_steps")
            if steps:
                return f"checkout has {steps} steps, creating paid-traffic friction"
            return "checkout flow has excessive friction"

        if sig == "pixel_blocking_scripts":
            count = ev.get("scripts_before_pixel")
            if count:
                return f"{count} third-party scripts may be delaying or blocking pixel execution"
            return "third-party scripts may be delaying or blocking pixel execution"

        if sig == "mixed_content":
            return "the page serves mixed HTTP/HTTPS content, which can break tracking and trust"

        if sig == "no_ssl":
            return "the landing page lacks valid SSL, which can block conversions and tracking"

        return "we found a " + sig.replace("_", " ") + " issue"
