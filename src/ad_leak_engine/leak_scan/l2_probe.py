"""L2 Live Probe: Industrial Grade Network Interception [SEED: 2399].
Strategy:
1. Primary: Camoufox (Firefox) - Native Gecko fingerprinting bypasses CF Enterprise.
2. Secondary: GHOST PROTOCOL - Deep-level stealth browser with fingerprint
masking (headful Chromium, WebGL/Audio/Canvas patches, human simulation).
3. Tertiary: UNIVERSAL DATA EXTRACTOR (Permanent Solution) - Multi-vector
extraction via `UniversalDataExtractor.full_extract`.
4. Quaternary: STATIC GTM RESOLVER - Deep parse of a GTM container ID if any
earlier step surfaced one.
FUNNEL AUDIT:
- `probe_funnel(url)` walks landing -> product -> cart -> checkout in one
browser session, capturing fbq() calls at every step.
PIXEL DISCOVERY (multi-vector):
- `_extract_pixel_id_from_network` reads the pixel ID from the config bundle
request URL that fbevents.js ALWAYS fires. Survives Shopify sandbox,
CF JS delay, and consent gates.
- `_wait_for_fbq_and_capture` captures fbq() calls for event payloads.
- `_validate_pixel_via_config` verifies the ID against Meta's public config.
META CONFIG VALIDATION:
- `_validate_pixel_via_config(pixel_id)` fetches Meta's public config bundle.
- `_infer_tracking_mode(funnel_log)` classifies the store as browser-side,
CAPI-server-side, or ambiguous.
E-COMMERCE DETECTION (resilient):
- `_looks_like_ecommerce(url)` returns True even when the main page is WAF-blocked.
HUMAN INTERACTION (new):
- `_attempt_checkout_click` simulates scroll + curved mouse + hesitation to
defeat Cloudflare Bot Management, DataDome, and Akamai behavioral layers.
Supports: Shopify, WooCommerce, BigCommerce, Magento, Custom/Headless.
"""
import logging
import re
import time
import random
import json
from urllib.parse import urlparse, urljoin
from src.ad_leak_engine.utils.managed_tor import ManagedTorDaemon
from src.ad_leak_engine.utils.data_extractor import UniversalDataExtractor
import hashlib
from pathlib import Path
import os

# --- CRITICAL FIX: Define Logger BEFORE any usage ---
logger = logging.getLogger(__name__)

# External Libs
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logger.warning("Camoufox not found. Falling back to Chromium only.")

try:
    from invisible_playwright import InvisiblePlaywright
    INVISIBLE_AVAILABLE = True
except ImportError:
    INVISIBLE_AVAILABLE = False
    logger.warning("invisible_playwright not found. Cloudflare-protected sites will fall back to Camoufox/Ghost.")

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

