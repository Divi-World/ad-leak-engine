#!/bin/bash
# Master Swarm Orchestrator [SEED: 2399]
KEYWORD="${1:-shoes}"
COUNTRY="${2:-US}"

echo "[SEED:2399] Dispatching Swarm for '$KEYWORD'..."
if ! command -v gh &>/dev/null; then
    echo "[SEED:2399] FATAL: GitHub CLI (gh) required. Install: https://cli.github.com/"
    exit 1
fi

gh workflow run swarm_matrix.yml -f keyword="$KEYWORD" -f country="$COUNTRY"
echo "[SEED:2399] Swarm dispatched. Monitor at: https://github.com/YOUR_REPO/actions"
echo "[SEED:2399] Once complete, run: python scripts/aggregate_swarm.py --download"
