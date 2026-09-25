"""Integration: Ad -> Leak Detection Pipeline [SEED: 2399]."""
import json
from pathlib import Path
from ad_leak_engine.shared.schemas import Page
from ad_leak_engine.leak_scan.l1_creative import L1CreativeScanner

def test_leak_pipeline_from_fixture():
    fixture = Path("tests/fixtures/sample_pages.json")
    if not fixture.exists(): return
    pages = [Page(**p) for p in json.loads(fixture.read_text())]
    scanner = L1CreativeScanner()
    for page in pages:
        leaks = scanner.scan(page)
        assert isinstance(leaks, list)
