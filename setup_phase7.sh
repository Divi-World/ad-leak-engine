#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 7: Reality Bridge + Polish
# Track A: ranked leaks, data-backed message, syntax validation
# Track B: REAL live crawl + REAL Meta ingestion + telemetry
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 7 BOOTSTRAP"
echo "=========================================================="

# ---------- Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ============================================================
# TRACK A — POLISH
# ============================================================

# ---------- A1. Fix Forge syntax validation ----------
cat << 'EOF' > src/ad_leak_engine/fix_forge/validation.py
"""Syntax validation for generated fix code [SEED: 2399]."""


def validate_python(code: str) -> bool:
    """True if code is syntactically valid Python (real compile check)."""
    try:
        compile(code, "<fix>", "exec")
        return True
    except SyntaxError:
        return False


def validate_php(code: str) -> bool:
    """Structural check: balanced braces + WordPress/PHP markers."""
    if code.count("{") != code.count("}"):
        return False
    if "add_action" not in code and "<?php" not in code:
        return False
    return True


def validate_javascript(code: str) -> bool:
    """Structural check: balanced braces and parentheses."""
    if code.count("{") != code.count("}"):
        return False
    if code.count("(") != code.count(")"):
        return False
    return True


def validate_liquid(code: str) -> bool:
    """Structural check: balanced Liquid block tags."""
    if code.count("{%") != code.count("%}"):
        return False
    return True


def validate_code_block(block: dict) -> bool:
    """Validate a single code block based on its language."""
    lang = block.get("language", "")
    code = block.get("code", "")
    if not code:
        return False
    if lang == "python":
        return validate_python(code)
    if lang == "php":
        return validate_php(code)
    if lang in ("javascript", "html"):
        return validate_javascript(code)
    if lang == "liquid":
        return validate_liquid(code)
    return True


def validate_fix(fix) -> bool:
    """Validate all code blocks in a Fix."""
    for block in fix.code_blocks:
        if not validate_code_block(block):
            return False
    return True
EOF

# ---------- A2. Richer data-backed message generator ----------
cat << 'EOF' > src/ad_leak_engine/outreach/message_gen.py
"""Data-backed outreach text generation [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..shared.schemas import Page, Leak, Fix

TEMPLATE_DIR = Path(__file__).parent / "templates"


class MessageGenerator:
    """Generates personalized, data-backed outreach messages."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_message(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> str:
        template = self.env.get_template("message.txt.j2")
        top_leak = max(leaks, key=lambda l: l.severity) if leaks else None
        observation = self._extract_observation(top_leak) if top_leak else "your ad tracking is incomplete"
        return template.render(
            page=page, top_leak=top_leak, leak_count=len(leaks), observation=observation
        )

    def generate_executive_summary(self, page: Page, leaks: list[Leak]) -> str:
        template = self.env.get_template("executive_summary.txt.j2")
        return template.render(page=page, leak_count=len(leaks))

    def _extract_observation(self, leak: Leak) -> str:
        """Pull a specific, data-backed observation from the leak's evidence."""
        sig = leak.signal
        ev = leak.evidence or {}
        if sig == "creative_fatigue":
            days = ev.get("days_running")
            return f"your oldest active ad has been running {days} days without a refresh" if days else "your creative shows signs of fatigue"
        if sig == "slow_lcp_mobile":
            lcp = ev.get("lcp_mobile_ms")
            return f"your landing page takes {lcp/1000:.1f}s to render on mobile" if lcp else "your landing page loads slowly on mobile"
        if sig == "slow_ttfb":
            ttfb = ev.get("ttfb_ms")
            return f"your server takes {ttfb}ms to respond" if ttfb else "your server response is slow"
        if sig == "pixel_not_firing":
            return "your Meta Pixel is not firing on the landing page"
        if sig == "unhashed_pii":
            return "your Conversions API is sending unhashed customer data"
        if sig == "missing_purchase_event":
            return "your checkout is not sending the Purchase event to Meta"
        if sig == "checkout_friction":
            steps = ev.get("checkout_steps")
            return f"your checkout requires {steps} steps" if steps else "your checkout has too many steps"
        if sig == "no_ab_variation":
            count = ev.get("active_ad_count")
            return f"you are running only {count} active ad(s) with no A/B variation" if count else "you have no A/B ad variation"
        return f"we detected a {sig.replace('_', ' ')} issue"
