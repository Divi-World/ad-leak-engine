#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 8: SCALE
# Field-mapping tuning + Distributed Ephemeral Swarm + persistence
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 8 BOOTSTRAP"
echo "=========================================================="

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ============================================================
# PART 1 — FIELD MAPPING TUNING (get REAL ads extracted)
# ============================================================

# ---------- 1a. Harden normalizer for real Ad Library fields ----------
cat << 'EOF' > src/ad_leak_engine/ingest/normalizer.py
"""Normalizes raw Meta Ad Library JSON into RawAd contract [SEED: 2399].

Tuned for real Ad Library field names: ad_archive_id, unix start_date,
snapshot{title,body,link_url}, page{id,name}.
"""
from datetime import datetime, timezone

from ..shared.schemas import RawAd


def normalize_meta_ad(raw: dict, country: str) -> RawAd:
    page_data = raw.get("page", {}) or {}
    snapshot = raw.get("snapshot", {}) or {}

    return RawAd(
        id=str(raw.get("id") or raw.get("ad_archive_id") or raw.get("ad_id") or "unknown"),
        page_id=str(page_data.get("id", "unknown")),
        page_name=page_data.get("name", "Unknown Page"),
        start_date=_parse_date(
            raw.get("creation_time") or raw.get("start_date") or raw.get("ad_delivery_start_time")
        ),
        media_type=_infer_media_type(raw, snapshot),
        title=raw.get("title") or snapshot.get("title"),
        body=raw.get("body") or snapshot.get("body"),
        cta=raw.get("cta_text") or snapshot.get("cta_text"),
        landing_url=snapshot.get("link_url") or raw.get("landing_url"),
        country=country,
        raw=raw,
    )


def _parse_date(val):
    """Handle ISO strings and unix timestamps."""
    if val is None:
        return datetime.now(timezone.utc)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _infer_media_type(raw: dict, snapshot: dict) -> str:
    mt = raw.get("media_type")
    if mt and str(mt).upper() in ("IMAGE", "VIDEO", "CAROUSEL", "DYNAMIC"):
        return str(mt).upper()
    if snapshot.get("videos") or snapshot.get("video"):
        return "VIDEO"
    if snapshot.get("cards") or snapshot.get("carousel"):
        return "CAROUSEL"
    return "IMAGE"
EOF

# ---------- 1b. Adaptive field mapper (multi-strategy extraction) ----------
cat << 'EOF' > src/ad_leak_engine/ingest/field_mapper.py
"""Adaptive field mapper for Meta Ad Library GraphQL responses [SEED: 2399].

Uses multiple extraction strategies so it survives Meta schema variation:
  Strategy 1: GraphQL Relay `nodes[]` arrays
  Strategy 2: any list of ad-like dicts
"""
from ..shared.schemas import RawAd
from .normalizer import normalize_meta_ad


class AdLibraryFieldMapper:
    AD_ID_KEYS = ["ad_archive_id", "id", "ad_id", "archive_id"]
    AD_HINT_KEYS = ["snapshot", "collation_count", "ad_delivery_start_time", "page"]

    def extract_ads(self, payload, country: str) -> list[RawAd]:
        ads = []
        seen = set()
        for node in self._iter_ad_nodes(payload):
            ad = self._node_to_ad(node, country)
            if ad and ad.id != "unknown" and ad.id not in seen:
                seen.add(ad.id)
                ads.append(ad)
        return ads

    def _iter_ad_nodes(self, payload):
        # Strategy 1: Relay nodes[] arrays
        for nodes_list in self._find_key_lists(payload, "nodes"):
            for node in nodes_list:
                if self._looks_like_ad(node):
                    yield node
        # Strategy 2: any list of ad-like dicts
        for lst in self._find_all_lists(payload):
            for item in lst:
                if self._looks_like_ad(item):
                    yield item

    def _looks_like_ad(self, node) -> bool:
        if not isinstance(node, dict):
            return False
        has_id = any(k in node for k in self.AD_ID_KEYS)
        has_hint = any(k in node for k in self.AD_HINT_KEYS)
        return has_id and has_hint

    def _find_key_lists(self, node, key):
        if isinstance(node, dict):
            if key in node and isinstance(node[key], list):
                yield node[key]
            for v in node.values():
                yield from self._find_key_lists(v, key)
        elif isinstance(node, list):
            for item in node:
                yield from self._find_key_lists(item, key)

    def _find_all_lists(self, node):
        if isinstance(node, dict):
            for v in node.values():
                yield from self._find_all_lists(v)
        elif isinstance(node, list):
            yield node
            for item in node:
                yield from self._find_all_lists(item)

    def _node_to_ad(self, node, country):
        try:
            return normalize_meta_ad(node, country)
        except Exception:
            return None
