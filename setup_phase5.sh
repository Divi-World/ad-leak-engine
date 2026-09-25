#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 5: Fix Forge
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 5 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ---------- 2. Directories ----------
mkdir -p src/ad_leak_engine/fix_forge/platforms
mkdir -p src/ad_leak_engine/fix_forge/templates/{shopify,woocommerce,bigcommerce,custom}
touch src/ad_leak_engine/fix_forge/__init__.py
touch src/ad_leak_engine/fix_forge/platforms/__init__.py

# ---------- 3. codegen.py — Template Rendering Engine ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/codegen.py
"""Template rendering engine for Fix Forge [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

TEMPLATE_DIR = Path(__file__).parent / "templates"


class CodeGenerator:
    """Renders Jinja2 templates into executable code blocks."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,  # Code output, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    def render(self, platform: str, template_name: str, context: dict | None = None) -> str:
        """Render a platform template with the given context."""
        context = context or {}
        template_path = f"{platform}/{template_name}"
        try:
            template = self.env.get_template(template_path)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_path}")
        return template.render(**context)

    def template_exists(self, platform: str, template_name: str) -> bool:
        """Check whether a template exists."""
        try:
            self.env.get_template(f"{platform}/{template_name}")
            return True
        except TemplateNotFound:
            return False
EOF

# ---------- 4. markdown.py — Guide Generation ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/markdown.py
"""Step-by-step guide generation for Fix Forge [SEED: 2399]."""
from .codegen import CodeGenerator


class MarkdownGenerator:
    """Generates human-readable implementation guides."""

    def __init__(self):
        self.codegen = CodeGenerator()

    def generate(self, platform: str, context: dict) -> str:
        """Render the platform-specific guide template."""
        return self.codegen.render(platform, "guide.md.j2", context)
EOF

# ---------- 5. forge.py — Orchestrator / Router ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/forge.py
"""Fix Forge orchestrator [SEED: 2399]. Routes leaks to platform generators."""
from ..shared.schemas import Leak, Fix
from ..shared.exceptions import PlatformAmbiguousError
from .platforms.shopify import ShopifyFixGenerator
from .platforms.woocommerce import WooCommerceFixGenerator
from .platforms.bigcommerce import BigCommerceFixGenerator
from .platforms.custom import CustomFixGenerator


class FixForge:
    """Selects the appropriate platform generator and produces fixes."""

    def __init__(self):
        self.generators = {
            "shopify": ShopifyFixGenerator(),
            "woocommerce": WooCommerceFixGenerator(),
            "bigcommerce": BigCommerceFixGenerator(),
            "custom": CustomFixGenerator(),
        }

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        """Generate a fix for the given leak and platform."""
        if confidence < 0.5:
            raise PlatformAmbiguousError(
                f"Platform confidence {confidence} too low for deterministic codegen"
            )
        generator = self.generators.get(platform, self.generators["custom"])
        return generator.generate(leak, platform, confidence)
EOF

# ---------- 6. Shopify Generator ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/platforms/shopify.py
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
EOF

# ---------- 7. WooCommerce Generator ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/platforms/woocommerce.py
"""WooCommerce fix generator [SEED: 2399]. functions.php CAPI + plugin guides."""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class WooCommerceFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["woocommerce"]

    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        if leak.signal == "pixel_not_firing":
            return self._fix_plugin(leak, confidence)
        return self._fix_capi(leak, confidence)

    def _fix_plugin(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[],
            verification_steps=[
                "Install a Meta Pixel plugin (Conversios or Pixel Manager)",
                "Connect your Meta account and Pixel ID",
                "Verify the pixel fires using Meta Pixel Helper",
            ],
            rollback_steps=[
                "Deactivate and delete the Meta Pixel plugin",
            ],
            expected_outcome="Meta Pixel fires on all WooCommerce pages via plugin.",
            confidence=confidence,
        )

    def _fix_capi(self, leak: Leak, confidence: float) -> Fix:
        code = self.codegen.render("woocommerce", "functions_snippet.php.j2")
        guide = self.markdown.generate("woocommerce", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "WooCommerce",
        })
        return Fix(
            leak_id=leak.id,
            platform="woocommerce",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "php",
                "filename": "functions.php",
                "location": "Child theme functions.php (bottom of file)",
                "code": code,
            }],
            verification_steps=[
                "Add the snippet to your child theme's functions.php",
                "Replace YOUR_PIXEL_ID_HERE and YOUR_ACCESS_TOKEN_HERE",
                "Place a test order",
                "Check Meta Events Manager for a server-side Purchase event with event_id",
            ],
            rollback_steps=[
                "Remove the added snippet from functions.php",
                "Clear any caching plugins",
            ],
            expected_outcome="Server-side Purchase events fire with hashed PII and deduplicated event_ids.",
            confidence=confidence,
        )
