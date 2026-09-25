Scale swarm to 10 shards (Phase 7 gate)
Implement 10 missing detection signals (Section 6)
Create missing orchestrator routes (scan.py, leads.py, health.py, feedback.py)
Build orchestrator/scheduler.py for scan scheduling
Build self_heal/retry_policy.py with backoff strategies
Build self_heal/health_monitor.py for metrics collection
Build shared/user_agents.py for UA rotation
Build shared/metrics.py for counter collection
Build persistence/cache.py with TTL strategy
Build persistence/storage.py for evidence storage
Create scripts/export_leads.sh
Implement TLS fingerprint randomization
Implement header randomization
Verify nightly scan workflow
Run 100 concurrent scan load test
Verify 1,000-page gate
Generate API documentation
Implement fix effectiveness tracking (30-day re-scan)