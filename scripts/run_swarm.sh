#!/bin/bash
# Master Swarm Orchestrator [SEED: 2399]
KEYWORD="${1:-shoes}"
COUNTRY="${2:-US}"

echo "[SEED:2399] Dispatching Swarm for '$KEYWORD'..."
if ! command -v gh &>/dev/null; then
    echo "[SEED:2399] FATAL: GitHub CLI (gh) required."
    exit 1
fi

# CRITICAL FIX: Added --ref main to bypass GitHub API caching of old workflow IDs
gh workflow run swarm_matrix.yml --ref main -f keyword="$KEYWORD" -f country="$COUNTRY"
echo "[SEED:2399] Swarm dispatched. Monitor at: https://github.com/Divi-World/ad-leak-engine/actions"
