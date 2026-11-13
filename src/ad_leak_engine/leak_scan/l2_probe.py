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

# NEW: Advanced Patterns for Minified GTM Containers
RE_GTM_MINIFIED_PIXEL = re.compile(r'["\'](?:pixelId|fb_pixel_id|metaPixelId|facebook_pixel_id)["\']\s*[:=]\s*["\']?(\d{10,16})["\']?', re.IGNORECASE)
RE_VAR_PIXEL_ASSIGN = re.compile(r'(?:var|let|const)\s+(?:pixelId|fbPixelId|metaPixelId)\s*=\s*["\'](\d{10,16})["\']', re.IGNORECASE)

# NEW: PII heuristic — SHA-256 hex is 64 chars lowercase; a raw email or phone is not
RE_HEX64 = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)
RE_EMAIL_RAW = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
RE_PHONE_RAW = re.compile(r'^\+?[\d\s\-()]{7,20}$')


# ---------------------------------------------------------------------- #
# MODULE-LEVEL: JavaScript that intercepts fbq() before any page script
# runs and stores every call with its payload on window.__fbq_captured.
# ---------------------------------------------------------------------- #
FBQ_INTERCEPTOR_JS = r"""
(function() {
    if (window.__fbq_interceptor_installed) return;
    window.__fbq_interceptor_installed = true;
    window.__fbq_captured = [];

    var real_fbq = null;
    try { real_fbq = window.fbq; } catch (e) {}

    function safe_clone(x) {
        try { return JSON.parse(JSON.stringify(x)); }
        catch (e) { return String(x); }
    }

    function capture(call_type, args) {
        try {
            var record = {
                ts: Date.now(),
                call_type: call_type,
                args: [],
            };
            for (var i = 0; i < args.length; i++) {
                if (args[i] !== null && typeof args[i] === 'object') {
                    record.args.push(safe_clone(args[i]));
                } else {
                    record.args.push(args[i]);
                }
            }
            window.__fbq_captured.push(record);
        } catch (e) { /* never break the page */ }
    }

    function proxy_fbq() {
        try {
            var args = Array.prototype.slice.call(arguments);
            if (args.length > 0 && typeof args[0] === 'string') {
                capture(args[0], args.slice(1));
            }
        } catch (e) {}
        if (real_fbq && typeof real_fbq === 'function') {
            return real_fbq.apply(window, arguments);
        }
    }

    if (real_fbq) {
        for (var k in real_fbq) {
            try { proxy_fbq[k] = real_fbq[k]; } catch (e) {}
        }
    }
    proxy_fbq.queue = [];
    proxy_fbq.loaded = true;
    proxy_fbq.version = '2.0';
    proxy_fbq._captured = window.__fbq_captured;

    Object.defineProperty(window, 'fbq', {
        configurable: true,
        get: function() { return proxy_fbq; },
        set: function(v) {
            if (typeof v === 'function' && v !== proxy_fbq) {
                real_fbq = v;
            }
        },
    });
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

        while time.time() < deadline:
            if not fb_js_loaded:
                fb_js_loaded = any(
                    "connect.facebook.net" in str(r.get("url", ""))
                    and "fbevents.js" in str(r.get("url", ""))
                    for r in all_requests if isinstance(r, dict)
                )

            try:
                captures = page.evaluate("window.__fbq_captured || []")
                if captures:
                    logger.info(f"[FBQ_WAIT] Captured {len(captures)} fbq call(s) after "
                                f"{timeout - (deadline - time.time()):.1f}s")
                    return captures
            except Exception:
                captures = []

            time.sleep(0.5)

        # Last-resort synthesis: fbevents.js loaded but no fbq('init') was called.
        if fb_js_loaded and not captures:
            logger.warning("[FBQ_WAIT] fbevents.js loaded but no fbq call captured. "
                           "Attempting synthetic init.")
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
                    if captures:
                        logger.info(f"[FBQ_WAIT] Synthetic init succeeded. Captured {len(captures)} call(s).")
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
        if not captures:
            return out

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
                elif call_type == "track" and len(args) >= 1:
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
                resp = page.goto(url, wait_until="networkidle", timeout=90000)

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
            const originalPermissionsQuery = navigator.permissions.query;
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
        for k in ("has_event_data", "has_add_to_cart", "has_initiate_checkout",
                  "has_purchase_event", "has_shared_event_id", "has_unhashed_pii"):
            if enriched.get(k):
                merged[k] = True
        merged["fbq_events_observed"] = list(dict.fromkeys(
            merged.get("fbq_events_observed", []) + enriched.get("fbq_events_observed", [])
        ))
        merged["fbq_events_with_event_id"] = (
            merged.get("fbq_events_with_event_id", []) + enriched.get("fbq_events_with_event_id", [])
        )
        logger.info(f"[FUNNEL] Step '{step_label}': {len(captures)} fbq call(s), "
                    f"events={enriched.get('fbq_events_observed')}")
        return merged

    def _find_product_link(self, page, base_url: str) -> str | None:
        selectors = [
            "a[href*='/products/']",
            "a[href*='/collections/'][href*='/products/']",
            "a[href*='/product/']",
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

    def _attempt_add_to_cart(self, page, product_url: str) -> bool:
        try:
            variant_id = page.evaluate("""() => {
                const input = document.querySelector('form[action*="/cart/add"] [name="id"]');
                return input ? input.value : null;
            }""")
            if variant_id:
                page.evaluate(f"""() => {{
                    fetch('/cart/add.js', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{id: {variant_id}, quantity: 1}})
                    }}).catch(e => console.error('ATC failed:', e));
                }}""")
                logger.info(f"[FUNNEL] Add-to-cart via fetch (variant {variant_id})")
                return True
        except Exception as e:
            logger.debug(f"[FUNNEL] Fetch ATC failed: {e}")

        for sel in [
            "button[name='add']",
            "button[type='submit']",
            ".product-form__submit",
            "button.single_add_to_cart_button",
            "button.add_to_cart_button",
            "button[data-button-action='add-to-cart']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    btn.click(timeout=5000)
                    logger.info(f"[FUNNEL] Add-to-cart via click ({sel})")
                    return True
            except Exception:
                continue
        return False

    def _attempt_checkout_click(self, page) -> bool:
        """
        Click checkout with human-like interaction simulation.
        Rotated mouse movement, variable delays, scroll before click —
        defeats behavioral analysis of Cloudflare Bot Management, DataDome, Akamai.
        """
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

                    # Humanization 3: Brief hesitation, then click
                    time.sleep(random.uniform(0.25, 0.9))
                    btn.click(timeout=5000)
                    time.sleep(5)
                    logger.info(f"[FUNNEL] Checkout click via {sel} (humanized)")
                    return True
            except Exception:
                continue
        return False

    def _run_funnel_session(self, landing_url: str, runner_name: str,
                            page_factory, on_response_factory, max_steps: int = 5) -> dict:
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
        }

        page, all_requests = page_factory()

        def attach_listener():
            def on_response(response):
                req_url = response.url
                status = response.status
                all_requests.append({"url": req_url, "method": response.request.method, "status": status})
                if "facebook.com/tr" in req_url:
                    merged_log["pixel_fired"] = True
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

        # Step 1: landing
        logger.info(f"[FUNNEL/{runner_name}] Step 1: Landing {landing_url}")
        try:
            page.goto(landing_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Landing failed: {e}")
            merged_log["blocked_status"] = "LANDING_FAILED"
            return merged_log

        merged_log["funnel_steps"].append({"step": 1, "url": landing_url, "status": "landed"})

        content = page.content()
        if "challenges.cloudflare.com" in content or "<title>Just a moment..." in content:
            merged_log["blocked_status"] = "CF_CHALLENGE_DETECTED"
            logger.warning(f"[FUNNEL/{runner_name}] Blocked at landing.")
            return merged_log

        # Network config bundle extraction FIRST (survives sandbox)
        if not merged_log.get("detected_pixel_id"):
            net_pid = self._extract_pixel_id_from_network(all_requests)
            if net_pid:
                merged_log["detected_pixel_id"] = net_pid
                merged_log["pixel_fired"] = True
                merged_log["engine_used"] = f"funnel_{runner_name}_network"
                logger.info(f"[FUNNEL/{runner_name}] Pixel from network (landing): {net_pid}")

        # fbq capture for event data
        captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=10)
        merged_log = self._merge_funnel_captures(merged_log, captures, "landing")

        m_gtm = RE_GTM_ID.search(content)
        if m_gtm:
            merged_log["gtm_id"] = m_gtm.group(0)

        # Step 2: find product
        product_url = self._find_product_link(page, landing_url)
        if not product_url:
            logger.info(f"[FUNNEL/{runner_name}] No product on landing. Trying /collections/all and /shop")
            for fallback in ("/collections/all", "/shop", "/products"):
                try:
                    fb_url = urljoin(landing_url, fallback)
                    page.goto(fb_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                    captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=8)
                    merged_log = self._merge_funnel_captures(merged_log, captures, f"fallback_{fallback.strip('/')}")
                    product_url = self._find_product_link(page, fb_url)
                    if product_url:
                        break
                except Exception as e:
                    logger.debug(f"[FUNNEL/{runner_name}] Fallback {fallback} failed: {e}")

        if not product_url:
            logger.warning(f"[FUNNEL/{runner_name}] No product found. Ending at landing.")
            merged_log["requests"] = all_requests
            return merged_log

        # Step 2b: product page
        logger.info(f"[FUNNEL/{runner_name}] Step 2: Product {product_url}")
        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(3)
            merged_log["funnel_steps"].append({"step": 2, "url": product_url, "status": "landed"})

            # Network config bundle extraction FIRST
            if not merged_log.get("detected_pixel_id"):
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["pixel_fired"] = True
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network (product): {net_pid}")

            captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
            merged_log = self._merge_funnel_captures(merged_log, captures, "product")
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Product load failed: {e}")

        product_content = page.content()
        m_shop = re.search(r'cdn\.shopify\.com/s/files/1/(\d+)/', product_content)
        m_theme = re.search(r'cdn\.shopify\.com/s/files/1/\d+/t/(\d+)/', product_content)
        shop_id = m_shop.group(1) if m_shop else None
        theme_id = m_theme.group(1) if m_theme else None

        # Step 3: add to cart
        logger.info(f"[FUNNEL/{runner_name}] Step 3: Add to cart")
        atc_ok = self._attempt_add_to_cart(page, product_url)
        time.sleep(4)
        merged_log["funnel_steps"].append({"step": 3, "url": page.url, "status": "atc_attempted", "success": atc_ok})

        # Network config bundle extraction FIRST
        if not merged_log.get("detected_pixel_id"):
            net_pid = self._extract_pixel_id_from_network(all_requests)
            if net_pid:
                merged_log["detected_pixel_id"] = net_pid
                merged_log["pixel_fired"] = True
                merged_log["engine_used"] = f"funnel_{runner_name}_network"
                logger.info(f"[FUNNEL/{runner_name}] Pixel from network (atc): {net_pid}")

        captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
        merged_log = self._merge_funnel_captures(merged_log, captures, "add_to_cart")

        # Step 4: cart
        cart_url = urljoin(landing_url, "/cart")
        logger.info(f"[FUNNEL/{runner_name}] Step 4: Cart {cart_url}")
        try:
            page.goto(cart_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(4)
            merged_log["funnel_steps"].append({"step": 4, "url": cart_url, "status": "landed"})

            # Network config bundle extraction FIRST
            if not merged_log.get("detected_pixel_id"):
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["pixel_fired"] = True
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network (cart): {net_pid}")

            captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=15)
            merged_log = self._merge_funnel_captures(merged_log, captures, "cart")

            # Step 5: checkout
            logger.info(f"[FUNNEL/{runner_name}] Step 5: Checkout attempt")
            checkout_ok = self._attempt_checkout_click(page)
            time.sleep(5)
            merged_log["funnel_steps"].append({
                "step": 5, "url": page.url, "status": "checkout_clicked", "success": checkout_ok
            })

            # [CRITICAL] Checkout is where fbevents.js actually loads on Shopify.
            # FIRST: network config bundle extraction (survives Shopify sandbox)
            if not merged_log.get("detected_pixel_id"):
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["pixel_fired"] = True
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network (checkout): {net_pid}")

            # SECOND: fbq capture for event payloads
            captures = self._wait_for_fbq_and_capture(page, all_requests, timeout=25)
            merged_log = self._merge_funnel_captures(merged_log, captures, "checkout")

            # [NEW] Post-checkout network scan — the config bundle may fire late
            if not merged_log.get("detected_pixel_id"):
                time.sleep(3)
                net_pid = self._extract_pixel_id_from_network(all_requests)
                if net_pid:
                    merged_log["detected_pixel_id"] = net_pid
                    merged_log["pixel_fired"] = True
                    merged_log["engine_used"] = f"funnel_{runner_name}_network"
                    logger.info(f"[FUNNEL/{runner_name}] Pixel from network (post-checkout): {net_pid}")
        except Exception as e:
            logger.warning(f"[FUNNEL/{runner_name}] Cart/checkout failed: {e}")

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
                                merged_log["pixel_fired"] = True
                                logger.info(f"[FUNNEL/{runner_name}] CDN fallback found pixel: {pid}")
                                break
                except Exception:
                    continue

        merged_log["requests"] = all_requests
        if merged_log["fbq_events_observed"]:
            merged_log["has_event_data"] = True

        logger.info(f"[FUNNEL/{runner_name}] Complete. pixel={merged_log.get('detected_pixel_id')}, "
                    f"events={merged_log.get('fbq_events_observed')}, "
                    f"steps={len(merged_log.get('funnel_steps', []))}")
        return merged_log

    def probe_funnel(self, landing_url: str) -> dict:
        """Multi-page funnel audit with post-funnel Meta validation."""
        result = None

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
                    context.close()
                    if result.get("detected_pixel_id"):
                        logger.info("[FUNNEL] Camoufox yielded pixel. Skipping Ghost.")
                    else:
                        logger.info("[FUNNEL] Camoufox yielded no pixel. Trying Ghost.")
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

        if result and result.get("detected_pixel_id"):
            pid = result["detected_pixel_id"]
            logger.info(f"[FUNNEL] Validating pixel {pid} against Meta config...")
            result["pixel_validation"] = self._validate_pixel_via_config(pid)
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

        # --- TIER 1: invisible_playwright (C++-level Firefox) ---
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

        # --- TIER 2: Camoufox ---
        logger.info(f"[SWARM] Starting Camoufox Probe for {url}...")
        cf_log = self._probe_with_camoufox(url)
        if cf_log:
            final_log.update(cf_log)
            if cf_log.get("detected_pixel_id"):
                logger.info(f"[SWARM] SUCCESS via Camoufox! Pixel: {cf_log['detected_pixel_id']}")
                final_log["detected_pixel_id"] = cf_log["detected_pixel_id"]  # [FIX] assign ID before validation
                final_log["pixel_validation"] = self._validate_pixel_via_config(cf_log["detected_pixel_id"])
                final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                return final_log
            elif cf_log.get("blocked_status"):
                logger.warning(f"[SWARM] Camoufox Blocked. Falling back to Ghost Protocol.")
            else:
                logger.info(f"[SWARM] Camoufox completed but no Pixel found. Trying Ghost Protocol.")

        # --- TIER 3: Ghost Protocol ---
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
                final_log["detected_pixel_id"] = ghost_log["detected_pixel_id"]  # [FIX] assign ID before validation
                final_log["pixel_validation"] = self._validate_pixel_via_config(ghost_log["detected_pixel_id"])
                final_log["tracking_mode_inferred"] = self._infer_tracking_mode(final_log)
                return final_log

            if ghost_log.get("gtm_id"):
                final_log["gtm_id"] = ghost_log["gtm_id"]

        # --- TIER 4: Universal Data Extractor ---
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

        # --- TIER 5: Static GTM Resolver ---
        gtm_id = final_log.get("gtm_id")
        if gtm_id:
            resolved_pixels = self._resolve_gtm_container_pixels(gtm_id, url)
            if resolved_pixels:
                best_pid = resolved_pixels[0][0]
                final_log["detected_pixel_id"] = best_pid
                final_log["pixel_fired"] = True
                final_log["engine_used"] = "static_resolver"
                logger.info(f"[SWARM] SUCCESS via Static Resolver! Pixel: {best_pid}")
                final_log["pixel_validation"] = self._validate_pixel_via_config(best_pid)
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
                if funnel.get("detected_pixel_id"):
                    final_log["detected_pixel_id"] = funnel["detected_pixel_id"]
                    final_log["pixel_fired"] = True
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
                    final_log["blocked_status"] = None
                    logger.info(
                        f"[SWARM] SUCCESS via funnel escalation! "
                        f"Pixel: {funnel['detected_pixel_id']} | "
                        f"validation: {funnel.get('pixel_validation', {}).get('verdict')} | "
                        f"tracking: {funnel.get('tracking_mode_inferred')}"
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