EOF

# ---------- 8. BigCommerce Generator ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/platforms/bigcommerce.py
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
EOF

# ---------- 9. Custom / GTM Generator ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/platforms/custom.py
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
EOF

# ---------- 10. Template: Shopify Pixel ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/shopify/pixel_base.liquid.j2
{%- raw -%}
{% comment %}
  Meta Pixel Base Code - Ad-Leak-Engine [SEED: 2399]
  Location: theme.liquid <head>
  Replace YOUR_PIXEL_ID_HERE with your Meta Pixel ID
{% endcomment %}
<script>
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', 'YOUR_PIXEL_ID_HERE');
  fbq('track', 'PageView');
</script>
<noscript>
  <img height="1" width="1" style="display:none"
       src="https://www.facebook.com/tr?id=YOUR_PIXEL_ID_HERE&ev=PageView&noscript=1"/>
</noscript>
{%- endraw -%}
EOF

# ---------- 11. Template: Shopify Customer Events ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/shopify/customer_events.js.j2
{%- raw -%}
// Meta Pixel Customer Events - Ad-Leak-Engine [SEED: 2399]
// Location: Shopify Admin > Settings > Customer Events > Add custom pixel
analytics.subscribe("page_viewed", (event) => {
  fbq('track', 'PageView', {event_id: event.id});
});

analytics.subscribe("product_viewed", (event) => {
  fbq('track', 'ViewContent', {
    content_ids: [event.data.productVariant.id],
    content_type: 'product',
    value: event.data.productVariant.price.amount,
    currency: event.data.productVariant.price.currencyCode,
    event_id: event.id
  });
});

analytics.subscribe("product_added_to_cart", (event) => {
  fbq('track', 'AddToCart', {
    content_ids: [event.data.productVariant.id],
    content_type: 'product',
    value: event.data.productVariant.price.amount,
    currency: event.data.productVariant.price.currencyCode,
    event_id: event.id
  });
});

analytics.subscribe("checkout_started", (event) => {
  fbq('track', 'InitiateCheckout', {
    value: event.data.checkout.totalPrice.amount,
    currency: event.data.checkout.totalPrice.currencyCode,
    event_id: event.id
  });
});

analytics.subscribe("payment_info_submitted", (event) => {
  fbq('track', 'AddPaymentInfo', {
    value: event.data.checkout.totalPrice.amount,
    currency: event.data.checkout.totalPrice.currencyCode,
    event_id: event.id
  });
});

analytics.subscribe("checkout_completed", (event) => {
  fbq('track', 'Purchase', {
    value: event.data.checkout.totalPrice.amount,
    currency: event.data.checkout.totalPrice.currencyCode,
    content_ids: event.data.checkout.lineItems.map(item => item.id),
    num_items: event.data.checkout.lineItems.length,
    event_id: event.id
  });
});
{%- endraw -%}
EOF

# ---------- 12. Template: Shopify Guide ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/shopify/guide.md.j2
# {{ platform }} Fix Guide — Ad-Leak-Engine [SEED: 2399]

## Detected Leak
- **Signal:** `{{ leak_signal }}`
- **Recommendation:** {{ recommendation }}

## What This Fix Does
This fix restores your Meta tracking infrastructure so Meta's algorithm
receives accurate conversion data. Without it, your ad spend optimizes
against incomplete signals, inflating CPA and suppressing ROAS.

## Implementation
Follow the code block provided alongside this guide. The exact location
to paste the code is specified in the code block metadata.

## After Applying
Allow 24-48 hours for Meta to re-optimize with the restored data stream.
Monitor Meta Events Manager for incoming events.
EOF

# ---------- 13. Template: WooCommerce PHP ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/woocommerce/functions_snippet.php.j2
<?php
/**
 * Meta CAPI Purchase Event - Ad-Leak-Engine [SEED: 2399]
 * Location: functions.php (use a child theme to survive updates)
 * Hook: woocommerce_thankyou
 * Replace: YOUR_PIXEL_ID_HERE, YOUR_ACCESS_TOKEN_HERE
 */
