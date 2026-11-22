"""Tests for file checkpoints / rollback (agent edit undo)."""

from __future__ import annotations

from pathlib import Path

from hachi.core.checkpoints import CheckpointManager
from hachi.core.loop import ToolRegistry
from hachi.tools.os_tools import register_os_tools


def _mgr(tmp_path: Path) -> CheckpointManager:
    return CheckpointManager(tmp_path / "_ckpt")


def test_rollback_restores_overwritten_file(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    target.write_text("original", encoding="utf-8")

    mgr = _mgr(tmp_path)
    mgr.snapshot(target, label="edit")
    target.write_text("modified by agent", encoding="utf-8")

    result = mgr.rollback()
    assert result["status"] == "restored"
    assert target.read_text(encoding="utf-8") == "original"


def test_rollback_removes_newly_created_file(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    mgr = _mgr(tmp_path)
    mgr.snapshot(target)  # file does not exist yet
    target.write_text("agent created this", encoding="utf-8")

    result = mgr.rollback()
    assert result["status"] == "removed"
    assert not target.exists()


def test_rollback_is_lifo_and_consumes(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    a.write_text("v1", encoding="utf-8")
    mgr = _mgr(tmp_path)

    mgr.snapshot(a)
    a.write_text("v2", encoding="utf-8")
    mgr.snapshot(a)
    a.write_text("v3", encoding="utf-8")

    assert mgr.count() == 2
    mgr.rollback()  # undo v3 -> v2
    assert a.read_text(encoding="utf-8") == "v2"
    mgr.rollback()  # undo v2 -> v1
    assert a.read_text(encoding="utf-8") == "v1"
    assert mgr.count() == 0
    assert mgr.rollback()["status"] == "no_checkpoint"


class _AllowGate:
    max_file_size_bytes = 10_000_000

    def check_path(self, _path: str, _mode: str):
        return type("R", (), {"allowed": True, "reason": ""})()


def test_write_file_tool_snapshots_and_rollback_tool_restores(tmp_path: Path) -> None:
    target = tmp_path / "managed.txt"
    target.write_text("before", encoding="utf-8")

    registry = ToolRegistry()
    mgr = _mgr(tmp_path)
    register_os_tools(registry, gate=_AllowGate(), checkpoints=mgr)

    registry._tools["write_file"](path=str(target), content="after (agent)")
    assert target.read_text(encoding="utf-8") == "after (agent)"

    out = registry._tools["rollback_changes"]()
    assert "Restored" in out
    assert target.read_text(encoding="utf-8") == "before"