# Pre-compiled regex patterns
RE_FBQ_INIT = re.compile(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]""")
RE_PIXEL_JSON = re.compile(r'"pixelId"\s*:\s*"(\d{8,})"')
RE_GTM_ID = re.compile(r'GTM-[A-Z0-9]{4,}')
RE_CAPI_URL = re.compile(r'graph\.facebook\.com/v\d+\.\d+/(\d+)/events')
RE_CONFIG_BUNDLE = re.compile(r'connect\.facebook\.net/signals/config/(\d{8,})')
RE_TR_PIXEL_ID = re.compile(r'[?&]id=(\d{8,})')
RE_TR_EVENT = re.compile(r'[?&]ev=([^&]+)')

# NEW: Advanced Patterns for Minified GTM Containers
RE_GTM_MINIFIED_PIXEL = re.compile(r'["\'](?:pixelId|fb_pixel_id|metaPixelId|facebook_pixel_id)["\']\s*[:=]\s*["\']?(\d{10,16})["\']?', re.IGNORECASE)
RE_VAR_PIXEL_ASSIGN = re.compile(r'(?:var|let|const)\s+(?:pixelId|fbPixelId|metaPixelId)\s*=\s*["\'](\d{10,16})["\']', re.IGNORECASE)

# NEW: PII heuristic — SHA-256 hex is 64 chars lowercase; a raw email or phone is not
RE_HEX64 = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)
RE_EMAIL_RAW = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
RE_PHONE_RAW = re.compile(r'^\+?[\d\s\-()]{7,20}$')

# Audit integrity: probe-generated fbq calls are OFF by default. Any capture
# produced while this is enabled is tagged and excluded from leak verdicts.
ALLOW_SYNTHETIC_FBQ = os.environ.get("ADLEAK_ALLOW_SYNTHETIC_FBQ", "0") == "1"

def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ.get(name, str(default)))))
    except (TypeError, ValueError):
        logger.warning(f"[CONFIG] {name} invalid; falling back to {default}")
        return default

FUNNEL_TARGET_ITEMS = _env_int("ADLEAK_FUNNEL_ITEMS", 2, 1, 6)
FUNNEL_MAX_ITEMS = _env_int("ADLEAK_FUNNEL_MAX_ITEMS", 4, 1, 8)
# ---------------------------------------------------------------------- #
# MODULE-LEVEL: JavaScript that intercepts fbq() before any page script
# runs and stores every call with its payload on window.__fbq_captured.
# ---------------------------------------------------------------------- #
FBQ_INTERCEPTOR_JS = r"""
(function() {
  if (window.__fbq_interceptor_installed) return;
  window.__fbq_interceptor_installed = true;
  window.__fbq_captured = [];
  window.__fbq_meta = {mode:'transparent', assignments:0, real_impl_seen:false, loader_scripts:0};
  var cache = new WeakMap();

  function clone(x){ try { return JSON.parse(JSON.stringify(x)); } catch(e){ return String(x); } }

  function record(args){
    try {
      var a = args, form = 'call';
      if (a.length === 1 && Array.isArray(a[0])) { a = a[0]; form = 'push'; }
      if (!a || !a.length || typeof a[0] !== 'string') return;
      var r = {ts: Date.now(), call_type: a[0], form: form, args: []};
      for (var i=1;i<a.length;i++){
        var v = a[i];
        r.args.push(v !== null && typeof v === 'object' ? clone(v) : v);
      }
      window.__fbq_captured.push(r);
    } catch(e){}
  }

  function wrap(fn){
    if (typeof fn !== 'function') return fn;
    if (cache.has(fn)) return cache.get(fn);
    var p;
    var h = {
      apply: function(t, th, args){ record(args); return Reflect.apply(t, th, args); },
      get:   function(t, k){ var v = t[k]; return (v === t) ? p : v; },
      set:   function(t, k, v){
               if (k === 'callMethod' || k === 'instance') window.__fbq_meta.real_impl_seen = true;
               t[k] = v; return true;
             }
    };
    p = new Proxy(fn, h);
    cache.set(fn, p);
    return p;
  }

  function trap(name){
    var cur;
    try {
      Object.defineProperty(window, name, {
        configurable: true,
        get: function(){ return cur; },
        set: function(v){
          window.__fbq_meta.assignments++;
          if (v && (v.callMethod || v.instance)) window.__fbq_meta.real_impl_seen = true;
          cur = wrap(v);
        }
      });
    } catch(e){}
  }
  trap('fbq'); trap('_fbq');

  try {
    new MutationObserver(function(muts){
      for (var i=0;i<muts.length;i++){
        var ns = muts[i].addedNodes || [];
        for (var j=0;j<ns.length;j++){
          var n = ns[j];
          if (n && n.tagName === 'SCRIPT' && /fbevents\.js/.test(n.src || ''))
            window.__fbq_meta.loader_scripts++;
        }
      }
    }).observe(document, {childList:true, subtree:true});
  } catch(e){}
})();
"""

def detect_capi_dedup_failure(telemetry) -> bool:
    return not telemetry.get("has_shared_event_id", True)

def detect_missing_initiate_checkout(telemetry) -> bool:
    return not telemetry.get("has_initiate_checkout", False)

def detect_missing_add_to_cart(telemetry) -> bool:
    return not telemetry.get("has_add_to_cart", False)

def detect_attribution_gap(page, telemetry) -> bool:
    has_spend = page.total_estimated_spend[1] > 0 if page.total_estimated_spend else False
    has_conversions = telemetry.get("has_purchase_event", False)
    return has_spend and not has_conversions


class L2LiveProbe:
    """Probes a live landing page using Hybrid Stealth Swarm."""

    def __init__(self):
        self.stealth_args_chromium = [
            "--disable-blink-features=AutomationControlled",
            "--exclude-switches=enable-automation",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--lang=en-US",
            "--start-maximized",
            "--window-size=1920,1080",
        ]
        self.uas = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]
        self.tor_daemon = ManagedTorDaemon()
        self.data_extractor = UniversalDataExtractor()

    # ------------------------------------------------------------------ #
    # NEW: NETWORK-LEVEL PIXEL ID EXTRACTION
    # ------------------------------------------------------------------ #
    def _extract_pixel_id_from_network(self, all_requests) -> str | None:
        """
        Extract the Meta pixel ID from any captured network request.
        When fbevents.js loads, Meta ALWAYS requests:
        https://connect.facebook.net/signals/config/<PIXEL_ID>
        That request is captured by page.on("response") regardless of whether
        fbq('init') fires. The pixel ID is literally in the URL path.
        This survives:
        - Shopify Web Pixel sandbox blocking fbq() (checkout case)
        - Cloudflare delaying theme JS (timing case)
        - Any site where fbq init happens in a subframe or worker
        Returns the first pixel ID found, or None.
        """
        candidates = []
        for r in all_requests:
            if not isinstance(r, dict):
                continue
            url = str(r.get("url", ""))
            m = RE_CONFIG_BUNDLE.search(url)
            if m:
                candidates.append(m.group(1))
        if not candidates:
            return None
        # Return most common (dedupe by frequency) — the pixel ID that fired most
        from collections import Counter
        pid = Counter(candidates).most_common(1)[0][0]
        logger.info(f"[NETWORK_PIXEL] Extracted pixel ID {pid} from {len(candidates)} config bundle request(s)")
        return pid

    # ------------------------------------------------------------------ #
    # TIMING-ROBUST CAPTURE HELPER
    # ------------------------------------------------------------------ #
    def _wait_for_fbq_and_capture(self, page, all_requests, timeout: int = 15) -> list:
        """
        Actively wait for connect.facebook.net/en_US/fbevents.js to load and for
        the page's own JS to call fbq('init', ...). Then read window.__fbq_captured.
        Behavior:
        1. Poll every 500ms for up to `timeout` seconds, checking:
           a. Did a request to connect.facebook.net/fbevents.js already fire?
           b. Is window.__fbq_captured non-empty?
        2. If fbevents.js loaded but the site never called fbq('init', ...) within
           `timeout`, synthesize one from the pixel ID found in window._fbq or
           the config-bundle's known pixelId — this makes the pixel fire so we
           can capture it.
        3. Return the captures array (possibly empty if nothing worked).
        """
        deadline = time.time() + timeout
        fb_js_loaded = False
        captures = []
        absent_since = None
        while time.time() < deadline:
            if not fb_js_loaded:
                fb_js_loaded = any(
                    "fbevents.js" in str(r.get("url", ""))
                    for r in all_requests if isinstance(r, dict)
                )
            state = {}
            try:
                captures = page.evaluate("window.__fbq_captured || []")
                if captures:
                    logger.info(f"[FBQ_WAIT] Captured {len(captures)} fbq call(s) after "
                                f"{timeout - (deadline - time.time()):.1f}s")
                    return captures
                state = page.evaluate("""() => ({
                    shim: !!window.__fbq_interceptor_installed,
                    loaders: (window.__fbq_meta && window.__fbq_meta.loader_scripts) || 0,
                    fn: typeof window.fbq
                })""") or {}
            except Exception:
                captures = []
            # Evidence-based early exit: shim active, no fbq, no loader script, no request.
            if (state.get("shim") and state.get("fn") == "undefined"
                    and not state.get("loaders") and not fb_js_loaded):
                if absent_since is None:
                    absent_since = time.time()
                elif time.time() - absent_since >= 3.0:
                    logger.info(f"[FBQ_WAIT] Proven absent after {time.time() - (deadline - timeout):.1f}s "
                                f"— early exit, no dead wait.")
                    return []
            else:
                absent_since = None
            time.sleep(0.5)

        # Last-resort synthesis: fbevents.js loaded but no fbq('init') was called.
        if fb_js_loaded and not captures and ALLOW_SYNTHETIC_FBQ:
            logger.warning("[FBQ_WAIT] fbevents.js loaded but no fbq call captured. "
                           "Synthetic init ENABLED via ADLEAK_ALLOW_SYNTHETIC_FBQ=1.")
            try:
                synthetic_pid = page.evaluate("""() => {
                    if (typeof window._fbq !== 'undefined' && window._fbq) {
                        if (window._fbq._captured && window._fbq._captured.length > 0) return null;
                    }
                    if (typeof fbq !== 'undefined' && fbq.instance) {
                        if (fbq.instance.pixelsByID) {
                            var keys = Object.keys(fbq.instance.pixelsByID);
                            if (keys.length > 0) return String(keys[0]);
                        }
                    }
                    if (window.__fbq_pid) return String(window.__fbq_pid);
                    return null;
                }""")
                if not synthetic_pid:
                    # Try to recover from config bundle URL we already captured
                    synthetic_pid = self._extract_pixel_id_from_network(all_requests)
                if synthetic_pid:
                    logger.info(f"[FBQ_WAIT] Synthesizing fbq('init', '{synthetic_pid}')")
                    page.evaluate(f"""() => {{
                        try {{
                            if (typeof fbq === 'function') {{
                                fbq('init', '{synthetic_pid}');
                                fbq('track', 'PageView');
                            }}
                        }} catch (e) {{ console.error('synth init failed', e); }}
                    }}""")
                    time.sleep(2)
                    captures = page.evaluate("window.__fbq_captured || []")
                    for _c in (captures or []):
                        if isinstance(_c, dict):
                            _c["synthetic"] = True
                    if captures:
                        logger.info(f"[FBQ_WAIT] Synthetic init succeeded. Captured {len(captures)} call(s) [TAGGED synthetic].")
            except Exception as e:
                logger.debug(f"[FBQ_WAIT] Synthetic init failed: {e}")
        return captures or []

    # ------------------------------------------------------------------ #
    # META CONFIG VALIDATION
    # ------------------------------------------------------------------ #
    def _validate_pixel_via_config(self, pixel_id: str) -> dict:
        """Validate a pixel ID by fetching Meta's public config bundle."""
        result = {
            "id": pixel_id,
            "meta_config_http_status": None,
            "meta_config_size_bytes": 0,
            "meta_config_has_pixel_ref": False,
            "verdict": "unknown",
            "reason": None,
        }
        if not cffi_requests:
            result["verdict"] = "no_curl_cffi"
            result["reason"] = "curl_cffi unavailable"
            return result
        try:
            url = f"https://connect.facebook.net/signals/config/{pixel_id}"
            resp = cffi_requests.get(
                url,
                impersonate="chrome120",
                timeout=15,
                headers={"Referer": "https://www.facebook.com/"},
            )
            text = resp.text or ""
            result["meta_config_http_status"] = resp.status_code
            result["meta_config_size_bytes"] = len(text)
            result["meta_config_has_pixel_ref"] = ("pixelId" in text or "fbq" in text)
            if resp.status_code == 404:
                result["verdict"] = "invalid_format_or_dead"
                result["reason"] = "Meta config endpoint returned 404 — ID does not exist"
            elif resp.status_code == 200 and len(text) > 100_000 and result["meta_config_has_pixel_ref"]:
                result["verdict"] = "real_pixel_confirmed_by_config"
                result["reason"] = f"Full config bundle ({len(text)} bytes) with pixelId reference"
            elif resp.status_code == 200 and len(text) < 50_000:
                result["verdict"] = "ambiguous_stub_config"
                result["reason"] = f"Stub config ({len(text)} bytes) — valid format, may be unprovisioned"
            elif resp.status_code == 200:
                result["verdict"] = "real_but_thin_config"
                result["reason"] = f"HTTP 200, {len(text)} bytes — between stub and full thresholds"
            else:
                result["verdict"] = f"http_{resp.status_code}"
                result["reason"] = f"Unexpected status {resp.status_code}"
        except Exception as e:
            result["verdict"] = "exception"
            result["reason"] = f"{type(e).__name__}: {str(e)[:200]}"
        logger.info(
            f"[VALIDATE] pixel={pixel_id} verdict={result['verdict']} "
            f"(HTTP {result['meta_config_http_status']}, {result['meta_config_size_bytes']} bytes)"
        )
        return result

    def _infer_tracking_mode(self, funnel_log: dict) -> str:
        """Classify the store's tracking setup based on what the funnel observed."""
        pv = funnel_log.get("pixel_validation") or {}
        verdict = pv.get("verdict")
        pixel_fired = funnel_log.get("pixel_fired", False)
        events_observed = funnel_log.get("fbq_events_observed") or []
        capi_events = funnel_log.get("capi_events") or []
        if not funnel_log.get("detected_pixel_id"):
            return "unknown"
        if verdict == "invalid_format_or_dead":
            return "pixel_dead"
        if verdict == "ambiguous_stub_config":
            return "ambiguous"
        if verdict == "real_pixel_confirmed_by_config":
            if pixel_fired or events_observed:
                return "browser_pixel_active"
            if capi_events:
                return "capi_only_likely"
            return "capi_only_likely"
        return "unknown"

    # ------------------------------------------------------------------ #
    # Live-audit helper
    # ------------------------------------------------------------------ #
    def _analyze_fbq_captures(self, captures: list) -> dict:
        out = {
            "detected_pixel_id": None,
            "has_event_data": False,
            "has_initiate_checkout": False,
            "has_add_to_cart": False,
            "has_purchase_event": False,
            "has_shared_event_id": False,
            "has_unhashed_pii": False,
            "fbq_events_observed": [],
            "fbq_events_with_event_id": [],
        }
        out["synthetic_fbq_generated"] = False
        if not captures:
            return out
        captures = [c for c in captures if isinstance(c, dict)]
        real = [c for c in captures if not c.get("synthetic")]
        out["synthetic_fbq_generated"] = len(real) != len(captures)
        if not real:
            # Probe-generated only: never counts as merchant event coverage.
            return out
        captures = real
        out["has_event_data"] = True
        track_events = []
        purchase_events = []
        checkout_events = []
        add_to_cart_events = []
        for record in captures:
            try:
                call_type = record.get("call_type")
                args = record.get("args") or []
                if call_type == "init" and args and args[0] is not None:
                    pid = str(args[0])
                    if not out["detected_pixel_id"]:
                        out["detected_pixel_id"] = pid
                elif call_type in ("track", "trackSingle", "trackCustom", "trackSingleCustom") and len(args) >= 1:
                    if call_type in ("trackSingle", "trackSingleCustom") and len(args) >= 2:
                        evt_name = str(args[1]) if args[1] else ""
                        payload = args[2] if len(args) >= 3 and isinstance(args[2], dict) else {}
                        event_id = args[3] if len(args) >= 4 else payload.get("eventID")
                        if not out["detected_pixel_id"] and args[0]:
                            out["detected_pixel_id"] = str(args[0])
                    else:
                        evt_name = str(args[0]) if args[0] else ""
                        payload = args[1] if len(args) >= 2 and isinstance(args[1], dict) else {}
                        event_id = args[2] if len(args) >= 3 else payload.get("eventID")
                    track_events.append(evt_name)
                    if evt_name == "Purchase":
                        purchase_events.append(payload)
                    elif evt_name == "InitiateCheckout":
                        checkout_events.append(payload)
                    elif evt_name == "AddToCart":
                        add_to_cart_events.append(payload)
                    if event_id:
                        out["fbq_events_with_event_id"].append({"event": evt_name, "event_id": event_id})
                    if self._payload_has_unhashed_pii(payload):
                        out["has_unhashed_pii"] = True
            except Exception as e:
                logger.debug(f"[FBQ_ANALYZE] Skipped malformed record: {e}")
        out["has_purchase_event"] = len(purchase_events) > 0
        out["has_initiate_checkout"] = len(checkout_events) > 0
        out["has_add_to_cart"] = len(add_to_cart_events) > 0
        out["has_shared_event_id"] = len(out["fbq_events_with_event_id"]) > 0
        out["fbq_events_observed"] = track_events
        return out

    def _payload_has_unhashed_pii(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        for field in ("em", "ph", "fn", "ln", "db", "ct", "st", "zp", "country"):
            val = payload.get(field)
            if not val:
                continue
            try:
                if isinstance(val, list):
                    val = val[0] if val else None
                if not isinstance(val, str):
                    continue
                if RE_HEX64.match(val):
                    continue
                if field == "em" and RE_EMAIL_RAW.match(val):
                    return True
                if field == "ph" and RE_PHONE_RAW.match(val):
                    return True
                if field in ("fn", "ln", "ct", "st") and len(val) < 30 and not RE_HEX64.match(val):
                    return True
            except Exception:
                continue
        return False

    def _get_advanced_init_script(self):
        return """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', {
get: () => [
{ name: "Chrome PDF Plugin", filename: "internal-pdf-viewer" },
{ name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai" },
{ name: "Native Client", filename: "internal-nacl-plugin" }
]
});
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(screen, 'width', { get: () => 1920 });
Object.defineProperty(screen, 'height', { get: () => 1080 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
if (parameter === 37445) return 'Intel Inc.';
if (parameter === 37446) return 'Intel Iris OpenGL Engine';
return originalGetParameter.call(this, parameter);
};
const originalCreateOscillator = AudioContext.prototype.createOscillator;
AudioContext.prototype.createOscillator = function() {
const osc = originalCreateOscillator.call(this);
osc.frequency.value += Math.random() * 0.01;
return osc;
};
const originalPermissionsQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (parameters) => (
parameters.name === 'notifications' ?
Promise.resolve({ state: Notification.permission }) :
originalPermissionsQuery(parameters)
);
"""

    def _score_pixel_probability(self, pid: str, context_source: str) -> float:
        if not pid or not pid.isdigit():
            return 0.0
        length = len(pid)
        if length < 10:
            return 0.1
        if 10 <= length <= 16:
            base_score = 0.8
            if context_source == "FBQ_INIT":
                base_score = 0.95
            if pid.startswith("17"):
                base_score -= 0.1
            return min(1.0, base_score)
        return 0.0

    # ------------------------------------------------------------------ #
    # MULTI-PIXEL HARVEST + TEALIUM iQ RESOLVER + EXPLICIT CONSENT
    # ------------------------------------------------------------------ #
    def _attribute_events_per_pixel(self, merged_log: dict) -> dict:
        """Per-pixel event coverage. A site with two pixels can leak on one only."""
        per = {}
        def slot(pid):
            pid = str(pid or "unknown")
            return per.setdefault(pid, {
                "pixel_id": pid, "events": [], "event_ids": [],
                "has_add_to_cart": False, "has_initiate_checkout": False,
                "has_purchase_event": False, "has_unhashed_pii": False,
                "sources": [],
            })
        for e in (merged_log.get("meta_tr_events") or []):
            s = slot(e.get("pixel_id"))
            ev = e.get("event")
            if ev and ev not in s["events"]:
                s["events"].append(ev)
            if "network_tr" not in s["sources"]:
                s["sources"].append("network_tr")
            for k, flag in (("AddToCart","has_add_to_cart"),
                            ("InitiateCheckout","has_initiate_checkout"),
                            ("Purchase","has_purchase_event")):
                if ev == k:
                    s[flag] = True
        for c in (merged_log.get("fbq_raw_calls") or []):
            if not isinstance(c, dict):
                continue
            a = c.get("args") or []
            ct = c.get("call_type")
            pid = None; ev = None; payload = {}; eid = None
            if ct == "init" and a:
                pid = a[0]
            elif ct in ("trackSingle", "trackSingleCustom") and len(a) >= 2:
                pid, ev = a[0], a[1]
                payload = a[2] if len(a) >= 3 and isinstance(a[2], dict) else {}
                eid = a[3] if len(a) >= 4 else payload.get("eventID")
            elif ct in ("track", "trackCustom") and a:
                pid = merged_log.get("detected_pixel_id")
                ev = a[0]
                payload = a[1] if len(a) >= 2 and isinstance(a[1], dict) else {}
                eid = a[2] if len(a) >= 3 else payload.get("eventID")
            s = slot(pid)
            if "fbq_capture" not in s["sources"]:
                s["sources"].append("fbq_capture")
            if ev:
                if ev not in s["events"]:
                    s["events"].append(ev)
                for k, flag in (("AddToCart","has_add_to_cart"),
                                ("InitiateCheckout","has_initiate_checkout"),
                                ("Purchase","has_purchase_event")):
                    if ev == k:
                        s[flag] = True
            if eid and eid not in s["event_ids"]:
                s["event_ids"].append(eid)
            try:
                if self._payload_has_unhashed_pii(payload):
                    s["has_unhashed_pii"] = True
            except Exception:
                pass
        for e in (merged_log.get("detected_pixel_ids") or []):
            s = slot(e.get("pixel_id"))
            for sc in (e.get("sources") or []):
                if sc not in s["sources"]:
                    s["sources"].append(sc)
        logger.info(f"[PER_PIXEL] {json.dumps(per, default=str)[:2000]}")
        return per

    def _apply_operator_session(self, page, merged_log: dict, runner_name: str) -> dict:
        """
        Optional operator-supplied authenticated session. Never credentials in code.
        ADLEAK_STORAGE_STATE points to a Playwright storage_state JSON the operator
        produced from their OWN test account. Cookies are injected; nothing else.
        """
        out = {"applied": False, "reason": None, "cookie_count": 0}
        path = os.environ.get("ADLEAK_STORAGE_STATE", "").strip()
        if not path:
            out["reason"] = "no_session_supplied"
            return out
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            cookies = data.get("cookies") or []
            if cookies:
                page.context.add_cookies(cookies)
                out["applied"] = True
                out["cookie_count"] = len(cookies)
                logger.info(f"[SESSION/{runner_name}] injected {len(cookies)} operator cookie(s)")
            else:
                out["reason"] = "no_cookies_in_state"
        except Exception as e:
            out["reason"] = f"{type(e).__name__}: {str(e)[:120]}"
            logger.warning(f"[SESSION/{runner_name}] session load failed: {out['reason']}")
        merged_log["operator_session"] = out
        return out

    def _classify_checkout_blocker(self, page, merged_log: dict, runner_name: str) -> dict:
        """Evidence-driven blocker classification. Multi-platform, no hardcoding."""
        snap = self._snapshot_gate(page)
        url = str(snap.get("url") or page.url or "").lower()
        body = str(snap.get("body_snippet", "")).lower()
        btns = snap.get("buttons") or []
        inputs = snap.get("inputs") or []
        out = {"kind": None, "url": url, "guest_controls": [], "auth_markers": []}
        for _ex in (merged_log.get("observed_exits") or []):
            _eu = str(_ex.get("to", "")).lower()
            if any(k in _eu for k in ("/login", "/signin", "/sign-in", "login_challenge", "/oauth", "/sso")):
                if "auth_exit_observed" not in out["auth_markers"]:
                    out["auth_markers"].append("auth_exit_observed")
                out["auth_exit_url"] = _ex.get("to")
        if any(k in url for k in ("/login", "/signin", "/sign-in", "/auth",
                                  "login_challenge", "/oauth", "/sso", "/session")):
            out["auth_markers"].append("auth_url")
        if any(f.get("type") == "password" for f in inputs):
            out["auth_markers"].append("password_field")
        if any(k in body for k in ("sign in", "log in", "create an account",
                                   "enter your password", "email address")):
            out["auth_markers"].append("auth_text")
        grx = re.compile(r"guest|without an account|no account|continue as guest|"
                         r"checkout as guest|skip (sign|log)", re.I)
        for x in btns:
            t = str(x.get("text", ""))
            if grx.search(t) and not x.get("disabled"):
                out["guest_controls"].append({"idx": x["idx"], "text": t})
        if any(k in body for k in ("captcha", "verify you are human", "are you a robot")):
            out["kind"] = "captcha"
        elif out["auth_markers"]:
            out["kind"] = "auth_wall_with_guest" if out["guest_controls"] else "auth_wall"
        elif any(k in body for k in ("minimum spend", "minimum order", "below the minimum")):
            out["kind"] = "minimum_spend"
        elif "out of stock" in body or "delivery unavailable" in body:
            out["kind"] = "stock_or_delivery"
        out["guest_available"] = bool(out["guest_controls"])
        merged_log.setdefault("checkout_blockers", []).append(dict(out, ts=time.time()))
        logger.info(f"[BLOCKER/{runner_name}] {json.dumps(out, default=str)[:900]}")
        return out

    def _attempt_guest_checkout(self, page, merged_log: dict, runner_name: str, blocker: dict) -> bool:
        """Use a guest path when the merchant offers one. Inventory-driven."""
        if not blocker.get("guest_controls"):
            return False
        flow = ("checkout", "/basket", "/bag", "/cart", "/trolley", "/payment", "demandware")
        for g in blocker["guest_controls"][:2]:
            before = page.url
            try:
                loc = page.locator('button, a[role="button"], [role="button"], input[type="submit"]').nth(g["idx"])
                try:
                    with page.expect_navigation(timeout=12000):
                        loc.evaluate("(el) => el.click()")
                except Exception:
                    loc.evaluate("(el) => el.click()")
                    time.sleep(4)
            except Exception as e:
                logger.debug(f"[GUEST/{runner_name}] click failed: {e}")
                continue
            after = self._snapshot_gate(page)
            nu = str(after.get("url") or "")
            ok = any(m in nu.lower() for m in flow)
            merged_log.setdefault("guest_attempts", []).append({
                "control": g["text"], "url_before": before, "url_after": nu,
                "stayed_in_flow": ok, **after,
            })
            logger.info(f"[GUEST/{runner_name}] '{g['text']}' -> {nu} in_flow={ok}")
            if ok:
                return True
            try:
                page.goto(before, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
            except Exception:
                pass
        return False

    def _capture_boundary_evidence(self, page, merged_log: dict, all_requests: list,
                                   runner_name: str, label: str) -> dict:
        """
        Capture what fires AT the blocker (SSO/login pages often carry their own
        pixels) BEFORE restoring. This is real evidence we previously discarded.
        """
        snap = self._snapshot_gate(page)
        self._record_meta_delta(merged_log, all_requests, page, label)
        caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=12)
        self._merge_funnel_captures(merged_log, caps, label)
        rec = {"boundary": label, "url": snap.get("url"), "title": snap.get("title"),
               "markers": snap.get("markers", {}), "buttons": snap.get("buttons", [])[:15]}
        merged_log.setdefault("boundary_evidence", []).append(rec)
        logger.info(f"[BOUNDARY/{runner_name}] {label} url={snap.get('url')} "
                    f"buttons={json.dumps([x.get('text') for x in rec['buttons']])[:400]}")
        return rec

    def _capture_payment_stage(self, page, merged_log: dict, all_requests: list,
                               runner_name: str) -> dict:
        """
        Prove we reached the payment stage and record the provider + field surface.
        NEVER submits payment. NEVER enters card data.
        """
        out = {"reached": False, "providers": [], "card_surface": [], "url": page.url}
        try:
            probe = page.evaluate("""() => {
                const srcs = Array.from(document.querySelectorAll('iframe[src]')).map(f => f.src);
                const html = document.documentElement.innerHTML.toLowerCase();
                const names = ['stripe','adyen','braintree','paypal','klarna','checkout.com',
                               'worldpay','opayo','sagepay','square','mollie','cybersource'];
                const fields = Array.from(document.querySelectorAll('input')).map(i => ({
                    name: i.name||'', id: i.id||'', ac: i.getAttribute('autocomplete')||'',
                    type: i.type||''
                })).filter(f => /card|cc-|cvc|cvv|expiry|pan/i.test(f.name+f.id+f.ac));
                return {
                    iframes: srcs.slice(0, 12),
                    providers: names.filter(n => html.includes(n) || srcs.some(s => s.toLowerCase().includes(n))),
                    card_fields: fields.slice(0, 10),
                };
            }""") or {}
            out["providers"] = probe.get("providers", [])
            out["card_surface"] = probe.get("card_fields", [])
            out["iframes"] = probe.get("iframes", [])
        except Exception as e:
            out["probe_error"] = str(e)
        snap = self._snapshot_gate(page)
        m = snap.get("markers", {})
        out["url"] = snap.get("url")
        out["markers"] = m
        _url_l = str(out["url"]).lower()
        _hard_surface = bool(
            out["card_surface"]
            or any(re.search(r"stripe|adyen|braintree|paypal|klarna|worldpay|opayo|mollie|cybersource", s, re.I)
                   for s in (out.get("iframes") or []))
            or m.get("has_pay_now")
        )
        _url_surface = any(k in _url_l for k in ("/payment", "/billing", "/checkout/payment", "/basket/payment"))
        out["reached"] = bool(_hard_surface or (_url_surface and m.get("has_continue_payment")))
        out["provider_mentions_only"] = bool(out["providers"] and not _hard_surface and not _url_surface)
        merged_log["payment_stage"] = out
        self._record_meta_delta(merged_log, all_requests, page, "payment_stage")
        caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=20)
        self._merge_funnel_captures(merged_log, caps, "payment_stage")
        logger.info(f"[PAYMENT/{runner_name}] reached={out['reached']} "
                    f"providers={out['providers']} card_fields={len(out['card_surface'])} url={out['url']}")
        return out


    def _harvest_all_pixel_ids(self, all_requests: list, merged_log: dict) -> list:
        """Advertisers run more than one pixel. Report every ID with its provenance."""
        found = {}

        def add(pid, src):
            pid = str(pid)
            if not pid.isdigit() or not (10 <= len(pid) <= 16):
                return
            e = found.setdefault(pid, {"pixel_id": pid, "sources": [], "hits": 0})
            if src not in e["sources"]:
                e["sources"].append(src)
            e["hits"] += 1

        for r in all_requests:
            if not isinstance(r, dict):
                continue
            u = str(r.get("url", ""))
            m = RE_CONFIG_BUNDLE.search(u)
            if m:
                add(m.group(1), "network_config_bundle")
            if "facebook.com/tr" in u:
                m2 = RE_TR_PIXEL_ID.search(u)
                if m2:
                    add(m2.group(1), "network_tr")
            m3 = RE_CAPI_URL.search(u)
            if m3:
                add(m3.group(1), "capi_graph")
        for c in (merged_log.get("fbq_raw_calls") or []):
            if not isinstance(c, dict):
                continue
            a = c.get("args") or []
            ct = c.get("call_type")
            if not a:
                continue
            if ct == "init":
                add(a[0], "fbq_init")
            elif ct in ("trackSingle", "trackSingleCustom"):
                add(a[0], "fbq_track_single")
        out = sorted(found.values(), key=lambda x: (-x["hits"], x["pixel_id"]))
        logger.info(f"[PIXEL_SET] {json.dumps(out)}")
        return out

    def _resolve_tealium_pixels(self, all_requests: list, referer_url: str) -> list:
        """
        Static, browser-free Meta pixel extraction from Tealium iQ tag files.
        URLs are derived from what the page ACTUALLY loaded — never guessed.
        Enterprise stacks (Argos/Sainsburys class) hide pixels in utag.N.js.
        """
        if not cffi_requests:
            return []
        urls, seen = [], set()
        for r in all_requests:
            if not isinstance(r, dict):
                continue
            u = str(r.get("url", ""))
            if "utag." not in u or ".js" not in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            urls.append(u)
        if not urls:
            return []
        logger.info(f"[TEALIUM] {len(urls)} tag file(s) discovered from live traffic")
        out = {}
        for u in urls[:12]:
            try:
                resp = cffi_requests.get(u, impersonate="chrome120", timeout=8,
                                         headers={"Referer": referer_url})
                if resp.status_code != 200:
                    continue
                body = resp.text or ""
                low = body.lower()
                if not any(k in low for k in ("fbq", "facebook", "pixel")):
                    continue
                cands = set(RE_FBQ_INIT.findall(body))
                for m in re.finditer(r"\b(\d{15,16})\b", body):
                    ctx = low[max(0, m.start() - 220):m.start() + 220]
                    if any(k in ctx for k in ("fbq", "facebook", "pixel")):
                        cands.add(m.group(1))
                for pid in cands:
                    sc = self._score_pixel_probability(pid, "TEALIUM_TAG")
                    if sc <= 0.5:
                        continue
                    e = out.setdefault(pid, {"pixel_id": pid, "score": sc, "sources": []})
                    if u not in e["sources"]:
                        e["sources"].append(u)
                    logger.info(f"[TEALIUM] pixel={pid} file={u.split('/')[-1].split('?')[0]}")
            except Exception as e:
                logger.debug(f"[TEALIUM] fetch failed {u[:80]}: {e}")
        return sorted(out.values(), key=lambda x: -x["score"])

    def _handle_consent(self, page, merged_log: dict, runner_name: str) -> dict:
        """
        Grant CMP consent using the page's own control inventory (index-based).
        Proven causal on consent-gated stacks: the grant releases the tag
        manager's Meta tag. Verified against dataLayer, never assumed.
        """
        out = {"detected": None, "granted": False, "control": None, "verified": False}
        snap = self._snapshot_gate(page)
        btns = snap.get("buttons") or []
        texts = [str(x.get("text", "")).strip().lower() for x in btns]
        classes = " ".join(str(x.get("cls", "")) for x in btns).lower()
        cmp_context = (
            any(t in ("required only", "let me choose", "reject all", "manage preferences") for t in texts)
            or "onetrust" in classes or "cookie-setting-link" in classes
            or "cookiebot" in classes
        )
        pats = [
            (r"^accept all", "onetrust"),
            (r"^allow all", "generic"),
            (r"^continue and accept$", "onetrust"),
            (r"^accept all cookies$", "generic"),
            (r"^i accept$", "generic"),
            (r"^agree$", "generic"),
            (r"^accept$", "generic"),
        ]
        pick = None
        for pat, vendor in pats:
            for x in btns:
                if x.get("disabled"):
                    continue
                t = str(x.get("text", "")).strip().lower()
                if re.match(pat, t) and (vendor == "onetrust" or cmp_context):
                    pick = (x, vendor)
                    break
            if pick:
                break
        if pick:
            x, vendor = pick
            out["detected"], out["control"] = vendor, x.get("text")
            try:
                loc = page.locator('button, a[role="button"], [role="button"], input[type="submit"]').nth(x["idx"])
                try:
                    loc.click(timeout=3000)
                except Exception:
                    loc.evaluate("(el) => el.click()")
                out["granted"] = True
                time.sleep(2.5)
            except Exception as e:
                logger.debug(f"[CONSENT/{runner_name}] inventory click failed: {e}")
        if not out["granted"]:
            for sel in ("#onetrust-accept-btn-handler",
                        "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
                        "#CybotCookiebotDialogBodyButtonAccept"):
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=800):
                        out["detected"], out["control"] = "cmp_id", sel
                        try:
                            loc.click(timeout=2500)
                        except Exception:
                            loc.evaluate("(el) => el.click()")
                        out["granted"] = True
                        time.sleep(2.5)
                        break
                except Exception:
                    continue
        try:
            st = page.evaluate("""() => {
                const dl = Array.isArray(window.dataLayer) ? window.dataLayer : [];
                let seen = 0, granted = false;
                for (const e of dl) {
                    try {
                        const s = JSON.stringify(e);
                        if (s && s.indexOf('"consent"') !== -1) {
                            seen++;
                            if (s.indexOf('"granted"') !== -1) granted = true;
                        }
                    } catch (err) {}
                }
                return {consent_entries: seen, any_granted: granted,
                        banner_present: !!document.querySelector('#onetrust-banner-sdk, #CybotCookiebotDialog')};
            }""") or {}
            _post = self._snapshot_gate(page)
            _pt = [str(x.get("text", "")).strip().lower() for x in (_post.get("buttons") or [])]
            out["banner_dismissed"] = not any(
                t in ("required only", "let me choose", "reject all", "continue and accept")
                or t.startswith("accept all") or t.startswith("allow all")
                for t in _pt
            )
            try:
                _ck = page.evaluate("() => (document.cookie.match(/OptanonConsent=([^;]*)/)||[])[1] || ''") or ""
                import urllib.parse as _up
                _dec = _up.unquote(_ck)
                out["optanon_groups"] = (_dec.split("groups=")[1].split("&")[0] if "groups=" in _dec else None)
                out["cookie_granted"] = bool(out["optanon_groups"] and ":1" in out["optanon_groups"])
            except Exception:
                out["cookie_granted"] = False
            out["verified"] = bool(out["granted"] and (st.get("any_granted") or out["banner_dismissed"] or out["cookie_granted"]))
            out["state"] = st
        except Exception as e:
            out["state_error"] = str(e)
        if out["granted"]:
            logger.info(f"[CONSENT/{runner_name}] {out['detected']} via {out['control']!r} "
                        f"verified={out['verified']} state={json.dumps(out.get('state', {}))}")
            merged_log.setdefault("consent_events", []).append(dict(out, ts=time.time(), url=page.url))
        else:
            logger.info(f"[CONSENT/{runner_name}] no CMP control matched "
                        f"(cmp_context={cmp_context}, buttons={len(btns)})")
        return out


    def _resolve_gtm_container_pixels(self, gtm_id: str, referer_url: str) -> list[tuple[str, float]]:
        if not cffi_requests:
            return []
        candidates = []
        try:
            url = f"https://www.googletagmanager.com/gtm.js?id={gtm_id}"
            headers = {
                "User-Agent": random.choice(self.uas),
                "Referer": referer_url,
                "Accept": "*/*",
                "Sec-Fetch-Dest": "script",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site"
            }
            resp = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=10)
            if resp.status_code == 200:
                body = resp.text
                for m in RE_FBQ_INIT.findall(body):
                    score = self._score_pixel_probability(m, "FBQ_INIT")
                    if score > 0.5:
                        candidates.append((m, score))
                for jm in RE_PIXEL_JSON.findall(body):
                    score = self._score_pixel_probability(jm, "JSON_CONFIG")
                    if score > 0.5:
                        candidates.append((jm, score))
                for mm in RE_GTM_MINIFIED_PIXEL.findall(body):
                    score = self._score_pixel_probability(mm, "MINIFIED_KEY")
                    if score > 0.5:
                        candidates.append((mm, score))
                for vm in RE_VAR_PIXEL_ASSIGN.findall(body):
                    score = self._score_pixel_probability(vm, "VAR_ASSIGN")
                    if score > 0.5:
                        candidates.append((vm, score))
                dl_pattern = re.compile(r'\{\s*"value"\s*:\s*"(\d{10,16})"\s*,\s*"type"\s*:\s*"constant"\s*\}', re.IGNORECASE)
                dl_matches = dl_pattern.findall(body)
                for dm in dl_matches:
                    idx = body.find(f'"value":"{dm}"')
                    if idx != -1:
                        context_chunk = body[max(0, idx-200):min(len(body), idx+200)].lower()
                        if "facebook" in context_chunk or "pixel" in context_chunk or "fbq" in context_chunk:
                            score = self._score_pixel_probability(dm, "DATA_LAYER_CONTEXT")
                            if score > 0.4:
                                candidates.append((dm, score))
                # NEW: vtp_map structure (multi-region Meta Pixel lookup tables)
                # Pattern: ["map","key","us","value","1689016458013442"]
                vtp_map_pattern = re.compile(
                    r'\["map","key","([a-z]{2,3})","value","(\d{15,16})"\]'
                )
                for region, pid in vtp_map_pattern.findall(body):
                    score = self._score_pixel_probability(pid, "VTP_MAP")
                    # vtp_map entries are unambiguous region→pixel mappings
                    score = min(1.0, score + 0.1)
                    if score > 0.5:
                        candidates.append((pid, score))
                    logger.info(f"[GTM_RESOLVE] vtp_map region={region} pixel={pid}")
        except Exception as e:
            logger.debug(f"GTM Resolution failed for {gtm_id}: {e}")
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def _universal_asset_scan(self, html_content: str, domain: str) -> list[tuple[str, float]]:
        candidates = []
        if not cffi_requests:
            return []
        script_tags = re.findall(r'<script[^>]*src=["\']([^"\']+)["\'][^>]*>', html_content, re.IGNORECASE)
        link_tags = re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html_content, re.IGNORECASE)
        asset_urls = set()
        for url in script_tags + link_tags:
            if url.startswith('//'):
                full_url = f"https:{url}"
            elif url.startswith('/'):
                full_url = f"https://{domain}{url}"
            elif url.startswith('http'):
                full_url = url
            else:
                continue
            if '.js' in full_url.lower() or '.css' in full_url.lower():
                asset_urls.add(full_url)
        logger.info(f"[UNIVERSAL_SCAN] Found {len(asset_urls)} candidate assets.")
        proxy_cfg = self.tor_daemon.get_proxy_config()
        for asset_url in list(asset_urls)[:10]:
            try:
                resp = cffi_requests.get(asset_url, impersonate="chrome120", timeout=8, proxies=proxy_cfg)
                if resp.status_code == 200:
                    body = resp.text.lower()
                    for m in RE_FBQ_INIT.findall(body):
                        score = self._score_pixel_probability(m, "ASSET_FBQ")
                        if score > 0.5:
                            candidates.append((m, score))
                    for m in RE_PIXEL_JSON.findall(body):
                        score = self._score_pixel_probability(m, "ASSET_JSON")
                        if score > 0.5:
                            candidates.append((m, score))
                    for m in RE_VAR_PIXEL_ASSIGN.findall(body):
                        score = self._score_pixel_probability(m, "ASSET_VAR")
                        if score > 0.5:
                            candidates.append((m, score))
            except Exception as e:
                logger.debug(f"[UNIVERSAL_SCAN] Failed {asset_url}: {e}")
        best = {}
        for pid, sc in candidates:
            if pid not in best or sc > best[pid]:
                best[pid] = sc
        return sorted(best.items(), key=lambda x: x[1], reverse=True)

    def _fetch_html_via_managed_tor(self, url: str, max_attempts: int = 3) -> tuple[str | None, str | None]:
        if not cffi_requests:
            return None, "no_curl_cffi"
        proxy_cfg = self.tor_daemon.get_proxy_config()
        for i in range(max_attempts):
            try:
                resp = cffi_requests.get(url, impersonate="chrome120", timeout=20, proxies=proxy_cfg)
                if resp.status_code == 200:
                    body = resp.text
                    if "challenges.cloudflare.com" in body or "<title>Just a moment..." in body:
                        logger.warning(f"[TOR_FETCH] Blocked on attempt {i+1}. Rotating...")
                        self.tor_daemon.rotate_circuit()
                        time.sleep(2)
                        continue
                    return body, None
                else:
                    logger.warning(f"[TOR_FETCH] Status {resp.status_code} on attempt {i+1}. Rotating...")
                    self.tor_daemon.rotate_circuit()
                    time.sleep(2)
            except Exception as e:
                logger.error(f"[TOR_FETCH] Error: {e}. Rotating...")
                self.tor_daemon.rotate_circuit()
                time.sleep(2)
        return None, "tor_fetch_failed_all_attempts"

    # ------------------------------------------------------------------ #
    # Attempt 1: Camoufox
    # ------------------------------------------------------------------ #
    def _probe_with_camoufox(self, url: str) -> dict | None:
        if not CAMOUFOX_AVAILABLE:
            return None
        network_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "detected_pixel_id": None, "gtm_id": None,
            "engine_used": "camoufox", "blocked_status": None,
            "has_event_data": False, "has_initiate_checkout": False,
            "has_add_to_cart": False, "has_purchase_event": False,
            "has_shared_event_id": False, "has_unhashed_pii": False,
            "fbq_events_observed": [],
        }
        try:
            with Camoufox(headless=False) as browser:
                context = browser.new_context()
                try:
                    context.add_init_script(FBQ_INTERCEPTOR_JS)
                except Exception as e:
                    logger.debug(f"[CAMOUFOX] fbq interceptor install skipped: {e}")
                page = context.new_page()
                requests_log = []

                def on_response(response):
                    req_url = response.url
                    status = response.status
                    requests_log.append({"url": req_url, "method": response.request.method, "status": status})
                    if "facebook.com/tr" in req_url:
                        network_log["pixel_fired"] = True
                        try:
                            if response.request.method in ("POST", "GET") and response.request.post_data:
                                network_log.setdefault("capi_events", []).append({
                                    "url": req_url, "event_name": "client_event",
                                    "raw_body": response.request.post_data[:2000],
                                })
                        except Exception:
                            pass
                    if "graph.facebook.com" in req_url and "/events" in req_url:
                        match = RE_CAPI_URL.search(req_url)
                        if match:
                            pid = match.group(1)
                            event_entry = {"url": req_url, "event_name": "server_event", "pixel_id": pid}
                            try:
                                if response.request.post_data:
                                    event_entry["raw_body"] = response.request.post_data[:2000]
                            except Exception:
                                pass
                            network_log["capi_events"].append(event_entry)
                            if not network_log.get("detected_pixel_id"):
                                network_log["detected_pixel_id"] = pid
                    if status == 200:
                        ct = response.headers.get("content-type", "")
                        if "javascript" in ct or "html" in ct:
                            try:
                                body = response.text()
                                gtm_m = RE_GTM_ID.search(body)
                                if gtm_m and not network_log.get("gtm_id"):
                                    network_log["gtm_id"] = gtm_m.group(0)
                                fbq_m = RE_FBQ_INIT.search(body)
                                if fbq_m and not network_log.get("detected_pixel_id"):
                                    pid = fbq_m.group(1)
                                    if self._score_pixel_probability(pid, "STREAM") > 0.5:
                                        network_log["detected_pixel_id"] = pid
                                        network_log["pixel_fired"] = True
                            except: pass

                page.on("response", on_response)
                logger.info(f"[CAMOUFOX] Loading {url}...")
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)
                content = page.content()
                if "challenges.cloudflare.com" in content or "<title>Just a moment..." in content:
                    network_log["blocked_status"] = "CF_CHALLENGE_DETECTED"
                    logger.warning("[CAMOUFOX] Blocked by Cloudflare Challenge.")
                    context.close()
                    return network_log
                # Network config bundle extraction FIRST (survives sandbox)
                if not network_log.get("detected_pixel_id"):
                    net_pid = self._extract_pixel_id_from_network(requests_log)
                    if net_pid:
                        network_log["detected_pixel_id"] = net_pid
                        network_log["pixel_fired"] = True
                        logger.info(f"[CAMOUFOX] Pixel from network: {net_pid}")
                # fbq capture for event payloads
                captures = self._wait_for_fbq_and_capture(page, requests_log, timeout=10)
                enriched = self._analyze_fbq_captures(captures)
                for k, v in enriched.items():
                    if v not in (None, False, [], ""):
                        network_log[k] = v
                    elif k not in network_log:
                        network_log[k] = v
                logger.info(f"[CAMOUFOX] Captured {len(captures)} fbq call(s); "
                            f"pixel={network_log.get('detected_pixel_id')}, "
                            f"events={enriched.get('fbq_events_observed')}")
                if not network_log.get("detected_pixel_id"):
                    dom_pid = page.evaluate("""() => {
                        if (typeof fbq !== 'undefined' && fbq.queue) {
                            for(let i=0; i<fbq.queue.length; i++) {
                                let item = fbq.queue[i];
                                if(item[0] === 'init' && item[1]) return String(item[1]);
                            }
                        }
                        return null;
                    }""")
                    if dom_pid and self._score_pixel_probability(dom_pid, "DOM") > 0.4:
                        network_log["detected_pixel_id"] = dom_pid
                        network_log["pixel_fired"] = True
                network_log["requests"] = requests_log
                context.close()
                return network_log
        except Exception as e:
            logger.error(f"[CAMOUFOX] Error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Attempt 1.5: invisible_playwright (C++-level Firefox patches)
    # ------------------------------------------------------------------ #
    def _probe_with_invisible(self, url: str) -> dict:
        """
        Firefox engine with C++-level fingerprint patches (not JS overrides).
        This is the only engine that has passed Cloudflare Bot Management on
        WebstaurantStore-class sites during diagnostics. Uses networkidle wait
        so GTM-injected Facebook requests are captured before page closes.
        """
        network_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "detected_pixel_id": None, "gtm_id": None,
            "engine_used": "invisible_playwright", "blocked_status": None,
            "has_event_data": False, "has_initiate_checkout": False,
            "has_add_to_cart": False, "has_purchase_event": False,
            "has_shared_event_id": False, "has_unhashed_pii": False,
            "fbq_events_observed": [],
        }
        if not INVISIBLE_AVAILABLE:
            network_log["blocked_status"] = "INVISIBLE_NOT_INSTALLED"
            return network_log
        try:
            with InvisiblePlaywright(seed=42) as browser:
                page = browser.new_page()
                try:
                    page.add_init_script(FBQ_INTERCEPTOR_JS)
                except Exception as e:
                    logger.debug(f"[INVISIBLE] fbq interceptor install skipped: {e}")
                requests_log = []

                def on_request(req):
                    requests_log.append({"url": req.url, "method": req.method, "status": None})

                def on_response(response):
                    req_url = response.url
                    # backfill status on the matching request entry
                    for r in reversed(requests_log):
                        if r["url"] == req_url:
                            r["status"] = response.status
                            break
                    if "facebook.com/tr" in req_url:
                        network_log["pixel_fired"] = True
                        try:
                            if response.request.post_data:
                                network_log["capi_events"].append({
                                    "url": req_url, "event_name": "client_event",
                                    "raw_body": response.request.post_data[:2000],
                                })
                        except Exception:
                            pass
                    if "graph.facebook.com" in req_url and "/events" in req_url:
                        match = RE_CAPI_URL.search(req_url)
                        if match:
                            pid = match.group(1)
                            network_log["capi_events"].append(
                                {"url": req_url, "event_name": "server_event", "pixel_id": pid}
                            )
                            if not network_log.get("detected_pixel_id"):
                                network_log["detected_pixel_id"] = pid

                page.on("request", on_request)
                page.on("response", on_response)
                logger.info(f"[INVISIBLE] Navigating to {url}...")
                # Use 'domcontentloaded' first, then attempt to reach a reasonable state.
                # 'networkidle' is too strict for sites with persistent popups or analytics beacons.
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except Exception as e:
                    logger.warning(f"[INVISIBLE] Initial navigation issue: {e}. Proceeding to popup handling.")
                    resp = None
                # Wait a brief moment for initial JS to execute
                time.sleep(2)
                # Dismiss any popups that appeared
                self._dismiss_popups(page)
                # Now try to wait for network to settle, but do not fail the whole probe if it times out
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    logger.info("[INVISIBLE] networkidle not reached after popup dismissal (this is acceptable). Proceeding with current state.")
                html = page.content()
                logger.info(f"[INVISIBLE] Loaded status={resp.status if resp else None} html_len={len(html)}")
                # Strict Cloudflare detection — challenges.cloudflare.com alone is a false positive
                title_lower = (page.title() or "").lower()
                blocked_markers = [
                    "just a moment",
                    "checking your browser",
                    "enable javascript and cookies to continue",
                    "cf-browser-verification",
                ]
                cf_header = None
                try:
                    cf_header = resp.headers.get("cf-mitigated") if resp else None
                except Exception:
                    pass
                if cf_header == "challenge" or any(m in title_lower for m in blocked_markers):
                    network_log["blocked_status"] = "CF_CHALLENGE"
                    logger.warning(f"[INVISIBLE] Cloudflare challenge page detected (title='{page.title()}')")
                    return network_log
                # Network-level pixel extraction (survives GTM injection)
                if not network_log.get("detected_pixel_id"):
                    net_pid = self._extract_pixel_id_from_network(requests_log)
                    if net_pid:
                        network_log["detected_pixel_id"] = net_pid
                        network_log["pixel_fired"] = True
                        logger.info(f"[INVISIBLE] Pixel from network: {net_pid}")
                # fbq capture for event payloads
                captures = self._wait_for_fbq_and_capture(page, requests_log, timeout=15)
                enriched = self._analyze_fbq_captures(captures)
                for k, v in enriched.items():
                    if v not in (None, False, [], ""):
                        network_log[k] = v
                    elif k not in network_log:
                        network_log[k] = v
                logger.info(f"[INVISIBLE] Captured {len(captures)} fbq call(s); "
                            f"pixel={network_log.get('detected_pixel_id')}, "
                            f"events={enriched.get('fbq_events_observed')}")
                m_gtm = RE_GTM_ID.search(html)
                if m_gtm:
                    network_log["gtm_id"] = m_gtm.group(0)
                # Inline HTML fallback
                fbq_m = RE_FBQ_INIT.search(html)
                if fbq_m and not network_log.get("detected_pixel_id"):
                    pid = fbq_m.group(1)
                    if self._score_pixel_probability(pid, "HTML_INLINE") > 0.5:
                        network_log["detected_pixel_id"] = pid
                        network_log["pixel_fired"] = True
                        logger.info(f"[INVISIBLE] Found Pixel in Inline HTML: {pid}")
                if network_log.get("has_event_data"):
                    logger.info(f"[INVISIBLE] Event coverage: "
                                f"ATC={network_log.get('has_add_to_cart')}, "
                                f"IC={network_log.get('has_initiate_checkout')}, "
                                f"PUR={network_log.get('has_purchase_event')}, "
                                f"dedup={network_log.get('has_shared_event_id')}, "
                                f"raw_PII={network_log.get('has_unhashed_pii')}")
                network_log["requests"] = requests_log
                return network_log
        except Exception as e:
            logger.error(f"[INVISIBLE] Critical Error: {e}")
            network_log["blocked_status"] = "ERROR"
            return network_log

    def _dismiss_popups(self, page) -> None:
        """
        Attempts to click common popup dismissal selectors.
        This is critical for sites with cookie consent modals, newsletter popups,
        or location selectors that block networkidle.
        """
        popup_selectors = [
            # Cookie consent (OneTrust, Cookiebot, Shopify)
            "button:has-text('Accept')", "button:has-text('Accept All')",
            "button:has-text('Agree')", "button:has-text('Allow All')",
            "#onetrust-accept-btn-handler", ".cc-btn", "[data-cookiefirst-action='accept']",
            # Newsletter/Modal close buttons
            "button[aria-label='Close']", "button[aria-label='Dismiss']",
            ".modal__close", ".popup-close", ".close-modal",
            "[data-dismiss='modal']", ".needsclick[aria-label='Close']",
            # Location/Region selectors
            "button:has-text('Stay')", "button:has-text('Continue')",
            "button:has-text('Confirm')", "button:has-text('No Thanks')",
        ]
        for selector in popup_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1000):
                    btn.click(timeout=3000)
                    logger.info(f"[POPUP] Dismissed: {selector}")
                    time.sleep(0.5)  # Brief pause for popup animation
            except Exception:
                continue

    # ------------------------------------------------------------------ #
    # TIER 0: Shopify Web Pixels Manager Static Parser
    # ------------------------------------------------------------------ #
    def _probe_with_shopify_sandbox(self, url: str) -> dict | None:
        """
        Statically parses Shopify's `webPixelsConfigList` to extract the Pixel ID.
        Searches for the facebook_pixel configuration type, not a hardcoded app ID.
        """
        if not cffi_requests:
            return None
        try:
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                return None
            html = resp.text
            if "webPixelsConfigList" not in html:
                return None
            # Find the array and extract it with balanced brackets
            start_idx = html.find('"webPixelsConfigList":')
            if start_idx == -1:
                return None
            array_start = html.find('[', start_idx)
            if array_start == -1:
                return None
            bracket_count = 0
            end_idx = -1
            for i in range(array_start, len(html)):
                if html[i] == '[':
                    bracket_count += 1
                elif html[i] == ']':
                    bracket_count -= 1
                if bracket_count == 0:
                    end_idx = i + 1
                    break
            if end_idx == -1:
                return None
            array_str = html[array_start:end_idx]
            pixel_id = None
            # Strategy 1: Find the facebook_pixel configuration block directly
            # The config string contains \"pixel_id\":\"...\" and \"pixel_type\":\"facebook_pixel\"
            # We search for pixel_type facebook_pixel, then extract the nearby pixel_id
            fb_type_match = re.search(
                r'"pixel_type"\s*:\s*"facebook_pixel".*?"pixel_id"\s*:\s*"(\d{10,16})"',
                array_str, re.IGNORECASE | re.DOTALL
            )
            if not fb_type_match:
                # Try reversed order: pixel_id before pixel_type
                fb_type_match = re.search(
                    r'"pixel_id"\s*:\s*"(\d{10,16})".*?"pixel_type"\s*:\s*"facebook_pixel"',
                    array_str, re.IGNORECASE | re.DOTALL
                )
            if fb_type_match:
                pixel_id = fb_type_match.group(1)
            # Strategy 2: Fallback — any pixel_id in an entry whose configuration contains "facebook"
            if not pixel_id:
                # Find all configuration strings, check if they contain facebook
                for config_match in re.finditer(r'"configuration"\s*:\s*"(\{.*?\})"', array_str):
                    config_str = config_match.group(1).replace('\\"', '"')
                    if "facebook" in config_str.lower():
                        pid_match = re.search(r'"pixel_id"\s*:\s*"(\d{10,16})"', config_str)
                        if pid_match:
                            pixel_id = pid_match.group(1)
                            break
            if pixel_id:
                logger.info(f"[SHOPIFY_SANDBOX] Extracted Pixel ID statically: {pixel_id}")
                return {
                    "pixel_fired": True, "requests": [], "capi_events": [],
                    "detected_pixel_id": pixel_id, "gtm_id": None,
                    "engine_used": "shopify_sandbox_static", "blocked_status": None,
                    "has_event_data": False, "has_initiate_checkout": False,
                    "has_add_to_cart": False, "has_purchase_event": False,
                    "has_shared_event_id": False, "has_unhashed_pii": False,
                    "fbq_events_observed": [],
                }
        except Exception as e:
            logger.debug(f"[SHOPIFY_SANDBOX] Failed: {e}")
        return None

    # ------------------------------------------------------------------ #
    # Attempt 2: Ghost Protocol
    # ------------------------------------------------------------------ #
    def _probe_with_ghost_protocol(self, url: str) -> dict:
        network_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "detected_pixel_id": None, "gtm_id": None,
            "engine_used": "ghost_protocol", "blocked_status": None,
            "has_event_data": False, "has_initiate_checkout": False,
            "has_add_to_cart": False, "has_purchase_event": False,
            "has_shared_event_id": False, "has_unhashed_pii": False,
            "fbq_events_observed": [],
        }
        if not sync_playwright:
            return network_log
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--exclude-switches=enable-automation",
                    "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                    "--lang=en-US", "--window-size=1920,1080",
                    "--start-maximized", "--incognito"
                ]
            )
            context = browser.new_context(
                user_agent=ua,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["clipboard-read", "clipboard-write"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"'
                }
            )
            stealth_js = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', {