add_action('woocommerce_thankyou', function($order_id) {
    $order = wc_get_order($order_id);
    if (!$order) {
        return;
    }

    $pixel_id     = 'YOUR_PIXEL_ID_HERE';
    $access_token = 'YOUR_ACCESS_TOKEN_HERE';
    $event_id     = 'order_' . $order_id; // Shared dedup key with browser pixel

    // SHA-256 hash PII for Event Match Quality (never send raw PII)
    $hashed_email = hash('sha256', strtolower(trim($order->get_billing_email())));
    $hashed_phone = hash('sha256', preg_replace('/[^0-9]/', '', $order->get_billing_phone()));

    $payload = array(
        'data' => array(
            array(
                'event_name'       => 'Purchase',
                'event_time'       => time(),
                'event_id'         => $event_id,
                'action_source'    => 'website',
                'event_source_url' => home_url('/checkout/order-received/' . $order_id),
                'user_data'        => array(
                    'em' => array($hashed_email),
                    'ph' => array($hashed_phone),
                ),
                'custom_data'      => array(
                    'currency' => $order->get_currency(),
                    'value'    => (float) $order->get_total(),
                ),
            ),
        ),
    );

    wp_remote_post(
        'https://graph.facebook.com/v18.0/' . $pixel_id . '/events?access_token=' . $access_token,
        array(
            'method'  => 'POST',
            'headers' => array('Content-Type' => 'application/json'),
            'body'    => wp_json_encode($payload),
            'timeout' => 5,
        )
    );
});
EOF

# ---------- 14. Template: WooCommerce Guide ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/woocommerce/guide.md.j2
# {{ platform }} Fix Guide — Ad-Leak-Engine [SEED: 2399]

## Detected Leak
- **Signal:** `{{ leak_signal }}`
- **Recommendation:** {{ recommendation }}

## What This Fix Does
This fix restores accurate conversion tracking for your WooCommerce store.
Without it, Meta cannot optimize for purchases, and your ad spend leaks.

## Implementation
Follow the code block provided alongside this guide. Always use a child
theme so your changes survive theme updates.

## After Applying
Place a test order and confirm the server-side event appears in Meta
Events Manager within a few minutes.
EOF

# ---------- 15. Template: BigCommerce Script Manager ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/bigcommerce/script_manager.js.j2
{%- raw -%}
// Meta Pixel via BigCommerce Script Manager - Ad-Leak-Engine [SEED: 2399]
// Location: Storefront > Script Manager > Create Script (all pages)
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', 'YOUR_PIXEL_ID_HERE');
fbq('track', 'PageView');
{%- endraw -%}
EOF

# ---------- 16. Template: BigCommerce Guide ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/bigcommerce/guide.md.j2
# {{ platform }} Fix Guide — Ad-Leak-Engine [SEED: 2399]

## Detected Leak
- **Signal:** `{{ leak_signal }}`
- **Recommendation:** {{ recommendation }}

## What This Fix Does
This fix restores Meta tracking for your BigCommerce storefront using
the native Script Manager, requiring no theme edits.

## Implementation
Use the Script Manager snippet provided. Alternatively, connect the
native Meta Pixel via Settings > Data Solutions.

## After Applying
Verify the pixel fires on all pages using the Meta Pixel Helper extension.
EOF

# ---------- 17. Template: Custom GTM Tag ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/custom/gtm_tag.html.j2
{%- raw -%}
<!-- Meta Pixel GTM Tag - Ad-Leak-Engine [SEED: 2399] -->
<!-- Location: Google Tag Manager > Tags > New > Custom HTML -->
<script>
  !function(f,b,e,v,n,t,s)
  {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
  n.callMethod.apply(n,arguments):n.queue.push(arguments)};
  if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
  n.queue=[];t=b.createElement(e);t.async=!0;
  t.src=v;s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s)}(window, document,'script',
  'https://connect.facebook.net/en_US/fbevents.js');
  fbq('init', 'YOUR_PIXEL_ID_HERE');
  fbq('track', 'PageView');
</script>
{%- endraw -%}
EOF

# ---------- 18. Template: Custom Server Webhook ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/custom/server_webhook.py.j2
"""
Meta CAPI Server-Side Webhook - Ad-Leak-Engine [SEED: 2399]
Endpoint: POST /orders/create
Replace: YOUR_PIXEL_ID_HERE, YOUR_ACCESS_TOKEN_HERE
"""
import hashlib
import time

import requests
from fastapi import FastAPI, Request

app = FastAPI()

PIXEL_ID = "YOUR_PIXEL_ID_HERE"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN_HERE"


def sha256_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


@app.post("/orders/create")
async def order_created(request: Request):
    order = await request.json()
    event_id = f"order_{order.get('id')}"

    payload = {
        "data": [{
            "event_name": "Purchase",
            "event_time": int(time.time()),
            "event_id": event_id,
            "action_source": "website",
            "user_data": {
                "em": [sha256_hash(order.get("email", ""))],
                "ph": [sha256_hash(order.get("phone", ""))],
            },
            "custom_data": {
                "currency": order.get("currency", "USD"),
                "value": order.get("total", 0),
            },
        }]
    }

    url = f"https://graph.facebook.com/v18.0/{PIXEL_ID}/events"
    resp = requests.post(url, json=payload, params={"access_token": ACCESS_TOKEN})
    return {"status": resp.status_code}
