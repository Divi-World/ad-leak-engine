#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 11.2: LIVE PIPELINE
# HTML Parser + Network Interception + Master Scan Command
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 11.2 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Build the HTML Parser (extracts ads from the 2.4MB HTML blob)
cat << 'EOF' > src/ad_leak_engine/ingest/html_parser.py
"""HTML Parser: Extracts RawAd contracts from Meta's embedded HTML [SEED: 2399].

When Meta embeds the GraphQL data directly into the HTML for React hydration,
the network interceptor may miss it. This parser uses regex to reliably
extract ad_archive_id, page_id, page_name, and body from the raw HTML.
"""
import re
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad

def parse_html_to_ads(html: str, country: str) -> list[RawAd]:
    """Extracts ads from the raw HTML using regex markers."""
    ads = []
    seen = set()
    
    # Find all ad_archive_ids in the HTML
    matches = re.finditer(r'"ad_archive_id":"(\d+)"', html)
    
    for match in matches:
        ad_id = match.group(1)
        if ad_id in seen:
            continue
        seen.add(ad_id)
        
        # Extract surrounding context (approx 3000 chars around the match)
        start = max(0, match.start() - 1500)
        end = min(len(html), match.end() + 1500)
        context = html[start:end]
        
        # Extract page_id
        page_id_match = re.search(r'"page":\s*\{\s*"id":"(\d+)"', context)
        page_id = page_id_match.group(1) if page_id_match else "unknown"
        
        # Extract page_name
        page_name_match = re.search(r'"page":\s*\{\s*"id":"\d+",\s*"name":"([^"]+)"', context)
        page_name = page_name_match.group(1) if page_name_match else "Unknown Page"
        
        # Extract snapshot/body
        body_match = re.search(r'"body":\s*"([^"]{0,1000})"', context)
        body = body_match.group(1) if body_match else None
        
        # Extract creation_time (unix timestamp)
        time_match = re.search(r'"ad_delivery_start_time":\s*"?(\d+)"?', context)
        creation_time = int(time_match.group(1)) if time_match else None
        
        raw_node = {
            "id": ad_id,
            "ad_archive_id": ad_id,
            "page": {"id": page_id, "name": page_name},
            "snapshot": {"body": body},
            "creation_time": creation_time
        }
        
        try:
            ad = normalize_meta_ad(raw_node, country)
            ads.append(ad)
        except Exception:
            continue
            
    return ads
EOF

