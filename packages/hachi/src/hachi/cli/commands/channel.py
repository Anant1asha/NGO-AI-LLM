"""Channel command group: run Telegram/WhatsApp bridges to Hachi."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()

channel_app = typer.Typer(
    help="Talk to Hachi from external chat apps (Telegram, WhatsApp, …)."
)


@channel_app.command("telegram")
def channel_telegram(
    token: str | None = typer.Option(
        None, "--token", envvar="TELEGRAM_BOT_TOKEN", help="Telegram bot token from @BotFather."
    ),
    allow: str | None = typer.Option(
        None, "--allow", help="Comma-separated Telegram chat ids to restrict access to."
    ),
    poll_interval: float = typer.Option(2.0, "--interval", help="Seconds between polls."),
    setup: bool = typer.Option(
        False,
        "--setup",
        help="Guided one-time setup: paste your bot token + allowlist, stored securely.",
    ),
):
    """Run a Telegram bot that relays messages to Hachi (one session per chat).

    Like OpenClaw, this runs entirely on your machine via Telegram long-polling —
    no deployment and no public URL. Run ``--setup`` once to store your bot token
    in the OS credential vault and pick who's allowed to talk to it.
    """
    import time

    from hachi.channels import ChannelRouter
    from hachi.channels.runner import GatewaySessionRunner
    from hachi.channels.telegram import TelegramAdapter
    from hachi.channels.telegram_setup import (
        load_allowlist,
        looks_like_token,
        parse_allowlist,
        resolve_token,
        save_allowlist,
        save_token,
    )

    if setup:
        console.print(
            "[bold]Telegram setup[/bold] — create a bot with [cyan]@BotFather[/cyan] "
            "(/newbot) and copy the token it gives you."
        )
        entered = typer.prompt("Paste your bot token", default="", show_default=False).strip()
        if not entered:
            console.print("[red]No token entered. Aborting setup.[/red]")
            raise typer.Exit(2)
        if not looks_like_token(entered):
            console.print(
                "[yellow]Warning:[/yellow] that doesn't look like a bot token "
                "(expected '<digits>:<letters>'). Saving it anyway."
            )
        save_token(entered)
        token = entered

        console.print(
            "\nWho may talk to this bot? Enter your Telegram [cyan]chat id(s)[/cyan], "
            "comma-separated.\nLeave blank to allow [bold]anyone[/bold] who messages it "
            "(only safe for a private bot)."
        )
        console.print(
            "[dim]Tip: message [cyan]@userinfobot[/cyan] to learn your chat id, or leave "
            "blank now and read it from this console after your first message.[/dim]"
        )
        allow_raw = typer.prompt("Allowed chat ids", default="", show_default=False)
        allowlist_setup = parse_allowlist(allow_raw)
        save_allowlist(allowlist_setup)
        console.print(
            f"[green]Saved.[/green] Token stored in the credential vault; "
            f"allowlist: {allowlist_setup or 'anyone'}.\n"
        )

    token = resolve_token(token)
    if not token:
        console.print(
            "[red]No bot token.[/red] Run [cyan]hachi channel telegram --setup[/cyan], "
            "or pass --token / set TELEGRAM_BOT_TOKEN (create a bot via @BotFather)."
        )
        raise typer.Exit(2)

    if allow is not None:
        allowlist = parse_allowlist(allow)
    else:
        allowlist = load_allowlist()
    if not allowlist:
        console.print(
            "[yellow]Heads up:[/yellow] no allowlist set — anyone who finds this bot can "
            "use your agent. Restrict it with --setup or --allow <chat-id>."
        )

    try:
        from hachi.core.onboarding import OnboardingService

        if OnboardingService().needs_setup():
            console.print(
                "[yellow]Note:[/yellow] no working LLM provider is configured yet. "
                "Run [cyan]hachi quickstart[/cyan] first, or messages will error."
            )
    except Exception:
        pass

    adapter = TelegramAdapter(token)
    runner = GatewaySessionRunner()
    router = ChannelRouter(runner, allowlist=allowlist or None)
    console.print("[green]Telegram bot running.[/green] Press Ctrl+C to stop.")
    try:
        while True:
            try:
                for inbound in adapter.poll_once():
                    console.print(
                        f"[cyan]{inbound.sender_name or inbound.sender_id}[/cyan] "
                        f"[dim](id {inbound.sender_id})[/dim]: {inbound.text}"
                    )
                    try:
                        adapter.send(router.dispatch(inbound))
                    except Exception as _dispatch_err:
                        console.print(f"[yellow]dispatch error:[/yellow] {_dispatch_err}")
            except KeyboardInterrupt:
                raise
            except Exception as _poll_err:
                console.print(f"[yellow]poll error (retrying):[/yellow] {_poll_err}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopping Telegram bot...[/dim]")
    finally:
        runner.shutdown()


@channel_app.command("whatsapp")
def channel_whatsapp(
    port: int = typer.Option(8080, "--port", help="Local port to bind the webhook server to."),
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind."),  # noqa: S104
    verify_token: str | None = typer.Option(
        None,
        "--verify-token",
        envvar="META_WHATSAPP_VERIFY_TOKEN",
        help="Webhook verify token to configure in Meta App Dashboard.",
    ),
    allow: str | None = typer.Option(
        None,
        "--allow",
        help="Comma-separated sender phone numbers (E.164) to restrict access to.",
    ),
) -> None:
    """Run a WhatsApp webhook receiver that relays inbound messages to Hachi."""
    from hachi.channels import ChannelRouter
    from hachi.channels.runner import GatewaySessionRunner
    from hachi.channels.whatsapp import WhatsAppAdapter, WhatsAppWebhookServer

    allowlist = {a.strip() for a in allow.split(",") if a.strip()} if allow else set()
    runner = GatewaySessionRunner()
    router = ChannelRouter(runner, allowlist=list(allowlist) if allowlist else None)
    adapter = WhatsAppAdapter()

    def dispatch(msg: object) -> None:
        console.print(
            f"[cyan]{getattr(msg, 'sender_name', None) or getattr(msg, 'sender_id', '?')}[/cyan]:"
            f" {getattr(msg, 'text', '')}"
        )
        try:
            adapter.send(router.dispatch(msg))  # type: ignore[arg-type]
        except Exception as exc:
            console.print(f"[red]WhatsApp reply failed:[/red] {exc}")

    server = WhatsAppWebhookServer(
        host=host,
        port=port,
        verify_token=verify_token or "",
        dispatcher=dispatch,
        allowed_senders=allowlist,
    )
    console.print(
        f"[green]WhatsApp webhook server running[/green] on http://{host}:{port}/\n"
        "Configure your Meta App Dashboard webhook URL to point here (path: /)\n"
        f"  Verify token: [bold]{verify_token or '(none)'}[/bold]\n"
        "Press Ctrl+C to stop."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Stopping WhatsApp webhook server...[/dim]")
    finally:
        server.server_close()
        runner.shutdown()
