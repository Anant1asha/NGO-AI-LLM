"""Tests for the always-on daemon installer.

Fully offline: subprocess calls are replaced by a RecordingRunner so we verify
the exact command lists without touching launchctl/systemctl/schtasks.  File I/O
that the installer performs (writing/removing service files) uses tmp_path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from hachi.daemon import (
    _LAUNCHD_LABEL,
    _SYSTEMD_UNIT,
    _TASK_NAME,
    DaemonConfig,
    DaemonInstaller,
    _build_argv,
    _detect_platform,
    build_launchd_plist,
    build_systemd_unit,
    locate_executable,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingRunner:
    """Captures every (cmd, kwargs) call and returns a canned CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self._returncode = returncode
        self._stdout = stdout
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        self.calls.append((cmd, kwargs))
        if self._returncode != 0:
            raise subprocess.CalledProcessError(self._returncode, cmd)
        return subprocess.CompletedProcess(cmd, self._returncode, stdout=self._stdout)

    @property
    def commands(self) -> list[list[str]]:
        """Flat list of command lists, for easy assertion."""
        return [c for c, _ in self.calls]

    def any_with_shell_true(self) -> bool:
        return any(kw.get("shell", False) for _, kw in self.calls)


def _installer(
    runner: RecordingRunner,
    host: str = "127.0.0.1",
    port: int = 8787,
    log_path: Path | None = None,
) -> DaemonInstaller:
    cfg = DaemonConfig(
        host=host,
        port=port,
        log_path=log_path or Path("/tmp/gw.log"),
    )
    return DaemonInstaller(config=cfg, runner=runner)


# ---------------------------------------------------------------------------
# Service-file builders (pure)
# ---------------------------------------------------------------------------


def test_build_launchd_plist_contains_label_and_args(tmp_path: Path):
    log = tmp_path / "gw.log"
    argv = ["/usr/local/bin/hachi", "gateway", "--host", "127.0.0.1", "--port", "8787"]
    plist = build_launchd_plist(argv, log)
    assert _LAUNCHD_LABEL in plist
    assert "/usr/local/bin/hachi" in plist
    assert "<true/>" in plist  # KeepAlive + RunAtLoad
    assert "gw.log" in plist  # log file name present regardless of path separator
    assert "StandardOutPath" in plist
    assert "StandardErrorPath" in plist


def test_build_launchd_plist_xml_structure():
    plist = build_launchd_plist(["/bin/hachi", "gateway"], Path("/log"))
    assert plist.startswith("<?xml")
    assert "<plist" in plist
    assert "<dict>" in plist


def test_build_systemd_unit_contains_exec_and_restart():
    argv = ["/usr/bin/hachi", "gateway", "--host", "0.0.0.0", "--port", "9999", "--runtime"]
    unit = build_systemd_unit(argv)
    assert "ExecStart=" in unit
    assert "/usr/bin/hachi gateway" in unit
    assert "Restart=on-failure" in unit
    assert "WantedBy=default.target" in unit
    assert "[Service]" in unit
    assert "[Install]" in unit


def test_build_systemd_unit_custom_description():
    unit = build_systemd_unit(["/bin/hachi", "gateway"], description="My Hachi")
    assert "Description=My Hachi" in unit


# ---------------------------------------------------------------------------
# locate_executable
# ---------------------------------------------------------------------------


def test_locate_executable_uses_which_when_available():
    with mock.patch("shutil.which", return_value="/usr/local/bin/hachi"):
        exe = locate_executable()
    assert exe.name == "hachi"


def test_locate_executable_falls_back_to_sys_executable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    # sys.executable exists on all platforms where tests run
    exe = locate_executable()
    assert exe.exists()


# ---------------------------------------------------------------------------
# _build_argv — security guardrail: never shell=True in produced commands
# ---------------------------------------------------------------------------


def test_build_argv_no_shell():
    cfg = DaemonConfig(host="127.0.0.1", port=8787, log_path=Path("/tmp/gw.log"))
    with mock.patch("shutil.which", return_value="/usr/local/bin/hachi"):
        argv = _build_argv(cfg)
    # Must be a plain list (not a shell string)
    assert isinstance(argv, list)
    assert all(isinstance(a, str) for a in argv)
    assert "--host" in argv
    assert "--port" in argv
    assert "--runtime" in argv


