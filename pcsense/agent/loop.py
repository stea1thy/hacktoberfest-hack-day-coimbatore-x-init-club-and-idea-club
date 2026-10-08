"""Bounded tool loop (max 4 steps) with deterministic playbook fallback on invalid/duplicate steps.

Owner: P4.
"""
from __future__ import annotations

from pcsense.contracts import Evidence
from pcsense.telemetry.collectors import collect_evidence

MAX_STEPS = 4


def run_loop(intent: str, params: dict) -> tuple[Evidence, list[dict]]:
    """Runs the bounded read-tool loop for the given intent. Stub: one deterministic step."""
    evidence = collect_evidence()
    tool_results = [{"tool": "get_system_snapshot", "result": evidence.model_dump()}]
    return evidence, tool_results
