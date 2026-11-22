"""Always-on daemon installer for the Hachi gateway.

Installs the gateway as a persistent background service that auto-starts on login:

- **macOS**   → launchd user agent
  ``~/Library/LaunchAgents/ai.hachi.gateway.plist``
- **Linux**   → systemd user service
  ``~/.config/systemd/user/hachi.service``
- **Windows** → Task Scheduler (ONLOGON trigger, current user, no ``shell=True``)

The ``runner`` parameter on :class:`DaemonInstaller` is injectable so tests run
fully offline — no actual launchctl/systemctl/schtasks calls are made.

Auth (UC-AUTH-002):
    The daemon always authenticates its gateway surface.  :meth:`DaemonInstaller.install`
    calls :func:`_ensure_daemon_token` before writing the service unit — this generates
    and persists a bearer token to ``~/.hachi/gateway-token`` (0600) if one does
    not already exist.  The spawned ``hachi gateway`` process resolves the same
    file at startup via :func:`_resolve_gateway_auth_token`.
"""

from __future__ import annotations

import logging
import logging.handlers
import secrets
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Platform constants
# ---------------------------------------------------------------------------

_LAUNCHD_LABEL = "ai.hachi.gateway"
_SYSTEMD_UNIT = "hachi"
_TASK_NAME = "Hachi Gateway"

# Type alias: same signature as subprocess.run for the injectable runner.
Runner = Any  # Callable[[list[str], ...], subprocess.CompletedProcess]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class DaemonConfig:
    """Runtime parameters for the gateway daemon.

    Attributes:
        host: Bind address for the gateway HTTP server.
        port: TCP port for the gateway HTTP server.
        log_path: Path where the daemon writes stdout/stderr (resolved at runtime).
    """

    host: str = "127.0.0.1"
    port: int = 8787
    log_path: Path = field(default_factory=lambda: _default_log_path())


def _default_log_path() -> Path:
    """Return the platform-appropriate log path for the gateway daemon."""
    from hachi.core.paths import get_hachi_paths

    return Path(get_hachi_paths().state_dir) / "gateway.log"


def _default_token_path() -> Path:
    """Return the canonical path of the persistent gateway bearer token."""
    return Path.home() / ".hachi" / "gateway-token"


def _ensure_daemon_token() -> str:
    """Return the existing gateway token or generate and persist a new one.

    This is called by :meth:`DaemonInstaller.install` so the spawned daemon
    process always starts with an authenticated gateway.  The token file is
    created with 0o600 permissions (owner-read-write only) on POSIX systems.

    Returns:
        The bearer token string the daemon gateway will require.
    """
    token_path = _default_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)

    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = secrets.token_urlsafe(32)
    token_path.write_text(token + "\n", encoding="utf-8")
    try:
        token_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except NotImplementedError:
        pass  # Windows — chmod is a no-op; OS-level ACLs protect the home dir.
    return token


