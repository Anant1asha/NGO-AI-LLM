"""Ingress idempotency for POST /sessions/{id}/messages (AUDIT P0-3 / Theme A).

Two layers:
  * the durable SessionStore key→response table (survives a gateway restart), and
  * the route wiring that replays a duplicate request instead of re-running the turn.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from hachi.core.session_store import SessionStore
from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

_CONNECT = {
    "client_id": "idem-client",
    "surface": "tui",
    "protocol_version": "1.0",
    "capabilities": ["events"],
}


# ---------------------------------------------------------------------------
# Durable store layer
# ---------------------------------------------------------------------------


def test_store_returns_none_for_unseen_key(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    assert store.get_idempotent_response("sess", "never-seen") is None


def test_store_round_trips_a_saved_response(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    payload = {"session_id": "sess", "response": "hello"}
    store.save_idempotent_response("sess", "k1", payload)
    assert store.get_idempotent_response("sess", "k1") == payload


def test_store_first_write_wins(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    store.save_idempotent_response("sess", "k1", {"response": "first"})
    store.save_idempotent_response("sess", "k1", {"response": "second"})  # ignored
    assert store.get_idempotent_response("sess", "k1") == {"response": "first"}


def test_store_keys_are_scoped_per_session(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    store.save_idempotent_response("sess-a", "k", {"response": "a"})
    assert store.get_idempotent_response("sess-b", "k") is None


def test_store_survives_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")
    SessionStore(db_path=db).save_idempotent_response("sess", "k", {"response": "persisted"})
    # A fresh store on the same file (simulating a restart) still replays it.
    assert SessionStore(db_path=db).get_idempotent_response("sess", "k") == {
        "response": "persisted"
    }


# ---------------------------------------------------------------------------
# Route layer
# ---------------------------------------------------------------------------


class _CountingChat:
    """on_chat double that records how many real turns actually ran."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _session_id: str, _prompt: str) -> str:
        self.calls += 1
        return f"reply-{self.calls}"


def _client_and_session(tmp_path: Path, chat: _CountingChat) -> tuple[TestClient, str]:
    cp = GatewayControlPlane(on_chat=chat)
    client = TestClient(create_gateway_app(cp))
    session_id = client.post("/sessions", json=_CONNECT).json()["session_id"]
    return client, session_id


def test_duplicate_post_with_same_key_replays_without_rerunning(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    chat = _CountingChat()
    with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
        client, session_id = _client_and_session(tmp_path, chat)
        headers = {"Idempotency-Key": "abc-123"}
        first = client.post(
            f"/sessions/{session_id}/messages", json={"prompt": "hi"}, headers=headers
        )
        second = client.post(
            f"/sessions/{session_id}/messages", json={"prompt": "hi"}, headers=headers
        )

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["response"] == "reply-1"
    assert second.json()["response"] == "reply-1"  # replayed, not "reply-2"
    assert chat.calls == 1  # the turn ran exactly once


def test_different_keys_run_independently(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    chat = _CountingChat()
    with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
        client, session_id = _client_and_session(tmp_path, chat)
        client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "hi"},
            headers={"Idempotency-Key": "k1"},
        )
        r2 = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "hi"},
            headers={"Idempotency-Key": "k2"},
        )
    assert r2.json()["response"] == "reply-2"
    assert chat.calls == 2


def test_no_key_means_no_idempotency(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    chat = _CountingChat()
    with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
        client, session_id = _client_and_session(tmp_path, chat)
        client.post(f"/sessions/{session_id}/messages", json={"prompt": "hi"})
        client.post(f"/sessions/{session_id}/messages", json={"prompt": "hi"})
    assert chat.calls == 2  # every keyless post runs


def test_body_field_key_is_honored_as_fallback(tmp_path: Path) -> None:
    store = SessionStore(db_path=str(tmp_path / "s.db"))
    chat = _CountingChat()
    with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
        client, session_id = _client_and_session(tmp_path, chat)
        body = {"prompt": "hi", "idempotency_key": "body-key"}
        first = client.post(f"/sessions/{session_id}/messages", json=body)
        second = client.post(f"/sessions/{session_id}/messages", json=body)
    assert first.json()["response"] == "reply-1"
    assert second.json()["response"] == "reply-1"
    assert chat.calls == 1
