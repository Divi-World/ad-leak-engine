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
