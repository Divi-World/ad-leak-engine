#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 0: Foundation & Contracts
# Self-contained bootstrap for Git Bash on Windows.
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 0 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Detect Python (prefer 'python' on Windows) ----------
if command -v python &>/dev/null; then PYTHON=python
elif command -v python3 &>/dev/null; then PYTHON=python3
else echo "[SEED:2399] FATAL: Python not found"; exit 1; fi
echo "[SEED:2399] Using Python: $($PYTHON --version 2>&1)"

# ---------- 2. Git Init ----------
if [ ! -d ".git" ]; then git init -q && echo "[SEED:2399] Git repository initialized."; fi

# ---------- 3. Directory Structure ----------
echo "[SEED:2399] Creating directory structure..."
mkdir -p src/ad_leak_engine/{orchestrator/routes,ingest,leak_scan/l3_site,platform_fingerprint,self_heal,persistence,shared}
mkdir -p src/ad_leak_engine/fix_forge/{platforms,templates/{shopify,woocommerce,bigcommerce,custom}}
mkdir -p src/ad_leak_engine/outreach/templates
mkdir -p tests/{unit,integration,fixtures}
mkdir -p scripts data/{db,cache} logs output .github/workflows
for d in data/db data/cache logs output tests/fixtures; do touch "$d/.gitkeep"; done

