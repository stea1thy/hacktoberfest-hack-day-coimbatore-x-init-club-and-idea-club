"""Duplicate detection: size -> first/last 64KB hash -> full hash.

Owner: P3.
"""
from __future__ import annotations


def find_duplicates(root: str) -> list[dict]:
    """Groups of duplicate files with total/recoverable bytes. Stub: mock duplicate group."""
    return [
        {
            "group_id": "dup_0001",
            "paths": [f"{root}\\Downloads\\video_export_{i}.mp4" for i in range(3)],
            "bytes_each": 800_000_000,
            "recoverable_bytes": 1_600_000_000,
        }
    ]
