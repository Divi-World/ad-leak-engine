from typing import Any

INTENT_TERMS = {
    "ecommerce_store": [
        ("shop", 4), ("store", 4), ("cart", 5), ("checkout", 5), ("product", 4),
        ("buy", 4), ("price", 3), ("shipping", 4), ("variant", 5),
        ("hoodie", 4), ("apparel", 4), ("boutique", 4), ("skincare", 4),
        ("cosmetic", 4), ("supplement", 4), ("retail", 4), ("d2c", 4),
        ("direct to consumer", 4), ("online store", 5), ("ecommerce", 5),
        ("/products/", 5), ("/cart", 5), ("/checkout", 5),
    ],
    "hospital_clinic": [
        ("hospital", 5), ("clinic", 5), ("medical center", 5), ("medical centre", 5),
        ("healthcare", 4), ("health care", 4), ("patient", 4), ("doctor", 4),
        ("physician", 4), ("surgery", 4), ("rehabilitation", 4),
        ("emergency care", 5), ("sparsh", 5), ("camh", 5), ("advocate health", 5),
        ("health system", 4), ("mental health", 3), ("wellness clinic", 4),
    ],
    "nonprofit_donation": [
        ("foundation", 5), ("charity", 5), ("nonprofit", 5), ("non-profit", 5),
        ("not-for-profit", 5), ("donate", 5), ("donation", 5), ("volunteer", 4),
        ("fundraising", 4), ("give to", 4), ("advocacy", 3),
    ],
    "school": [
        ("school", 5), ("university", 5), ("college", 5), ("academy", 4),
        ("institute", 3), ("admissions", 5), ("campus", 4), ("student", 3),
        ("enrollment", 4), ("course", 2),
    ],
    "finance": [
        ("bank", 5), ("credit union", 5), ("investment", 5), ("insurance", 4),
        ("loan", 4), ("mortgage", 5), ("wealth", 4), ("trading", 4),
        ("financial services", 5), ("fintech", 4),
    ],
    "saas_demo": [
        ("saas", 5), ("software", 4), ("platform", 3), ("demo", 4),
        ("free trial", 5), ("sign up", 4), ("signup", 4), ("api", 3),
        ("dashboard", 4), ("b2b", 3), ("pricing plans", 4),
    ],
    "lead_generation": [
        ("contact us", 4), ("request appointment", 5), ("book now", 4),
        ("schedule", 4), ("call us", 4), ("lead form", 5), ("get started", 3),
        ("talk to", 3), ("consultation", 4), ("inquire", 4), ("enquire", 4),
        ("request quote", 5), ("book consultation", 5),
    ],
    "local_service": [
        ("near me", 4), ("locations", 3), ("booking", 3), ("service area", 4),
        ("hours", 2), ("directions", 3), ("phone", 2), ("salon", 3),
        ("spa", 3), ("restaurant", 3),
    ],
    "brand_awareness": [
        ("brand", 2), ("awareness", 2), ("story", 1), ("mission", 1),
    ],
}

NON_ECOMMERCE_INTENTS = {
    "hospital_clinic",
    "nonprofit_donation",
    "school",
    "finance",
    "lead_generation",
    "local_service",
    "saas_demo",
    "brand_awareness",
}

ECOMMERCE_STRONG_TERMS = (
    "add to cart", "addtocart", "cart", "checkout", "buy now",
    "product", "variant", "shipping", "purchase", "order summary",
    "/products/", "/cart", "/checkout", "shopify", "woocommerce", "bigcommerce",
)

EXPECTED_EVENTS = {
    "ecommerce_store": ["ViewContent", "AddToCart", "InitiateCheckout", "Purchase"],
    "hospital_clinic": ["Lead", "Contact", "Schedule", "Call", "PatientPortalClick"],
    "nonprofit_donation": ["Donate", "Lead", "Contact", "Volunteer"],
    "saas_demo": ["DemoRequest", "Signup", "Lead", "PricingView"],
    "school": ["Inquiry", "Apply", "Visit", "Contact"],
    "finance": ["Lead", "Application", "Quote", "Contact"],
    "lead_generation": ["Lead", "Contact", "Schedule", "Call"],
    "local_service": ["Lead", "Contact", "Call", "DirectionClick"],
    "brand_awareness": [],
    "unknown": [],
}


def classify_intent_from_text(text: str) -> dict:
    blob = (text or "").lower()
    scores = {}
    evidence = {}

    for intent, terms in INTENT_TERMS.items():
        score = 0
        hits = []
        for term, weight in terms:
            if term in blob:
                score += weight
                hits.append(term)
        if score:
            scores[intent] = score
            evidence[intent] = list(dict.fromkeys(hits))[:20]

    if not scores:
        return {
            "primary": "unknown",
            "secondary": [],
            "scores": {},
            "evidence": {},
        }

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "primary": ordered[0][0],
        "secondary": [i for i, s in ordered[1:] if s > 0][:4],
        "scores": dict(ordered),
        "evidence": evidence,
    }


def _page_text(page: Any, limit_html: int = 20000) -> str:
    parts = []

    for attr in ("name", "url"):
        value = getattr(page, attr, None)
        if value:
            parts.append(str(value))

    ads = getattr(page, "ads", []) or []
    for ad in ads[:50]:
        for attr in ("page_name", "landing_url", "title", "body", "cta"):
            value = getattr(ad, attr, None)
            if value:
                parts.append(str(value))

    raw = getattr(page, "raw", None)
    if isinstance(raw, dict):
        html = raw.get("html") or ""
        if html:
            parts.append(str(html)[:limit_html])

        network_log = raw.get("network_log") or {}
        if isinstance(network_log, dict):
            requests = network_log.get("requests") or []
            if isinstance(requests, list):
                for r in requests[:50]:
                    if isinstance(r, dict):
                        parts.append(str(r.get("url", "")))
                    else:
                        parts.append(str(r))

    return " ".join(parts)


def classify_intent_from_page(page: Any) -> dict:
    return classify_intent_from_text(_page_text(page))


def has_strong_ecommerce_evidence(page: Any, intent_result: dict | None = None) -> tuple[bool, list[str]]:
    blob = _page_text(page, limit_html=50000).lower()
    hits = [term for term in ECOMMERCE_STRONG_TERMS if term in blob]

    if intent_result and intent_result.get("primary") == "ecommerce_store" and hits:
        return True, hits

    return bool(hits), hits


def expected_events_for_intent(intent: str | None) -> list[str]:
    return list(EXPECTED_EVENTS.get(intent or "unknown", []))
