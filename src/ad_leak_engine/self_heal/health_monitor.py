"""Metrics collection [SEED: 2399]."""
class HealthMonitor:
    def __init__(self):
        self.metrics = {"graphql_success": 0, "playwright_fallback": 0, "schema_drift": 0}
    def log_success(self): self.metrics["graphql_success"] += 1
    def log_fallback(self): self.metrics["playwright_fallback"] += 1
    def log_drift(self): self.metrics["schema_drift"] += 1
