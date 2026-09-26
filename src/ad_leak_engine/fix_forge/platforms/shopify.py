"""Shopify fix generator [SEED: 2399]. theme.liquid + Customer Events API."""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class ShopifyFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["shopify"]

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        if leak.tier == "L1":
            return self._fix_strategy(leak, confidence)
        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)
        # L2: Tracking infrastructure fixes
        if leak.signal == "pixel_not_firing":
            return self._fix_pixel(leak, confidence)
        return self._fix_customer_events(leak, confidence)

    def _fix_pixel(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("shopify", "pixel_base.liquid.j2")
        guide = self.markdown.generate("shopify", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Shopify",
        })
        return Fix(
            leak_id=leak.id,
            platform="shopify",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "liquid",
                "filename": "theme.liquid",
                "location": "<head>",
                "code": code,
            }],
            verification_steps=[
                "Go to Shopify Admin > Online Store > Themes > Edit Code",
                "Open theme.liquid and confirm the pixel snippet is inside <head>",
                "Visit your storefront with the Meta Pixel Helper extension installed",
                "Confirm the PageView event fires with your Pixel ID",
            ],
            rollback_steps=[
                "Open theme.liquid in the Shopify code editor",
                "Remove the Meta Pixel snippet from <head>",
                "Click Save",
            ],
            expected_outcome="Meta Pixel fires PageView on every storefront page, restoring conversion tracking.",
            confidence=confidence,
        )

    def _fix_customer_events(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("shopify", "customer_events.js.j2")
        guide = self.markdown.generate("shopify", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Shopify",
        })
        return Fix(
            leak_id=leak.id,
            platform="shopify",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "javascript",
                "filename": "customer-events.js",
                "location": "Shopify Admin > Settings > Customer Events > Add custom pixel",
                "code": code,
            }],
            verification_steps=[
                "Go to Shopify Admin > Settings > Customer Events",
                "Click 'Add custom pixel' and paste the snippet",
                "Confirm the pixel shows 'Connected' status",
                "Place a test order and verify events appear in Meta Events Manager",
            ],
            rollback_steps=[
                "Go to Settings > Customer Events",
                "Remove the custom pixel",
                "Click Save",
            ],
            expected_outcome="All 6 Shopify Customer Events fire server-side with deduplicated event_ids.",
            confidence=confidence,
        )

    def _fix_strategy(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("shopify", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Shopify",
            "tier": "L1",
        })
        return Fix(
            leak_id=leak.id,
            platform="shopify",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[],
            verification_steps=[
                "Review current ad creatives in Meta Ads Manager",
                "Implement the strategic recommendation outlined in this guide",
                "Monitor CTR, CPM, and CPA for 7-14 days",
                "Compare performance against the pre-change baseline",
            ],
            rollback_steps=[
                "Revert to previous ad creative or campaign structure in Meta Ads Manager",
            ],
            expected_outcome="Improved ad relevance, lower CPM, and higher conversion rate through disciplined creative strategy.",
            confidence=confidence,
        )

    def _fix_site_performance(self, leak: Leak, confidence: float) -> Fix:
        code_blocks = []
        if leak.signal == "no_mobile_viewport":
            code = self.codegen.render("shopify", "viewport_fix.html.j2")
            code_blocks.append({
                "language": "html",
                "filename": "theme.liquid",
                "location": "<head>",
                "code": code,
            })
        elif leak.signal == "small_tap_targets":
            code = self.codegen.render("shopify", "tap_targets.css.j2")
            code_blocks.append({
                "language": "css",
                "filename": "base.css",
                "location": "Global stylesheet (Shopify Admin > Online Store > Themes > Edit Code > Assets)",
                "code": code,
            })
        guide = self.markdown.generate("shopify", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Shopify",
            "tier": "L3",
        })
        return Fix(
            leak_id=leak.id,
            platform="shopify",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=code_blocks,
            verification_steps=[
                "Apply the fix to your Shopify theme",
                "Open your storefront on a mobile device or Chrome DevTools mobile emulation",
                "Verify the fix is visible and functional",
                "Run Google PageSpeed Insights to confirm improvement",
            ],
            rollback_steps=[
                "Remove the added code from your Shopify theme",
                "Click Save in the theme editor",
            ],
            expected_outcome="Improved mobile user experience, faster page load, and higher conversion rate from paid traffic.",
            confidence=confidence,
        )
