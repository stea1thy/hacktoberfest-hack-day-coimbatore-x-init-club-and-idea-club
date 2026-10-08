"""What-if simulator (PCSense_Complete_Feature_Specification.txt §25): estimates the effect of
a proposed Plan before approval, reusing the Evidence/Action data the orchestrator already has.
Read-only — never touches the filesystem or a process, so it's safe to run before any approval.

New top-level module (not under telemetry/** or storage/**) since it reads across both domains;
wired in from pcsense/orchestrator.py.
"""
from __future__ import annotations

import psutil

from pcsense.contracts import Action, Evidence


def simulate_plan(evidence: Evidence, actions: list[Action]) -> dict:
    """Returns {"ram": {...} | None, "storage": {...} | None, "notes": [str, ...]}."""
    ram_effect = _simulate_ram(evidence, actions)
    storage_effect = _simulate_storage(evidence, actions)

    notes = []
    if ram_effect:
        notes.append(
            f"RAM: {ram_effect['before_percent']:.0f}% -> approximately {ram_effect['after_percent']:.0f}%"
        )
    if storage_effect:
        notes.append(
            f"Storage used: {storage_effect['before_percent']:.0f}% -> "
            f"approximately {storage_effect['after_percent']:.0f}%"
        )
    return {"ram": ram_effect, "storage": storage_effect, "notes": notes}


def _simulate_ram(evidence: Evidence, actions: list[Action]) -> dict | None:
    stop_pids = {a.params.get("pid") for a in actions if a.tool == "stop_process"}
    if not stop_pids:
        return None
    freed_gb = sum(p.mem_gb for p in evidence.top_processes if p.pid in stop_pids)
    if freed_gb <= 0:
        return None
    try:
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
    except Exception:
        return None
    if total_ram_gb <= 0:
        return None
    freed_percent_points = (freed_gb / total_ram_gb) * 100
    before_percent = evidence.ram_percent
    after_percent = max(0.0, before_percent - freed_percent_points)
    return {"before_percent": before_percent, "after_percent": after_percent, "freed_gb": freed_gb}


def _simulate_storage(evidence: Evidence, actions: list[Action]) -> dict | None:
    freed_bytes = sum(a.est_bytes for a in actions if a.tool in ("quarantine_paths", "empty_quarantine"))
    if freed_bytes <= 0 or evidence.total_gb <= 0:
        return None
    freed_gb = freed_bytes / 1_000_000_000
    before_free_gb = evidence.free_gb
    after_free_gb = min(evidence.total_gb, before_free_gb + freed_gb)
    before_percent = 100 * (1 - before_free_gb / evidence.total_gb)
    after_percent = 100 * (1 - after_free_gb / evidence.total_gb)
    return {
        "before_percent": before_percent,
        "after_percent": after_percent,
        "freed_gb": freed_gb,
        "before_free_gb": before_free_gb,
        "after_free_gb": after_free_gb,
    }
