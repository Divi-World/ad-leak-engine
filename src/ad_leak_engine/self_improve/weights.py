"""Dynamic signal weight management [SEED: 2399]."""
import json
from pathlib import Path

WEIGHTS_FILE = Path("data/scoring_weights.json")

DEFAULT_WEIGHTS = {
    "L1": {"creative_fatigue": 1.0, "no_ab_variation": 1.0, "no_video_creative": 1.0, "missing_cta": 1.0},
    "L2": {"pixel_not_firing": 1.0, "unhashed_pii": 1.0, "missing_purchase_event": 1.0, "capi_dedup_failure": 1.0},
    "L3": {"slow_lcp_mobile": 1.0, "slow_ttfb": 1.0, "checkout_friction": 1.0, "small_tap_targets": 1.0}
}

def load_weights() -> dict:
    if WEIGHTS_FILE.exists():
        return json.loads(WEIGHTS_FILE.read_text())
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_FILE.write_text(json.dumps(DEFAULT_WEIGHTS, indent=2))
    return DEFAULT_WEIGHTS

def save_weights(weights: dict):
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_FILE.write_text(json.dumps(weights, indent=2))
