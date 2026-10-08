"""CPU/RAM/swap/disk + per-process metrics via psutil, disk activity via typeperf.

Owner: P2. Stub returns realistic mock data until the real collectors land.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pcsense.contracts import Evidence, Process


def collect_evidence() -> Evidence:
    """Snapshot of system + top-process state. Real impl samples psutil twice for I/O deltas."""
    return Evidence(
        ts=datetime.now(timezone.utc).isoformat(),
        cpu_percent=42.0,
        ram_percent=61.5,
        swap_percent=5.0,
        disk_active_percent=18.0,
        free_gb=120.4,
        total_gb=512.0,
        top_processes=[
            Process(pid=1234, name="chrome.exe", cpu_percent=12.0, mem_gb=1.8, io_mb_s=0.4),
            Process(pid=5678, name="ollama.exe", cpu_percent=8.0, mem_gb=3.2, io_mb_s=0.1),
        ],
        storage={},
    )
