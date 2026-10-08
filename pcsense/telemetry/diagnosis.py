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


# Multi-factor diagnosis (PCSense_Complete_Feature_Specification.txt §1.6): don't treat every
# ranked hypothesis as a problem. Split into a primary cause, weaker secondary contributors,
# and plain-language notes about metrics that are elevated but not actually a problem.
PRIMARY_CONFIDENCE_THRESHOLD = 0.5
SECONDARY_CONFIDENCE_THRESHOLD = 0.2


def classify_hypotheses(hypotheses: list[Hypothesis], evidence: Evidence) -> dict:
    """Returns {"primary": Hypothesis|None, "secondary": list[Hypothesis], "normal": list[str]}.

    Purely additive — `diagnose()`'s signature and the Hypothesis contract are unchanged;
    this just classifies what diagnose() already returned, for a richer activity-feed/UI view.
    """
    ranked = sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
    primary = ranked[0] if ranked and ranked[0].confidence >= PRIMARY_CONFIDENCE_THRESHOLD else None
    rest = ranked[1:] if primary else ranked
    secondary = [h for h in rest if h.confidence >= SECONDARY_CONFIDENCE_THRESHOLD]
    exclude_names = {h.name for h in ([primary] if primary else []) + secondary}
    return {
        "primary": primary,
        "secondary": secondary,
        "normal": _normal_observations(evidence, exclude_names),
    }


def _normal_observations(evidence: Evidence, exclude_names: set[str]) -> list[str]:
    """Plain-language notes for metrics that look elevated but aren't flagged as a cause —
    avoids treating every high number as an error (§1.6)."""
    notes = []
    if "cpu_bound" not in exclude_names and evidence.cpu_percent < 70:
        notes.append(f"CPU usage is {evidence.cpu_percent:.0f}% — within normal range")
    if (
        "disk_io_saturation" not in exclude_names
        and evidence.disk_active_percent is not None
        and evidence.disk_active_percent < 50
    ):
        notes.append(f"Disk activity is {evidence.disk_active_percent:.0f}% — not a bottleneck")
    if "storage_pressure" not in exclude_names and evidence.total_gb > 0:
        free_percent = 100 * evidence.free_gb / evidence.total_gb
        if free_percent > 20:
            notes.append(f"Storage has {free_percent:.0f}% free — not under pressure")
    return notes
