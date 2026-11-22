"""Cross-platform notification backends for Hachi.

Provides two lightweight, zero-extra-dependency notification paths:

- :class:`DesktopNotifier` — sends an OS-native pop-up/toast via platform tools:
  macOS → ``osascript``, Linux → ``notify-send``, Windows → PowerShell balloon tip.
  No credentials required.  Injectable ``runner`` makes it fully offline-testable.

- :class:`EmailNotifier` — sends email via SMTP (stdlib ``smtplib``).  Credentials
  are resolved lazily from environment variables at call time (never at import/boot).
  Injectable ``sender`` replaces the network call in tests.

Both backends degrade gracefully: when not available or not configured they return
a human-readable "not configured / not available" string rather than raising.
"""

from __future__ import annotations

import json
import os
import smtplib
import sys
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

# ---------------------------------------------------------------------------
# Desktop notifier
# ---------------------------------------------------------------------------

# subprocess.run compatible: (cmd: list[str], **kwargs) -> CompletedProcess-like
_Runner = Callable[..., Any]


def _default_runner(cmd: list[str], **kwargs: Any) -> Any:
    """Run a subprocess command (shell=False always)."""
    import subprocess

    return subprocess.run(cmd, shell=False, **kwargs)  # noqa: S603


def _applescript_literal(value: str) -> str:
    """Encode *value* as an AppleScript double-quoted string literal.

    AppleScript string literals are inert with respect to shell-style expansion —
    ``$VAR``, ``$(...)`` subexpressions and backticks have no special meaning to
    AppleScript — so JSON double-quote encoding is an injection-safe representation
    here. ``ensure_ascii=False`` keeps Unicode (emoji, accents) literal instead of
    emitting ``\\uXXXX`` escapes that AppleScript would not decode; ``\\n``/``\\t``
    survive as AppleScript-recognised escapes (rendered as newline/tab).
    """
    return json.dumps(value, ensure_ascii=False)


# Windows desktop notifications are dispatched through PowerShell. Untrusted text
# (notification bodies are frequently summarised from email/web/tool output) must
# NOT be interpolated into the ``-Command`` script: inside the double-quoted strings
# ``json.dumps`` produces, PowerShell expands ``$var``, evaluates ``$(...)``
# subexpressions and processes backtick escapes — a command-injection and
# info-disclosure surface. Instead, title/body travel out-of-band as environment
# variables and the script — a compile-time constant with no interpolation of user
# text — reads them via ``$env:`` (whose values are NOT re-expanded as code).
_WIN_NOTIFY_TITLE_ENV = "HACHI_NOTIFY_TITLE"
_WIN_NOTIFY_BODY_ENV = "HACHI_NOTIFY_BODY"
_WINDOWS_NOTIFY_SCRIPT = (
    "[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
    "$n = New-Object System.Windows.Forms.NotifyIcon; "
    "$n.Icon = [System.Drawing.SystemIcons]::Information; "
    f"$n.BalloonTipTitle = $env:{_WIN_NOTIFY_TITLE_ENV}; "
    f"$n.BalloonTipText = $env:{_WIN_NOTIFY_BODY_ENV}; "
    "$n.Visible = $True; "
    "$n.ShowBalloonTip(4000); "
    "Start-Sleep -Milliseconds 4500; "
    "$n.Dispose()"
)


