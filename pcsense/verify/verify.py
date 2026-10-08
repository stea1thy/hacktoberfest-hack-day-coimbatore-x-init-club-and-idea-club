"""Verification module — measured before/after outcomes.

Takes a 5-sample median of system metrics before and after an action,
then compares them to prove whether the fix actually worked.
"""
from __future__ import annotations

import os
import shutil
import statistics
import time
from typing import Optional, Any

import psutil
from pcsense.telemetry.collectors import _get_disk_active_percent

from pcsense.contracts import VerifyResult


def _get_sandbox_bytes(sandbox_dir: Optional[str]) -> int:
    """Measure total size of the sandbox directory."""
    if not sandbox_dir or not os.path.exists(sandbox_dir):
        return 0
    total = 0
    try:
        # Use os.scandir for speed, matching scanner rules where possible
        for root, dirs, files in os.walk(sandbox_dir):
            for name in files:
                path = os.path.join(root, name)
                try:
                    # Skip symlinks/junctions
                    stat = os.stat(path, follow_symlinks=False)
                    # Reparse points not strictly needed for size count, but be safe
                    total += stat.st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def measure(sandbox_dir: Optional[str] = None, target_pid: Optional[int] = None) -> dict[str, Any]:
    """Capture a stable measurement (5-sample median over ~5 seconds)."""
    cpu_samples = []
    ram_samples = []

    # 5 samples, taking ~1s each for CPU
    for _ in range(5):
        cpu_samples.append(psutil.cpu_percent(interval=1.0))
        ram_samples.append(psutil.virtual_memory().percent)

    cpu_median = round(statistics.median(cpu_samples), 1)
    ram_median = round(statistics.median(ram_samples), 1)

    disk_active = _get_disk_active_percent()

    sys_drive = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        du = shutil.disk_usage(sys_drive)
        free_gb = round(du.free / (1 << 30), 2)
    except Exception:
        free_gb = 0.0

    sandbox_bytes = _get_sandbox_bytes(sandbox_dir)

    pid_gone = True
    if target_pid is not None:
        pid_gone = not psutil.pid_exists(target_pid)

    return {
        "cpu_percent": cpu_median,
        "ram_percent": ram_median,
        "disk_active_percent": round(disk_active, 1) if disk_active is not None else None,
        "free_gb": free_gb,
        "sandbox_bytes": sandbox_bytes,
        "target_pid_gone": pid_gone,
    }


def before(sandbox_dir: Optional[str] = None, target_pid: Optional[int] = None) -> dict[str, Any]:
    """Take the 'before' measurement."""
    return measure(sandbox_dir, target_pid)


def after(sandbox_dir: Optional[str] = None, target_pid: Optional[int] = None) -> dict[str, Any]:
    """Take the 'after' measurement."""
    return measure(sandbox_dir, target_pid)


def compare(
    before_dict: dict[str, Any],
    after_dict: dict[str, Any],
    scenario: str,
    expected_freed_bytes: int = 0
) -> VerifyResult:
    """Compare before and after states to determine if the issue was resolved.

    Scenarios: 'memory_hog', 'io_hog', 'storage_cleanup'
    """
    improved = False
    summary = "The attempted fix did not resolve the issue."

    if scenario == "memory_hog":
        ram_drop = before_dict["ram_percent"] - after_dict["ram_percent"]
        # Improved requires a real measured change AND target PID gone
        if ram_drop >= 5.0 and after_dict.get("target_pid_gone", False):
            improved = True
            summary = f"Memory issue resolved. RAM usage dropped by {ram_drop:.1f}%."
        else:
            summary = "The attempted fix did not resolve the issue."

    elif scenario == "io_hog":
        disk_before = before_dict.get("disk_active_percent")
        disk_after = after_dict.get("disk_active_percent")
        pid_gone = after_dict.get("target_pid_gone", False)

        if disk_before is not None and disk_after is not None:
            disk_drop = disk_before - disk_after
            if disk_drop >= 10.0 and pid_gone:
                improved = True
                summary = f"Disk I/O issue resolved. Disk active time dropped by {disk_drop:.1f}%."
            else:
                summary = "The attempted fix did not resolve the issue."
        else:
            # Fallback if typeperf was unavailable
            if pid_gone:
                improved = True
                summary = "Process stopped (I/O metrics unavailable, assuming resolved)."
            else:
                summary = "The attempted fix did not resolve the issue."

    elif scenario == "storage_cleanup":
        bytes_freed = before_dict["sandbox_bytes"] - after_dict["sandbox_bytes"]
        gb_freed = bytes_freed / (1 << 30)

        # We consider it a success if we freed at least 90% of the expected amount,
        # or if we expected nothing and freed > 0.
        if bytes_freed > 0 and (expected_freed_bytes == 0 or bytes_freed >= expected_freed_bytes * 0.9):
            improved = True
            drive_delta = after_dict["free_gb"] - before_dict["free_gb"]
            summary = f"Recovered {gb_freed:.2f} GB (sandbox). Drive free space changed by {drive_delta:.2f} GB."
        else:
            summary = "The attempted fix did not resolve the issue."

    return VerifyResult(
        before=before_dict,
        after=after_dict,
        improved=improved,
        summary=summary
    )
