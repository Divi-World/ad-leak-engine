"""Tests for human_browser primitives [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser, _bezier_curve

def test_bezier_curve_endpoints():
    p0, p1, p2, p3 = (0, 0), (10, 10), (20, 5), (30, 30)
    sx, sy = _bezier_curve(p0, p1, p2, p3, 0.0)
    ex, ey = _bezier_curve(p0, p1, p2, p3, 1.0)
    assert (sx, sy) == (0, 0)
    assert (ex, ey) == (30, 30)

def test_human_browser_initializes():
    hb = HumanBrowser(headless=True)
    assert hb.headless is True

def test_human_browser_session_context_manager():
    hb = HumanBrowser(headless=True)
    with hb.session() as page:
        assert page is not None

def test_human_pause_does_not_raise():
    HumanBrowser.human_pause(0.01, 0.02)
