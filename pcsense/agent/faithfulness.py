"""Every number in LLM text must match a value in the evidence JSON (+/-0.5% or +/-0.1 absolute).

Owner: P4.
"""
from __future__ import annotations

import re

from pcsense.contracts import Evidence


def check_faithfulness(text: str, evidence: Evidence) -> bool:
    """Extracts numbers from text and checks each against evidence values. Stub: always passes."""
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]
    evidence_values = {evidence.cpu_percent, evidence.ram_percent, evidence.free_gb, evidence.total_gb}
    if not numbers:
        return True
    return all(any(abs(n - v) <= max(0.1, 0.005 * v) for v in evidence_values) for n in numbers)
