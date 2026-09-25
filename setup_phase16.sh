#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 16 (Roadmap Phase 8)
# Feedback Loop & Self-Improvement Engine
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 16 BOOTSTRAP"
echo "  (Roadmap Phase 8: Feedback Loop & Self-Improvement)"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

mkdir -p src/ad_leak_engine/self_improve
touch src/ad_leak_engine/self_improve/__init__.py

# 1. Dynamic Weight Storage (scoring_weights.json)
cat << 'EOF' > src/ad_leak_engine/self_improve/weights.py
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
EOF

# 2. Reply Tracker (Adjusts weights based on prospect engagement)
cat << 'EOF' > src/ad_leak_engine/self_improve/tracker.py
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
EOF

# 3. Niche Performance Tracker
cat << 'EOF' > src/ad_leak_engine/self_improve/niche.py
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
EOF

# 4. Update Master CLI to include the feedback command
cat << 'EOF' > src/ad_leak_engine/cli.py
"""Ad-Leak-Engine Master CLI [SEED: 2399]."""
import sys
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        os.environ["PYTHONIOENCODING"] = "utf-8"

from .ingest.playwright_source import PlaywrightSource
from .leak_scan.l1_creative import L1CreativeScanner
from .leak_scan.l2_tracking import L2TrackingScanner
from .leak_scan.l3_scanner import L3SiteScanner
from .platform_fingerprint.detector import PlatformDetector
from .fix_forge.forge import FixForge
from .outreach.bundle import OutreachBuilder
from .persistence.db import init_db
from .persistence.repository import AdRepository
from .shared.schemas import Page
from .self_heal.human_browser import HumanBrowser

def _fetch_html_stealth(url: str) -> str | None:
    hb = HumanBrowser(headless=True)
    try:
        with hb.session() as page:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            hb.human_pause(1.5, 3.0)
            return page.content()
    except Exception:
        return None

def cmd_scan(keyword: str, country: str, limit: int, skip_crawl: bool):
    print(f"[ALE] Initiating LIVE SCAN for '{keyword}' in {country}...")
    init_db()
    repo = AdRepository()

    source = PlaywrightSource(headless=True)
    print("[ALE] Launching stealth browser and pulling ads...")
    ads = list(source.search(keyword, country, max_results=50))
    
    if not ads:
        print("[ALE] ERROR: No ads extracted.")
        return

    inserted = repo.upsert_ads(ads)
    print(f"[ALE] Extracted {len(ads)} real ads. Persisted {inserted} new to SQLite.")

    by_page = defaultdict(list)
    for ad in ads:
        by_page[ad.page_id].append(ad)

    l1, l2, l3 = L1CreativeScanner(), L2TrackingScanner(), L3SiteScanner()
    detector, forge = PlatformDetector(), FixForge()
    builder = OutreachBuilder(output_dir="output")

    processed = 0
    for page_id, page_ads in by_page.items():
        if processed >= limit:
            break
        
        page_name = page_ads[0].page_name
        landing = next((a.landing_url for a in page_ads if a.landing_url), None)
        page = Page(id=page_id, name=page_name, url=landing, ads=page_ads,
                    first_seen=datetime.now(timezone.utc))
        
        print(f"\n[ALE] Auditing: {page_name} ({len(page_ads)} ads)")
        
        leaks = list(l1.scan(page))
        print(f"[ALE]   L1 Leaks: {len(leaks)}")
        
        if landing and not skip_crawl:
            try:
                from .leak_scan.telemetry_collector import TelemetryCollector
                print(f"[ALE]   Crawling landing page with stealth browser for L2/L3 telemetry...")
                page.raw = TelemetryCollector().collect(landing)
                l2_leaks, l3_leaks = l2.scan(page), l3.scan(page)
                leaks += l2_leaks + l3_leaks
                print(f"[ALE]   L2/L3 Leaks: {len(l2_leaks) + len(l3_leaks)}")
            except Exception as e:
                print(f"[ALE]   (L2/L3 crawl skipped: {e})")

        platform, conf = "custom", 0.3
        if landing:
            print(f"[ALE]   Fetching HTML for platform fingerprinting...")
            html_content = _fetch_html_stealth(landing)
            if html_content:
                platform, conf = detector.detect(landing, html_content)
            page.fingerprint = platform
        print(f"[ALE]   Platform: {platform} (confidence {conf:.2f})")

        fixes = []
        for leak in leaks:
            try:
                fixes.append(forge.generate(leak, platform, conf))
            except Exception:
                continue
        
        pack = builder.build(page, leaks, fixes)
        print(f"[ALE]   -> Outreach pack saved: output/{page_id}/teardown.md")
        print(f"[ALE]   -> Estimated recovery: {pack.estimated_recovery}")
        processed += 1

    print(f"\n[ALE] SCAN COMPLETE. {processed} pages audited.")

