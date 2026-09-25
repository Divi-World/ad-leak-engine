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
        ],
        "secondary": [
            "myshopify.com",
            "X-ShopId",
            "shopify-checkout",
            "ShopifyAnalytics",
        ],
    },
    "woocommerce": {
        "primary": [
            "wp-content/plugins/woocommerce",
            "wc-ajax",
        ],
        "secondary": [
            "woocommerce",
            "wp-json/wc/",
            "wc-store-api",
            "woocommerce_session",
        ],
    },
    "bigcommerce": {
        "primary": [
            "cdn11.bigcommerce.com",
            "stencil",
        ],
        "secondary": [
            "bigcommerce.com",
            "X-Bc-",
            "bc-cart",
        ],
    },
    "webflow": {
        "primary": [
            "webflow.com",
            "w-webflow-badge",
        ],
        "secondary": [
            "data-w-id",
            "wf-page",
            "webflow.js",
        ],
    },
}

# Custom platform is the fallback when no signatures match
CUSTOM_PLATFORM = "custom"
CUSTOM_CONFIDENCE = 0.3
