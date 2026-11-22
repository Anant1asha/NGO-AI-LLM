"""Cross-platform advisory file lock for safe concurrent file access.

Provides a single context manager :func:`file_lock` that serializes access to a
shared file across **multiple processes** (not just threads).

Platform strategy
-----------------
- **Windows** — ``msvcrt.locking`` on a companion ``.lock`` file adjacent to the
  target.  ``msvcrt.locking`` is a mandatory (byte-range) lock;  it blocks any
  other process that tries to lock the same byte range simultaneously.
- **POSIX** — ``fcntl.flock(LOCK_EX)`` on the same companion file.  ``flock`` is
  advisory but universally honoured across CPython processes.

The lock file is created automatically and is never deleted (deletion under a lock
is a TOCTOU race on Windows); its presence on disk is harmless.

Usage::

    with file_lock(Path("/var/data/schedules.json")):
        data = path.read_text()
        path.write_text(mutate(data))

The returned context manager is **not** reentrant on Windows (``msvcrt.locking``
does not support nested locks from the *same* process on the same byte range) and
is **reentrant** on POSIX (``flock`` is per file-descriptor, so a second
``flock(LOCK_EX)`` from the same process on a *different* fd deadlocks — but this
module always opens a fresh fd per ``__enter__``, so nested calls deadlock).
In practice callers should not nest :func:`file_lock` on the same path.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def _lock_path(path: Path) -> Path:
    """Return the companion lock-file path for *path*."""
    return path.with_suffix(path.suffix + ".lock")


if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def file_lock(path: Path) -> Generator[None, None, None]:
        """Acquire an exclusive advisory lock on *path* for the duration of the block.

        Args:
            path: The file whose access you want to serialize.  A companion
                  ``<path>.lock`` file is created/used as the lock target.

        Yields:
            None — the block runs while the lock is held.
        """
        lock_file = _lock_path(path)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
        try:
            # Lock exactly 1 byte at the current position (offset 0).
            # msvcrt.locking blocks until the lock is acquired (LK_LOCK retries
            # for ~10 s then raises OSError; use LK_NBLCK if you want a quick
            # fail).  LK_LOCK is the blocking / retrying variant.
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                # Seek back to byte 0 before unlocking (locking is positional).
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)

else:
    import fcntl

    @contextmanager
    def file_lock(path: Path) -> Generator[None, None, None]:
        """Acquire an exclusive advisory lock on *path* for the duration of the block.

        Args:
            path: The file whose access you want to serialize.  A companion
                  ``<path>.lock`` file is created/used as the lock target.

        Yields:
            None — the block runs while the lock is held.
        """
        lock_file = _lock_path(path)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_file, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
