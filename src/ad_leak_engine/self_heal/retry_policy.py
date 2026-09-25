"""Backoff strategies [SEED: 2399]."""
import random
def get_backoff(error_type: str, attempt: int) -> float:
    if error_type == "RateLimitError":
        return (30 * (2 ** attempt)) + random.uniform(0, 5)
    elif error_type == "BlockedError":
        return (60 * (attempt + 1)) + random.uniform(0, 10)
    return 10.0
