"""Tests for Telegram /command → Hachi skill auto-registration."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hachi.channels.base import InboundMessage
from hachi.channels.telegram import TelegramAdapter
from hachi.channels.telegram_commands import (
    _BUILTIN_COMMANDS,
    TelegramCommandRegistry,
    _slugify,
    parse_telegram_command,
)

# ---------------------------------------------------------------------------
# parse_telegram_command — pure function, no I/O
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected_cmd, expected_args",
    [
        ("/check_mail", "check_mail", ""),
        ("/check-mail", "check-mail", ""),  # raw hyphen preserved in parse
        ("/CHECK_MAIL", "check_mail", ""),  # lowercased
        ("/check_mail@mybot", "check_mail", ""),  # @suffix stripped
        ("/check_mail@mybot hello world", "check_mail", "hello world"),
        ("/check_mail some args here", "check_mail", "some args here"),
        ("hello there", "", ""),  # not a command
        ("/", "", ""),  # bare slash
        ("  /check_mail  ", "check_mail", ""),  # leading/trailing whitespace
    ],
)
def test_parse_telegram_command(text, expected_cmd, expected_args):
    cmd, args = parse_telegram_command(text)
    assert cmd == expected_cmd
    assert args == expected_args


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("check_mail", "check_mail"),
        ("check-mail", "check_mail"),
        ("CheckMail", "checkmail"),
        ("check mail", "check_mail"),
        ("123go", "123go"),
    ],
)
def test_slugify(name, expected):
    assert _slugify(name) == expected


# ---------------------------------------------------------------------------
# TelegramCommandRegistry (using tmp_path, no network)
# ---------------------------------------------------------------------------


def _make_registry(tmp_path: Path, token: str = "test-token") -> TelegramCommandRegistry:
    reg = TelegramCommandRegistry(token=token, skills_dir=tmp_path)
    return reg


def test_registry_creates_skill_for_new_command(tmp_path):
    reg = _make_registry(tmp_path)
    result = reg.ensure_command("check_mail")

    assert result["created"] is True
    assert result["slug"] == "check_mail"
    assert result["is_builtin"] is False
    skill_path = Path(result["path"])
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "check_mail" in content
    assert "telegram" in content


def test_registry_skips_existing_skill(tmp_path):
    reg = _make_registry(tmp_path)
    r1 = reg.ensure_command("check_mail")
    assert r1["created"] is True

    r2 = reg.ensure_command("check_mail")
    assert r2["created"] is False
    assert r2["slug"] == "check_mail"


@pytest.mark.parametrize("cmd", sorted(_BUILTIN_COMMANDS))
def test_registry_skips_builtin_commands(tmp_path, cmd):
    reg = _make_registry(tmp_path)
    result = reg.ensure_command(cmd)
    assert result["is_builtin"] is True
    assert result["created"] is False
    # No .og file should be created
    assert not list((tmp_path / "telegram" / "learned").glob("*.og")) or not any(
        p.stem == cmd for p in (tmp_path / "telegram" / "learned").glob("*.og")
    )


def test_registry_hyphenated_command_normalised(tmp_path):
    reg = _make_registry(tmp_path)
    result = reg.ensure_command("check-mail")
    assert result["slug"] == "check_mail"
    assert result["created"] is True


def test_registry_skill_file_has_valid_content(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_command("plan_day")
    path = tmp_path / "telegram" / "learned" / "plan_day.og"
    assert path.exists()
    content = path.read_text()
    # Must have required .og sections
    assert "::meta" in content
    assert "::node" in content
    assert "::index" in content
    assert "plan" in content
    assert "day" in content


def test_registry_list_commands(tmp_path):
    reg = _make_registry(tmp_path)
    reg.ensure_command("check_mail")
    reg.ensure_command("plan_day")
    cmds = reg.list_commands()
    slugs = [c["command"] for c in cmds]
    assert "check_mail" in slugs
    assert "plan_day" in slugs


def test_registry_calls_set_my_commands_on_new_command(tmp_path):
    reg = _make_registry(tmp_path)
    called_with: list[Any] = []

    def fake_tg_call(method, params):
        called_with.append((method, params))
        return {"ok": True}

    reg._tg_call = fake_tg_call
    reg.ensure_command("check_mail")

    set_cmd_calls = [args for method, args in called_with if method == "setMyCommands"]
    assert len(set_cmd_calls) == 1
    commands = set_cmd_calls[0]["commands"]
    assert any(c["command"] == "check_mail" for c in commands)


def test_registry_does_not_call_set_my_commands_for_existing(tmp_path):
    reg = _make_registry(tmp_path)
    called_with: list[Any] = []

    def fake_tg_call(method, params):
        called_with.append(method)
        return {"ok": True}

    reg._tg_call = fake_tg_call
    reg.ensure_command("check_mail")
    called_with.clear()  # reset after first creation

    reg.ensure_command("check_mail")  # second call — no-op
    assert "setMyCommands" not in called_with


def test_registry_sync_failure_does_not_raise(tmp_path):
    reg = _make_registry(tmp_path)

    def broken_tg_call(method, params):
        raise OSError("network error")

    reg._tg_call = broken_tg_call
    # Should not raise; warning is logged internally
    reg.ensure_command("check_mail")


# ---------------------------------------------------------------------------
# intercept_messages
# ---------------------------------------------------------------------------


def _msg(text: str, sender_id: str = "42") -> InboundMessage:
    return InboundMessage(channel="telegram", sender_id=sender_id, text=text, sender_name="user")


def test_intercept_annotates_new_command(tmp_path):
    reg = _make_registry(tmp_path)
    reg._tg_call = lambda m, p: {"ok": True}  # suppress network

    msgs = reg.intercept_messages([_msg("/check_mail")])
    assert len(msgs) == 1
    assert "check_mail" in msgs[0].text
    assert "System:" in msgs[0].text
    # Original command text is preserved after the note
    assert "/check_mail" in msgs[0].text


def test_intercept_does_not_annotate_existing_command(tmp_path):
    reg = _make_registry(tmp_path)
    reg._tg_call = lambda m, p: {"ok": True}

    reg.ensure_command("check_mail")  # pre-create

    msgs = reg.intercept_messages([_msg("/check_mail")])
    assert msgs[0].text == "/check_mail"  # unchanged


def test_intercept_passthrough_non_command(tmp_path):
    reg = _make_registry(tmp_path)
    msgs = reg.intercept_messages([_msg("hello")])
    assert msgs[0].text == "hello"


def test_intercept_passthrough_builtin(tmp_path):
    reg = _make_registry(tmp_path)
    msgs = reg.intercept_messages([_msg("/start")])
    assert msgs[0].text == "/start"


def test_intercept_mixed_batch(tmp_path):
    reg = _make_registry(tmp_path)
    reg._tg_call = lambda m, p: {"ok": True}

    batch = [
        _msg("hello"),
        _msg("/check_mail"),
        _msg("/start"),
    ]
    out = reg.intercept_messages(batch)
    assert len(out) == 3
    assert out[0].text == "hello"
    assert "System:" in out[1].text  # new command annotated
    assert out[2].text == "/start"  # builtin unchanged


# ---------------------------------------------------------------------------
# TelegramAdapter integration with command_registry
# ---------------------------------------------------------------------------


def _fake_updates(texts: list[str]) -> dict[str, Any]:
    updates = []
    for i, text in enumerate(texts):
        updates.append(
            {
                "update_id": i + 1,
                "message": {
                    "text": text,
                    "chat": {"id": "99"},
                    "from": {"username": "tester"},
                },
            }
        )
    return {"ok": True, "result": updates}


def test_adapter_uses_registry_on_poll(tmp_path):
    reg = _make_registry(tmp_path)
    reg._tg_call = lambda m, p: {"ok": True}

    adapter = TelegramAdapter("fake-token", command_registry=reg)
    raw_response = _fake_updates(["/plan_day", "just a message"])

    with patch.object(adapter, "_call", return_value=raw_response):
        messages = adapter.poll_once()

    assert len(messages) == 2
    # First message (/plan_day) should have annotation
    assert "System:" in messages[0].text
    # Second message is plain text — unchanged
    assert messages[1].text == "just a message"


def test_adapter_without_registry_passes_through(tmp_path):
    adapter = TelegramAdapter("fake-token")
    raw_response = _fake_updates(["/check_mail"])

    with patch.object(adapter, "_call", return_value=raw_response):
        messages = adapter.poll_once()

    assert len(messages) == 1
    # No annotation — no registry configured
    assert messages[0].text == "/check_mail"
