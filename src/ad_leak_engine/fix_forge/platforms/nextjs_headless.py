"""Next.js / Vercel Headless Fix Generator [SEED: 2399].
Generates SSR-safe React components for Meta Pixel initialization.
Targets _app.tsx or layout.tsx patterns common in Next.js apps.
"""
from ...shared.schemas import Leak, Fix
from ...shared.interfaces import AbstractFixGenerator
from ..codegen import CodeGenerator
from ..markdown import MarkdownGenerator


class NextJsHeadlessFixGenerator(AbstractFixGenerator):
    def __init__(self):
        self.codegen = CodeGenerator()
        self.markdown = MarkdownGenerator()

    def supported_platforms(self) -> list[str]:
        return ["nextjs", "vercel"]

    def generate(self, leak: Leak, platform: str, confidence: float, vertical: str | None = None) -> Fix:
        """Generate specific code fixes for Next.js environments."""
        
        # Route L1/L3 to standard strategies if needed, but primarily focus on L2 Tracking
        if leak.tier == "L1":
             # For Next.js, L1 is usually creative. Use generic strategy for now 
             # as specialized Next.js creative advice is less common than tracking.
             return self._fix_generic_strategy(leak, confidence)
             
        elif leak.tier == "L3":
             return self._fix_site_performance(leak, confidence)

        # L2: Tracking Infrastructure Fixes
        pixel_id = leak.evidence.get("detected_pixel_id") or "YOUR_PIXEL_ID_HERE"
        
        if leak.signal in ["pixel_not_firing", "client_side_only_risk", "no_tracking_infrastructure"]:
            return self._fix_pixel_component(leak, pixel_id, confidence)
            
        elif leak.signal in ["missing_purchase_event", "retargeting_event_depth_gap"]:
            return self._fix_checkout_hook(leak, pixel_id, confidence)
            
        else:
            return self._fix_generic_strategy(leak, confidence)

    def _fix_pixel_component(self, leak: Leak, pixel_id: str, confidence: float) -> Fix:
        """Injects the SSR-Safe MetaPixel Component."""
        
        # STRATEGY: Build raw TSX string WITHOUT f-string interpolation for JSX parts.
        # Inject Pixel ID via simple replace at the end to avoid brace hell.
        
        tsx_template = '''// components/MetaPixel.tsx
"use client"; // Required for Next.js App Router

import Script from 'next/script';
import { useEffect } from 'react';

const PIXEL_ID = '__PIXEL_ID_PLACEHOLDER__'; // Auto-injected by Ad-Leak-Engine

export default function MetaPixel() {
  useEffect(() => {
    // Initialize fbq object if not present
    if (!window.fbq) {
      window.fbq = function () {
        window.fbq.callMethod ?
          window.fbq.callMethod.apply(window.fbq, arguments) :
          window.fbq.queue.push(arguments);
      };
      window.fbq.push = window.fbq;
      window.fbq.loaded = true;
      window.fbq.version = '2.0';
      window.fbq.queue = [];

      // Fire PageView immediately after init
      window.fbq('init', PIXEL_ID);
      window.fbq('track', 'PageView');
    }
  }, []);

  return (
    <>
      {/* Load Facebook SDK */}
      <Script id="fb-sdk" strategy="afterInteractive">
        {`!function(f,b,e,v,n,t,s)
        {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
        n.callMethod.apply(n,arguments):n.queue.push(arguments)};
        if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
        n.queue=[];t=b.createElement(e);t.async=!0;
        t.src=v;s=b.getElementsByTagName(e)[0];
        s.parentNode.insertBefore(t,s)}(window, document,'script',
        'https://connect.facebook.net/en_US/fbevents.js');`}
      </Script>

      {/* Noscript fallback for crawlers/blocked JS */}
      <noscript>
        <img height="1" width="1" style={{display:'none'}} alt=""
             src={`https://www.facebook.com/tr?id=${PIXEL_ID}&ev=PageView&noscript=1`} />
      </noscript>
    </>
  );
}'''

        # Safe Injection
        final_code = tsx_template.replace('__PIXEL_ID_PLACEHOLDER__', pixel_id)

        guide = self.markdown.generate("nextjs", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Next.js",
        })
        
        return Fix(
            leak_id=leak.id,
            platform="nextjs",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "typescript",
                "filename": "components/MetaPixel.tsx",
                "location": "Create this file in your project root/components",
                "code": final_code,
            }],
            verification_steps=[
                "Create `components/MetaPixel.tsx` with the code above.",
                "Import `<MetaPixel />` into your root layout (`app/layout.tsx`) or `_app.tsx`.",
                "Ensure `use client` directive is present at the top of the component.",
                "Visit your site with Meta Pixel Helper to verify firing."
            ],
            rollback_steps=[
                "Remove `<MetaPixel />` import from layout.",
                "Delete `components/MetaPixel.tsx`."
            ],
            expected_outcome=f"SSR-Safe Meta Pixel ({pixel_id}) initialized correctly without hydration errors.",
            confidence=confidence,
        )

    def _fix_checkout_hook(self, leak: Leak, pixel_id: str, confidence: float) -> Fix:
        """Provides guidance for hooking Purchase events in Next.js Checkout flows."""
        
        tsx_template = '''// Example: Hook into Order Confirmation Page
// app/checkout/success/page.tsx (or similar)
"use client";
import { useEffect } from 'react';

export default function OrderSuccess({ orderId, amount, currency }) {
  useEffect(() => {
    if (window.fbq) {
      window.fbq('track', 'Purchase', {
        value: amount,
        currency: currency,
        content_ids: [orderId], 
        content_type: 'product'
      });
    }
  }, [amount, currency, orderId]);

  return <div>Order Confirmed!</div>;
}'''

        # No pixel ID injection needed here as it relies on global fbq from MetaPixel component
        final_code = tsx_template 

        guide = self.markdown.generate("nextjs", {
            "leak_signal": leak.signal,
            "recommendation": "Trigger Purchase event on order confirmation.",
            "platform": "Next.js",
        })

        return Fix(
            leak_id=leak.id,
            platform="nextjs",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[{
                "language": "typescript",
                "filename": "app/checkout/success/page.tsx",
                "location": "Your Order Confirmation Component/Page",
                "code": final_code,
            }],
            verification_steps=[
                "Identify your post-purchase redirect page/component.",
                "Add the `useEffect` hook shown above.",
                "Pass real order data (ID, Amount, Currency) as props.",
                "Place a test order and check Events Manager."
            ],
            rollback_steps=[
                "Remove the useEffect hook from the success page."
            ],
            expected_outcome="Purchase events fire reliably on server-rendered or client-side checkout completion.",
            confidence=confidence,
        )

    def _fix_generic_strategy(self, leak: Leak, confidence: float) -> Fix:
        guide = self.markdown.generate("nextjs", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Next.js",
            "tier": "L1",
        })
        return Fix(
            leak_id=leak.id,
            platform="nextjs",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=[],
            verification_steps=[
                "Review current ad creatives in Meta Ads Manager",
                "Implement the strategic recommendation outlined in this guide",
                "Monitor CTR, CPM, and CPA for 7-14 days",
            ],
            rollback_steps=[
                "Revert to previous ad creative or campaign structure in Meta Ads Manager",
            ],
            expected_outcome="Improved ad relevance and conversion rate.",
            confidence=confidence,
        )
    
    def _fix_site_performance(self, leak: Leak, confidence: float) -> Fix:
        # Reuse logic from Custom/Shopify for viewport/tap targets as they are universal CSS/HTML
        code_blocks = []
        if leak.signal == "no_mobile_viewport":
            code = self.codegen.render("custom", "viewport_fix.html.j2") # Reusing custom template
            code_blocks.append({
                "language": "html",
                "filename": "layout.tsx",
                "location": "Root Layout (<head>)",
                "code": code,
            })
        elif leak.signal == "small_tap_targets":
            code = self.codegen.render("custom", "tap_targets.css.j2")
            code_blocks.append({
                "language": "css",
                "filename": "globals.css",
                "location": "Global Stylesheet",
                "code": code,
            })
            
        guide = self.markdown.generate("nextjs", {
            "leak_signal": leak.signal,
            "recommendation": leak.recommendation,
            "platform": "Next.js",
            "tier": "L3",
        })
        return Fix(
            leak_id=leak.id,
            platform="nextjs",
            platform_confidence=confidence,
            markdown_guide=guide,
            code_blocks=code_blocks,
            verification_steps=[
                "Apply the fix to your Next.js layout/styles",
                "Test on mobile devices",
                "Run Lighthouse CI"
            ],
            rollback_steps=["Revert changes"],
            expected_outcome="Improved mobile UX and Core Web Vitals.",
            confidence=confidence,
        )