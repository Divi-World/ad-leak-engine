import re
from typing import Iterable

TIER1_EXACT = {
    "founder", "co-founder", "cofounder", "owner", "president",
    "managing-director", "managing_director", "partner",
    "ceo", "cto", "cfo", "coo", "cmo",
    "vp-sales", "vp-marketing", "vp-engineering",
    "head-of-growth", "head-of-product", "head-of-sales",
    "director-of-marketing", "sales-director", "marketing-director",
    "digital-director", "ecommerce-director", "it-director",
    "product-manager", "brand-manager", "marketing-manager",
    "growth-manager", "sales-manager", "operations-manager",
}

TIER1_TOKENS = {
    "founder", "cofounder", "owner", "president", "partner",
    "ceo", "cto", "cfo", "coo", "cmo", "cio",
    "vp", "head", "director", "chief", "officer",
    "manager", "lead", "growth", "ecommerce", "digital",
    "marketing", "sales", "product", "operations",
}

TIER2_EXACT = {
    "marketing", "growth", "demandgen", "demand-gen", "content", "brand",
    "social", "pr", "communications", "comms",
    "digital", "ecommerce", "e-commerce", "online", "web", "website",
    "sales", "business", "partnerships", "bizdev", "alliances",
    "crm", "retention", "loyalty", "data", "analytics",
    "product", "operations", "ops", "projects",
}

TIER2_TOKENS = {
    "marketing", "growth", "demandgen", "demand", "content", "brand",
    "social", "pr", "communications", "comms",
    "digital", "ecommerce", "online", "web", "website",
    "sales", "business", "partnerships", "bizdev", "alliances",
    "crm", "retention", "loyalty", "data", "analytics",
    "product", "operations", "ops", "projects",
}

TIER3_EXACT = {
    "hello", "hi", "contact", "contactus", "contact-us", "info", "general",
    "enquiries", "inquiries", "support", "help", "helpdesk", "service",
    "customercare", "customer-care", "customer.care", "customerservice",
    "customer-service", "care", "assist", "reception", "frontdesk",
    "front-desk", "office", "billing", "accounts", "finance", "payments",
    "invoices",
}

TIER3_TOKENS = {
    "hello", "hi", "contact", "contactus", "info", "general",
    "enquiries", "inquiries", "support", "help", "helpdesk", "service",
    "customercare", "customerservice", "care", "assist", "reception",
    "frontdesk", "office", "billing", "accounts", "finance", "payments",
    "invoices",
}

TIER4_EXACT = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "legal", "compliance", "privacy", "gdpr", "dpo", "terms",
    "security", "abuse", "spam", "phishing", "cert", "root",
    "unsubscribe", "optout", "opt-out", "remove", "list", "listserv",
    "admin", "webmaster", "hostmaster", "it", "devnull", "null",
}

TIER4_TOKENS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "mailer-daemon",
    "postmaster", "legal", "compliance", "privacy", "gdpr", "dpo", "terms",
    "security", "abuse", "spam", "phishing", "cert", "root",
    "unsubscribe", "optout", "opt-out", "remove", "list", "listserv",
    "admin", "webmaster", "hostmaster", "it", "devnull", "null",
}

NON_PERSON_TOKENS = (
    TIER2_TOKENS
    | TIER3_TOKENS
    | TIER4_TOKENS
    | {
        "customer", "customers", "service", "support", "info", "contact",
        "general", "office", "help", "care", "billing", "accounts",
        "finance", "payments", "invoices", "reception", "frontdesk",
    }
)

POISON_DOMAINS = (
    "example.com", "example.org", "example.net", "test.com", "localhost",
    "sentry.io", "bugsnag", "newrelic", "datadome", "shopify.com",
    "wix.com", "wordpress.com", "squarespace.com", "stripe.com",
    "paypal.com", "facebook.com", "instagram.com",
)

ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".js", ".css")


def classify_email(email: str) -> dict:
    e = (email or "").strip().lower()

    if not e:
        return {"email": email, "tier": "empty", "score": 0, "reason": "No email.", "recommended_use": "none"}

    if e.startswith("FORM:"):
        return {"email": email, "tier": "form_placeholder", "score": 0, "reason": "FORM placeholder, not reachable email.", "recommended_use": "reject"}

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e):
        return {"email": email, "tier": "malformed", "score": 0, "reason": "Malformed email.", "recommended_use": "reject"}

    local, domain = e.split("@", 1)
    local = local.split("+")[0].strip().replace("_", "-")
    tokens = set(re.split(r"[^a-z0-9]+", local))
    tokens.discard("")

    if any(p in domain for p in POISON_DOMAINS):
        return {"email": email, "tier": "suspicious_domain", "score": 5, "reason": "Vendor/test/platform domain.", "recommended_use": "reject"}

    if local.endswith(ASSET_SUFFIXES):
        return {"email": email, "tier": "asset_false_positive", "score": 0, "reason": "Asset filename captured as email.", "recommended_use": "reject"}

    if local in TIER4_EXACT or tokens & TIER4_TOKENS:
        return {
            "email": email,
            "tier": "tier4_low_value",
            "score": 10,
            "reason": "Low-value compliance/security/unsubscribe/admin mailbox.",
            "recommended_use": "avoid_primary",
        }

    if local in TIER1_EXACT or tokens & TIER1_TOKENS:
        return {
            "email": email,
            "tier": "tier1_decision_maker",
            "score": 95,
            "reason": "Explicit decision-maker/senior role mailbox.",
            "recommended_use": "primary",
        }

    if "." in local and local not in TIER3_EXACT and not (tokens & NON_PERSON_TOKENS):
        if re.match(r"^[a-z]{1,20}\.[a-z]{1,20}$", local):
            return {
                "email": email,
                "tier": "tier1_possible_named_person",
                "score": 84,
                "reason": "first.last style mailbox.",
                "recommended_use": "primary_candidate",
            }
        if re.match(r"^[a-z]{1,2}\.[a-z]{1,20}$", local):
            return {
                "email": email,
                "tier": "tier1_possible_named_person",
                "score": 80,
                "reason": "f.last style mailbox.",
                "recommended_use": "primary_candidate",
            }

    if local in TIER2_EXACT or tokens & TIER2_TOKENS:
        return {
            "email": email,
            "tier": "tier2_department",
            "score": 80,
            "reason": "Marketing/digital/growth/sales/product department mailbox.",
            "recommended_use": "primary_or_secondary",
        }

    if local in TIER3_EXACT or tokens & TIER3_TOKENS:
        return {
            "email": email,
            "tier": "tier3_general",
            "score": 55,
            "reason": "General support/info/contact/finance mailbox.",
            "recommended_use": "fallback",
        }

    return {
        "email": email,
        "tier": "tier3_unknown_general",
        "score": 50,
        "reason": "Unclassified mailbox; treat as fallback.",
        "recommended_use": "fallback",
    }


def select_best_email(emails: Iterable[str] | None) -> dict:
    candidates = []
    for e in emails or []:
        candidates.append(classify_email(e))

    if not candidates:
        return {
            "email": None,
            "tier": "none",
            "score": 0,
            "reason": "No email candidate captured.",
            "recommended_use": "none",
            "candidates": [],
        }

    best = max(candidates, key=lambda x: x.get("score", 0))
    best = dict(best)
    best["candidates"] = candidates
    return best