EOF

# ---------- 1c. Playwright source wired to field mapper + diagnostics ----------
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""REAL Meta Ad Library scraper via Playwright network interception [SEED: 2399].

Intercepts GraphQL/JSON responses, parses them with the adaptive field mapper.
Set debug_dir to dump raw payloads for field-mapping diagnostics.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from playwright.sync_api import sync_playwright

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from .field_mapper import AdLibraryFieldMapper

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")


class PlaywrightSource(AbstractAdSource):
    def __init__(self, debug_dir: str | None = None):
        self.debug_dir = debug_dir
        self.field_mapper = AdLibraryFieldMapper()

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        url = AD_LIBRARY_URL.format(country=country, query=query.replace(" ", "%20"))
        payloads = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(user_agent=DESKTOP_UA, viewport={"width": 1366, "height": 900})
                page = context.new_page()

                def on_response(response):
                    try:
                        u = response.url.lower()
                        if "graphql" in u or "adlibrary" in u or "search_ads" in u:
                            ct = response.headers.get("content-type", "")
                            if "json" in ct or "javascript" in ct:
                                payloads.append(response.json())
                    except Exception:
                        pass

                page.on("response", on_response)
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(7000)
                for _ in range(3):
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(2000)

                browser.close()
        except Exception:
            return

        if self.debug_dir:
            self._dump_payloads(payloads)

        seen = set()
        count = 0
        for payload in payloads:
            for ad in self.field_mapper.extract_ads(payload, country):
                if ad.id not in seen:
                    seen.add(ad.id)
                    yield ad
                    count += 1
                    if count >= max_results:
                        return

    def _dump_payloads(self, payloads):
        d = Path(self.debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        stamp = int(datetime.now(timezone.utc).timestamp())
        for i, p in enumerate(payloads):
            (d / f"payload_{stamp}_{i}.json").write_text(
                json.dumps(p, indent=2, default=str), encoding="utf-8"
            )

    def health_check(self) -> bool:
        return True
EOF

# ============================================================
# PART 2 — PERSISTENCE (swarm results land in SQLite)
# ============================================================

# ---------- 2a. ORM models ----------
cat << 'EOF' > src/ad_leak_engine/persistence/models.py
"""SQLModel ORM tables for Ad-Leak-Engine [SEED: 2399]."""
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow():
    return datetime.now(timezone.utc)


class AdRecord(SQLModel, table=True):
    ad_id: str = Field(primary_key=True)
    page_id: str = Field(index=True)
    page_name: str
    media_type: str
    landing_url: str | None = None
    country: str
    raw_json: str
    collected_at: datetime = Field(default_factory=_utcnow)
EOF

# ---------- 2b. Repository ----------
cat << 'EOF' > src/ad_leak_engine/persistence/repository.py
"""Ad persistence repository [SEED: 2399]."""
import json

from sqlmodel import Session

from ..shared.schemas import RawAd
from .db import engine
from .models import AdRecord


class AdRepository:
    def upsert_ads(self, ads: list[RawAd]) -> int:
        """Insert new ads, skip duplicates. Returns count inserted."""
        count = 0
        with Session(engine) as session:
            for ad in ads:
                if session.get(AdRecord, ad.id):
                    continue
                session.add(AdRecord(
                    ad_id=ad.id,
                    page_id=ad.page_id,
                    page_name=ad.page_name,
                    media_type=ad.media_type,
                    landing_url=ad.landing_url,
                    country=ad.country,
                    raw_json=json.dumps(ad.raw, default=str),
                ))
                count += 1
            session.commit()
        return count

    def count_ads(self) -> int:
        with Session(engine) as session:
            return len(session.query(AdRecord).all())
EOF

# ---------- 2c. Update db.py to register models ----------
cat << 'EOF' > src/ad_leak_engine/persistence/db.py
"""SQLite persistence layer via SQLModel for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import SQLModel, create_engine

DB_PATH = os.getenv("DB_PATH", "data/db/adleak.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    from . import models  # noqa: F401  register tables with SQLModel.metadata
    SQLModel.metadata.create_all(engine)
EOF

# ============================================================
# PART 3 — DISTRIBUTED EPHEMERAL SWARM
# ============================================================

# ---------- 3a. Swarm dispatcher ----------
cat << 'EOF' > src/ad_leak_engine/orchestrator/dispatcher.py
"""Swarm task distribution for the Distributed Ephemeral Swarm [SEED: 2399]."""


class SwarmDispatcher:
    """Plans batches and generates GitHub Actions dispatch commands."""

    def plan_batches(self, keywords: list[str], shards: int) -> list[list[str]]:
        """Distribute keywords across shards via round-robin."""
        if shards <= 0:
            raise ValueError("shards must be > 0")
        batches = [[] for _ in range(shards)]
        for i, kw in enumerate(keywords):
            batches[i % shards].append(kw)
        return batches

    def generate_dispatch_commands(self, keyword: str, country: str, runs: int = 1) -> list[str]:
        """Generate `gh workflow run` commands to trigger the swarm."""
        return [
            f'gh workflow run swarm_matrix.yml -f keyword="{keyword}" -f country="{country}"'
            for _ in range(runs)
        ]

    def estimate_runner_load(self, runs: int, shards_per_run: int = 5) -> dict:
        """Estimate GitHub Actions minute usage against the free tier."""
        total_runners = runs * shards_per_run
        minutes_per_runner = 6
        total_minutes = total_runners * minutes_per_runner
        return {
            "total_runners": total_runners,
            "estimated_minutes": total_minutes,
            "within_free_tier": total_minutes <= 2000,
        }
EOF

# ---------- 3b. Ephemeral swarm scrape runner ----------
cat << 'EOF' > scripts/swarm_scrape.py
"""Ephemeral swarm scrape runner [SEED: 2399].

Executes on a GitHub Actions runner (fresh IP, fresh browser). Collects ads
and writes them to output/swarm/ for artifact upload + later aggregation.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.ingest.playwright_source import PlaywrightSource


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--country", default="US")
    parser.add_argument("--max-results", type=int, default=50)
    parser.add_argument("--output-dir", default="output/swarm")
    args = parser.parse_args()

    source = PlaywrightSource()
    ads = list(source.search(args.keyword, args.country, args.max_results))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(datetime.now(timezone.utc).timestamp())
    out_file = out_dir / f"ads_{stamp}.json"
    out_file.write_text(
        json.dumps([ad.model_dump(mode="json") for ad in ads], indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[SEED:2399] Collected {len(ads)} ads for '{args.keyword}' -> {out_file}")


if __name__ == "__main__":
    main()
EOF

# ---------- 3c. Swarm result aggregator ----------
cat << 'EOF' > scripts/aggregate_swarm.py
"""Aggregate swarm results from output/swarm/ into SQLite [SEED: 2399]."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.shared.schemas import RawAd
from ad_leak_engine.persistence.db import init_db
from ad_leak_engine.persistence.repository import AdRepository


def main():
    swarm_dir = Path("output/swarm")
    if not swarm_dir.exists():
        print("[SEED:2399] No output/swarm directory found.")
        return

    all_ads = []
    seen = set()
    for f in sorted(swarm_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            for item in data:
                for key in ("impressions", "spend"):
                    if isinstance(item.get(key), list):
                        item[key] = tuple(item[key])
                ad = RawAd(**item)
                if ad.id not in seen:
                    seen.add(ad.id)
                    all_ads.append(ad)
        except Exception as e:
            print(f"[SEED:2399] Skipping {f.name}: {e}")

    init_db()
    repo = AdRepository()
    inserted = repo.upsert_ads(all_ads)
    print(f"[SEED:2399] Aggregated {len(all_ads)} unique ads; inserted {inserted} new into SQLite.")


if __name__ == "__main__":
    main()
EOF

# ---------- 3d. Diagnostic ingest (field-mapping tuner) ----------
cat << 'EOF' > scripts/debug_ingest.py
"""Diagnostic live fetch: dumps raw Ad Library payloads for field mapping [SEED: 2399]."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ad_leak_engine.ingest.playwright_source import PlaywrightSource


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else "shoes"
    country = sys.argv[2] if len(sys.argv) > 2 else "US"
    debug_dir = "data/debug/payloads"

    print(f"[SEED:2399] Live diagnostic fetch: keyword='{keyword}' country={country}")
    print(f"[SEED:2399] Dumping raw payloads to {debug_dir}/")

    source = PlaywrightSource(debug_dir=debug_dir)
    ads = list(source.search(keyword, country, max_results=20))

    print(f"[SEED:2399] Extracted {len(ads)} ads.")
    for ad in ads[:5]:
        print(f"  - {ad.id} | {ad.page_name} | {ad.media_type}")

    if not ads:
        print("[SEED:2399] No ads extracted. Inspect data/debug/payloads/*.json")
        print("[SEED:2399] to see Meta's live response structure and tune field_mapper.py.")


if __name__ == "__main__":
    main()
EOF

# ---------- 3e. Swarm dispatch shell trigger ----------
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

for i in $(seq 1 "$RUNS"); do
    gh workflow run swarm_matrix.yml -f keyword="$KEYWORD" -f country="$COUNTRY"
    echo "[SEED:2399] Dispatched swarm run $i for '$KEYWORD'."
    sleep 2
done
EOF
chmod +x scripts/dispatch_swarm.sh

# ---------- 3f. GitHub Actions: swarm matrix ----------
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

# ---------- 3g. GitHub Actions: nightly scan ----------
cat << 'EOF' > .github/workflows/nightly_scan.yml
name: Nightly Scan [SEED: 2399]

on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch:

jobs:
  nightly:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        keyword: ['shoes', 'skincare', 'fitness']
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

      - name: Scrape keyword
        run: |
          python scripts/swarm_scrape.py --keyword "${{ matrix.keyword }}" --country "US" --max-results 50

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: nightly-${{ github.run_id }}-${{ strategy.job-index }}
          path: output/swarm/
EOF

# ============================================================
# PART 4 — TESTS
# ============================================================

cat << 'EOF' > tests/unit/test_field_mapper.py
"""Tests for the adaptive Ad Library field mapper [SEED: 2399]."""
import pytest

from ad_leak_engine.ingest.field_mapper import AdLibraryFieldMapper

SAMPLE_PAYLOAD = {
    "data": {
        "ad_library_search": {
            "results": {
                "nodes": [
                    {
                        "ad_archive_id": "111",
                        "page": {"id": "p1", "name": "Store One"},
                        "start_date": 1700000000,
                        "snapshot": {"body": "Buy now", "title": "Sale", "link_url": "storeone.com"},
                    },
                    {
                        "ad_archive_id": "222",
                        "page": {"id": "p2", "name": "Store Two"},
                        "start_date": 1700000001,
                        "snapshot": {"body": "Shop now", "title": "Deal"},
                    },
                ]
            }
        }
    }
}


@pytest.fixture
def mapper():
    return AdLibraryFieldMapper()


def test_extracts_ads_from_nodes(mapper):
    ads = mapper.extract_ads(SAMPLE_PAYLOAD, "US")
    assert len(ads) == 2
    assert ads[0].id == "111"
    assert ads[0].page_name == "Store One"


def test_handles_empty_payload(mapper):
    assert mapper.extract_ads({}, "US") == []


def test_dedupes_by_id(mapper):
    node = SAMPLE_PAYLOAD["data"]["ad_library_search"]["results"]["nodes"][0]
    payload = {"nodes": [node, node, node]}
    ads = mapper.extract_ads(payload, "US")
    assert len(ads) == 1


def test_handles_unix_timestamp(mapper):
    ads = mapper.extract_ads(SAMPLE_PAYLOAD, "US")
    assert ads[0].start_date.year >= 2023


def test_ignores_non_ad_nodes(mapper):
    payload = {"nodes": [{"foo": "bar"}, {"baz": 1}]}
    assert mapper.extract_ads(payload, "US") == []


def test_normalizes_landing_url(mapper):
    ads = mapper.extract_ads(SAMPLE_PAYLOAD, "US")
    assert ads[0].landing_url == "https://storeone.com"
EOF

cat << 'EOF' > tests/unit/test_dispatcher.py
"""Tests for the swarm dispatcher [SEED: 2399]."""
import pytest

from ad_leak_engine.orchestrator.dispatcher import SwarmDispatcher


@pytest.fixture
def dispatcher():
    return SwarmDispatcher()


def test_plan_batches_round_robin(dispatcher):
    batches = dispatcher.plan_batches(["a", "b", "c", "d", "e"], shards=2)
    assert len(batches) == 2
    assert sum(len(b) for b in batches) == 5


def test_plan_batches_rejects_zero_shards(dispatcher):
    with pytest.raises(ValueError):
        dispatcher.plan_batches(["a"], shards=0)


def test_generate_dispatch_commands(dispatcher):
    cmds = dispatcher.generate_dispatch_commands("shoes", "US", runs=2)
    assert len(cmds) == 2
    assert "swarm_matrix.yml" in cmds[0]
    assert "shoes" in cmds[0]


def test_estimate_runner_load(dispatcher):
    load = dispatcher.estimate_runner_load(runs=2, shards_per_run=5)
    assert load["total_runners"] == 10
    assert load["estimated_minutes"] == 60
    assert load["within_free_tier"] is True
EOF

# ============================================================
# RUN OFFLINE TESTS
# ============================================================
echo "[SEED:2399] Running Phase 8 offline test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 8 COMPLETE"
echo "  Field mapping tuned. Swarm infrastructure built."
echo ""
echo "  NEXT — field-mapping diagnostic (proves real ad extraction):"
echo "    python scripts/debug_ingest.py \"your keyword\" US"
echo ""
echo "  NEXT — activate the swarm (requires repo pushed to GitHub):"
echo "    bash scripts/dispatch_swarm.sh \"keyword\" US 1"
echo "=========================================================="