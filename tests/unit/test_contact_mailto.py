"""Phase 42.14 regression locks: mailto extraction + routes compile gate [SEED: 2399]."""
import pathlib
import re

MAILTO_RE = re.compile(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', re.IGNORECASE)


def test_mailto_regex_extracts_hidden_emails():
    html = ('<a href="mailto:support@brand.com?subject=Hi">Email</a>'
            '<a href="MAILTO:hello@brand.co.uk">h</a>')
    found = MAILTO_RE.findall(html)
    assert "support@brand.com" in found
    assert "hello@brand.co.uk" in found


def test_routes_module_compiles():
    root = pathlib.Path(__file__).resolve().parents[2]
    src = (root / 'src' / 'ad_leak_engine' / 'orchestrator' / 'routes' / 'api.py').read_text(encoding='utf-8')
    compile(src, 'api.py', 'exec')
