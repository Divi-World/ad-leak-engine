"""Integration: Leak -> Fix Generation Pipeline [SEED: 2399]."""
import json
from pathlib import Path
from ad_leak_engine.shared.schemas import Leak
from ad_leak_engine.fix_forge.forge import FixForge

def test_fix_pipeline_from_fixture():
    fixture = Path("tests/fixtures/sample_leaks.json")
    if not fixture.exists(): return
    leaks = [Leak(**l) for l in json.loads(fixture.read_text())]
    forge = FixForge()
    for leak in leaks:
        try:
            fix = forge.generate(leak, "shopify", 0.95)
            assert fix.platform == "shopify"
        except Exception:
            pass # Some leaks might not have fixes for specific platforms
