#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 19 (Roadmap Phase 7)
# FINAL PHASE: Distributed Ephemeral Swarm — Scale Automation
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 19 BOOTSTRAP"
echo "  (Roadmap Phase 7: Distributed Ephemeral Swarm)"
echo "  THIS IS THE FINAL PHASE OF THE MASTER ROADMAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# 1. Swarm IP Coordination Manager
cat << 'EOF' > src/ad_leak_engine/self_heal/proxy_manager.py
"""Swarm IP coordination for Distributed Ephemeral Swarm [SEED: 2399].

In the GitHub Actions swarm model, each runner IS a unique IP.
This manager coordinates shard assignment, tracks runner health,
and enforces pacing to prevent collective rate limiting.
"""
import time
import random
from dataclasses import dataclass, field
from enum import Enum


class RunnerStatus(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    FAILED = "failed"


@dataclass
class RunnerState:
    runner_id: str
    status: RunnerStatus = RunnerStatus.IDLE
    requests_made: int = 0
    failures: int = 0
    last_active: float = 0.0
    cooldown_until: float = 0.0


class SwarmProxyManager:
    """Coordinates ephemeral runners in the GitHub Actions swarm."""

    def __init__(self, max_shards: int = 10, cooldown_seconds: int = 600):
        self.max_shards = max_shards
        self.cooldown_seconds = cooldown_seconds
        self.runners: dict[str, RunnerState] = {}
        self._request_log: list[float] = []

    def register_runner(self, runner_id: str) -> RunnerState:
        if runner_id not in self.runners:
            self.runners[runner_id] = RunnerState(runner_id=runner_id)
        return self.runners[runner_id]

    def get_available_runner(self) -> RunnerState | None:
        now = time.time()
        for runner in self.runners.values():
            if runner.status == RunnerStatus.COOLDOWN:
                if now >= runner.cooldown_until:
                    runner.status = RunnerStatus.IDLE
                    runner.failures = 0
                else:
                    continue
            if runner.status == RunnerStatus.IDLE:
                return runner
        return None

    def assign_task(self, runner_id: str) -> bool:
        runner = self.runners.get(runner_id)
        if not runner or runner.status != RunnerStatus.IDLE:
            return False
        runner.status = RunnerStatus.ACTIVE
        runner.last_active = time.time()
        runner.requests_made += 1
        self._request_log.append(time.time())
        return True

    def report_success(self, runner_id: str):
        runner = self.runners.get(runner_id)
        if runner:
            runner.status = RunnerStatus.IDLE
            runner.failures = 0

    def report_failure(self, runner_id: str):
        runner = self.runners.get(runner_id)
        if runner:
            runner.failures += 1
            if runner.failures >= 3:
                runner.status = RunnerStatus.COOLDOWN
                runner.cooldown_until = time.time() + self.cooldown_seconds
            else:
                runner.status = RunnerStatus.IDLE

    def get_request_rate(self, window_seconds: int = 60) -> float:
        """Requests per second in the given window."""
        now = time.time()
        cutoff = now - window_seconds
        recent = [t for t in self._request_log if t >= cutoff]
        return len(recent) / window_seconds if window_seconds > 0 else 0.0

    def should_throttle(self, max_rps: float = 0.5) -> bool:
        """Returns True if collective request rate exceeds threshold."""
        return self.get_request_rate() > max_rps

    def get_pacing_delay(self) -> float:
        """Randomized delay to prevent collective rate limiting."""
        return random.uniform(15.0, 45.0)

    def health_summary(self) -> dict:
        statuses = {}
        for runner in self.runners.values():
            s = runner.status.value
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "total_runners": len(self.runners),
            "max_shards": self.max_shards,
            "statuses": statuses,
            "request_rate_rps": round(self.get_request_rate(), 3),
        }
EOF

