"""Shopify fix generator [SEED: 2399]. theme.liquid + Customer Events API + Vertical Strategy."""
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

    def generate(self, leak: Leak, platform: str, confidence: float, vertical: str | None = None) -> Fix:
        """
        Generate fix for Shopify stores.
        Supports vertical-aware L1 creative strategies.
        """
        if leak.tier == "L1":
            # Route to vertical-specific strategy if resolved, otherwise generic
            if vertical:
                return self._fix_vertical_strategy(leak, vertical, confidence)
            return self._fix_generic_strategy(leak, confidence)
        
        elif leak.tier == "L3":
            return self._fix_site_performance(leak, confidence)
        
        # L2: Tracking infrastructure fixes
        if leak.signal == "pixel_not_firing":
            return self._fix_pixel(leak, confidence)
        return self._fix_customer_events(leak, confidence)

    def _fix_vertical_strategy(self, leak: Leak, vertical: str, confidence: float) -> Fix:
        """Generates niche-specific creative advice using Jinja templates."""
        guide = self.markdown.generate("strategies", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Shopify",
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
            platform="shopify",
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

    def _fix_pixel(self, leak: Leak, confidence: float) -> Fix:
        # [SEED: 2399] DYNAMIC PIXEL INJECTION
        pixel_id = leak.evidence.get("detected_pixel_id") or "YOUR_PIXEL_ID_HERE"
        
        # Pass pixel_id to renderer (Assuming CodeGenerator supports kwargs/context)
        # If your CodeGenerator.render signature is fixed, you may need to update templates 
        # to use {{ pixel_id }} instead of hardcoded strings.
        # For now, we assume render accepts a context dict or we string-replace post-render.
        
        raw_code = self.codegen.render("shopify", "pixel_base.liquid.j2")
        final_code = raw_code.replace("'YOUR_PIXEL_ID_HERE'", f"'{pixel_id}'")
        
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
                "code": final_code, # <--- INJECTED CODE
            }],
            verification_steps=[
                "Go to Shopify Admin > Online Store > Themes > Edit Code",
                "Open theme.liquid and confirm the pixel snippet is inside <head>",
                "Visit your storefront with the Meta Pixel Helper extension installed",
                "Confirm the PageView event fires with YOUR SPECIFIC PIXEL ID",
            ],
            rollback_steps=[
                "Open theme.liquid in the Shopify code editor",
                "Remove the Meta Pixel snippet from <head>",
                "Click Save",
            ],
            expected_outcome=f"Meta Pixel ({pixel_id}) fires PageView on every storefront page, restoring conversion tracking.",
            confidence=confidence,
        )

    def _fix_customer_events(self, leak: Leak, confidence: float) -> Fix:
        # [SEED: 2399] DYNAMIC PIXEL INJECTION
        pixel_id = leak.evidence.get("detected_pixel_id") or "YOUR_PIXEL_ID_HERE"
        raw_code = self.codegen.render("shopify", "customer_events.js.j2")
        final_code = raw_code.replace("'YOUR_PIXEL_ID_HERE'", f"'{pixel_id}'")
        
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
                "code": final_code,
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
            expected_outcome=f"All 6 Shopify Customer Events fire server-side with deduplicated event_ids using Pixel {pixel_id}.",
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