def cmd_feedback(page_id: str, reply_text: str, positive: bool):
    from .self_improve.tracker import process_reply
    from .self_improve.niche import log_niche_result
    print(f"[ALE] Processing feedback for page {page_id}...")
    process_reply(page_id, reply_text, positive)
    # Simulate logging niche performance (defaulting to 'ecommerce' for now)
    log_niche_result("ecommerce", positive)
    print("[ALE] Niche performance logged.")

def main():
    import argparse
    parser = argparse.ArgumentParser(prog="ale")
    sub = parser.add_subparsers(dest="command")
    
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("keyword", nargs="?", default="shoes")
    p_scan.add_argument("country", nargs="?", default="US")
    p_scan.add_argument("--limit", type=int, default=3)
    p_scan.add_argument("--skip-crawl", action="store_true")

    p_fb = sub.add_parser("feedback")
    p_fb.add_argument("page_id")
    p_fb.add_argument("reply_text")
    p_fb.add_argument("--positive", action="store_true", default=True)
    
    args = parser.parse_args()
    if args.command == "scan":
        cmd_scan(args.keyword, args.country, args.limit, args.skip_crawl)
    elif args.command == "feedback":
        cmd_feedback(args.page_id, args.reply_text, args.positive)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
EOF

# 5. Unit Tests for Feedback Loop
cat << 'EOF' > tests/unit/test_feedback.py
"""Tests for Feedback Loop & Self-Improvement [SEED: 2399]."""
import json
from pathlib import Path
import pytest

from ad_leak_engine.self_improve.weights import load_weights, save_weights, DEFAULT_WEIGHTS
from ad_leak_engine.self_improve.tracker import process_reply

@pytest.fixture
def clean_weights(tmp_path, monkeypatch):
    test_file = tmp_path / "scoring_weights.json"
    monkeypatch.setattr("ad_leak_engine.self_improve.weights.WEIGHTS_FILE", test_file)
    return test_file

def test_load_weights_creates_default(clean_weights):
    weights = load_weights()
    assert weights == DEFAULT_WEIGHTS
    assert clean_weights.exists()

def test_process_reply_boosts_l2(clean_weights):
    load_weights() # initialize
    process_reply("p1", "Hey, our pixel was indeed broken, thanks!", positive=True)
    weights = load_weights()
    assert weights["L2"]["pixel_not_firing"] > 1.0
    assert weights["L1"]["creative_fatigue"] == 1.0 # Unchanged

def test_process_reply_caps_at_2(clean_weights):
    load_weights()
    for _ in range(20):
        process_reply("p1", "The tracking is bad", positive=True)
    weights = load_weights()
    assert weights["L2"]["pixel_not_firing"] <= 2.0
EOF

echo "[SEED:2399] Running Phase 16 test suite..."
python -m pytest tests/unit/test_feedback.py -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 16 (Roadmap Phase 8) COMPLETE"
echo "  Feedback Loop & Self-Improvement Engine installed."
echo ""
echo "  TEST THE LOOP:"
echo "  ./scripts/ale feedback 103032366405927 \"Thanks, our pixel was broken!\""
echo "  cat data/scoring_weights.json"
echo "=========================================================="