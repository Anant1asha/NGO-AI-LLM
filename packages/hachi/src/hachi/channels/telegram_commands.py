"""Telegram bot command ↔ Hachi skill bridge.

When a Telegram user sends a ``/command`` that has no matching .og skill, this
module:

1. Writes a skill stub to ``<skills_dir>/telegram/learned/<slug>.og``
2. Calls Telegram's ``setMyCommands`` so the command appears in the bot menu
3. Prepends a one-line system note to the message so the agent can act on the
   new command without waiting for a session restart

Subsequent invocations pass through unmodified (the skill file is available to
every new session via ``load_directory``; the agent remembers the command from
prior context in the current session).
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from pathlib import Path
from typing import Any

from hachi.channels.base import InboundMessage
from hachi.core.paths import get_hachi_paths
from hachi.og_engine.engine import SkillEngine

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/{method}"

# Standard Telegram commands: never auto-create skills for these.
_BUILTIN_COMMANDS: frozenset[str] = frozenset({"start", "help", "settings", "cancel"})

# Telegram's hard cap on command name length (32 chars).
_MAX_CMD_LEN: int = 32


def parse_telegram_command(text: str) -> tuple[str, str]:
    """Extract ``(command_name, args)`` from a Telegram message.

    Strips the leading slash and optional ``@botname`` suffix.  Returns
    ``("", "")`` for non-command messages.

    Args:
        text: Raw message text from Telegram.

    Returns:
        Tuple of ``(command_name_lower, args_string)``.

    Examples::

        parse_telegram_command("/check_mail")          # → ("check_mail", "")
        parse_telegram_command("/check_mail@mybot hi") # → ("check_mail", "hi")
        parse_telegram_command("hello world")          # → ("", "")
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return "", ""
    # Telegram officially restricts commands to [a-z0-9_], but some clients
    # (and users) send hyphens; accept them and let _slugify normalise later.
    m = re.match(
        r"^/([A-Za-z0-9_-]{1,64})(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]*))?\s*$",
        stripped,
    )
    if not m:
        return "", ""
    return m.group(1).lower(), (m.group(2) or "").strip()


def _slugify(command_name: str) -> str:
    """Normalise a command name to a Hachi skill slug (snake_case, a-z0-9_)."""
    return re.sub(r"[^a-z0-9]+", "_", command_name.lower()).strip("_") or "command"


def _human_title(slug: str) -> str:
    """``'check_mail'`` → ``'Check Mail'``."""
    return " ".join(w.capitalize() for w in slug.split("_"))


