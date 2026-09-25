"""Scoring and weighting logic for leak prioritization."""
from ..shared.schemas import Leak

def calculate_priority_score(leak: Leak, weight: float = 1.0) -> float:
    """Calculates final priority score (0.0 to 1.0)."""
    return min(1.0, leak.severity * leak.confidence * weight)
