"""Tests for the shared env-aware outbound redaction helper and its use in the
scheduler's webhook delivery."""

from __future__ import annotations

import urllib.request

from hachi.cli.commands.schedule import _deliver_schedule_result
from hachi.core.secret_scanner import redact_outbound

_SECRET = "sk-ant-" + "a" * 40


# --------------------------------------------------------------------------- #
# redact_outbound (shared helper)
# --------------------------------------------------------------------------- #
def test_redact_outbound_redacts_by_default(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_ALLOW_OUTBOUND_SECRETS", raising=False)
    out, count = redact_outbound(f"the key is {_SECRET}")
    assert count == 1
    assert "[REDACTED SECRET]" in out and "sk-ant-" not in out


def test_redact_outbound_opt_out(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "true")
    out, count = redact_outbound(f"the key is {_SECRET}")
    assert count == 0 and _SECRET in out


# --------------------------------------------------------------------------- #
# scheduler webhook delivery
# --------------------------------------------------------------------------- #
class _Sched:
    def __init__(self, url: str) -> None:
        self.deliver_to = "webhook"
        self.webhook_url = url
        self.name = "nightly"


def _capture(monkeypatch) -> dict:
    captured: dict = {}
    monkeypatch.setattr(
        "hachi.core.net_guard.validate_outbound_url", lambda *_a, **_k: (True, "")
    )

    def fake_urlopen(req, timeout=15):
        captured["data"] = req.data
        return None

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return captured


def test_webhook_payload_redacts_secret(monkeypatch) -> None:
    monkeypatch.delenv("HACHI_ALLOW_OUTBOUND_SECRETS", raising=False)
    captured = _capture(monkeypatch)
    _deliver_schedule_result(_Sched("https://example.com/hook"), f"task done. key={_SECRET}")
    body = captured["data"].decode("utf-8")
    assert "[REDACTED SECRET]" in body and "sk-ant-" not in body


def test_webhook_opt_out_keeps_secret(monkeypatch) -> None:
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "true")
    captured = _capture(monkeypatch)
    _deliver_schedule_result(_Sched("https://example.com/hook"), f"key={_SECRET}")
    body = captured["data"].decode("utf-8")
    assert _SECRET in body
