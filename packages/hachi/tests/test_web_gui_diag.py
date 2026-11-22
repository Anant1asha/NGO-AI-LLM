"""Regression tests for the web-GUI diagnosis batch (BB-13 / BB-14).

BB-13 — the conversation dropdown was empty on a fresh server start because
        ``_InProcessGatewayRuntime.recent_sessions`` returned ``[]`` whenever no
        agent had booted yet, instead of reading the persisted SessionStore.

BB-14 — a Tavily API key saved through the Integrations UI lands under the
        namespaced key ``apikey.tavily.tavily_api_key`` but the search provider
        and the "Test Connection" endpoint only read the bare ``tavily_api_key``,
        so both reported the key as missing.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# BB-13 — recent_sessions reads the store with no live agent
# ---------------------------------------------------------------------------


def _make_paths(tmp_path: Path):
    from hachi.core.paths import HachiPaths

    paths = HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
    for d in (paths.config_dir, paths.data_dir, paths.cache_dir, paths.state_dir):
        d.mkdir(parents=True, exist_ok=True)
    return paths


class TestRecentSessionsNoAgent:
    def test_returns_persisted_sessions_when_no_agent_booted(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from hachi.core.session_store import SessionStore

        paths = _make_paths(tmp_path)
        # Point the runtime at our temp sessions.db and seed one real session.
        monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)

        store = SessionStore(db_path=str(paths.sessions_db))
        session_id = store.start_session(model="test-model")
        store.log_message(session_id, "user", "hello there")
        store.shutdown()

        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()  # no agents booted
        assert runtime._agents == {}

        result = runtime.recent_sessions(10)
        ids = [s.get("id") or s.get("session_id") for s in result]
        assert session_id in ids, f"seeded session {session_id} missing from {ids}"

    def test_empty_store_returns_empty_list(self, tmp_path: Path, monkeypatch) -> None:
        paths = _make_paths(tmp_path)
        monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: paths)

        from hachi.cli.main import _InProcessGatewayRuntime

        runtime = _InProcessGatewayRuntime()
        assert runtime.recent_sessions(10) == []


# ---------------------------------------------------------------------------
# BB-14 — Tavily key resolution honours the namespaced credential key
# ---------------------------------------------------------------------------


class _FakeStore:
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    def get(self, key: str) -> str | None:
        return self._data.get(key)


class TestTavilyKeyResolution:
    def test_resolves_namespaced_apikey_scheme(self, monkeypatch) -> None:
        from hachi.core.providers import tavily_provider

        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        store = _FakeStore({"apikey.tavily.tavily_api_key": "tvly-from-ui"})
        assert tavily_provider._resolve_api_key(store) == "tvly-from-ui"

    def test_resolves_bare_key(self, monkeypatch) -> None:
        from hachi.core.providers import tavily_provider

        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        store = _FakeStore({"tavily_api_key": "tvly-bare"})
        assert tavily_provider._resolve_api_key(store) == "tvly-bare"

    def test_namespaced_key_takes_precedence_over_env(self, monkeypatch) -> None:
        from hachi.core.providers import tavily_provider

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-env")
        store = _FakeStore({"apikey.tavily.tavily_api_key": "tvly-from-ui"})
        assert tavily_provider._resolve_api_key(store) == "tvly-from-ui"

    def test_env_fallback_when_store_empty(self, monkeypatch) -> None:
        from hachi.core.providers import tavily_provider

        monkeypatch.setenv("TAVILY_API_KEY", "tvly-env")
        assert tavily_provider._resolve_api_key(_FakeStore({})) == "tvly-env"

    def test_returns_none_when_nothing_set(self, monkeypatch) -> None:
        from hachi.core.providers import tavily_provider

        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        assert tavily_provider._resolve_api_key(_FakeStore({})) is None


class TestTavilyTestConnectionEndpoint:
    """The Integrations 'Test Connection' endpoint must find a UI-saved key."""

    def test_test_connection_finds_namespaced_key(self, monkeypatch) -> None:
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from hachi.gateway.control_plane import GatewayControlPlane
        from hachi.gateway.fastapi_app import create_gateway_app

        # In-memory vault holding the key under the namespaced scheme only.
        vault = MagicMock()
        vault.get_token.side_effect = lambda name: (
            "tvly-stored" if name == "apikey.tavily.tavily_api_key" else None
        )
        # _resolve_secret imports CredentialVault lazily from its source module.
        monkeypatch.setattr(
            "hachi.core.credential_vault.CredentialVault",
            lambda *a, **k: vault,
            raising=False,
        )

        # Mock the outbound Tavily call so the test never hits the network.
        resp = MagicMock()
        resp.status_code = 200
        monkeypatch.setattr("httpx.post", lambda *a, **k: resp)

        client = TestClient(create_gateway_app(GatewayControlPlane()))
        r = client.post("/integrations/tavily/credentials/test")
        assert r.status_code == 200
        body = r.json()
        assert body.get("message") != "No Tavily API key stored.", body
        assert body.get("ok") is True, body
