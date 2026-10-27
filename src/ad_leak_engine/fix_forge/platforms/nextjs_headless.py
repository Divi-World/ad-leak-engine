"""Next.js / Vercel Headless Fix Generator [SEED: 2399].

Generates SSR-safe React components for Meta Pixel initialization.
Targets _app.tsx or layout.tsx patterns common in Next.js apps.
"""
import logging
from ...shared.schemas import Leak, Fix

logger = logging.getLogger(__name__)


class NextJsHeadlessFixGenerator:
    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        """Generate specific code fixes for Next.js environments."""
        
        # Base structure for all leaks
        title = f"Next.js Pixel Initialization Fix ({leak.severity})"
        description = (
            "Your Next.js application is missing proper Meta Pixel initialization. "
            "Because Next.js uses Server-Side Rendering (SSR), standard <script> tags "
            "may not fire correctly or may cause hydration mismatches. "
            "Use the following React component approach to ensure reliable tracking."
        )
        
        code_snippet = ""
        instructions = ""
        
        if leak.leak_type == "pixel_not_firing":
            title = "Critical: Implement SSR-Safe Meta Pixel Component"
            description += "\n\nRecommended Action: Create a dedicated `<MetaPixel />` component."
            
            code_snippet = '''// components/MetaPixel.tsx
"use client"; // Required for Next.js App Router

import Script from 'next/script';
import { useEffect } from 'react';

const PIXEL_ID = 'YOUR_PIXEL_ID_HERE'; // Replace with actual ID

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
            instructions = "1. Create `components/MetaPixel.tsx`.\n2. Import and add `<MetaPixel />` to your root layout (`app/layout.tsx`) or `_app.tsx`.\n3. Ensure `use client` directive is present at the top."

        elif leak.leak_type == "missing_purchase_event":
            title = "High: Hook Purchase Events into Checkout Flow"
            description += "\n\nRecommended Action: Trigger `fbq('track', 'Purchase')` upon successful order confirmation."
            
            code_snippet = '''// In your checkout success page/component
import { useEffect } from 'react';

export default function OrderConfirmation({ orderId, amount, currency }) {
  useEffect(() => {
    if (window.fbq) {
      window.fbq('track', 'Purchase', {
        value: amount,
        currency: currency,
        content_ids: [orderId], // Optional: Product IDs
        content_type: 'product'
      });
    }
  }, [amount, currency, orderId]);

  return <div>Order Confirmed!</div>;
}'''
            instructions = "Pass order details from your backend/API to this frontend component and trigger the event in `useEffect`."

        else:
            # Generic fallback for other leak types
            title = f"General Next.js Tracking Improvement ({leak.severity})"
            code_snippet = "// Refer to official Meta docs for Next.js integration best practices."
            instructions = "Ensure all tracking scripts are wrapped in Client Components ('use client')."

        return Fix(
            id=leak.id,
            platform=platform,
            title=title,
            description=description,
            code_snippet=code_snippet,
            implementation_instructions=instructions,
            estimated_recovery_usd=leak.estimated_loss_usd * 0.8 # Assume 80% recovery potential
        )
