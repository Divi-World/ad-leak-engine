"""BigCommerce fix generator [SEED: 2399]. Data Solutions + Script Manager + Vertical Strategy."""
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

    def generate(self, leak: Leak, platform: str, confidence: float, vertical: str | None = None) -> Fix:
        """
        Generate fix for BigCommerce stores.
        Supports vertical-aware L1 creative strategies.
        """
        if leak.tier == "L1":
            if vertical:
                return self._fix_vertical_strategy(leak, vertical, confidence)
            return self._fix_generic_strategy(leak, confidence)

        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)

        # L2: Tracking infrastructure fixes
        # [SEED: 2399] DYNAMIC PIXEL INJECTION
        pixel_id = leak.evidence.get("detected_pixel_id") or "YOUR_PIXEL_ID_HERE"
        raw_code = self.codegen.render("bigcommerce", "script_manager.js.j2")
        final_code = raw_code.replace("'YOUR_PIXEL_ID_HERE'", f"'{pixel_id}'")

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
                "code": final_code, # <--- USE FINAL_CODE, NOT UNDEFINED 'code'
            }],
            verification_steps=[
                "Go to Storefront > Script Manager and create a new script",
                "Paste the snippet and set it to load on all pages",
                "Verify the pixel fires using Meta Pixel Helper",
            ],
            rollback_steps=[
                "Delete the script from Script Manager",
            ],
            expected_outcome=f"Meta Pixel ({pixel_id}) and CAPI events fire via BigCommerce Script Manager.",
            confidence=confidence,
        )

    def _fix_vertical_strategy(self, leak: Leak, vertical: str, confidence: float) -> Fix:
        """Generates niche-specific creative advice using Jinja templates."""
        guide = self.markdown.generate("strategies", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "BigCommerce",
            "tier": "L1",
            "vertical": vertical,
            "title_map": {
                "no_video_creative": f"{vertical.replace('_',' ').title()} Video Strategy",
                "missing_cta": f"{vertical.replace('_',' ').title()} CTA Framework",
                "no_ab_variation": f"{vertical.replace('_',' ').title()} Testing Protocol",
                "retargeting_gap_not_observed": f"{vertical.replace('_',' ').title()} Retention Funnel"
            }
        })
        return Fix(
            leak_id=leak.id,
            platform="bigcommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[],
            verification_steps=[
                f"Implement the {vertical.replace('_',' ')} specific strategy outlined above.",
                "Monitor performance metrics for 7 days."
            ],
            rollback_steps=["Revert to previous creative setup."],
            expected_outcome=f"Increased relevance and conversion for {vertical.replace('_',' ')} audience.",
            confidence=confidence,
        )

    def _fix_generic_strategy(self, leak: Leak, confidence: float) -> Fix:
        """Fallback generic advice if no vertical matched."""
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