"""Niche conversion tracking [SEED: 2399]."""
import json
from pathlib import Path

NICHE_FILE = Path("data/niche_performance.json")

def log_niche_result(niche: str, replied: bool):
    if not NICHE_FILE.exists():
        NICHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        NICHE_FILE.write_text("{}")
    
    data = json.loads(NICHE_FILE.read_text())
    if niche not in data:
        data[niche] = {"sent": 0, "replied": 0}
        
    data[niche]["sent"] += 1
    if replied:
        data[niche]["replied"] += 1
        
    NICHE_FILE.write_text(json.dumps(data, indent=2))
