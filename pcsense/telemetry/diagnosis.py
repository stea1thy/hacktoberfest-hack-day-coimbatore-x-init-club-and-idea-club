"""Rule-based diagnosis — PCSENSE.md §4.4.

Hypothesis rules live as a data table (list of dicts).  Confidence is
the sum of weights whose conditions are satisfied in the evidence.
No LLM is used here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import psutil


# ---------------------------------------------------------------------------
# Condition type: (evidence) -> (satisfied: bool, detail: str)
# ---------------------------------------------------------------------------
CondFn = Callable[[Any], tuple[bool, str]]


# ---------------------------------------------------------------------------
# Condition builders — each returns a CondFn
# ---------------------------------------------------------------------------

def _ram_above(threshold: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        return (
            e.ram_percent > threshold,
            f"RAM {e.ram_percent:.0f}% {'>' if e.ram_percent > threshold else '≤'} {threshold}%",
        )
    return check


def _ram_below(threshold: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        return (
            e.ram_percent < threshold,
            f"RAM {e.ram_percent:.0f}% {'<' if e.ram_percent < threshold else '≥'} {threshold}%",
        )
    return check


def _cpu_above(threshold: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        return (
            e.cpu_percent > threshold,
            f"CPU {e.cpu_percent:.0f}% {'>' if e.cpu_percent > threshold else '≤'} {threshold}%",
        )
    return check


def _cpu_below(threshold: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        return (
            e.cpu_percent < threshold,
            f"CPU {e.cpu_percent:.0f}% {'<' if e.cpu_percent < threshold else '≥'} {threshold}%",
        )
    return check


def _disk_active_above(threshold: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        if e.disk_active_percent is None:
            return False, "Disk active %: unavailable"
        return (
            e.disk_active_percent > threshold,
            f"Disk active {e.disk_active_percent:.0f}% {'>' if e.disk_active_percent > threshold else '≤'} {threshold}%",
        )
    return check


def _top_proc_mem_above(threshold_pct: float) -> CondFn:
    """True if any single process uses > threshold_pct of total RAM."""
    def check(e: Any) -> tuple[bool, str]:
        if not e.top_processes:
            return False, "No process data"
        total_ram_gb = psutil.virtual_memory().total / (1 << 30)
        for p in e.top_processes:
            proc_pct = (p.mem_gb / total_ram_gb * 100) if total_ram_gb > 0 else 0
            if proc_pct > threshold_pct:
                return True, f"{p.name} (PID {p.pid}) uses {proc_pct:.0f}% of RAM (> {threshold_pct}%)"
        return False, f"No process > {threshold_pct}% of RAM"
    return check


def _top_proc_cpu_above(threshold_pct: float) -> CondFn:
    """True if any single process uses > threshold_pct CPU."""
    def check(e: Any) -> tuple[bool, str]:
        if not e.top_processes:
            return False, "No process data"
        for p in e.top_processes:
            if p.cpu_percent > threshold_pct:
                return True, f"{p.name} (PID {p.pid}) at {p.cpu_percent:.0f}% CPU (> {threshold_pct}%)"
        return False, f"No process > {threshold_pct}% CPU"
    return check


def _swap_in_use() -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        if e.swap_percent is None:
            return False, "Swap data unavailable"
        if e.swap_percent > 5:
            return True, f"Swap/pagefile {e.swap_percent:.0f}% in use"
        return False, f"Swap {e.swap_percent:.0f}% (low)"
    return check


def _one_proc_dominates_io() -> CondFn:
    """True if one process has > 50% of total I/O across top procs."""
    def check(e: Any) -> tuple[bool, str]:
        io_procs = [p for p in e.top_processes if p.io_mb_s is not None and p.io_mb_s > 0]
        if not io_procs:
            return False, "No I/O data"
        total_io = sum(p.io_mb_s for p in io_procs)  # type: ignore[union-attr]
        if total_io <= 0:
            return False, "No I/O activity"
        top_io = max(io_procs, key=lambda p: p.io_mb_s)  # type: ignore[union-attr,arg-type]
        share = top_io.io_mb_s / total_io * 100  # type: ignore[operator]
        if share > 50:
            return True, f"{top_io.name} (PID {top_io.pid}) dominates I/O at {share:.0f}% share"
        return False, f"I/O spread across processes (top share {share:.0f}%)"
    return check


def _free_space_above(threshold_pct: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        pct = (e.free_gb / e.total_gb * 100) if e.total_gb > 0 else 100
        return (
            pct > threshold_pct,
            f"Free space {pct:.0f}% {'>' if pct > threshold_pct else '≤'} {threshold_pct}%",
        )
    return check


def _free_space_below(threshold_pct: float) -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        pct = (e.free_gb / e.total_gb * 100) if e.total_gb > 0 else 100
        return (
            pct < threshold_pct,
            f"Free space {pct:.0f}% {'<' if pct < threshold_pct else '≥'} {threshold_pct}%",
        )
    return check


def _large_reclaimable() -> CondFn:
    def check(e: Any) -> tuple[bool, str]:
        reclaimable = e.storage.get("reclaimable_gb", 0)
        if reclaimable > 2:
            return True, f"Reclaimable set {reclaimable:.1f} GB"
        return False, f"Reclaimable set {reclaimable:.1f} GB (small)"
    return check


# ---------------------------------------------------------------------------
# Hypothesis data table — PCSENSE.md §4.4
# ---------------------------------------------------------------------------

@dataclass
class _Condition:
    name: str
    weight: float
    check: CondFn


HYPOTHESIS_TABLE: list[dict] = [
    {
        "name": "memory_pressure",
        "conditions": [
            _Condition("RAM > 85%",                        0.40, _ram_above(85)),
            _Condition("Top process > 25% of RAM",         0.30, _top_proc_mem_above(25)),
            _Condition("CPU < 60%",                        0.15, _cpu_below(60)),
            _Condition("Swap/pagefile in use",              0.15, _swap_in_use()),
        ],
    },
    {
        "name": "disk_io_saturation",
        "conditions": [
            _Condition("Disk active > 85%",                0.40, _disk_active_above(85)),
            _Condition("One process dominates I/O delta",  0.35, _one_proc_dominates_io()),
            _Condition("RAM < 85%",                        0.15, _ram_below(85)),
            _Condition("Free space > 10%",                 0.10, _free_space_above(10)),
        ],
    },
    {
        "name": "cpu_bound",
        "conditions": [
            _Condition("CPU avg > 85%",                    0.50, _cpu_above(85)),
            _Condition("One process > 40% CPU",            0.35, _top_proc_cpu_above(40)),
            _Condition("RAM < 85%",                        0.15, _ram_below(85)),
        ],
    },
    {
        "name": "storage_pressure",
        "conditions": [
            _Condition("Free < 15%",                       0.50, _free_space_below(15)),
            _Condition("Free < 10%",                       0.30, _free_space_below(10)),
            _Condition("Large reclaimable set",            0.20, _large_reclaimable()),
        ],
    },
]


# ---------------------------------------------------------------------------
# Public types & API
# ---------------------------------------------------------------------------

@dataclass
class ConditionResult:
    """Result of evaluating one condition."""
    name: str
    weight: float
    satisfied: bool
    detail: str


@dataclass
class Hypothesis:
    """A scored diagnosis hypothesis."""
    name: str
    confidence: float
    conditions: list[ConditionResult] = field(default_factory=list)


def diagnose(evidence: Any) -> list[Hypothesis]:
    """Evaluate all hypotheses against evidence.

    Returns hypotheses sorted by confidence (descending), including
    those with zero confidence so the UI can show what was ruled out.
    """
    results: list[Hypothesis] = []

    for hyp in HYPOTHESIS_TABLE:
        total_confidence = 0.0
        cond_results: list[ConditionResult] = []

        for cond in hyp["conditions"]:
            satisfied, detail = cond.check(evidence)
            cond_results.append(ConditionResult(
                name=cond.name,
                weight=cond.weight,
                satisfied=satisfied,
                detail=detail,
            ))
            if satisfied:
                total_confidence += cond.weight

        results.append(Hypothesis(
            name=hyp["name"],
            confidence=round(total_confidence, 2),
            conditions=cond_results,
        ))

    # Sort by confidence descending
    results.sort(key=lambda h: h.confidence, reverse=True)
    return results
