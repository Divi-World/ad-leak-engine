#!/bin/bash
# Dispatch the Distributed Ephemeral Swarm [SEED: 2399]
KEYWORD="${1:-shoes}"
COUNTRY="${2:-US}"
RUNS="${3:-1}"

if ! command -v gh &>/dev/null; then
    echo "[SEED:2399] GitHub CLI (gh) not found. Install: https://cli.github.com/"
    echo "[SEED:2399] Or trigger 'Swarm Matrix Scan' manually in the GitHub Actions UI."
    exit 1
fi

echo "[SEED:2399] Dispatching swarm for keyword='$KEYWORD' country=$COUNTRY runs=$RUNS"
for i in $(seq 1 "$RUNS"); do
    gh workflow run swarm_matrix.yml -f keyword="$KEYWORD" -f country="$COUNTRY"
    echo "[SEED:2399] Dispatched swarm run $i."
    sleep 2
done
echo "[SEED:2399] All dispatches sent. Check GitHub Actions for progress."
