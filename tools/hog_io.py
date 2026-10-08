"""PCSense demo — disk I/O hog.

Spawns threads that write chunks, fsync, and read back at random
offsets to saturate disk I/O.  Works inside %TEMP%\\pcsense_hog_io
and cleans up on exit.

Usage:
    python tools/hog_io.py --mb 512 --seconds 600 --threads 4
"""
from __future__ import annotations

import argparse
import atexit
import os
import random
import shutil
import sys
import tempfile
import threading
import time

_STOP = threading.Event()

CHUNK_SIZE = 1 << 20  # 1 MiB writes


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sustained disk I/O for demo purposes.")
    p.add_argument("--mb", type=int, default=512, help="File size in MiB per thread (default: 512)")
    p.add_argument("--seconds", type=int, default=600, help="Duration in seconds (default: 600)")
    p.add_argument("--threads", type=int, default=4, help="Number of I/O threads (default: 4)")
    return p.parse_args()


def _io_worker(worker_id: int, path: str, file_bytes: int) -> None:
    """Write-fsync-read loop until STOP is set."""
    chunk = os.urandom(CHUNK_SIZE)
    try:
        with open(path, "w+b") as f:
            while not _STOP.is_set():
                # ── Write pass ──
                f.seek(0)
                written = 0
                while written < file_bytes and not _STOP.is_set():
                    f.write(chunk)
                    written += CHUNK_SIZE
                f.flush()
                os.fsync(f.fileno())

                # ── Random-read pass ──
                for _ in range(file_bytes // CHUNK_SIZE):
                    if _STOP.is_set():
                        break
                    offset = random.randint(0, max(0, file_bytes - CHUNK_SIZE))
                    f.seek(offset)
                    f.read(CHUNK_SIZE)
    except Exception as exc:
        print(f"[hog_io] worker-{worker_id}: {exc}", file=sys.stderr)


def _cleanup(work_dir: str) -> None:
    """Best-effort removal of the temp directory."""
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"[hog_io] Cleaned up {work_dir}")
    except Exception:
        pass


def main() -> None:
    args = _parse_args()
    file_bytes = args.mb * (1 << 20)

    # Work directory under %TEMP%
    base = os.path.join(tempfile.gettempdir(), "pcsense_hog_io")
    os.makedirs(base, exist_ok=True)
    atexit.register(_cleanup, base)

    print(f"[hog_io] PID={os.getpid()}  threads={args.threads}  "
          f"file={args.mb} MiB  duration={args.seconds}s")
    print(f"[hog_io] Work dir: {base}")

    threads: list[threading.Thread] = []
    for i in range(args.threads):
        path = os.path.join(base, f"hog_{i}.bin")
        t = threading.Thread(target=_io_worker, args=(i, path, file_bytes), daemon=True)
        t.start()
        threads.append(t)

    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass

    _STOP.set()
    print("[hog_io] Stopping threads …")
    for t in threads:
        t.join(timeout=5)

    _cleanup(base)
    print("[hog_io] Done.")


if __name__ == "__main__":
    main()
