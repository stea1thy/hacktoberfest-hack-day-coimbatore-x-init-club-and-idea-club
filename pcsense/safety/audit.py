"""SQLite audit log: every request/tool call/decision/denial/result/verify. Real persistence
lands in step 2.

Owner: P1.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pcsense.contracts import AuditEntry

_LOG: list[AuditEntry] = []


def log(kind: str, payload: dict) -> AuditEntry:
    """Stub: appends to an in-memory list instead of SQLite until the real audit DB lands."""
    entry = AuditEntry(ts=datetime.now(timezone.utc).isoformat(), kind=kind, payload=payload)
    _LOG.append(entry)
    return entry


def read_all() -> list[AuditEntry]:
    """Stub: returns the in-memory log."""
    return list(_LOG)