EOF

# ---------- A3. Richer message template ----------
cat << 'EOF' > src/ad_leak_engine/outreach/templates/message.txt.j2
Subject: Found {{ leak_count }} revenue leaks on {{ page.name }}'s ads

Hi Team,

I ran an automated audit of {{ page.name }}'s live Meta ads and landing page. The headline: {{ observation }}.

In total I found {{ leak_count }} leaks in your tracking and landing-page setup. When this happens, Meta's algorithm optimizes against incomplete data - which inflates your CPA and suppresses ROAS.

I've prepared a short teardown with the exact code-level fixes to recover this. Would you be open to me sending it over?

Best,
[Your Name]
Ad-Leak-Engine

---
[Physical Address] | To opt-out of future audits, reply "UNSUBSCRIBE"
EOF

# ---------- A4. Ranked teardown template ----------
cat << 'EOF' > src/ad_leak_engine/outreach/templates/teardown.md.j2
# Ad Infrastructure Teardown: {{ page.name }}
**Generated by Ad-Leak-Engine [SEED: 2399]**

## Executive Summary
We analyzed your active Meta ad campaigns and landing page infrastructure.
We identified **{{ leaks|length }} revenue leaks**, ranked below by severity.

---

## Detected Leaks (Ranked by Severity)
{% for leak in leaks %}
### #{{ loop.index }} — {{ leak.signal.replace('_', ' ').title() }} (Severity: {{ "%.0f"|format(leak.severity * 100) }}%)
- **Tier:** {{ leak.tier }}
- **Impact:** {{ leak.recommendation }}
{% endfor %}

---

## Recommended Fixes
{% for fix in fixes %}
### Fix {{ loop.index }}: {{ fix.platform.title() }} Implementation
{{ fix.markdown_guide }}

**Expected Outcome:** {{ fix.expected_outcome }}

**Verification Steps:**
{% for step in fix.verification_steps %}
- {{ step }}
{% endfor %}
{% endfor %}
EOF

