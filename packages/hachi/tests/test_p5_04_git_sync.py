"""Tests for P5-04: per-device journal shard naming (git-sync pattern)."""
from __future__ import annotations

import socket
from pathlib import Path

from hachi.core.paths import HachiPaths


def _make_paths(tmp_path: Path) -> HachiPaths:
    """Return a HachiPaths instance rooted in a temp directory."""
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def test_journal_shard_default_uses_hostname(tmp_path: Path) -> None:
    """journal_shard_path() with no args uses socket.gethostname()."""
    paths = _make_paths(tmp_path)
    result = paths.journal_shard_path()
    hostname = socket.gethostname()
    # The safe slug may differ from the raw hostname (special chars replaced).
    import re
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", hostname)[:32]
    assert result.name == f"journal-{safe}.og"
    assert isinstance(result, Path)


def test_journal_shard_explicit_device_id(tmp_path: Path) -> None:
    """journal_shard_path(device_id='my-laptop') embeds the id in the filename."""
    paths = _make_paths(tmp_path)
    result = paths.journal_shard_path(device_id="my-laptop")
    assert "my-laptop" in result.name
    assert result.name == "journal-my-laptop.og"


def test_journal_shard_sanitises_special_chars(tmp_path: Path) -> None:
    """Special characters in device_id are replaced with hyphens."""
    paths = _make_paths(tmp_path)
    result = paths.journal_shard_path(device_id="my.server.local")
    # The stem (without the .og extension) must not contain dots.
    stem = result.stem  # e.g. "journal-my-server-local"
    assert "." not in stem, f"stem '{stem}' still contains a dot"
    assert result.name == "journal-my-server-local.og"


def test_journal_shard_inside_memory_dir(tmp_path: Path) -> None:
    """The returned path is inside memory_dir."""
    paths = _make_paths(tmp_path)
    result = paths.journal_shard_path(device_id="testbox")
    assert result.parent == paths.memory_dir