EOF

# ---------- 19. Template: Custom Guide ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/templates/custom/guide.md.j2
# {{ platform }} Fix Guide — Ad-Leak-Engine [SEED: 2399]

## Detected Leak
- **Signal:** `{{ leak_signal }}`
- **Recommendation:** {{ recommendation }}

## What This Fix Does
This fix restores Meta tracking on a custom-built site using either
Google Tag Manager (browser) or a server-side webhook (CAPI).

## Implementation
For browser tracking, use the GTM tag. For server-side reliability,
deploy the CAPI webhook to your backend.

## After Applying
Verify events appear in Meta Events Manager for both browser and
server sources with matching event_ids.
EOF

# ---------- 20. Tests: Fix Forge ----------
cat << 'EOF' > tests/unit/test_fix_forge.py
"""Unit tests for Phase 5: Fix Forge code generation."""
import pytest
from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.shared.schemas import Leak
from ad_leak_engine.shared.exceptions import PlatformAmbiguousError


@pytest.fixture
def forge():
    return FixForge()


@pytest.fixture
def pixel_leak():
    return Leak(
        page_id="p1", tier="L2", signal="pixel_not_firing",
        severity=0.95, recommendation="Install Meta Pixel base code",
    )


def test_shopify_pixel_fix_generates_valid_liquid(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "shopify", 0.95)
    assert fix.platform == "shopify"
    assert len(fix.code_blocks) == 1
    code = fix.code_blocks[0]["code"]
    assert "fbq('init'" in code
    assert "YOUR_PIXEL_ID_HERE" in code
    assert fix.code_blocks[0]["filename"] == "theme.liquid"
    assert fix.markdown_guide
    assert len(fix.verification_steps) > 0
    assert len(fix.rollback_steps) > 0


def test_shopify_capi_fix_generates_customer_events(forge):
    leak = Leak(page_id="p1", tier="L2", signal="missing_purchase_event",
                severity=0.9, recommendation="Add Purchase event")
    fix = forge.generate(leak, "shopify", 0.95)
    code = fix.code_blocks[0]["code"]
    assert "analytics.subscribe" in code
    assert "checkout_completed" in code


def test_woocommerce_capi_fix_generates_valid_php(forge):
    leak = Leak(page_id="p2", tier="L2", signal="unhashed_pii",
                severity=0.8, recommendation="Hash PII with SHA-256")
    fix = forge.generate(leak, "woocommerce", 0.92)
    assert fix.platform == "woocommerce"
    code = fix.code_blocks[0]["code"]
    assert "woocommerce_thankyou" in code
    assert "hash('sha256'" in code
    assert fix.markdown_guide


def test_bigcommerce_fix_generates_script_manager(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "bigcommerce", 0.90)
    assert fix.platform == "bigcommerce"
    code = fix.code_blocks[0]["code"]
    assert "fbq('init'" in code


def test_custom_gtm_fix(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "custom", 0.6)
    assert fix.platform == "custom"
    code = fix.code_blocks[0]["code"]
    assert "Google Tag Manager" in code


def test_custom_server_side_fix(forge):
    leak = Leak(page_id="p4", tier="L2", signal="unhashed_pii",
                severity=0.8, recommendation="Hash PII")
    fix = forge.generate(leak, "custom", 0.6)
    code = fix.code_blocks[0]["code"]
    assert "sha256_hash" in code
    assert "/orders/create" in code


def test_low_confidence_raises_ambiguous(forge, pixel_leak):
    with pytest.raises(PlatformAmbiguousError):
        forge.generate(pixel_leak, "shopify", 0.3)


def test_fix_schema_completeness(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "shopify", 0.95)
    assert fix.leak_id == pixel_leak.id
    assert fix.expected_outcome
    assert 0.0 <= fix.confidence <= 1.0
    assert 0.0 <= fix.platform_confidence <= 1.0


def test_unknown_platform_falls_back_to_custom(forge, pixel_leak):
    fix = forge.generate(pixel_leak, "unknown_platform", 0.6)
    assert fix.platform == "custom"
EOF

# ---------- 21. Execute Tests ----------
echo "[SEED:2399] Running Phase 5 test suite..."
python -m pytest tests/unit/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 5 COMPLETE"
echo "  Fix Forge Built. Revenue Recovery Code Verified."
echo "=========================================================="