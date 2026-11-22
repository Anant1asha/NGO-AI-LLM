"""Guided, persisted setup for the local Telegram channel.

Mirrors the OpenClaw experience: a user creates a bot with @BotFather, runs one
command, pastes the token, and starts chatting with Hachi from Telegram — no
deployment and no public URL (Telegram long-polling reaches *out* from the
machine). The token is stored in the OS credential vault (so it survives
restarts without living in a shell profile), and the optional chat-id allowlist
is persisted to the global config.

Everything here is pure/persistence logic with no console I/O, so it is unit
tested without a network or a TTY; the interactive prompt lives in the CLI.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.credential_vault import CredentialVault
from hachi.core.paths import HachiPaths

#: Logical key the bot token is stored under in the credential vault. Matches the
#: ``<service>_<kind>`` convention used by ``slack_bot_token`` / ``notion_api_key``.
TELEGRAM_TOKEN_KEY = "telegram_bot_token"

#: Conventional environment variable, also accepted as a token source.
TELEGRAM_TOKEN_ENV = "TELEGRAM_BOT_TOKEN"


def parse_allowlist(raw: str | None) -> list[str]:
    """Split a user-entered allowlist into clean chat ids.

    Accepts comma- and/or whitespace-separated ids so ``"111, 222"`` and
    ``"111 222"`` both work. Pure.
    """
    if not raw:
        return []
    normalized = raw.replace(",", " ")
    return [token for token in normalized.split() if token]


def looks_like_token(token: str | None) -> bool:
    """Cheap shape check for a Telegram bot token (``<digits>:<rest>``).

    Catches the common paste mistake (an id or empty string) before we try to
    use it. Not a validation of liveness — that needs a network call.
    """
    if not token:
        return False
    head, sep, tail = token.partition(":")
    return bool(sep) and head.isdigit() and len(tail) >= 20


def resolve_token(
    explicit: str | None = None,
    *,
    vault: CredentialVault | None = None,
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve the bot token from the highest-priority available source.

    Priority: explicit ``--token`` flag → ``TELEGRAM_BOT_TOKEN`` env → vault.
    Returns ``None`` when no token is configured anywhere.
    """
    if explicit and explicit.strip():
        return explicit.strip()

    environ = env if env is not None else os.environ
    from_env = environ.get(TELEGRAM_TOKEN_ENV)
    if from_env and from_env.strip():
        return from_env.strip()

    vault = vault or CredentialVault()
    try:
        stored: str | None = vault.get_token(TELEGRAM_TOKEN_KEY)
        return stored
    except Exception:
        # get_token raises when the credential is absent — treat as "not set".
        return None


def save_token(token: str, *, vault: CredentialVault | None = None) -> None:
    """Persist the bot token to the credential vault."""
    cleaned = (token or "").strip()
    if not cleaned:
        raise ValueError("Telegram bot token cannot be empty")
    (vault or CredentialVault()).set_token(TELEGRAM_TOKEN_KEY, cleaned)


def load_allowlist(*, paths: HachiPaths | None = None) -> list[str]:
    """Return the persisted Telegram chat-id allowlist (empty = no restriction)."""
    config = load_effective_config(paths=paths)
    return list(config.channels.telegram.allowlist)


def save_allowlist(allowlist: list[str], *, paths: HachiPaths | None = None) -> None:
    """Persist the Telegram chat-id allowlist to the global config."""
    config = load_effective_config(paths=paths)
    config.channels.telegram.allowlist = [
        str(entry).strip() for entry in allowlist if str(entry).strip()
    ]
    write_global_config(config, paths=paths)
