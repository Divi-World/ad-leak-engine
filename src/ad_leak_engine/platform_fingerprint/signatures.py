"""Platform detection markers for Ad-Leak-Engine [SEED: 2399].

Each platform has primary markers (high confidence) and secondary
markers (supporting evidence). Detection requires at least 2 primary
markers for high confidence.
"""

PLATFORM_SIGNATURES = {
    "shopify": {
        "primary": [
            "cdn.shopify.com",
            "Shopify.theme",
            "/cart.js",
            "ShopifyAnalytics",      # Upgraded: Highly reliable indicator
            "shopifycdn.com",        # Added: Common CDN variant
        ],
        "secondary": [
            "myshopify.com",
            "X-ShopId",
            "shopify-checkout",
        ],
    },
    "woocommerce": {
        "primary": [
            "wp-content/plugins/woocommerce",
            "wc-ajax",
            "wp-json/wc/",           # Upgraded: Highly reliable REST API endpoint
        ],
        "secondary": [
            "woocommerce",
            "wc-store-api",
            "woocommerce_session",
        ],
    },
    "bigcommerce": {
        "primary": [
            "cdn11.bigcommerce.com",
            "stencil",
            "bigcommerce.com",       # Upgraded: Highly reliable domain presence
        ],
        "secondary": [
            "X-Bc-",
            "bc-cart",
        ],
    },
    "webflow": {
        "primary": [
            "webflow.com",
            "w-webflow-badge",
            "data-w-id",             # Upgraded: Unique Webflow DOM attribute
        ],
        "secondary": [
            "wf-page",
            "webflow.js",
        ],
    },
}

# Custom platform is the fallback when no signatures match
CUSTOM_PLATFORM = "custom"
CUSTOM_CONFIDENCE = 0.3