def setup_rotating_log(
    log_path: Path,
    *,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB per file
    backup_count: int = 3,
    level: int = logging.INFO,
) -> None:
    """Attach a RotatingFileHandler to the root logger for the daemon process.

    Keeps up to ``backup_count`` rotated archives beside the live log file so
    the gateway log never grows unbounded.  Call this once at daemon startup
    (before any log output).

    Args:
        log_path: Destination log file (created if absent; parent must exist).
        max_bytes: Maximum size of a single log file before rotation.
        backup_count: Number of rotated archives to keep.
        level: Minimum log level to capture.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))
    root = logging.getLogger()
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)


# ---------------------------------------------------------------------------
# Executable discovery
# ---------------------------------------------------------------------------


def locate_executable() -> Path:
    """Return the absolute path of the ``hachi`` CLI entry point.

    Resolution order:
    1. ``shutil.which("hachi")`` — preferred; works for ``pip install`` / ``uv tool install``.
    2. ``sys.executable -m hachi`` — fallback for editable/development installs.

    Raises:
        RuntimeError: When neither resolution succeeds.
    """
    which = shutil.which("hachi")
    if which:
        return Path(which).resolve()

    # Fallback: invoke as a Python module.  We return sys.executable so callers
    # can build ``[sys.executable, "-m", "hachi", ...]`` command lists.
    if Path(sys.executable).exists():
        return Path(sys.executable).resolve()

    raise RuntimeError(
        "Cannot find the 'hachi' executable. "
        "Make sure it is installed and available on PATH, "
        "or activate the virtual environment first."
    )


def _build_argv(config: DaemonConfig) -> list[str]:
    """Build the gateway command-line arguments list (no shell=True)."""
    exe = locate_executable()
    # If shutil.which found a direct entry point, call it directly.
    # If we fell back to sys.executable, invoke as a module.
    if exe.name in ("python", "python3", "python.exe", "python3.exe"):
        cmd = [str(exe), "-m", "hachi"]
    else:
        cmd = [str(exe)]
    return cmd + [
        "gateway",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--runtime",
    ]


# ---------------------------------------------------------------------------
# Service-file builders (pure — no I/O, unit-testable)
# ---------------------------------------------------------------------------


def _build_windows_task_xml(argv: list[str], task_name: str, log_path: Path) -> str:
    """Build a Windows Task Scheduler XML definition with restart-on-failure.

    Uses an ONLOGON trigger and a ``RestartOnFailure`` element (30 s delay,
    3 attempts) — equivalent to systemd's ``Restart=on-failure RestartSec=30``.
    The XML format is consumed by ``schtasks /create /xml``.

    Args:
        argv: Full command list (program + arguments).
        task_name: Display name shown in Task Scheduler.
        log_path: Redirects stdout/stderr in the command via ``cmd /c``.

    Returns:
        UTF-8 XML string suitable for a temporary file.
    """
    import xml.sax.saxutils as saxutils

    program = saxutils.escape(argv[0])
    args_str = saxutils.escape(" ".join(argv[1:]))
    log_escaped = saxutils.escape(str(log_path))
    name_escaped = saxutils.escape(task_name)

    return f"""\
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{name_escaped} — Hachi always-on agent gateway</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT30S</Interval>
      <Count>3</Count>
    </RestartOnFailure>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{program}</Command>
      <Arguments>{args_str} &gt;&gt; "{log_escaped}" 2&gt;&amp;1</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def build_launchd_plist(argv: list[str], log_path: Path) -> str:
    """Build a launchd plist XML string for the given gateway command.

    Args:
        argv: Full command as a list (no shell).
        log_path: Path for stdout/stderr log file.

    Returns:
        XML plist content as a string.
    """
    args_xml = "\n".join(f"        <string>{a}</string>" for a in argv)
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
{args_xml}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>
</dict>
</plist>
"""


def build_systemd_unit(argv: list[str], description: str = "Hachi Gateway") -> str:
    """Build a systemd user-service unit file for the given gateway command.

    Args:
        argv: Full command as a list (written as space-joined ExecStart).
        description: Free-text description for the unit.

    Returns:
        Systemd unit file content as a string.
    """
    exec_start = " ".join(argv)
    return f"""\
[Unit]
Description={description}
After=network.target

[Service]
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


# ---------------------------------------------------------------------------
# Platform-specific path helpers
# ---------------------------------------------------------------------------


def _launchd_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHD_LABEL}.plist"


def _systemd_unit_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / f"{_SYSTEMD_UNIT}.service"


# ---------------------------------------------------------------------------
# DaemonInstaller
# ---------------------------------------------------------------------------


