"""Fix Forge orchestrator [SEED: 2399]. Routes leaks to platform generators."""
from ..shared.schemas import Leak, Fix
from ..shared.exceptions import PlatformAmbiguousError
from .platforms.shopify import ShopifyFixGenerator
from .platforms.woocommerce import WooCommerceFixGenerator
from .platforms.bigcommerce import BigCommerceFixGenerator
from .platforms.custom import CustomFixGenerator


class FixForge:
    def __init__(self):
        self.generators = {
            "shopify": ShopifyFixGenerator(),
            "woocommerce": WooCommerceFixGenerator(),
            "bigcommerce": BigCommerceFixGenerator(),
            "custom": CustomFixGenerator(),
        }

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        # Platform-specific code injection requires confidence >= 0.5.
        # Custom/generic fixes (GTM, server-side) are safe for ANY platform,
        # so they bypass the gate — a 'custom' site still gets working fixes.
        if platform != "custom" and confidence < 0.5:
            raise PlatformAmbiguousError(
                f"Platform confidence {confidence} too low for {platform} codegen"
            )
        generator = self.generators.get(platform, self.generators["custom"])
        return generator.generate(leak, platform, confidence)
