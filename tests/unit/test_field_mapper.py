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
