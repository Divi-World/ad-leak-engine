#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — URL SANITIZATION PATCH
# Fixes malformed Meta Ad Library URLs (e.g., https://https////)
# ============================================================
set -e

echo "[SEED:2399] Patching URL normalizer..."

if [ -f ".venv/Scripts/activate" ]; then source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then source .venv/bin/activate
fi

cat << 'EOF' > src/ad_leak_engine/ingest/normalizer.py
"""Normalizes raw Meta Ad Library JSON into RawAd contract [SEED: 2399]."""
import re
from datetime import datetime, timezone
from ..shared.schemas import RawAd

def clean_landing_url(url: str | None) -> str | None:
    """Sanitizes messy URLs extracted from Meta's HTML/JSON."""
    if not url:
        return None
    # 1. Fix escaped slashes from JSON extraction (e.g., https:\/\/www...)
    url = url.replace("\\/", "/")
    # 2. Fix duplicate protocols (e.g., https://https://...)
    url = re.sub(r'^(https?:\/\/)+', 'https://', url, flags=re.IGNORECASE)
    # 3. Collapse excessive slashes in the path (but preserve the domain slash)
    # e.g., https://www.hoka.com//en//us/ -> https://www.hoka.com/en/us/
    parts = url.split('/', 3)
    if len(parts) == 4:
        url = f"{parts[0]}//{parts[2]}/{parts[3].replace('//', '/')}"
    return url

def normalize_meta_ad(raw: dict, country: str) -> RawAd:
    page_data = raw.get("page", {}) or {}
    snapshot = raw.get("snapshot", {}) or {}

    raw_url = snapshot.get("link_url") or raw.get("landing_url")
    
    return RawAd(
        id=str(raw.get("id") or raw.get("ad_archive_id") or raw.get("ad_id") or "unknown"),
        page_id=str(page_data.get("id", "unknown")),
        page_name=page_data.get("name", "Unknown Page"),
        start_date=_parse_date(
            raw.get("creation_time") or raw.get("start_date") or raw.get("ad_delivery_start_time")
        ),
        media_type=_infer_media_type(raw, snapshot),
        title=raw.get("title") or snapshot.get("title"),
        body=raw.get("body") or snapshot.get("body"),
        cta=raw.get("cta_text") or snapshot.get("cta_text"),
        landing_url=clean_landing_url(raw_url),
        country=country,
        raw=raw,
    )

def _parse_date(val):
    if val is None:
        return datetime.now(timezone.utc)
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)

def _infer_media_type(raw: dict, snapshot: dict) -> str:
    mt = raw.get("media_type")
    if mt and str(mt).upper() in ("IMAGE", "VIDEO", "CAROUSEL", "DYNAMIC"):
        return str(mt).upper()
    if snapshot.get("videos") or snapshot.get("video"):
        return "VIDEO"
    if snapshot.get("cards") or snapshot.get("carousel"):
        return "CAROUSEL"
    return "IMAGE"
EOF

echo "[SEED:2399] URL Sanitizer installed."
echo "Run: ./scripts/ale scan shoes US --limit 2"