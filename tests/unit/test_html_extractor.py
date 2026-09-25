"""Tests for the HTML ad extractor [SEED: 2399]."""
from pathlib import Path

import pytest

from ad_leak_engine.ingest.html_extractor import HtmlAdExtractor

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "sample_meta_ads.html").read_text(encoding="utf-8")


@pytest.fixture
def extractor():
    return HtmlAdExtractor()


def test_extracts_ads_from_html(extractor):
    ads = extractor.extract_ads(FIXTURE, "US")
    assert len(ads) == 2


def test_extracts_correct_fields(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    assert ads["111"].page_name == "Store One"
    assert ads["111"].landing_url == "https://storeone.com"
    assert ads["222"].body == "Best sneakers"
    assert ads["222"].country == "US"


def test_handles_braces_in_strings(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    # Body contains literal "{ special }" — must not break JSON parsing
    assert "special" in ads["111"].body


def test_handles_unix_timestamp(extractor):
    ads = {a.id: a for a in extractor.extract_ads(FIXTURE, "US")}
    assert ads["111"].start_date.year >= 2023


def test_dedupes_by_id(extractor):
    doubled = FIXTURE + FIXTURE
    ads = extractor.extract_ads(doubled, "US")
    assert len(ads) == 2


def test_empty_html(extractor):
    assert extractor.extract_ads("", "US") == []


def test_no_ads_html(extractor):
    assert extractor.extract_ads("<html><body>nothing here</body></html>", "US") == []


def test_invalid_json_returns_empty(extractor):
    bad = '<script>{"ad_archive_id":"9","page":{broken json,,,</script>'
    assert extractor.extract_ads(bad, "US") == []
