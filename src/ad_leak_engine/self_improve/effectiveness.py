"""Fix Effectiveness Tracking [SEED: 2399].
Compares before/after leak scores to adjust Fix Forge confidence.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
WEIGHTS_FILE = Path("data/scoring_weights.json")

def _load_weights() -> dict:
    """Safely load existing weights, or return defaults."""
    if WEIGHTS_FILE.exists():
        try:
            with open(WEIGHTS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("Corrupted weights file, resetting to defaults.")
    return {"default_confidence": 0.5, "template_multipliers": {}}

def _save_weights(weights: dict):
    """Persist weights to disk."""
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(WEIGHTS_FILE, "w") as f:
        json.dump(weights, f, indent=2)

def track_fix_effectiveness(page_id: str, before_score: float, after_score: float, fix_template_id: str):
    """
    If fix resolved leak (score dropped significantly), increase template confidence.
    """
    improvement = before_score - after_score
    weights = _load_weights()
    
    if improvement > 0.3: # Significant resolution
        logger.info(f"[EFFECTIVENESS] Fix {fix_template_id} for {page_id} resolved leaks. Boosting confidence.")
        current_mult = weights["template_multipliers"].get(fix_template_id, 1.0)
        weights["template_multipliers"][fix_template_id] = min(current_mult + 0.1, 2.0) # Cap at 2.0
        _save_weights(weights)
        return {"status": "boosted", "template": fix_template_id, "delta": 0.1}
        
    elif improvement < 0: # Fix made it worse or new leaks appeared
        logger.warning(f"[EFFECTIVENESS] Fix {fix_template_id} for {page_id} failed. Flagging for review.")
        current_mult = weights["template_multipliers"].get(fix_template_id, 1.0)
        weights["template_multipliers"][fix_template_id] = max(current_mult - 0.2, 0.1) # Floor at 0.1
        _save_weights(weights)
        return {"status": "flagged", "template": fix_template_id}
        
    return {"status": "neutral", "template": fix_template_id}