# 2. Updated swarm_scrape.py — aligned with current ale scan pipeline
cat << 'EOF' > scripts/swarm_scrape.py
"""Ephemeral swarm scrape runner [SEED: 2399].

Executes on a GitHub Actions runner (fresh IP, fresh browser).
Runs the full ale scan pipeline and writes results to output/swarm/.
"""
import argparse
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.ingest.playwright_source import PlaywrightSource
from ad_leak_engine.leak_scan.l1_creative import L1CreativeScanner
from ad_leak_engine.shared.schemas import Page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--country", default="US")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output-dir", default="output/swarm")
    args = parser.parse_args()

    print(f"[SWARM] Scraping '{args.keyword}' in {args.country}...")
    source = PlaywrightSource(headless=True)
    ads = list(source.search(args.keyword, args.country, args.max_results))
    print(f"[SWARM] Collected {len(ads)} ads.")

    if not ads:
        print("[SWARM] No ads collected. Exiting.")
        return

    # Run L1 analysis
    scanner = L1CreativeScanner()
    pages_data = {}
    for ad in ads:
        if ad.page_id not in pages_data:
            pages_data[ad.page_id] = {
                "page_id": ad.page_id,
                "page_name": ad.page_name,
                "ads": [],
                "leaks": []
            }
        pages_data[ad.page_id]["ads"].append(ad.model_dump(mode="json"))

    for page_id, pdata in pages_data.items():
        page = Page(
            id=pdata["page_id"],
            name=pdata["page_name"],
            first_seen=datetime.now(timezone.utc),
            ads=[type('Ad', (), ad)() for ad in pdata["ads"]]
        )
        try:
            from ad_leak_engine.shared.schemas import RawAd
            page.ads = [RawAd(**ad) for ad in pdata["ads"]]
            leaks = scanner.scan(page)
            pdata["leaks"] = [l.model_dump(mode="json") for l in leaks]
        except Exception as e:
            print(f"[SWARM] L1 scan error for {page_id}: {e}")

    # Write results
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(datetime.now(timezone.utc).timestamp())
    out_file = out_dir / f"swarm_{args.keyword}_{stamp}.json"
    
    result = {
        "keyword": args.keyword,
        "country": args.country,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "seed": 2399,
        "total_ads": len(ads),
        "total_pages": len(pages_data),
        "pages": pages_data
    }
    
    out_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"[SWARM] Results saved: {out_file}")
    print(f"[SWARM] {len(pages_data)} pages, {sum(len(p['leaks']) for p in pages_data.values())} leaks detected.")


if __name__ == "__main__":
    main()
EOF

# 3. Updated aggregate_swarm.py — merges swarm results into SQLite
cat << 'EOF' > scripts/aggregate_swarm.py
"""Aggregate swarm results from output/swarm/ into SQLite [SEED: 2399]."""
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.shared.schemas import RawAd
from ad_leak_engine.persistence.db import init_db
from ad_leak_engine.persistence.repository import AdRepository


def main():
    swarm_dir = Path("output/swarm")
    if not swarm_dir.exists():
        print("[AGG] No output/swarm directory found. Run swarm first.")
        return

    all_ads = []
    seen = set()
    files_processed = 0

    for f in sorted(swarm_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for page_id, pdata in data.get("pages", {}).items():
                for ad_dict in pdata.get("ads", []):
                    # Convert lists back to tuples for Pydantic
                    for key in ("impressions", "spend"):
                        if isinstance(ad_dict.get(key), list):
                            ad_dict[key] = tuple(ad_dict[key])
                    ad = RawAd(**ad_dict)
                    if ad.id not in seen:
                        seen.add(ad.id)
                        all_ads.append(ad)
            files_processed += 1
        except Exception as e:
            print(f"[AGG] Skipping {f.name}: {e}")

    if not all_ads:
        print("[AGG] No new ads found in swarm results.")
        return

    init_db()
    repo = AdRepository()
    inserted = repo.upsert_ads(all_ads)
    
    print(f"[AGG] Processed {files_processed} swarm files.")
    print(f"[AGG] Found {len(all_ads)} unique ads.")
    print(f"[AGG] Inserted {inserted} new ads into SQLite.")


if __name__ == "__main__":
    main()
EOF

# 4. Updated GitHub Actions: swarm_matrix.yml
cat << 'EOF' > .github/workflows/swarm_matrix.yml
name: Swarm Matrix Scan [SEED: 2399]

on:
  workflow_dispatch:
    inputs:
      keyword:
        description: 'Keyword to search'
        required: true
        default: 'shoes'
      country:
        description: 'Country code'
        required: true
        default: 'US'
      max_results:
        description: 'Max ads per runner'
        required: false
        default: '50'

jobs:
  swarm:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4, 5]
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[scrape]"
          playwright install chromium

      - name: Ephemeral scrape (shard ${{ matrix.shard }})
        run: |
          python scripts/swarm_scrape.py \
            --keyword "${{ inputs.keyword }}" \
            --country "${{ inputs.country }}" \
            --max-results "${{ inputs.max_results }}"

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: swarm-shard-${{ matrix.shard }}-${{ github.run_id }}
          path: output/swarm/
EOF

# 5. Updated dispatch_swarm.sh
cat << 'EOF' > scripts/dispatch_swarm.sh
#!/bin/bash
# Dispatch the Distributed Ephemeral Swarm [SEED: 2399]
KEYWORD="${1:-shoes}"
COUNTRY="${2:-US}"
RUNS="${3:-1}"

if ! command -v gh &>/dev/null; then
    echo "[SEED:2399] GitHub CLI (gh) not found. Install: https://cli.github.com/"
    echo "[SEED:2399] Or trigger 'Swarm Matrix Scan' manually in the GitHub Actions UI."
    exit 1
fi

echo "[SEED:2399] Dispatching swarm for keyword='$KEYWORD' country=$COUNTRY runs=$RUNS"
for i in $(seq 1 "$RUNS"); do
    gh workflow run swarm_matrix.yml -f keyword="$KEYWORD" -f country="$COUNTRY"
    echo "[SEED:2399] Dispatched swarm run $i."
    sleep 2
