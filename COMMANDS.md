# Ad-Leak-Engine [SEED: 2399] — Operational Commands

This document contains all standard operating procedures for prospecting, scanning, and managing the Ad-Leak-Engine.

---

## 1. PROSPECTING & SCANNING

### Local Live Scan (Stealth Browser)
Scrapes live Meta Ad Library data, audits landing pages, fingerprints the platform, and generates outreach packs locally.


bash
Syntax: ./scripts/ale scan "<keyword>" "<COUNTRY_CODE>" --limit <N>
./scripts/ale scan "supplements" "US" --limit 5
./scripts/ale scan "B2B SaaS" "UK" --limit 3
./scripts/ale scan "organic skincare" "CA" --limit 10

*Note: Country codes must be valid ISO 3166-1 alpha-2 codes (e.g., US, UK, CA, AU, DE).*

### Cloud Swarm Scan (Unlimited Scale)
Dispatches 10 ephemeral GitHub Action runners to scrape a keyword in parallel, bypassing all rate limits.
```bash
# 1. Dispatch the swarm
export MSYS_NO_PATHCONV=1
gh api --method POST -H "Accept: application/vnd.github+json" /repos/Divi-World/ad-leak-engine/actions/workflows/swarm_matrix.yml/dispatches -f ref='main' -f 'inputs[keyword]'='fashion' -f 'inputs[country]'='US'

# 2. Wait 2-3 minutes, then aggregate the results locally
python scripts/aggregate_swarm.py --download

# 3. Process the aggregated data through the L2/L3 pipeline
./scripts/ale scan "fashion" "US" --limit 20


SYSTEM MANAGEMENT & VERIFICATION
Run Full Test Suite
Verifies all 113+ tests pass with zero regressions.
./scripts/ale test


Process Prospect Feedback (Self-Improvement Loop)
Logs a prospect's reply to dynamically adjust leak detection weights for future scans.
# Syntax: ./scripts/ale feedback <meta_page_id> "<reply_text>" --positive
./scripts/ale feedback 35888984712 "Thanks, our pixel was indeed broken. Fixing it now." --positive


Export High-Score Leads
Exports prospects with a leak severity score above the threshold to a CSV file.
# Syntax: ./scripts/export_leads.sh <min_score>
./scripts/export_leads.sh 60

OUTPUT & DELIVERABLES
After a successful scan, navigate to the output/ directory. Each prospect has a dedicated folder named after their Meta Page ID (e.g., output/35888984712/).
Inside each folder, you will find:
teardown.md: The complete, professional audit report. Includes ranked leaks, hard evidence (Ad IDs, network logs), and exact copy-paste code fixes tailored to their platform (Shopify, WooCommerce, etc.).
message.txt: The ready-to-send, CAN-SPAM compliant outreach email with a personalized hook and specific leak observations.


SEARCH STRATEGY & LIMITATIONS
Best Practices for Keywords
High Intent: Use specific, high-value niches (e.g., "vegan protein powder", "luxury real estate", "CRM software").
Avoid Broad Terms: Generic terms like "shoes" or "clothing" return massive, noisy datasets that require heavy filtering.
Combine with Geography: Always pair with a high-value country code (US, UK, CA, AU) to ensure prospects have the budget to act on the fixes.