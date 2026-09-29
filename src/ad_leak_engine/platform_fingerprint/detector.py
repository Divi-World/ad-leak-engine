"""Multi-signal platform detector for Ad-Leak-Engine [SEED: 2399]."""
from ..shared.interfaces import AbstractPlatformDetector
from .signatures import PLATFORM_SIGNATURES, CUSTOM_PLATFORM, CUSTOM_CONFIDENCE
from .confidence import calculate_confidence


class PlatformDetector(AbstractPlatformDetector):
    """Detects e-commerce platform from HTML content and HTTP headers."""

    def detect(self, url: str, html: str | None = None, headers: dict | None = None) -> tuple[str, float]:
        """Return (platform_name, confidence_score).

        Scans HTML content and HTTP headers for platform-specific
        markers. Returns the platform with the highest confidence.
        Falls back to 'custom' if no markers match.
        """
        html = html or ""
        headers = headers or {}

        best_platform = CUSTOM_PLATFORM
        best_confidence = CUSTOM_CONFIDENCE
        best_evidence = []

        for platform, sigs in PLATFORM_SIGNATURES.items():
            primary_hits = self._count_primary_hits(sigs["primary"], html, headers)
            secondary_hits = self._count_secondary_hits(sigs["secondary"], html, headers)
            # [SEED: 2399] Track which markers actually matched for auditability
            matched_markers = self._collect_matched_markers(sigs["primary"] + sigs["secondary"], html, headers)

            confidence = calculate_confidence(primary_hits, secondary_hits)

            if confidence > best_confidence:
                best_confidence = confidence
                best_platform = platform
                best_evidence = matched_markers

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
