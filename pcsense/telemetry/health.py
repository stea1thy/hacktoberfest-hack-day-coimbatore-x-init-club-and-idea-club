"""Rule-based health score (0-100) with a visible deduction breakdown. Never produced by the LLM.

Owner: P2.
"""
from __future__ import annotations

from pcsense.contracts import Evidence

PENALTIES = [
    {"signal": "free_space_lt_10pct", "penalty": 20},
    {"signal": "free_space_lt_20pct", "penalty": 10},
    {"signal": "ram_gt_90pct", "penalty": 20},
    {"signal": "ram_gt_80pct", "penalty": 10},
    {"signal": "cpu_avg_gt_85pct", "penalty": 15},
    {"signal": "disk_active_gt_90pct", "penalty": 15},
    {"signal": "reclaimable_junk_gt_5gb", "penalty": 5},
]


def health_score(evidence: Evidence, reclaimable_gb: float = 0.0) -> dict:
    """Returns {"score": int, "deductions": [{"signal": str, "penalty": int}]}. Stub: fixed mock breakdown."""
    deductions = [{"signal": "ram_gt_80pct", "penalty": 10}]
    score = 100 - sum(d["penalty"] for d in deductions)
    return {"score": score, "deductions": deductions}
