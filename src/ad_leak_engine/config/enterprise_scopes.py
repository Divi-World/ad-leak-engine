
# ============================================================
# [SEED: 2399] ENTERPRISE META GRAPH API SCOPES & TENANT ISOLATION
# Required for $80k-$200k SaaS Valuation (Real Financial Data Ingestion)
# ============================================================

META_GRAPH_API_SCOPES = [
    "ads_read",            # Pull campaign structure, active ads, creatives, and CTR/CPM
    "ads_management",      # Read pixel events, CAPI status, custom audiences (Retargeting verification)
    "business_management", # Access Business Manager, verify Pixel ownership and catalog mapping
    "pages_read_engagement", # Analyze social proof and page-level engagement metrics
    "pages_show_list"      # Map ad accounts to their respective Facebook Pages
]

TENANT_RBAC_SCOPES = {
    "workspace:read": "View workspace settings and team members",
    "workspace:write": "Modify workspace settings and invite users",
    "scan:trigger": "Initiate ad infrastructure teardowns",
    "scan:read": "View historical teardown reports and financial leak data",
    "billing:manage": "Manage subscriptions, invoices, and API credits (Phase 43)",
    "oauth:manage": "Connect/Disconnect Meta Business Manager and Ad Accounts"
}

# Financial Validation Thresholds (Used to replace 'estimated' spend with 'hard' proof)
ROAS_VALIDATION_THRESHOLD = 2.5 # Target ROAS
CPA_DEVIATION_ALERT = 0.20      # Alert if CPA deviates >20% from niche average
