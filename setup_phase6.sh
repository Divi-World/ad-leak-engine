#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — PHASE 6: Outreach Bundle
# ============================================================
set -e

echo ""
echo "=========================================================="
echo "  Ad-Leak-Engine [SEED: 2399] — PHASE 6 BOOTSTRAP"
echo "=========================================================="

# ---------- 1. Activate Venv ----------
if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
else echo "[SEED:2399] FATAL: Venv not found."; exit 1; fi

# ---------- 2. Directories ----------
mkdir -p src/ad_leak_engine/outreach/templates
touch src/ad_leak_engine/outreach/__init__.py

# ---------- 3. Compliance Checker ----------
cat << 'EOF' > src/ad_leak_engine/outreach/compliance.py
"""CAN-SPAM and GDPR compliance validation [SEED: 2399]."""

class ComplianceError(Exception):
    """Raised when outreach message violates compliance rules."""

class ComplianceChecker:
    """Validates outreach messages against legal frameworks."""

    def validate(self, message: str) -> bool:
        """Ensure message contains required compliance elements."""
        msg_lower = message.lower()
        
        # CAN-SPAM requires physical address and unsubscribe mechanism
        has_address = "[physical address]" in msg_lower or "street" in msg_lower or "ave" in msg_lower or "blvd" in msg_lower
        has_unsub = "unsubscribe" in msg_lower or "opt-out" in msg_lower or "opt out" in msg_lower
        
        if not has_unsub:
            raise ComplianceError("Message missing unsubscribe/opt-out mechanism (CAN-SPAM/GDPR violation)")
            
        # We allow placeholders for physical address in templates
        if not has_address and "[physical address]" not in message:
             raise ComplianceError("Message missing physical address placeholder (CAN-SPAM violation)")
             
        return True
EOF

