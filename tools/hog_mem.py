"""Allocates N GB and holds it, to seed a reliable memory_pressure diagnosis demo.

Owner: P2. Stub: argument parsing only; real allocation loop lands in step 2.
"""
from __future__ import annotations

import argparse
import time


def hog_mem(gb: float, hold_seconds: int) -> None:
    block = bytearray(int(gb * 1024 ** 3))
    print(f"[stub] allocated {gb} GB, holding for {hold_seconds}s")
    time.sleep(hold_seconds)
    del block


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gb", type=float, default=2.0)
    parser.add_argument("--hold-seconds", type=int, default=60)
    args = parser.parse_args()
    hog_mem(args.gb, args.hold_seconds)
