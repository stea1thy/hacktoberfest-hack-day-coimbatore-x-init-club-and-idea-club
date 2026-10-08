"""Move candidates to PCSense_Quarantine/<batch_id>/ (reversible); empty permanently deletes
only inside quarantine. Every function here is called ONLY by safety/executor.py, and only
after safety/policy.check() has approved the action (AGENTS.md §3).

Owner: P1.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from pcsense.safety import policy


def _size_of(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_dir():
        return _dir_size(path)
    return path.stat().st_size


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def quarantine_paths(paths: list[str], batch_id: str) -> dict:
    sandbox_root = policy.get_sandbox_root()
    if sandbox_root is None:
        raise RuntimeError("PCSENSE_SANDBOX not configured")
    quarantine_dir = sandbox_root / policy.QUARANTINE_DIRNAME / batch_id
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"batch_id": batch_id, "items": []}
    total_bytes = 0
    for raw in paths:
        src = Path(raw)
        size = _size_of(src)
        dest = quarantine_dir / src.name
        shutil.move(str(src), str(dest))
        manifest["items"].append({"original": str(src), "quarantined": str(dest)})
        total_bytes += size

    (quarantine_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return {
        "detail": f"quarantined {len(paths)} item(s) ({total_bytes} bytes) into batch '{batch_id}'",
        "bytes": total_bytes,
        "quarantined": [item["quarantined"] for item in manifest["items"]],
    }


def empty_quarantine(batch_id: str) -> dict:
    sandbox_root = policy.get_sandbox_root()
    if sandbox_root is None:
        raise RuntimeError("PCSENSE_SANDBOX not configured")
    quarantine_dir = sandbox_root / policy.QUARANTINE_DIRNAME / batch_id
    deleted_bytes = _dir_size(quarantine_dir)
    shutil.rmtree(quarantine_dir, ignore_errors=True)
    return {"detail": f"emptied batch '{batch_id}' ({deleted_bytes} bytes recovered)", "bytes": deleted_bytes}


def restore_from_quarantine(batch_id: str) -> dict:
    sandbox_root = policy.get_sandbox_root()
    if sandbox_root is None:
        raise RuntimeError("PCSENSE_SANDBOX not configured")
    quarantine_dir = sandbox_root / policy.QUARANTINE_DIRNAME / batch_id
    manifest_path = quarantine_dir / "manifest.json"
    if not manifest_path.is_file():
        return {"detail": f"no manifest found for batch '{batch_id}'", "bytes": 0, "restored": []}

    manifest = json.loads(manifest_path.read_text())
    restored = []
    for item in manifest["items"]:
        shutil.move(item["quarantined"], item["original"])
        restored.append(item["original"])
    return {"detail": f"restored {len(restored)} item(s) from batch '{batch_id}'", "bytes": 0, "restored": restored}
