"""Move candidates to PCSense_Quarantine/<batch_id>/ (reversible); empty permanently deletes only
inside quarantine. Real implementation + manifest handling lands in step 2.

Owner: P1.
"""
from __future__ import annotations


def quarantine_paths(paths: list[str], batch_id: str) -> dict:
    """Stub: mock move result, no filesystem writes performed yet."""
    return {"batch_id": batch_id, "quarantined": paths, "bytes": 0}


def empty_quarantine(batch_id: str) -> dict:
    """Stub: mock permanent-delete result, no filesystem writes performed yet."""
    return {"batch_id": batch_id, "deleted_bytes": 0}


def restore_from_quarantine(batch_id: str) -> dict:
    """Stub: mock restore result using the batch manifest."""
    return {"batch_id": batch_id, "restored": []}