class DesktopNotifier:
    """Send desktop OS-native notifications (macOS / Linux / Windows).

    No credentials or configuration required — uses built-in OS tools.

    On Windows, PowerShell cold-start takes ~4–8 s on the first invocation.
    To keep :meth:`send` non-blocking, the implementation already dispatches
    the balloon tip in a daemon thread (UC-DESK-001).  When *prewarm* is True
    (the default on Windows), the constructor fires a no-op PowerShell command
    in a daemon thread so the CLR/PS runtime is already resident by the time the
    first real notification arrives, eliminating the cold-start penalty from the
    visible notification delay entirely.

    Args:
        runner: Callable with the same signature as :func:`subprocess.run`.
            Injected in tests so no actual notification is sent.
        prewarm: When True (default) and the platform is Windows, spawn a
            background thread at construction time that runs a minimal PowerShell
            command to warm the interpreter cache.  Has no effect on other
            platforms or when a custom *runner* is injected (test mode).
    """

    def __init__(self, runner: _Runner | None = None, *, prewarm: bool = True) -> None:
        self._runner = runner or _default_runner
        # UC-DESK-001: pre-warm PowerShell on Windows so the first real toast is
        # dispatched to an already-warm interpreter.  Skip when a custom runner is
        # injected (test isolation) or on non-Windows platforms.
        if prewarm and runner is None and sys.platform == "win32":
            self._prewarm()

    def _prewarm(self) -> None:
        """Fire a no-op PowerShell command in a daemon thread to warm the PS runtime.

        This runs completely in the background; any error is silently ignored
        because a failed pre-warm is non-fatal — the toast will still be sent,
        just with the full cold-start latency on the first call.
        """

        def _run() -> None:
            try:
                self._runner(
                    [
                        "powershell.exe",
                        "-NonInteractive",
                        "-NoProfile",
                        "-Command",
                        "[void]0",  # Minimal no-op — loads the CLR/PS runtime.
                    ],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass  # Pre-warm failure is non-fatal.

        threading.Thread(target=_run, daemon=True).start()

    def send(self, title: str, body: str, urgency: str = "normal") -> str:
        """Send a desktop notification.

        Args:
            title: Short notification title (headline).
            body: Notification body text.
            urgency: One of ``"low"``, ``"normal"``, ``"critical"`` (Linux only;
                silently ignored on other platforms).

        Returns:
            Human-readable status string.
        """
        platform = _platform()
        try:
            if platform == "macos":
                return self._send_macos(title, body)
            if platform == "linux":
                return self._send_linux(title, body, urgency)
            if platform == "windows":
                return self._send_windows(title, body)
        except FileNotFoundError as exc:
            return (
                f"Desktop notification not available: {exc}. "
                "On Linux, install 'libnotify-bin' (notify-send). "
                "On macOS, osascript should be present by default."
            )
        except Exception as exc:
            return f"Desktop notification failed: {exc}"
        return "Desktop notifications are not supported on this platform."

    # ------------------------------------------------------------------
    # Platform implementations
    # ------------------------------------------------------------------

    def _send_macos(self, title: str, body: str) -> str:
        # AppleScript double-quoted literals do not perform shell-style expansion,
        # so _applescript_literal is an injection-safe encoding of user text.
        script = (
            f"display notification {_applescript_literal(body)} "
            f"with title {_applescript_literal(title)}"
        )
        self._runner(["osascript", "-e", script], capture_output=True, timeout=10)
        return f"Desktop notification sent: {title!r}"

    def _send_linux(self, title: str, body: str, urgency: str) -> str:
        valid_urgency = urgency if urgency in ("low", "normal", "critical") else "normal"
        self._runner(
            ["notify-send", f"--urgency={valid_urgency}", title, body],
            capture_output=True,
            timeout=10,
        )
        return f"Desktop notification sent: {title!r}"

    def _send_windows(self, title: str, body: str) -> str:
        # Use PowerShell WinForms balloon tip — no BurntToast required.
        # Title/body are passed out-of-band via environment variables (read by the
        # constant _WINDOWS_NOTIFY_SCRIPT) so untrusted text is never parsed as
        # PowerShell code. A fresh per-call env dict (no os.environ mutation) keeps
        # this thread-safe; it inherits the current environment so PowerShell and its
        # assemblies resolve normally.
        #
        # The PS script blocks for ~4.5 s (waiting for the balloon to expire), so we
        # run it in a daemon thread to avoid stalling the caller.
        import threading

        env = {
            **os.environ,
            _WIN_NOTIFY_TITLE_ENV: title,
            _WIN_NOTIFY_BODY_ENV: body,
        }

        def _run() -> None:
            self._runner(
                [
                    "powershell.exe",
                    "-NonInteractive",
                    "-NoProfile",
                    "-Command",
                    _WINDOWS_NOTIFY_SCRIPT,
                ],
                capture_output=True,
                timeout=15,
                env=env,
            )

        threading.Thread(target=_run, daemon=True).start()
        return f"Desktop notification queued: {title!r}"


# ---------------------------------------------------------------------------
# Email notifier (SMTP)
# ---------------------------------------------------------------------------

# Injectable sender: (host, port, user, password, from_addr, to_addr, msg) -> None
EmailSender = Callable[[str, int, str, str, str, str, MIMEMultipart], None]


def _default_email_sender(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    msg: MIMEMultipart,
) -> None:
    """Send email via SMTP with STARTTLS (stdlib, no extra deps)."""
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, to_addr, msg.as_string())


