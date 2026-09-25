#!/bin/bash
# ============================================================
# Ad-Leak-Engine [SEED: 2399] — Environment Bootstrap
# Creates venv, installs dependencies, initializes database.
# ============================================================
set -e

echo "[SEED:2399] Bootstrapping Ad-Leak-Engine environment..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[SETUP] Creating virtual environment..."
    python -m venv .venv
fi

# Activate venv
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Install dependencies
echo "[SETUP] Installing dependencies..."
pip install -e ".[test]" 2>/dev/null || pip install -e .

# Create required directories
echo "[SETUP] Creating required directories..."
mkdir -p data/db data/cache logs output

# Initialize database
echo "[SETUP] Initializing SQLite database..."
python -c "
import sys
sys.path.insert(0, 'src')
from ad_leak_engine.persistence.db import init_db
init_db()
print('[SETUP] Database initialized successfully.')
"

echo ""
echo "=========================================================="
echo "  [SEED: 2399] ENVIRONMENT BOOTSTRAP COMPLETE"
echo "  Run './scripts/ale test' to verify the system."
echo "=========================================================="
