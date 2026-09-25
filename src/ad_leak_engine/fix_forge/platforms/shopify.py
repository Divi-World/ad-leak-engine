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
