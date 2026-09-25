#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 15: SURGICAL FIXES
# Fixes relative imports & upgrades stealth HTML fetch for fingerprinting
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 15 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Fix L2 Probe Import (Absolute path)
cat << 'EOF' > src/ad_leak_engine/leak_scan/l2_probe.py
"""REAL Playwright probe using camoufox (stealth) [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class L2LiveProbe:
    def probe(self, url: str, timeout_ms: int = 25000) -> dict:
        network_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "has_unhashed_pii": False, "is_checkout_page": False,
        }
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                captured = []
                def on_request(request): captured.append(request.url)
                page.on("request", on_request)
                
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 4.0)
                hb.human_scroll(page, distance=500, steps=5)
                hb.human_pause(1.0, 2.0)

                content = ""
                try: content = page.content().lower()
                except Exception: pass

                pixel_requests = [u for u in captured if "facebook.com/tr" in u.lower()]
                has_fbq = "fbevents.js" in content or "fbq(" in content
                network_log["pixel_fired"] = len(pixel_requests) > 0 or has_fbq
                network_log["requests"] = [u for u in captured if "facebook" in u.lower()]

                capi_requests = [u for u in captured if "graph.facebook.com" in u.lower() and "/events" in u.lower()]
                for cr in capi_requests:
                    network_log["capi_events"].append({"event_name": "server_event", "url": cr})

                url_lower = url.lower()
                network_log["is_checkout_page"] = any(
                    k in url_lower for k in ["checkout", "thank", "order", "confirm", "cart"]
                )
        except Exception as e:
            network_log["error"] = str(e)
        return network_log
EOF

# 2. Fix L3 Performance Import (Absolute path)
cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/performance.py
"""REAL Core Web Vitals measurement via camoufox [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class PerformanceAuditor:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 4.0)

                ttfb = page.evaluate(
                    "() => { const n = performance.getEntriesByType('navigation')[0];"
                    " return n ? n.responseStart - n.requestStart : null; }"
                )
                if ttfb and ttfb > 0: telemetry["ttfb_ms"] = ttfb

                lcp = page.evaluate(
                    "() => { const e = performance.getEntriesByType('largest-contentful-paint');"
                    " return e.length ? e[e.length-1].startTime : null; }"
                )
                if lcp: telemetry["lcp_mobile_ms"] = lcp
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
EOF

# 3. Fix L3 UX Import (Absolute path)
cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/mobile_ux.py
"""REAL mobile UX analysis via camoufox [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class MobileUXAnalyzer:
    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 3.0)

                min_tap = page.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('a,button,input,select,[role=button]'));"
                    " const sizes = els.map(e => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height); }).filter(s => s > 0);"
                    " return sizes.length ? Math.min(...sizes) : null; }"
                )
                if min_tap is not None: telemetry["min_tap_target_px"] = min_tap
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
EOF

# 4. Upgrade CLI to use HumanBrowser for stealth HTML fetching (bypasses Cloudflare for fingerprinting)
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
    """Uses camoufox to fetch fully rendered HTML, bypassing Cloudflare/Akamai."""
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

def main():
    import argparse
    parser = argparse.ArgumentParser(prog="ale")
    sub = parser.add_subparsers(dest="command")
    
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("keyword", nargs="?", default="shoes")
    p_scan.add_argument("country", nargs="?", default="US")
    p_scan.add_argument("--limit", type=int, default=3)
    p_scan.add_argument("--skip-crawl", action="store_true")
    
    args = parser.parse_args()
    if args.command == "scan":
        cmd_scan(args.keyword, args.country, args.limit, args.skip_crawl)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
EOF

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 15 COMPLETE"
echo "  Imports fixed. Stealth HTML fetch enabled for fingerprinting."
echo "=========================================================="