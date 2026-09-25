"""Integration tests for Distributed Ephemeral Swarm [SEED: 2399]."""
import pytest
import time

from ad_leak_engine.self_heal.proxy_manager import (
    SwarmProxyManager, RunnerStatus
)
from ad_leak_engine.orchestrator.dispatcher import SwarmDispatcher


class TestSwarmProxyManager:
    def test_register_and_assign(self):
        pm = SwarmProxyManager(max_shards=5)
        pm.register_runner("runner-1")
        assert pm.assign_task("runner-1") is True

    def test_runner_cooldown_after_failures(self):
        pm = SwarmProxyManager(max_shards=5, cooldown_seconds=10)
        pm.register_runner("runner-1")
        pm.assign_task("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        runner = pm.runners["runner-1"]
        assert runner.status == RunnerStatus.COOLDOWN

    def test_get_available_runner_skips_cooldown(self):
        pm = SwarmProxyManager(max_shards=5, cooldown_seconds=9999)
        pm.register_runner("runner-1")
        pm.assign_task("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        pm.report_failure("runner-1")
        # runner-1 is now in cooldown
        pm.register_runner("runner-2")
        available = pm.get_available_runner()
        assert available is not None
        assert available.runner_id == "runner-2"

    def test_health_summary(self):
        pm = SwarmProxyManager(max_shards=5)
        pm.register_runner("runner-1")
        pm.register_runner("runner-2")
        summary = pm.health_summary()
        assert summary["total_runners"] == 2
        assert summary["max_shards"] == 5

    def test_pacing_delay_in_range(self):
        pm = SwarmProxyManager()
        delay = pm.get_pacing_delay()
        assert 15.0 <= delay <= 45.0


class TestSwarmDispatcher:
    def test_plan_batches_distribution(self):
        d = SwarmDispatcher()
        batches = d.plan_batches(["a", "b", "c", "d", "e", "f"], shards=3)
        assert len(batches) == 3
        assert sum(len(b) for b in batches) == 6

    def test_dispatch_commands_format(self):
        d = SwarmDispatcher()
        cmds = d.generate_dispatch_commands("shoes", "US", runs=2)
        assert len(cmds) == 2
        assert "swarm_matrix.yml" in cmds[0]
        assert "shoes" in cmds[0]

    def test_runner_load_estimation(self):
        d = SwarmDispatcher()
        load = d.estimate_runner_load(runs=3, shards_per_run=5)
        assert load["total_runners"] == 15
        assert load["within_free_tier"] is True