def test_build_argv_python_module_fallback():
    """When locate_executable returns a python interpreter, use -m hachi."""
    with mock.patch("shutil.which", return_value=None):
        with mock.patch("pathlib.Path.exists", return_value=True):
            cfg = DaemonConfig(log_path=Path(sys.executable).parent / "gw.log")
            argv = _build_argv(cfg)
    # argv[0] should be sys.executable (or resolved), argv[1] == "-m", argv[2] == "hachi"
    assert argv[1] == "-m"
    assert argv[2] == "hachi"
    assert "gateway" in argv


# ---------------------------------------------------------------------------
# macOS (launchd) — mocked subprocess + file I/O
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="launchd path irrelevant on Windows")
def test_install_launchd_writes_plist_and_calls_load(tmp_path: Path):
    runner = RecordingRunner()
    installer = _installer(runner, log_path=tmp_path / "gw.log")

    plist_path = tmp_path / f"{_LAUNCHD_LABEL}.plist"
    with (
        mock.patch("hachi.daemon._launchd_plist_path", return_value=plist_path),
        mock.patch("shutil.which", return_value="/usr/local/bin/hachi"),
        mock.patch("hachi.daemon._detect_platform", return_value="macos"),
    ):
        msg = installer.install()

    assert plist_path.exists()
    content = plist_path.read_text()
    assert _LAUNCHD_LABEL in content
    # launchctl load must have been called
    load_cmds = [c for c in runner.commands if "load" in c]
    assert any(str(plist_path) in c for c in load_cmds)
    assert "Installed launchd agent" in msg
    assert not runner.any_with_shell_true()


@pytest.mark.skipif(sys.platform == "win32", reason="launchd path irrelevant on Windows")
def test_uninstall_launchd_removes_plist(tmp_path: Path):
    plist_path = tmp_path / f"{_LAUNCHD_LABEL}.plist"
    plist_path.write_text("dummy", encoding="utf-8")
    runner = RecordingRunner()
    installer = _installer(runner, log_path=tmp_path / "gw.log")

    with (
        mock.patch("hachi.daemon._launchd_plist_path", return_value=plist_path),
        mock.patch("hachi.daemon._detect_platform", return_value="macos"),
    ):
        msg = installer.uninstall()

    assert not plist_path.exists()
    assert "Removed launchd agent" in msg
    assert not runner.any_with_shell_true()


# ---------------------------------------------------------------------------
# Linux (systemd --user)
# ---------------------------------------------------------------------------


def test_install_systemd_writes_unit_and_enables(tmp_path: Path):
    runner = RecordingRunner()
    unit_path = tmp_path / "hachi.service"
    installer = _installer(runner, log_path=tmp_path / "gw.log")

    with (
        mock.patch("hachi.daemon._systemd_unit_path", return_value=unit_path),
        mock.patch("shutil.which", return_value="/usr/local/bin/hachi"),
        mock.patch("hachi.daemon._detect_platform", return_value="linux"),
    ):
        msg = installer.install()

    assert unit_path.exists()
    content = unit_path.read_text()
    assert "ExecStart=" in content
    # systemctl enable --now must have been called
    enable_cmds = [c for c in runner.commands if "enable" in c]
    assert enable_cmds
    assert "Installed systemd user service" in msg
    assert not runner.any_with_shell_true()


def test_uninstall_systemd_removes_unit(tmp_path: Path):
    unit_path = tmp_path / "hachi.service"
    unit_path.write_text("[Service]\nExecStart=hachi\n", encoding="utf-8")
    runner = RecordingRunner()
    installer = _installer(runner, log_path=tmp_path / "gw.log")

    with (
        mock.patch("hachi.daemon._systemd_unit_path", return_value=unit_path),
        mock.patch("hachi.daemon._detect_platform", return_value="linux"),
    ):
        msg = installer.uninstall()

    assert not unit_path.exists()
    assert "Removed systemd user service" in msg
    assert not runner.any_with_shell_true()


