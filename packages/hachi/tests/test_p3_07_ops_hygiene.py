"""P3-07: Ops hygiene — log rotation, thread join on shutdown, Chroma close.

Tests:
  1. setup_rotating_log() attaches a RotatingFileHandler and creates the file.
  2. ScheduleRunner.stop() joins its thread (thread is dead after stop).
  3. MemoryVault.close() completes without raising even on repeated calls.
  4. _build_windows_task_xml() generates valid XML with RestartOnFailure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1. Rotating log
# ---------------------------------------------------------------------------


def test_setup_rotating_log_creates_handler(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon.log"
    from hachi.daemon import setup_rotating_log

    root = logging.getLogger()
    original_handlers = list(root.handlers)
    try:
        setup_rotating_log(log_path, max_bytes=1024, backup_count=2)
        file_handlers = [
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert file_handlers, "RotatingFileHandler not attached to root logger"
        assert any(Path(h.baseFilename) == log_path for h in file_handlers)
    finally:
        # Remove any handlers we added so we don't pollute other tests.
        for h in list(root.handlers):
            if h not in original_handlers:
                root.removeHandler(h)
                h.close()


def test_setup_rotating_log_idempotent(tmp_path: Path) -> None:
    log_path = tmp_path / "daemon2.log"
    from hachi.daemon import setup_rotating_log

    root = logging.getLogger()
    before = len(root.handlers)
    try:
        setup_rotating_log(log_path, max_bytes=1024)
        setup_rotating_log(log_path, max_bytes=1024)  # second call — no duplicate
        file_handlers = [
            h for h in root.handlers[before:]
            if isinstance(h, logging.handlers.RotatingFileHandler)
            and Path(h.baseFilename) == log_path
        ]
        assert len(file_handlers) <= 1, "Duplicate RotatingFileHandler attached"
    finally:
        for h in list(root.handlers[before:]):
            root.removeHandler(h)
            h.close()


# ---------------------------------------------------------------------------
# 2. ScheduleRunner thread join
# ---------------------------------------------------------------------------


def test_schedule_runner_stop_joins_thread() -> None:
    from hachi.jobs.scheduler import Scheduler, ScheduleRunner

    sched = Scheduler.__new__(Scheduler)
    sched._schedules = {}  # type: ignore[attr-defined]

    runner = ScheduleRunner(sched, fire=lambda _s: None, tick_interval_seconds=60)
    runner.start()
    assert runner._thread.is_alive()
    runner.stop(timeout=3.0)
    # After stop() the thread must be dead (not merely signalled).
    assert not runner._thread.is_alive(), (
        "ScheduleRunner thread still alive after stop() — join() not called"
    )


# ---------------------------------------------------------------------------
# 3. MemoryVault.close()
# ---------------------------------------------------------------------------


def test_memory_vault_close_idempotent() -> None:
    """close() must not raise and must be callable multiple times."""
    from hachi.core.memory_vault import MemoryVault

    vault = MagicMock(spec=MemoryVault)
    vault.close = MemoryVault.close.__get__(vault, type(vault))  # type: ignore[assignment]
    # Patch out the chroma client
    vault.client = MagicMock()
    vault.collection = MagicMock()
    vault.user_collection = MagicMock()
    vault.agent_profile = MagicMock()
    vault.delegation_collection = MagicMock()
    vault.quarantine_collection = MagicMock()
    # HIGH-021: close() acquires the re-entrant vault lock before nulling refs.
    import threading

    vault._vault_lock = threading.RLock()
    # HIGH-021/H12: close() guards re-entry with a _closed flag (set in __init__).
    vault._closed = False

    # Should not raise.
    vault.close()
    vault.close()  # Idempotent second call.


# ---------------------------------------------------------------------------
# 4. Windows Task XML
# ---------------------------------------------------------------------------


def test_windows_task_xml_has_restart_on_failure(tmp_path: Path) -> None:
    from hachi.daemon import _build_windows_task_xml

    argv = ["C:\\Python313\\python.exe", "-m", "hachi", "gateway", "--runtime"]
    xml = _build_windows_task_xml(argv, "Hachi Gateway", tmp_path / "gateway.log")

    assert "RestartOnFailure" in xml
    assert "PT30S" in xml  # 30-second restart interval
    assert "LogonTrigger" in xml
    assert "hachi" in xml.lower()


import logging.handlers  # noqa: E402 — needed for isinstance checks above