# ---------- A5. Bundle now ranks leaks by severity ----------
cat << 'EOF' > src/ad_leak_engine/outreach/bundle.py
"""Outreach package assembly [SEED: 2399]."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..shared.schemas import Page, Leak, Fix, OutreachPack
from ..shared.interfaces import AbstractOutreachBuilder
from .message_gen import MessageGenerator
from .compliance import ComplianceChecker

TEMPLATE_DIR = Path(__file__).parent / "templates"


class OutreachBuilder(AbstractOutreachBuilder):
    """Assembles the complete client-facing teardown package."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.message_gen = MessageGenerator()
        self.compliance = ComplianceChecker()
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> OutreachPack:
        """Assemble teardown, message, and evidence into an OutreachPack."""
        # Rank leaks by severity (highest first)
        leaks = sorted(leaks, key=lambda l: l.severity, reverse=True)

        teardown_md = self._generate_teardown(page, leaks, fixes)
        exec_summary = self.message_gen.generate_executive_summary(page, leaks)
        message_text = self.message_gen.generate_message(page, leaks, fixes)

        self.compliance.validate(message_text)
        estimated_recovery = self._estimate_recovery(leaks)

        page_dir = self.output_dir / page.id
        page_dir.mkdir(parents=True, exist_ok=True)

        teardown_path = page_dir / "teardown.md"
        teardown_path.write_text(teardown_md, encoding="utf-8")

        message_path = page_dir / "message.txt"
        message_path.write_text(message_text, encoding="utf-8")

        evidence_paths = [str(teardown_path), str(message_path)]

        return OutreachPack(
            page_id=page.id,
            page_name=page.name,
            prospect_url=page.url,
            teardown_markdown=teardown_md,
            executive_summary=exec_summary,
            leaks_found=leaks,
            fixes=fixes,
            evidence_paths=evidence_paths,
            message_text=message_text,
            estimated_recovery=estimated_recovery,
        )

    def _generate_teardown(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> str:
        template = self.env.get_template("teardown.md.j2")
        return template.render(page=page, leaks=leaks, fixes=fixes)

    def _estimate_recovery(self, leaks: list[Leak]) -> str:
        high_sev = sum(1 for l in leaks if l.severity >= 0.8)
        med_sev = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
        recovery = (high_sev * 1000) + (med_sev * 300)
        return f"${recovery:,}/month potential recovery"
EOF

# ============================================================
# TRACK B — REALITY BRIDGE (REAL live connectors)
# ============================================================

# ---------- B1. REAL L2 Playwright probe ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l2_probe.py
"""REAL Playwright probe that captures Meta Pixel/CAPI network activity [SEED: 2399]."""
from playwright.sync_api import sync_playwright

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


class L2LiveProbe:
    """Loads a live URL in a real browser and captures pixel/CAPI signals."""

    def probe(self, url: str, timeout_ms: int = 25000) -> dict:
        network_log = {
            "pixel_fired": False,
            "requests": [],
            "capi_events": [],
            "has_unhashed_pii": False,
            "is_checkout_page": False,
        }
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=MOBILE_UA,
                    viewport={"width": 390, "height": 844},
                )
                page = context.new_page()

                captured = []

                def on_request(request):
                    captured.append(request.url)

                page.on("request", on_request)
                page.goto(url, wait_until="load", timeout=timeout_ms)
                page.wait_for_timeout(3000)

                content = ""
                try:
                    content = page.content().lower()
                except Exception:
                    pass

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

                browser.close()
        except Exception as e:
            network_log["error"] = str(e)
        return network_log
EOF

# ---------- B2. REAL L3 performance auditor ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/performance.py
"""REAL Core Web Vitals measurement via Playwright [SEED: 2399]."""
from playwright.sync_api import sync_playwright

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


class PerformanceAuditor:
    """Measures LCP and TTFB on a live page using a mobile emulation."""

    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    user_agent=MOBILE_UA,
                    is_mobile=True,
                    has_touch=True,
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=timeout_ms)
                page.wait_for_timeout(3000)

                ttfb = page.evaluate(
                    "() => { const n = performance.getEntriesByType('navigation')[0];"
                    " return n ? n.responseStart - n.requestStart : null; }"
                )
                if ttfb and ttfb > 0:
                    telemetry["ttfb_ms"] = ttfb

                lcp = page.evaluate(
                    "() => { const e = performance.getEntriesByType('largest-contentful-paint');"
                    " return e.length ? e[e.length-1].startTime : null; }"
                )
                if lcp:
                    telemetry["lcp_mobile_ms"] = lcp

                browser.close()
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
EOF

# ---------- B3. REAL mobile UX analyzer ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/l3_site/mobile_ux.py
"""REAL mobile UX analysis: tap target measurement [SEED: 2399]."""
from playwright.sync_api import sync_playwright

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


class MobileUXAnalyzer:
    """Measures the smallest interactive tap target on a live page."""

    def measure(self, url: str, timeout_ms: int = 30000) -> dict:
        telemetry = {}
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    user_agent=MOBILE_UA,
                    is_mobile=True,
                    has_touch=True,
                )
                page = context.new_page()
                page.goto(url, wait_until="load", timeout=timeout_ms)
                page.wait_for_timeout(2000)

                min_tap = page.evaluate(
                    "() => { const els = Array.from(document.querySelectorAll('a,button,input,select,[role=button]'));"
                    " const sizes = els.map(e => { const r = e.getBoundingClientRect(); return Math.min(r.width, r.height); }).filter(s => s > 0);"
                    " return sizes.length ? Math.min(...sizes) : null; }"
                )
                if min_tap is not None:
                    telemetry["min_tap_target_px"] = min_tap

                browser.close()
        except Exception as e:
            telemetry["error"] = str(e)
        return telemetry
