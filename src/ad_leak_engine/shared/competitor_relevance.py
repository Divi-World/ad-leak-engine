GENERIC_LOW_VALUE_COMPETITOR_TERMS = (
    "community",
    "insider",
    "relief",
    "support community",
    "senior health",
    "cholesterol",
    "wellness community",
    "daily health",
    "health tips",
    "remedy",
    "cure",
)

NON_ECOMMERCE_GENERIC_RISK_INTENTS = {
    "hospital_clinic",
    "nonprofit_donation",
    "school",
    "finance",
}


def filter_competitors(
    prospect_intent: dict | str | None,
    prospect_name: str,
    prospect_domain: str,
    competitors: list[dict],
    country: str | None = None,
) -> tuple[list[dict], list[dict], list[str]]:
    if isinstance(prospect_intent, dict):
        intent = prospect_intent.get("primary") or "unknown"
    else:
        intent = prospect_intent or "unknown"

    kept = []
    filtered = []
    reasons = []

    prospect_blob = f"{prospect_name} {prospect_domain}".lower()
    geo_mismatch_warning = False

    if (country or "").upper() == "CA" and (
        ".in" in prospect_domain
        or "bangalore" in prospect_blob
        or "india" in prospect_blob
    ):
        geo_mismatch_warning = True
        reasons.append("Country filter is CA but prospect appears India-based; observed-pool competitor geo relevance is weak.")

    for c in competitors or []:
        name = ""
        if isinstance(c, dict):
            name = str(c.get("page_name") or "")
        else:
            name = str(c)

        low = name.lower()

        if intent in NON_ECOMMERCE_GENERIC_RISK_INTENTS and any(term in low for term in GENERIC_LOW_VALUE_COMPETITOR_TERMS):
            filtered.append(c)
            reasons.append(f"Filtered generic/low-value competitor for intent={intent}: {name}")
            continue

        kept.append(c)

    if not kept and competitors:
        reasons.append("No relevant competitors remained after relevance filtering.")

    return kept, filtered, reasons