# ---------- 4. .gitignore ----------
cat << 'EOF' > .gitignore
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/
env/
.env
.env.local
data/db/*
data/cache/*
logs/*
output/*
!data/db/.gitkeep
!data/cache/.gitkeep
!logs/.gitkeep
!output/.gitkeep
.vscode/
.idea/
*.swp
.DS_Store
.pytest_cache/
.coverage
htmlcov/
coverage.xml
playwright-report/
test-results/
EOF

# ---------- 5. README.md (minimal placeholder) ----------
cat << 'EOF' > README.md
# Ad-Leak-Engine [SEED: 2399]
Top 1 Global Ad Infrastructure Audit Engine.
Architecture: Distributed Ephemeral Swarm | Scale: Unlimited | Cost: 100% Free.
See project knowledge base for the full engineering contract.
EOF

# ---------- 6. pyproject.toml ----------
cat << 'EOF' > pyproject.toml
[project]
name = "ad-leak-engine"
version = "0.1.0"
description = "Top 1 Global Ad Infrastructure Audit Engine [SEED: 2399]"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.29.0",
    "sqlmodel>=0.0.16",
    "pydantic>=2.6.4",
    "pydantic-settings>=2.2.1",
    "python-dotenv>=1.0.1",
    "diskcache>=5.6.3",
    "jinja2>=3.1.3",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
scrape = [
    "curl-cffi>=0.6.2",
    "playwright>=1.42.0",
    "beautifulsoup4>=4.12.3",
    "lxml>=5.1.0",
]
test = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
EOF

# ---------- 7. pytest.ini ----------
cat << 'EOF' > pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short
markers =
    unit: unit tests (fast, no network)
    integration: integration tests (may use network)
EOF

# ---------- 8. .env.example and .env ----------
cat << 'EOF' > .env.example
SEED_NUMBER=2399
ENVIRONMENT=development
DB_PATH=data/db/adleak.db
CACHE_DIR=data/cache
LOG_DIR=logs
OUTPUT_DIR=output
LOG_LEVEL=INFO
EOF
cp .env.example .env

# ---------- 9. GitHub Actions CI ----------
cat << 'EOF' > .github/workflows/test.yml
name: Ad-Leak-Engine Test Suite [SEED: 2399]
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]"
      - name: Run unit tests
        run: pytest tests/unit/ -v --tb=short
EOF

# ---------- 10. Package __init__ ----------
cat << 'EOF' > src/ad_leak_engine/__init__.py
"""Ad-Leak-Engine [SEED: 2399] — Top 1 Global Ad Infrastructure Audit Engine."""
__version__ = "0.1.0"
SEED = 2399
EOF
for d in orchestrator orchestrator/routes ingest leak_scan leak_scan/l3_site \
         platform_fingerprint fix_forge fix_forge/platforms self_heal \
         outreach persistence shared; do
  touch "src/ad_leak_engine/$d/__init__.py"
done

# ---------- 11. shared/constants.py ----------
cat << 'EOF' > src/ad_leak_engine/shared/constants.py
"""Global constants for Ad-Leak-Engine [SEED: 2399]."""
SEED_NUMBER = 2399
ENGINE_NAME = "Ad-Leak-Engine"
ENGINE_VERSION = "0.1.0"

CREATIVE_FATIGUE_DAYS = 30
MIN_AB_VARIATION_ADS = 3
SPEND_WITHOUT_TESTING_USD = 1000.0
SPEND_WITHOUT_TESTING_MIN_ADS = 5

LCP_MOBILE_THRESHOLD_MS = 2500
TTFB_THRESHOLD_MS = 800
TAP_TARGET_MIN_PX = 48
CHECKOUT_MAX_STEPS = 4
PIXEL_BLOCKING_SCRIPTS_MAX = 5

HIGH_CONFIDENCE_MIN_SIGNALS = 2
LOW_CONFIDENCE_THRESHOLD = 0.5

CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
CIRCUIT_BREAKER_RECOVERY_SECONDS = 300
PROXY_COOLDOWN_SECONDS = 600
EOF

# ---------- 12. shared/exceptions.py ----------
cat << 'EOF' > src/ad_leak_engine/shared/exceptions.py
"""Error taxonomy for Ad-Leak-Engine [SEED: 2399]."""


class AdLeakEngineError(Exception):
    """Base exception for all engine errors."""


class SchemaDriftError(AdLeakEngineError):
    """GraphQL response keys changed unexpectedly."""


class RateLimitError(AdLeakEngineError):
    """HTTP 429 - too many requests."""


class BlockedError(AdLeakEngineError):
    """HTTP 403 after session handshake - access blocked."""


class ProxyDeadError(AdLeakEngineError):
    """Proxy failed repeated health checks."""


class PlatformAmbiguousError(AdLeakEngineError):
    """Fingerprint confidence too low for deterministic codegen."""


class CrawlerTimeoutError(AdLeakEngineError):
    """Page load exceeded the time budget."""


class CAPTCHAError(AdLeakEngineError):
    """CAPTCHA challenge detected in response."""


class EmptyResponseError(AdLeakEngineError):
    """Valid HTTP response but no usable ad data."""
EOF

# ---------- 13. shared/schemas.py ----------
cat << 'EOF' > src/ad_leak_engine/shared/schemas.py
"""Data contracts for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _short_id(prefix: str = "") -> str:
    seed = f"{prefix}{datetime.now(timezone.utc).isoformat()}"
    return hashlib.md5(seed.encode()).hexdigest()[:12]


class RawAd(BaseModel):
    """Canonical ad object flowing from Ingest -> Leak Scan."""
    id: str
    page_id: str
    page_name: str
    start_date: datetime
    end_date: datetime | None = None
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"
    media_type: Literal["IMAGE", "VIDEO", "CAROUSEL", "DYNAMIC", "UNKNOWN"]
    title: str | None = None
    body: str | None = None
    cta: str | None = None
    landing_url: str | None = None
    impressions: tuple[int, int] | None = None
    spend: tuple[float, float] | None = None
    platforms: list[str] = Field(default_factory=list)
    country: str = "US"
    raw: dict = Field(default_factory=dict)

    @field_validator("landing_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class Page(BaseModel):
    """Page-level aggregate containing all ads for a business."""
    id: str
    name: str
    url: str | None = None
    ads: list[RawAd] = Field(default_factory=list)
    first_seen: datetime
    last_scanned: datetime | None = None
    fingerprint: str | None = None

    @property
    def active_ads(self) -> list[RawAd]:
        return [ad for ad in self.ads if ad.status == "ACTIVE"]

    @property
    def total_estimated_spend(self) -> tuple[float, float]:
        lower = sum(ad.spend[0] for ad in self.active_ads if ad.spend)
        upper = sum(ad.spend[1] for ad in self.active_ads if ad.spend)
        return (lower, upper)


class Leak(BaseModel):
    """A detected revenue leak with evidence and severity."""
    id: str = Field(default_factory=lambda: _short_id("leak_"))
    page_id: str
    tier: Literal["L1", "L2", "L3"]
    signal: str
    severity: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    evidence: dict = Field(default_factory=dict)
    recommendation: str
    revenue_impact: str | None = None
    detected_at: datetime = Field(default_factory=_utcnow)


class Fix(BaseModel):
    """Platform-specific implementation guide with executable code."""
    id: str = Field(default_factory=lambda: _short_id("fix_"))
    leak_id: str
    platform: Literal["shopify", "woocommerce", "bigcommerce", "custom"]
    platform_confidence: float
    markdown_guide: str
    code_blocks: list[dict] = Field(default_factory=list)
    verification_steps: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    expected_outcome: str
    confidence: float = Field(ge=0.0, le=1.0)


class OutreachPack(BaseModel):
    """Complete client-facing package."""
    page_id: str
    page_name: str
    prospect_url: str | None = None
    teardown_markdown: str
    executive_summary: str
    leaks_found: list[Leak] = Field(default_factory=list)
    fixes: list[Fix] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    message_text: str
    estimated_recovery: str
    generated_at: datetime = Field(default_factory=_utcnow)
EOF

# ---------- 14. shared/interfaces.py ----------
cat << 'EOF' > src/ad_leak_engine/shared/interfaces.py
"""Stage interface contracts for Ad-Leak-Engine [SEED: 2399]."""
from abc import ABC, abstractmethod
from typing import Iterator

from .schemas import Fix, Leak, OutreachPack, Page, RawAd


class AbstractAdSource(ABC):
    """Ingest stage: collects ads from Meta Ad Library."""

    @abstractmethod
    def search(self, query: str, country: str, max_results: int = 100) -> Iterator[RawAd]:
        """Search Ad Library and yield normalized ads."""

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the source is operational."""


class AbstractLeakScanner(ABC):
    """Leak Scan stage: detects revenue leaks at a given tier."""

    @abstractmethod
    def scan(self, page: Page) -> list[Leak]:
        """Analyze a page and return all detected leaks."""

    @abstractmethod
    def tier(self) -> str:
        """Return which tier this scanner handles (L1/L2/L3)."""


class AbstractPlatformDetector(ABC):
    """Fingerprint stage: identifies the e-commerce platform."""

    @abstractmethod
    def detect(self, url: str, html: str | None = None, headers: dict | None = None) -> tuple[str, float]:
        """Return (platform_name, confidence_score)."""


class AbstractFixGenerator(ABC):
    """Fix Forge stage: generates platform-specific solutions."""

    @abstractmethod
    def generate(self, leak: Leak, platform: str, confidence: float) -> Fix:
        """Generate an executable fix for a detected leak."""

    @abstractmethod
    def supported_platforms(self) -> list[str]:
        """Return the list of platforms this generator handles."""


class AbstractOutreachBuilder(ABC):
    """Outreach stage: assembles client-facing packages."""

    @abstractmethod
    def build(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> OutreachPack:
        """Assemble a complete outreach bundle."""
EOF

# ---------- 15. persistence/db.py ----------
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
    """Create all tables."""
    SQLModel.metadata.create_all(engine)
EOF

# ---------- 16. orchestrator/app.py ----------
cat << 'EOF' > src/ad_leak_engine/orchestrator/app.py
"""FastAPI orchestrator for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI

from ..shared.constants import ENGINE_NAME, ENGINE_VERSION, SEED_NUMBER

app = FastAPI(
    title=ENGINE_NAME,
    version=ENGINE_VERSION,
    description=f"Top 1 Global Ad Infrastructure Audit Engine [SEED: {SEED_NUMBER}]",
)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Must return SEED: 2399."""
    return {
        "status": "healthy",
        "engine": ENGINE_NAME,
        "seed": SEED_NUMBER,
        "version": ENGINE_VERSION,
        "phase": "0-foundation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
EOF

# ---------- 17. tests/conftest.py ----------
cat << 'EOF' > tests/conftest.py
"""Shared pytest fixtures for Ad-Leak-Engine [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.shared.schemas import RawAd


@pytest.fixture
def sample_ad() -> RawAd:
    return RawAd(
        id="ad_001",
        page_id="page_001",
        page_name="Test Commerce",
        start_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
        media_type="IMAGE",
        title="Buy Now",
        landing_url="example.com/shop",
        spend=(100.0, 500.0),
        country="US",
    )
EOF

# ---------- 18. tests/unit/test_schemas.py ----------
cat << 'EOF' > tests/unit/test_schemas.py
"""Contract validation tests for [SEED: 2399] data schemas."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ad_leak_engine.shared.schemas import Fix, Leak, OutreachPack, Page, RawAd


def _ad(**overrides) -> RawAd:
    base = dict(
        id="ad_1",
        page_id="page_1",
        page_name="Test Page",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        media_type="IMAGE",
    )
    base.update(overrides)
    return RawAd(**base)


def test_raw_ad_minimal_defaults():
    ad = _ad()
    assert ad.status == "ACTIVE"
    assert ad.country == "US"
    assert ad.raw == {}
    assert ad.platforms == []


def test_raw_ad_url_normalization():
    ad = _ad(landing_url="example.com/landing")
    assert ad.landing_url == "https://example.com/landing"


def test_raw_ad_url_preserves_https():
    ad = _ad(landing_url="https://example.com/x")
    assert ad.landing_url == "https://example.com/x"


def test_raw_ad_rejects_bad_media_type():
    with pytest.raises(ValidationError):
        _ad(media_type="HOLOGRAM")


def test_page_active_ads_filter():
    a1 = _ad(id="a1", status="ACTIVE")
    a2 = _ad(id="a2", status="INACTIVE")
    page = Page(id="page_1", name="Test", ads=[a1, a2],
                first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert len(page.active_ads) == 1
    assert page.active_ads[0].id == "a1"


def test_page_total_estimated_spend():
    a1 = _ad(id="a1", spend=(100.0, 200.0))
    a2 = _ad(id="a2", spend=(50.0, 150.0))
    page = Page(id="page_1", name="Test", ads=[a1, a2],
                first_seen=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert page.total_estimated_spend == (150.0, 350.0)


def test_leak_severity_bounds():
    with pytest.raises(ValidationError):
        Leak(page_id="p", tier="L1", signal="x", severity=1.5, recommendation="r")


def test_leak_auto_id():
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing",
                severity=0.9, recommendation="Install pixel")
    assert leak.id
    assert leak.confidence == 0.8


def test_fix_round_trip():
    fix = Fix(leak_id="leak_1", platform="shopify", platform_confidence=0.95,
              markdown_guide="# Fix", expected_outcome="Pixel fires", confidence=0.9)
    assert fix.platform == "shopify"
    assert fix.code_blocks == []


def test_outreach_pack_structure(sample_ad):
    leak = Leak(page_id="page_1", tier="L1", signal="creative_fatigue",
                severity=0.8, recommendation="Refresh creative")
    pack = OutreachPack(page_id="page_1", page_name="Test",
                        teardown_markdown="# Teardown",
                        executive_summary="You are leaking money.",
                        leaks_found=[leak], message_text="Hi, found a leak.",
                        estimated_recovery="$1,500/month")
    assert len(pack.leaks_found) == 1
    assert pack.estimated_recovery == "$1,500/month"
EOF

# ---------- 19. Virtual env + install ----------
echo "[SEED:2399] Creating virtual environment..."
$PYTHON -m venv .venv
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
fi

echo "[SEED:2399] Upgrading pip..."
python -m pip install --upgrade pip -q

echo "[SEED:2399] Installing Phase 0 dependencies (core + test)..."
python -m pip install -e ".[test]" -q

# ---------- 20. Init DB ----------
echo "[SEED:2399] Initializing SQLite database..."
python -c "from ad_leak_engine.persistence.db import init_db; init_db()"

# ---------- 21. Run tests ----------
echo "[SEED:2399] Running Phase 0 test suite..."
python -m pytest tests/unit/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 0 COMPLETE"
echo "  Foundation built. Contracts frozen. Tests executed."
echo "=========================================================="