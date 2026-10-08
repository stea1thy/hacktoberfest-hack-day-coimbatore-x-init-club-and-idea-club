"""Before/after measurement with honest 'did not resolve' reporting (median of 5 samples).

Owner: P2.
"""
from __future__ import annotations

from pcsense.contracts import VerifyResult
from pcsense.telemetry.collectors import collect_evidence


def before() -> dict:
    """Stub: snapshot evidence as the 'before' baseline."""
    return collect_evidence().model_dump()


def after() -> dict:
    """Stub: snapshot evidence as the 'after' measurement."""
    return collect_evidence().model_dump()


def compare(before_snapshot: dict, after_snapshot: dict) -> VerifyResult:
    """Stub: mock 'improved' comparison; real impl measures sandbox bytes / RAM% deltas."""
    return VerifyResult(
        before=before_snapshot,
        after=after_snapshot,
        improved=True,
        summary="stub verify — comparison not yet measuring real deltas",
    )
