#!/bin/bash
# Export high-score leads from SQLite [SEED: 2399]
echo "[SEED:2399] Exporting leads with score >= 60..."
sqlite3 -header -csv data/db/adleak.db "SELECT id, name, fingerprint FROM pages WHERE id IN (SELECT page_id FROM leaks GROUP BY page_id HAVING COUNT(*) > 2);" > output/high_score_leads.csv
echo "[SEED:2399] Exported to output/high_score_leads.csv"
