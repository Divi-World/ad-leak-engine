"""Custom fix generator [SEED: 2399]. GTM tag + server-side webhook."""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class CustomFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["custom"]

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        if leak.tier == "L1":
            return self._fix_strategy(leak, confidence)
        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)
        # L2: Tracking infrastructure fixes
        if leak.signal == "pixel_not_firing":
            return self._fix_gtm(leak, confidence)
        return self._fix_server_side(leak, confidence)

    def _fix_gtm(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("custom", "gtm_tag.html.j2")
        guide = self.markdown.generate("custom", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Custom",
        })
        return Fix(
            leak_id=leak.id,
            platform="custom",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "html",
                "filename": "gtm-tag.html",
                "location": "Google Tag Manager > Tags > New > Custom HTML",
                "code": code,
            }],
            verification_steps=[
                "Create a Custom HTML tag in Google Tag Manager",
                "Paste the snippet and set trigger to All Pages",
                "Publish the container and verify with Meta Pixel Helper",
            ],
            rollback_steps=[
                "Delete or pause the GTM tag",
                "Publish the container",
            ],
            expected_outcome="Meta Pixel fires on all pages via Google Tag Manager.",
            confidence=confidence,
        )

    def _fix_server_side(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("custom", "server_webhook.py.j2")
        guide = self.markdown.generate("custom", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Custom",
        })
        return Fix(
            leak_id=leak.id,
            platform="custom",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "python",
                "filename": "capi_webhook.py",
                "location": "Server-side endpoint (deploy to your backend)",
                "code": code,
            }],
            verification_steps=[
                "Deploy the webhook to your backend",
                "Call POST /orders/create on checkout completion",
                "Verify the server event appears in Meta Events Manager",
            ],
            rollback_steps=[
                "Remove the webhook endpoint from your backend",
            ],
            expected_outcome="Server-side Purchase events sent to Meta CAPI with hashed PII.",
            confidence=confidence,
        )

    def _fix_strategy(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("custom", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Custom",
            "tier": "L1",
        })
        return Fix(
            leak_id=leak.id,
            platform="custom",
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
            code = self.codegen.render("custom", "viewport_fix.html.j2")
            code_blocks.append({
                "language": "html",
                "filename": "index.html",
                "location": "<head> section of your landing page HTML",
                "code": code,
            })
        elif leak.signal == "small_tap_targets":
            code = self.codegen.render("custom", "tap_targets.css.j2")
            code_blocks.append({
                "language": "css",
                "filename": "styles.css",
                "location": "Global stylesheet",
                "code": code,
            })
        guide = self.markdown.generate("custom", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Custom",
            "tier": "L3",
        })
        return Fix(
            leak_id=leak.id,
            platform="custom",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=code_blocks,
            verification_steps=[
                "Apply the fix to your landing page codebase",
                "Open your landing page on a mobile device or Chrome DevTools mobile emulation",
                "Verify the fix is visible and functional",
                "Run Google PageSpeed Insights to confirm improvement",
            ],
            rollback_steps=[
                "Remove the added code from your codebase",
                "Redeploy the previous version",
            ],
            expected_outcome="Improved mobile user experience, faster page load, and higher conversion rate from paid traffic.",
            confidence=confidence,
        )
