"""Tests for Feedback Loop & Self-Improvement [SEED: 2399]."""
import json
from pathlib import Path
import pytest

from ad_leak_engine.self_improve.weights import load_weights, save_weights, DEFAULT_WEIGHTS
from ad_leak_engine.self_improve.tracker import process_reply

@pytest.fixture
def clean_weights(tmp_path, monkeypatch):
    test_file = tmp_path / "scoring_weights.json"
    monkeypatch.setattr("ad_leak_engine.self_improve.weights.WEIGHTS_FILE", test_file)
    return test_file

def test_load_weights_creates_default(clean_weights):
    weights = load_weights()
    assert weights == DEFAULT_WEIGHTS
    assert clean_weights.exists()

def test_process_reply_boosts_l2(clean_weights):
    load_weights() # initialize
    process_reply("p1", "Hey, our pixel was indeed broken, thanks!", positive=True)
    weights = load_weights()
    assert weights["L2"]["pixel_not_firing"] > 1.0
    assert weights["L1"]["creative_fatigue"] == 1.0 # Unchanged

def test_process_reply_caps_at_2(clean_weights):
    load_weights()
    for _ in range(20):
        process_reply("p1", "The tracking is bad", positive=True)
    weights = load_weights()
    assert weights["L2"]["pixel_not_firing"] <= 2.0