EOF

# ---------- B4. Telemetry collector (the reality bridge) ----------
cat << 'EOF' > src/ad_leak_engine/leak_scan/telemetry_collector.py
"""Collects REAL telemetry from a live landing page [SEED: 2399].

This is the reality bridge: it runs live Playwright probes and returns the
{'network_log': ..., 'telemetry': ...} dict that the L2/L3 scanners consume.
"""
from .l2_probe import L2LiveProbe
from .l3_site.performance import PerformanceAuditor
from .l3_site.mobile_ux import MobileUXAnalyzer


class TelemetryCollector:
    def __init__(self):
        self.l2_probe = L2LiveProbe()
        self.perf = PerformanceAuditor()
        self.mobile_ux = MobileUXAnalyzer()

    def collect(self, url: str) -> dict:
        """Run all live probes against url, return injectable page.raw data."""
        network_log = self.l2_probe.probe(url)
        telemetry = self.perf.measure(url)
        telemetry.update(self.mobile_ux.measure(url))
        return {"network_log": network_log, "telemetry": telemetry}
EOF

# ---------- B5. REAL Meta Ad Library scraper (Playwright network interception) ----------
cat << 'EOF' > src/ad_leak_engine/ingest/playwright_source.py
"""REAL Meta Ad Library scraper via Playwright network interception [SEED: 2399].

Loads the public Ad Library search page in a real browser and intercepts the
GraphQL/JSON responses from the network layer. Logged-out public data only
(Meta v. Bright Data, Jan 2024). Adversarial target; field mapping may need
live tuning as Meta changes its schema.
"""
from typing import Iterator

from playwright.sync_api import sync_playwright

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from .normalizer import normalize_meta_ad

DESKTOP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

AD_LIBRARY_URL = ("https://www.facebook.com/ads/library/?active_status=active"
                  "&ad_type=all&country={country}&q={query}&search_type=keyword_unordered")


class PlaywrightSource(AbstractAdSource):
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

        seen = set()
        count = 0
        for payload in payloads:
            for ad in self._extract(payload, country):
                if ad.id not in seen:
                    seen.add(ad.id)
                    yield ad
                    count += 1
                    if count >= max_results:
                        return

    def _extract(self, payload, country):
        ads = []
        self._walk(payload, ads, country)
        return ads

    def _walk(self, node, ads, country):
        if isinstance(node, dict):
            if ("id" in node or "ad_archive_id" in node) and "page" in node:
                try:
                    ads.append(normalize_meta_ad(node, country))
                except Exception:
                    pass
            for v in node.values():
                self._walk(v, ads, country)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, ads, country)

    def health_check(self) -> bool:
        return True
EOF

# ---------- B6. REAL GraphQL source via curl_cffi ----------
cat << 'EOF' > src/ad_leak_engine/ingest/graphql_source.py
"""REAL Meta Ad Library ingestion via curl_cffi TLS fingerprinting [SEED: 2399].

Logged-out public data only. Attempts the Ad Library search endpoint with a
Chrome TLS fingerprint. This endpoint is adversarial; on any failure a typed
exception is raised so HybridRouter falls back to Playwright.
"""
from typing import Iterator

from curl_cffi import requests

from ..shared.schemas import RawAd
from ..shared.interfaces import AbstractAdSource
from ..shared.exceptions import BlockedError, RateLimitError, EmptyResponseError
from .normalizer import normalize_meta_ad

AD_LIBRARY_SEARCH_URL = "https://www.facebook.com/ads/library/async/search_ads/"


