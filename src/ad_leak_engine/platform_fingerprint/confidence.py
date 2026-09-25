"""Confidence scoring for platform fingerprint detection."""
from .signatures import CUSTOM_CONFIDENCE


def calculate_confidence(primary_hits: int, secondary_hits: int) -> float:
    """Calculate detection confidence based on marker hits.

    Rules:
    - 3+ primary markers: 0.95 (near-certain)
    - 2 primary markers: 0.90 + 0.02 per secondary hit
    - 1 primary marker: 0.60 + 0.10 per secondary hit
    - Only secondary markers: 0.40
    - No markers: 0.30 (custom fallback)
    """
    if primary_hits == 0 and secondary_hits == 0:
        return CUSTOM_CONFIDENCE

    if primary_hits >= 3:
        return 0.95
    elif primary_hits == 2:
        return min(0.94, 0.90 + secondary_hits * 0.02)
    elif primary_hits == 1:
        return min(0.70, 0.60 + secondary_hits * 0.10)
    else:
        # Only secondary hits
        return 0.40
