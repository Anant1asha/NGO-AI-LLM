"""CLI integration tests for ``hachi daemon`` commands.

All subprocess calls are patched so tests run fully offline.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_installer_mock(return_value: str = "OK") -> MagicMock:
    """Return a MagicMock DaemonInstaller whose action methods return *return_value*."""
    inst = MagicMock()
    inst.install.return_value = return_value
    inst.uninstall.return_value = return_value
    inst.start.return_value = return_value
    inst.stop.return_value = return_value
    inst.status.return_value = return_value
    return inst


def _patch_installer(mock_installer: MagicMock):
    """Patch _make_installer in cli.main to return *mock_installer*."""
    return patch("hachi.cli.commands.daemon._make_installer", return_value=mock_installer)


# ---------------------------------------------------------------------------
# daemon install
# ---------------------------------------------------------------------------


def test_daemon_install_success() -> None:
    inst = _make_installer_mock("Installed launchd agent. plist: /tmp/x.plist")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "install"])
    assert result.exit_code == 0
    assert "Installed" in result.output
    inst.install.assert_called_once()


def test_daemon_install_custom_host_port() -> None:
    inst = _make_installer_mock("Installed")
    with patch("hachi.cli.commands.daemon._make_installer", return_value=inst) as mock_make:
        result = runner.invoke(app, ["daemon", "install", "--host", "0.0.0.0", "--port", "9000"])
    assert result.exit_code == 0
    mock_make.assert_called_once_with("0.0.0.0", 9000)


def test_daemon_install_error_exits_nonzero() -> None:
    inst = _make_installer_mock()
    inst.install.side_effect = RuntimeError("schtasks not found")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "install"])
    assert result.exit_code != 0
    assert "failed" in result.output.lower() or "schtasks" in result.output


# ---------------------------------------------------------------------------
# daemon uninstall
# ---------------------------------------------------------------------------


def test_daemon_uninstall_success() -> None:
    inst = _make_installer_mock("Removed launchd agent.")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "uninstall"])
    assert result.exit_code == 0
    assert "Removed" in result.output
    inst.uninstall.assert_called_once()


def test_daemon_uninstall_error_exits_nonzero() -> None:
    inst = _make_installer_mock()
    inst.uninstall.side_effect = subprocess.CalledProcessError(1, ["schtasks"])
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "uninstall"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# daemon start
# ---------------------------------------------------------------------------


def test_daemon_start_success() -> None:
    inst = _make_installer_mock("Started systemd unit 'hachi'.")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "start"])
    assert result.exit_code == 0
    assert "Started" in result.output
    inst.start.assert_called_once()


def test_daemon_start_error() -> None:
    inst = _make_installer_mock()
    inst.start.side_effect = RuntimeError("unit not installed")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "start"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# daemon stop
# ---------------------------------------------------------------------------


def test_daemon_stop_success() -> None:
    inst = _make_installer_mock("Stopped systemd unit 'hachi'.")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "stop"])
    assert result.exit_code == 0
    assert "Stopped" in result.output
    inst.stop.assert_called_once()


# ---------------------------------------------------------------------------
# daemon status
# ---------------------------------------------------------------------------


def test_daemon_status_running() -> None:
    inst = _make_installer_mock("systemd: active")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "active" in result.output
    inst.status.assert_called_once()


def test_daemon_status_not_installed() -> None:
    inst = _make_installer_mock("not installed (exit 1)")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code == 0
    assert "not installed" in result.output


def test_daemon_status_error_exits_nonzero() -> None:
    inst = _make_installer_mock()
    inst.status.side_effect = RuntimeError("launchctl unavailable")
    with _patch_installer(inst):
        result = runner.invoke(app, ["daemon", "status"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Help / no-args
# ---------------------------------------------------------------------------


def test_daemon_no_args_shows_help() -> None:
    result = runner.invoke(app, ["daemon"])
    # no_args_is_help=True shows the help text (exit 0 or 2 depending on Typer version)
    assert result.exit_code in (0, 2)
    assert "install" in result.output
    assert "uninstall" in result.output
    assert "start" in result.output
    assert "stop" in result.output
    assert "status" in result.output
