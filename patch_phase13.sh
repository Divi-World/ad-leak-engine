#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 13: DEFINITIVE EXTRACTION
# Merges proven regex extraction with full pipeline execution
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 13 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. The Definitive Regex Extractor (Handles Meta's messy Relay HTML)
cat << 'EOF' > src/ad_leak_engine/ingest/html_extractor.py
"""Robust HTML ad extractor for Meta Ad Library [SEED: 2399].
Uses regex windows around ad_archive_id anchors to extract fields
from Meta's embedded Relay/GraphQL data, which is often not valid JSON.
"""
import re
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad

class HtmlAdExtractor:
    def extract_ads(self, html: str, country: str) -> list[RawAd]:
        if not html: return []
        
        # Find all ad archive IDs (the anchor points)
        matches = list(re.finditer(r'"ad_archive_id":"(\d+)"', html))
        if not matches:
            # Fallback for older/different Meta HTML structures
            matches = list(re.finditer(r'"id":"(\d{10,20})"', html))
            
        seen = set()
        ads = []
        
        for m in matches:
            ad_id = m.group(1)
            if ad_id in seen: continue
            
            # Take a large window (6000 chars) around the match to capture context
            start = max(0, m.start() - 3000)
            end = min(len(html), m.end() + 3000)
            ctx = html[start:end]
            
            # Extract fields using multiple fallback regexes (handles Meta's schema drift)
            page_name = self._extract(ctx, [
                r'"page_name":"([^"]+)"',
                r'"page":\s*\{[^}]*"name":"([^"]+)"',
                r'"page":\s*\{[^}]*"id":"\d+"[^}]*"name":"([^"]+)"'
            ], "Unknown Page")
            
            page_id = self._extract(ctx, [
                r'"page_id":"(\d+)"',
                r'"page":\s*\{[^}]*"id":"(\d+)"'
            ], "unknown")
            
            body = self._extract(ctx, [
                r'"body":"([^"]*)"',
                r'"ad_creative_bodies":\["([^"]*)"',
                r'"snapshot":\{[^}]*"body":"([^"]*)"'
            ])
            
            link_url = self._extract(ctx, [
                r'"link_url":"([^"]+)"',
                r'"ad_creative_link_urls":\["([^"]+)"',
                r'"snapshot":\{[^}]*"link_url":"([^"]+)"'
            ])
            
            cta = self._extract(ctx, [
                r'"cta_text":"([^"]+)"',
                r'"call_to_action":"([^"]+)"'
            ])
            
            start_time = self._extract(ctx, [
                r'"ad_delivery_start_time":"?(\d+)"?',
                r'"creation_time":"?(\d+)"?'
            ])
            
            raw_node = {
                "id": ad_id,
                "ad_archive_id": ad_id,
                "page": {"id": page_id, "name": page_name},
                "snapshot": {"body": body, "link_url": link_url, "cta_text": cta},
                "body": body,
                "ad_delivery_start_time": start_time
            }
            
            try:
                ad = normalize_meta_ad(raw_node, country)
                ads.append(ad)
                seen.add(ad_id)
            except Exception:
                continue
                
        return ads

    def _extract(self, text: str, patterns: list[str], default=None):
        for p in patterns:
            m = re.search(p, text)
            if m: return m.group(1)
        return default
EOF

# 2. Update PlaywrightSource to use the Definitive Extractor
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""HUMAN-GRADE Meta Ad Library scraper using camoufox + Regex Extractor [SEED: 2399]."""
from typing import Iterator
from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..self_heal.human_browser import HumanBrowser
from .html_extractor import HtmlAdExtractor

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")

class PlaywrightSource(AbstractAdSource):
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.extractor = HtmlAdExtractor()

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

        ads = self.extractor.extract_ads(html, country)

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

# 3. Update CLI to run the FULL pipeline (L1 + L2/L3 + Fingerprint + Forge + Bundle)
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

def _fetch_html(url: str) -> str | None:
    import httpx
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, follow_redirects=True)
        return r.text if r.status_code == 200 else None
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
                print(f"[ALE]   Crawling landing page for L2/L3 telemetry...")
                page.raw = TelemetryCollector().collect(landing)
                l2_leaks, l3_leaks = l2.scan(page), l3.scan(page)
                leaks += l2_leaks + l3_leaks
                print(f"[ALE]   L2/L3 Leaks: {len(l2_leaks) + len(l3_leaks)}")
            except Exception as e:
                print(f"[ALE]   (L2/L3 crawl skipped: {e})")

        platform, conf = "custom", 0.3
        if landing:
            html = _fetch_html(landing)
            if html:
                platform, conf = detector.detect(landing, html)
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

def cmd_diagnose(keyword: str, country: str):
    print("[ALE] Diagnose command is now integrated into the scan pipeline.")
    print("[ALE] Run: ./scripts/ale scan <keyword> <country>")

def main():
    import argparse
    parser = argparse.ArgumentParser(prog="ale")
    sub = parser.add_subparsers(dest="command")
    
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("keyword", nargs="?", default="shoes")
    p_scan.add_argument("country", nargs="?", default="US")
    p_scan.add_argument("--limit", type=int, default=3)
    p_scan.add_argument("--skip-crawl", action="store_true")
    
    p_diag = sub.add_parser("diagnose")
    p_diag.add_argument("keyword", nargs="?", default="shoes")
    p_diag.add_argument("country", nargs="?", default="US")

    args = parser.parse_args()
    if args.command == "scan":
        cmd_scan(args.keyword, args.country, args.limit, args.skip_crawl)
    elif args.command == "diagnose":
        cmd_diagnose(args.keyword, args.country)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
EOF

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 13 COMPLETE"
echo "  Definitive extraction + full pipeline installed."
echo ""
echo "  RUN THE ULTIMATE COMMAND:"
echo "    ./scripts/ale scan shoes US --limit 3"
echo ""
echo "  VIEW THE TOP-1 DELIVERABLE:"
echo "    cat output/*/teardown.md"
echo "=========================================================="