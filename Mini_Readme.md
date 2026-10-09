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

Install the New Dependencies:
   pip install -e ".[scrape]"

Ensure Redis is Running:
If you don't have Redis installed locally, the easiest way on Windows is via Docker:
   docker run -d -p 6379:6379 redis:alpine

Start the Celery Worker (in a NEW terminal):
   celery -A src.ad_leak_engine.orchestrator.celery_app worker --loglevel=info --pool=solo

Start Uvicorn (in your main backend terminal):
    uvicorn src.ad_leak_engine.orchestrator.app:app --reload --port 8000