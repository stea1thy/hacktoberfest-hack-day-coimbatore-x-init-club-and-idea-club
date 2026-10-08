"""The safety layer (pure code, unit-tested). Implements every check in PCSENSE.md §4.8:
tool/arg validation, sandbox confinement, reparse-point rejection, the protected denylist,
process ownership/denylist checks, and per-batch budgets.

Owner: P1. This is the only module allowed to say an action is safe. `safety/executor.py`
must call `check()` before touching the filesystem or a process; nothing else may decide this.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import stat
from pathlib import Path

import psutil

from pcsense.contracts import Action, Decision

SANDBOX_MARKER = ".pcsense_sandbox"
QUARANTINE_DIRNAME = "PCSense_Quarantine"

# Budgets (§4.8-6) — data, not buried in code.
MAX_FILES_PER_BATCH = 500
MAX_BYTES_PER_BATCH = 20_000_000_000  # 20 GB — generous headroom over the ~6 GB demo sandbox

# §4.8-5 protected process names (case-insensitive, with or without .exe)
PROTECTED_PROCESS_NAMES = {
    "system", "csrss", "wininit", "winlogon", "services", "lsass", "svchost", "explorer", "dwm",
}


# ---------------------------------------------------------------------------
# Path normalization helpers
# ---------------------------------------------------------------------------

def _expand_short_path(raw: str) -> str:
    """Best-effort 8.3 short-name -> long-name expansion (e.g. PROGRA~1 -> Program Files)."""
    if platform.system() != "Windows":
        return raw
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(32767)
        if ctypes.windll.kernel32.GetLongPathNameW(raw, buf, len(buf)):
            return buf.value
    except Exception:
        pass
    return raw


def _literal_normalize(raw: str) -> str:
    """Lexical normalization only (collapses '..' without following symlinks/junctions)."""
    return os.path.normcase(os.path.abspath(os.path.normpath(raw)))


def _resolved_normalize(raw: str) -> str:
    """OS-level canonical path: follows reparse points, expands 8.3 short names."""
    return os.path.normcase(os.path.realpath(_expand_short_path(raw)))


def _is_within(path: str, root: str) -> bool:
    root = root.rstrip(os.sep)
    if not root:
        return False
    return path == root or path.startswith(root + os.sep)


def _reparse_reason_in_chain(literal_path: str, sandbox_root_literal: str) -> str | None:
    """Rejects any symlink/junction/reparse point along the path, even if it points back
    inside the sandbox — a reparse point can be swapped after the check (TOCTOU)."""
    if not _is_within(literal_path, sandbox_root_literal) and literal_path != sandbox_root_literal:
        return None
    rel = os.path.relpath(literal_path, sandbox_root_literal)
    if rel in (".", ""):
        return None
    cumulative = sandbox_root_literal
    for part in rel.split(os.sep):
        cumulative = os.path.join(cumulative, part)
        try:
            st = os.lstat(cumulative)
        except OSError:
            continue  # not created yet — nothing to check
        if getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return f"path component '{cumulative}' is a symlink/junction/reparse point"
    return None


def _app_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _protected_roots() -> list[str]:
    system_drive = os.environ.get("SystemDrive", "C:")
    roots = [
        f"{system_drive}\\Windows",
        f"{system_drive}\\Program Files",
        f"{system_drive}\\Program Files (x86)",
        f"{system_drive}\\ProgramData",
        str(Path.home()),
        str(_app_dir()),
    ]
    try:
        roots.extend(p.mountpoint for p in psutil.disk_partitions())
    except Exception:
        pass
    return [_resolved_normalize(r) for r in roots if r]


def _sandbox_root_protected_reason(sandbox_root: Path) -> str | None:
    """Catches a misconfigured PCSENSE_SANDBOX that *is* a protected root (PCSENSE.md §17):
    e.g. PCSENSE_SANDBOX=C:\\ or =C:\\Users\\alice. A sandbox that is merely a subdirectory
    of a protected root (the common case — most sandboxes live under the user profile or a
    drive root) is fine; only exact equality is dangerous here, since every individual target
    path is already required to resolve inside the sandbox root."""
    sandbox_resolved = _resolved_normalize(str(sandbox_root))
    for root in _protected_roots():
        if sandbox_resolved == root:
            return f"PCSENSE_SANDBOX itself is the protected path '{root}'"
    return None


# ---------------------------------------------------------------------------
# Sandbox root / marker
# ---------------------------------------------------------------------------

def get_sandbox_root() -> Path | None:
    raw = os.environ.get("PCSENSE_SANDBOX")
    return Path(raw) if raw else None


def _check_marker(sandbox_root: Path) -> Decision | None:
    marker = sandbox_root / SANDBOX_MARKER
    if not marker.is_file():
        return Decision(
            allowed=False,
            reason=f"sandbox marker '{SANDBOX_MARKER}' missing at {sandbox_root} — refusing all writes",
        )
    protected_reason = _sandbox_root_protected_reason(sandbox_root)
    if protected_reason:
        return Decision(allowed=False, reason=protected_reason)
    return None


# ---------------------------------------------------------------------------
# quarantine_paths
# ---------------------------------------------------------------------------

def _check_quarantine_paths(action: Action) -> Decision:
    paths = action.params.get("paths")
    if not isinstance(paths, list) or not paths:
        return Decision(allowed=False, reason="quarantine_paths: no paths given")
    if len(paths) > MAX_FILES_PER_BATCH:
        return Decision(
            allowed=False,
            reason=f"quarantine_paths: budget exceeded — {len(paths)} files > max {MAX_FILES_PER_BATCH}",
        )
    if action.est_bytes > MAX_BYTES_PER_BATCH:
        return Decision(
            allowed=False,
            reason=f"quarantine_paths: budget exceeded — est_bytes {action.est_bytes} > max {MAX_BYTES_PER_BATCH}",
        )

    sandbox_root = get_sandbox_root()
    if sandbox_root is None:
        return Decision(allowed=False, reason="PCSENSE_SANDBOX not configured")
    marker_decision = _check_marker(sandbox_root)
    if marker_decision is not None:
        return marker_decision

    sandbox_literal = _literal_normalize(str(sandbox_root))
    sandbox_resolved = _resolved_normalize(str(sandbox_root))
    quarantine_literal = _literal_normalize(str(sandbox_root / QUARANTINE_DIRNAME))

    for raw in paths:
        literal = _literal_normalize(raw)
        if not _is_within(literal, sandbox_literal):
            return Decision(allowed=False, reason=f"quarantine_paths: '{raw}' escapes the sandbox (traversal)")
        if literal == quarantine_literal or _is_within(literal, quarantine_literal):
            return Decision(allowed=False, reason=f"quarantine_paths: '{raw}' targets the quarantine root itself")

        reparse_reason = _reparse_reason_in_chain(literal, sandbox_literal)
        if reparse_reason:
            return Decision(allowed=False, reason=f"quarantine_paths: '{raw}' {reparse_reason}")

        resolved = _resolved_normalize(raw)
        if not _is_within(resolved, sandbox_resolved):
            return Decision(allowed=False, reason=f"quarantine_paths: '{raw}' resolves outside the sandbox")

    return Decision(allowed=True, reason="ok")


# ---------------------------------------------------------------------------
# empty_quarantine / restore_from_quarantine
# ---------------------------------------------------------------------------

def _check_quarantine_batch_path(action: Action) -> Decision:
    batch_id = action.params.get("batch_id")
    if not batch_id or not isinstance(batch_id, str):
        return Decision(allowed=False, reason=f"{action.tool}: batch_id missing or invalid")

    sandbox_root = get_sandbox_root()
    if sandbox_root is None:
        return Decision(allowed=False, reason="PCSENSE_SANDBOX not configured")
    marker_decision = _check_marker(sandbox_root)
    if marker_decision is not None:
        return marker_decision

    quarantine_root = sandbox_root / QUARANTINE_DIRNAME
    quarantine_literal = _literal_normalize(str(quarantine_root))
    target_literal = _literal_normalize(str(quarantine_root / batch_id))
    if not _is_within(target_literal, quarantine_literal):
        return Decision(allowed=False, reason=f"{action.tool}: batch_id '{batch_id}' escapes the quarantine root (traversal)")

    sandbox_literal = _literal_normalize(str(sandbox_root))
    reparse_reason = _reparse_reason_in_chain(target_literal, sandbox_literal)
    if reparse_reason:
        return Decision(allowed=False, reason=f"{action.tool}: {reparse_reason}")

    quarantine_resolved = _resolved_normalize(str(quarantine_root))
    target_resolved = _resolved_normalize(str(quarantine_root / batch_id))
    if not _is_within(target_resolved, quarantine_resolved):
        return Decision(allowed=False, reason=f"{action.tool}: batch path resolves outside the quarantine root")

    return Decision(allowed=True, reason="ok")


# ---------------------------------------------------------------------------
# stop_process
# ---------------------------------------------------------------------------

def _own_username() -> str:
    return psutil.Process(os.getpid()).username()


def _own_pid_chain() -> set[int]:
    try:
        me = psutil.Process(os.getpid())
        return {me.pid} | {p.pid for p in me.parents()}
    except psutil.Error:
        return {os.getpid()}


def _check_stop_process(action: Action) -> Decision:
    pid = action.params.get("pid")
    if not isinstance(pid, int):
        return Decision(allowed=False, reason="stop_process: pid missing or invalid")

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return Decision(allowed=False, reason="stop_process: process not found")
    except psutil.Error as exc:
        return Decision(allowed=False, reason=f"stop_process: cannot inspect process ({exc})")

    if pid in _own_pid_chain():
        return Decision(allowed=False, reason="stop_process: cannot target PCSense's own process chain")

    name = proc.name().lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    if "ollama" in name:
        return Decision(allowed=False, reason="stop_process: cannot stop Ollama")
    if name in PROTECTED_PROCESS_NAMES:
        return Decision(allowed=False, reason=f"stop_process: '{name}' is a protected system process")

    try:
        owner = proc.username()
    except psutil.Error as exc:
        return Decision(allowed=False, reason=f"stop_process: cannot verify process owner ({exc})")
    if owner != _own_username():
        return Decision(allowed=False, reason="stop_process: process is not owned by the current user")

    return Decision(allowed=True, reason="ok")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def check(action: Action) -> Decision:
    if action.tool == "quarantine_paths":
        return _check_quarantine_paths(action)
    if action.tool in ("empty_quarantine", "restore_from_quarantine"):
        return _check_quarantine_batch_path(action)
    if action.tool == "stop_process":
        return _check_stop_process(action)
    return Decision(allowed=False, reason=f"unknown or unsupported tool: {action.tool!r}")


# ---------------------------------------------------------------------------
# Plan-hash binding (§4.8-7)
# ---------------------------------------------------------------------------

def compute_plan_hash(actions: list[Action]) -> str:
    canonical = [a.model_dump() for a in sorted(actions, key=lambda a: a.id)]
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