# 2. Update playwright_source.py to use HTML Parser as primary
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HUMAN-GRADE Meta Ad Library scraper using camoufox + HTML Parser [SEED: 2399]."""
from typing import Iterator
from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .html_parser import parse_html_to_ads

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

class PlaywrightSource(AbstractAdSource):
    def __init__(self, headless: bool = True):
        self.headless = headless

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        hb = HumanBrowser(headless=self.headless)
        
        try:
            with hb.session() as page:
                hb.prime_facebook_session(page)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                hb.human_pause(3.0, 5.0)
                
                for _ in range(3):
                    hb.human_scroll(page, distance=800, steps=10)
                    hb.human_pause(1.5, 3.0)
                    
                html = page.content()
        except Exception:
            return

        # Parse the 2.4MB HTML blob directly
        ads = parse_html_to_ads(html, country)
        
        seen = set()
        count = 0
        for ad in ads:
            if ad.id not in seen:
                seen.add(ad.id)
                yield ad
                count += 1
                if count >= max_results:
                    return

    def health_check(self) -> bool:
        return True
EOF

# 3. Update the Master CLI with the `scan` command
cat << 'EOF' > src/ad_leak_engine/cli.py
"""Ad-Leak-Engine Master CLI [SEED: 2399]."""
import sys
import os
import json
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        os.environ['PYTHONIOENCODING'] = 'utf-8'

from .ingest.playwright_source import PlaywrightSource
from .ingest.deduplicator import Deduplicator
from .leak_scan.l1_creative import L1CreativeScanner
from .persistence.db import init_db
from .persistence.repository import AdRepository
from .shared.schemas import Page
from datetime import datetime, timezone

def cmd_diagnose(keyword: str, country: str):
    from .self_heal.human_browser import HumanBrowser
    import re
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&q={keyword}&search_type=keyword_unordered"
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[ALE] Target: {url}")
    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        print("[ALE] Priming session...")
        hb.prime_facebook_session(page)
        print("[ALE] Navigating...")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        hb.human_pause(3.0, 5.0)
        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)
        html = page.content()
        page.screenshot(path=str(debug_dir / "screenshot.png"), full_page=True)
        
    (debug_dir / "page.html").write_text(html, encoding="utf-8")
    ad_ids = set(re.findall(r'"ad_archive_id":"(\d+)"', html))
    page_ids = set(re.findall(r'"page_id":"(\d+)"', html))
    
    print(f"\n[ALE] HTML Size: {len(html):,} chars")
    print(f"[ALE] Unique Ad IDs found: {len(ad_ids)}")
    print(f"[ALE] Unique Page IDs found: {len(page_ids)}")
    if len(ad_ids) > 0:
        print("[ALE] VERDICT: SUCCESS. Ads are fully rendered.")

def cmd_scan(keyword: str, country: str):
    print(f"[ALE] Initiating LIVE SCAN for '{keyword}' in {country}...")
    init_db()
    repo = AdRepository()
    dedup = Deduplicator()
    
    source = PlaywrightSource(headless=True)
    print("[ALE] Launching stealth browser and pulling ads...")
    raw_ads = list(source.search(keyword, country, max_results=50))
    
    if not raw_ads:
        print("[ALE] ERROR: No ads extracted. Run './scripts/ale diagnose' to troubleshoot.")
        return
        
    new_ads = dedup.filter_new(raw_ads)
    inserted = repo.upsert_ads(new_ads)
    
    print(f"[ALE] Extracted {len(raw_ads)} total ads.")
    print(f"[ALE] Saved {inserted} NEW ads to SQLite database.")
    
    # Group by page for L1 scanning
    pages = {}
    for ad in raw_ads:
        if ad.page_id not in pages:
            pages[ad.page_id] = Page(
                id=ad.page_id, 
                name=ad.page_name, 
                first_seen=datetime.now(timezone.utc)
            )
        pages[ad.page_id].ads.append(ad)
        
    print(f"[ALE] Running L1 Leak Scanner on {len(pages)} unique pages...")
    scanner = L1CreativeScanner()
    total_leaks = 0
    
    print("\n" + "="*60)
    print(f"  LIVE LEAK REPORT: {keyword} ({country})")
    print("="*60)
    
    for page_id, page in pages.items():
        leaks = scanner.scan(page)
        if leaks:
            total_leaks += len(leaks)
            print(f"\n[!] PAGE: {page.name} (ID: {page_id})")
            print(f"    Active Ads: {len(page.active_ads)}")
            for leak in leaks:
                sev_pct = int(leak.severity * 100)
                print(f"    -> LEAK: {leak.signal} (Severity: {sev_pct}%)")
                print(f"       Fix: {leak.recommendation}")
                
    print("\n" + "="*60)
    print(f"  SUMMARY: Found {total_leaks} leaks across {len(pages)} pages.")
    print("="*60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ad-Leak-Engine Master CLI [SEED: 2399]")
        print("Usage: ./scripts/ale <command> [args]")
        print("Commands:")
        print("  diagnose <kw> <country>  - Verify browser stealth & HTML extraction")
        print("  scan <kw> <country>      - Pull live ads, save to DB, run L1 scanner")
        sys.exit(1)
        
    cmd = sys.argv[1]
    kw = sys.argv[2] if len(sys.argv) > 2 else "shoes"
    co = sys.argv[3] if len(sys.argv) > 3 else "US"
    
    if cmd == "diagnose": cmd_diagnose(kw, co)
    elif cmd == "scan": cmd_scan(kw, co)
    else: print(f"Unknown command: {cmd}")
EOF

# 4. Update the bash wrapper
cat << 'EOF' > scripts/ale
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "$ROOT_DIR/.venv/Scripts/activate" ]; then source "$ROOT_DIR/.venv/Scripts/activate"
    elif [ -f "$ROOT_DIR/.venv/bin/activate" ]; then source "$ROOT_DIR/.venv/bin/activate"
    fi
fi
cd "$ROOT_DIR"
python -m ad_leak_engine.cli "$@"
EOF
chmod +x scripts/ale

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 11.2 COMPLETE"
echo "  HTML Parser wired. Live Scan command ready."
echo ""
echo "  RUN THE ULTIMATE COMMAND NOW:"
echo "    ./scripts/ale scan shoes US"
echo "=========================================================="