"""Rule-based health score — PCSENSE.md §4.5.

Start at 100, subtract penalties for each condition that is true.
Rules live as a data table so the README can print them.
The LLM never produces or influences this score.
"""
from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# Penalty rules — each is (condition_fn, reason_template, penalty).
# condition_fn takes an evidence-like object and returns (bool, str)
# where str is the human-readable breakdown detail.
# ---------------------------------------------------------------------------

def _free_space_critical(e: Any) -> tuple[bool, str]:
    pct = (e.free_gb / e.total_gb * 100) if e.total_gb > 0 else 100
    if pct < 10:
        return True, f"Free space {pct:.0f}% (< 10%)"
    return False, ""


def _free_space_low(e: Any) -> tuple[bool, str]:
    pct = (e.free_gb / e.total_gb * 100) if e.total_gb > 0 else 100
    # Only applies when NOT already in the critical band
    if 10 <= pct < 20:
        return True, f"Free space {pct:.0f}% (< 20%)"
    return False, ""


def _ram_critical(e: Any) -> tuple[bool, str]:
    if e.ram_percent > 90:
        return True, f"RAM {e.ram_percent:.0f}% (> 90%)"
    return False, ""


def _ram_high(e: Any) -> tuple[bool, str]:
    if 80 < e.ram_percent <= 90:
        return True, f"RAM {e.ram_percent:.0f}% (> 80%)"
    return False, ""


def _cpu_high(e: Any) -> tuple[bool, str]:
    if e.cpu_percent > 85:
        return True, f"CPU {e.cpu_percent:.0f}% (> 85%)"
    return False, ""


def _disk_active_high(e: Any) -> tuple[bool, str]:
    if e.disk_active_percent is not None and e.disk_active_percent > 90:
        return True, f"Disk active {e.disk_active_percent:.0f}% (> 90%)"
    return False, ""


def _reclaimable_junk(e: Any) -> tuple[bool, str]:
    reclaimable_gb = e.storage.get("reclaimable_gb", 0)
    if reclaimable_gb > 5:
        return True, f"Reclaimable junk {reclaimable_gb:.1f} GB (> 5 GB)"
    return False, ""


PENALTY_RULES: list[dict] = [
    {"check": _free_space_critical, "penalty": -20},
    {"check": _free_space_low,      "penalty": -10},
    {"check": _ram_critical,        "penalty": -20},
    {"check": _ram_high,            "penalty": -10},
    {"check": _cpu_high,            "penalty": -15},
    {"check": _disk_active_high,    "penalty": -15},
    {"check": _reclaimable_junk,    "penalty": -5},
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def health_score(evidence: Any) -> tuple[int, list[tuple[str, int]]]:
    """Compute a 0–100 health score from evidence.

    Returns ``(score, breakdown)`` where *breakdown* is a list of
    ``(reason_string, penalty_int)`` for every rule that fired.
    """
    score = 100
    breakdown: list[tuple[str, int]] = []

    for rule in PENALTY_RULES:
        fired, reason = rule["check"](evidence)
        if fired:
            penalty: int = rule["penalty"]
            score += penalty  # penalty is negative
            breakdown.append((reason, penalty))

    score = max(0, min(100, score))
    return score, breakdown
