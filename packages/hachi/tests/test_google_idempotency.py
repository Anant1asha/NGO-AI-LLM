"""In-turn idempotency for Google write tools (AUDIT Theme A — connector hardening).

The opt-in guard lives in ``GoogleHTTPClient.post``: a duplicate POST carrying the same
``idempotency_key`` replays the prior response instead of re-sending, so an LLM retry or
tool-pool re-dispatch within a turn cannot double-send an email or double-create an event.
Reads / batch POSTs pass no key and are never deduped.
"""

from __future__ import annotations

import pytest

from hachi.core.idempotency import IdempotencyGuard
from hachi.integrations.google.client import GoogleHTTPClient
from hachi.integrations.google.gmail import GmailService


def _client() -> GoogleHTTPClient:
    # Bypass OAuthManager / secret-store construction; we only exercise post()'s guard.
    c = GoogleHTTPClient.__new__(GoogleHTTPClient)
    c._idem_guard = IdempotencyGuard()
    c.approver = None
    return c


# -- client-level mechanism --------------------------------------------------


def test_keyed_post_sends_once_and_replays(monkeypatch) -> None:
    c = _client()
    sends: list[str] = []
    monkeypatch.setattr(c, "_post_raw", lambda ep, jd, p: (sends.append(ep), {"id": "m1"})[1])
    r1 = c.post("/send", json_data={"raw": "x"}, idempotency_key="k")
    r2 = c.post("/send", json_data={"raw": "x"}, idempotency_key="k")
    assert r1 == {"id": "m1"}
    assert r2 == {"id": "m1"}  # replayed, not re-sent
    assert sends == ["/send"]  # the API send happened exactly once


def test_post_without_key_is_never_deduped(monkeypatch) -> None:
    c = _client()
    sends: list[str] = []
    monkeypatch.setattr(c, "_post_raw", lambda ep, jd, p: (sends.append(ep), {})[1])
    c.post("/freeBusy", json_data={"a": 1})  # a read-via-POST must always run
    c.post("/freeBusy", json_data={"a": 1})
    assert len(sends) == 2


def test_failed_keyed_post_stays_retryable(monkeypatch) -> None:
    c = _client()
    sends: list[str] = []

    def boom(ep, jd, p):
        sends.append(ep)
        raise RuntimeError("api down")

    monkeypatch.setattr(c, "_post_raw", boom)
    with pytest.raises(RuntimeError):
        c.post("/send", idempotency_key="k")
    with pytest.raises(RuntimeError):
        c.post("/send", idempotency_key="k")  # not suppressed — a real retry re-attempts
    assert len(sends) == 2


def test_different_keys_send_independently(monkeypatch) -> None:
    c = _client()
    sends: list[str] = []
    monkeypatch.setattr(c, "_post_raw", lambda ep, jd, p: (sends.append(ep), {})[1])
    c.post("/send", idempotency_key="k1")
    c.post("/send", idempotency_key="k2")
    assert len(sends) == 2


# -- leaf-tool wiring: send_email dedups a retried identical send ------------


class _ApproveAll:
    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        return (True, "ok")


def test_send_email_dedups_identical_retry(monkeypatch) -> None:
    c = _client()
    c.approver = _ApproveAll()  # auto-approve the outbound gate
    sends: list[tuple] = []
    monkeypatch.setattr(c, "_post_raw", lambda ep, jd, p: (sends.append((ep, jd)), {"id": "m1"})[1])
    svc = GmailService(client=c)
    out1 = svc.send_email(to="a@b.com", subject="Hi", body="Hello")
    out2 = svc.send_email(to="a@b.com", subject="Hi", body="Hello")  # retry, same content
    assert "sent" in out1.lower()
    assert "sent" in out2.lower()  # second still reports success (replayed)
    assert len(sends) == 1  # the actual Gmail send happened exactly once


def test_send_email_distinct_content_sends_again(monkeypatch) -> None:
    c = _client()
    c.approver = _ApproveAll()
    sends: list[tuple] = []
    monkeypatch.setattr(c, "_post_raw", lambda ep, jd, p: (sends.append((ep, jd)), {})[1])
    svc = GmailService(client=c)
    svc.send_email(to="a@b.com", subject="Hi", body="Hello")
    svc.send_email(to="a@b.com", subject="Hi", body="A different body")
    assert len(sends) == 2
