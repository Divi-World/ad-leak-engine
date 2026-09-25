"""Fix Effectiveness Tracking [SEED: 2399].
Compares before/after leak scores to adjust Fix Forge confidence.
"""
import json
from pathlib import Path

WEIGHTS_FILE = Path("data/scoring_weights.json")

def track_fix_effectiveness(page_id: str, before_score: float, after_score: float, fix_template_id: str):
    """
    If fix resolved leak (score dropped significantly), increase template confidence.
    """
    improvement = before_score - after_score
    if improvement > 0.3: # Significant resolution
        print(f"[EFFECTIVENESS] Fix {fix_template_id} for {page_id} resolved leaks. Boosting confidence.")
        # In a real system, this would update the DB and retrain the template weights
        return {"status": "boosted", "template": fix_template_id, "delta": 0.1}
    elif improvement < 0: # Fix made it worse or new leaks appeared
        print(f"[EFFECTIVENESS] Fix {fix_template_id} for {page_id} failed. Flagging for review.")
        return {"status": "flagged", "template": fix_template_id}
    return {"status": "neutral", "template": fix_template_id}
