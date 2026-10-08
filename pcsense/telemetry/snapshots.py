"""SQLite snapshots for the 'what changed?' stretch feature (S1). No fake history.

Owner: P2.
"""
from __future__ import annotations


def take_snapshot(label: str) -> dict:
    """Persists a real snapshot row. Stub: returns a mock snapshot id."""
    return {"snapshot_id": "snap_mock_0001", "label": label}


def diff_snapshots(before_id: str, after_id: str) -> dict:
    """Stub: returns a mock diff."""
    return {"before_id": before_id, "after_id": after_id, "storage_delta_gb": 0.0, "ram_delta_pct": 0.0}
