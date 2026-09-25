#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — Local Scan Execution
# Executes a full local scan pipeline for a given keyword.
# ============================================================
set -e

KEYWORD="shoes"
COUNTRY="US"
LIMIT="5"

echo "[SEED:2399] Initiating local scan for '' in ..."

# Activate venv
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Execute scan via CLI
./scripts/ale scan "" "" --limit ""

echo ""
echo "=========================================================="
echo "  [SEED: 2399] LOCAL SCAN COMPLETE"
echo "  Results saved to output/ directory."
echo "=========================================================="
