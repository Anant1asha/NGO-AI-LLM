"""The outbound messaging tools must redact secrets before sending (with an
env opt-out for power users)."""

from __future__ import annotations

from hachi.core.idempotency import IdempotencyGuard
from hachi.tools.messaging_tools import _make_send_discord, _make_send_slack

_KEY = "sk-ant-" + "a" * 40


class _FakeSlack:
    def __init__(self) -> None:
        self.sent_text: str | None = None

    def is_configured(self) -> bool:
        return True

    def send(self, text: str, channel: str = "") -> dict:
        self.sent_text = text
        return {"target": "#ops"}


class _FakeDiscord:
    def __init__(self) -> None:
        self.sent_text: str | None = None

    def is_configured(self) -> bool:
        return True

    def send(self, content: str, channel: str = "") -> dict:
        self.sent_text = content
        return {"target": "123"}


def test_slack_redacts_secret_before_sending(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_ALLOW_OUTBOUND_SECRETS", raising=False)
    fake = _FakeSlack()
    send = _make_send_slack(fake, IdempotencyGuard())
    out = send(f"the token is {_KEY}", "#ops")
    assert "sk-ant-" not in fake.sent_text
    assert "[REDACTED SECRET]" in fake.sent_text
    assert "redacted" in out


def test_discord_redacts_secret_before_sending(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_ALLOW_OUTBOUND_SECRETS", raising=False)
    fake = _FakeDiscord()
    send = _make_send_discord(fake, IdempotencyGuard())
    out = send(f"creds: {_KEY}")
    assert "sk-ant-" not in fake.sent_text
    assert "redacted" in out


def test_clean_message_has_no_redaction_note(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_ALLOW_OUTBOUND_SECRETS", raising=False)
    fake = _FakeSlack()
    out = _make_send_slack(fake, IdempotencyGuard())("just a normal status update", "#ops")
    assert fake.sent_text == "just a normal status update"
    assert "redacted" not in out


def test_env_opt_out_disables_redaction(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "true")
    fake = _FakeSlack()
    _make_send_slack(fake, IdempotencyGuard())(f"the token is {_KEY}", "#ops")
    assert _KEY in fake.sent_text  # passed through unredacted
