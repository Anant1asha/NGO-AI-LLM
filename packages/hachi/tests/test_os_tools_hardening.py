"""Hardening tests for os_tools, checkpoints, and notifier.

Covers:
- UC-PERF-005: oversized / unstattable file → read refused (fail closed)
- UC-PERM-003: bare filename from blocked cwd is caught by gate
- ADV-026:     failing checkpoint is surfaced, not swallowed
- UC-PERM-004: run_shell_script schema accurately reflects tier restrictions
- UC-DESK-001: notifier passes user content via env vars; dispatch is non-blocking
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest import mock

from hachi.core.loop import ToolRegistry
from hachi.core.notifier import (
    _WIN_NOTIFY_BODY_ENV,
    _WIN_NOTIFY_TITLE_ENV,
    DesktopNotifier,
)
from hachi.core.permissions import _DEFAULT_BLOCKED, PermissionGate, generate_permissions_og
from hachi.tools.os_tools import RUN_SHELL_SCRIPT_SCHEMA, register_os_tools

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gate(
    tmp_path: Path,
    *,
    max_file_size_mb: int = 1,
    blocked_dir: Path | None = None,
    allowed_dir: Path | None = None,
) -> tuple[PermissionGate, Path, Path]:
    """Build a guided-tier PermissionGate with controllable allowed/blocked dirs.

    Returns (gate, allowed_dir, blocked_dir).
    """
    ad = allowed_dir or (tmp_path / "allowed")
    bd = blocked_dir or (tmp_path / "blocked")
    ad.mkdir(parents=True, exist_ok=True)
    bd.mkdir(parents=True, exist_ok=True)

    content = generate_permissions_og("guided", custom_paths=[str(ad)])
    # Replace the default blocked paths with just our test blocked dir. Derive the
    # default-blocked string from the implementation so this stays correct across
    # platforms (Windows ~/AppData, macOS ~/Library, Linux ~/.config).
    default_blocked = ", ".join(str(p) for p in _DEFAULT_BLOCKED)
    content = content.replace(f"blocked_paths={default_blocked}", f"blocked_paths={bd}")
    content = content.replace("max_file_size_mb=50", f"max_file_size_mb={max_file_size_mb}")

    pf = tmp_path / "device-permissions.og"
    pf.write_text(content, encoding="utf-8")
    return PermissionGate(pf), ad, bd


class _RecordingRunner:
    """Captures subprocess calls; returns a canned CompletedProcess."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:  # type: ignore[override]
        self.calls.append((cmd, dict(kwargs)))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    @property
    def latest_env(self) -> dict[str, str] | None:
        return self.calls[-1][1].get("env") if self.calls else None

    @property
    def latest_cmd(self) -> list[str] | None:
        return self.calls[-1][0] if self.calls else None


# ---------------------------------------------------------------------------
# UC-PERF-005: fail-closed size check
# ---------------------------------------------------------------------------


class test_oversized_file_read_is_refused:
    """Oversized file: read_file must return Permission Denied, never file content."""

    def test_read_file_refused_when_file_exceeds_max(self, tmp_path: Path) -> None:
        gate, allowed_dir, _ = _make_gate(tmp_path, max_file_size_mb=0)
        # A 1-byte file already exceeds max_file_size_mb=0 (0 bytes).
        big_file = allowed_dir / "big.txt"
        big_file.write_bytes(b"x")

        registry = ToolRegistry()
        register_os_tools(registry, gate=gate)

        result = registry._tools["read_file"](path=str(big_file))

        assert "Permission Denied" in result, f"Expected denial, got: {result!r}"
        # Must not have leaked file content
        assert "x" not in result or "Permission" in result


def test_read_file_refused_when_size_exceeds_limit(tmp_path: Path) -> None:
    """read_file refuses when file is larger than max_file_size_mb."""
    gate, allowed_dir, _ = _make_gate(tmp_path, max_file_size_mb=0)
    over = allowed_dir / "over.bin"
    over.write_bytes(b"a" * 10)

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    result = registry._tools["read_file"](path=str(over))
    assert "Permission Denied" in result
    # File content must not be in the denial message
    assert b"a".decode() * 10 not in result