class DaemonInstaller:
    """Platform-aware daemon manager for the Hachi gateway.

    Supports macOS (launchd), Linux (systemd --user), and Windows (schtasks).
    Inject ``runner`` to replace subprocess calls in tests.

    Args:
        config: Gateway host/port/log configuration.
        runner: Callable with the same signature as :func:`subprocess.run`.
            Defaults to :func:`subprocess.run`.
    """

    def __init__(
        self,
        config: DaemonConfig | None = None,
        runner: Runner = None,
    ) -> None:
        self._config = config or DaemonConfig()
        self._runner = runner or subprocess.run

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self) -> str:
        """Install and start the gateway daemon.  Returns a human-readable summary.

        UC-AUTH-002: Ensures a bearer token exists (generating + persisting one if
        absent) before writing the service unit.  The spawned ``hachi gateway``
        process resolves the same ``~/.hachi/gateway-token`` file at startup,
        so the daemon surface is always authenticated without encoding the token in
        the service-unit definition (which would be world-readable on some platforms).
        """
        _ensure_daemon_token()
        platform = _detect_platform()
        if platform == "macos":
            return self._install_launchd()
        if platform == "linux":
            return self._install_systemd()
        if platform == "windows":
            return self._install_windows()
        raise RuntimeError(f"Unsupported platform: {sys.platform!r}")

    def uninstall(self) -> str:
        """Stop and remove the daemon service."""
        platform = _detect_platform()
        if platform == "macos":
            return self._uninstall_launchd()
        if platform == "linux":
            return self._uninstall_systemd()
        if platform == "windows":
            return self._uninstall_windows()
        raise RuntimeError(f"Unsupported platform: {sys.platform!r}")

    def start(self) -> str:
        """Start the daemon without reinstalling."""
        platform = _detect_platform()
        if platform == "macos":
            self._run(["launchctl", "start", _LAUNCHD_LABEL])
            return f"Started launchd agent '{_LAUNCHD_LABEL}'."
        if platform == "linux":
            self._run(["systemctl", "--user", "start", _SYSTEMD_UNIT])
            return f"Started systemd unit '{_SYSTEMD_UNIT}'."
        if platform == "windows":
            self._run(["schtasks", "/run", "/tn", _TASK_NAME])
            return f"Started Windows task '{_TASK_NAME}'."
        raise RuntimeError(f"Unsupported platform: {sys.platform!r}")

    def stop(self) -> str:
        """Stop the daemon without uninstalling."""
        platform = _detect_platform()
        if platform == "macos":
            self._run(["launchctl", "stop", _LAUNCHD_LABEL])
            return f"Stopped launchd agent '{_LAUNCHD_LABEL}'."
        if platform == "linux":
            self._run(["systemctl", "--user", "stop", _SYSTEMD_UNIT])
            return f"Stopped systemd unit '{_SYSTEMD_UNIT}'."
        if platform == "windows":
            self._run(["schtasks", "/end", "/tn", _TASK_NAME])
            return f"Stopped Windows task '{_TASK_NAME}'."
        raise RuntimeError(f"Unsupported platform: {sys.platform!r}")

    def status(self) -> str:
        """Return a human-readable status string for the daemon."""
        platform = _detect_platform()
        try:
            if platform == "macos":
                result = self._run(["launchctl", "list", _LAUNCHD_LABEL], capture=True)
                lines = result.stdout.strip() if result.stdout else ""
                return f"launchd: {lines or 'not running'}"
            if platform == "linux":
                result = self._run(
                    ["systemctl", "--user", "is-active", _SYSTEMD_UNIT], capture=True
                )
                state = result.stdout.strip() if result.stdout else "unknown"
                return f"systemd: {state}"
            if platform == "windows":
                result = self._run(
                    ["schtasks", "/query", "/tn", _TASK_NAME, "/fo", "LIST"],
                    capture=True,
                )
                return f"schtasks: {result.stdout.strip() if result.stdout else 'unknown'}"
        except subprocess.CalledProcessError as exc:
            return f"not installed (exit {exc.returncode})"
        raise RuntimeError(f"Unsupported platform: {sys.platform!r}")

    # ------------------------------------------------------------------
    # macOS (launchd)
    # ------------------------------------------------------------------

    def _install_launchd(self) -> str:
        argv = _build_argv(self._config)
        plist_content = build_launchd_plist(argv, self._config.log_path)
        plist_path = _launchd_plist_path()
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content, encoding="utf-8")
        # Unload first in case it was already registered (idempotent).
        try:
            self._run(["launchctl", "unload", str(plist_path)])
        except subprocess.CalledProcessError:
            pass  # Not loaded yet — fine.
        self._run(["launchctl", "load", "-w", str(plist_path)])
        return (
            f"Installed launchd agent '{_LAUNCHD_LABEL}'.\n"
            f"  plist: {plist_path}\n"
            f"  log:   {self._config.log_path}\n"
            "Gateway will start now and on every future login."
        )

    def _uninstall_launchd(self) -> str:
        plist_path = _launchd_plist_path()
        try:
            self._run(["launchctl", "unload", "-w", str(plist_path)])
        except subprocess.CalledProcessError:
            pass  # Already unloaded.
        if plist_path.exists():
            plist_path.unlink()
        return f"Removed launchd agent '{_LAUNCHD_LABEL}'."

    # ------------------------------------------------------------------
    # Linux (systemd --user)
    # ------------------------------------------------------------------

    def _install_systemd(self) -> str:
        argv = _build_argv(self._config)
        unit_content = build_systemd_unit(argv)
        unit_path = _systemd_unit_path()
        unit_path.parent.mkdir(parents=True, exist_ok=True)
        unit_path.write_text(unit_content, encoding="utf-8")
        self._run(["systemctl", "--user", "daemon-reload"])
        self._run(["systemctl", "--user", "enable", "--now", _SYSTEMD_UNIT])
        return (
            f"Installed systemd user service '{_SYSTEMD_UNIT}'.\n"
            f"  unit: {unit_path}\n"
            "Gateway will start now and on every future login."
        )

    def _uninstall_systemd(self) -> str:
        try:
            self._run(["systemctl", "--user", "disable", "--now", _SYSTEMD_UNIT])
        except subprocess.CalledProcessError:
            pass
        unit_path = _systemd_unit_path()
        if unit_path.exists():
            unit_path.unlink()
        try:
            self._run(["systemctl", "--user", "daemon-reload"])
        except subprocess.CalledProcessError:
            pass
        return f"Removed systemd user service '{_SYSTEMD_UNIT}'."

    # ------------------------------------------------------------------
    # Windows (Task Scheduler)
    # ------------------------------------------------------------------

    def _install_windows(self) -> str:
        argv = _build_argv(self._config)
        xml = _build_windows_task_xml(argv, _TASK_NAME, self._config.log_path)
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(xml)
            tmp_path = tmp.name
        try:
            self._run(["schtasks", "/create", "/tn", _TASK_NAME, "/xml", tmp_path, "/f"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return (
            f"Installed Task Scheduler task '{_TASK_NAME}' (with restart-on-failure).\n"
            "Gateway will start at next logon. To start now: hachi daemon start\n"
            f"Logs: {self._config.log_path}"
        )

    def _uninstall_windows(self) -> str:
        try:
            self._run(["schtasks", "/end", "/tn", _TASK_NAME])
        except subprocess.CalledProcessError:
            pass
        self._run(["schtasks", "/delete", "/tn", _TASK_NAME, "/f"])
        return f"Removed Task Scheduler task '{_TASK_NAME}'."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(
        self,
        cmd: list[str],
        capture: bool = False,
    ) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
        """Execute ``cmd`` via the injectable runner.

        Never uses ``shell=True`` (security guardrail).
        """
        return self._runner(
            cmd,
            check=True,
            text=True,
            capture_output=capture,
        )


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------


def _detect_platform() -> str:
    """Return one of ``'macos'``, ``'linux'``, or ``'windows'``."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    # Broad fallback: treat unknown Unixes as Linux (systemd may not be present
    # but the unit file placement is still the XDG convention).
    return "linux"
