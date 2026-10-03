
# ============================================================
# [SEED: 2399] ENTERPRISE CMS & NICHE PRE-FLIGHT CLASSIFIER
# Prevents Shopify pollution on Enterprise/Custom sites (Ulta, Amazon, etc.)
# ============================================================
import re

def detect_cms(html: str, url: str) -> str:
    html_lower = html.lower()
    if "shopify" in html_lower or "cdn.shopify.com" in html_lower or "shopify.checkout" in html_lower:
        return "shopify"
    elif "woocommerce" in html_lower or "wp-content/plugins/woocommerce" in html_lower:
        return "woocommerce"
    elif "magento" in html_lower or "mage/" in html_lower or "x-magento-init" in html_lower:
        return "magento"
    elif "wix.com" in html_lower or "wixstatic.com" in html_lower:
        return "wix"
    elif "squarespace" in html_lower:
        return "squarespace"
    elif "amazon" in url or "ulta.com" in url or "alibaba" in url:
        return "enterprise_marketplace"
    return "custom"

def get_fix_context(cms: str) -> dict:
    if cms == "shopify":
        return {"platform": "Shopify", "file_hint": "theme.liquid / customer-events.js", "confidence": 95}
    elif cms == "woocommerce":
        return {"platform": "WordPress/WooCommerce", "file_hint": "functions.php / Google Tag Manager", "confidence": 90}
    elif cms == "enterprise_marketplace":
        return {"platform": "Enterprise Marketplace", "file_hint": "Server-Side CAPI / GTM", "confidence": 80}
    else:
        return {"platform": "Custom / Headless", "file_hint": "Global <head> / Server-Side Webhook", "confidence": 70}
