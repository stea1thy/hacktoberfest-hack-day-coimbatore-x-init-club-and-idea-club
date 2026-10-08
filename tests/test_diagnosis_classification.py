"""Multi-factor diagnosis classification (PCSense_Complete_Feature_Specification.txt §1.6):
primary cause / secondary contributors / plain-language normal observations."""
from __future__ import annotations

from pcsense.contracts import Evidence, Hypothesis, Process
from pcsense.telemetry.diagnosis import classify_hypotheses

EVIDENCE = Evidence(
    ts="2026-01-01T00:00:00Z",
    cpu_percent=30.0,
    ram_percent=92.0,
    swap_percent=10.0,
    disk_active_percent=20.0,
    free_gb=200.0,
    total_gb=500.0,
    top_processes=[Process(pid=1, name="chrome.exe", cpu_percent=5.0, mem_gb=6.0)],
)


def test_high_confidence_hypothesis_becomes_primary():
    hypotheses = [Hypothesis(name="memory_pressure", confidence=0.85, conditions_met=["ram_gt_85"])]
    result = classify_hypotheses(hypotheses, EVIDENCE)
    assert result["primary"].name == "memory_pressure"
    assert result["secondary"] == []


def test_second_hypothesis_above_threshold_is_secondary_not_primary():
    hypotheses = [
        Hypothesis(name="memory_pressure", confidence=0.85, conditions_met=[]),
        Hypothesis(name="storage_pressure", confidence=0.30, conditions_met=[]),
    ]
    result = classify_hypotheses(hypotheses, EVIDENCE)
    assert result["primary"].name == "memory_pressure"
    assert [h.name for h in result["secondary"]] == ["storage_pressure"]


def test_low_confidence_hypothesis_is_dropped_not_primary_or_secondary():
    hypotheses = [Hypothesis(name="cpu_bound", confidence=0.10, conditions_met=[])]
    result = classify_hypotheses(hypotheses, EVIDENCE)
    assert result["primary"] is None
    assert result["secondary"] == []


def test_normal_observations_exclude_the_firing_hypothesis():
    """Storage is NOT flagged as pressure here (free=200/500=40%), so it should show up as a
    normal observation — but only because storage_pressure isn't the classified cause."""
    hypotheses = [Hypothesis(name="memory_pressure", confidence=0.85, conditions_met=[])]
    result = classify_hypotheses(hypotheses, EVIDENCE)
    assert any("storage" in note.lower() for note in result["normal"])
    assert all("memory" not in note.lower() for note in result["normal"])


def test_no_hypotheses_everything_is_normal_or_empty():
    result = classify_hypotheses([], EVIDENCE)
    assert result["primary"] is None
    assert result["secondary"] == []
    assert isinstance(result["normal"], list)
