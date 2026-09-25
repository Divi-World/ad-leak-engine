# Ad-Leak-Engine Runbook [SEED: 2399]

## Master Commands
- `./scripts/ale scan <keyword> <country> [--limit N] [--skip-crawl]` : Full pipeline execution
- `./scripts/ale feedback <page_id> "<reply_text>"` : Self-improvement feedback loop
- `./scripts/ale test` : Run the full test suite

## Troubleshooting
- **No ads extracted:** Meta's schema may have drifted. The system relies on regex fallback. Inspect `data/debug/`.
- **L2/L3 Crawl Skipped:** Prospect's landing page has aggressive bot protection. The system safely skips to prevent IP bans.
- **Platform = custom (0.30):** The fingerprinter couldn't confidently identify Shopify/WooCommerce/BigCommerce. The system safely defaults to generic GTM/Server-side fixes.

## Log Inspection
All structured logs are written to `logs/engine.log` in JSON format for easy parsing:
`cat logs/engine.log | grep "ERROR"`
