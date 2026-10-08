"""Sustained disk read/write loop, to seed a reliable disk_io_saturation diagnosis demo.

Owner: P2. Stub: argument parsing only; real I/O loop lands in step 2.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path


def hog_io(target_dir: str, duration_seconds: int) -> None:
    target = Path(target_dir) / "hog_io.tmp"
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"[stub] would read/write {target} for {duration_seconds}s")
    time.sleep(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--duration-seconds", type=int, default=60)
    args = parser.parse_args()
    hog_io(args.target_dir, args.duration_seconds)
