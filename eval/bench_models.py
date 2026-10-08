"""Benchmarks gemma4:e2b vs the 12B tag for schema-valid JSON rate and p50 latency.

Owner: P4. Stub: not yet wired to Ollama.
"""
from __future__ import annotations


def bench_models(models: list[str]) -> dict:
    return {model: {"schema_valid_rate": None, "p50_latency_ms": None} for model in models}


if __name__ == "__main__":
    import os

    print(bench_models([os.environ.get("PCSENSE_MODEL", "gemma4:e2b")]))
