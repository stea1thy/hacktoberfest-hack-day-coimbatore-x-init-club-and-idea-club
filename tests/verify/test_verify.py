"""Tests for pcsense.verify.verify — before/after measurement logic."""
from __future__ import annotations

from pcsense.verify.verify import compare

def test_memory_hog_resolved() -> None:
    before = {"ram_percent": 90.0, "target_pid_gone": False}
    after = {"ram_percent": 80.0, "target_pid_gone": True}
    res = compare(before, after, "memory_hog")
    assert res.improved is True
    assert "Memory issue resolved" in res.summary

def test_memory_hog_not_resolved_ram_stuck() -> None:
    before = {"ram_percent": 90.0, "target_pid_gone": False}
    after = {"ram_percent": 88.0, "target_pid_gone": True} # < 5% drop
    res = compare(before, after, "memory_hog")
    assert res.improved is False
    assert res.summary == "The attempted fix did not resolve the issue."

def test_io_hog_resolved() -> None:
    before = {"disk_active_percent": 95.0, "target_pid_gone": False}
    after = {"disk_active_percent": 10.0, "target_pid_gone": True}
    res = compare(before, after, "io_hog")
    assert res.improved is True
    assert "Disk I/O issue resolved" in res.summary

def test_io_hog_not_resolved() -> None:
    before = {"disk_active_percent": 95.0, "target_pid_gone": False}
    after = {"disk_active_percent": 90.0, "target_pid_gone": True}
    res = compare(before, after, "io_hog")
    assert res.improved is False
    assert res.summary == "The attempted fix did not resolve the issue."

def test_storage_cleanup_resolved() -> None:
    before = {"sandbox_bytes": 5 * (1 << 30), "free_gb": 100.0}
    after = {"sandbox_bytes": 2 * (1 << 30), "free_gb": 103.0}
    res = compare(before, after, "storage_cleanup", expected_freed_bytes=3 * (1 << 30))
    assert res.improved is True
    assert "Recovered 3.00 GB (sandbox)" in res.summary
    assert "changed by 3.00 GB" in res.summary

def test_storage_cleanup_not_resolved() -> None:
    before = {"sandbox_bytes": 5 * (1 << 30), "free_gb": 100.0}
    after = {"sandbox_bytes": 5 * (1 << 30), "free_gb": 100.0}
    res = compare(before, after, "storage_cleanup", expected_freed_bytes=3 * (1 << 30))
    assert res.improved is False
    assert res.summary == "The attempted fix did not resolve the issue."