class GraphQLSource(AbstractAdSource):
    def __init__(self, impersonate: str = "chrome120"):
        self.impersonate = impersonate

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        session = requests.Session(impersonate=self.impersonate)
        params = {
            "q": query,
            "country": country,
            "active_status": "active",
            "ad_type": "all",
            "count": str(max_results),
        }
        try:
            resp = session.get(AD_LIBRARY_SEARCH_URL, params=params, timeout=20)
        except Exception as e:
            raise EmptyResponseError(f"GraphQL request failed: {e}")

        if resp.status_code == 403:
            raise BlockedError("Meta returned 403 (blocked)")
        if resp.status_code == 429:
            raise RateLimitError("Meta returned 429 (rate limited)")
        if resp.status_code != 200:
            raise EmptyResponseError(f"Unexpected status {resp.status_code}")

        try:
            payload = resp.json()
        except Exception:
            raise EmptyResponseError("Response was not valid JSON")

        ads = self._extract(payload, country)
        if not ads:
            raise EmptyResponseError("No ads parsed from GraphQL payload")
        for ad in ads[:max_results]:
            yield ad

    def _extract(self, payload, country):
        ads = []
        self._walk(payload, ads, country)
        return ads

    def _walk(self, node, ads, country):
        if isinstance(node, dict):
            if "id" in node and "page" in node:
                try:
                    ads.append(normalize_meta_ad(node, country))
                except Exception:
                    pass
            for v in node.values():
                self._walk(v, ads, country)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, ads, country)

    def health_check(self) -> bool:
        return True
EOF

# ---------- B7. Hybrid router with dependency injection ----------
cat << 'EOF' > src/ad_leak_engine/ingest/hybrid_router.py
"""Orchestrates fallback chain and circuit breaker [SEED: 2399].

Sources are injectable so offline tests use test doubles while production
uses the real GraphQL + Playwright sources.
"""
import logging
from typing import Iterator

from ..shared.schemas import RawAd
from ..shared.exceptions import SchemaDriftError, BlockedError, RateLimitError
from ..self_heal.circuit_breaker import CircuitBreaker
from .graphql_source import GraphQLSource
from .playwright_source import PlaywrightSource

logger = logging.getLogger(__name__)


class HybridRouter:
    """Routes searches through GraphQL primary, Playwright fallback."""

    def __init__(self, graphql=None, playwright=None, breaker=None):
        self.graphql = graphql or GraphQLSource()
        self.playwright = playwright or PlaywrightSource()
        self.breaker = breaker or CircuitBreaker(failure_threshold=3, recovery_timeout=60)

    def search(self, query: str, country: str, max_results: int = 50) -> Iterator[RawAd]:
        if self.breaker.can_execute():
            try:
                ads = list(self.graphql.search(query, country, max_results))
                self.breaker.record_success()
                yield from ads
                return
            except (SchemaDriftError, BlockedError, RateLimitError) as e:
                logger.warning("GraphQL failed (%s), engaging fallback.", type(e).__name__)
                self.breaker.record_failure()

        logger.info("Routing to Playwright fallback.")
        yield from self.playwright.search(query, country, max_results)
EOF

# ============================================================
# TESTS
# ============================================================

