"""Dynamic signal weight management [SEED: 2399]."""
import json
from pathlib import Path

WEIGHTS_FILE = Path("data/scoring_weights.json")

DEFAULT_WEIGHTS = {
    "L1": {"creative_fatigue": 1.0, "no_ab_variation": 1.0, "no_video_creative": 1.0, "missing_cta": 1.0},
    "L2": {"pixel_not_firing": 1.0, "unhashed_pii": 1.0, "missing_purchase_event": 1.0, "capi_dedup_failure": 1.0},
    # Real emitted L2 signals (legacy keys above retained for backward compatibility)
    "L2": {**{"pixel_not_firing": 1.0, "unhashed_pii": 1.0, "missing_purchase_event": 1.0, "capi_dedup_failure": 1.0},
           **{k: 1.0 for k in ("homepage_browser_only_observation","browser_add_to_cart_missing",
              "browser_initiate_checkout_missing","pixel_funnel_event_gap","pixel_provisioned_but_dormant",
              "capi_browser_dedup_gap","no_tracking_infrastructure","pixel_blocking_scripts",
              "tag_manager_wrapped_tracking","server_side_orphan_risk","retargeting_gap_not_observed",
              "telemetry_blind_spot","enterprise_security_wall","enterprise_bot_cloaking_detected")}},
    "L3": {"slow_lcp_mobile": 1.0, "slow_ttfb": 1.0, "checkout_friction": 1.0, "small_tap_targets": 1.0}
}

def _merge_defaults(disk: dict) -> dict:
    """Additive: defaults supply missing keys; on-disk learned values always win."""
    merged = {}
    for tier, keys in DEFAULT_WEIGHTS.items():
        base = dict(keys)
        base.update((disk.get(tier) or {}))
        merged[tier] = base
    for tier, keys in (disk or {}).items():
        if tier not in merged:
            merged[tier] = keys
    return merged


def load_weights() -> dict:
    if WEIGHTS_FILE.exists():
        try:
            disk = json.loads(WEIGHTS_FILE.read_text())
        except json.JSONDecodeError:
            disk = {}
        return _merge_defaults(disk if isinstance(disk, dict) else {})
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_FILE.write_text(json.dumps(DEFAULT_WEIGHTS, indent=2))
    return json.loads(WEIGHTS_FILE.read_text())

def save_weights(weights: dict):
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEIGHTS_FILE.write_text(json.dumps(weights, indent=2))
