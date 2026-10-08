"""Hypothesis rules (as data) + confidence = sum of weights of true conditions.

Owner: P2.
"""
from __future__ import annotations

from pcsense.contracts import Evidence, Hypothesis

RULES = [
    {
        "name": "memory_pressure",
        "conditions": [
            {"id": "ram_gt_85", "weight": 0.40},
            {"id": "top_proc_gt_25pct_ram", "weight": 0.30},
            {"id": "cpu_lt_60", "weight": 0.15},
            {"id": "swap_in_use", "weight": 0.15},
        ],
    },
    {
        "name": "disk_io_saturation",
        "conditions": [
            {"id": "disk_active_gt_85", "weight": 0.40},
            {"id": "one_proc_dominates_io", "weight": 0.35},
            {"id": "ram_lt_85", "weight": 0.15},
            {"id": "free_gt_10pct", "weight": 0.10},
        ],
    },
    {
        "name": "cpu_bound",
        "conditions": [
            {"id": "cpu_avg_gt_85", "weight": 0.50},
            {"id": "one_proc_gt_40pct_cpu", "weight": 0.35},
            {"id": "ram_lt_85", "weight": 0.15},
        ],
    },
    {
        "name": "storage_pressure",
        "conditions": [
            {"id": "free_lt_15pct", "weight": 0.50},
            {"id": "free_lt_10pct", "weight": 0.30},
            {"id": "large_reclaimable_set", "weight": 0.20},
        ],
    },
]


def diagnose(evidence: Evidence) -> list[Hypothesis]:
    """Rank hypotheses by rule-based confidence. Stub: mock memory_pressure guess from RAM%."""
    if evidence.ram_percent > 60:
        return [Hypothesis(name="memory_pressure", confidence=0.70, conditions_met=["ram_gt_85", "swap_in_use"])]
    return [Hypothesis(name="storage_pressure", confidence=0.30, conditions_met=["free_lt_15pct"])]
