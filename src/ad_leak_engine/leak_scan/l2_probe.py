"""REAL Playwright probe using camoufox (stealth) [SEED: 2399]."""
from ad_leak_engine.self_heal.human_browser import HumanBrowser

class L2LiveProbe:
    def probe(self, url: str, timeout_ms: int = 25000) -> dict:
        network_log = {
            "pixel_fired": False, "requests": [], "capi_events": [],
            "has_unhashed_pii": False, "is_checkout_page": False,
        }
        hb = HumanBrowser(headless=True)
        try:
            with hb.session() as page:
                captured = []
                def on_request(request): captured.append(request.url)
                page.on("request", on_request)
                
                page.goto(url, wait_until="load", timeout=timeout_ms)
                hb.human_pause(2.0, 4.0)
                hb.human_scroll(page, distance=500, steps=5)
                hb.human_pause(1.0, 2.0)

                content = ""
                try: content = page.content().lower()
                except Exception: pass

                pixel_requests = [u for u in captured if "facebook.com/tr" in u.lower()]
                has_fbq = "fbevents.js" in content or "fbq(" in content
                network_log["pixel_fired"] = len(pixel_requests) > 0 or has_fbq
                network_log["requests"] = [u for u in captured if "facebook" in u.lower()]

                capi_requests = [u for u in captured if "graph.facebook.com" in u.lower() and "/events" in u.lower()]
                for cr in capi_requests:
                    network_log["capi_events"].append({"event_name": "server_event", "url": cr})

                url_lower = url.lower()
                network_log["is_checkout_page"] = any(
                    k in url_lower for k in ["checkout", "thank", "order", "confirm", "cart"]
                )
        except Exception as e:
            network_log["error"] = str(e)
        return network_log
