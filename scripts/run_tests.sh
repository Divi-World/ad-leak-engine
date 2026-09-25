#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — Test Suite Execution
# Runs the complete test suite with coverage reporting.
# ============================================================
set -e

echo "[SEED:2399] Running complete test suite..."

# Activate venv
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run tests with coverage
python -m pytest tests/ -v --tb=short --cov=src/ad_leak_engine --cov-report=term-missing

echo ""
echo "=========================================================="
echo "  [SEED: 2399] TEST SUITE EXECUTION COMPLETE"
echo "=========================================================="
