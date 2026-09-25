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
