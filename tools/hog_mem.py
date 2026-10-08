"""PCSense demo — memory hog.

Allocates a large bytearray and touches every page so the memory is
really committed (not just reserved).  Prints its PID so the demo
can target it with stop_process.

Usage:
    python tools/hog_mem.py --gb 3 --hold 600
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time

PAGE_SIZE = 4096  # bytes per page on x86-64 Windows


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Allocate and hold RAM for demo purposes.")
    p.add_argument("--gb", type=float, default=3.0, help="Gigabytes to allocate (default: 3)")
    p.add_argument("--hold", type=int, default=600, help="Seconds to hold before releasing (default: 600)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    nbytes = int(args.gb * (1 << 30))  # GB → bytes

    print(f"[hog_mem] PID={os.getpid()}  Allocating {args.gb:.1f} GB …")

    buf = bytearray(nbytes)

    # Touch every page so the OS actually commits physical RAM.
    print(f"[hog_mem] Touching {nbytes // PAGE_SIZE:,} pages …")
    for offset in range(0, nbytes, PAGE_SIZE):
        buf[offset] = 0xFF
    print(f"[hog_mem] Memory committed.  Holding for {args.hold}s (Ctrl+C to stop).")

    try:
        time.sleep(args.hold)
    except KeyboardInterrupt:
        pass

    # Explicit release (CPython refcount would handle it, but be explicit).
    del buf
    print("[hog_mem] Released.  Exiting.")


if __name__ == "__main__":
    main()
