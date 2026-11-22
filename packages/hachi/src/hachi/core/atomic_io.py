"""Shared atomic JSON write + corrupt-file quarantine helpers.

Several JSON-backed state stores (``secret_store.py``'s encrypted-file/metadata
stores, ``onboarding.py``'s ``onboarding_state.json``, the OG engine's
``skill_usage.json``) each grew their own hand-rolled "write the file" logic
that used a plain ``Path.write_text`` — not atomic, so a crash/kill mid-write
(or a full disk) can leave a truncated/corrupt JSON file on disk. Combined with
a read path that swallows any parse error and returns an empty/default value,
this is a self-wipe hazard: corrupt read → empty in-memory state → next write
persists the empty state, permanently destroying whatever was on disk before
the crash.

This module factors out the pattern that :class:`hachi.jobs.scheduler.ScheduleStore`
and :class:`hachi.core.checkpoints.CheckpointManager` already implemented
correctly — write to a sibling temp file in the *same* directory, then
:func:`os.replace` onto the final path. ``os.replace`` is atomic on both POSIX
and Windows (same-volume), so a crash mid-write either leaves the old file
completely intact or the new file completely written — never a half-written
file.

Use :func:`atomic_write_json` for the write side and :func:`quarantine_corrupt_file`
on the read side, immediately when a parse error is detected and *before* any
subsequent write can happen — this converts a silent data-loss cascade into a
recoverable, inspectable ``<path>.corrupt-<timestamp>`` sibling file.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def atomic_write_json(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    """Write *payload* as JSON to *path* atomically.

    Writes to a temp file created alongside *path* (same directory, so
    ``os.replace`` stays on one filesystem/volume) and then atomically renames
    it onto *path*. A crash/kill mid-write leaves the original file untouched;
    it never observes a partially-written or empty file.

    Args:
        path:    Destination file path. Parent directory is created if missing.
        payload: JSON-serializable value to write.
        indent:  Passed through to :func:`json.dumps` (``None`` for compact output).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=indent, default=str)

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of the temp file on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def quarantine_corrupt_file(path: Path) -> Path | None:
    """Rename an unparseable state file out of the way so it is never clobbered.

    Call this from a read path's ``except`` branch (before returning an empty
    or default value) so the corrupt file is preserved for inspection/recovery
    instead of being silently overwritten by the next write with fresh/empty
    state.

    Returns the quarantine path, or ``None`` if *path* did not exist (nothing
    to quarantine).
    """
    if not path.exists():
        return None
    quarantine_path = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
    try:
        os.replace(path, quarantine_path)
    except OSError:
        logger.warning("Failed to quarantine corrupt state file %s", path, exc_info=True)
        return None
    logger.warning(
        "State file %s was unparseable — quarantined to %s so the next write doesn't "
        "silently overwrite it with empty/default state.",
        path,
        quarantine_path,
    )
    return quarantine_path
