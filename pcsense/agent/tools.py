"""Read-only tool registry the LLM may pick from (max 4 steps, no repeated identical calls).

Owner: P4.
"""
from __future__ import annotations

from typing import Callable

from pcsense.storage.artifacts import find_dev_artifacts
from pcsense.storage.candidates import find_temp_candidates
from pcsense.storage.duplicates import find_duplicates
from pcsense.storage.scanner import find_largest, get_storage_summary
from pcsense.telemetry.collectors import collect_evidence

READ_ONLY_TOOLS: dict[str, Callable] = {
    "get_system_snapshot": collect_evidence,
    "get_storage_summary": get_storage_summary,
    "find_largest": find_largest,
    "find_duplicates": find_duplicates,
    "find_dev_artifacts": find_dev_artifacts,
    "find_temp_candidates": find_temp_candidates,
}
