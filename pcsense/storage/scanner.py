"""Scoped os.scandir scanner. No link following, skip access-denied, time-budgeted.

Owner: P3.
"""
from __future__ import annotations


def get_storage_summary(root: str) -> dict:
    """Size by top-level folder and file-type group. Stub: mock summary."""
    return {
        "root": root,
        "by_folder": {"Downloads": 4_200_000_000, "Projects": 1_800_000_000, "Temp": 300_000_000},
        "by_type": {"video": 2_400_000_000, "code": 900_000_000, "other": 3_000_000_000},
    }


def find_largest(root: str, n: int = 10) -> list[dict]:
    """Stub: mock largest-files list."""
    return [{"path": f"{root}\\Downloads\\video_export_{i}.mp4", "bytes": 800_000_000} for i in range(min(n, 3))]


def scan(root: str) -> list[dict]:
    """Full scoped scan entry point used by candidates(). Stub: mock file list."""
    return find_largest(root, n=10)
