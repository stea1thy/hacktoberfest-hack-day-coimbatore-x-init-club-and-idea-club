"""`make eval` entry point: prints the metrics table from PCSENSE.md §12.

Owner: P4. Stub: prints mock metrics until prompts.jsonl + bench_models.py are real.
"""
from __future__ import annotations


def run_eval() -> dict:
    return {
        "schema_valid_rate": None,
        "routing_accuracy": None,
        "faithfulness_pass_rate": None,
        "step_latency_p50_ms": None,
        "step_latency_p95_ms": None,
        "e2e_verified_success_rate": None,
    }


if __name__ == "__main__":
    results = run_eval()
    print("PCSense eval (stub — no real runs yet):")
    for key, value in results.items():
        print(f"  {key}: {value}")
