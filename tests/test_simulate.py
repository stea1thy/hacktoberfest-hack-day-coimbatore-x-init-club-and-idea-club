"""What-if simulator (PCSense_Complete_Feature_Specification.txt §25)."""
from __future__ import annotations

import psutil

from pcsense.contracts import Action, Evidence, Process
from pcsense.simulate import simulate_plan


def _evidence(**overrides) -> Evidence:
    base = dict(
        ts="2026-01-01T00:00:00Z",
        cpu_percent=40.0,
        ram_percent=80.0,
        swap_percent=5.0,
        disk_active_percent=10.0,
        free_gb=50.0,
        total_gb=500.0,
        top_processes=[Process(pid=111, name="hog.exe", cpu_percent=10.0, mem_gb=4.0)],
    )
    base.update(overrides)
    return Evidence(**base)


def test_stop_process_action_predicts_ram_drop():
    evidence = _evidence()
    actions = [Action(id="a1", tool="stop_process", params={"pid": 111}, risk="HIGH", rationale="r")]
    result = simulate_plan(evidence, actions)
    assert result["ram"] is not None
    assert result["ram"]["after_percent"] < result["ram"]["before_percent"]
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    expected_drop = (4.0 / total_ram_gb) * 100
    assert result["ram"]["before_percent"] - result["ram"]["after_percent"] == expected_drop


def test_quarantine_action_predicts_storage_improvement():
    evidence = _evidence()
    actions = [
        Action(id="a1", tool="quarantine_paths", params={"paths": ["x"]}, risk="LOW", est_bytes=10_000_000_000, rationale="r")
    ]
    result = simulate_plan(evidence, actions)
    assert result["storage"] is not None
    assert result["storage"]["after_free_gb"] == 60.0
    assert result["storage"]["after_percent"] < result["storage"]["before_percent"]


def test_no_relevant_actions_returns_none_for_both():
    evidence = _evidence()
    actions = [Action(id="a1", tool="restore_from_quarantine", params={"batch_id": "x"}, risk="LOW", rationale="r")]
    result = simulate_plan(evidence, actions)
    assert result["ram"] is None
    assert result["storage"] is None
    assert result["notes"] == []


def test_stopping_unknown_pid_does_not_crash_and_yields_no_ram_effect():
    evidence = _evidence()
    actions = [Action(id="a1", tool="stop_process", params={"pid": 999999}, risk="HIGH", rationale="r")]
    result = simulate_plan(evidence, actions)
    assert result["ram"] is None
