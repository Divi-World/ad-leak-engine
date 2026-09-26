"""BigCommerce fix generator [SEED: 2399]. Data Solutions + Script Manager."""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class BigCommerceFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["bigcommerce"]

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        if leak.tier == "L1":
            return self._fix_strategy(leak, confidence)
        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)
        # L2: Tracking infrastructure fixes
        code = self.codegen.render("bigcommerce", "script_manager.js.j2")
        guide = self.markdown.generate("bigcommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "BigCommerce",
        })
        return Fix(
            leak_id=leak.id,
            platform="bigcommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "javascript",
                "filename": "script-manager.js",
                "location": "Storefront > Script Manager > Create Script",
                "code": code,
            }],
            verification_steps=[
                "Go to Storefront > Script Manager and create a new script",
                "Paste the snippet and set it to load on all pages",
                "Verify the pixel fires using Meta Pixel Helper",
            ],
            rollback_steps=[
                "Delete the script from Script Manager",
            ],
            expected_outcome="Meta Pixel and CAPI events fire via BigCommerce Script Manager.",
            confidence=confidence,
        )

    def _fix_strategy(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("bigcommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "BigCommerce",
            "tier": "L1",
        })
        return Fix(
            leak_id=leak.id,
            platform="bigcommerce",
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
            code = self.codegen.render("bigcommerce", "viewport_fix.html.j2")
            code_blocks.append({
                "language": "html",
                "filename": "head.html",
                "location": "BigCommerce Admin > Storefront > Script Manager (head section)",
                "code": code,
            })
        elif leak.signal == "small_tap_targets":
            code = self.codegen.render("bigcommerce", "tap_targets.css.j2")
            code_blocks.append({
                "language": "css",
                "filename": "theme.css",
                "location": "BigCommerce Admin > Storefront > Script Manager (CSS injection)",
                "code": code,
            })
        guide = self.markdown.generate("bigcommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "BigCommerce",
            "tier": "L3",
        })
        return Fix(
            leak_id=leak.id,
            platform="bigcommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=code_blocks,
            verification_steps=[
                "Apply the fix via BigCommerce Script Manager or theme editor",
                "Open your storefront on a mobile device or Chrome DevTools mobile emulation",
                "Verify the fix is visible and functional",
                "Run Google PageSpeed Insights to confirm improvement",
            ],
            rollback_steps=[
                "Remove the script from BigCommerce Script Manager",
            ],
            expected_outcome="Improved mobile user experience, faster page load, and higher conversion rate from paid traffic.",
            confidence=confidence,
        )
