"""Pixel forensics helpers [SEED: 2399].

Pure functions, no browser, no network. Extracts Meta pixel identity from
transports and encodings that URL-only matching cannot see:
  * multipart POST /tr  -> id and ev live in the BODY, not the query string
  * base64 / split-join -> advertisers deliberately fragment the ID
"""
import base64
import binascii
import re

RE_TR_FORM_ID = re.compile(r'name="id"[\r\n]+(\d{10,16})')
RE_TR_FORM_EV = re.compile(r'name="ev"[\r\n]+([A-Za-z][A-Za-z0-9_]{1,60})')
RE_URLFORM_ID = re.compile(r'(?:^|[&?])id=(\d{10,16})')
RE_URLFORM_EV = re.compile(r'(?:^|[&?])ev=([A-Za-z][A-Za-z0-9_]{1,60})')

# 10-digit IDs base64 to a 14-char core; 16-digit to 22. Bound measured, not guessed.
_B64_TOKEN = re.compile(r'[A-Za-z0-9+/]{14,}={0,2}')
_DIGITS = re.compile(r'\b\d{10,16}\b')
# Fragments may be ANY width. Concatenation intent is enforced in code below.
_SPLIT_JOIN = re.compile(r"""["']\d{1,16}["'](?:\s*[,+]\s*["']\d{1,16}["']){2,}""")
_ANY_DIGITS = re.compile(r'\d+')


def post_form_meta(post_data):
    """Return (pixel_id, event_name) from a /tr request body. Either may be None."""
    if not post_data:
        return None, None
    pid = ev = None
    m = RE_TR_FORM_ID.search(post_data) or RE_URLFORM_ID.search(post_data)
    if m:
        pid = m.group(1)
    m = RE_TR_FORM_EV.search(post_data) or RE_URLFORM_EV.search(post_data)
    if m:
        ev = m.group(1)
    return pid, ev


def decode_obfuscated_ids(body):
    """Recover pixel IDs hidden by base64 or split-join. Returns a set of str."""
    found = set()
    if not body:
        return found
    for tok in _B64_TOKEN.findall(body)[:400]:
        try:
            dec = base64.b64decode(tok + '=' * (-len(tok) % 4)).decode('utf-8', 'ignore')
        except (binascii.Error, ValueError):
            continue
        found.update(_DIGITS.findall(dec))
    for m in _SPLIT_JOIN.finditer(body):
        grp = m.group(0)
        tail = body[m.end():m.end() + 16].replace(" ", "")
        # '+' IS concatenation. ',' only counts when the array is actually joined.
        if "+" not in grp and ".join" not in tail:
            continue
        joined = ''.join(_ANY_DIGITS.findall(grp))
        if 10 <= len(joined) <= 16:
            found.add(joined)
    return found


def build_census(merged_log, validate=None):
    """Canonical multi-pixel census. Never collapses to a single ID.

    Unions every discovery vector, validates each unique ID exactly once,
    and grades each on measured transmission strength.
    Pure aggregation: no browser, no network of its own.
    """
    ids = {}

    def slot(pid):
        pid = str(pid or "").strip()
        if not pid or not pid.isdigit() or not (8 <= len(pid) <= 20):
            return None
        return ids.setdefault(pid, {
            "pixel_id": pid, "sources": [], "events": [], "event_ids": [],
            "has_add_to_cart": False, "has_initiate_checkout": False,
            "has_purchase_event": False, "has_unhashed_pii": False,
            "tr_hits": 0,
        })

    def merge_sources(entry, label):
        s = slot(entry.get("pixel_id"))
        if s and label not in s["sources"]:
            s["sources"].append(label)

    for e in (merged_log.get("detected_pixel_ids") or []):
        s = slot(e.get("pixel_id"))
        if not s:
            continue
        for sc in (e.get("sources") or []):
            if sc not in s["sources"]:
                s["sources"].append(sc)
    for e in (merged_log.get("tealium_pixels") or []):
        merge_sources(e, "tealium_static")
    for e in (merged_log.get("first_party_meta_hits") or []):
        merge_sources(e, "first_party_proxy")
    for fr in (merged_log.get("frame_harvest") or []):
        for pid in (fr.get("pixel_ids") or []):
            s = slot(pid)
            if s and "subframe" not in s["sources"]:
                s["sources"].append("subframe")
    for ev in (merged_log.get("meta_tr_events") or []):
        s = slot(ev.get("pixel_id"))
        if not s:
            continue
        s["tr_hits"] += 1
        if ev.get("event") and ev["event"] not in s["events"]:
            s["events"].append(ev["event"])
        if "network_tr" not in s["sources"]:
            s["sources"].append("network_tr")
    for pid, d in (merged_log.get("per_pixel") or {}).items():
        s = slot(pid)
        if not s:
            continue
        for k in ("events", "event_ids", "sources"):
            for v in (d.get(k) or []):
                if v not in s[k]:
                    s[k].append(v)
        for k in ("has_add_to_cart", "has_initiate_checkout",
                  "has_purchase_event", "has_unhashed_pii"):
            if d.get(k):
                s[k] = True

    vals = {}
    for v in (merged_log.get("pixel_validations") or []):
        if isinstance(v, dict) and v.get("id"):
            vals[str(v["id"])] = v
    pv = merged_log.get("pixel_validation")
    if isinstance(pv, dict) and pv.get("id"):
        vals.setdefault(str(pv["id"]), pv)

    rows = []
    for pid, s in ids.items():
        v = vals.get(pid)
        if v is None and validate is not None:
            v = validate(pid)
            vals[pid] = v
        v = v or {}
        if s["tr_hits"] or s["events"]:
            transmission = "transmitting"
        elif "fbq_init" in s["sources"] or "fbq_track_single" in s["sources"]:
            transmission = "initialized_no_events"
        elif "network_config_bundle" in s["sources"]:
            transmission = "config_loaded"
        else:
            transmission = "static_only"
        rows.append(dict(s, verdict=v.get("verdict") or "unknown",
                         transmission=transmission,
                         config_bytes=v.get("meta_config_size_bytes"),
                         config_http=v.get("meta_config_http_status")))

    order = {"transmitting": 0, "initialized_no_events": 1,
             "config_loaded": 2, "static_only": 3}
    rows.sort(key=lambda r: (order.get(r["transmission"], 9),
                             -len(r["sources"]), r["pixel_id"]))
    return {
        "total_ids": len(rows),
        "confirmed_real": sum(1 for r in rows if r["verdict"] == "real_pixel_confirmed_by_config"),
        "transmitting": sum(1 for r in rows if r["transmission"] == "transmitting"),
        "initialized_no_events": sum(1 for r in rows if r["transmission"] == "initialized_no_events"),
        "config_loaded": sum(1 for r in rows if r["transmission"] == "config_loaded"),
        "static_only": sum(1 for r in rows if r["transmission"] == "static_only"),
        "dead_or_invalid": sum(1 for r in rows if r["verdict"] == "invalid_format_or_dead"),
        "pixels": rows,
        "primary_pixel_id": rows[0]["pixel_id"] if rows else None,
        "all_validations": list(vals.values()),
    }
