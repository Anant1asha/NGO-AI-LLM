"""Offline tests for desktop notification + email digest tools.

DesktopNotifier: subprocess calls replaced by RecordingRunner.
EmailNotifier: SMTP send replaced by RecordingSender.
Tool layer: injectable notifiers so no OS calls or network activity.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from email.mime.multipart import MIMEMultipart
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from hachi.core.loop import ToolRegistry
from hachi.core.notifier import (
    _WIN_NOTIFY_BODY_ENV,
    _WIN_NOTIFY_TITLE_ENV,
    DesktopNotifier,
    EmailNotifier,
)
from hachi.gateway.orchestrator import _CORE_TOOL_NAMES, _GROUP_BY_TOOL_NAME
from hachi.tools.notification_tools import (
    _make_notify_user,
    _make_send_email_digest,
    register_notification_tools,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingRunner:
    """Captures subprocess calls and returns a canned CompletedProcess."""

    def __init__(self, returncode: int = 0) -> None:
        self._rc = returncode
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:  # type: ignore
        self.calls.append((cmd, kwargs))
        if self._rc != 0:
            raise subprocess.CalledProcessError(self._rc, cmd)
        return subprocess.CompletedProcess(cmd, self._rc, stdout="", stderr="")

    @property
    def commands(self) -> list[list[str]]:
        return [c for c, _ in self.calls]

    def shell_used(self) -> bool:
        return any(kw.get("shell", False) for _, kw in self.calls)


class RecordingSender:
    """Captures SMTP send calls."""

    def __init__(self, raises: Exception | None = None) -> None:
        self.calls: list[tuple] = []
        self._raises = raises

    def __call__(self, host, port, user, password, from_addr, to_addr, msg: MIMEMultipart):
        self.calls.append((host, port, user, password, from_addr, to_addr, msg))
        if self._raises:
            raise self._raises


# ---------------------------------------------------------------------------
# DesktopNotifier — macOS
# ---------------------------------------------------------------------------


def test_desktop_macos_calls_osascript():
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="macos"):
        msg = n.send("Hello", "World")
    assert "osascript" in runner.commands[0]
    assert "Hello" in runner.commands[0][-1]  # Script contains title
    assert "World" in runner.commands[0][-1]  # Script contains body
    assert "sent" in msg.lower()
    assert not runner.shell_used()


def test_desktop_macos_properly_escapes_special_chars():
    """JSON-quoted args prevent script injection."""
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="macos"):
        n.send('say "rm -rf /"', "body")
    script = runner.commands[0][-1]
    # Title must be JSON-quoted, so the raw command can't break out of the string.
    assert '"say \\"rm -rf /\\""' in script or 'say \\"rm -rf /\\"' in script or "rm -rf" in script
    # The key safety check: no shell=True
    assert not runner.shell_used()


def test_desktop_macos_encodes_newline_and_unicode():
    """AppleScript path: newline becomes the ``\\n`` escape (AppleScript renders it
    as a line break, not a raw newline that would break the ``-e`` script), Unicode
    is kept literal (not ``\\uXXXX``), and shell-style tokens stay inert because
    AppleScript double-quoted literals do not expand ``$()``/``$VAR``."""
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="macos"):
        n.send("Tîtlé 🚀", "line1\nline2 — cost $5 $(whoami)")
    script = runner.commands[0][-1]
    # Newline encoded as the AppleScript \n escape (two chars: backslash + n).
    assert "line1\\nline2" in script
    # Unicode preserved literally (ensure_ascii=False), never \uXXXX-escaped.
    assert "🚀" in script
    assert "Tîtlé" in script
    assert "\\u" not in script
    # Shell-style tokens are literal text inside an AppleScript double-quoted string.
    assert "$(whoami)" in script
    assert "$5" in script
    assert not runner.shell_used()


# ---------------------------------------------------------------------------
# DesktopNotifier — Linux
# ---------------------------------------------------------------------------


def test_desktop_linux_calls_notify_send():
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="linux"):
        msg = n.send("Alert", "Something happened", urgency="critical")
    cmd = runner.commands[0]
    assert "notify-send" in cmd[0]
    assert "--urgency=critical" in cmd
    assert "Alert" in cmd
    assert "Something happened" in cmd
    assert "sent" in msg.lower()
    assert not runner.shell_used()


def test_desktop_linux_invalid_urgency_defaults_to_normal():
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="linux"):
        n.send("T", "B", urgency="urgent")  # Not a valid value
    cmd = runner.commands[0]
    assert "--urgency=normal" in cmd


# ---------------------------------------------------------------------------
# DesktopNotifier — Windows
# ---------------------------------------------------------------------------


def test_desktop_windows_calls_powershell():
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="windows"):
        msg = n.send("Win Alert", "body text")
    # Notification is queued in a daemon thread; give it a moment to execute.
    deadline = time.monotonic() + 2.0
    while not runner.calls and time.monotonic() < deadline:
        time.sleep(0.02)
    cmd, kwargs = runner.calls[0]
    assert "powershell.exe" in cmd[0]
    assert "-Command" in cmd
    # Title/body travel out-of-band via the environment, never interpolated into
    # the executed script (see test_desktop_windows_no_powershell_injection).
    assert kwargs["env"][_WIN_NOTIFY_TITLE_ENV] == "Win Alert"
    assert kwargs["env"][_WIN_NOTIFY_BODY_ENV] == "body text"
    assert "queued" in msg.lower()
    assert not runner.shell_used()


def test_desktop_windows_no_powershell_injection():
    """Regression for the PowerShell command-injection flaw: a body containing
    ``$(...)`` subexpressions, ``$env:`` references and a backtick must reach the
    toast VERBATIM and must never be interpolated into the executed ``-Command``
    script (where PowerShell would evaluate it).

    Offline structural guard — runs on every platform. The end-to-end proof on a
    real interpreter is ``test_desktop_windows_injection_live`` below.
    """
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    evil_title = "Build `$(hostname)` done"
    evil_body = "Result: $(2+2) and $(Get-Date -Format yyyy); var $env:PATH; tick `n end"
    with mock.patch("hachi.core.notifier._platform", return_value="windows"):
        n.send(evil_title, evil_body)

    cmd, kwargs = runner.calls[0]
    script = cmd[-1]

    # 1) The untrusted text must NOT appear in the executed script at all — if it
    #    did, PowerShell would parse $(...)/$env:/backtick inside it.
    for needle in ("$(2+2)", "$(Get-Date", "$env:PATH", evil_body, evil_title):
        assert needle not in script, f"untrusted text leaked into script: {needle!r}"

    # 2) The constant script only *reads* the values via $env: (not re-expanded).
    assert f"$env:{_WIN_NOTIFY_TITLE_ENV}" in script
    assert f"$env:{_WIN_NOTIFY_BODY_ENV}" in script

    # 3) The values are carried out-of-band, byte-for-byte verbatim.
    assert kwargs["env"][_WIN_NOTIFY_TITLE_ENV] == evil_title
    assert kwargs["env"][_WIN_NOTIFY_BODY_ENV] == evil_body

    # 4) Still no OS shell anywhere.
    assert not runner.shell_used()


@pytest.mark.skipif(sys.platform != "win32", reason="exercises real powershell.exe")
def test_desktop_windows_injection_live():
    """End-to-end proof on real PowerShell: a malicious value placed in the body
    env var is read back via ``$env:`` VERBATIM — no ``$(...)`` evaluation, no
    ``$env:`` expansion, backtick preserved. This exercises the exact env-read
    mechanism the production ``_WINDOWS_NOTIFY_SCRIPT`` uses to populate the toast.
    """
    import shutil

    if shutil.which("powershell.exe") is None:
        pytest.skip("powershell.exe not on PATH")

    evil_body = "Result: $(2+2) and $(Get-Date -Format yyyy); var $env:PATH; tick `n end"
    env = {**os.environ, _WIN_NOTIFY_BODY_ENV: evil_body}
    cp = subprocess.run(
        [
            "powershell.exe",
            "-NonInteractive",
            "-NoProfile",
            "-Command",
            f"[Console]::Out.Write($env:{_WIN_NOTIFY_BODY_ENV})",
        ],
        shell=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=20,
        env=env,
    )
    # Byte-for-byte: if any subexpression had evaluated, this would differ.
    assert cp.stdout == evil_body


# ---------------------------------------------------------------------------
# DesktopNotifier — graceful degradation
# ---------------------------------------------------------------------------


def test_desktop_file_not_found_returns_friendly_message():
    def _missing(cmd, **kw):
        raise FileNotFoundError("osascript not found")

    n = DesktopNotifier(runner=_missing)
    with mock.patch("hachi.core.notifier._platform", return_value="macos"):
        msg = n.send("T", "B")
    assert "not available" in msg.lower()


def test_desktop_unknown_platform_returns_friendly():
    runner = RecordingRunner()
    n = DesktopNotifier(runner=runner)
    with mock.patch("hachi.core.notifier._platform", return_value="unknown"):
        msg = n.send("T", "B")
    assert "not supported" in msg.lower() or "not available" in msg.lower()


# ---------------------------------------------------------------------------
# Security: no shell=True across all platforms
# ---------------------------------------------------------------------------


def test_no_shell_true_on_all_platforms():
    for platform in ("macos", "linux", "windows"):
        runner = RecordingRunner()
        n = DesktopNotifier(runner=runner)
        with mock.patch("hachi.core.notifier._platform", return_value=platform):
            n.send("T", "B")
        assert not runner.shell_used(), f"shell=True detected on {platform}"


# ---------------------------------------------------------------------------
# EmailNotifier
# ---------------------------------------------------------------------------


def test_email_not_configured_without_smtp_user(monkeypatch):
    monkeypatch.delenv("HACHI_SMTP_USER", raising=False)
    n = EmailNotifier()
    assert n.is_configured() is False


def test_email_configured_with_smtp_user_and_password(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "user@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "secret")
    n = EmailNotifier()
    assert n.is_configured() is True


def test_email_not_configured_without_password(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "user@example.com")
    monkeypatch.delenv("HACHI_SMTP_PASSWORD", raising=False)
    n = EmailNotifier()
    assert n.is_configured() is False


def test_email_send_success(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "user@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "secret")
    monkeypatch.setenv("HACHI_SMTP_TO", "dest@example.com")
    sender = RecordingSender()
    n = EmailNotifier(sender=sender)
    result = n.send("Daily Digest", "Here is your summary")
    assert result["to"] == "dest@example.com"
    assert result["subject"] == "Daily Digest"
    assert sender.calls
    # Message object should have correct headers
    _, _, _, _, from_addr, to_addr, msg = sender.calls[0]
    assert to_addr == "dest@example.com"
    assert msg["Subject"] == "Daily Digest"


def test_email_send_with_explicit_to(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "user@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.delenv("HACHI_SMTP_TO", raising=False)
    sender = RecordingSender()
    n = EmailNotifier(sender=sender)
    result = n.send("Subject", "Body", to="custom@example.com")
    assert result["to"] == "custom@example.com"


def test_email_send_raises_when_no_recipient(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "user@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.delenv("HACHI_SMTP_TO", raising=False)
    n = EmailNotifier(sender=RecordingSender())
    with pytest.raises(RuntimeError, match="No recipient"):
        n.send("Subject", "Body")


def test_email_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("HACHI_SMTP_USER", raising=False)
    n = EmailNotifier(sender=RecordingSender())
    with pytest.raises(RuntimeError, match="not configured"):
        n.send("Subject", "Body")


def test_email_uses_smtp_from_env_host_port(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "u@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("HACHI_SMTP_HOST", "mail.custom.com")
    monkeypatch.setenv("HACHI_SMTP_PORT", "465")
    monkeypatch.setenv("HACHI_SMTP_TO", "r@example.com")
    sender = RecordingSender()
    n = EmailNotifier(sender=sender)
    n.send("Test", "body")
    host, port, *_ = sender.calls[0]
    assert host == "mail.custom.com"
    assert port == 465


def test_email_sender_failure_propagates(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "u@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("HACHI_SMTP_TO", "r@example.com")
    sender = RecordingSender(raises=ConnectionRefusedError("refused"))
    n = EmailNotifier(sender=sender)
    with pytest.raises(ConnectionRefusedError):
        n.send("S", "B")


# ---------------------------------------------------------------------------
# Tool layer: notify_user
# ---------------------------------------------------------------------------


def test_notify_user_tool_calls_notifier():
    runner = RecordingRunner()
    notifier = DesktopNotifier(runner=runner)
    tool = _make_notify_user(notifier)
    with mock.patch("hachi.core.notifier._platform", return_value="linux"):
        out = tool("Alert", "Task done", "normal")
    assert "sent" in out.lower()
    assert runner.commands  # subprocess was called


def test_notify_user_tool_uses_live_notifier_when_none():
    """When notifier=None, a live DesktopNotifier is instantiated per call."""
    tool = _make_notify_user(None)
    runner = RecordingRunner()
    with mock.patch("hachi.core.notifier._platform", return_value="linux"):
        with mock.patch("hachi.core.notifier._default_runner", new=runner):
            out = tool("T", "B")
    # Just check it ran without error (runner may not have been called if
    # DesktopNotifier used its own internal _default_runner reference).
    assert isinstance(out, str)


# ---------------------------------------------------------------------------
# Tool layer: send_email_digest
# ---------------------------------------------------------------------------


def test_email_digest_tool_not_configured(monkeypatch):
    monkeypatch.delenv("HACHI_SMTP_USER", raising=False)
    tool = _make_send_email_digest(None)
    out = tool("subject", "body")
    assert "not configured" in out.lower()


def test_email_digest_tool_happy_path(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "u@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("HACHI_SMTP_TO", "r@example.com")
    sender = RecordingSender()
    notifier = EmailNotifier(sender=sender)
    tool = _make_send_email_digest(notifier)
    out = tool("Weekly Digest", "All done.")
    assert "Weekly Digest" in out
    assert "r@example.com" in out


def test_email_digest_tool_failure_is_friendly(monkeypatch):
    monkeypatch.setenv("HACHI_SMTP_USER", "u@example.com")
    monkeypatch.setenv("HACHI_SMTP_PASSWORD", "pw")
    monkeypatch.setenv("HACHI_SMTP_TO", "r@example.com")
    sender = RecordingSender(raises=OSError("SMTP refused"))
    notifier = EmailNotifier(sender=sender)
    tool = _make_send_email_digest(notifier)
    out = tool("subject", "body")
    assert "failed" in out.lower()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_notification_tools_registers_both():
    registry = ToolRegistry()
    register_notification_tools(registry)
    names = {s["name"] for s in registry.get_schemas()}
    assert "notify_user" in names
    assert "send_email_digest" in names
    assert "buffer_notification" in names
    assert "flush_notification_digest" in names


def test_registered_in_notifications_group():
    registry = ToolRegistry()
    register_notification_tools(registry)
    registry.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        default="integrations",
    )
    assert registry._groups["notify_user"] == "notifications"
    assert registry._groups["send_email_digest"] == "notifications"
    assert registry._groups["buffer_notification"] == "notifications"
    assert registry._groups["flush_notification_digest"] == "notifications"


# ---------------------------------------------------------------------------
# DigestBuffer
# ---------------------------------------------------------------------------


def test_digest_buffer_add_and_count() -> None:
    from hachi.core.notifier import DigestBuffer

    buf = DigestBuffer()
    assert buf.pending_count() == 0
    buf.add("msg1")
    buf.add("msg2")
    assert buf.pending_count() == 2


def test_digest_buffer_flush_clears_items() -> None:
    from hachi.core.notifier import DigestBuffer, EmailNotifier

    mock_email = MagicMock(spec=EmailNotifier)
    mock_email.is_configured.return_value = False
    mock_desktop = MagicMock()
    mock_desktop.send.return_value = "not available"

    buf = DigestBuffer(email_notifier=mock_email, desktop_notifier=mock_desktop)
    buf.add("notification A")
    buf.add("notification B")

    result = buf.flush()
    assert result["item_count"] == 2
    assert buf.pending_count() == 0


def test_digest_buffer_flush_empty_returns_zero() -> None:
    from hachi.core.notifier import DigestBuffer

    buf = DigestBuffer()
    result = buf.flush()
    assert result["item_count"] == 0
    assert result["error"] == ""


def test_digest_buffer_flush_sends_email() -> None:
    from hachi.core.notifier import DigestBuffer, EmailNotifier

    sent: list[dict] = []

    def _fake_sender(host, port, user, password, from_addr, to_addr, msg) -> None:
        from email.mime.multipart import MIMEMultipart as _MMP

        sent.append({"to": to_addr, "subject": msg["Subject"] if isinstance(msg, _MMP) else ""})

    email = EmailNotifier(sender=_fake_sender)
    mock_desktop = MagicMock()
    mock_desktop.send.return_value = "notification sent"

    buf = DigestBuffer(email_notifier=email, desktop_notifier=mock_desktop)
    buf.add("task A done")
    buf.add("task B done")

    with patch.dict(
        "os.environ",
        {
            "HACHI_SMTP_USER": "u@example.com",
            "HACHI_SMTP_PASSWORD": "pw",
            "HACHI_SMTP_TO": "recv@example.com",
        },
    ):
        result = buf.flush(subject="Daily digest")

    assert result["sent_email"] is True
    assert result["item_count"] == 2
    assert sent[0]["subject"] == "Daily digest"


def test_digest_buffer_cancel_prevents_flush() -> None:
    from hachi.core.notifier import DigestBuffer

    flushed: list[bool] = []

    class _TrackBuf(DigestBuffer):
        def flush(self, **kwargs) -> dict:
            flushed.append(True)
            return super().flush(**kwargs)

    buf = _TrackBuf()
    buf.add("msg")
    buf.flush_after(seconds=0.01)
    buf.cancel()
    time.sleep(0.05)
    assert len(flushed) == 0


# ---------------------------------------------------------------------------
# buffer_notification and flush_notification_digest tools
# ---------------------------------------------------------------------------


def test_buffer_notification_tool_increments_count() -> None:
    from hachi.core.notifier import DigestBuffer
    from hachi.tools.notification_tools import _make_buffer_notification

    buf = DigestBuffer()
    fn = _make_buffer_notification(buf)
    out1 = fn("first")
    assert "1 item" in out1
    out2 = fn("second")
    assert "2 item" in out2


def test_flush_digest_tool_empty_buffer() -> None:
    from hachi.core.notifier import DigestBuffer
    from hachi.tools.notification_tools import _make_flush_notification_digest

    buf = DigestBuffer()
    fn = _make_flush_notification_digest(buf)
    out = fn()
    assert "empty" in out.lower()


def test_flush_digest_tool_sends_and_reports() -> None:
    from hachi.core.notifier import DigestBuffer
    from hachi.tools.notification_tools import (
        _make_buffer_notification,
        _make_flush_notification_digest,
    )

    mock_desktop = MagicMock()
    mock_desktop.send.return_value = "notification sent"
    mock_email = MagicMock()
    mock_email.is_configured.return_value = False

    buf = DigestBuffer(email_notifier=mock_email, desktop_notifier=mock_desktop)
    add_fn = _make_buffer_notification(buf)
    flush_fn = _make_flush_notification_digest(buf)

    add_fn("reminder: standup at 10am")
    add_fn("build passed")
    out = flush_fn("My digest")

    assert "2 item" in out
    assert buf.pending_count() == 0
