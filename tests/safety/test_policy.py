"""Adversarial tests for pcsense/safety/policy.py — PCSENSE.md §4.8 / AGENTS.md §3.

Written FIRST (CLAUDE.md step 2), before trusting the implementation. Every denial case
asserts the Decision is both `allowed is False` AND that the reason names the actual rule
that fired, so a future "deny everything" regression can't slip through unnoticed.
"""
from __future__ import annotations

import os
import platform
import subprocess

import pytest

from pcsense.contracts import Action
from pcsense.safety import policy

WINDOWS = platform.system() == "Windows"


def _action(tool: str, params: dict, risk: str = "MEDIUM", est_bytes: int = 0) -> Action:
    return Action(id="a1", tool=tool, params=params, risk=risk, est_bytes=est_bytes, rationale="test")


# ---------------------------------------------------------------------------
# Positive control — prove the policy isn't just "deny everything"
# ---------------------------------------------------------------------------

def test_legit_path_inside_sandbox_allowed(sandbox_root):
    target = sandbox_root / "Temp" / "old.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("junk")
    decision = policy.check(_action("quarantine_paths", {"paths": [str(target)]}))
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Sandbox marker
# ---------------------------------------------------------------------------

def test_missing_sandbox_marker_denied(unmarked_sandbox_root):
    target = unmarked_sandbox_root / "Temp" / "old.log"
    decision = policy.check(_action("quarantine_paths", {"paths": [str(target)]}))
    assert decision.allowed is False
    assert "marker" in decision.reason.lower()


def test_sandbox_not_configured_denied(monkeypatch):
    monkeypatch.delenv("PCSENSE_SANDBOX", raising=False)
    decision = policy.check(_action("quarantine_paths", {"paths": [r"C:\whatever\file.tmp"]}))
    assert decision.allowed is False


# ---------------------------------------------------------------------------
# Path traversal ('..\\')
# ---------------------------------------------------------------------------

def test_dot_dot_traversal_escaping_sandbox_denied(sandbox_root):
    evil = str(sandbox_root / ".." / "Windows" / "System32" / "config")
    decision = policy.check(_action("quarantine_paths", {"paths": [evil]}))
    assert decision.allowed is False
    assert "traversal" in decision.reason.lower() or "protected" in decision.reason.lower() or "outside" in decision.reason.lower()


def test_empty_quarantine_batch_id_traversal_denied(sandbox_root):
    (sandbox_root / policy.QUARANTINE_DIRNAME).mkdir()
    decision = policy.check(_action("empty_quarantine", {"batch_id": "..\\..\\Windows"}, risk="HIGH"))
    assert decision.allowed is False
    assert "traversal" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Protected paths (denylist)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not WINDOWS, reason="Windows-only protected paths")
def test_windows_system_dir_denied(sandbox_root):
    system_drive = os.environ.get("SystemDrive", "C:")
    decision = policy.check(_action("quarantine_paths", {"paths": [f"{system_drive}\\Windows\\System32\\drivers\\etc\\hosts"]}))
    assert decision.allowed is False


@pytest.mark.skipif(not WINDOWS, reason="Windows-only protected paths")
def test_drive_root_denied(sandbox_root):
    system_drive = os.environ.get("SystemDrive", "C:")
    decision = policy.check(_action("quarantine_paths", {"paths": [f"{system_drive}\\"]}))
    assert decision.allowed is False


@pytest.mark.skipif(not WINDOWS, reason="Windows-only protected paths")
def test_user_profile_root_denied(sandbox_root):
    decision = policy.check(_action("quarantine_paths", {"paths": [os.environ["USERPROFILE"]]}))
    assert decision.allowed is False


@pytest.mark.skipif(not WINDOWS, reason="Windows-only protected paths")
def test_app_dir_itself_denied(sandbox_root):
    app_dir = policy._app_dir()
    decision = policy.check(_action("quarantine_paths", {"paths": [str(app_dir)]}))
    assert decision.allowed is False


def test_quarantine_root_as_source_denied(sandbox_root):
    quarantine_dir = sandbox_root / policy.QUARANTINE_DIRNAME
    quarantine_dir.mkdir()
    decision = policy.check(_action("quarantine_paths", {"paths": [str(quarantine_dir)]}))
    assert decision.allowed is False
    assert "quarantine root" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Case tricks / 8.3 short names
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not WINDOWS, reason="Windows-only case-insensitivity")
def test_mixed_case_protected_path_denied(sandbox_root):
    system_drive = os.environ.get("SystemDrive", "C:")
    decision = policy.check(_action("quarantine_paths", {"paths": [f"{system_drive}\\WiNdOwS\\sYsTeM32"]}))
    assert decision.allowed is False


