"""Ad-Leak-Engine Master CLI [SEED: 2399]."""
import sys
import os
import subprocess
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
from .shared.schemas import Page, Leak
from .self_heal.human_browser import HumanBrowser
from .shared.logging import get_logger
from .shared.exceptions import PlatformAmbiguousError
try:
    from .self_improve.effectiveness import track_fix_effectiveness
except ImportError:
    track_fix_effectiveness = None

logger = get_logger()

def _fetch_html_stealth(url: str) -> str | None:
    hb = HumanBrowser(headless=True)
    try:
        with hb.session() as page:
            # [SEED: 2399] Increased timeout to 45s for heavy Shopify themes
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            hb.human_pause(1.5, 3.0)
            return page.content()
    except Exception as e:
        logger.warning(f"Stealth fetch timeout/fail: {e}. Trying early-commit...", extra={"stage": "ingest", "action": "fetch_html"})
        # [SEED: 2399] Fallback: Grab HTML as soon as network commits
        try:
            with hb.session() as page:
                page.goto(url, wait_until="commit", timeout=15000)
                return page.content()
        except Exception:
            pass
        
        # [SEED: 2399] Final Fallback: High-stealth HTTPX
        try:
            import httpx
            resp = httpx.get(url, timeout=20.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none"
            })
            if resp.status_code == 200: return resp.text
        except Exception: pass
        return None

def _fetch_html_resilient(url: str) -> str | None:
    """Self-healing HTML acquisition: stealth -> early-commit retry -> plain HTTP."""
    html = _fetch_html_stealth(url)
    if html:
        return html
    hb = HumanBrowser(headless=True)
    try:
        with hb.session() as page:
            page.goto(url, wait_until="commit", timeout=45000)
            hb.human_pause(1.0, 2.0)
            return page.content()
    except Exception as e:
        logger.error(f"Early-commit fetch failed: {e}", extra={"stage": "ingest", "action": "fetch_html_commit"})
    try:
        import httpx
        resp = httpx.get(url, timeout=20.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
        })
        if resp.status_code == 200 and resp.text:
            return resp.text
    except Exception as e:
        logger.error(f"Plain HTTP fetch failed: {e}", extra={"stage": "ingest", "action": "fetch_html_http"})
    
    # [SEED: 2399] WAYBACK MACHINE FALLBACK (Defeats enterprise bot protection)
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        wb_resp = httpx.get(f"http://archive.org/wayback/available?url={domain}", timeout=10.0)
        if wb_resp.status_code == 200:
            wb_data = wb_resp.json()
            if "archived_snapshots" in wb_data and "closest" in wb_data["archived_snapshots"]:
                wb_url = wb_data["archived_snapshots"]["closest"].get("url")
                if wb_url:
                    wb_html_resp = httpx.get(wb_url, timeout=15.0, follow_redirects=True)
                    if wb_html_resp.status_code == 200 and wb_html_resp.text:
                        logger.info(f"Wayback fetch succeeded for {url}", extra={"stage": "ingest", "action": "fetch_html_wayback"})
                        return wb_html_resp.text
    except Exception as e:
        logger.error(f"Wayback fetch failed: {e}", extra={"stage": "ingest", "action": "fetch_html_wayback"})
    return None

