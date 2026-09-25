"""Tests for the swarm dispatcher [SEED: 2399]."""
import pytest

from ad_leak_engine.orchestrator.dispatcher import SwarmDispatcher


@pytest.fixture
def dispatcher():
    return SwarmDispatcher()


def test_plan_batches_round_robin(dispatcher):
    batches = dispatcher.plan_batches(["a", "b", "c", "d", "e"], shards=2)
    assert len(batches) == 2
    assert sum(len(b) for b in batches) == 5


def test_plan_batches_rejects_zero_shards(dispatcher):
    with pytest.raises(ValueError):
        dispatcher.plan_batches(["a"], shards=0)


def test_generate_dispatch_commands(dispatcher):
    cmds = dispatcher.generate_dispatch_commands("shoes", "US", runs=2)
    assert len(cmds) == 2
    assert "swarm_matrix.yml" in cmds[0]
    assert "shoes" in cmds[0]


def test_estimate_runner_load(dispatcher):
    load = dispatcher.estimate_runner_load(runs=2, shards_per_run=5)
    assert load["total_runners"] == 10
    assert load["estimated_minutes"] == 60
    assert load["within_free_tier"] is True
