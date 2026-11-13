"""Multi-signal platform detector for Ad-Leak-Engine [SEED: 2399]."""
from ..shared.interfaces import AbstractPlatformDetector
from .signatures import PLATFORM_SIGNATURES, CUSTOM_PLATFORM, CUSTOM_CONFIDENCE
from .confidence import calculate_confidence


class PlatformDetector(AbstractPlatformDetector):
    """Detects e-commerce platform from HTML content and HTTP headers."""

    def detect(self, url: str, html: str | None = None, headers: dict | None = None) -> tuple[str, float, list]:
        """Return (platform_name, confidence_score, evidence_list)."""
        html = html or ""
        headers = headers or {}

        best_platform = CUSTOM_PLATFORM
        best_confidence = CUSTOM_CONFIDENCE
        best_evidence = []

        # --- PHASE 1: Signature Matching ---
        for platform, sigs in PLATFORM_SIGNATURES.items():
            primary_hits = self._count_primary_hits(sigs["primary"], html, headers)
            secondary_hits = self._count_secondary_hits(sigs["secondary"], html, headers)
            matched_markers = self._collect_matched_markers(sigs["primary"] + sigs["secondary"], html, headers)

            confidence = calculate_confidence(primary_hits, secondary_hits)

            if confidence > best_confidence:
                best_confidence = confidence
                best_platform = platform
                best_evidence = matched_markers

        # --- PHASE 2: AGGRESSIVE FRAMEWORK DETECTION ---
        if html:
            lower_html = html.lower()
            
            # Next.js / Vercel
            if "__next_data__" in lower_html or "_next/static" in lower_html or "buildId" in lower_html:
                return ("nextjs", 0.98, ["Next.js Build Artifacts Found"]) 
            
            # Nuxt.js
            if "__NUXT_DATA__" in lower_html or "/_nuxt/" in lower_html:
                return ("nuxt", 0.95, ["Nuxt.js Hydration Data Found"])
                
            # Gatsby
            if "___gatsby" in lower_html or "/page-data/" in lower_html:
                return ("gatsby", 0.90, ["Gatsby Page Data Found"])

            # Shopify (Double Check for Minified Themes)
            if "cdn.shopify.com" in lower_html and "Shopify.theme" in lower_html:
                 # Override low confidence if strong signals exist
                 if best_platform != "shopify" or best_confidence < 0.9:
                     return ("shopify", 0.96, ["CDN Shop Theme Assets"])

        # Final Return: Always 3 items
        return (best_platform, best_confidence, best_evidence)

    def _collect_matched_markers(self, markers: list[str], html: str, headers: dict) -> list[str]:
        """Return list of markers that actually matched (for evidence/audit)."""
        matched = []
        for marker in markers:
            if marker.lower() in html.lower():
                matched.append(marker)
                continue
            for header_key, header_value in headers.items():
                if marker.lower() in header_key.lower() or marker.lower() in str(header_value).lower():
                    matched.append(f"{header_key}: {marker}")
                    break
        return matched

    def _count_primary_hits(self, markers: list[str], html: str, headers: dict) -> int:
        """Count primary marker hits in HTML and headers."""
        hits = 0
        for marker in markers:
            if marker.lower() in html.lower():
                hits += 1
            # Check headers (e.g., X-ShopId)
            for header_key, header_value in headers.items():
                if marker.lower() in header_key.lower() or marker.lower() in str(header_value).lower():
                    hits += 1
                    break  # Count each marker only once
        return hits

    def _count_secondary_hits(self, markers: list[str], html: str, headers: dict) -> int:
        """Count secondary marker hits in HTML and headers."""
        hits = 0
        for marker in markers:
            if marker.lower() in html.lower():
                hits += 1
            for header_key, header_value in headers.items():
                if marker.lower() in header_key.lower() or marker.lower() in str(header_value).lower():
                    hits += 1
                    break
        return hits
