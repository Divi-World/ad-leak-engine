Daily Prospecting (Local):
./scripts/ale scan "your_niche" "US" --limit 10


(This pulls from your local DB, crawls live sites, and generates the teardown packs in the output/ folder).
Unlimited Scale (Cloud Swarm):
# Fire 5 ephemeral runners to scrape a new keyword
export MSYS_NO_PATHCONV=1
gh api --method POST -H "Accept: application/vnd.github+json" /repos/Divi-World/ad-leak-engine/actions/workflows/swarm_matrix.yml/dispatches -f ref='main' -f 'inputs[keyword]'='supplements' -f 'inputs[country]'='US'

# Wait 3 minutes, then pull the data
python scripts/aggregate_swarm.py --download


AI Training (Feedback Loop):
When a prospect replies to your outreach, feed it back to the engine to make it smarter:
./scripts/ale feedback <page_id> "Thanks, our CAPI was indeed dropping events."


System Health:
./scripts/ale test