def cmd_scan(keyword: str, country: str, limit: int, skip_crawl: bool):
    logger.info(f"Initiating LIVE SCAN for '{keyword}'", extra={"stage": "orchestrator", "action": "scan_start"})
    print(f"[ALE] Initiating LIVE SCAN for '{keyword}' in {country}...")
    init_db()
    repo = AdRepository()

    source = PlaywrightSource(headless=True)
    print("[ALE] Launching stealth browser and pulling ads...")
    ads = list(source.search(keyword, country, max_results=50))
    
    if not ads:
        logger.warning("No ads extracted.", extra={"stage": "ingest", "action": "search"})
        print("[ALE] ERROR: No ads extracted.")
        return

    inserted = repo.upsert_ads(ads)
    logger.info(f"Extracted {len(ads)} real ads. Persisted {inserted} new.", extra={"stage": "persistence", "action": "upsert"})
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
        
        # Top 1 Polish: Detect invalid or geo-blocked URLs before fetching
        is_invalid_url = False
        if landing:
            if not landing.startswith(("http://", "https://")) or "fbgeo" in landing or "facebook.com" in landing or "instagram.com" in landing:
                is_invalid_url = True
                print(f"[ALE]   Skipping crawl: Invalid or internal Meta URL detected.")
                leaks.append(Leak(
                    page_id=page.id, 
                    tier="L3", 
                    signal="invalid_landing_url", 
                    severity=0.9, 
                    recommendation="Landing page URL is invalid, internal, or geo-blocked. Fix the destination URL in Ads Manager.", 
                    evidence={"url": landing}
                ))

        html_content = None
        platform, conf = "custom", 0.3
        if landing and not is_invalid_url:
            print(f"[ALE]   Fetching HTML for platform fingerprinting...")
            html_content = _fetch_html_resilient(landing)
            if html_content:
                platform, conf, _evidence = detector.detect(landing, html_content)
            page.fingerprint = platform

        if landing and not skip_crawl and not is_invalid_url:
            try:
                from .leak_scan.telemetry_collector import TelemetryCollector
                print(f"[ALE]   Crawling landing page with stealth browser for L2/L3 telemetry...")
                page.raw = TelemetryCollector().collect(landing)
                if html_content:
                    page.raw["html"] = html_content
                l2_leaks, l3_leaks = l2.scan(page), l3.scan(page)
                leaks += l2_leaks + l3_leaks
                print(f"[ALE]   L2/L3 Leaks: {len(l2_leaks) + len(l3_leaks)}")
            except Exception as e:
                logger.error(f"L2/L3 crawl failed: {e}", extra={"stage": "leak_scan", "action": "l2_l3_crawl"})
                print(f"[ALE]   (L2/L3 crawl skipped: {e})")
        print(f"[ALE]   Platform: {platform} (confidence {conf:.2f})")

        fixes = []
        for leak in leaks:
            try:
                fixes.append(forge.generate(leak, platform, conf))
            except PlatformAmbiguousError:
                # Top 1 Polish: Fallback to platform-agnostic custom fixes (GTM/Server-side)
                logger.warning(f"Platform confidence {conf} too low for {platform}. Falling back to custom fixes.", extra={"stage": "fix_forge", "action": "fallback"})
                try:
                    fixes.append(forge.generate(leak, "custom", conf))
                except Exception as e:
                    logger.error(f"Custom fix generation also failed: {e}", extra={"stage": "fix_forge", "action": "generate"})
            except Exception as e:
                logger.error(f"Fix generation failed: {e}", extra={"stage": "fix_forge", "action": "generate"})
                continue
        
        pack = builder.build(page, leaks, fixes)
        print(f"[ALE]   -> Outreach pack saved: output/{page_id}/teardown.md")
        print(f"[ALE]   -> Estimated recovery: {pack.estimated_recovery}")
        processed += 1

    logger.info(f"SCAN COMPLETE. {processed} pages audited.", extra={"stage": "orchestrator", "action": "scan_complete", "ad_count": len(ads)})
    print(f"\n[ALE] SCAN COMPLETE. {processed} pages audited.")

def cmd_feedback(page_id: str, reply_text: str, positive: bool):
    from .self_improve.tracker import process_reply
    from .self_improve.niche import log_niche_result
    print(f"[ALE] Processing feedback for page {page_id}...")
    process_reply(page_id, reply_text, positive)
    if track_fix_effectiveness:
        track_fix_effectiveness(page_id, 0.8, 0.4 if positive else 0.9, "template_id")
    log_niche_result("ecommerce", positive)
    print("[ALE] Niche performance logged.")

def cmd_test():
    print("[ALE] Running full test suite...")
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "--tb=short"])

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

    sub.add_parser("test")
    
    args = parser.parse_args()
    if args.command == "scan":
        cmd_scan(args.keyword, args.country, args.limit, args.skip_crawl)
    elif args.command == "feedback":
        cmd_feedback(args.page_id, args.reply_text, args.positive)
    elif args.command == "test":
        cmd_test()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
