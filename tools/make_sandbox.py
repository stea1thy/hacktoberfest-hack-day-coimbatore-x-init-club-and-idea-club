"""Seeded sandbox generator (PCSENSE.md §11.1): duplicates, dev artifacts, temp junk, a
protected Documents folder, a hostile filename, and a junction trap. Writes the
.pcsense_sandbox marker file so safety/policy.py will allow writes there.

Owner: P3. Stub: creates the marker + folder skeleton only; real seeded content lands in step 2.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def make_sandbox(root: str, size_gb: float, seed: int) -> None:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    (root_path / ".pcsense_sandbox").write_text("marker\n")
    for folder in ("Downloads", "Projects/webapp", "Projects/ml", "Temp", "Documents", "Trap"):
        (root_path / folder).mkdir(parents=True, exist_ok=True)
    print(f"[stub] sandbox skeleton created at {root_path} (size_gb={size_gb}, seed={seed})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--size-gb", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    make_sandbox(args.root, args.size_gb, args.seed)
