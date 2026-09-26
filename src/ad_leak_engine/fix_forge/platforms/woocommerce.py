"""WooCommerce fix generator [SEED: 2399]. functions.php CAPI + plugin guides."""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class WooCommerceFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["woocommerce"]

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        if leak.tier == "L1":
            return self._fix_strategy(leak, confidence)
        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)
        # L2: Tracking infrastructure fixes
        if leak.signal == "pixel_not_firing":
            return self._fix_plugin(leak, confidence)
        return self._fix_capi(leak, confidence)

    def _fix_plugin(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[],
            verification_steps=[
                "Install a Meta Pixel plugin (Conversios or Pixel Manager)",
                "Connect your Meta account and Pixel ID",
                "Verify the pixel fires using Meta Pixel Helper",
            ],
            rollback_steps=[
                "Deactivate and delete the Meta Pixel plugin",
            ],
            expected_outcome="Meta Pixel fires on all WooCommerce pages via plugin.",
            confidence=confidence,
        )

    def _fix_capi(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("woocommerce", "functions_snippet.php.j2")
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "php",
                "filename": "functions.php",
                "location": "Child theme functions.php (bottom of file)",
                "code": code,
            }],
            verification_steps=[
                "Add the snippet to your child theme's functions.php",
                "Replace YOUR_PIXEL_ID_HERE and YOUR_ACCESS_TOKEN_HERE",
                "Place a test order",
                "Check Meta Events Manager for a server-side Purchase event with event_id",
            ],
            rollback_steps=[
                "Remove the added snippet from functions.php",
                "Clear any caching plugins",
            ],
            expected_outcome="Server-side Purchase events fire with hashed PII and deduplicated event_ids.",
            confidence=confidence,
        )

    def _fix_strategy(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
            "tier": "L1",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
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
            code = self.codegen.render("woocommerce", "viewport_fix.html.j2")
            code_blocks.append({
                "language": "html",
                "filename": "header.php",
                "location": "<head> section of your child theme header.php",
                "code": code,
            })
        elif leak.signal == "small_tap_targets":
            code = self.codegen.render("woocommerce", "tap_targets.css.j2")
            code_blocks.append({
                "language": "css",
                "filename": "style.css",
                "location": "Child theme stylesheet",
                "code": code,
            })
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
            "tier": "L3",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=code_blocks,
            verification_steps=[
                "Apply the fix to your WordPress child theme",
                "Open your storefront on a mobile device or Chrome DevTools mobile emulation",
                "Verify the fix is visible and functional",
                "Run Google PageSpeed Insights to confirm improvement",
            ],
            rollback_steps=[
                "Remove the added code from your child theme files",
                "Clear any caching plugins",
            ],
            expected_outcome="Improved mobile user experience, faster page load, and higher conversion rate from paid traffic.",
            confidence=confidence,
        )
