"""Cross-platform advisory file locks for run checkpoints and vault transactions.

POSIX uses fcntl.flock. Windows uses msvcrt.locking on the first byte; its
blocking mode gives up after ten seconds, so a bounded retry loop is used.
"""
from __future__ import annotations

import os
import time

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_WINDOWS_WAIT_SECONDS = 120
_WINDOWS_RETRY_SECONDS = 0.2


def lock(handle):
    if os.name == "nt":
        deadline = time.monotonic() + _WINDOWS_WAIT_SECONDS
        while True:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(_WINDOWS_RETRY_SECONDS)
    fcntl.flock(handle, fcntl.LOCK_EX)


def unlock(handle):
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle, fcntl.LOCK_UN)