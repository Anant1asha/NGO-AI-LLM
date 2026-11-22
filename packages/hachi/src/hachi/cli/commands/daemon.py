"""Daemon command group: manage the Hachi background gateway service."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

daemon_app = typer.Typer(
    help="Manage the Hachi always-on background gateway daemon.",
    no_args_is_help=True,
)


def _make_installer(host: str, port: int):  # type: ignore[no-untyped-def]
    from hachi.daemon import DaemonConfig, DaemonInstaller

    return DaemonInstaller(DaemonConfig(host=host, port=port))


@daemon_app.command("install")
def daemon_install(
    host: str = typer.Option("127.0.0.1", "--host", help="Gateway bind address."),
    port: int = typer.Option(8787, "--port", help="Gateway bind port."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the service unit that would be installed, then exit."
    ),
) -> None:
    """Install the gateway as a persistent background service (auto-starts on login).

    Supports macOS (launchd), Linux (systemd --user), and Windows (Task Scheduler).
    """
    if dry_run:
        from hachi.daemon import (
            DaemonConfig,
            _build_argv,
            _default_log_path,
            _detect_platform,
            build_launchd_plist,
            build_systemd_unit,
        )

        cfg = DaemonConfig(host=host, port=port)
        argv = _build_argv(cfg)
        platform = _detect_platform()
        if platform == "macos":
            unit = build_launchd_plist(argv, _default_log_path())
        elif platform == "linux":
            unit = build_systemd_unit(argv)
        else:
            unit = "\n".join(argv)
        console.print(f"[dim]# dry-run — platform: {platform}[/dim]")
        console.print(unit)
        return

    try:
        msg = _make_installer(host, port).install()
        console.print(f"[green]✓[/green] {msg}")
    except Exception as exc:
        console.print(f"[red]daemon install failed:[/red] {exc}")
        raise typer.Exit(1) from exc


@daemon_app.command("uninstall")
def daemon_uninstall() -> None:
    """Stop and remove the Hachi daemon service."""
    try:
        msg = _make_installer("127.0.0.1", 8787).uninstall()
        console.print(f"[green]✓[/green] {msg}")
    except Exception as exc:
        console.print(f"[red]daemon uninstall failed:[/red] {exc}")
        raise typer.Exit(1) from exc


@daemon_app.command("start")
def daemon_start() -> None:
    """Start the installed daemon without reinstalling."""
    try:
        msg = _make_installer("127.0.0.1", 8787).start()
        console.print(f"[green]✓[/green] {msg}")
    except Exception as exc:
        console.print(f"[red]daemon start failed:[/red] {exc}")
        raise typer.Exit(1) from exc


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the running daemon without uninstalling."""
    try:
        msg = _make_installer("127.0.0.1", 8787).stop()
        console.print(f"[green]✓[/green] {msg}")
    except Exception as exc:
        console.print(f"[red]daemon stop failed:[/red] {exc}")
        raise typer.Exit(1) from exc


@daemon_app.command("status")
def daemon_status() -> None:
    """Show whether the gateway daemon is running."""
    try:
        msg = _make_installer("127.0.0.1", 8787).status()
        console.print(msg)
    except Exception as exc:
        console.print(f"[red]daemon status failed:[/red] {exc}")
        raise typer.Exit(1) from exc


@daemon_app.command("logs")
def daemon_logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of tail lines to show."),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Stream new log lines (Ctrl-C to stop)."
    ),
) -> None:
    """Show (or stream) the gateway daemon log."""
    from hachi.daemon import _default_log_path

    log_path = _default_log_path()
    if not log_path.exists():
        console.print(f"[yellow]Log file not found:[/yellow] {log_path}")
        console.print("The daemon may not have been started yet. Run: hachi daemon start")
        raise typer.Exit(1)

    if follow:
        import time

        console.print(f"[dim]Streaming {log_path} (Ctrl-C to stop)…[/dim]")
        with log_path.open(encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            try:
                while True:
                    chunk = fh.read(4096)
                    if chunk:
                        console.print(chunk, end="", markup=False, highlight=False)
                    else:
                        time.sleep(0.25)
            except KeyboardInterrupt:
                pass
        return

    text = log_path.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
    console.print(f"[dim]# {log_path}  (last {len(tail)} lines)[/dim]")
    for line in tail:
        console.print(line, markup=False, highlight=False)
