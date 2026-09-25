"""Tests for Swarm Aggregator JSON parsing [SEED: 2399]."""
import json
from ad_leak_engine.shared.schemas import RawAd

def test_swarm_json_parsing(tmp_path):
    sample = [{"id": "999", "page_id": "p1", "page_name": "Test", "start_date": "2026-01-01T00:00:00Z", "media_type": "IMAGE", "country": "US", "raw": {}}]
    f = tmp_path / "ads_123.json"
    f.write_text(json.dumps(sample))
    data = json.loads(f.read_text())
    ads = [RawAd(**item) for item in data]
    assert len(ads) == 1
    assert ads[0].id == "999"