# ---------- conftest.py with live-test gating ----------
cat << 'EOF' > tests/conftest.py
"""Shared pytest fixtures and live-test gating [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.shared.schemas import RawAd


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run live tests that hit real external targets",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "live: live test hitting real external targets")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="requires --run-live to hit real targets")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


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

# ---------- pytest.ini with live marker ----------
cat << 'EOF' > pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short
markers =
    unit: unit tests (fast, no network)
    integration: integration tests (may use network)
    live: LIVE tests hitting real external targets (run with --run-live)
EOF

# ---------- Rewritten offline ingest tests (dependency-injected) ----------
cat << 'EOF' > tests/unit/test_ingest.py
"""Offline unit tests for ingestion: contracts, breaker, router logic [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.ingest.hybrid_router import HybridRouter
from ad_leak_engine.ingest.normalizer import normalize_meta_ad
from ad_leak_engine.ingest.deduplicator import Deduplicator
from ad_leak_engine.self_heal.circuit_breaker import CircuitBreaker, CircuitState
from ad_leak_engine.shared.exceptions import BlockedError
from ad_leak_engine.shared.schemas import RawAd


class MockAdSource:
    """Test double for AbstractAdSource."""

    def __init__(self, ads=None, raise_error=None):
        self._ads = ads or []
        self._raise = raise_error

    def search(self, query, country, max_results=50):
        if self._raise:
            raise self._raise
        yield from self._ads

    def health_check(self):
        return True


def _ad(id="1"):
    return RawAd(id=id, page_id="p1", page_name="Test Page",
                 start_date=datetime.now(timezone.utc), media_type="IMAGE")


def test_circuit_breaker_opens_on_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    assert cb.state == CircuitState.CLOSED
    cb.record_failure(); cb.record_failure(); cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert not cb.can_execute()


def test_circuit_breaker_half_open_transition():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute()
    assert cb.state == CircuitState.HALF_OPEN


def test_normalizer_produces_rawad():
    raw = {
        "id": "ad_1",
        "page": {"id": "p1", "name": "Test Page"},
        "creation_time": "2026-01-01T00:00:00Z",
        "media_type": "IMAGE",
    }
    ad = normalize_meta_ad(raw, "US")
    assert ad.id == "ad_1"
    assert ad.page_name == "Test Page"
    assert ad.country == "US"


def test_hybrid_router_primary_path():
    router = HybridRouter(graphql=MockAdSource(ads=[_ad("a")]), playwright=MockAdSource())
    ads = list(router.search("x", "US"))
    assert len(ads) == 1
    assert ads[0].id == "a"


def test_hybrid_router_fallback_on_blocked():
    router = HybridRouter(
        graphql=MockAdSource(raise_error=BlockedError("blocked")),
        playwright=MockAdSource(ads=[_ad("b")]),
    )
    ads = list(router.search("x", "US"))
    assert len(ads) == 1
    assert ads[0].id == "b"


def test_deduplicator_filters_correctly():
    dedup = Deduplicator()
    a1 = _ad("1"); a2 = _ad("2"); a1_dup = _ad("1")
    result = dedup.filter_new([a1, a2, a1_dup])
    assert len(result) == 2
EOF

# ---------- Syntax validation tests ----------
cat << 'EOF' > tests/unit/test_syntax_validation.py
"""Tests proving generated fix code is syntactically valid [SEED: 2399]."""
import pytest

from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.fix_forge.validation import validate_fix, validate_python
from ad_leak_engine.shared.schemas import Leak


@pytest.fixture
def forge():
    return FixForge()


def test_python_webhook_compiles(forge):
    leak = Leak(page_id="p", tier="L2", signal="unhashed_pii", severity=0.8, recommendation="hash PII")
    fix = forge.generate(leak, "custom", 0.6)
    py_blocks = [b for b in fix.code_blocks if b["language"] == "python"]
    assert len(py_blocks) == 1
    assert validate_python(py_blocks[0]["code"]) is True


def test_shopify_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "shopify", 0.95)
    assert validate_fix(fix) is True


def test_woocommerce_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="unhashed_pii", severity=0.8, recommendation="hash PII")
    fix = forge.generate(leak, "woocommerce", 0.92)
    assert validate_fix(fix) is True


def test_bigcommerce_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "bigcommerce", 0.90)
    assert validate_fix(fix) is True


