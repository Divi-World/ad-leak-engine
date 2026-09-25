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
