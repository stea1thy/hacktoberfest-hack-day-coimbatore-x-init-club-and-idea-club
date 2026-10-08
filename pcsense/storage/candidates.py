"""Risk-ranked cleanup candidates; goal selection picks cheapest-risk set to hit N GB.

Owner: P3.
"""
from __future__ import annotations

from pcsense.contracts import Action


def find_temp_candidates(root: str) -> list[dict]:
    """Stub: mock temp/log/cache candidates with age and size."""
    return [{"path": f"{root}\\Temp\\old.log", "bytes": 50_000_000, "age_days": 90}]


def candidates(root: str, goal_gb: float | None = None) -> list[Action]:
    """Risk-labelled candidate Actions, optionally trimmed to hit goal_gb. Stub: mock candidate list."""
    all_candidates = [
        Action(
            id="a1",
            tool="quarantine_paths",
            params={"paths": [f"{root}\\Temp\\old.log"]},
            risk="LOW",
            est_bytes=50_000_000,
            rationale="Old temp log, regenerable.",
        ),
        Action(
            id="a2",
            tool="quarantine_paths",
            params={"paths": [f"{root}\\Projects\\webapp\\node_modules"]},
            risk="MEDIUM",
            est_bytes=1_200_000_000,
            rationale="Dev artifact, rebuildable via npm install.",
        ),
    ]
    if goal_gb is None:
        return all_candidates
    goal_bytes = goal_gb * 1_000_000_000
    selected, total = [], 0
    for action in sorted(all_candidates, key=lambda a: {"LOW": 0, "MEDIUM": 1, "HIGH": 2}[a.risk]):
        selected.append(action)
        total += action.est_bytes
        if total >= goal_bytes:
            break
    return selected
