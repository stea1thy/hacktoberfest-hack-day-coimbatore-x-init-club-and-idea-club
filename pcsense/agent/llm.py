"""Ollama client: schema-constrained calls, retries, timeouts, think:false.

Owner: P4. Model name comes from env PCSENSE_MODEL (never hard-code it).
"""
from __future__ import annotations

import os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("PCSENSE_MODEL", "gemma4:e2b")


def call_schema(prompt: str, schema: dict, retries: int = 1) -> dict:
    """POST /api/generate with format=schema, temperature=0, think=false. Stub: not yet wired to Ollama."""
    raise NotImplementedError("agent/llm.py: Ollama schema call not implemented yet (owner: P4)")
