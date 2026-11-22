"""Tests for GET /interactions and PUT /interactions/{id}/rating (eval loop E1).

Harness pattern mirrors test_ingress_idempotency.py:
  - patch ``hachi.gateway.fastapi_app._resolve_session_store`` to point at a real
    ``SessionStore`` backed by a tmp_path sqlite DB.
  - Use ``TestClient(create_gateway_app(cp))`` for HTTP.
  - Seed rows via ``store.log_interaction`` (the real write path) so round-trips
    are genuine, not stubs.

Ownership model in no-auth mode (all tests): ``_require_auth`` returns None, so
``_check_session_ownership`` is a no-op and every row is visible to every caller.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient  # noqa: F401 (used via TestClient)

from hachi.core.session_store import SessionStore
from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> SessionStore:
    """Return an isolated SessionStore backed by a temp file."""
    return SessionStore(db_path=str(tmp_path / "interactions.db"))


def _make_client(cp: GatewayControlPlane) -> TestClient:
    """Wrap a control-plane in a TestClient (no auth, no bind_host)."""
    return TestClient(create_gateway_app(cp))


def _seed_interaction(
    store: SessionStore,
    *,
    session_id: str = "sess-1",
    user_input: str = "hello",
    agent_output: str = "world",
    tool_calls: list[str] | None = None,
    memory_hits: list[str] | None = None,
    model_used: str = "claude-haiku-4-5",
    rating: str | None = None,
    notes: str | None = None,
) -> str:
    """Seed one interaction_log row and return its id."""
    return store.log_interaction(
        session_id=session_id,
        turn_id="turn-1",
        user_input=user_input,
        agent_output=agent_output,
        tool_calls=tool_calls,
        memory_hits=memory_hits,
        model_used=model_used,
        token_cost=0.001,
        tokens=128,
        rating=rating,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Test 1 — GET /interactions with session_id filter
# ---------------------------------------------------------------------------


class TestGetInteractionsWithSessionId:
    """GET /interactions?session_id=<id> returns only rows for that session."""

    def test_returns_rows_for_session(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        _seed_interaction(store, session_id="sess-a", user_input="ping", agent_output="pong")
        _seed_interaction(store, session_id="sess-b", user_input="other", agent_output="stuff")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"session_id": "sess-a"})

        assert resp.status_code == 200
        data = resp.json()
        assert "interactions" in data
        assert len(data["interactions"]) == 1
        row = data["interactions"][0]
        assert row["session_id"] == "sess-a"
        assert row["user_input"] == "ping"
        assert row["agent_output"] == "pong"

    def test_excludes_other_sessions(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        for i in range(3):
            _seed_interaction(store, session_id="sess-x", user_input=f"q{i}", agent_output="a")
        _seed_interaction(store, session_id="sess-y", user_input="unrelated", agent_output="nope")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"session_id": "sess-x"})

        data = resp.json()
        assert all(r["session_id"] == "sess-x" for r in data["interactions"])
        assert len(data["interactions"]) == 3

    def test_returns_empty_list_for_unknown_session(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"session_id": "does-not-exist"})

        assert resp.status_code == 200
        assert resp.json()["interactions"] == []

    def test_response_shape_has_required_fields(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        _seed_interaction(
            store,
            session_id="sess-z",
            tool_calls=["read_file", "list_files"],
            memory_hits=["fact-1"],
        )

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"session_id": "sess-z"})

        row = resp.json()["interactions"][0]
        assert "id" in row
        assert "session_id" in row
        assert "ts" in row
        assert isinstance(row["tool_calls"], list)
        assert row["tool_calls"] == ["read_file", "list_files"]
        assert row["memory_hits"] == ["fact-1"]
        assert row["model_used"] == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# Test 2 — GET /interactions without session_id (ownership filtering)
# ---------------------------------------------------------------------------


class TestGetInteractionsWithoutSessionId:
    """GET /interactions (no filter) returns all rows in no-auth mode."""

    def test_returns_rows_across_sessions_in_no_auth(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        _seed_interaction(store, session_id="s1")
        _seed_interaction(store, session_id="s2")
        _seed_interaction(store, session_id="s3")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions")

        assert resp.status_code == 200
        rows = resp.json()["interactions"]
        session_ids = {r["session_id"] for r in rows}
        assert "s1" in session_ids
        assert "s2" in session_ids
        assert "s3" in session_ids

    def test_limit_param_is_respected(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        for i in range(10):
            _seed_interaction(store, session_id="sess", user_input=f"q{i}", agent_output="a")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"limit": 3})

        assert len(resp.json()["interactions"]) == 3

    def test_limit_too_high_returns_422(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions", params={"limit": 9999})

        assert resp.status_code == 422

    def test_empty_store_returns_empty_list(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.get("/interactions")

        assert resp.status_code == 200
        assert resp.json()["interactions"] == []


# ---------------------------------------------------------------------------
# Test 3 — PUT /interactions/{id}/rating succeeds and persists (round-trip)
# ---------------------------------------------------------------------------


class TestRatingRoundTrip:
    """PUT /interactions/{id}/rating writes to the real store and reads back."""

    def test_rating_up_persists(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-r", user_input="q", agent_output="a")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                put_resp = client.put(
                    f"/interactions/{row_id}/rating",
                    json={"rating": "up"},
                )

        assert put_resp.status_code == 200
        assert put_resp.json()["ok"] is True

        # Verify persistence via the store directly.
        rows = store.get_interactions(session_id="sess-r")
        assert rows[0]["rating"] == "up"

    def test_rating_down_persists(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-r")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                client.put(f"/interactions/{row_id}/rating", json={"rating": "down"})

        rows = store.get_interactions(session_id="sess-r")
        assert rows[0]["rating"] == "down"

    def test_notes_persists_alongside_rating(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-notes")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                client.put(
                    f"/interactions/{row_id}/rating",
                    json={"rating": "up", "notes": "Excellent answer!"},
                )

        rows = store.get_interactions(session_id="sess-notes")
        assert rows[0]["notes"] == "Excellent answer!"

    def test_list_endpoint_reflects_updated_rating(self, tmp_path: Path) -> None:
        """Full round-trip: seed → rate → list → assert rating visible."""
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-rt")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                client.put(f"/interactions/{row_id}/rating", json={"rating": "up"})
                list_resp = client.get("/interactions", params={"session_id": "sess-rt"})

        rows = list_resp.json()["interactions"]
        assert rows[0]["rating"] == "up"


# ---------------------------------------------------------------------------
# Test 4 — PUT rating returns 404 for unknown interaction_id
# ---------------------------------------------------------------------------


class TestRating404:
    """PUT /interactions/{id}/rating returns 404 when the id does not exist."""

    def test_unknown_id_returns_404(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.put(
                    "/interactions/no-such-id/rating",
                    json={"rating": "down"},
                )

        assert resp.status_code == 404

    def test_404_detail_mentions_interaction_id(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.put(
                    "/interactions/ghost-row/rating",
                    json={"rating": "up"},
                )

        assert resp.status_code == 404
        body = resp.text
        assert "ghost-row" in body or "not found" in body.lower()


# ---------------------------------------------------------------------------
# Test 5 — Rating validation rejects bad values (422)
# ---------------------------------------------------------------------------


class TestRatingValidation:
    """Invalid ``rating`` values must be rejected with 422 (Pydantic Literal guard)."""

    @pytest.mark.parametrize("bad_value", ["thumbsup", "yes", "1", "", "UP", "DOWN"])
    def test_invalid_rating_value_returns_422(self, bad_value: str, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-val")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.put(
                    f"/interactions/{row_id}/rating",
                    json={"rating": bad_value},
                )

        assert resp.status_code == 422, (
            f"Expected 422 for rating={bad_value!r}, got {resp.status_code}"
        )

    def test_missing_rating_field_returns_422(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-missing")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.put(f"/interactions/{row_id}/rating", json={})

        assert resp.status_code == 422

    @pytest.mark.parametrize("good_value", ["up", "down"])
    def test_valid_rating_values_accepted(self, good_value: str, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        row_id = _seed_interaction(store, session_id="sess-good")

        cp = GatewayControlPlane()
        with patch("hachi.gateway.fastapi_app._resolve_session_store", return_value=store):
            with _make_client(cp) as client:
                resp = client.put(
                    f"/interactions/{row_id}/rating",
                    json={"rating": good_value},
                )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
