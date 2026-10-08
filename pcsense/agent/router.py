"""Free text -> {intent, params} via schema-constrained Gemma, with a keyword-router fallback baseline.

Owner: P4.
"""
from __future__ import annotations

from pcsense.contracts import RouterOut


def route(text: str) -> RouterOut:
    """Stub: naive keyword match so the UI is never blocked; real impl calls agent/llm.py."""
    lowered = text.lower()
    if "slow" in lowered:
        return RouterOut(intent="diagnose_slow", params={})
    if "free up" in lowered or "free space" in lowered:
        return RouterOut(intent="free_space", params={"goal_gb": 3})
    return RouterOut(intent="status", params={})
