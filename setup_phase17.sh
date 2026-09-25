#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 17 (Roadmap Phase 9)
# Hardening, Structured JSON Logging, Chaos Testing, Runbook
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 17 BOOTSTRAP"
echo "  (Roadmap Phase 9: Hardening & Production Readiness)"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Structured JSON Logger
cat << 'EOF' > src/ad_leak_engine/shared/logging.py
"""Structured JSON logging for Ad-Leak-Engine [SEED: 2399]."""
import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": 2399,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "stage": getattr(record, "stage", "unknown"),
            "action": getattr(record, "action", "unknown"),
            "error": str(record.exc_info[1]) if record.exc_info else None
        }
        return json.dumps(log_entry)

def get_logger(name: str = "ad_leak_engine") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Console handler (clean output for CLI)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter("[SEED:2399] %(message)s"))
        logger.addHandler(ch)
        
        # File handler (structured JSON for production monitoring)
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "engine.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        logger.addHandler(fh)
        
    return logger
EOF

# 2. Chaos Tests (Proves system never crashes under adversarial failure)
cat << 'EOF' > tests/integration/test_chaos.py
"""Chaos testing: Resilience under failure [SEED: 2399]."""
import pytest
from ad_leak_engine.self_heal.circuit_breaker import CircuitBreaker, CircuitState
from ad_leak_engine.shared.exceptions import BlockedError, SchemaDriftError, EmptyResponseError
from ad_leak_engine.ingest.hybrid_router import HybridRouter
from ad_leak_engine.shared.schemas import RawAd
from datetime import datetime, timezone

class ChaosSource:
    def __init__(self, error_to_raise=None, ads=None):
        self.error = error_to_raise
        self.ads = ads or []

    def search(self, query, country, max_results=50):
        if self.error:
            raise self.error
        yield from self.ads

    def health_check(self): return True

def _ad(id="1"):
    return RawAd(id=id, page_id="p1", page_name="Test", start_date=datetime.now(timezone.utc), media_type="IMAGE")

def test_chaos_circuit_breaker_opens_and_fallbacks():
    """Simulates primary source failing repeatedly, forcing circuit open and fallback."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=BlockedError("DataDome Block")),
        playwright=ChaosSource(ads=[_ad("fallback_ad")]),
    )
    ads = list(router.search("shoes", "US"))
    assert len(ads) == 1
    assert ads[0].id == "fallback_ad"
    assert router.breaker.state == CircuitState.OPEN

def test_chaos_schema_drift_triggers_fallback():
    """Simulates Meta changing GraphQL schema, system must auto-fallback."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=SchemaDriftError("Keys changed")),
        playwright=ChaosSource(ads=[_ad("drift_fallback")]),
    )
    ads = list(router.search("shoes", "US"))
    assert ads[0].id == "drift_fallback"

def test_chaos_total_system_failure():
    """Simulates both sources failing. Router must not crash, just yield empty."""
    router = HybridRouter(
        graphql=ChaosSource(error_to_raise=EmptyResponseError("Timeout")),
        playwright=ChaosSource(error_to_raise=BlockedError("IP Ban")),
    )
    ads = list(router.search("shoes", "US"))
    assert len(ads) == 0
EOF

# 3. Update Master CLI (adds 'test' command + wires JSON logger)
cat << 'EOF' > src/ad_leak_engine/cli.py
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
from .shared.schemas import Page
from .self_heal.human_browser import HumanBrowser
from .shared.logging import get_logger

logger = get_logger()

def _fetch_html_stealth(url: str) -> str | None:
    hb = HumanBrowser(headless=True)
    try:
        with hb.session() as page:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            hb.human_pause(1.5, 3.0)
            return page.content()
    except Exception as e:
        logger.error(f"Stealth fetch failed: {e}", extra={"stage": "ingest", "action": "fetch_html"})
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
        
        if landing and not skip_crawl:
            try:
                from .leak_scan.telemetry_collector import TelemetryCollector
                print(f"[ALE]   Crawling landing page with stealth browser for L2/L3 telemetry...")
                page.raw = TelemetryCollector().collect(landing)
                l2_leaks, l3_leaks = l2.scan(page), l3.scan(page)
                leaks += l2_leaks + l3_leaks
                print(f"[ALE]   L2/L3 Leaks: {len(l2_leaks) + len(l3_leaks)}")
            except Exception as e:
                logger.error(f"L2/L3 crawl failed: {e}", extra={"stage": "leak_scan", "action": "l2_l3_crawl"})
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
EOF

# 4. Production Runbook
cat << 'EOF' > RUNBOOK.md
# Ad-Leak-Engine Runbook [SEED: 2399]

## Master Commands
- `./scripts/ale scan <keyword> <country> [--limit N] [--skip-crawl]` : Full pipeline execution
- `./scripts/ale feedback <page_id> "<reply_text>"` : Self-improvement feedback loop
- `./scripts/ale test` : Run the full test suite

## Troubleshooting
- **No ads extracted:** Meta's schema may have drifted. The system relies on regex fallback. Inspect `data/debug/`.
- **L2/L3 Crawl Skipped:** Prospect's landing page has aggressive bot protection. The system safely skips to prevent IP bans.
- **Platform = custom (0.30):** The fingerprinter couldn't confidently identify Shopify/WooCommerce/BigCommerce. The system safely defaults to generic GTM/Server-side fixes.

## Log Inspection
All structured logs are written to `logs/engine.log` in JSON format for easy parsing:
`cat logs/engine.log | grep "ERROR"`
EOF

# 5. Run Chaos Tests
echo "[SEED:2399] Running Phase 17 Chaos test suite..."
python -m pytest tests/integration/test_chaos.py -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 17 (Roadmap Phase 9) COMPLETE"
echo "  Hardening, JSON Logging, Chaos Testing, Runbook installed."
echo ""
echo "  RUN THE FULL TEST SUITE ANYTIME:"
echo "  ./scripts/ale test"
echo ""
echo "  VIEW THE LOGS AFTER A SCAN:"
echo "  cat logs/engine.log"
echo "=========================================================="