def test_systemd_start_stop_use_correct_commands():
    runner = RecordingRunner()
    installer = _installer(runner)

    with mock.patch("hachi.daemon._detect_platform", return_value="linux"):
        start_msg = installer.start()
        stop_msg = installer.stop()

    start_cmds = [c for c in runner.commands if "start" in c]
    stop_cmds = [c for c in runner.commands if "stop" in c]
    assert any(_SYSTEMD_UNIT in c for c in start_cmds)
    assert any(_SYSTEMD_UNIT in c for c in stop_cmds)
    assert "--user" in start_cmds[0]
    assert "Started systemd unit" in start_msg
    assert "Stopped systemd unit" in stop_msg


def test_systemd_status_returns_state():
    runner = RecordingRunner(stdout="active\n")
    installer = _installer(runner)

    with mock.patch("hachi.daemon._detect_platform", return_value="linux"):
        msg = installer.status()

    assert "systemd" in msg
    assert "active" in msg


# ---------------------------------------------------------------------------
# Windows (Task Scheduler)
# ---------------------------------------------------------------------------


def test_install_windows_calls_schtasks_create():
    runner = RecordingRunner()
    installer = _installer(runner)

    with (
        mock.patch("shutil.which", return_value=r"C:\Python\Scripts\hachi.exe"),
        mock.patch("hachi.daemon._detect_platform", return_value="windows"),
    ):
        msg = installer.install()

    create_cmds = [c for c in runner.commands if "schtasks" in c[0] and "/create" in c]
    assert create_cmds
    cmd = create_cmds[0]
    assert "/tn" in cmd
    assert _TASK_NAME in cmd
    # New XML-based install uses /xml <tmpfile> /f instead of /sc ONLOGON
    assert "/xml" in cmd
    assert "/f" in cmd
    assert "Installed Task Scheduler task" in msg
    assert not runner.any_with_shell_true()


def test_uninstall_windows_calls_schtasks_delete():
    runner = RecordingRunner()
    installer = _installer(runner)

    with mock.patch("hachi.daemon._detect_platform", return_value="windows"):
        msg = installer.uninstall()

    delete_cmds = [c for c in runner.commands if "schtasks" in c[0] and "/delete" in c]
    assert delete_cmds
    assert _TASK_NAME in delete_cmds[0]
    assert "Removed Task Scheduler task" in msg
    assert not runner.any_with_shell_true()


def test_windows_start_stop_commands():
    runner = RecordingRunner()
    installer = _installer(runner)

    with mock.patch("hachi.daemon._detect_platform", return_value="windows"):
        installer.start()
        installer.stop()

    run_cmds = [c for c in runner.commands if "schtasks" in c[0] and "/run" in c]
    end_cmds = [c for c in runner.commands if "schtasks" in c[0] and "/end" in c]
    assert run_cmds and _TASK_NAME in run_cmds[0]
    assert end_cmds and _TASK_NAME in end_cmds[0]


# ---------------------------------------------------------------------------
# Security: no shell=True anywhere
# ---------------------------------------------------------------------------


def test_no_shell_true_on_any_platform(tmp_path: Path):
    """Critical security check: shell=True must never be passed."""
    for platform in ("macos", "linux", "windows"):
        runner = RecordingRunner()
        plist = tmp_path / "p.plist"
        unit = tmp_path / "u.service"
        installer = _installer(runner, log_path=tmp_path / "gw.log")

        with (
            mock.patch("hachi.daemon._launchd_plist_path", return_value=plist),
            mock.patch("hachi.daemon._systemd_unit_path", return_value=unit),
            mock.patch("shutil.which", return_value="/usr/local/bin/hachi"),
            mock.patch("hachi.daemon._detect_platform", return_value=platform),
        ):
            try:
                installer.install()
            except Exception:
                pass  # File not found / ctl failure — we only care about shell usage

        assert not runner.any_with_shell_true(), f"shell=True detected on platform={platform}"


# ---------------------------------------------------------------------------
# _detect_platform
# ---------------------------------------------------------------------------


def test_detect_platform_darwin():
    with mock.patch.object(sys, "platform", "darwin"):
        assert _detect_platform() == "macos"


def test_detect_platform_linux():
    with mock.patch.object(sys, "platform", "linux"):
        assert _detect_platform() == "linux"


def test_detect_platform_windows():
    with mock.patch.object(sys, "platform", "win32"):
        assert _detect_platform() == "windows"


def test_detect_platform_unknown_falls_back_to_linux():
    with mock.patch.object(sys, "platform", "freebsd12"):
        assert _detect_platform() == "linux"
