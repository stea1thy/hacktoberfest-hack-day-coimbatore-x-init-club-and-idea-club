"""Gemma writes Observed/Inferred/Uncertain from evidence; recommended_action_ids subset actions.

Owner: P4.
"""
from __future__ import annotations

from pcsense.contracts import Action, Evidence, Explanation, Hypothesis


def explain(evidence: Evidence, hypotheses: list[Hypothesis], actions: list[Action]) -> Explanation:
    """Stub: deterministic template explanation, no LLM call yet."""
    top = hypotheses[0] if hypotheses else None
    headline = f"Likely cause: {top.name}" if top else "No clear cause found."
    return Explanation(
        headline=headline,
        observed=[f"RAM at {evidence.ram_percent}%"],
        inferred=[f"{top.name} (confidence {top.confidence:.2f})"] if top else [],
        uncertain=["Disk I/O trend unconfirmed over a short sample."],
        recommended_action_ids=[a.id for a in actions[:1]],
    )