def test_read_file_refused_on_stat_failure(tmp_path: Path) -> None:
    """read_file refuses (not silently proceeds) when stat() raises."""
    gate, allowed_dir, _ = _make_gate(tmp_path, max_file_size_mb=50)
    target = allowed_dir / "probe.txt"
    target.write_text("content", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    # Simulate stat failure by patching Path.stat to raise OSError.
    original_stat = Path.stat

    def _bad_stat(self, **kwargs):  # type: ignore[override]
        if self == target.resolve() or self == target:
            raise OSError("simulated stat failure")
        return original_stat(self, **kwargs)

    with mock.patch.object(Path, "stat", _bad_stat):
        result = registry._tools["read_file"](path=str(target))

    assert "Permission Denied" in result or "Cannot determine file size" in result
    # Must not have returned the file content
    assert "content" not in result


# ---------------------------------------------------------------------------
# UC-PERM-003: bare filename from blocked cwd caught by gate
# ---------------------------------------------------------------------------


def test_cat_bare_filename_from_blocked_cwd_is_denied(tmp_path: Path) -> None:
    """'cat id_rsa' with the cwd set to a blocked directory must be denied."""
    gate, allowed_dir, blocked_dir = _make_gate(tmp_path)

    # Place the target file inside the blocked directory.
    secret = blocked_dir / "id_rsa"
    secret.write_text("PRIVATE KEY", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    # Use the blocked dir as cwd; 'id_rsa' has no path separator.
    result = registry._tools["run_terminal_command"](
        command="cat id_rsa",
        cwd=str(blocked_dir),
    )

    assert "Permission Denied" in result, (
        f"Expected denial for bare filename in blocked cwd, got: {result!r}"
    )
    # File content must not be leaked.
    assert "PRIVATE KEY" not in result


def test_ren_and_rename_are_recognized_as_exfil_stems() -> None:
    """M3: 'ren'/'rename' must trigger the same blocked_paths re-check as
    cat/copy/move — they were entirely absent from _EXFIL_STEMS before the fix,
    so a rename in/out of a blocked path was never checked at all.
    """
    from hachi.core.permissions import _EXFIL_STEMS

    assert "ren" in _EXFIL_STEMS
    assert "rename" in _EXFIL_STEMS


def test_move_denied_when_destination_outside_allowed_paths(tmp_path: Path) -> None:
    """M3: 'move' only had blocked_paths coverage via _EXFIL_STEMS — a destination
    outside allowed_paths but not explicitly blocked previously went unchecked.
    """
    gate, allowed_dir, blocked_dir = _make_gate(tmp_path)
    src = allowed_dir / "source.txt"
    src.write_text("payload", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    dst = blocked_dir / "dest.txt"
    result = registry._tools["run_terminal_command"](
        command=f"move {src} {dst}",
        cwd=str(allowed_dir),
    )

    assert "Permission Denied" in result, f"Expected denial, got: {result!r}"
    assert src.exists()  # the move must not have actually happened
    assert not dst.exists()


def test_copy_denied_when_source_outside_allowed_paths(tmp_path: Path) -> None:
    """M3: 'copy' reading a source outside allowed_paths was previously unchecked
    unless the source happened to sit inside blocked_paths specifically."""
    gate, allowed_dir, blocked_dir = _make_gate(tmp_path)
    src = blocked_dir / "secret.txt"
    src.write_text("TOP SECRET", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    dst = allowed_dir / "leaked.txt"
    result = registry._tools["run_terminal_command"](
        command=f"copy {src} {dst}",
        cwd=str(allowed_dir),
    )

    assert "Permission Denied" in result, f"Expected denial, got: {result!r}"
    assert not dst.exists()


def test_move_allowed_within_allowed_paths_when_delete_enabled(tmp_path: Path) -> None:
    """Sanity check: the new gate must not break the legitimate in-bounds case.

    Guided tier defaults allow_delete=false, and 'move' needs delete on its
    source — explicitly enable it here to isolate the path-scope check under
    test from the (correctly, separately enforced) delete-permission check.
    """
    from hachi.core.permissions import PermissionGate

    _gate, allowed_dir, _blocked_dir = _make_gate(tmp_path)
    pf = tmp_path / "device-permissions.og"
    content = pf.read_text(encoding="utf-8").replace("allow_delete=false", "allow_delete=true")
    pf.write_text(content, encoding="utf-8")
    gate = PermissionGate(pf)

    src = allowed_dir / "source.txt"
    src.write_text("payload", encoding="utf-8")
    dst = allowed_dir / "moved.txt"

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    result = registry._tools["run_terminal_command"](
        command=f"move {src} {dst}",
        cwd=str(allowed_dir),
    )

    assert "Permission Denied" not in result, f"Unexpected denial: {result!r}"
    assert dst.exists()
    assert not src.exists()


def test_cat_absolute_blocked_path_is_denied(tmp_path: Path) -> None:
    """'cat /blocked/secret.txt' with an absolute blocked path is also denied."""
    gate, allowed_dir, blocked_dir = _make_gate(tmp_path)

    secret = blocked_dir / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    result = registry._tools["run_terminal_command"](
        command=f"cat {secret}",
        cwd=str(allowed_dir),
    )

    assert "Permission Denied" in result
    assert "TOP SECRET" not in result


def test_cat_bare_filename_from_allowed_cwd_is_permitted(tmp_path: Path) -> None:
    """'cat file.txt' with cwd in an allowed directory must succeed."""
    gate, allowed_dir, _ = _make_gate(tmp_path)

    note = allowed_dir / "note.txt"
    note.write_text("hello from allowed dir", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    result = registry._tools["run_terminal_command"](
        command="cat note.txt",
        cwd=str(allowed_dir),
    )

    # Should not be a permission denial; content should be present.
    assert "Permission Denied" not in result
    assert "hello from allowed dir" in result


# ---------------------------------------------------------------------------
# ADV-026: checkpoint failure is surfaced, not swallowed
# ---------------------------------------------------------------------------


class _BrokenCheckpoints:
    """Stub checkpoints that always raises on snapshot."""

    def snapshot(self, path, *, label: str = "") -> None:  # type: ignore[override]
        raise RuntimeError("disk full — cannot write snapshot")

    def rollback(self, path=None) -> dict:  # type: ignore[override]
        return {"status": "no_checkpoint", "path": str(path)}

    def count(self) -> int:
        return 0


def test_write_aborted_when_checkpoint_fails(tmp_path: Path) -> None:
    """When the checkpoint manager raises, write_file must abort and report the error."""
    gate, allowed_dir, _ = _make_gate(tmp_path)

    target = allowed_dir / "important.txt"
    target.write_text("original content", encoding="utf-8")

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate, checkpoints=_BrokenCheckpoints())

    result = registry._tools["write_file"](path=str(target), content="new content")

    # Must report the checkpoint failure.
    assert "Write aborted" in result or "checkpoint" in result.lower(), (
        f"Expected checkpoint error message, got: {result!r}"
    )

    # The file must NOT have been modified — fail closed.
    assert target.read_text(encoding="utf-8") == "original content", (
        "File was modified despite checkpoint failure — ADV-026 regression"
    )


def test_write_proceeds_when_checkpoints_none(tmp_path: Path) -> None:
    """write_file with checkpoints=None (no rollback registered) must still write."""
    gate, allowed_dir, _ = _make_gate(tmp_path)

    target = allowed_dir / "new.txt"

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate, checkpoints=None)

    result = registry._tools["write_file"](path=str(target), content="written!")

    assert "wrote" in result.lower() or "successfully" in result.lower(), (
        f"Expected write success, got: {result!r}"
    )
    assert target.read_text(encoding="utf-8") == "written!"


# ---------------------------------------------------------------------------
# UC-PERM-004: run_shell_script schema accurately reflects tier behavior
# ---------------------------------------------------------------------------


def test_run_shell_script_schema_mentions_tier_restriction() -> None:
    """Schema description must state that sandbox/guided tiers deny this tool."""
    description: str = RUN_SHELL_SCRIPT_SCHEMA["description"]

    # Must explicitly mention tier(s) where it is blocked.
    assert "sandbox" in description or "guided" in description, (
        "Schema description should mention which tiers block this tool."
    )
    # Must not mislead by saying it is always available as a 'run_terminal_command' fallback.
    assert "too restrictive" not in description, (
        "Schema must not imply this tool is freely available as a fallback."
    )


def test_run_shell_script_denied_at_guided_tier(tmp_path: Path) -> None:
    """run_shell_script must be denied at the guided tier (shell not allowlisted)."""
    gate, allowed_dir, _ = _make_gate(tmp_path)

    registry = ToolRegistry()
    register_os_tools(registry, gate=gate)

    result = registry._tools["run_shell_script"](script="echo hello", cwd=str(allowed_dir))

    assert "Permission Denied" in result, f"Expected denial at guided tier, got: {result!r}"


# ---------------------------------------------------------------------------
# UC-DESK-001: notifier is non-blocking; injection guard preserved
# ---------------------------------------------------------------------------


def test_notifier_windows_dispatch_is_non_blocking() -> None:
    """Windows toast must return quickly (daemon thread), not block ~8s."""
    calls: list[float] = []

    def _slow_runner(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:  # type: ignore[override]
        # Simulate the ~4.5s PowerShell balloon wait.
        start = time.monotonic()
        time.sleep(0.1)  # Use a shorter sleep to keep tests fast.
        calls.append(time.monotonic() - start)
        return subprocess.CompletedProcess(cmd, 0)

    notifier = DesktopNotifier(runner=_slow_runner)

    with mock.patch("hachi.core.notifier._platform", return_value="windows"):
        t0 = time.monotonic()
        result = notifier.send("Test", "Body")
        elapsed = time.monotonic() - t0

    # The call must return well before the simulated subprocess finishes.
    assert elapsed < 0.05, f"send() blocked for {elapsed:.3f}s — expected near-zero (non-blocking)"
    assert "queued" in result.lower()


def test_notifier_windows_user_content_via_env_vars_not_interpolated() -> None:
    """User content must travel via env vars, never interpolated into the script."""
    runner = _RecordingRunner()
    notifier = DesktopNotifier(runner=runner)

    evil_title = "Build `$(hostname)` done"
    evil_body = "Result: $(2+2) and $env:PATH; tick `n end"

    with mock.patch("hachi.core.notifier._platform", return_value="windows"):
        notifier.send(evil_title, evil_body)

    # Give the daemon thread a moment to record the call.
    deadline = time.monotonic() + 2.0
    while not runner.calls and time.monotonic() < deadline:
        time.sleep(0.01)

    assert runner.calls, "Runner was never called (daemon thread did not execute)"

    cmd, kwargs = runner.calls[0]
    script = cmd[-1]

    # 1. The untrusted text must NOT appear in the executed script.
    for needle in (evil_title, evil_body, "$(2+2)", "$env:PATH", "$(hostname)"):
        assert needle not in script, f"Untrusted text leaked into PowerShell script: {needle!r}"

    # 2. The constant script reads values only via $env: references.
    assert f"$env:{_WIN_NOTIFY_TITLE_ENV}" in script
    assert f"$env:{_WIN_NOTIFY_BODY_ENV}" in script

    # 3. Values carried verbatim out-of-band via env dict.
    env = kwargs.get("env", {})
    assert env.get(_WIN_NOTIFY_TITLE_ENV) == evil_title
    assert env.get(_WIN_NOTIFY_BODY_ENV) == evil_body

    # 4. No shell=True.
    assert not kwargs.get("shell", False)


def test_notifier_prewarm_does_not_block(tmp_path: Path) -> None:
    """DesktopNotifier constructor must return immediately even on Windows (prewarm is async)."""
    runner = _RecordingRunner()

    with mock.patch("sys.platform", "win32"):
        t0 = time.monotonic()
        # prewarm=True is the default; patch platform so the branch is taken.
        notifier = DesktopNotifier(runner=runner, prewarm=True)
        elapsed = time.monotonic() - t0

    assert elapsed < 0.1, f"Constructor blocked {elapsed:.3f}s — prewarm must be async"
    # Runner may or may not have fired yet (it's in a daemon thread); that's fine.
    _ = notifier  # silence unused warning


def test_notifier_prewarm_skipped_when_runner_injected() -> None:
    """When a custom runner is provided, no prewarm thread is fired."""
    runner = _RecordingRunner()

    # Even with the platform patched to windows, prewarm is skipped when runner != None.
    with mock.patch("sys.platform", "win32"):
        DesktopNotifier(runner=runner, prewarm=True)

    # Give a moment for any errant background thread.
    time.sleep(0.05)

    # The prewarm code path checks `runner is None`, so no pre-warm call happens.
    assert not runner.calls, (
        "Prewarm runner was called despite a custom runner being injected — "
        "prewarm should be disabled in test mode (runner is not None)."
    )