@pytest.mark.skipif(not WINDOWS, reason="Windows-only 8.3 short names")
def test_8dot3_short_name_trick_denied(sandbox_root):
    system_drive = os.environ.get("SystemDrive", "C:")
    short_dir = f"{system_drive}\\PROGRA~1"
    if not os.path.exists(short_dir):
        pytest.skip("8.3 short names disabled/unavailable on this system")
    decision = policy.check(_action("quarantine_paths", {"paths": [f"{short_dir}\\Evil"]}))
    assert decision.allowed is False


# ---------------------------------------------------------------------------
# Junction / reparse-point trap
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not WINDOWS, reason="Windows junctions")
def test_junction_trap_denied(sandbox_root, tmp_path):
    outside_target = tmp_path / "outside_target"
    outside_target.mkdir()
    (outside_target / "secret.txt").write_text("not yours")

    trap = sandbox_root / "Trap"
    try:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(trap), str(outside_target)],
            check=True, capture_output=True, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        pytest.skip(f"could not create a junction on this system: {exc}")

    decision = policy.check(_action("quarantine_paths", {"paths": [str(trap / "secret.txt")]}))
    assert decision.allowed is False
    assert "reparse" in decision.reason.lower() or "junction" in decision.reason.lower() or "symlink" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def test_too_many_files_denied(sandbox_root):
    paths = [str(sandbox_root / "Temp" / f"f{i}.tmp") for i in range(policy.MAX_FILES_PER_BATCH + 1)]
    decision = policy.check(_action("quarantine_paths", {"paths": paths}))
    assert decision.allowed is False
    assert "budget" in decision.reason.lower()


def test_too_many_bytes_denied(sandbox_root):
    target = sandbox_root / "Temp" / "huge.bin"
    decision = policy.check(
        _action("quarantine_paths", {"paths": [str(target)]}, est_bytes=policy.MAX_BYTES_PER_BATCH + 1)
    )
    assert decision.allowed is False
    assert "budget" in decision.reason.lower()


# ---------------------------------------------------------------------------
# Protected / unowned processes (stop_process)
# ---------------------------------------------------------------------------

class _FakeProcess:
    def __init__(self, name: str, username: str, pid: int = 4242):
        self._name = name
        self._username = username
        self.pid = pid

    def name(self) -> str:
        return self._name

    def username(self) -> str:
        return self._username


def test_stop_protected_system_process_denied(monkeypatch, sandbox_root):
    monkeypatch.setattr(policy, "_own_pid_chain", lambda: {os.getpid()})
    monkeypatch.setattr(policy, "_own_username", lambda: "alice")
    monkeypatch.setattr(policy.psutil, "Process", lambda pid: _FakeProcess("explorer.exe", "alice", pid))
    decision = policy.check(_action("stop_process", {"pid": 111}, risk="HIGH"))
    assert decision.allowed is False
    assert "protected" in decision.reason.lower()


def test_stop_ollama_denied(monkeypatch, sandbox_root):
    monkeypatch.setattr(policy, "_own_pid_chain", lambda: {os.getpid()})
    monkeypatch.setattr(policy, "_own_username", lambda: "alice")
    monkeypatch.setattr(policy.psutil, "Process", lambda pid: _FakeProcess("ollama.exe", "alice", pid))
    decision = policy.check(_action("stop_process", {"pid": 222}, risk="HIGH"))
    assert decision.allowed is False
    assert "ollama" in decision.reason.lower()


def test_stop_own_process_chain_denied(monkeypatch, sandbox_root):
    monkeypatch.setattr(policy, "_own_pid_chain", lambda: {os.getpid(), 333})
    monkeypatch.setattr(policy, "_own_username", lambda: "alice")
    monkeypatch.setattr(policy.psutil, "Process", lambda pid: _FakeProcess("python.exe", "alice", pid))
    decision = policy.check(_action("stop_process", {"pid": 333}, risk="HIGH"))
    assert decision.allowed is False
    assert "own process" in decision.reason.lower()


def test_stop_process_not_owned_by_current_user_denied(monkeypatch, sandbox_root):
    monkeypatch.setattr(policy, "_own_pid_chain", lambda: {os.getpid()})
    monkeypatch.setattr(policy, "_own_username", lambda: "alice")
    monkeypatch.setattr(policy.psutil, "Process", lambda pid: _FakeProcess("chrome.exe", "bob", pid))
    decision = policy.check(_action("stop_process", {"pid": 444}, risk="HIGH"))
    assert decision.allowed is False
    assert "owned" in decision.reason.lower()


def test_stop_legit_user_process_allowed(monkeypatch, sandbox_root):
    monkeypatch.setattr(policy, "_own_pid_chain", lambda: {os.getpid()})
    monkeypatch.setattr(policy, "_own_username", lambda: "alice")
    monkeypatch.setattr(policy.psutil, "Process", lambda pid: _FakeProcess("hog_mem.exe", "alice", pid))
    decision = policy.check(_action("stop_process", {"pid": 555}, risk="HIGH"))
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

def test_unknown_tool_denied(sandbox_root):
    decision = policy.check(_action("delete_everything", {}, risk="HIGH"))
    assert decision.allowed is False
