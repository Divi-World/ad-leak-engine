"""Swarm IP coordination for Distributed Ephemeral Swarm [SEED: 2399].

In the GitHub Actions swarm model, each runner IS a unique IP.
This manager coordinates shard assignment, tracks runner health,
and enforces pacing to prevent collective rate limiting.
"""
import time
import random
from dataclasses import dataclass, field
from enum import Enum


class RunnerStatus(Enum):
    IDLE = "idle"
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    FAILED = "failed"


@dataclass
class RunnerState:
    runner_id: str
    status: RunnerStatus = RunnerStatus.IDLE
    requests_made: int = 0
    failures: int = 0
    last_active: float = 0.0
    cooldown_until: float = 0.0


class SwarmProxyManager:
    """Coordinates ephemeral runners in the GitHub Actions swarm."""

    def __init__(self, max_shards: int = 10, cooldown_seconds: int = 600):
        self.max_shards = max_shards
        self.cooldown_seconds = cooldown_seconds
        self.runners: dict[str, RunnerState] = {}
        self._request_log: list[float] = []

    def register_runner(self, runner_id: str) -> RunnerState:
        if runner_id not in self.runners:
            self.runners[runner_id] = RunnerState(runner_id=runner_id)
        return self.runners[runner_id]

    def get_available_runner(self) -> RunnerState | None:
        now = time.time()
        for runner in self.runners.values():
            if runner.status == RunnerStatus.COOLDOWN:
                if now >= runner.cooldown_until:
                    runner.status = RunnerStatus.IDLE
                    runner.failures = 0
                else:
                    continue
            if runner.status == RunnerStatus.IDLE:
                return runner
        return None

    def assign_task(self, runner_id: str) -> bool:
        runner = self.runners.get(runner_id)
        if not runner or runner.status != RunnerStatus.IDLE:
            return False
        runner.status = RunnerStatus.ACTIVE
        runner.last_active = time.time()
        runner.requests_made += 1
        self._request_log.append(time.time())
        return True

    def report_success(self, runner_id: str):
        runner = self.runners.get(runner_id)
        if runner:
            runner.status = RunnerStatus.IDLE
            runner.failures = 0

    def report_failure(self, runner_id: str):
        runner = self.runners.get(runner_id)
        if runner:
            runner.failures += 1
            if runner.failures >= 3:
                runner.status = RunnerStatus.COOLDOWN
                runner.cooldown_until = time.time() + self.cooldown_seconds
            else:
                runner.status = RunnerStatus.IDLE

    def get_request_rate(self, window_seconds: int = 60) -> float:
        """Requests per second in the given window."""
        now = time.time()
        cutoff = now - window_seconds
        recent = [t for t in self._request_log if t >= cutoff]
        return len(recent) / window_seconds if window_seconds > 0 else 0.0

    def should_throttle(self, max_rps: float = 0.5) -> bool:
        """Returns True if collective request rate exceeds threshold."""
        return self.get_request_rate() > max_rps

    def get_pacing_delay(self) -> float:
        """Randomized delay to prevent collective rate limiting."""
        return random.uniform(15.0, 45.0)

    def health_summary(self) -> dict:
        statuses = {}
        for runner in self.runners.values():
            s = runner.status.value
            statuses[s] = statuses.get(s, 0) + 1
        return {
            "total_runners": len(self.runners),
            "max_shards": self.max_shards,
            "statuses": statuses,
            "request_rate_rps": round(self.get_request_rate(), 3),
        }
