"""Reply analysis and weight adjustment [SEED: 2399]."""
from .weights import load_weights, save_weights

# Keywords that indicate which tier the prospect cares about
TIER_KEYWORDS = {
    "L2": ["pixel", "tracking", "capi", "conversion", "event", "server-side"],
    "L1": ["creative", "ad", "video", "fatigue", "copy", "variant", "testing"],
    "L3": ["speed", "slow", "checkout", "mobile", "lcp", "load", "friction"]
}

def process_reply(page_id: str, reply_text: str, positive: bool = True):
    """Analyzes reply text and boosts relevant signal weights."""
    if not positive:
        return 
        
    weights = load_weights()
    text = reply_text.lower()
    updated = False
    
    for tier, keywords in TIER_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            # Boost all signals in this tier slightly (max cap 2.0)
            for signal in weights.get(tier, {}):
                old_val = weights[tier][signal]
                weights[tier][signal] = min(2.0, old_val + 0.1)
                updated = True
                
    if updated:
        save_weights(weights)
        print(f"[FEEDBACK] Weights updated based on positive reply from {page_id}.")
        print(f"[FEEDBACK] The system will now prioritize these leak types in future scans.")
    else:
        print(f"[FEEDBACK] Reply logged for {page_id}, but no specific tier keywords detected.")
