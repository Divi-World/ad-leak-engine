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
