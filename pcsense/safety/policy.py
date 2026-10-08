"""The safety layer (pure code, unit-tested). Real adversarial implementation lands in step 2 —
see PCSENSE.md §4.8 and AGENTS.md §3. This stub exists only so other modules can import `check()`
and the UI can run end to end; it must NOT be trusted for real path/process decisions yet.

Owner: P1.
"""
from __future__ import annotations

from pcsense.contracts import Action, Decision


def check(action: Action) -> Decision:
    """Validates an Action against every rule in PCSENSE.md §4.8. Stub: allows everything — DO NOT
    use against real folders or processes until the real policy engine (with adversarial tests) lands."""
    return Decision(allowed=True, reason="stub policy — not yet enforcing §4.8 rules")
