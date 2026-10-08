"""Telemetry collectors — real system measurements, no LLM.

Provides ``collect_evidence()`` which gathers CPU, RAM, swap, disk,
and per-process metrics using *psutil* and a single fixed-args
``typeperf`` call for disk-active %.

Once P1 lands ``contracts.py`` the local stubs below will be replaced
by a one-line import change.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import psutil

# ---------------------------------------------------------------------------
# Local stub models — mirrors contracts.py exactly.
# TODO: replace with `from pcsense.contracts import Process, Evidence`
#       once P1 commits the skeleton.
# ---------------------------------------------------------------------------
try:
    from pcsense.contracts import Process, Evidence  # type: ignore[import]
except ImportError:
    from pydantic import BaseModel

    class Process(BaseModel):  # type: ignore[no-redef]
        pid: int
        name: str
        cpu_percent: float
        mem_gb: float
        io_mb_s: Optional[float] = None

    class Evidence(BaseModel):  # type: ignore[no-redef]
        ts: str
        cpu_percent: float
        ram_percent: float
        swap_percent: Optional[float]
        disk_active_percent: Optional[float]
        free_gb: float
        total_gb: float
        top_processes: list[Process] = []
        storage: dict = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TOP_N = 10  # default number of top processes to return
_IO_SAMPLE_INTERVAL = 2.0  # seconds between I/O counter snapshots
_CPU_PRIME_INTERVAL = 0.8  # seconds for cpu_percent priming


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _display_name(proc: psutil.Process) -> str:
    """Return a human-friendly process name.

    For python.exe processes, appends the script name from cmdline
    (e.g. ``python.exe [hog_mem.py]``) so the user can tell them apart.
    """
    try:
        name = proc.name()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return "<unknown>"

    if name.lower() in ("python.exe", "python3.exe", "pythonw.exe"):
        try:
            cmdline = proc.cmdline()
            # Find the first .py argument
            for arg in cmdline[1:]:
                if arg.endswith(".py"):
                    script = os.path.basename(arg)
                    return f"{name} [{script}]"
        except (psutil.AccessDenied, psutil.NoSuchProcess, IndexError):
            pass

    return name


def _get_disk_active_percent() -> Optional[float]:
    """Read disk-active % via a fixed-args ``typeperf`` call.

    Returns ``None`` if parsing fails (e.g. non-English counter names
    or typeperf not available).
    """
    try:
        result = subprocess.run(
            [
                "typeperf",
                "\\PhysicalDisk(_Total)\\% Disk Time",
                "-sc", "1",       # one sample
            ],
            capture_output=True,
            text=True,
            timeout=8,
            shell=False,          # AGENTS.md: never shell=True
        )
        # typeperf CSV output looks like:
        #   "(PDH-CSV 4.0)","\\…\\% Disk Time"
        #   "10/08/2026 12:00:00.000","42.123"
        for line in result.stdout.splitlines():
            # Skip the header row
            if "PDH-CSV" in line or "Disk Time" in line.replace('"', ''):
                continue
            # Try to extract the numeric value from the second CSV field
            match = re.search(r'"([^"]*)"[,\s]+"([^"]*)"', line)
            if match:
                raw = match.group(2).strip()
                try:
                    val = float(raw)
                    # Clamp to [0, 100] — typeperf can briefly exceed 100
                    return max(0.0, min(val, 100.0))
                except ValueError:
                    continue
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return None


def _collect_top_processes(
    by: str = "mem",
    n: int = _TOP_N,
) -> list[Process]:
    """Gather top-N processes by memory or CPU, with I/O rates.

    I/O counters are cumulative, so we sample twice ~2 s apart and
    compute the delta to get MB/s.
    """
    # --- First pass: prime cpu_percent and grab I/O baseline ----------
    procs_snap: dict[int, dict] = {}

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc.cpu_percent()  # priming call (returns 0.0)
            io_start = proc.io_counters()
            procs_snap[proc.pid] = {
                "proc": proc,
                "io_start_read": io_start.read_bytes,
                "io_start_write": io_start.write_bytes,
            }
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
            continue

    time.sleep(_IO_SAMPLE_INTERVAL)

    # --- Second pass: collect real cpu_percent + I/O delta -------------
    results: list[Process] = []

    for pid, snap in procs_snap.items():
        proc: psutil.Process = snap["proc"]
        try:
            cpu = proc.cpu_percent()
            mem_bytes = proc.memory_info().rss
            mem_gb = round(mem_bytes / (1 << 30), 3)

            # I/O delta
            io_end = proc.io_counters()
            io_bytes = (
                (io_end.read_bytes - snap["io_start_read"])
                + (io_end.write_bytes - snap["io_start_write"])
            )
            io_mb_s = round(io_bytes / (1 << 20) / _IO_SAMPLE_INTERVAL, 2)

            name = _display_name(proc)
            results.append(Process(
                pid=pid,
                name=name,
                cpu_percent=round(cpu, 1),
                mem_gb=mem_gb,
                io_mb_s=io_mb_s,
            ))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    # Sort by requested metric
    if by == "cpu":
        results.sort(key=lambda p: p.cpu_percent, reverse=True)
    elif by == "io":
        results.sort(key=lambda p: (p.io_mb_s or 0.0), reverse=True)
    else:  # default: memory
        results.sort(key=lambda p: p.mem_gb, reverse=True)

    return results[:n]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect_evidence(
    *,
    top_by: str = "mem",
    top_n: int = _TOP_N,
) -> Evidence:
    """Collect a full system evidence snapshot.

    This takes ~3 s (CPU priming + I/O delta sampling).
    """
    # CPU — blocking interval-based measurement
    cpu = psutil.cpu_percent(interval=_CPU_PRIME_INTERVAL)

    # RAM / Swap
    vm = psutil.virtual_memory()
    ram_pct = vm.percent

    try:
        sw = psutil.swap_memory()
        swap_pct = sw.percent
    except Exception:
        swap_pct = None

    # Disk free / total — system drive
    sys_drive = os.environ.get("SystemDrive", "C:") + "\\"
    du = shutil.disk_usage(sys_drive)
    free_gb = round(du.free / (1 << 30), 2)
    total_gb = round(du.total / (1 << 30), 2)

    # Disk active %
    disk_active = _get_disk_active_percent()

    # Top processes (includes ~2 s I/O delta)
    top_procs = _collect_top_processes(by=top_by, n=top_n)

    return Evidence(
        ts=datetime.now(timezone.utc).isoformat(),
        cpu_percent=round(cpu, 1),
        ram_percent=round(ram_pct, 1),
        swap_percent=round(swap_pct, 1) if swap_pct is not None else None,
        disk_active_percent=round(disk_active, 1) if disk_active is not None else None,
        free_gb=free_gb,
        total_gb=total_gb,
        top_processes=top_procs,
    )