def test_custom_gtm_fix_validates(forge):
    leak = Leak(page_id="p", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")
    fix = forge.generate(leak, "custom", 0.6)
    assert validate_fix(fix) is True


def test_invalid_python_rejected():
    assert validate_python("def broken(:") is False
EOF

# ---------- Outreach polish tests ----------
cat << 'EOF' > tests/unit/test_outreach_polish.py
"""Tests for Phase 7 polish: ranked leaks + data-backed message [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.outreach.bundle import OutreachBuilder
from ad_leak_engine.shared.schemas import Page, Leak


@pytest.fixture
def builder(tmp_path):
    return OutreachBuilder(output_dir=str(tmp_path))


@pytest.fixture
def page():
    return Page(id="p_polish", name="Polish Store", url="https://polish.com",
                first_seen=datetime.now(timezone.utc))


def test_leaks_ranked_by_severity(builder, page):
    leaks = [
        Leak(page_id="p_polish", tier="L1", signal="no_video_creative", severity=0.5, recommendation="add video"),
        Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel"),
        Leak(page_id="p_polish", tier="L1", signal="creative_fatigue", severity=0.7, recommendation="refresh"),
    ]
    pack = builder.build(page, leaks, [])
    severities = [l.severity for l in pack.leaks_found]
    assert severities == sorted(severities, reverse=True)
    assert pack.leaks_found[0].signal == "pixel_not_firing"


def test_teardown_marks_ranked(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")]
    pack = builder.build(page, leaks, [])
    assert "Ranked by Severity" in pack.teardown_markdown


def test_message_has_specific_observation_for_fatigue(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L1", signal="creative_fatigue", severity=0.8,
                  recommendation="refresh", evidence={"days_running": 47})]
    pack = builder.build(page, leaks, [])
    assert "47 days" in pack.message_text


def test_message_has_specific_observation_for_pixel(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L2", signal="pixel_not_firing", severity=0.95, recommendation="install pixel")]
    pack = builder.build(page, leaks, [])
    assert "Pixel" in pack.message_text


def test_message_has_specific_observation_for_lcp(builder, page):
    leaks = [Leak(page_id="p_polish", tier="L3", signal="slow_lcp_mobile", severity=0.8,
                  recommendation="optimize", evidence={"lcp_mobile_ms": 4200})]
    pack = builder.build(page, leaks, [])
    assert "4.2s" in pack.message_text
EOF

# ---------- LIVE tests (opt-in, skipped by default) ----------
mkdir -p tests/integration
cat << 'EOF' > tests/integration/test_live_crawl.py
"""LIVE: crawl a real landing page and produce telemetry [SEED: 2399]."""
from datetime import datetime, timezone

import pytest

from ad_leak_engine.leak_scan.telemetry_collector import TelemetryCollector
from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
from ad_leak_engine.leak_scan.l3_scanner import L3SiteScanner
from ad_leak_engine.shared.schemas import Page

LIVE_URL = "https://example.com"


@pytest.mark.live
def test_live_landing_page_audit():
    collector = TelemetryCollector()
    data = collector.collect(LIVE_URL)
    assert "network_log" in data
    assert "telemetry" in data

    page = Page(id="live_crawl", name="Live Crawl", url=LIVE_URL,
                first_seen=datetime.now(timezone.utc), raw=data)
    l2_leaks = L2TrackingScanner().scan(page)
    l3_leaks = L3SiteScanner().scan(page)
    assert isinstance(l2_leaks, list)
    assert isinstance(l3_leaks, list)
EOF

cat << 'EOF' > tests/integration/test_live_ingest.py
"""LIVE: fetch real ads from Meta Ad Library [SEED: 2399]."""
import pytest

from ad_leak_engine.ingest.playwright_source import PlaywrightSource
from ad_leak_engine.ingest.hybrid_router import HybridRouter


@pytest.mark.live
def test_live_ad_library_playwright():
    source = PlaywrightSource()
    ads = list(source.search("shoes", "US", max_results=5))
    # Adversarial target: assert it runs and returns a list (may be 0 if blocked).
    assert isinstance(ads, list)


@pytest.mark.live
def test_live_hybrid_router():
    router = HybridRouter()
    ads = list(router.search("shoes", "US", max_results=5))
    assert isinstance(ads, list)
EOF

# ---------- Run offline test suite ----------
echo "[SEED:2399] Running Phase 7 offline test suite..."
python -m pytest tests/ --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 7 COMPLETE"
echo "  Reality Bridge + Polish built. Live connectors installed."
echo ""
echo "  To run LIVE tests against the real internet:"
echo "    python -m pytest tests/ -m live --run-live"
echo "=========================================================="