class EmailNotifier:
    """Send email notifications via SMTP.

    Credentials are resolved lazily from environment variables at call time:
    - ``HACHI_SMTP_HOST``   (default: ``smtp.gmail.com``)
    - ``HACHI_SMTP_PORT``   (default: ``587``)
    - ``HACHI_SMTP_USER``   (required for auth)
    - ``HACHI_SMTP_PASSWORD`` (required for auth)
    - ``HACHI_SMTP_FROM``   (defaults to SMTP_USER)
    - ``HACHI_SMTP_TO``     (default recipient when ``to`` is empty)

    Args:
        sender: Injectable SMTP sender for tests (replaces the real network call).
    """

    def __init__(self, sender: EmailSender | None = None) -> None:
        self._sender = sender or _default_email_sender

    @classmethod
    def from_env(cls, sender: EmailSender | None = None) -> EmailNotifier:
        """Convenience constructor — explicitly reads env at call time."""
        return cls(sender=sender)

    def is_configured(self) -> bool:
        """Return True when SMTP credentials (user AND password) are available."""
        return bool(
            os.environ.get("HACHI_SMTP_USER") and os.environ.get("HACHI_SMTP_PASSWORD")
        )

    def send(self, subject: str, body: str, to: str = "") -> dict[str, str]:
        """Send an email notification.

        Args:
            subject: Email subject line.
            body: Email body (plain text).
            to: Recipient address; falls back to ``HACHI_SMTP_TO`` when empty.

        Returns:
            ``{"to": addr, "subject": subject}`` on success.

        Raises:
            RuntimeError: When not configured or the send fails.
        """
        if not self.is_configured():
            raise RuntimeError(
                "Email notifications are not configured. "
                "Set HACHI_SMTP_USER and HACHI_SMTP_PASSWORD."
            )
        host = os.environ.get("HACHI_SMTP_HOST", "smtp.gmail.com")
        _raw_port = os.environ.get("HACHI_SMTP_PORT", "587")
        try:
            port = int(_raw_port)
        except ValueError:
            raise RuntimeError(
                f"HACHI_SMTP_PORT must be an integer, got: {_raw_port!r}"
            ) from None
        user = os.environ.get("HACHI_SMTP_USER", "")
        password = os.environ.get("HACHI_SMTP_PASSWORD", "")
        from_addr = os.environ.get("HACHI_SMTP_FROM") or user
        to_addr = to or os.environ.get("HACHI_SMTP_TO", "")

        if not to_addr:
            raise RuntimeError("No recipient address. Pass `to` or set HACHI_SMTP_TO.")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.attach(MIMEText(body, "plain"))

        self._sender(host, port, user, password, from_addr, to_addr, msg)
        return {"to": to_addr, "subject": subject}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "win32":
        return "windows"
    return "unknown"


# ---------------------------------------------------------------------------
# Notification digest buffer
# ---------------------------------------------------------------------------


class DigestBuffer:
    """Thread-safe accumulator for batched notification digests.

    Notifications are added via :meth:`add` and flushed (sent as one email
    and/or desktop pop-up) via :meth:`flush`. A background timer can be
    scheduled with :meth:`flush_after` to send automatically.

    Each item is a ``(timestamp_iso, message)`` tuple stored in a deque.
    """

    def __init__(
        self,
        email_notifier: EmailNotifier | None = None,
        desktop_notifier: DesktopNotifier | None = None,
    ) -> None:
        self._items: deque[tuple[str, str]] = deque()
        self._lock = threading.Lock()
        self._email = email_notifier
        self._desktop = desktop_notifier
        self._timer: threading.Timer | None = None

    def add(self, message: str) -> None:
        """Add a notification to the pending digest."""
        ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        with self._lock:
            self._items.append((ts, message))

    def pending_count(self) -> int:
        """Return the number of buffered items not yet flushed."""
        with self._lock:
            return len(self._items)

    def flush(
        self,
        subject: str = "Hachi digest",
        to: str = "",
    ) -> dict[str, Any]:
        """Send all pending items as one digest and clear the buffer.

        Returns a result dict with keys ``sent_email``, ``sent_desktop``,
        ``item_count``, and ``error`` (empty string on success).
        """
        with self._lock:
            items = list(self._items)
            self._items.clear()

        if not items:
            return {"sent_email": False, "sent_desktop": False, "item_count": 0, "error": ""}

        body = "\n".join(f"[{ts}] {msg}" for ts, msg in items)
        result: dict[str, Any] = {
            "sent_email": False,
            "sent_desktop": False,
            "item_count": len(items),
            "error": "",
        }

        email_notifier = self._email or EmailNotifier.from_env()
        if email_notifier.is_configured():
            try:
                send_result = email_notifier.send(subject=subject, body=body, to=to)
                result["sent_email"] = bool(send_result.get("to"))
            except Exception as exc:
                result["error"] = str(exc)

        desktop = self._desktop or DesktopNotifier()
        desktop_body = (
            f"{len(items)} notification(s) — check your email for details."
            if result["sent_email"]
            else body[:200]
        )
        desktop_result = desktop.send(title=subject, body=desktop_body)
        result["sent_desktop"] = "sent" in desktop_result.lower()
        return result

    def flush_after(self, seconds: float, subject: str = "Hachi digest", to: str = "") -> None:
        """Schedule a one-shot flush after *seconds*.

        If a timer is already pending it is cancelled and replaced — calling
        this multiple times just pushes the flush back.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                seconds, self.flush, kwargs={"subject": subject, "to": to}
            )
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        """Cancel any pending scheduled flush without sending."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
