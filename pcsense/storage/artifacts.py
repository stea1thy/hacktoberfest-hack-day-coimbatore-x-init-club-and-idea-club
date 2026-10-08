"""Dev-artifact detection by name/path rules (node_modules, dist, build, __pycache__, venvs).

Owner: P3.
"""
from __future__ import annotations

ARTIFACT_NAMES = {"node_modules", "dist", "build", "__pycache__", ".venv", "venv"}


def find_dev_artifacts(root: str) -> list[dict]:
    """Stub: mock dev-artifact matches with sizes."""
    return [
        {"path": f"{root}\\Projects\\webapp\\node_modules", "bytes": 1_200_000_000, "kind": "node_modules"},
        {"path": f"{root}\\Projects\\ml\\__pycache__", "bytes": 15_000_000, "kind": "__pycache__"},
    ]