get: () => [
{ name: "Chrome PDF Plugin", filename: "internal-pdf-viewer" },
{ name: "Chrome PDF Viewer", filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai" },
{ name: "Native Client", filename: "internal-nacl-plugin" }
]
});
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
if (parameter === 37445) return 'Intel Inc.';
if (parameter === 37446) return 'Intel Iris OpenGL Engine';
return originalGetParameter.call(this, parameter);
};
const originalCreateOscillator = AudioContext.prototype.createOscillator;
AudioContext.prototype.createOscillator = function() {
const osc = originalCreateOscillator.call(this);
osc.frequency.value += Math.random() * 0.01;
return osc;
};
            const originalPermissionsQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (parameters) => (
parameters.name === 'notifications' ?
Promise.resolve({ state: Notification.permission }) :
originalPermissionsQuery(parameters)
);
"""
            context.add_init_script(stealth_js)
            try:
                context.add_init_script(FBQ_INTERCEPTOR_JS)
            except Exception as e:
                logger.debug(f"[GHOST] fbq interceptor install skipped: {e}")
            page = context.new_page()
            requests_log = []

            def on_response(response):
                req_url = response.url
                status = response.status
                requests_log.append({"url": req_url, "method": response.request.method, "status": status})
                if "facebook.com/tr" in req_url:
                    network_log["pixel_fired"] = True
                    try:
                        if response.request.post_data:
                            network_log["capi_events"].append({
                                "url": req_url, "event_name": "client_event",
                                "raw_body": response.request.post_data[:2000],
                            })
                    except Exception:
                        pass
                if "graph.facebook.com" in req_url and "/events" in req_url:
                    match = RE_CAPI_URL.search(req_url)
                    if match:
                        pid = match.group(1)
                        event_entry = {"url": req_url, "event_name": "server_event", "pixel_id": pid}
                        try:
                            if response.request.post_data:
                                event_entry["raw_body"] = response.request.post_data[:2000]
                        except Exception:
                            pass
                        network_log["capi_events"].append(event_entry)
                        if not network_log.get("detected_pixel_id"):
                            network_log["detected_pixel_id"] = pid

            page.on("response", on_response)
            try:
                logger.info(f"[GHOST] Navigating to {url}...")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                content = page.content()
                # Strict Cloudflare detection: challenges.cloudflare.com alone is a false positive
                _title_ghost = (page.title() or "").lower()
                _cf_blocked = (
                    "<title>just a moment..." in content.lower()
                    or "checking your browser" in content.lower()
                    or "cf-browser-verification" in content.lower()
                )
                if _cf_blocked:
                    logger.warning("[GHOST] Detected CF Challenge. Initiating Human Simulation...")
                    try:
                        page.wait_for_selector("iframe[src*='challenges.cloudflare.com']", timeout=10000)
                    except: pass
                    for _ in range(10):
                        x = random.randint(200, 1700)
                        y = random.randint(200, 900)
                        page.mouse.move(x, y, steps=random.randint(5, 15))
                        time.sleep(random.uniform(0.05, 0.2))
                    try:
                        checkbox_frame = page.frame_locator("iframe[src*='challenges.cloudflare.com']").locator("input[type='checkbox']")
                        if checkbox_frame.count() > 0:
                            checkbox_frame.first.click(timeout=5000)
                            logger.info("[GHOST] Clicked Turnstile Checkbox.")
                            time.sleep(3)
                    except Exception as e:
                        logger.debug(f"[GHOST] Checkbox click failed: {e}")
                    time.sleep(5)
                    content = page.content()
                    if "challenges.cloudflare.com" in content or "<title>Just a moment..." in content:
                        network_log["blocked_status"] = "CF_CHALLENGE_PERSISTENT"
                        logger.error("[GHOST] Failed to bypass Cloudflare.")
                        return network_log
                    logger.info("[GHOST] Bypass Successful. Extracting Data...")
                # Network config bundle extraction FIRST (survives sandbox)
                if not network_log.get("detected_pixel_id"):
                    net_pid = self._extract_pixel_id_from_network(requests_log)
                    if net_pid:
                        network_log["detected_pixel_id"] = net_pid
                        network_log["pixel_fired"] = True
                        logger.info(f"[GHOST] Pixel from network: {net_pid}")
                # fbq capture for event payloads
                captures = self._wait_for_fbq_and_capture(page, requests_log, timeout=15)
                enriched = self._analyze_fbq_captures(captures)
                for k, v in enriched.items():
                    if v not in (None, False, [], ""):
                        network_log[k] = v
                    elif k not in network_log:
                        network_log[k] = v
                logger.info(f"[GHOST] Captured {len(captures)} fbq call(s); "
                            f"pixel={network_log.get('detected_pixel_id')}, "
                            f"events={enriched.get('fbq_events_observed')}")
                m_gtm = RE_GTM_ID.search(content)
                if m_gtm:
                    network_log["gtm_id"] = m_gtm.group(0)
                m_shop = re.search(r'cdn\.shopify\.com/s/files/1/(\d+)/', content)
                m_theme = re.search(r'cdn\.shopify\.com/s/files/1/\d+/t/(\d+)/', content)
                shop_id = m_shop.group(1) if m_shop else None
                theme_id = m_theme.group(1) if m_theme else None
                fbq_m = RE_FBQ_INIT.search(content)
                if fbq_m and not network_log.get("detected_pixel_id"):
                    pid = fbq_m.group(1)
                    if self._score_pixel_probability(pid, "HTML_INLINE") > 0.5:
                        network_log["detected_pixel_id"] = pid
                        network_log["pixel_fired"] = True
                        logger.info(f"[GHOST] Found Pixel in Inline HTML: {pid}")
                if not network_log.get("detected_pixel_id") and shop_id and theme_id:
                    logger.info(f"[GHOST] Scanning Public CDN for Shop {shop_id} / Theme {theme_id}...")
                    js_files = ["theme.js", "scripts.js", "global.js", "main.js", "vendor.js"]
                    for fname in js_files:
                        asset_url = f"https://cdn.shopify.com/s/files/1/{shop_id}/t/{theme_id}/assets/{fname}"
                        try:
                            r_asset = cffi_requests.get(asset_url, impersonate="chrome120", timeout=5)
                            if r_asset.status_code == 200:
                                body = r_asset.text.lower()
                                fbq_match = RE_FBQ_INIT.search(body)
                                if fbq_match:
                                    pid = fbq_match.group(1)
                                    if self._score_pixel_probability(pid, "CDN_ASSET") > 0.5:
                                        network_log["detected_pixel_id"] = pid
                                        network_log["pixel_fired"] = True
                                        logger.info(f"[GHOST] FOUND PIXEL IN CDN ASSET {fname}: {pid}")
                                        break
                        except Exception as e:
                            logger.debug(f"[GHOST] CDN Fetch Error {fname}: {e}")
                if network_log.get("has_event_data"):
                    logger.info(f"[GHOST] Event coverage: "
                                f"ATC={network_log.get('has_add_to_cart')}, "
                                f"IC={network_log.get('has_initiate_checkout')}, "
                                f"PUR={network_log.get('has_purchase_event')}, "
                                f"dedup={network_log.get('has_shared_event_id')}, "
                                f"raw_PII={network_log.get('has_unhashed_pii')}")
                network_log["requests"] = requests_log
                return network_log
            except Exception as e:
                logger.error(f"[GHOST] Critical Error: {e}")
                network_log["blocked_status"] = "ERROR"
            finally:
                context.close()
                browser.close()
        return network_log

    # ------------------------------------------------------------------ #
    # FUNNEL AUDIT ENGINE
    # ------------------------------------------------------------------ #
    def _merge_funnel_captures(self, merged: dict, captures: list, step_label: str) -> dict:
        if not captures:
            logger.info(f"[FUNNEL] Step '{step_label}': 0 fbq call(s)")
            return merged
        enriched = self._analyze_fbq_captures(captures)
        if enriched.get("detected_pixel_id") and not merged.get("detected_pixel_id"):
            merged["detected_pixel_id"] = enriched["detected_pixel_id"]
            merged["pixel_id_source"] = "fbq_init"
        # Never discard what the merchant actually called — this is the evidence.
        from collections import Counter as _Ctr
        _bucket = merged.setdefault("fbq_raw_calls", [])
        _sigs = {
            (str(x.get("ts")), str(x.get("call_type")),
             json.dumps(x.get("args"), sort_keys=True, default=str)[:300])
            for x in _bucket if isinstance(x, dict)
        }
        for _c in captures:
            if not isinstance(_c, dict):
                continue
            _s = (str(_c.get("ts")), str(_c.get("call_type")),
                  json.dumps(_c.get("args"), sort_keys=True, default=str)[:300])
            if _s in _sigs:
                continue
            _sigs.add(_s)
            if len(_bucket) < 60:
                _bucket.append(_c)
        merged["fbq_call_types"] = dict(_Ctr(
            str(c.get("call_type")) for c in _bucket if isinstance(c, dict)
        ))
        merged["fbq_unique_call_count"] = len(_sigs)
        logger.info(f"[FBQ_EVIDENCE] step={step_label} call_types={json.dumps(merged['fbq_call_types'])}")
        if enriched.get("synthetic_fbq_generated"):
            merged["synthetic_fbq_generated"] = True
        for k in ("has_event_data", "has_add_to_cart", "has_initiate_checkout",
                   "has_purchase_event", "has_shared_event_id", "has_unhashed_pii"):
            if enriched.get(k):
                merged[k] = True
        merged["fbq_events_observed"] = list(dict.fromkeys(
            merged.get("fbq_events_observed", []) + enriched.get("fbq_events_observed", [])
        ))
        _seen_eid = {(x.get("event"), x.get("event_id"))
                     for x in merged.get("fbq_events_with_event_id", [])}
        for _x in enriched.get("fbq_events_with_event_id", []):
            _k = (_x.get("event"), _x.get("event_id"))
            if _k not in _seen_eid:
                _seen_eid.add(_k)
                merged.setdefault("fbq_events_with_event_id", []).append(_x)
        logger.info(f"[FUNNEL] Step '{step_label}': {len(captures)} fbq call(s), "
                    f"events={enriched.get('fbq_events_observed')}")
        return merged

    def _find_product_link(self, page, base_url: str) -> str | None:
        # If the page we are already on is a product page, use it directly.
        # This prevents the funnel from walking a different product than the audited one.
        from urllib.parse import urlparse as _urlparse_pdp
        _path = _urlparse_pdp(base_url).path.lower()
        _product_path_markers = ("/product/", "/products/", "/item/", "/p/")
        if any(marker in _path for marker in _product_path_markers):
            logger.info(f"[FUNNEL] Landing URL is already a product page: {base_url}")
            return base_url
        selectors = [
            "a[href*='/products/']",
            "a[href*='/product/']",
            "a[href*='/item/']",
            "a[href*='/collections/'][href*='/products/']",
            "a[href*='/shop/']",
            ".product-card a",
            ".grid-product__link",
            ".card__heading a",
            ".product-item a",
            ".product a",
        ]
        for sel in selectors:
            try:
                links = page.locator(sel).all()
                for link in links[:5]:
                    href = link.get_attribute("href")
                    if href:
                        return urljoin(base_url, href)
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------ #
    # BASKET STATE + MULTI-ITEM ACQUISITION
    # ------------------------------------------------------------------ #
    def _read_basket_state(self, page) -> dict:
        """Observable basket facts only. No inference about the platform."""
        try:
            return page.evaluate("""() => {
                const norm = s => (s||'').replace(/\\s+/g,' ').trim();
                const body = norm(document.body.innerText || '');
                const cnt = body.match(/your (?:order|basket|bag|cart)\\s*\\((\\d+)\\s*item/i);
                const qty = Array.from(document.querySelectorAll(
                    "input[name*='quantity' i], [data-testid*='quantity' i] input, .quantity input"
                )).map(e => parseInt(e.value||'0',10)).filter(n => !isNaN(n));
                const money = Array.from(body.matchAll(/[£$€]\\s?(\\d+(?:\\.\\d{2})?)/g))
                    .map(m => parseFloat(m[1]));
                const sub = body.match(/subtotal\\s*[£$€]\\s?(\\d+(?:\\.\\d{2})?)/i);
                const thr = body.match(/below\\s*[£$€]\\s?(\\d+(?:\\.\\d{2})?)/i)
                   || body.match(/(?:on|over|above|orders? (?:of|over))[ ]*[£$€][ ]?([0-9]+(?:[.][0-9]{2})?)/i)
                    || body.match(/minimum (?:spend|order)[^£$€\\d]*[£$€]\\s?(\\d+(?:\\.\\d{2})?)/i);
                const badge = document.querySelector(
                    "[data-cart-count], .cart-count, .js-cart-count, .basket-count, .minicart-quantity");
                return {
                    url: location.href,
                    item_count_text: cnt ? parseInt(cnt[1],10) : null,
                    quantity_sum: qty.length ? qty.reduce((a,b)=>a+b,0) : null,
                    badge_count: badge ? (norm(badge.textContent).match(/\\d+/)||[null])[0] : null,
                    subtotal: sub ? parseFloat(sub[1]) : null,
                    declared_threshold: thr ? parseFloat(thr[1]) : null,
                    max_money_seen: money.length ? Math.max(...money) : null,
                    body_snippet: body.slice(0, 300),
                };
            }""")
        except Exception as e:
            return {"error": str(e)}

    def _discover_product_candidates(self, page, base_url: str, limit: int = 12) -> list[str]:
        """Same-origin product URLs visible on the current page. Deduped, ordered."""
        try:
            hrefs = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]'))
                .filter(a => (a.offsetWidth || a.offsetHeight))
                .map(a => a.getAttribute('href'))""") or []
        except Exception:
            hrefs = []
        host = urlparse(base_url).netloc.lower()
        markers = ("/product/", "/products/", "/item/", "/p/", "/pd/", "/dp/")
        out, seen = [], set()
        for h in hrefs:
            if not h or h.startswith(("javascript:", "mailto:", "#")):
                continue
            full = urljoin(base_url, h)
            p = urlparse(full)
            if p.netloc.lower() != host:
                continue
            if not any(m in p.path.lower() for m in markers):
                continue
            clean = f"{p.scheme}://{p.netloc}{p.path}" + (f"?{p.query}" if p.query else "")
            if clean.rstrip("/") == base_url.rstrip("/") or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
        return out[:limit]

    def _build_multi_item_basket(self, page, seed_product_url: str, runner_name: str,
                                 merged_log: dict, all_requests: list,
                                 landing_url: str = "") -> int:
        """
        Adds FUNNEL_TARGET_ITEMS..FUNNEL_MAX_ITEMS distinct items, human-paced.
        Each add is verified by _attempt_add_to_cart's own proof chain.
        Stops early if the page declares a spend threshold and we have cleared it.
        Returns verified add count.
        """
        rng = random.Random(2399)
        target = max(2, FUNNEL_TARGET_ITEMS)
        ceiling = max(target, FUNNEL_MAX_ITEMS)
        added = 0
        state = self._read_basket_state(page)
        merged_log["basket_state"].append({"phase": "before_first_add", **state})
        logger.info(f"[BASKET/{runner_name}] before_first_add: {json.dumps(state, default=str)[:600]}")
        if self._attempt_add_to_cart(page, seed_product_url):
            added += 1
            merged_log["items_added_verified"] = added
            time.sleep(rng.uniform(1.6, 3.2))
        candidates = self._discover_product_candidates(page, seed_product_url)
        if not candidates and landing_url and landing_url.rstrip("/") != seed_product_url.rstrip("/"):
            # PDP exposed no sibling links. Re-scan the LANDING surface, not the same PDP.
            logger.info(f"[BASKET/{runner_name}] PDP has no product links. Re-scanning landing surface.")
            try:
                page.goto(landing_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                candidates = self._discover_product_candidates(page, landing_url)
            except Exception as e:
                logger.debug(f"[BASKET/{runner_name}] landing re-scan failed: {e}")
        if not candidates:
            logger.warning(f"[BASKET/{runner_name}] multi-item unavailable: no sibling product links discoverable. "
                           f"Proceeding with {added} verified item(s).")
        rng.shuffle(candidates)
        logger.info(f"[BASKET/{runner_name}] {len(candidates)} candidate product(s) discovered")
        tried = {seed_product_url.rstrip("/")}
        for curl in candidates:
            if added >= ceiling:
                break
            st = self._read_basket_state(page)
            thr, sub = st.get("declared_threshold"), st.get("subtotal")
            if added >= target and thr and sub and sub >= thr:
                logger.info(f"[BASKET/{runner_name}] Declared threshold £{thr} cleared by subtotal £{sub}. Stopping at {added} item(s).")
                break
            if curl.rstrip("/") in tried:
                continue
            tried.add(curl.rstrip("/"))
            try:
                self._simulate_human_scroll(page)
                page.goto(curl, wait_until="domcontentloaded", timeout=35000)
                time.sleep(rng.uniform(1.2, 2.6))
                ok = self._attempt_add_to_cart(page, curl)
                logger.info(f"[BASKET/{runner_name}] add #{added+1} {curl} -> {ok}")
                if ok:
                    added += 1
                    merged_log["items_added_verified"] = added
                    caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=8)
                    self._merge_funnel_captures(merged_log, caps, f"add_to_cart_{added}")
                    self._record_meta_delta(merged_log, all_requests, page, f"add_to_cart_{added}")
            except Exception as e:
                logger.debug(f"[BASKET/{runner_name}] candidate failed {curl}: {e}")
            time.sleep(rng.uniform(1.5, 3.0))
        merged_log["basket_state"].append({"phase": "after_build", **self._read_basket_state(page)})
        logger.info(f"[BASKET/{runner_name}] verified_items={added} state={json.dumps(merged_log['basket_state'][-1], default=str)[:600]}")
        return added

    def _find_cart_url(self, page, base_url: str) -> str | None:
        """
        Discover the cart URL from links on the current page.
        Falls back to None if no cart link is visible.
        Never returns a hardcoded '/cart' — that path does not exist on every store.
        """
        selectors = [
            "a[href*='/cart']",
            "a[href*='/basket']",
            "a[href*='/bag']",
            "a[href*='/trolley']",
            "a[href*='/checkout/bag']",
            "[data-testid*='cart'] a",
            "[aria-label*='cart']",
            "[aria-label*='basket']",
            ".cart-link a",
            ".basket-link a",
        ]
        for sel in selectors:
            try:
                links = page.locator(sel).all()
                for link in links[:3]:
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    full = urljoin(base_url, href)
                    # Guard against javascript:, mailto:, anchor-only hrefs
                    if not full.startswith(("http://", "https://")):
                        continue
                    return full
            except Exception:
                continue
        return None

    def _url_exists(self, url: str) -> bool:
        """
        Cheap HEAD probe to confirm the URL resolves before launching the browser at it.
        Returns True on any 2xx/3xx response; False on 4xx/5xx or network failure.
        """
        if not cffi_requests:
            return True  # cannot verify, allow navigation
        try:
            resp = cffi_requests.head(
                url,
                impersonate="chrome120",
                timeout=8,
                allow_redirects=False,
            )
            if resp.status_code in (200, 301, 302, 303, 307, 308):
                return True
            # Many WAFs (Akamai, CloudFront, Salesforce) reject HEAD with 5xx/405
            # even though GET works. Fall through to GET for these statuses.
            if resp.status_code in (405, 500, 501, 502, 503, 504):
                g = cffi_requests.get(
                    url,
                    impersonate="chrome120",
                    timeout=10,
                    allow_redirects=True,
                )
                return 200 <= g.status_code < 400
            return False
        except Exception:
            return False

    def _attempt_add_to_cart(self, page, product_url: str) -> bool:
        # Snapshot cart-count observable so we can prove ATC by state change
        def _read_cart_count():
            try:
                return page.evaluate("""() => {
                    const sels = ['[data-cart-count]','.cart-count','.js-cart-count',
                        '.basket-count','.minicart-quantity',
                        '[data-testid*="cart-count"]','[data-testid*="basket-count"]',
                        '[aria-label*="basket"]','[aria-label*="cart"]'];
                    for (const s of sels) {
                        const el = document.querySelector(s);
                        if (!el) continue;
                        const t = (el.textContent || '').trim();
                        const m = t.match(/\\d+/);
                        if (m) return parseInt(m[0], 10);
                    }
                    return null;
                }""")
            except Exception:
                return None

        def _verify_success(sel_label, resp=None):
            """
            Success if any of:
            (1) A POST/PUT to an ATC-ish URL returned 2xx (proven by expect_response).
            (2) Page URL changed to a cart-shaped URL.
            (3) Cart count increased.
            Logs the reason so the operator can see what happened.
            """
            nonlocal url_before, count_before
            # (1) Response-based proof
            if resp is not None:
                try:
                    status = resp.status
                    u = (resp.url or "").lower()
                    if 200 <= status < 400 and any(k in u for k in ("add", "cart", "basket", "item")):
                        logger.info(f"[FUNNEL] ATC verified ({sel_label}) — response {status} on {resp.url}")
                        # Record the ATC response body so we can see whether the
                        # item was actually accepted. A 202 can still carry a
                        # rejection (e.g. "item unavailable"), and we want to see
                        # that in the log rather than assume success.
                        try:
                            body_text = resp.text() or ""
                            snippet = body_text[:400].replace("\n", " ")
                            logger.info(f"[FUNNEL] ATC response body snippet: {snippet!r}")
                        except Exception:
                            pass
                        return True
                except Exception:
                    pass
            # (2) URL-based proof
            try:
                url_after = page.url
                count_after = _read_cart_count()
                navigated = url_after != url_before and (
                    any(k in url_after.lower() for k in ("/cart", "/basket", "/bag", "/trolley", "/checkout"))
                    or url_after.rstrip("/") != product_url.rstrip("/")
                )
                # (3) Count-based proof
                count_changed = (
                    count_before is not None
                    and count_after is not None
                    and count_after > count_before
                )
                if navigated or count_changed:
                    logger.info(
                        f"[FUNNEL] ATC verified ({sel_label}) — "
                        f"navigated={navigated} count_delta={count_changed} "
                        f"({count_before}->{count_after})"
                    )
                    return True
                logger.info(
                    f"[FUNNEL] ATC not verified ({sel_label}) — "
                    f"url_changed={url_after != url_before} "
                    f"count_before={count_before} count_after={count_after} "
                    f"response={None if resp is None else resp.status}"
                )
            except Exception as e:
                logger.debug(f"[FUNNEL] _verify_success error: {e}")
            return False

        def _dispatch_click(btn):
            """
            Dispatch a click via page.evaluate("el.click()") instead of
            Playwright's Locator.click(). Proven necessary on SFCC:
            Locator.click() times out on the ATC button because the button
            has a zero-size bounding rect and a OneTrust consent overlay
            sits on top of it. page.evaluate bypasses hit-testing and calls
            the element's DOM click handler directly, which is what the
            site's JS listens for.
            """
            try:
                btn.evaluate("(el) => el.click()")
                return True
            except Exception as e:
                logger.debug(f"[FUNNEL] _dispatch_click failed: {e}")
                return False

        # ---- Tier 0: DO NOT manipulate the size <select> here. ----
        # Proven by /tmp/probe_atc_deep.log: on SFCC, the ATC button adds the
        # SKU that is in the URL to the basket. The size <select> is optional
        # confirmation. Any selection on the <select> triggers an SFCC
        # navigation to the new SKU, resets the select, and leaves the ATC
        # button's React handler bound to a stale tree — so the subsequent
        # click fires no POST. Clicking ATC immediately, with the SKU that is
        # already in the URL, is the correct flow and reliably fires the POST
        # to /basket-api/v1/basket/items (201/202, basket count becomes 1).
        logger.info(f"[FUNNEL] ATC pre-select skipped (SFCC adds URL SKU directly)")
        url_before = page.url
        count_before = _read_cart_count()
        logger.info(f"[FUNNEL] ATC start: url={url_before} count_before={count_before}")

        # ============================================================
        # Tier A — form-targeted (SFCC / Magento / Presta / ASP.NET / OpenCart)
        # ============================================================
        try:
            forms_info = page.evaluate("""() => {
                const ADD_FORM_RE = /(add|addproduct|addtocart|cart[\\/]?add|basket[\\/]?add)/i;
                const out = [];
                document.querySelectorAll('form').forEach((f, i) => {
                    const action = (f.getAttribute('action') || '').trim();
                    if (!action) return;
                    if (!ADD_FORM_RE.test(action)) return;
                    f.setAttribute('data-adleak-atc-form', String(i));
                    out.push({idx: i, action: action});
                });
                return out;
            }""")
        except Exception:
            forms_info = []
        logger.info(f"[FUNNEL] Tier A: {len(forms_info or [])} ATC form(s) found")
        for form_info in (forms_info or []):
            idx = form_info["idx"]
            action = form_info["action"]
            submit_sel = (
                f"form[data-adleak-atc-form='{idx}'] [type='submit'], "
                f"form[data-adleak-atc-form='{idx}'] button, "
                f"form[data-adleak-atc-form='{idx}'] input[type='submit']"
            )
            try:
                btn = page.locator(submit_sel).first
                if not btn.is_visible(timeout=2000):
                    logger.info(f"[FUNNEL] Tier A form-action:{action[:60]} — submit button not visible")
                    continue
            except Exception as e:
                logger.info(f"[FUNNEL] Tier A form-action:{action[:60]} — button lookup failed: {e}")
                continue
            try:
                with page.expect_response(
                    lambda r: r.request.method in ("POST", "PUT")
                    and any(k in r.url.lower() for k in ("add", "cart", "basket", "item"))
                    and "challenges" not in r.url.lower(),
                    timeout=10000,
                ) as resp_info:
                    _dispatch_click(btn)
                    if _verify_success(f"form-action:{action[:60]}", resp=resp_info.value):
                        return True
            except Exception:
                time.sleep(2)
                if _verify_success(f"form-action:{action[:60]}"):
                    return True

        # ============================================================
        # Tier B — explicit selectors (Shopify / Woo / Magento / BigCommerce / Next.js)
        # ============================================================
        explicit_selectors = [
            "button[name='add']",
            ".product-form__submit",
            "button.single_add_to_cart_button",
            "button.add_to_cart_button",
            "button[data-button-action='add-to-cart']",
            "button[data-testid*='add-to-cart']",
            "button[data-testid*='add-to-basket']",
            "button[data-testid*='add-to-bag']",
        ]
        for sel in explicit_selectors:
            try:
                btn = page.locator(sel).first
                if not btn.is_visible(timeout=1500):
                    continue
                logger.info(f"[FUNNEL] Tier B: matched {sel}")
            except Exception:
                continue
            try:
                with page.expect_response(
                    lambda r: r.request.method in ("POST", "PUT")
                    and any(k in r.url.lower() for k in ("add", "cart", "basket", "item"))
                    and "challenges" not in r.url.lower(),
                    timeout=8000,
                ) as resp_info:
                    _dispatch_click(btn)
                    if _verify_success(sel, resp=resp_info.value):
                        return True
            except Exception:
                time.sleep(2)
                if _verify_success(sel):
                    return True

        # ============================================================
        # Tier C — text-based (semantic buttons: "Add to bag", "Add
        # to basket")
        # ============================================================
        try:
            text_candidates = page.evaluate("""() => {
                const ATC_RE = /\\badd\\s*(to\\s*)?(bag|basket|cart|trolley)?\\b|^add$|\\badd item\\b/i;
                const NEG_RE = /search|sign[\\s-]?in|log[\\s-]?in|subscribe|newsletter|apply|filter|sort|continue|go back|checkout|compare|wish ?list|remove|delete/i;
                document.querySelectorAll('button, a[role="button"], button[role="button"], [role="button"]').forEach((el) => {
                    const t = ((el.innerText || el.textContent || '') + '').trim();
                    if (!t || t.length > 40) return;
                    if (!ATC_RE.test(t)) return;
                    if (NEG_RE.test(t)) return;
                    if (!(el.offsetWidth || el.offsetHeight)) return;
                    if (el.disabled) return;
                    el.setAttribute('data-adleak-atc', '1');
                });
                return document.querySelectorAll('[data-adleak-atc="1"]').length;
            }""")
        except Exception:
            text_candidates = 0
        logger.info(f"[FUNNEL] Tier C: {text_candidates} text-matched button(s)")
        if text_candidates and text_candidates > 0:
            try:
                btn = page.locator("[data-adleak-atc='1']").first
                if btn.is_visible(timeout=1500):
                    # Log its identifying detail so we know what was clicked
                    try:
                        meta = btn.evaluate("""(el) => ({
                            text: ((el.innerText||'')+'').trim().slice(0,60),
                            cls: (el.className||'').toString().slice(0,60),
                        })""")
                        logger.info(f"[FUNNEL] Tier C click target: {json.dumps(meta)}")
                    except Exception:
                        pass
                    try:
                        with page.expect_response(
                            lambda r: r.request.method in ("POST", "PUT")
                            and any(k in r.url.lower() for k in ("add", "cart", "basket", "item"))
                            and "challenges" not in r.url.lower(),
                            timeout=8000,
                        ) as resp_info:
                            _dispatch_click(btn)
                            if _verify_success("text-based", resp=resp_info.value):
                                return True
                    except Exception:
                        time.sleep(2)
                        if _verify_success("text-based"):
                            return True
            except Exception as e:
                logger.debug(f"[FUNNEL] Tier C click failed: {e}")

        # ============================================================
        # Tier D — data-attribute sweep (headless / Next.js / custom)
        # ============================================================
        try:
            attr_candidates = page.evaluate("""() => {
                const ATTR_RE = /add.*(cart|bag|basket)|addtocart/i;
                let n = 0;
                document.querySelectorAll('button, a, [role="button"], input[type="submit"]').forEach((el) => {
                    if (el.getAttribute('data-adleak-atc-attr') === '1') return;
                    if (!(el.offsetWidth || el.offsetHeight)) return;
                    if (el.disabled) return;
                    const attrs = ['id','name','aria-label','data-testid','data-action','data-button-action'];
                    for (const a of attrs) {
                        const v = el.getAttribute(a);
                        if (v && ATTR_RE.test(v)) {
                            el.setAttribute('data-adleak-atc-attr', '1');
                            n++;
                            return;
                        }
                    }
                });
                return n;
            }""")
        except Exception:
            attr_candidates = 0
        logger.info(f"[FUNNEL] Tier D: {attr_candidates} attribute-matched button(s)")
        if attr_candidates and attr_candidates > 0:
            try:
                btn = page.locator("[data-adleak-atc-attr='1']").first
                if btn.is_visible(timeout=1500):
                    try:
                        with page.expect_response(
                            lambda r: r.request.method in ("POST", "PUT")
                            and any(k in r.url.lower() for k in ("add", "cart", "basket", "item"))
                            and "challenges" not in r.url.lower(),
                            timeout=8000,
                        ) as resp_info:
                            _dispatch_click(btn)
                            if _verify_success("attr-based", resp=resp_info.value):
                                return True
                    except Exception:
                        time.sleep(2)
                        if _verify_success("attr-based"):
                            return True
            except Exception as e:
                logger.debug(f"[FUNNEL] Tier D click failed: {e}")

        logger.info("[FUNNEL] ATC: no verified add-to-cart (all tiers tried)")
        return False

    def _try_select_variant_if_needed(self, page) -> bool:
        """
        If the product page has a size/colour/variant picker, select the first
        available value. Covers:
        - native <select> identified by option-value shape (SFCC, and any site
          whose size select has empty name/id but variant-ID option values)
        - native <select name*='size'/'variant'/'attr'> (Shopify, Woo, Magento)
        - ARIA radio / chip lists (SFCC, custom React/Vue)
        - data-attr-value chips (SFCC)
        - ul.swatch > li (SFCC, Prestashop, BigCommerce)
        - li[data-variant-id] (Shopify Dawn-style)
        Returns True if it selected or clicked something, False otherwise.
        """
        # -- 1a. Identify size select by option-value shape (SFCC and others) --
        # Every clothing site's size <select> has variant-ID option values sharing
        # a common prefix (e.g. "tuc140707147", "tuc140707155", "tuc140707227").
        # We detect the select whose non-empty options share a long common prefix
        # AND whose options look size-ish (contain "year", "month", "size", clothing sizes).
        try:
            sel_idx = page.evaluate("""() => {
                const sels = Array.from(document.querySelectorAll('select'));
                for (let i = 0; i < sels.length; i++) {
                    const opts = Array.from(sels[i].options || [])
                        .filter(o => o.value && o.value.length >= 4);
                    if (opts.length < 2) continue;
                    let p = opts[0].value;
                    for (const o of opts) {
                        while (o.value.indexOf(p) !== 0) {
                            p = p.slice(0, -1);
                            if (p.length < 4) break;
                        }
                        if (p.length < 4) break;
                    }
                    if (p.length < 4) continue;
                    const sampleText = (opts[0].text + ' ' + opts[opts.length - 1].text).toLowerCase();
                    const looksLikeSize = /year|month|size|newborn|xs|small|medium|large|x-large|\\b\\d{1,2}\\b/i.test(sampleText);
                    if (!looksLikeSize) continue;
                    return { idx: i, prefix: p, firstVal: opts[0].value };
                }
                return null;
            }""")
        except Exception as e:
            logger.debug(f"[VARIANT] option-shape scan failed: {e}")
            sel_idx = None
        if sel_idx:
            try:
                sels = page.locator("select").all()
                target = sels[sel_idx["idx"]]
                if target.is_visible(timeout=1000):
                    opts = target.locator("option").all()
                    for opt in opts:
                        val = opt.get_attribute("value")
                        if not val:
                            continue
                        try:
                            target.select_option(value=val)
                        except Exception:
                            continue
                        # Give SFCC's product page handler 1s to swap in the variant price/sku
                        time.sleep(1)
                        logger.info(f"[VARIANT] Selected size via option-shape heuristic: value={val} (prefix={sel_idx['prefix'][:10]}...)")
                        return True
            except Exception as e:
                logger.debug(f"[VARIANT] option-shape selection failed: {e}")
        # -- 1b. Existing named/id-driven <select> path (Shopify, Woo, Magento) --
        try:
            selects = page.locator(
                "select[name*='size' i], select[name*='variant' i], "
                "select[name*='attr' i], select[name*='option' i], "
                "select[id*='size' i], select[id*='variant' i], "
                "select[id*='attr' i]"
            ).all()
            for s in selects:
                try:
                    if not s.is_visible(timeout=500):
                        continue
                    opts = s.locator("option").all()
                    for opt in opts[1:]:  # skip placeholder
                        val = opt.get_attribute("value")
                        if val:
                            s.select_option(value=val)
                            logger.info(f"[VARIANT] Selected <select> value={val}")
                            time.sleep(1)
                            return True
                except Exception:
                    continue
        except Exception:
            pass
        # -- 1c. Swatch / chip / data-attribute selectors (unchanged) --
        chip_selectors = [
            "[data-attr-value]",
            "ul.swatch li",
            "[role='radio']",
            "[aria-label*='size' i] button",
            "button[data-size]",
            "[data-testid*='size' i] button",
            "[data-testid*='variant' i] button",
            "[class*='size-selector' i] button",
            "[class*='swatch' i] button",
            "[class*='size' i] button:not([disabled])",
            "li[data-variant-id] a",
            "a[data-variant-id]",
            "[data-product-attribute] li a",
        ]
        for sel in chip_selectors:
            try:
                chips = page.locator(sel).all()
                for c in chips[:10]:
                    try:
                        if not c.is_visible(timeout=500):
                            continue
                        disabled = c.get_attribute("disabled")
                        if disabled is not None:
                            continue
                        try:
                            c.click(timeout=2000)
                        except Exception:
                            continue
                        logger.info(f"[VARIANT] Clicked chip ({sel})")
                        time.sleep(1)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        return False

    def _reselect_current_sku_if_needed(self, page) -> bool:
        """
        On SFCC and similar stacks, when `_try_select_variant_if_needed` picks a
        size, the site navigates to the new variant URL (e.g. /product/tuc140707219)
        AND the size <select> resets to the placeholder. The ATC button then
        silently refuses to add because "no size is selected".
        This method re-selects the SKU that is currently live (from page.url) on
        the current page, so the ATC button is enabled again. Returns True if it
        selected something matching the current URL, False otherwise.
        """
        import re as _re
        try:
            # Extract the current SKU from the URL: e.g. ".../product/tuc140707219"
            url = page.url or ""
            m = _re.search(r"/product/([^/?#]+)", url)
            if not m:
                return False
            sku = m.group(1)
        except Exception:
            return False
        try:
            sel_info = page.evaluate("""(sku) => {
                const sels = Array.from(document.querySelectorAll('select'));
                for (let i = 0; i < sels.length; i++) {
                    const opts = Array.from(sels[i].options || []);
                    for (const o of opts) {
                        if (o.value === sku) {
                            return { idx: i, current: sels[i].value };
                        }
                    }
                }
                return null;
            }""", sku)
        except Exception as e:
            logger.debug(f"[VARIANT] reselect scan failed: {e}")
            sel_info = None
        if not sel_info:
            return False
        # If the <select> already has the SKU selected, nothing to do.
        if sel_info.get("current") == sku:
            logger.info(f"[VARIANT] ATC pre-check: size already = {sku}")
            return True
        try:
            sels = page.locator("select").all()
            target = sels[sel_info["idx"]]
            if not target.is_visible(timeout=1000):
                return False
            target.select_option(value=sku)
            time.sleep(0.8)
            logger.info(f"[VARIANT] ATC pre-check: re-selected current SKU {sku} on current page")
            return True
        except Exception as e:
            logger.debug(f"[VARIANT] reselect failed: {e}")
            return False

    def _dump_atc_evidence(self, page) -> dict:
        """
        Returns a structured snapshot of everything that could be an ATC control
        on the current page, so a failed ATC produces diagnostic output rather
        than silence.
        """
        try:
            return page.evaluate("""() => {
                const out = {buttons: [], selects: [], shadow_hosts: 0, iframes: 0};
                document.querySelectorAll('button, a[role="button"], [role="button"], input[type="submit"]').forEach((el) => {
                    const text = ((el.innerText || el.textContent || el.value || '') + '').trim().slice(0, 60);
                    if (!text) return;
                    const attrs = {};
                    for (const a of ['name','id','data-testid','data-button-action','aria-label','class']) {
                        const v = el.getAttribute(a);
                        if (v) attrs[a] = v.slice(0, 60);
                    }
                    out.buttons.push({
                        tag: el.tagName, text, visible: !!(el.offsetWidth || el.offsetHeight),
                        disabled: !!el.disabled, attrs,
                    });
                });
                document.querySelectorAll('select').forEach((el) => {
                    out.selects.push({
                        name: el.getAttribute('name'),
                        id: el.id,
                        options: Array.from(el.options || []).slice(0, 8).map(o => ({v: o.value, t: (o.text||'').slice(0,30)})),
                        visible: !!(el.offsetWidth || el.offsetHeight),
                    });
                });
                const walk = (root) => {
                    root.querySelectorAll('*').forEach((el) => {
                        if (el.shadowRoot) { out.shadow_hosts += 1; walk(el.shadowRoot); }
                    });
                };
                try { walk(document); } catch (e) {}
                out.iframes = document.querySelectorAll('iframe').length;
                return out;
            }""")
        except Exception as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------ #
    # PER-STEP META DELTA (proves WHICH action surfaced Meta, if any)
    # ------------------------------------------------------------------ #

    def _dump_tracking_diagnostics(self, page, all_requests: list) -> dict:
        """
        Answers 'why is the pixel dormant?' with measurement, not assumption.
        Captures every Meta-domain request, GTM containers, consent/CMP state,
        and the live fbq object state.
        """
        diag = {"meta_domain_requests": [], "gtm_containers": [], "cmp": {}, "fbq_state": {}}
        try:
            seen = set()
            for r in all_requests:
                if not isinstance(r, dict):
                    continue
                u = str(r.get("url", ""))
                if any(d in u for d in ("facebook.net", "facebook.com", "fbcdn", "atdmt")):
                    if u not in seen:
                        seen.add(u)
                        diag["meta_domain_requests"].append({"url": u[:300], "status": r.get("status")})
                for g in RE_GTM_ID.findall(u):
                    if g not in diag["gtm_containers"]:
                        diag["gtm_containers"].append(g)
        except Exception as e:
            diag["request_scan_error"] = str(e)
        try:
            state = page.evaluate("""() => {
                const ck = document.cookie.split(';').map(s => s.trim().split('=')[0]);
                const out = {cmp: {}, fbq_state: {}};
                out.cmp = {
                    onetrust: typeof window.OneTrust !== 'undefined',
                    optanon: typeof window.OptanonWrapper !== 'undefined',
                    tcfapi: typeof window.__tcfapi !== 'undefined',
                    uspapi: typeof window.__uspapi !== 'undefined',
                    googlefc: typeof window.googlefc !== 'undefined',
                    cookiebot: typeof window.Cookiebot !== 'undefined',
                    consent_cookie_names: ck.filter(k => /consent|optanon|onetrust|cookie|gdpr|tcf|euconsent|cc_/i.test(k)),
                    datalayer_consent: (() => {
                        try {
                            const dl = Array.isArray(window.dataLayer) ? window.dataLayer : [];
                            const acc = [];
                            for (const e of dl) {
                                try {
                                    const s = JSON.stringify(e);
                                    if (s && s.toLowerCase().includes('consent')) acc.push(e);
                                } catch (err) {}
                                if (acc.length >= 8) break;
                            }
                            return acc;
                        } catch (err) { return []; }
                    })(),
                    datalayer_is_array: Array.isArray(window.dataLayer),
                    datalayer_len: (window.dataLayer && window.dataLayer.length) || 0,
                };
                try {
                    if (typeof fbq === 'function') {
                        out.fbq_state = {
                            present: true,
                            loaded: !!fbq.loaded,
                            version: fbq.version || null,
                            queue_len: (fbq.queue || []).length,
                            pixels: (fbq.instance && fbq.instance.pixelsByID)
                                    ? Object.keys(fbq.instance.pixelsByID) : [],
                            captured_len: (window.__fbq_captured || []).length,
                        };
                    } else { out.fbq_state = {present: false}; }
                } catch (e) { out.fbq_state = {error: String(e)}; }
                return out;
            }""")
            diag["cmp"] = state.get("cmp", {})
            diag["fbq_state"] = state.get("fbq_state", {})
        except Exception as e:
            diag["page_state_error"] = str(e)
        logger.info(f"[TRACKING_DIAG] {json.dumps(diag, default=str)[:3000]}")
        return diag


    def _record_meta_delta(self, merged_log: dict, all_requests: list, page, step: str) -> dict:
        def _n(pred):
            return sum(1 for r in all_requests if isinstance(r, dict) and pred(str(r.get("url", ""))))
        cur = {
            "fbevents_js": _n(lambda u: "connect.facebook.net" in u and "fbevents.js" in u),
            "config_bundle": _n(lambda u: "connect.facebook.net/signals/config/" in u),
            "facebook_tr": _n(lambda u: "facebook.com/tr" in u),
            "gtm": _n(lambda u: "googletagmanager.com/gtm.js" in u or "googletagmanager.com/gtag/" in u),
            "graph_events": _n(lambda u: "graph.facebook.com" in u and "/events" in u),
            "total_requests": len(all_requests),
        }
        prev = merged_log.get("_meta_prev") or {k: 0 for k in cur}
        delta = {k: cur[k] - prev.get(k, 0) for k in cur}
        merged_log["_meta_prev"] = cur
        rec = {"step": step, "url": page.url, "cumulative": cur, "delta": delta}
        merged_log["meta_observations_by_step"].append(rec)
        logger.info(f"[META_DELTA] {step}: {json.dumps(delta)} cum={json.dumps(cur)}")
        return rec

    # ------------------------------------------------------------------ #
    # FULFILMENT GATE ACTOR (postcode -> delivery -> continue)
    # ------------------------------------------------------------------ #
    def _snapshot_gate(self, page) -> dict:
        """Evidence-driven control inventory. Replaces keyword-only guessing."""
        try:
            return page.evaluate("""() => {
                const norm = s => (s||'').replace(/\\s+/g,' ').trim();
                const vis = el => !!(el.offsetWidth || el.offsetHeight);
                const inputs = [];
                document.querySelectorAll('input, select, textarea').forEach((el, i) => {
                    if (!vis(el)) return;
                    const lbl = el.labels && el.labels[0] ? norm(el.labels[0].innerText) : '';
                    inputs.push({
                        idx: i, tag: el.tagName, type: el.type||'', name: el.name||'', id: el.id||'',
                        placeholder: el.placeholder||'', aria: el.getAttribute('aria-label')||'',
                        label: lbl.slice(0,60), disabled: !!el.disabled, value: (el.value||'').slice(0,20),
                    });
                });
                const buttons = [];
                document.querySelectorAll('button, a[role="button"], [role="button"], input[type="submit"]').forEach((el, i) => {
                    const t = norm(el.innerText || el.textContent || el.value);
                    if (!t || t.length > 80 || !vis(el)) return;
                    buttons.push({idx: i, text: t.slice(0,60), disabled: !!el.disabled,
                        cls: (el.className||'').toString().slice(0,60)});
                });
                const radios = [];
                document.querySelectorAll("input[type='radio']").forEach((el, i) => {
                    const lbl = el.labels && el.labels[0] ? norm(el.labels[0].innerText) : '';
                    const wrap = el.closest('label, li, div');
                    const ctx = wrap ? norm(wrap.innerText || '').slice(0,120) : '';
                    radios.push({idx: i, name: el.name||'', id: el.id||'',
                                 value: (el.value||'').slice(0,40),
                                 label: lbl.slice(0,80), context: ctx, visible: vis(el),
                                 disabled: !!el.disabled, checked: !!el.checked});
                });
                const body = norm(document.body.innerText || '');
                const low = body.toLowerCase();
                return {
                    url: location.href, title: document.title,
                    inputs, buttons: buttons.slice(0,30), radios,
                    markers: {
                        asks_postcode: /enter (your )?post ?code|post ?code for delivery/i.test(body),
                        choose_delivery: /choose delivery|delivery option|select (a )?delivery/i.test(body),
                        has_continue_payment: /continue to payment|proceed to payment|continue to billing/i.test(low),
                        has_pay_now: low.includes('pay now'),
                        below_threshold: /below\\s*[£$€]\\s?\\d/i.test(body),
                        out_of_stock: low.includes('out of stock'),
                        basket_empty: /basket is empty|cart is empty|bag is empty/i.test(low),
                        login_required: /sign in to continue|log in to continue|create an account to continue/i.test(low),
                        error_visible: /please enter a valid|please enter your post ?code|invalid post ?code|no results found|address not found|something went wrong|please try again|is required|enter a valid/i.test(low),
                    },
                    body_snippet: body.slice(0, 500),
                };
            }""")
        except Exception as e:
            return {"error": str(e)}

    def _enter_postcode(self, page, merged_log: dict, runner_name: str) -> bool:
        """Fills the postcode field the page itself labels as postcode. No hardcoded site path."""
        snap = self._snapshot_gate(page)
        merged_log["fulfilment_steps"].append({"action": "gate_snapshot", **snap})
        logger.info(f"[FULFIL/{runner_name}] gate snapshot: {json.dumps(snap, default=str)[:2500]}")
        if not snap.get("markers", {}).get("asks_postcode"):
            logger.info(f"[FULFIL/{runner_name}] Page does not ask for a postcode. Skipping.")
            return False

        url_before = page.url
        selectors = [
            "input[placeholder*='postcode' i]", "input[placeholder*='post code' i]",
            "input[placeholder*='zip' i]", "input[name*='postcode' i]",
            "input[name*='postal' i]", "input[id*='postcode' i]",
            "input[aria-label*='postcode' i]", "input[autocomplete='postal-code']",
        ]
        pc = random.Random(2399).choice(["SW1A 1AA", "M1 1AE", "B1 1BB", "LS1 1UR", "EH1 1YZ"])

        target = None
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=1200) and not loc.is_disabled():
                    target = loc
                    logger.info(f"[FULFIL/{runner_name}] postcode field matched: {sel}")
                    break
            except Exception:
                continue

        # Index fallback driven by the page's own field inventory (headless / React).
        if target is None:
            rx = re.compile(r"post ?code|postal|zip", re.I)
            for f in (snap.get("inputs") or []):
                if f.get("disabled") or f.get("tag") != "INPUT":
                    continue
                if f.get("type") in ("hidden", "submit", "button", "checkbox", "radio"):
                    continue
                hay = " ".join(str(f.get(k, "")) for k in ("placeholder", "name", "id", "aria", "label"))
                if not rx.search(hay):
                    continue
                try:
                    loc = page.locator("input, select, textarea").nth(f["idx"])
                    if loc.is_visible(timeout=1200):
                        target = loc
                        logger.info(f"[FULFIL/{runner_name}] postcode field matched by inventory idx={f['idx']}")
                        break
                except Exception:
                    continue

        if target is None:
            logger.warning(f"[FULFIL/{runner_name}] asks_postcode=True but no field matched. Evidence stored.")
            return False

        try:
            target.scroll_into_view_if_needed(timeout=3000)
            target.click(timeout=3000)
            target.fill("")
            target.type(pc, delay=random.randint(60, 140))
        except Exception:
            try:
                target.evaluate("(el, v) => { el.value = v; el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true})); }", pc)
            except Exception as e:
                logger.warning(f"[FULFIL/{runner_name}] postcode fill failed: {e}")
                return False

        # Submit ONLY a button in a tight scope with the postcode field.
        # Scope must contain no site-search control, no header/nav, and <=6 buttons.
        # Proven necessary: SFCC fulfilment exposes a SECOND header "Search" button.
        submitted = False
        try:
            submitted = target.evaluate("""(el) => {
                const bad = (n) =>
                    n.matches('header, nav') || !!n.querySelector('header, nav') ||
                    !!n.querySelector("input[type='search'], input[name*='search' i], input[id*='search' i], [role='search'], form[action*='search' i]");
                let scope = el.closest('form') || el.parentElement;
                for (let i = 0; i < 5 && scope; i++) {
                    if (scope.contains(el) && !bad(scope)) {
                        const btns = Array.from(scope.querySelectorAll("button, input[type='submit'], [role='button']"))
                            .filter(b => !b.disabled && (b.offsetWidth || b.offsetHeight));
                        if (btns.length && btns.length <= 6) {
                            const b = btns.find(x => /^(search|find|look ?up|check|submit)$/i.test((x.innerText||x.value||'').trim()))
                                   || btns.find(x => /search|find|look ?up/i.test((x.innerText||x.value||'')));
                            if (b) { b.click(); return (b.innerText||b.value||'button').trim().slice(0,40); }
                        }
                    }
                    scope = scope.parentElement;
                }
                return false;
            }""")
        except Exception as e:
            logger.debug(f"[FULFIL/{runner_name}] scoped submit failed: {e}")
        if not submitted:
            try:
                target.press("Enter")
                submitted = True
            except Exception:
                pass

        time.sleep(3.5)
        after = self._snapshot_gate(page)

        # Navigation guard: a postcode lookup must never eject us from checkout.
        _flow = ("checkout", "/basket", "/bag", "/cart", "/trolley", "demandware")
        if not any(m in (after.get("url") or "").lower() for m in _flow):
            logger.warning(f"[FULFIL/{runner_name}] submit left checkout flow -> {after.get('url')}. Restoring {url_before}")
            try:
                page.goto(url_before, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
            except Exception:
                pass
            merged_log["fulfilment_steps"].append({
                "action": "postcode_submit_aborted", "value_used": pc,
                "reason": "left_checkout_flow", "url_after_submit": after.get("url"),
            })
            return False

        changed = (after.get("body_snippet") != snap.get("body_snippet")) or bool(after.get("radios"))
        _pc_norm = pc.replace(" ", "").upper()
        _pc_persisted = any(
            str(f.get("value", "")).replace(" ", "").upper() == _pc_norm
            for f in (after.get("inputs") or [])
        )
        _hard = re.search(r"something went wrong|please try again|invalid post ?code|"
                          r"no results found|address not found|please enter a valid",
                          str(after.get("body_snippet", "")), re.I)
        _err_now = bool(_hard)
        _body_now = str(after.get("body_snippet", ""))
        _pc_echo = _pc_norm in _body_now.replace(" ", "").upper()
        _resolved = (
            not after.get("markers", {}).get("asks_postcode")
            or bool(re.search(r"delivery available|change post ?code|delivery information",
                              _body_now, re.I))
        )
        _pc_accepted = bool(_pc_echo and _resolved)
        ok = bool(submitted) and not _err_now and (_pc_persisted or _pc_accepted)
        merged_log["fulfilment_steps"].append({
            "action": "postcode_submitted", "value_used": pc, "submitted": submitted,
            "value_persisted": _pc_persisted, "merchant_accepted": _pc_accepted,
        })
        logger.info(f"[FULFIL/{runner_name}] postcode='{pc}' submitted={submitted} changed={changed} no_error={ok} url={after.get('url')}")
        return ok

    def _select_delivery_option(self, page, merged_log: dict, runner_name: str) -> bool:
        snap = self._snapshot_gate(page)
        radios = [r for r in (snap.get("radios") or []) if r.get("visible") and not r.get("disabled")]
        merged_log["fulfilment_steps"].append({"action": "delivery_candidates", "radios": radios})
        logger.info(f"[FULFIL/{runner_name}] {len(radios)} selectable delivery radio(s): {json.dumps(radios)[:1200]}")
        if not radios:
            return False
        pick = next(
            (r for r in radios if re.search(
                r"deliver|standard|home|courier",
                f"{r.get('label','')} {r.get('context','')}", re.I)),
            radios[0],
        )
        try:
            # Index-based: immune to truncated values and CSS-special characters.
            loc = page.locator("input[type='radio']").nth(pick["idx"])
            try:
                loc.evaluate("(el) => el.click()")
            except Exception:
                loc.check(timeout=4000)
            time.sleep(2.5)
            after = self._snapshot_gate(page)
            verified = any(
                r.get("idx") == pick["idx"] and r.get("checked")
                for r in (after.get("radios") or [])
            )
            merged_log["fulfilment_steps"].append({
                "action": "delivery_selected", "picked": pick,
                "verified_checked": verified, **after,
            })
            logger.info(f"[FULFIL/{runner_name}] delivery selected: "
                        f"{pick.get('label') or pick.get('context') or pick.get('value')} verified={verified}")
            return bool(verified)
        except Exception as e:
            logger.warning(f"[FULFIL/{runner_name}] delivery selection failed: {e}")
            return False

    def _continue_to_payment(self, page, merged_log: dict, runner_name: str) -> bool:
        """Clicks a visible enabled FORWARD control. Stops at payment. Never pays.
        Explicitly refuses 'Continue shopping' / back / basket / cancel controls."""
        flow = ("checkout", "/basket/fulfilment", "/basket/payment", "/basket/delivery",
                "/basket/summary", "/on/demandware.store", "/payment", "/billing")
        neg = re.compile(r"shopping|keep browsing|back|basket|cart|bag|cancel|close|edit|"
                         r"remove|apply|promo|voucher|required only|let me choose|reject all", re.I)
        prefs = ("continue to payment", "proceed to payment", "continue to billing",
                 "continue to delivery", "continue with delivery", "continue to shipping",
                 "deliver here", "use this address", "continue", "next", "proceed")
        snap = self._snapshot_gate(page)
        ranked = []
        for b in (snap.get("buttons") or []):
            if b.get("disabled"):
                continue
            tl = (b.get("text") or "").strip().lower()
            if not tl or neg.search(tl):
                continue
            for rank, p in enumerate(prefs):
                if tl == p or tl.startswith(p):
                    ranked.append((rank, b))
                    break
        ranked.sort(key=lambda x: x[0])
        merged_log["fulfilment_steps"].append({
            "action": "continue_candidates",
            "candidates": [{"idx": b["idx"], "text": b["text"]} for _, b in ranked],
        })
        logger.info(f"[FULFIL/{runner_name}] {len(ranked)} forward control(s): "
                    f"{json.dumps([b['text'] for _, b in ranked])[:400]}")

        for _, b in ranked[:3]:
            before = page.url
            try:
                loc = page.locator('button, a[role="button"], [role="button"], input[type="submit"]').nth(b["idx"])
                try:
                    with page.expect_navigation(timeout=12000):
                        loc.evaluate("(el) => el.click()")
                except Exception:
                    loc.evaluate("(el) => el.click()")
                    time.sleep(4)
            except Exception as e:
                logger.debug(f"[FULFIL/{runner_name}] continue click failed idx={b['idx']}: {e}")
                continue
            after = self._snapshot_gate(page)
            new_url = after.get("url") or ""
            moved = new_url != before
            in_flow = any(m in new_url.lower() for m in flow)
            pay = bool(after.get("markers", {}).get("has_pay_now")) or "payment" in new_url.lower()
            merged_log["fulfilment_steps"].append({
                "action": "continue_clicked", "control": b["text"], "idx": b["idx"],
                "url_before": before, "navigated": moved,
                "still_in_checkout_flow": in_flow, "payment_markers": pay, **after,
            })
            logger.info(f"[FULFIL/{runner_name}] '{b['text']}' -> {new_url} "
                        f"moved={moved} in_flow={in_flow} payment={pay}")
            if moved and not in_flow:
                merged_log.setdefault("observed_exits", []).append(
                    {"from": before, "to": new_url, "ts": time.time()})
                logger.warning(f"[FULFIL/{runner_name}] left checkout flow. Restoring {before}")
                try:
                    page.goto(before, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                except Exception:
                    pass
                return False
            if pay or (moved and in_flow):
                return True
        return False


    def _walk_fulfilment_gate(self, page, merged_log: dict, all_requests: list, runner_name: str) -> dict:
        """
        Evidence-driven gate. Supports BOTH observed orderings:
          (a) postcode asked upfront
          (b) delivery method first, postcode rendered conditionally afterwards
        Every sub-action records a Meta delta. Nothing is assumed about the platform.
        """
        out = {"attempted": False, "postcode": False, "delivery": False, "payment_reached": False}
        snap = self._snapshot_gate(page)
        m = snap.get("markers", {})
        if not (m.get("asks_postcode") or m.get("choose_delivery")):
            logger.info(f"[FULFIL/{runner_name}] No fulfilment gate evidenced on {page.url}. Not acting.")
            return out
        out["attempted"] = True
        # CMP on this class of stack renders at checkout, not at landing.
        merged_log["consent_at_gate"] = self._handle_consent(page, merged_log, runner_name)
        self._record_meta_delta(merged_log, all_requests, page, "after_consent")

        # Pass 1 — postcode only if already rendered (upfront-ask platforms).
        if m.get("asks_postcode"):
            out["postcode"] = self._enter_postcode(page, merged_log, runner_name)
            self._record_meta_delta(merged_log, all_requests, page, "after_postcode")
            caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
            self._merge_funnel_captures(merged_log, caps, "after_postcode")

        # Pass 2 — delivery method. On SFCC this RENDERS the postcode field.
        out["delivery"] = self._select_delivery_option(page, merged_log, runner_name)
        self._record_meta_delta(merged_log, all_requests, page, "after_delivery")
        caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
        self._merge_funnel_captures(merged_log, caps, "after_delivery")

        # Pass 3 — re-check: did the delivery choice reveal a postcode field?
        if not out["postcode"]:
            post = self._snapshot_gate(page)
            if post.get("markers", {}).get("asks_postcode"):
                logger.info(f"[FULFIL/{runner_name}] Postcode field appeared AFTER delivery selection. Filling now.")
                out["postcode"] = self._enter_postcode(page, merged_log, runner_name)
                self._record_meta_delta(merged_log, all_requests, page, "after_postcode")
                caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
                self._merge_funnel_captures(merged_log, caps, "after_postcode")

        # Pass 4 — forward control. Stops at payment. Never pays.
        out["payment_reached"] = self._continue_to_payment(page, merged_log, runner_name)
        self._record_meta_delta(merged_log, all_requests, page, "after_continue")
        caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=20)
        self._merge_funnel_captures(merged_log, caps, "payment_gate")

        # Pass 5 — one bounded retry if a required postcode is still outstanding.
        # Pass 5 — a successful postcode re-renders the page and exposes a NEW
        # forward control. Poll for it (bounded), then act. Never pays.
        if not out["payment_reached"]:
            _dl = time.time() + 10
            while time.time() < _dl:
                late = self._snapshot_gate(page)
                lm = late.get("markers", {})
                if lm.get("asks_postcode") and not out["postcode"]:
                    logger.info(f"[FULFIL/{runner_name}] postcode outstanding - retry once")
                    out["postcode"] = self._enter_postcode(page, merged_log, runner_name)
                    self._record_meta_delta(merged_log, all_requests, page, "after_postcode_retry")
                    break
                _txt = [str(x.get("text", "")).lower() for x in (late.get("buttons") or [])]
                if any(t.startswith(("continue", "proceed", "next", "deliver here", "use this"))
                       and not re.search(r"shopping|accept|required only|let me choose", t)
                       for t in _txt):
                    logger.info(f"[FULFIL/{runner_name}] new forward control appeared after postcode")
                    break
                time.sleep(1.0)
            out["payment_reached"] = self._continue_to_payment(page, merged_log, runner_name)
            self._record_meta_delta(merged_log, all_requests, page, "after_continue_retry")
            caps = self._wait_for_fbq_and_capture(page, all_requests, timeout=20)
            self._merge_funnel_captures(merged_log, caps, "payment_gate_retry")


        # Phase 2 — payment execution: classify blocker, capture boundary, try guest,
        # re-attempt forward, then record the payment stage. Never pays.
        if not out["payment_reached"]:
            _bl = self._classify_checkout_blocker(page, merged_log, runner_name)
            if _bl.get("kind") in ("auth_wall", "auth_wall_with_guest", "captcha"):
                self._capture_boundary_evidence(page, merged_log, all_requests,
                                                runner_name, f"boundary_{_bl['kind']}")
            if _bl.get("guest_available"):
                if self._attempt_guest_checkout(page, merged_log, runner_name, _bl):
                    out["guest_checkout"] = True
                    out["payment_reached"] = self._continue_to_payment(page, merged_log, runner_name)
                    self._record_meta_delta(merged_log, all_requests, page, "after_guest_continue")
            out["blocker"] = _bl.get("kind")
        _pay = self._capture_payment_stage(page, merged_log, all_requests, runner_name)
        out["payment_stage_reached"] = bool(_pay.get("reached"))
        if _pay.get("reached"):
            out["payment_reached"] = True
        merged_log["per_pixel"] = self._attribute_events_per_pixel(merged_log)


        final = self._snapshot_gate(page)
        merged_log["checkout_snapshot"] = final
        _bs = self._read_basket_state(page)
        merged_log["basket_state"].append({"phase": "fulfilment_final", **_bs})
        logger.info(f"[BASKET/{runner_name}] fulfilment_final: {json.dumps(_bs, default=str)[:600]}")
        logger.info(f"[FULFIL/{runner_name}] RESULT {json.dumps(out)} url={final.get('url')} markers={json.dumps(final.get('markers',{}))}")
        return out


    def _attempt_checkout_click(self, page) -> bool:
        """
        Click checkout with human-like interaction simulation.
        Rotated mouse movement, variable delays, scroll before click —
        defeats behavioral analysis of Cloudflare Bot Management, DataDome, Akamai.
        """
        def _dispatch_click(btn):
            """
            Same JS-dispatch mechanism as in _attempt_add_to_cart. Needed
            because the OneTrust consent overlay may also cover the checkout
            button and Playwright's Locator.click() may time out on it.
            """
            try:
                btn.evaluate("(el) => el.click()")
                return True
            except Exception as e:
                logger.debug(f"[FUNNEL] _dispatch_click (checkout) failed: {e}")
                return False

        self._last_checkout_snapshot = None
        for sel in ["button[name='checkout']", "input[name='checkout']",
                     "a[href*='/checkout']", "button:has-text('Checkout')",
                     "button:has-text('Check out')", "a.checkout-button"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    # Humanization 1: Scroll like a shopper
                    try:
                        for _ in range(random.randint(2, 4)):
                            y_off = random.randint(80, 220)
                            page.mouse.wheel(0, y_off)
                            time.sleep(random.uniform(0.15, 0.45))
                    except Exception:
                        pass
                    # Humanization 2: Curved mouse to the button
                    try:
                        box = btn.bounding_box()
                        if box:
                            target_x = box["x"] + box["width"] / 2 + random.uniform(-8, 8)
                            target_y = box["y"] + box["height"] / 2 + random.uniform(-8, 8)
                            start_x = random.randint(100, 800)
                            start_y = random.randint(100, 600)
                            steps = random.randint(8, 18)
                            for i in range(steps + 1):
                                t = i / steps
                                ease = t * t * (3 - 2 * t)
                                cx = start_x + (target_x - start_x) * ease
                                cy = start_y + (target_y - start_y) * ease
                                cx += random.uniform(-2, 2)
                                cy += random.uniform(-2, 2)
                                page.mouse.move(cx, cy)
                                time.sleep(random.uniform(0.015, 0.05))
                    except Exception:
                        pass
                    # Humanization 3: Brief hesitation, then click with verification
                    time.sleep(random.uniform(0.25, 0.9))
                    url_before = page.url
                    clicked = False
                    try:
                        with page.expect_navigation(timeout=15000):
                            _dispatch_click(btn)
                            clicked = True
                            url_after = page.url
                            # Accept any URL that is a checkout-flow step. SFCC's flow
                            # is /basket → /basket/fulfilment → /basket/payment → /checkout.
                            # /basket/fulfilment IS part of the checkout flow even though
                            # the literal token "checkout" is not in the URL. Treat the
                            # whole set as a successful checkout navigation.
                            checkout_url_markers = (
                                "checkout", "/basket/fulfilment", "/basket/payment",
                                "/basket/delivery", "/basket/summary",
                                "/on/demandware.store",
                            )
                            if url_after != url_before and any(
                                m in url_after.lower() for m in checkout_url_markers
                            ):
                                logger.info(f"[FUNNEL] Checkout click via {sel} — navigated to {url_after}")
                                # Page snapshot so the audit knows WHAT we reached, not just
                                # its URL. This turns 'pixel missing' from silence into a
                                # recorded fact we can reason about. Nothing here is
                                # assumed about the site — it just captures what is on
                                # the page at this moment.
                                try:
                                    snapshot = page.evaluate("""() => {
                                        const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                                        const buttons = [];
                                        document.querySelectorAll('button, a[role="button"], [role="button"]').forEach((el) => {
                                            const t = norm(el.innerText || el.textContent);
                                            if (!t || t.length > 80) return;
                                            if (!(el.offsetWidth || el.offsetHeight)) return;
                                            buttons.push({
                                                text: t.slice(0, 60),
                                                disabled: !!el.disabled,
                                                cls: (el.className || '').toString().slice(0, 60)
                                            });
                                        });
                                        const body = norm(document.body.innerText || '');
                                        const lowered = body.toLowerCase();
                                        const markers = {
                                            has_checkout: lowered.includes('checkout'),
                                            has_pay_now: lowered.includes('pay now'),
                                            has_continue_payment: lowered.includes('continue to payment') || lowered.includes('proceed to payment'),
                                            has_minimum_spend: /minimum (spend|order)|add \\d|spend \\d|below (the )?minimum|minimum basket/i.test(lowered),
                                            has_out_of_stock: lowered.includes('out of stock'),
                                            has_delivery_unavailable: lowered.includes('delivery unavailable'),
                                            has_delivery_options: /choose delivery|delivery option|select (a )?delivery|delivery from|standard delivery|express delivery|click (&|and) collect/i.test(body),
                                            asks_postcode: /enter (your )?post ?code|post ?code for delivery/i.test(body),
                                            below_declared_threshold: /below\\s*[£$€]\\s?\\d/i.test(body),
                                            has_basket_empty: lowered.includes('your basket is empty') || lowered.includes('basket is empty'),
                                            has_login_required: lowered.includes('sign in') || lowered.includes('log in'),
                                        };
                                        const basket_count_el = document.querySelector('[data-cart-count], .cart-count, .basket-count');
                                        const basket_count = basket_count_el ? norm(basket_count_el.textContent) : null;
                                        return {
                                            url: location.href,
                                            title: document.title,
                                            visible_button_texts: buttons.slice(0, 25),
                                            markers: markers,
                                            basket_count_visible: basket_count,
                                            body_snippet: body.slice(0, 400),
                                        };
                                    }""")
                                    logger.info(f"[FUNNEL] Checkout page snapshot: {json.dumps(snapshot, default=str)[:4000]}")
                                    self._last_checkout_snapshot = snapshot
                                except Exception as e:
                                    logger.debug(f"[FUNNEL] Checkout page snapshot failed: {e}")
                                return True
                            # Navigation happened but not to checkout; not success
                            logger.info(f"[FUNNEL] Checkout click via {sel} — navigated to {url_after} (not checkout)")
                    except Exception:
                        # Try response-based verification instead
                        try:
                            with page.expect_response(
                                lambda r: "checkout" in r.url.lower(),
                                timeout=8000,
                            ) as resp_info:
                                _dispatch_click(btn)
                                clicked = True
                                resp = resp_info.value
                                if 200 <= resp.status < 400:
                                    logger.info(f"[FUNNEL] Checkout click via {sel} — XHR response {resp.status} on {resp.url}")
                                    return True
                        except Exception:
                            if clicked:
                                pass
                    # No verified checkout for this selector; try the next one
            except Exception:
                continue

        # SPA settle: client-side routing can outrun the verification window.
        try:
            time.sleep(4)
            settled = (page.url or "").lower()
            if any(m in settled for m in ("checkout", "/basket/fulfilment", "/basket/payment",
                                          "/basket/delivery", "/basket/summary",
                                          "/on/demandware.store")):
                self._last_checkout_snapshot = self._snapshot_gate(page)
                logger.info(f"[FUNNEL] Checkout confirmed after SPA settle: {page.url}")
                return True
        except Exception:
            pass
        logger.info("[FUNNEL] Checkout: no selector verified a checkout navigation or XHR")
        return False

    def _run_funnel_session(self, landing_url: str, runner_name: str,
                            page_factory, on_response_factory=None, max_steps: int = 6) -> dict:
        merged_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "detected_pixel_id": None, "gtm_id": None,
            "engine_used": f"funnel_{runner_name}",
            "blocked_status": None,
            "has_event_data": False, "has_initiate_checkout": False,
            "has_add_to_cart": False, "has_purchase_event": False,
            "has_shared_event_id": False, "has_unhashed_pii": False,
            "fbq_events_observed": [], "fbq_events_with_event_id": [],
            "funnel_steps": [],
            "meta_config_seen": False, "meta_fbevents_loaded": False,
            "meta_tr_events": [], "pixel_id_source": None,
            "synthetic_fbq_generated": False,
            "basket_state": [], "fulfilment_steps": [],
            "meta_observations_by_step": [], "items_added_verified": 0,
            "checkout_snapshot": None, "step_budget_exhausted": False,
        }
        page, all_requests = page_factory()

        def attach_listener():
            def on_response(response):
                req_url = response.url
                status = response.status
                all_requests.append({"url": req_url, "method": response.request.method, "status": status})
                if "connect.facebook.net/signals/config/" in req_url:
                    merged_log["meta_config_seen"] = True
                if "fbevents.js" in req_url:
                    merged_log["meta_fbevents_loaded"] = True
                if "facebook.com/tr" in req_url:
                    merged_log["pixel_fired"] = True
                    _m_id = RE_TR_PIXEL_ID.search(req_url)
                    _m_ev = RE_TR_EVENT.search(req_url)
                    merged_log.setdefault("meta_tr_events", []).append({
                        "pixel_id": _m_id.group(1) if _m_id else None,
                        "event": _m_ev.group(1) if _m_ev else None,
                        "page_url": page.url,
                        "ts": time.time(),
                    })
                    if _m_id and not merged_log.get("detected_pixel_id"):
                        merged_log["detected_pixel_id"] = _m_id.group(1)
                        merged_log["pixel_id_source"] = "network_tr"
                    try:
                        if response.request.post_data:
                            merged_log["capi_events"].append({
                                "url": req_url, "event_name": "client_event",
                                "raw_body": response.request.post_data[:2000],
                            })
                    except Exception:
                        pass
                if "graph.facebook.com" in req_url and "/events" in req_url:
                    match = RE_CAPI_URL.search(req_url)
                    if match:
                        pid = match.group(1)
                        entry = {"url": req_url, "event_name": "server_event", "pixel_id": pid}
                        try:
                            if response.request.post_data:
                                entry["raw_body"] = response.request.post_data[:2000]
                        except Exception:
                            pass
                        merged_log["capi_events"].append(entry)
                        if not merged_log.get("detected_pixel_id"):
                            merged_log["detected_pixel_id"] = pid
            page.on("response", on_response)

        attach_listener()
        self._apply_operator_session(page, merged_log, runner_name)
        # Blocked != absent. Capture attempts and failures, not just responses.
        def _on_req(req):
            try:
                merged_log.setdefault("request_attempts", []).append(
                    {"url": req.url, "method": req.method, "rt": req.resource_type})
            except Exception:
                pass

        def _on_reqfailed(req):
            try:
                merged_log.setdefault("blocked_requests", []).append(
                    {"url": req.url, "method": req.method,
                     "rt": req.resource_type, "failure": req.failure})
            except Exception:
                pass

        try:
            page.on("request", _on_req)
            page.on("requestfailed", _on_reqfailed)
        except Exception as e:
            logger.debug(f"[FUNNEL/{runner_name}] request listeners not attached: {e}")
        if callable(on_response_factory):
            try:
                extra = on_response_factory(page, merged_log, all_requests)
                if callable(extra):
                    page.on("response", extra)
            except Exception as e:
                logger.debug(f"[FUNNEL/{runner_name}] on_response_factory not attached: {e}")
        merged_log["session_fingerprint"] = hashlib.sha256(
            f"{landing_url}|{runner_name}|2399".encode()
        ).hexdigest()[:16]

        # Step 1: landing
        logger.info(f"[FUNNEL/{runner_name}] Step 1: Landing {landing_url}")
        try:
            page.goto(landing_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Landing failed: {e}")
            merged_log["blocked_status"] = "LANDING_FAILED"
            merged_log["requests"] = all_requests
            return merged_log
        merged_log["funnel_steps"].append({"step": 1, "url": landing_url, "status": "landed"})

        # Dismiss any consent / cookie overlay before interacting with ATC or
        # checkout. Proven necessary by /tmp/probe_click_diff.log: the OneTrust
        # dark filter overlay sits on top of the ATC button and prevents any
        # hit-test-based click from reaching it. Dismissing here is the first
        # line of defense; the JS-dispatch click in _attempt_add_to_cart is the
        # second.
        try:
            self._dismiss_popups(page)
        except Exception as e:
            logger.debug(f"[FUNNEL/{runner_name}] _dismiss_popups failed: {e}")
        merged_log["consent_result"] = self._handle_consent(page, merged_log, runner_name)
        content = page.content()

        if "challenges.cloudflare.com" in content or "<title>Just a moment..." in content:
            merged_log["blocked_status"] = "CF_CHALLENGE_DETECTED"
            logger.warning(f"[FUNNEL/{runner_name}] Blocked at landing.")
            merged_log["requests"] = all_requests
            return merged_log

        # Network config bundle extraction FIRST (survives sandbox)
        if not merged_log.get("detected_pixel_id"):
            net_pid = self._extract_pixel_id_from_network(all_requests)
            if net_pid:
                merged_log["detected_pixel_id"] = net_pid
                merged_log["meta_config_seen"] = True
                merged_log["pixel_id_source"] = "network_config_bundle"
                merged_log["engine_used"] = f"funnel_{runner_name}_network"
                logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (landing): {net_pid}")

        # fbq capture for event data
        captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=10)
        merged_log = self._merge_funnel_captures(merged_log, captures, "landing")
        self._record_meta_delta(merged_log, all_requests, page, "landing")
        m_gtm = RE_GTM_ID.search(content)
        if m_gtm:
            merged_log["gtm_id"] = m_gtm.group(0)

        # Step 2: determine the product URL to walk
        # If landing is already a product page, use it directly. Otherwise search the page.
        product_url = self._find_product_link(page, landing_url)
        if not product_url:
            logger.info(f"[FUNNEL/{runner_name}] No product on landing. Trying /collections/all and /shop")
            for fallback in ("/collections/all", "/shop", "/products"):
                try:
                    fb_url = urljoin(landing_url, fallback)
                    page.goto(fb_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                    captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=8)
                    merged_log = self._merge_funnel_captures(
                        merged_log,
                        captures,
                        f"fallback_{fallback.strip('/')}",
                    )
                    self._record_meta_delta(
                        merged_log,
                        all_requests,
                        page,
                        f"fallback_{fallback.strip('/')}",
                    )
                    product_url = self._find_product_link(page, fb_url)
                    if product_url:
                        break
                except Exception as e:
                    logger.debug(f"[FUNNEL/{runner_name}] Fallback {fallback} failed: {e}")
        if not product_url:
            logger.warning(f"[FUNNEL/{runner_name}] No product found. Ending at landing.")
            merged_log["requests"] = all_requests
            return merged_log

        # Step 2b: navigate to the product page only if it differs from the current page
        if product_url.rstrip("/") != landing_url.rstrip("/"):
            logger.info(f"[FUNNEL/{runner_name}] Step 2: Product {product_url}")
        else:
            logger.info(f"[FUNNEL/{runner_name}] Step 2: Already on product page, continuing")
        try:
            if product_url.rstrip("/") != landing_url.rstrip("/"):
                page.goto(product_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)
            merged_log["funnel_steps"].append({"step": 2, "url": product_url, "status": "landed"})
            # Network config bundle extraction FIRST
            if not merged_log.get("detected_pixel_id"):
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["meta_config_seen"] = True
                    merged_log["pixel_id_source"] = "network_config_bundle"
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (product): {net_pid}")
            captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
            merged_log = self._merge_funnel_captures(merged_log, captures, "product")
            self._record_meta_delta(merged_log, all_requests, page, "product")
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Product load failed: {e}")
        product_content = page.content()
        m_shop = re.search(r'cdn\.shopify\.com/s/files/1/(\d+)/', product_content)
        m_theme = re.search(r'cdn\.shopify\.com/s/files/1/\d+/t/(\d+)/', product_content)
        shop_id = m_shop.group(1) if m_shop else None
        theme_id = m_theme.group(1) if m_theme else None

        # Step 3: add to cart (multi-item, verified — see _build_multi_item_basket).
        # Tier 0 intentionally does NOT pre-select the size <select>: proven by
        # probe_atc_deep.log that SFCC adds the SKU already present in the URL and
        # that touching the select swaps SKU + rebinds the ATC handler to a stale tree.
        logger.info(f"[FUNNEL/{runner_name}] Step 3: Multi-item basket build")
        items_added = self._build_multi_item_basket(
            page,
            product_url,
            runner_name,
            merged_log,
            all_requests,
            landing_url=landing_url,
        )
        atc_ok = items_added > 0
        logger.info(f"[FUNNEL/{runner_name}] Step 3: verified_items={items_added}")
        time.sleep(3)
        merged_log["funnel_steps"].append({
            "step": 3,
            "url": page.url,
            "status": "basket_built",
            "success": atc_ok,
            "items_added_verified": items_added,
        })

        if not atc_ok:
            logger.info(f"[FUNNEL/{runner_name}] ATC recovery: variant selection attempt")
            if self._try_select_variant_if_needed(page):
                self._reselect_current_sku_if_needed(page)
                time.sleep(1.5)
                if self._attempt_add_to_cart(page, page.url):
                    merged_log["items_added_verified"] = merged_log.get("items_added_verified", 0) + 1
                    atc_ok = True
                    logger.info(f"[FUNNEL/{runner_name}] ATC recovery succeeded after variant selection")
                    for _st in merged_log["funnel_steps"]:
                        if _st.get("step") == 3:
                            _st["items_added_verified"] = merged_log["items_added_verified"]
                            _st["success"] = True
                            _st["status"] = "basket_built_after_recovery"
                

        if not atc_ok:
            evidence = self._dump_atc_evidence(page)
            logger.warning(
                f"[FUNNEL/{runner_name}] ATC failed — DOM evidence: "
                f"{json.dumps(evidence, default=str)[:4000]}"
            )
            merged_log["atc_evidence"] = evidence

        # Network config bundle extraction FIRST
        if not merged_log.get("detected_pixel_id"):
            net_pid = self._extract_pixel_id_from_network(all_requests)
            if net_pid:
                merged_log["detected_pixel_id"] = net_pid
                merged_log["meta_config_seen"] = True
                merged_log["pixel_id_source"] = "network_config_bundle"
                merged_log["engine_used"] = f"funnel_{runner_name}_network"
                logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (atc): {net_pid}")
        captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
        merged_log = self._merge_funnel_captures(merged_log, captures, "add_to_cart")

        # Step 4: navigate to the cart URL we discovered. Do not gate on _url_exists —
        # the browser is the source of truth for whether the page loads.
        cart_url = self._find_cart_url(page, landing_url)
        cart_navigable = False
        if not cart_url:
            logger.info(f"[FUNNEL/{runner_name}] Step 4: No cart link discovered. Will attempt checkout on current page.")
            merged_log["funnel_steps"].append({
                "step": 4, "url": None, "status": "no_cart_link_on_page"
            })
        else:
            if not self._url_exists(cart_url):
                logger.info(
                    f"[FUNNEL/{runner_name}] Cart precheck negative for {cart_url}; "
                    f"browser remains source of truth."
                )
            logger.info(f"[FUNNEL/{runner_name}] Step 4: Cart {cart_url}")
            try:
                page.goto(cart_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(3)
                # Confirm we actually landed on a cart-shaped page
                landed_url = (page.url or "").lower()
                landed_body = (page.content() or "").lower()
                url_ok = any(k in landed_url for k in ("/cart", "/basket", "/bag", "/trolley", "/checkout"))
                body_ok = any(k in landed_body for k in (
                    "your basket", "your cart", "shopping bag",
                    "line item", "basket total", "cart total", "subtotal",
                    "checkout", "quantity",
                ))
                if url_ok or body_ok:
                        cart_navigable = True
                        _bs = self._read_basket_state(page)
                        merged_log["basket_state"].append({"phase": "cart_page", **_bs})
                        logger.info(f"[BASKET/{runner_name}] cart_page: {json.dumps(_bs, default=str)[:600]}")
                        merged_log["funnel_steps"].append({
                            "step": 4, "url": page.url, "status": "landed",
                            "url_ok": url_ok, "body_ok": body_ok, "basket": _bs,
                        })
                else:
                    merged_log["funnel_steps"].append({
                        "step": 4, "url": page.url, "status": "cart_navigation_bounced",
                        "url_ok": url_ok, "body_ok": body_ok,
                    })
                if not merged_log.get("detected_pixel_id"):
                    net_pid = self._extract_pixel_id_from_network(all_requests)
                    if net_pid:
                        merged_log["detected_pixel_id"] = net_pid
                        merged_log["meta_config_seen"] = True
                        merged_log["pixel_id_source"] = "network_config_bundle"
                        merged_log["engine_used"] = f"funnel_{runner_name}_network"
                        logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (cart): {net_pid}")
                captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
                merged_log = self._merge_funnel_captures(merged_log, captures, "cart")
                self._record_meta_delta(merged_log, all_requests, page, "cart")
            except Exception as e:
                logger.warning(f"[FUNNEL/{runner_name}] Cart navigation failed: {e}")
                merged_log["funnel_steps"].append({
                    "step": 4, "url": cart_url, "status": "cart_navigation_failed"
                })

        # Step 5: ALWAYS attempt checkout, whether on cart page or product page
        logger.info(f"[FUNNEL/{runner_name}] Step 5: Checkout attempt (on {'cart' if cart_navigable else 'current page'})")
        try:
            checkout_ok = self._attempt_checkout_click(page)
            merged_log["checkout_snapshot"] = getattr(self, "_last_checkout_snapshot", None)
            time.sleep(5)
            merged_log["funnel_steps"].append({
                "step": 5, "url": page.url, "status": "checkout_clicked", "success": checkout_ok
            })
            if not merged_log.get("detected_pixel_id"):
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["meta_config_seen"] = True
                    merged_log["pixel_id_source"] = "network_config_bundle"
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (checkout): {net_pid}")
            captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=25)
            merged_log = self._merge_funnel_captures(merged_log, captures, "checkout")
            self._record_meta_delta(merged_log, all_requests, page, "checkout")

            # Step 6: fulfilment gate — postcode -> delivery -> payment initiation.
            # This runs only after checkout navigation, never during product discovery.
            _in_checkout_flow = any(
                m in (page.url or "").lower()
                for m in ("checkout", "/basket/fulfilment", "/basket/payment",
                          "/basket/delivery", "/basket/summary", "/on/demandware.store")
            )
            if not (checkout_ok or _in_checkout_flow):
                merged_log["fulfilment_result"] = {"attempted": False, "reason": "not_in_checkout_flow"}
                logger.info(f"[FUNNEL/{runner_name}] Step 6 skipped: not in checkout flow ({page.url})")
            elif max_steps >= 6:
                gate = self._walk_fulfilment_gate(page, merged_log, all_requests, runner_name)
                merged_log["fulfilment_result"] = gate
                merged_log["funnel_steps"].append({
                    "step": 6, "url": page.url, "status": "fulfilment_walked", **gate,
                })
            else:
                merged_log["step_budget_exhausted"] = True

            if not merged_log.get("detected_pixel_id"):
                time.sleep(3)
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["meta_config_seen"] = True
                    merged_log["pixel_id_source"] = "network_config_bundle"
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network config (post-checkout): {net_pid}")
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Checkout attempt failed: {e}")
            merged_log["funnel_steps"].append({
                "step": 5, "url": page.url, "status": "checkout_failed"
            })

        # CDN fallback if still no pixel
        if not merged_log.get("detected_pixel_id") and shop_id and theme_id and cffi_requests:
            logger.info(f"[FUNNEL/{runner_name}] CDN fallback: theme {theme_id}")
            for fname in ["theme.js", "global.js", "vendor.js", "main.js"]:
                try:
                    asset_url = f"https://cdn.shopify.com/s/files/1/{shop_id}/t/{theme_id}/assets/{fname}"
                    r = cffi_requests.get(asset_url, impersonate="chrome120", timeout=8)
                    if r.status_code == 200:
                        fbq_match = RE_FBQ_INIT.search(r.text.lower())
                        if fbq_match:
                            pid = fbq_match.group(1)
                            if self._score_pixel_probability(pid, "CDN_FUNNEL") > 0.5:
                                merged_log["detected_pixel_id"] = pid
                                merged_log["pixel_id_source"] = "cdn_asset"
                                logger.info(f"[FUNNEL/{runner_name}] CDN fallback found pixel: {pid}")
                                break
                except Exception:
                    continue

        merged_log["requests"] = all_requests
        if merged_log["fbq_events_observed"]:
            merged_log["has_event_data"] = True

        # Record whether fbevents.js was EVER requested during this funnel run.
        # This tells us the difference between:
        #  (a) fbevents.js was never requested → the pixel is gated (consent / GTM / different page)
        #  (b) fbevents.js was requested but fbq() was never called → interceptor missed the call site
        #  (c) fbevents.js was requested and fbq() was called → normally cannot happen with 0 captures, but log it anyway
        fbevents_hits = [
            r for r in all_requests
            if isinstance(r, dict) and "connect.facebook.net" in str(r.get("url", "")) and "fbevents.js" in str(r.get("url", ""))
        ]
        config_bundle_hits = [
            r for r in all_requests
            if isinstance(r, dict) and "connect.facebook.net/signals/config" in str(r.get("url", ""))
        ]
        tr_hits = [
            r for r in all_requests
            if isinstance(r, dict) and "facebook.com/tr" in str(r.get("url", ""))
        ]
        meta_fb_summary = {
            "fbevents_js_requests": len(fbevents_hits),
            "config_bundle_requests": len(config_bundle_hits),
            "facebook_com_tr_requests": len(tr_hits),
            "fbevents_js_urls": [r["url"] for r in fbevents_hits[:3]],
            "config_bundle_urls": [r["url"] for r in config_bundle_hits[:3]],
        }
        merged_log["detected_pixel_ids"] = self._harvest_all_pixel_ids(all_requests, merged_log)
        merged_log["tealium_pixels"] = self._resolve_tealium_pixels(all_requests, landing_url)
        for _tp in (merged_log["tealium_pixels"] or []):
            if not any(e["pixel_id"] == _tp["pixel_id"] for e in merged_log["detected_pixel_ids"]):
                merged_log["detected_pixel_ids"].append(
                    {"pixel_id": _tp["pixel_id"], "sources": ["tealium_static"], "hits": 1})
        if not merged_log.get("detected_pixel_id") and merged_log["detected_pixel_ids"]:
            merged_log["detected_pixel_id"] = merged_log["detected_pixel_ids"][0]["pixel_id"]
            merged_log["pixel_id_source"] = merged_log["detected_pixel_ids"][0]["sources"][0]
        merged_log["per_pixel"] = self._attribute_events_per_pixel(merged_log)
        _rank = {"network_tr": 5, "network_config_bundle": 4, "fbq_track_single": 3,
                 "fbq_init": 2, "cdn_asset": 1, "tealium_static": 0}
        _best_src, _best_pid = None, None
        for _e in (merged_log.get("detected_pixel_ids") or []):
            for _s in (_e.get("sources") or []):
                if _best_src is None or _rank.get(_s, -1) > _rank.get(_best_src, -1):
                    _best_src, _best_pid = _s, _e["pixel_id"]
        if _best_src:
            merged_log["pixel_id_source"] = _best_src
            merged_log["detected_pixel_id"] = _best_pid
        merged_log["meta_fb_observations"] = meta_fb_summary
        merged_log["tracking_diagnostics"] = self._dump_tracking_diagnostics(page, all_requests)
        logger.warning(f"[FUNNEL/{runner_name}] META_FB_OBSERVATIONS: {json.dumps(meta_fb_summary, default=str)[:2000]}")
        logger.info(f"[FUNNEL/{runner_name}] Complete. pixel={merged_log.get('detected_pixel_id')}, "
                    f"events={merged_log.get('fbq_events_observed')}, "
                    f"steps={len(merged_log.get('funnel_steps', []))}")
        return merged_log

    def probe_funnel(self, landing_url: str) -> dict:
        """Multi-page funnel audit with post-funnel Meta validation."""
        result = None
        camoufox_result = None
        if CAMOUFOX_AVAILABLE:
            logger.info(f"[FUNNEL] Attempting with Camoufox for {landing_url}")
            try:
                with Camoufox(headless=False) as browser:
                    context = browser.new_context()
                    try:
                        context.add_init_script(FBQ_INTERCEPTOR_JS)
                    except Exception:
                        pass
                    page = context.new_page()
                    all_requests = []

                    def factory():
                        return page, all_requests

                    result = self._run_funnel_session(
                        landing_url, "camoufox", factory, None
                    )
                    camoufox_result = result
                    context.close()
                    _net_grade = (bool(result.get("meta_tr_events"))
                                  or bool(result.get("meta_config_seen"))
                                  or bool(result.get("fbq_events_observed")))
                    if result.get("detected_pixel_id") and _net_grade:
                        logger.info("[FUNNEL] Camoufox yielded NETWORK-grade pixel evidence. Skipping Ghost.")
                    else:
                        logger.info("[FUNNEL] Camoufox yielded no pixel. Trying Ghost, preserving Camoufox evidence.")
                        result = None
            except Exception as e:
                logger.warning(f"[FUNNEL] Camoufox funnel failed: {e}")

        if result is None:
            if not sync_playwright:
                return {
                    "pixel_fired": False, "requests": [], "capi_events": [],
                    "detected_pixel_id": None, "gtm_id": None,
                    "engine_used": "funnel_none", "blocked_status": "NO_ENGINES_AVAILABLE",
                    "has_event_data": False, "has_initiate_checkout": False,
                    "has_add_to_cart": False, "has_purchase_event": False,
                    "has_shared_event_id": False, "has_unhashed_pii": False,
                    "fbq_events_observed": [], "funnel_steps": [],
                }
            logger.info(f"[FUNNEL] Attempting with Ghost Protocol for {landing_url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=self.stealth_args_chromium + ["--incognito"]
                )
                context = browser.new_context(
                    user_agent=random.choice(self.uas),
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    timezone_id="America/New_York",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Windows"'
                    }
                )
                context.add_init_script(self._get_advanced_init_script())
                try:
                    context.add_init_script(FBQ_INTERCEPTOR_JS)
                except Exception:
                    pass
                page = context.new_page()
                all_requests = []

                def factory():
                    return page, all_requests

                try:
                    result = self._run_funnel_session(
                        landing_url, "ghost", factory, None
                    )
                finally:
                    context.close()
                    browser.close()

        def _union_engine_evidence(strong, weak):
            """Never discard the other engine's findings. Union, do not replace."""
            if not strong or not weak:
                return strong
            for k in ("meta_tr_events", "fbq_raw_calls", "blocked_requests",
                      "request_attempts", "capi_events", "boundary_evidence",
                      "checkout_blockers", "consent_events", "meta_observations_by_step"):
                a = strong.setdefault(k, [])
                seen = {json.dumps(x, sort_keys=True, default=str) for x in a if isinstance(x, (dict, list))}
                for x in (weak.get(k) or []):
                    s = json.dumps(x, sort_keys=True, default=str)
                    if s not in seen:
                        a.append(x); seen.add(s)
            ids = {e["pixel_id"]: e for e in (strong.get("detected_pixel_ids") or [])}
            for e in (weak.get("detected_pixel_ids") or []):
                t = ids.setdefault(e["pixel_id"], {"pixel_id": e["pixel_id"], "sources": [], "hits": 0})
                for sc in (e.get("sources") or []):
                    if sc not in t["sources"]:
                        t["sources"].append(sc)
                t["hits"] = max(t.get("hits", 0), e.get("hits", 0))
            strong["detected_pixel_ids"] = list(ids.values())
            for k in ("tealium_pixels", "payment_stage", "operator_session"):
                if not strong.get(k) and weak.get(k):
                    strong[k] = weak[k]
            for k in ("meta_config_seen", "meta_fbevents_loaded", "pixel_fired"):
                strong[k] = bool(strong.get(k)) or bool(weak.get(k))
            if not strong.get("detected_pixel_id") and weak.get("detected_pixel_id"):
                strong["detected_pixel_id"] = weak["detected_pixel_id"]
                strong["pixel_id_source"] = weak.get("pixel_id_source")
            return strong


        def _evidence_score(r):
            if not r:
                return -1
            g = r.get("fulfilment_result") or {}
            return (
                (100 if r.get("detected_pixel_id") else 0)
                + (150 if r.get("meta_tr_events") else 0)
                + (40 if r.get("meta_config_seen") else 0)
                + (30 if r.get("fbq_events_observed") else 0)
                + (10 if g.get("postcode") else 0)
                + 10 * int(r.get("items_added_verified") or 0)
                + (20 if g.get("attempted") else 0)
                + (5 if g.get("payment_reached") else 0)
                + len(r.get("funnel_steps") or [])
                - (50 if r.get("blocked_status") else 0)
            )
        if _evidence_score(camoufox_result) > _evidence_score(result):
            logger.info("[FUNNEL] Camoufox run carried stronger evidence. Using it.")
            result = camoufox_result
            result = _union_engine_evidence(result, camoufox_result if result is not camoufox_result else None)

        if result is not None and camoufox_result is not None and result is not camoufox_result:
            result = _union_engine_evidence(result, camoufox_result)
        if result and result.get("detected_pixel_id"):
            pid = result["detected_pixel_id"]
            logger.info(f"[FUNNEL] Validating pixel {pid} against Meta config...")
            _val_by_id = {}
            _ids = [pid] + [e["pixel_id"] for e in (result.get("detected_pixel_ids") or [])]
            for _p in dict.fromkeys(_ids):
                _val_by_id[_p] = self._validate_pixel_via_config(_p)
            result["pixel_validation"] = _val_by_id.get(pid)
            result["pixel_validations"] = list(_val_by_id.values())
            result["pixel_evidence_grade"] = (
                "network_transmission" if result.get("meta_tr_events")
                else "network_config" if result.get("meta_config_seen")
                else "browser_call" if result.get("fbq_events_observed")
                else "static_only"
            )
            result["per_pixel"] = self._attribute_events_per_pixel(result)
            result["tracking_mode_inferred"] = self._infer_tracking_mode(result)
            logger.info(
                f"[FUNNEL] pixel={pid} | "
                f"config_verdict={result['pixel_validation']['verdict']} | "
                f"tracking_mode={result['tracking_mode_inferred']}"
            )
        elif result:
            result["pixel_validation"] = None
            result["tracking_mode_inferred"] = "unknown"
        return result

    # ------------------------------------------------------------------ #
    # Orchestrator
    # ------------------------------------------------------------------ #
    def probe(self, url: str, force_ecommerce: bool = False) -> dict:
        """Main Entry Point: Hybrid Stealth Swarm."""
        domain_lower = urlparse(url).netloc.lower()
        enterprise_domains = ["amazon.", "alibaba.", "walmart.", "target.", "ebay.", "etsy.com", "tiktok.com", "facebook.com", "instagram.com", "youtube.com", "ulta.com", "reitmans.com"]
        if any(m in domain_lower for m in enterprise_domains):
            return {
                "pixel_fired": True, "requests": [], "capi_events": [],
                "has_unhashed_pii": False, "has_initiate_checkout": True,
                "has_add_to_cart": True, "has_shared_event_id": True,
                "has_purchase_event": True, "is_checkout_page": False,
                "is_enterprise": True, "engine_used": "exempt",
                "has_event_data": True, "fbq_events_observed": [],
            }
        final_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "has_unhashed_pii": False, "has_initiate_checkout": False,
            "has_add_to_cart": False, "has_shared_event_id": True,
            "has_purchase_event": False, "is_checkout_page": False,
            "detected_pixel_id": None, "gtm_id": None,
            "visited_pages": [url], "blocked_status": None,
            "platform_hints": [], "engine_used": "none",
            "has_event_data": False, "fbq_events_observed": [],
        }
        gtm_id = None
        _tier1_html = None

        # --- TIER 0: Shopify Web Pixels Sandbox (Static) ---
        logger.info(f"[SWARM] Checking Shopify Web Pixels Sandbox for {url}...")
        sandbox_log = self._probe_with_shopify_sandbox(url)
        if sandbox_log and sandbox_log.get("detected_pixel_id"):
            final_log.update(sandbox_log)
            logger.info(f"[SWARM] SUCCESS via Shopify Sandbox! Pixel: {sandbox_log['detected_pixel_id']}")
            final_log["pixel_validation"] = self._validate_pixel_via_config(sandbox_log["detected_pixel_id"])
            final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
            return final_log

        # --- TIER 1: Static GTM Resolver (early, before browser engines) ---
        if cffi_requests:
            try:
                resp = cffi_requests.get(url, impersonate="chrome120", timeout=15)
                if resp.status_code == 200:
                    _tier1_html = resp.text
                    gtm_matches = RE_GTM_ID.findall(resp.text)
                    if gtm_matches:
                        gtm_id = gtm_matches[0]
                        logger.info(f"[SWARM] Found GTM container {gtm_id}, resolving statically...")
                        resolved_pixels = self._resolve_gtm_container_pixels(gtm_id, url)
                        if resolved_pixels:
                            best_pid = resolved_pixels[0][0]
                            final_log["detected_pixel_id"] = best_pid
                            final_log["pixel_fired"] = True
                            final_log["gtm_id"] = gtm_id
                            final_log["engine_used"] = "gtm_static_resolver"
                            logger.info(f"[SWARM] SUCCESS via GTM Static Resolver! Pixel: {best_pid}")
                            final_log["pixel_validation"] = self._validate_pixel_via_config(best_pid)
                            final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                            return final_log
            except Exception as e:
                logger.debug(f"[SWARM] Early GTM check failed: {e}")

        # --- TIER 2: invisible_playwright (C++-level Firefox) ---
        if INVISIBLE_AVAILABLE:
            logger.info(f"[SWARM] Starting invisible_playwright Probe for {url}...")
            iw_log = self._probe_with_invisible(url)
            if iw_log:
                final_log.update(iw_log)
                if iw_log.get("detected_pixel_id"):
                    logger.info(f"[SWARM] SUCCESS via invisible_playwright! Pixel: {iw_log['detected_pixel_id']}")
                    final_log["pixel_validation"] = self._validate_pixel_via_config(iw_log["detected_pixel_id"])
                    final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                    return final_log
                elif iw_log.get("blocked_status"):
                    logger.warning(f"[SWARM] invisible_playwright blocked ({iw_log['blocked_status']}). Falling back.")
                else:
                    logger.info(f"[SWARM] invisible_playwright completed but no Pixel found. Trying Camoufox.")

        # --- TIER 3: Camoufox ---
        logger.info(f"[SWARM] Starting Camoufox Probe for {url}...")
        cf_log = self._probe_with_camoufox(url)
        if cf_log:
            final_log.update(cf_log)
            if cf_log.get("detected_pixel_id"):
                logger.info(f"[SWARM] SUCCESS via Camoufox! Pixel: {cf_log['detected_pixel_id']}")
                final_log["detected_pixel_id"] = cf_log["detected_pixel_id"]
                final_log["pixel_validation"] = self._validate_pixel_via_config(cf_log["detected_pixel_id"])
                final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                return final_log
            elif cf_log.get("blocked_status"):
                logger.warning(f"[SWARM] Camoufox Blocked. Falling back to Ghost Protocol.")
            else:
                logger.info(f"[SWARM] Camoufox completed but no Pixel found. Trying Ghost Protocol.")

        # --- TIER 4: Ghost Protocol ---
        logger.info(f"[SWARM] Starting Ghost Protocol for {url}...")
        ghost_log = self._probe_with_ghost_protocol(url)
        if ghost_log:
            if final_log.get("requests"):
                existing_urls = {r["url"] for r in final_log["requests"]}
                new_reqs = [r for r in ghost_log.get("requests", []) if r["url"] not in existing_urls]
                final_log["requests"].extend(new_reqs)
            else:
                final_log.update(ghost_log)
            for k in ("has_event_data", "has_add_to_cart", "has_initiate_checkout",
                       "has_purchase_event", "has_shared_event_id", "has_unhashed_pii",
                       "fbq_events_observed"):
                if ghost_log.get(k) not in (None, False, [], ""):
                    final_log[k] = ghost_log[k]
            if ghost_log.get("detected_pixel_id"):
                logger.info(f"[SWARM] SUCCESS via Ghost Protocol! Pixel: {ghost_log['detected_pixel_id']}")
                final_log["detected_pixel_id"] = ghost_log["detected_pixel_id"]
                final_log["pixel_validation"] = self._validate_pixel_via_config(ghost_log["detected_pixel_id"])
                final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                return final_log
            if ghost_log.get("gtm_id"):
                final_log["gtm_id"] = ghost_log["gtm_id"]


        # --- TIER 4.5: Tor-routed HTML + Universal Asset Sweep ---
        # Reuses TIER 1 HTML when present. Engages ManagedTor circuit rotation
        # only when the direct fetch was blocked. Sweeps bundled JS/CSS assets
        # for pixels that never surface in inline HTML.
        _sweep_html = _tier1_html
        if not _sweep_html:
            try:
                _sweep_html, _tor_err = self._fetch_html_via_managed_tor(url)
                if _tor_err:
                    logger.info(f"[SWARM] Tor HTML fetch unavailable ({_tor_err}). Asset sweep skipped.")
            except Exception as e:
                logger.debug(f"[SWARM] Tor HTML fetch failed: {e}")
        if _sweep_html:
            try:
                asset_pixels = self._universal_asset_scan(_sweep_html, urlparse(url).netloc)
                if asset_pixels:
                    best_pid, best_score = asset_pixels[0]
                    final_log["detected_pixel_id"] = best_pid
                    final_log["pixel_id_source"] = "universal_asset_scan"
                    final_log["engine_used"] = "universal_asset_scan"
                    final_log["asset_scan_score"] = best_score
                    final_log["pixel_validation"] = self._validate_pixel_via_config(best_pid)
                    final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                    logger.info(f"[SWARM] SUCCESS via Universal Asset Sweep! Pixel: {best_pid} (score={best_score})")
                    return final_log
            except Exception as e:
                logger.debug(f"[SWARM] Universal asset sweep failed: {e}")


        # --- TIER 5: Universal Data Extractor ---
        logger.info(f"[SWARM] Engaging Universal Data Extractor...")
        extraction_result = self.data_extractor.full_extract(url)
        if extraction_result["status"] == "success":
            final_log["detected_pixel_id"] = extraction_result["detected_pixel_id"]
            final_log["pixel_fired"] = True
            final_log["engine_used"] = extraction_result["engine_used"]
            logger.info(f"[SWARM] SUCCESS via Universal Extractor! Pixel: {extraction_result['detected_pixel_id']}")
            final_log["pixel_validation"] = self._validate_pixel_via_config(extraction_result["detected_pixel_id"])
            final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
            return final_log

        # --- TIER 6: Funnel escalation for e-commerce targets ---
        escalate = force_ecommerce or self._looks_like_ecommerce(url)
        if escalate:
            logger.info(
                f"[SWARM] Static tiers failed. Escalating to funnel navigation "
                f"for {url} (force_ecommerce={force_ecommerce})..."
            )
            try:
                funnel = self.probe_funnel(url)
                if (
                    funnel.get("detected_pixel_id")
                    or funnel.get("fulfilment_result", {}).get("attempted")
                    or funnel.get("items_added_verified", 0) > 0
                ):
                    final_log["detected_pixel_id"] = funnel.get("detected_pixel_id")
                    final_log["pixel_fired"] = bool(funnel.get("pixel_fired"))
                    final_log["engine_used"] = funnel.get("engine_used", "funnel_escalation")
                    final_log["pixel_validation"] = funnel.get("pixel_validation")
                    final_log["tracking_mode_inferred"] = funnel.get("tracking_mode_inferred")
                    final_log["fbq_events_observed"] = funnel.get("fbq_events_observed", [])
                    final_log["has_event_data"] = funnel.get("has_event_data", False)
                    final_log["has_add_to_cart"] = funnel.get("has_add_to_cart", False)
                    final_log["has_initiate_checkout"] = funnel.get("has_initiate_checkout", False)
                    final_log["has_purchase_event"] = funnel.get("has_purchase_event", False)
                    final_log["has_shared_event_id"] = funnel.get("has_shared_event_id", True)
                    final_log["has_unhashed_pii"] = funnel.get("has_unhashed_pii", False)
                    final_log["funnel_steps"] = funnel.get("funnel_steps", [])
                    for _k in (
                        "requests",
                        "capi_events",
                        "gtm_id",
                        "meta_fb_observations",
                        "meta_observations_by_step",
                        "meta_config_seen",
                        "meta_fbevents_loaded",
                        "meta_tr_events",
                        "pixel_id_source",
                        "synthetic_fbq_generated",
                        "basket_state",
                        "fulfilment_steps",
                        "fulfilment_result",
                        "items_added_verified",
                        "checkout_snapshot",
                        "fbq_events_with_event_id",
                        "session_fingerprint",
                        "fbq_raw_calls",
                        "fbq_call_types",
                        "tracking_diagnostics",
                        "per_pixel",
                        "pixel_evidence_grade",
                        "payment_stage",
                        "checkout_blockers",
                        "guest_attempts",
                        "boundary_evidence",
                        "operator_session",
                        "detected_pixel_ids",
                        "pixel_validations",
                        "tealium_pixels",
                        "consent_events",
                        "consent_result",
                        "request_attempts",
                        "blocked_requests",
                    ):
                        if funnel.get(_k) not in (None, [], {}, ""):
                            final_log[_k] = funnel[_k]
                    final_log["blocked_status"] = None
                    _pv = funnel.get("pixel_validation") or {}
                    if funnel.get("detected_pixel_id"):
                        logger.info(
                            f"[SWARM] SUCCESS via funnel escalation! "
                            f"Pixel: {funnel.get('detected_pixel_id')} | "
                            f"validation: {_pv.get('verdict')} | "
                            f"tracking: {funnel.get('tracking_mode_inferred')}"
                        )
                    else:
                        logger.warning(
                            f"[SWARM] Funnel completed WITHOUT pixel. Evidence preserved. "
                            f"items={funnel.get('items_added_verified')} | "
                            f"gate={funnel.get('fulfilment_result')} | "
                            f"meta={funnel.get('meta_fb_observations')}"
                        )
                    return final_log
            except Exception as e:
                logger.warning(f"[SWARM] Funnel escalation failed: {e}")
        final_log["blocked_status"] = "ALL_VECTORS_FAILED"
        logger.error(f"[SWARM] Critical Failure: No Pixel ID found.")
        return final_log

    def _simulate_human_scroll(self, page):
        try:
            height = page.evaluate("document.body.scrollHeight")
            steps = 5
            step_height = height // steps
            for i in range(steps):
                page.mouse.wheel(0, step_height)
                time.sleep(random.uniform(0.5, 1.5))
            page.mouse.wheel(0, -height)
            time.sleep(1.0)
        except Exception as e:
            logger.debug(f"Scroll simulation failed: {e}")

    # ------------------------------------------------------------------ #
    # E-COMMERCE DETECTION (resilient — survives WAF blocks)
    # ------------------------------------------------------------------ #
    def _looks_like_ecommerce(self, url: str) -> bool:
        """
        Heuristic: is this URL a store with a checkout funnel worth walking?
        Resilient to WAF blocks:
        - If the main page returns 200, scans body markers.
        - If the main page returns 403/503, checks response headers (x-shopid)
          and probes known e-commerce endpoints (/cart, /products.json,
          /wp-json/wc/store/products).
        """
        if not cffi_requests:
            return False
        proxy_cfg = self.tor_daemon.get_proxy_config()
        markers = [
            "shopify", "cdn.shopify.com", "myshopify",
            "woocommerce", "wp-content/plugins/woocommerce",
            "bigcommerce", "bigcommerce.com/s-",
            "add-to-cart", "add_to_cart", "product-form",
            '"@type": "product"', "application/ld+json",
        ]
        try:
            resp = cffi_requests.get(
                url,
                impersonate="chrome120",
                timeout=10,
                proxies=proxy_cfg,
                allow_redirects=True,
            )
            body = (resp.text or "").lower()
            headers_str = str(resp.headers).lower()
            if any(m in body for m in markers):
                logger.info(f"[ECOMM] Body marker hit on {url}")
                return True
            if any(h in headers_str for h in ("x-shopid", "x-shopify-stage", "x-sorting-hat-pod")):
                logger.info(f"[ECOMM] Shopify header hit on {url}")
                return True
            for probe_path in ("/cart", "/cart.js"):
                try:
                    p_resp = cffi_requests.head(
                        urljoin(url, probe_path),
                        impersonate="chrome120",
                        timeout=5,
                        proxies=proxy_cfg,
                        allow_redirects=False,
                    )
                    if p_resp.status_code in (200, 302):
                        logger.info(f"[ECOMM] /cart responded {p_resp.status_code} on {url}")
                        return True
                except Exception:
                    pass
            try:
                products_resp = cffi_requests.get(
                    urljoin(url, "/products.json?limit=1"),
                    impersonate="chrome120",
                    timeout=5,
                    proxies=proxy_cfg,
                )
                if products_resp.status_code == 200:
                    try:
                        data = products_resp.json()
                        if isinstance(data, dict) and "products" in data:
                            logger.info(f"[ECOMM] Shopify products.json hit on {url}")
                            return True
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                wc_resp = cffi_requests.get(
                    urljoin(url, "/wp-json/wc/store/products"),
                    impersonate="chrome120",
                    timeout=5,
                    proxies=proxy_cfg,
                )
                if wc_resp.status_code == 200:
                    logger.info(f"[ECOMM] WooCommerce store API hit on {url}")
                    return True
            except Exception:
                pass
            if "bigcommerce" in headers_str or "stencil" in headers_str:
                logger.info(f"[ECOMM] BigCommerce header hit on {url}")
                return True
            logger.info(f"[ECOMM] No e-commerce signals found for {url}")
            return False
        except Exception as e:
            logger.debug(f"[ECOMM] Detection exception for {url}: {e}")
            return False