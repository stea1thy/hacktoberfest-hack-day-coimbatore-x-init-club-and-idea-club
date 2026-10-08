"""SQLite audit log: every request/tool call/decision/denial/result/verify (F11).

Owner: P1. DB path comes from env PCSENSE_AUDIT_DB (default: pcsense_audit.sqlite3 in the
cwd) so tests can isolate it; never hard-code the path elsewhere.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pcsense.contracts import AuditEntry


def _db_path() -> Path:
    return Path(os.environ.get("PCSENSE_AUDIT_DB", "pcsense_audit.sqlite3"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute(
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL
        )"""
    )
    return conn


def log(kind: str, payload: dict) -> AuditEntry:
    entry = AuditEntry(ts=datetime.now(timezone.utc).isoformat(), kind=kind, payload=payload)
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO audit_log (ts, kind, payload) VALUES (?, ?, ?)",
            (entry.ts, entry.kind, json.dumps(payload, default=str)),
        )
        conn.commit()
    finally:
        conn.close()
    return entry


def read_all() -> list[AuditEntry]:
    conn = _connect()
    try:
        rows = conn.execute("SELECT ts, kind, payload FROM audit_log ORDER BY id").fetchall()
    finally:
        conn.close()
    return [AuditEntry(ts=ts, kind=kind, payload=json.loads(payload)) for ts, kind, payload in rows]
