"""Universal Data Extractor [SEED: 2399].
Multi-vector approach to extract Pixel IDs and Theme Data without relying on unstable Tor/Browsers.
"""
import logging
import re
import json
import time
import random
from urllib.parse import urlparse
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

# Pre-compiled patterns
RE_FBQ_INIT = re.compile(r"""fbq\s*\(\s*['"]init['"]\s*,\s*['"](\d{8,})['"]""")
RE_PIXEL_JSON = re.compile(r'"pixelId"\s*:\s*"(\d{8,})"')
RE_GTM_ID = re.compile(r'GTM-[A-Z0-9]{4,}')
RE_SHOPIFY_THEME_ASSET = re.compile(r'cdn\.shopify\.com/s/themes/(\d+)/assets/')
RE_SHOPIFY_FILES_PATH = re.compile(r'cdn\.shopify\.com/s/files/1/(\d+)/t/(\d+)/')

class UniversalDataExtractor:
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        ]
        
    def _get_headers(self, referer=None):
        """Generates realistic headers."""
        ua = random.choice(self.user_agents)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    def extract_from_shopify_api(self, domain: str) -> dict | None:
        """
        Tier 1: Query Shopify Storefront API for theme/product data.
        Returns {'theme_id': ..., 'pixel_hint': ...} or None.
        """
        logger.info(f"[API_EXTRACT] Attempting Shopify API for {domain}...")
        
        # Try GraphQL Endpoint (often less restricted)
        graphql_url = f"https://{domain}/api/graphql"
        query = """
        {
          shop {
            name
            primaryDomain { url }
          }
        }
        """
        
        try:
            resp = cffi_requests.post(
                graphql_url,
                json={"query": query},
                headers=self._get_headers(referer=f"https://{domain}/"),
                impersonate="chrome120",
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data and 'shop' in data['data']:
                    logger.info("[API_EXTRACT] Shopify API Accessible.")
                    # Note: Public Storefront API doesn't expose Theme ID directly.
                    # But we can use this access to prove the domain is alive and open.
                    # We will proceed to scan assets based on common patterns if we have a hint.
                    return {"accessible": True, "source": "graphql"}
                    
        except Exception as e:
            logger.debug(f"[API_EXTRACT] GraphQL failed: {e}")
            
        # Try REST Endpoint /products.json (Public)
        rest_url = f"https://{domain}/products.json?limit=1"
        try:
            resp = cffi_requests.get(
                rest_url,
                headers=self._get_headers(referer=f"https://{domain}/"),
                impersonate="chrome120",
                timeout=10
            )
            if resp.status_code == 200:
                logger.info("[API_EXTRACT] REST API Accessible.")
                return {"accessible": True, "source": "rest"}
                
        except Exception as e:
            logger.debug(f"[API_EXTRACT] REST failed: {e}")
            
        return None

    def extract_from_gtm_static(self, gtm_id: str, domain: str) -> list[tuple[str, float]]:
        """
        Tier 2: Deep parse GTM container for Pixel IDs.
        """
        candidates = []
        url = f"https://www.googletagmanager.com/gtm.js?id={gtm_id}"
        
        try:
            resp = cffi_requests.get(url, impersonate="chrome120", timeout=10)
            if resp.status_code == 200:
                body = resp.text
                
                # Pattern 1: Direct fbq init
                matches = RE_FBQ_INIT.findall(body)
                for m in matches:
                    candidates.append((m, 0.95))
                    
                # Pattern 2: JSON config
                json_matches = RE_PIXEL_JSON.findall(body)
                for jm in json_matches:
                    candidates.append((jm, 0.85))
                    
                # Pattern 3: Minified keys
                minified_pattern = re.compile(r'["\'](?:pixelId|fb_pixel_id)["\']\s*[:=]\s*["\']?(\d{10,16})["\']?', re.IGNORECASE)
                mm_matches = minified_pattern.findall(body)
                for mm in mm_matches:
                    candidates.append((mm, 0.75))
                    
        except Exception as e:
            logger.error(f"[GTM_STATIC] Failed: {e}")
            
        return sorted(candidates, key=lambda x: x[1], reverse=True)

    def brute_force_theme_assets(self, domain: str, theme_id: str = None) -> list[tuple[str, float]]:
        """
        Tier 3: Scan common theme asset paths for Pixel IDs.
        If theme_id is unknown, tries common IDs or extracts from HTML if accessible via API.
        """
        candidates = []
        
        # Common filenames across platforms (Shopify, Woo, etc.)
        js_files = ["theme.js", "scripts.js", "global.js", "main.js", "app.js", "vendor.js", "bundle.js"]
        
        # Construct base URLs
        # Shopify Pattern: cdn.shopify.com/s/themes/{ID}/assets/{FILE}
        # WooCommerce Pattern: wp-content/themes/{THEME}/js/{FILE}
        # Generic: /js/{FILE}
        
        urls_to_try = []
        
        if theme_id:
            for fname in js_files:
                urls_to_try.append(f"https://cdn.shopify.com/s/themes/{theme_id}/assets/{fname}")
        
        # Always try generic paths
        for fname in js_files:
            urls_to_try.append(f"https://{domain}/js/{fname}")
            urls_to_try.append(f"https://{domain}/assets/{fname}")
            urls_to_try.append(f"https://{domain}/static/js/{fname}")
            
        logger.info(f"[BRUTE_FORCE] Scanning {len(urls_to_try)} asset paths...")
        
        for url in urls_to_try:
            try:
                resp = cffi_requests.get(url, impersonate="chrome120", timeout=5, headers=self._get_headers())
                if resp.status_code == 200:
                    body = resp.text.lower()
                    
                    # Check for fbq init
                    fbq_matches = RE_FBQ_INIT.findall(body)
                    for pid in fbq_matches:
                        candidates.append((pid, 0.9))
                        
                    # Check for variable assignment
                    var_pattern = re.compile(r'(?:var|let|const)\s+(?:pixelId|fbPixelId)\s*=\s*[\'"](\d{8,})[\'"]', re.IGNORECASE)
                    var_matches = var_pattern.findall(body)
                    for pid in var_matches:
                        candidates.append((pid, 0.8))
                        
            except Exception:
                continue
                
        # Deduplicate
        best = {}
        for pid, sc in candidates:
            if pid not in best or sc > best[pid]:
                best[pid] = sc
                
        return sorted(best.items(), key=lambda x: x[1], reverse=True)

    def full_extract(self, url: str) -> dict:
        """
        Main Entry Point: Executes all tiers sequentially until success.
        """
        domain = urlparse(url).netloc
        result = {
            "detected_pixel_id": None,
            "gtm_id": None,
            "theme_id": None,
            "engine_used": "none",
            "status": "failed"
        }
        
        # --- TIER 1: Check Accessibility & Get Hints ---
        api_data = self.extract_from_shopify_api(domain)
        if api_data:
            logger.info("[FULL_EXTRACT] Site is accessible via API. Proceeding to Asset Scan.")
            
        # --- TIER 2: Try to get GTM ID from Static Fetch (if possible) or Known List ---
        # Since we can't fetch HTML easily, we might miss GTM ID unless we have it from previous logs.
        # For now, we skip direct HTML fetch and go to Brute Force which covers most cases.
        
        # --- TIER 3: Brute Force Assets (Works for Shopify/Woo/Generic) ---
        # We don't have theme_id yet, so we try generic paths first.
        # If we had a way to guess theme_id, we'd add it here.
        candidates = self.brute_force_theme_assets(domain)
        
        if candidates:
            best_pid, score = candidates[0]
            result["detected_pixel_id"] = best_pid
            result["engine_used"] = "brute_force_assets"
            result["status"] = "success"
            logger.info(f"[FULL_EXTRACT] SUCCESS! Pixel: {best_pid} (Score: {score})")
            return result
            
        # --- FALLBACK: If no pixel found, check if we can find GTM ID via simple header sniffing ---
        # Sometimes CF allows HEAD requests
        try:
            head_resp = cffi_requests.head(url, impersonate="chrome120", timeout=5)
            # Not much info in headers, but confirms accessibility
        except: pass
        
        logger.warning("[FULL_EXTRACT] No Pixel ID found via Brute Force.")
        return result