class TelegramCommandRegistry:
    """Auto-register Telegram ``/commands`` as Hachi ``.og`` skills.

    Lifecycle of a new command:

    1. User sends ``/check_mail`` to the bot.
    2. :meth:`intercept_messages` detects the unknown command.
    3. A skill stub is written to ``<skills_dir>/telegram/learned/check_mail.og``.
    4. Telegram's ``setMyCommands`` is called to add the command to the bot menu.
    5. The message is prefixed with a brief system note so the running agent can
       fulfil the command without needing a restart.

    Args:
        token: Telegram bot token (used to call ``setMyCommands``).
        skills_dir: Root skills directory.  Command skills land under
            ``<skills_dir>/telegram/learned/``.  Defaults to the global
            Hachi skills directory.
    """

    def __init__(self, token: str, skills_dir: Path | None = None) -> None:
        self._token = token
        base = skills_dir or get_hachi_paths().skills_dir
        self._telegram_dir: Path = base / "telegram"
        self._learned_dir: Path = self._telegram_dir / "learned"
        self._learned_dir.mkdir(parents=True, exist_ok=True)
        # Lightweight engine: tracks what's been written, used for upsert_skill.
        self._write_engine = SkillEngine()
        self._write_engine.load_directory(self._telegram_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def skill_exists(self, slug: str) -> bool:
        """Return True when an .og file for *slug* already exists on disk."""
        return (self._learned_dir / f"{slug}.og").exists()

    def ensure_command(self, command_name: str) -> dict[str, Any]:
        """Create a skill for *command_name* if one doesn't exist yet.

        Args:
            command_name: Raw command name without leading slash.

        Returns:
            ``{"created": bool, "slug": str, "path": str, "is_builtin": bool}``
        """
        slug = _slugify(command_name)

        if command_name.lower() in _BUILTIN_COMMANDS or slug in _BUILTIN_COMMANDS:
            return {"created": False, "slug": slug, "path": "", "is_builtin": True}

        if len(slug) > _MAX_CMD_LEN:
            logger.warning(
                "Command slug '%s' exceeds Telegram's %d-char limit — skipped",
                slug,
                _MAX_CMD_LEN,
            )
            return {"created": False, "slug": slug, "path": "", "is_builtin": False}

        path = str(self._learned_dir / f"{slug}.og")
        if self.skill_exists(slug):
            return {"created": False, "slug": slug, "path": path, "is_builtin": False}

        result = self._create_skill(slug, command_name)
        created = result.get("status") == "created"

        if created:
            self._sync_commands_to_telegram()

        return {"created": created, "slug": slug, "path": path, "is_builtin": False}

    def intercept_messages(self, messages: list[InboundMessage]) -> list[InboundMessage]:
        """Intercept command messages; create skills and annotate as needed.

        Non-command messages and built-in commands are returned unchanged.
        For a *new* command a one-line system note is prepended to the message
        text so the agent knows about the just-created skill.

        Args:
            messages: Parsed inbound messages from ``TelegramAdapter.poll_once``.

        Returns:
            The same list, possibly with modified ``.text`` on new-command messages.
        """
        out: list[InboundMessage] = []
        for msg in messages:
            cmd_name, _args = parse_telegram_command(msg.text)
            if not cmd_name:
                out.append(msg)
                continue

            result = self.ensure_command(cmd_name)

            if result["is_builtin"] or not result["created"]:
                out.append(msg)
                continue

            # New skill was just created — annotate the message.
            slug = result["slug"]
            note = (
                f"[System: /{cmd_name} is a new Hachi command — "
                f"skill '{slug}' was just registered. "
                f"Use your tools to fulfil the request now.]\n"
            )
            out.append(
                InboundMessage(
                    channel=msg.channel,
                    sender_id=msg.sender_id,
                    sender_name=msg.sender_name,
                    text=note + msg.text,
                )
            )
        return out

    def list_commands(self) -> list[dict[str, str]]:
        """Return all registered custom commands as ``[{command, path}]``."""
        return [
            {"command": p.stem, "path": str(p)}
            for p in sorted(self._learned_dir.glob("*.og"))
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_skill(self, slug: str, command_name: str) -> dict[str, Any]:
        words = slug.split("_")

        # Build a deduplicated keyword list
        raw_keywords = words + ["telegram", "command", slug]
        seen: set[str] = set()
        keywords: list[str] = []
        for k in raw_keywords:
            if k not in seen:
                seen.add(k)
                keywords.append(k)

        # Dense block: short keyword phrase, well under the 30-token budget
        dense = ", ".join(words[:2]) + " | tg cmd"

        full_desc = (
            f"Telegram custom command: /{command_name}\n\n"
            f"When invoked, use available tools to {' '.join(words)} for the user. "
            "Check relevant integrations (email, calendar, tasks, etc.) and "
            "return a clear, concise response."
        )

        return self._write_engine.upsert_skill(
            name=slug,
            keywords=keywords,
            dense=dense,
            full=full_desc,
            role="skill",
            scope="all",
            domain="telegram",
            reason=f"auto-registered via Telegram command /{command_name}",
            skills_dir=self._telegram_dir,
        )

    def _tg_call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        url = _TG_API.format(token=self._token, method=method)
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
        return result if isinstance(result, dict) else {}

    def _sync_commands_to_telegram(self) -> None:
        """Push all registered command slugs to Telegram's ``setMyCommands`` API."""
        try:
            commands = [
                {
                    "command": p.stem,
                    "description": _human_title(p.stem)[:256],
                }
                for p in sorted(self._learned_dir.glob("*.og"))
                if len(p.stem) <= _MAX_CMD_LEN and p.stem not in _BUILTIN_COMMANDS
            ]
            if commands:
                self._tg_call("setMyCommands", {"commands": commands})
                logger.info("Synced %d command(s) to Telegram bot menu", len(commands))
        except Exception as exc:
            logger.warning("Could not sync commands to Telegram: %s", exc)