# ---------- 4. Message Generator ----------
cat << 'EOF' > src/ad_leak_engine/outreach/message_gen.py
"""Data-backed outreach text generation [SEED: 2399]."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from ..shared.schemas import Page, Leak, Fix

TEMPLATE_DIR = Path(__file__).parent / "templates"

class MessageGenerator:
    """Generates personalized outreach messages and executive summaries."""

    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_message(self, page: Page, leaks: list[Leak], fixes: list[Fix]) -> str:
        """Generate the initial outreach email/DM text."""
        template = self.env.get_template("message.txt.j2")
        top_leak = max(leaks, key=lambda l: l.severity) if leaks else None
        return template.render(page=page, top_leak=top_leak, leak_count=len(leaks))

    def generate_executive_summary(self, page: Page, leaks: list[Leak]) -> str:
        """Generate a 2-sentence executive summary."""
        template = self.env.get_template("executive_summary.txt.j2")
        return template.render(page=page, leak_count=len(leaks))
EOF

# ---------- 5. Bundle Builder (Orchestrator) ----------
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
        # 1. Generate Teardown Markdown
        teardown_md = self._generate_teardown(page, leaks, fixes)
        
        # 2. Generate Executive Summary & Message
        exec_summary = self.message_gen.generate_executive_summary(page, leaks)
        message_text = self.message_gen.generate_message(page, leaks, fixes)
        
        # 3. Validate Compliance
        self.compliance.validate(message_text)
        
        # 4. Calculate Estimated Recovery
        estimated_recovery = self._estimate_recovery(leaks)
        
        # 5. Save to Disk
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
        """Heuristic: $1000/mo per high severity leak, $300/mo per medium."""
        high_sev = sum(1 for l in leaks if l.severity >= 0.8)
        med_sev = sum(1 for l in leaks if 0.5 <= l.severity < 0.8)
        recovery = (high_sev * 1000) + (med_sev * 300)
        return f"${recovery:,}/month potential recovery"
EOF

# ---------- 6. Template: Teardown Markdown ----------
cat << 'EOF' > src/ad_leak_engine/outreach/templates/teardown.md.j2
# Ad Infrastructure Teardown: {{ page.name }}
**Generated by Ad-Leak-Engine [SEED: 2399]**

## Executive Summary
We analyzed your active Meta ad campaigns and landing page infrastructure. 
We identified **{{ leaks|length }} critical revenue leaks** that are currently degrading your ROAS and inflating your CPA.

---

## Detected Leaks
{% for leak in leaks %}
### {{ loop.index }}. {{ leak.signal.replace('_', ' ').title() }} (Severity: {{ "%.0f"|format(leak.severity * 100) }}%)
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

# ---------- 7. Template: Outreach Message ----------
cat << 'EOF' > src/ad_leak_engine/outreach/templates/message.txt.j2
Subject: Found {{ leak_count }} tracking leaks on {{ page.name }}'s ads

Hi Team,

I was analyzing {{ page.name }}'s active Meta ad campaigns and noticed your landing page infrastructure has {{ leak_count }} tracking leaks. 

Specifically, your most critical issue is: {{ top_leak.signal.replace('_', ' ') if top_leak else 'tracking misconfiguration' }}. This is likely causing Meta's algorithm to optimize against incomplete data, inflating your CPA.

I've attached a brief teardown with the exact code-level fixes to recover this lost revenue. 

Are you open to a quick chat this week to walk through the implementation?

Best,
[Your Name]
Ad-Leak-Engine

---
[Physical Address] | To opt-out of future audits, reply "UNSUBSCRIBE"
EOF

# ---------- 8. Template: Executive Summary ----------
cat << 'EOF' > src/ad_leak_engine/outreach/templates/executive_summary.txt.j2
{{ page.name }} is currently losing estimated revenue due to {{ leak_count }} detected infrastructure leaks in their Meta ad tracking and landing page performance. Immediate implementation of the provided fixes will restore data fidelity and lower CPA.
EOF

# ---------- 9. Tests: Outreach Bundle ----------
cat << 'EOF' > tests/unit/test_outreach.py
"""Unit tests for Phase 6: Outreach Bundle Assembly."""
import pytest
from pathlib import Path
from datetime import datetime, timezone

from ad_leak_engine.outreach.bundle import OutreachBuilder
from ad_leak_engine.outreach.compliance import ComplianceChecker, ComplianceError
from ad_leak_engine.shared.schemas import Page, Leak, Fix


@pytest.fixture
def builder(tmp_path):
    return OutreachBuilder(output_dir=str(tmp_path))


@pytest.fixture
def sample_page():
    return Page(id="p_outreach", name="Test Store", url="https://test.com",
                first_seen=datetime.now(timezone.utc))


@pytest.fixture
def sample_leaks():
    return [
        Leak(page_id="p_outreach", tier="L2", signal="pixel_not_firing",
             severity=0.95, recommendation="Install pixel"),
        Leak(page_id="p_outreach", tier="L1", signal="creative_fatigue",
             severity=0.7, recommendation="Refresh ads"),
    ]


@pytest.fixture
def sample_fixes():
    return [
        Fix(leak_id="l1", platform="shopify", platform_confidence=0.95,
            markdown_guide="# Guide", expected_outcome="Pixel fires",
            confidence=0.9, verification_steps=["Check Events Manager"]),
    ]


def test_bundle_creates_files(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert pack.page_id == "p_outreach"
    assert len(pack.evidence_paths) == 2
    for p in pack.evidence_paths:
        assert Path(p).exists()


def test_message_contains_compliance_footer(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert "UNSUBSCRIBE" in pack.message_text
    assert "[Physical Address]" in pack.message_text


def test_teardown_contains_leaks(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    assert "Pixel Not Firing" in pack.teardown_markdown
    assert "Creative Fatigue" in pack.teardown_markdown


def test_estimated_recovery_calculation(builder, sample_page, sample_leaks, sample_fixes):
    pack = builder.build(sample_page, sample_leaks, sample_fixes)
    # 1 high sev (0.95) = $1000, 1 med sev (0.7) = $300 -> $1,300
    assert "$1,300" in pack.estimated_recovery


def test_compliance_checker_rejects_missing_unsub():
    checker = ComplianceChecker()
    with pytest.raises(ComplianceError):
        checker.validate("Hi, buy my stuff. [Physical Address]")
EOF

# ---------- 10. Integration Test: Full Pipeline ----------
mkdir -p tests/integration
cat << 'EOF' > tests/integration/test_full_pipeline.py
"""End-to-end integration test: Scan -> Detect -> Fix -> Bundle [SEED: 2399]."""
from datetime import datetime, timezone

from ad_leak_engine.ingest.normalizer import normalize_meta_ad
from ad_leak_engine.leak_scan.l1_creative import L1CreativeScanner
from ad_leak_engine.leak_scan.l2_tracking import L2TrackingScanner
from ad_leak_engine.platform_fingerprint.detector import PlatformDetector
from ad_leak_engine.fix_forge.forge import FixForge
from ad_leak_engine.outreach.bundle import OutreachBuilder
from ad_leak_engine.shared.schemas import Page


def test_end_to_end_pipeline(tmp_path):
    # 1. Ingest (Mocked Raw Ad)
    raw_ad = {
        "id": "ad_99",
        "page": {"id": "p_99", "name": "Ecom Store"},
        "creation_time": "2025-01-01T00:00:00Z",
        "media_type": "IMAGE",
    }
    ad = normalize_meta_ad(raw_ad, "US")
    
    # 2. Build Page with Network Log (Mocked L2 Data)
    page = Page(
        id="p_99", name="Ecom Store", url="https://ecom.com",
        ads=[ad], first_seen=datetime.now(timezone.utc),
        raw={"network_log": {"pixel_fired": False}}
    )
    
    # 3. Scan L1 & L2
    l1_leaks = L1CreativeScanner().scan(page)
    l2_leaks = L2TrackingScanner().scan(page)
    all_leaks = l1_leaks + l2_leaks
    assert len(all_leaks) > 0, "Pipeline failed to detect leaks"
    
    # 4. Fingerprint
    html = '<html><script src="https://cdn.shopify.com/s/files/1/0000/0001/themes/theme.css"></script><script>Shopify.theme = {};</script></html>'
    platform, conf = PlatformDetector().detect("https://ecom.com", html)
    assert platform == "shopify", "Pipeline failed to fingerprint Shopify"
    
    # 5. Forge Fixes
    forge = FixForge()
    fixes = [forge.generate(leak, platform, conf) for leak in all_leaks if leak.tier == "L2"]
    assert len(fixes) > 0, "Pipeline failed to generate fixes"
    
    # 6. Outreach Bundle
    builder = OutreachBuilder(output_dir=str(tmp_path))
    pack = builder.build(page, all_leaks, fixes)
    
    assert pack.page_name == "Ecom Store"
    assert "UNSUBSCRIBE" in pack.message_text
    assert len(pack.fixes) > 0
    assert "Shopify" in pack.teardown_markdown
    assert "$" in pack.estimated_recovery
EOF

# ---------- 11. Execute Tests ----------
echo "[SEED:2399] Running Phase 6 test suite (Unit + Integration)..."
python -m pytest tests/ -v --tb=short

echo ""
echo "=========================================================="
echo "  [SEED: 2399] PHASE 6 COMPLETE"
echo "  Outreach Bundle Built. End-to-End Pipeline Verified."
echo "=========================================================="