done
echo "[SEED:2399] All dispatches sent. Check GitHub Actions for progress."
EOF
chmod +x scripts/dispatch_swarm.sh

# 6. Swarm integration test
cat << 'EOF' > tests/integration/test_swarm.py
"""Integration tests for Distributed Ephemeral Swarm [SEED: 2399]."""
import pytest
import time

from ad_leak_engine.self_heal.proxy_manager import (
    SwarmProxyManager, RunnerStatus
)
from ad_leak_engine.orchestrator.dispatcher import SwarmDispatcher


class TestSwarmProxyManager:
    def test_register_and_assign(self):
        pm = SwarmProxyManager(max_shards=5)
        pm.register_runner("runner-1")
        assert pm.assign_task("runner-1") is True

    def test_runner_cooldown_after_failures(self):
        pm = SwarmProxyManager(max_shards=5, cooldown_seconds=10)
        pm.register_runner("runner-1")
        pm.assign_task("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        runner = pm.runners["runner-1"]
        assert runner.status == RunnerStatus.COOLDOWN

    def test_get_available_runner_skips_cooldown(self):
        pm = SwarmProxyManager(max_shards=5, cooldown_seconds=9999)
        pm.register_runner("runner-1")
        pm.assign_task("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        # runner-1 is now in cooldown
        pm.register_runner("runner-2")
        available = pm.get_available_runner()
        assert available is not None
        assert available.runner_id == "runner-2"

    def test_health_summary(self):
        pm = SwarmProxyManager(max_shards=5)
        pm.register_runner("runner-1")
        pm.register_runner("runner-2")
        summary = pm.health_summary()
        assert summary["total_runners"] == 2
        assert summary["max_shards"] == 5

    def test_pacing_delay_in_range(self):
        pm = SwarmProxyManager()
        delay = pm.get_pacing_delay()
        assert 15.0 <= delay <= 45.0


class TestSwarmDispatcher:
    def test_plan_batches_distribution(self):
        d = SwarmDispatcher()
        batches = d.plan_batches(["a", "b", "c", "d", "e", "f"], shards=3)
        assert len(batches) == 3
        assert sum(len(b) for b in batches) == 6

    def test_dispatch_commands_format(self):
        d = SwarmDispatcher()
        cmds = d.generate_dispatch_commands("shoes", "US", runs=2)
        assert len(cmds) == 2
        assert "swarm_matrix.yml" in cmds[0]
        assert "shoes" in cmds[0]

    def test_runner_load_estimation(self):
        d = SwarmDispatcher()
        load = d.estimate_runner_load(runs=3, shards_per_run=5)
        assert load["total_runners"] == 15
        assert load["within_free_tier"] is True
EOF

# 7. Run swarm tests
echo "[SEED:2399] Running Phase 19 Swarm test suite..."
python -m pytest tests/integration/test_swarm.py -v --tb=short

# 8. Run full test suite
echo ""
echo "[SEED:2399] Running FULL test suite for final verification..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  ██████████████████████████████████████████████████████"
echo "  █                                                    █"
echo "  █   [SEED: 2399] MASTER ROADMAP COMPLETE            █"
echo "  █                                                    █"
echo "  █   Phase 0: Foundation & Contracts        ✅       █"
echo "  █   Phase 1: Ingestion Pipeline            ✅       █"
echo "  █   Phase 2: L1 + L2 Leak Detection        ✅       █"
echo "  █   Phase 3: L3 Site Audit                 ✅       █"
echo "  █   Phase 4: Platform Fingerprint          ✅       █"
echo "  █   Phase 5: Fix Forge                     ✅       █"
echo "  █   Phase 6: Outreach Bundle               ✅       █"
echo "  █   Phase 7: Distributed Ephemeral Swarm   ✅       █"
echo "  █   Phase 8: Feedback Loop                 ✅       █"
echo "  █   Phase 9: Hardening & Production        ✅       █"
echo "  █                                                    █"
echo "  █   Ad-Leak-Engine is FULLY OPERATIONAL.            █"
echo "  █                                                    █"
echo "  ██████████████████████████████████████████████████████"
echo "=========================================================="
echo ""
echo "  MASTER COMMANDS:"
echo "    ./scripts/ale scan <keyword> <country>    — Full pipeline"
echo "    ./scripts/ale feedback <id> \"<reply>\"     — Self-improvement"
echo "    ./scripts/ale test                        — Full test suite"
echo "    bash scripts/dispatch_swarm.sh <kw> <co>  — Deploy swarm"
echo ""
echo "  SWARM DEPLOYMENT (requires repo pushed to GitHub):"
echo "    git add -A && git commit -m '[SEED:2399] Complete system'"
echo "    git remote add origin <your-github-repo-url>"
echo "    git push -u origin master"
echo "    bash scripts/dispatch_swarm.sh shoes US 1"
echo "=========================================================="