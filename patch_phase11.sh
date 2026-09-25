#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 11: CONSOLIDATION
# Deletes pollution, builds the master 'ale' CLI, fixes Windows encoding
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 11 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Delete the pollution
echo "[SEED:2399] Cleaning up scattered diagnostic scripts..."
rm -f scripts/diagnose_ingest.py
rm -f scripts/diagnose_ingest_v2.py
rm -f scripts/debug_ingest.py

# 2. Build the Master CLI (src/ad_leak_engine/cli.py)
cat << 'EOF' > src/ad_leak_engine/cli.py
"""Ad-Leak-Engine Master CLI [SEED: 2399].
Usage:
  ./scripts/ale diagnose <keyword> <country>
"""
import sys
import re
from pathlib import Path
from .self_heal.human_browser import HumanBrowser

def cmd_diagnose(keyword: str, country: str):
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&q={keyword}&search_type=keyword_unordered"
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"[ALE] Target: {url}")
    hb = HumanBrowser(headless=True)
    
    with hb.session() as page:
        print("[ALE] Priming session on facebook.com...")
        hb.prime_facebook_session(page)
        
        print("[ALE] Navigating to Ad Library with human behavior...")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        hb.human_pause(3.0, 5.0)
        
        for _ in range(3):
            hb.human_scroll(page, distance=800, steps=10)
            hb.human_pause(1.5, 3.0)
            
        html = page.content()
        page.screenshot(path=str(debug_dir / "screenshot.png"), full_page=True)
        
    # Save HTML for inspection
    (debug_dir / "page.html").write_text(html, encoding="utf-8")
    
    # Analyze the 2.4MB HTML for embedded ad data
    # Meta embeds the GraphQL data directly in the HTML for React hydration
    ad_ids = set(re.findall(r'"ad_archive_id":"(\d+)"', html))
    page_ids = set(re.findall(r'"page_id":"(\d+)"', html))
    
    print("")
    print("=" * 50)
    print(f"[ALE] HTML Size: {len(html):,} chars")
    print(f"[ALE] Unique Ad IDs found in DOM: {len(ad_ids)}")
    print(f"[ALE] Unique Page IDs found in DOM: {len(page_ids)}")
    print("=" * 50)
    
    if len(ad_ids) > 0:
        print("[ALE] VERDICT: SUCCESS. Ads are fully rendered in the HTML.")
        print(f"[ALE] Sample Ad IDs: {list(ad_ids)[:5]}")
        print("[ALE] Next step: The field mapper will parse this HTML into RawAd contracts.")
    else:
        print("[ALE] VERDICT: HTML loaded but no ad_archive_id markers found.")
        print("[ALE] Check data/debug/screenshot.png to see what Meta rendered.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ad-Leak-Engine Master CLI [SEED: 2399]")
        print("Usage: ./scripts/ale <command> [args]")
        print("Commands:")
        print("  diagnose <keyword> <country>  - Run human-grade diagnostic")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == "diagnose":
        kw = sys.argv[2] if len(sys.argv) > 2 else "shoes"
        co = sys.argv[3] if len(sys.argv) > 3 else "US"
        cmd_diagnose(kw, co)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
EOF

# 3. Build the bash wrapper (scripts/ale)
cat << 'EOF' > scripts/ale
#!/bin/bash
# Ad-Leak-Engine Master CLI Wrapper [SEED: 2399]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Auto-activate venv if not already active
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f "$ROOT_DIR/.venv/Scripts/activate" ]; then
        source "$ROOT_DIR/.venv/Scripts/activate"
    elif [ -f "$ROOT_DIR/.venv/bin/activate" ]; then
        source "$ROOT_DIR/.venv/bin/activate"
    fi
fi

cd "$ROOT_DIR"
python -m ad_leak_engine.cli "$@"
EOF
chmod +x scripts/ale

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 11 COMPLETE"
echo "  System consolidated. Master CLI built."
echo ""
echo "  RUN THE NEW MASTER COMMAND:"
echo "    ./scripts/ale diagnose shoes US"
echo "=========================================================="