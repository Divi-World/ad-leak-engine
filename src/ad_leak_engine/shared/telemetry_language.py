WAF_MARKERS = (
    "challenges.cloudflare.com",
    "just a moment...",
    "cdn-cgi/challenge-platform",
    "datadome",
    "imperva",
    "akamai",
    "cf-browser-verification",
)


def waf_markers_in_text(text: str) -> list[str]:
    low = (text or "").lower()
    return [m for m in WAF_MARKERS if m in low]


def telemetry_reason(
    waf_blocked: bool = False,
    request_count: int = 0,
    fetch_blocked: bool = False,
    pixel_fired: bool = False,
) -> dict:
    if waf_blocked:
        return {
            "code": "waf_blocked",
            "causes": ["bot protection", "WAF challenge", "managed security gate"],
        }

    if fetch_blocked:
        return {
            "code": "fetch_blocked",
            "causes": ["fetch blocked", "probe denied", "network/edge block"],
        }

    if request_count == 0:
        return {
            "code": "no_telemetry_captured",
            "causes": ["timeout", "blank response", "blocked subresources", "browser probe failure"],
        }

    if request_count < 5 and not pixel_fired:
        return {
            "code": "insufficient_telemetry",
            "causes": ["timeout", "SPA delay", "consent gating", "deferred tracking", "partial bot protection"],
        }

    return {
        "code": "partial_telemetry",
        "causes": ["timeout", "SPA delay", "consent gating", "deferred tracking"],
    }


def precise_telemetry_recommendation(reason: dict) -> str:
    code = (reason or {}).get("code", "insufficient_telemetry")
    causes = (reason or {}).get("causes", [])
    cause_text = ", ".join(causes) if causes else "timeout, SPA delay, consent gating, or bot protection"

    if code == "waf_blocked":
        return "Automated telemetry was blocked by bot protection/WAF. Server-side CAPI recommended."

    if code == "fetch_blocked":
        return "Automated telemetry fetch was blocked before reliable event data could be captured. Server-side CAPI recommended."

    if code == "no_telemetry_captured":
        return "No usable network telemetry was captured. This may be caused by timeout, blank response, blocked subresources, or probe failure. Server-side CAPI recommended."

    if code == "insufficient_telemetry":
        return f"Automated telemetry was insufficient. Possible causes: {cause_text}. Server-side CAPI recommended."

    return f"Automated telemetry was partial. Possible causes: {cause_text}. Server-side CAPI recommended."
