"""Runs approved actions after policy.check() passes; refuses on plan_hash mismatch (§4.8-7).
Real enforcement lands in step 2.

Owner: P1.
"""
from __future__ import annotations

from pcsense.contracts import ActionResult, Plan


def run(plan: Plan, approved_ids: list[str]) -> list[ActionResult]:
    """Stub: mock successful results for each approved action id, no real execution yet."""
    return [
        ActionResult(action_id=action_id, ok=True, detail="stub executor — no-op", bytes_moved=0)
        for action_id in approved_ids
    ]
