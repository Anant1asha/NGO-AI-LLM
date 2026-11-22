"""Tests for the new gateway endpoints added in the backend-wiring pass.

Covers:
  Step 1 — GET /config limits round-trip (per_task_cap_usd / daily_cap_usd)
  Step 2 — POST /authoring/targets/{name}/source (CONTRACT-AUTHORING-SAVE)
  Step 3 — GET /og/graph (verify already-wired stub path still works)
  Step 4 — GET /spend (verify already-wired stub path still works)
  Step 5 — GET /capabilities includes ``configured`` field
  Step 6 — POST /memory/facts accepts all three group values
  Step 7 — Slash-command handling for /model, /help, /unknown
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _app(cp: GatewayControlPlane) -> TestClient:
    """Create a TestClient for the given control plane (no auth, no bind_host)."""
    return TestClient(create_gateway_app(cp))


# ---------------------------------------------------------------------------
# Step 1 — GET /config limits round-trip
# ---------------------------------------------------------------------------


class _FakeLimits:
    max_turn_cost_usd: float | None = 1.5
    max_session_cost_usd: float | None = 10.0
    max_session_tokens: int | None = None
    max_turn_tokens: int | None = None


class _FakeResolvedConfig:
    """Minimal ResolvedConfig double used to test get_config() mapping."""

    def __init__(self, per_task: float | None = None, daily: float | None = None) -> None:
        self.limits = SimpleNamespace(
            max_turn_cost_usd=per_task,
            max_daily_cost_usd=daily,
        )
        self.provider = SimpleNamespace(
            kind="anthropic",
            model="claude-haiku-4-5",
            base_url=None,
            api_key_ref=None,
            api_key_env=None,
            allowed_models=[],
            headers={},
        )
        self.providers: dict = {}
        self.permissions = SimpleNamespace(tier="guided")
        self.memory = SimpleNamespace(
            enable_session_history=True,
            enable_semantic_memory=True,
            backend="chroma",
            graph=False,
        )
        self.capabilities: dict = {}

    def model_dump(self, mode: str = "python", exclude_none: bool = True) -> dict:
        return {
            "provider": {
                "kind": self.provider.kind,
                "model": self.provider.model,
            },
            "limits": {},
        }


def test_get_config_includes_limits_frontend_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /config must return limits.per_task_cap_usd and limits.daily_cap_usd."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    fake_cfg = _FakeResolvedConfig(per_task=1.5, daily=10.0)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)

    result = runtime.get_config()
    assert "limits" in result
    assert result["limits"]["per_task_cap_usd"] == 1.5
    assert result["limits"]["daily_cap_usd"] == 10.0


def test_get_config_limits_null_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset caps must appear as None (not missing) so the frontend round-trips."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    fake_cfg = _FakeResolvedConfig(per_task=None, daily=None)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)

    result = runtime.get_config()
    assert result["limits"]["per_task_cap_usd"] is None
    assert result["limits"]["daily_cap_usd"] is None


def test_get_config_endpoint_includes_limits_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """The /config HTTP endpoint must return limits with the frontend-facing keys."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    fake_cfg = _FakeResolvedConfig(per_task=2.0, daily=20.0)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)

    cp = GatewayControlPlane(get_config=runtime.get_config)
    with _app(cp) as client:
        resp = client.get("/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "limits" in data
    assert data["limits"]["per_task_cap_usd"] == 2.0
    assert data["limits"]["daily_cap_usd"] == 20.0


# ---------------------------------------------------------------------------
# BB-57 — GET /config must mask secret refs / base URLs / raw headers
# ---------------------------------------------------------------------------


def _real_config_with_secrets():
    """A real ResolvedConfig populated with secret-shaped fields (BB-57 repro)."""
    from hachi.core.settings import CapabilityState, ProviderSettings, ResolvedConfig

    return ResolvedConfig(
        provider=ProviderSettings(
            kind="openai-compatible",
            model="gpt-4",
            base_url="https://api.example.com/v1",
            api_key_ref="vault:openai_key",
            api_key_env="OPENAI_API_KEY",
            headers={"Authorization": "Bearer sk-secret123"},
        ),
        providers={
            "backup": ProviderSettings(
                kind="anthropic",
                model="claude",
                base_url="https://backup.example.com",
                api_key_env="ANTHROPIC_API_KEY",
                api_key_ref="vault:anthropic_key",
            ),
        },
        capabilities={
            "google": CapabilityState(
                enabled=True, configured=True, secret_ref="vault:google_oauth"
            ),
        },
    )


def test_get_config_masks_provider_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /config must not leak api_key_ref/api_key_env/raw header values.

    BB-57: the raw ResolvedConfig.model_dump() was returned verbatim, unlike the
    already-masked GET /config/providers (provider_admin._mask_provider). Masking
    must be *consistent* with that endpoint: api_key_ref/api_key_env are dropped
    entirely (collapsed into a ``configured`` boolean) and header values are
    replaced with ``"***"``. ``base_url`` is not itself a secret and stays
    visible (matching /providers) so the UI can still display/edit it.
    """
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _real_config_with_secrets())

    result = runtime.get_config()

    for block in (result["provider"], result["providers"]["backup"]):
        assert "api_key_ref" not in block
        assert "api_key_env" not in block
        assert "configured" in block
        if block.get("headers"):
            assert all(v == "***" for v in block["headers"].values())

    assert result["capabilities"]["google"]["secret_ref"] != "vault:google_oauth"


def test_get_config_endpoint_masks_secrets_via_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """The GET /config HTTP endpoint must not echo secret refs or raw header values."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _real_config_with_secrets())

    cp = GatewayControlPlane(get_config=runtime.get_config)
    with _app(cp) as client:
        resp = client.get("/config")
    assert resp.status_code == 200
    body = resp.text
    assert "vault:openai_key" not in body
    assert "vault:anthropic_key" not in body
    assert "vault:google_oauth" not in body
    assert "sk-secret123" not in body


# ---------------------------------------------------------------------------
# Step 2 — POST /authoring/targets/{name}/source
# ---------------------------------------------------------------------------


def test_authoring_save_source_returns_ok() -> None:
    """POST /authoring/targets/{name}/source with valid content returns {"ok": true}."""

    def _stub(name: str, content: str) -> dict:
        return {"ok": True, "name": name}

    cp = GatewayControlPlane(authoring_save_source=_stub)
    with _app(cp) as client:
        resp = client.post(
            "/authoring/targets/brain-core.og/source",
            json={"content": "::node[example]\nfull = Some content\n"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["name"] == "brain-core.og"


def test_authoring_save_source_empty_content_returns_422() -> None:
    """POST /authoring/targets/{name}/source with empty content must be rejected."""

    def _stub(name: str, content: str) -> dict:  # pragma: no cover
        return {"ok": True, "name": name}

    cp = GatewayControlPlane(authoring_save_source=_stub)
    with _app(cp) as client:
        resp = client.post(
            "/authoring/targets/brain-core.og/source",
            json={"content": "   "},  # whitespace-only
        )
    assert resp.status_code == 422


def test_authoring_save_source_missing_content_field_returns_422() -> None:
    """POST body missing the ``content`` field must be rejected with 422."""
    cp = GatewayControlPlane(authoring_save_source=lambda n, c: {"ok": True, "name": n})
    with _app(cp) as client:
        resp = client.post("/authoring/targets/brain-core.og/source", json={})
    assert resp.status_code == 422


def test_authoring_save_source_not_attached_returns_503() -> None:
    """When authoring_save_source is not wired, route returns 503."""
    cp = GatewayControlPlane()  # authoring_save_source not wired
    with _app(cp) as client:
        resp = client.post(
            "/authoring/targets/brain-core.og/source",
            json={"content": "some content"},
        )
    assert resp.status_code == 503


def test_authoring_save_source_runtime_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> None:
    """_InProcessGatewayRuntime.authoring_save_source rejects parse failures for .og."""
    from hachi.cli.main import _InProcessGatewayRuntime
    from hachi.gateway.control_plane import GatewayUnavailableError

    runtime = _InProcessGatewayRuntime()

    # Mock _resolve_authoring_target_path to return a real temp file path.
    og_file = tmp_path / "brain-test.og"
    og_file.write_text("", encoding="utf-8")
    monkeypatch.setattr(runtime, "_resolve_authoring_target_path", lambda name: og_file)

    # Patch the og parser at the module level to simulate a parse failure.
    with patch("hachi.og_engine.parser.parse_og_file", side_effect=ValueError("bad syntax")):
        with pytest.raises(GatewayUnavailableError, match="does not parse"):
            runtime.authoring_save_source("brain-test.og", "bad content here")


def test_authoring_save_source_non_og_skips_parse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.fixture
) -> None:
    """authoring_save_source for non-.og targets skips parse validation."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    toml_file = tmp_path / "settings.toml"
    toml_file.write_text("[provider]\nkind = 'anthropic'\n", encoding="utf-8")

    monkeypatch.setattr(runtime, "_resolve_authoring_target_path", lambda name: toml_file)

    result = runtime.authoring_save_source("settings.toml", "[provider]\nkind = 'ollama'\n")
    assert result["ok"] is True
    assert toml_file.read_text(encoding="utf-8") == "[provider]\nkind = 'ollama'\n"


# ---------------------------------------------------------------------------
# Step 3 — GET /og/graph (already wired, verify shape)
# ---------------------------------------------------------------------------


def test_og_graph_returns_expected_node_shape() -> None:
    """GET /og/graph must return nodes with id, name, kind, index, dense, full, deps."""
    stub = {
        "nodes": [
            {
                "id": "brain",
                "name": "brain",
                "kind": "root",
                "index": 30,
                "dense": 220,
                "full": 1840,
                "deps": [],
            }
        ]
    }
    cp = GatewayControlPlane(get_og_graph=lambda: stub)
    with _app(cp) as client:
        resp = client.get("/og/graph")
    assert resp.status_code == 200
    node = resp.json()["nodes"][0]
    assert node["id"] == "brain"
    assert node["kind"] == "root"
    assert isinstance(node["index"], int)
    assert isinstance(node["full"], int)
    assert isinstance(node["deps"], list)


def test_og_graph_empty_when_not_attached() -> None:
    cp = GatewayControlPlane()
    with _app(cp) as client:
        resp = client.get("/og/graph")
    assert resp.status_code == 200
    assert resp.json() == {"nodes": []}


# ---------------------------------------------------------------------------
# Step 4 — GET /spend (already wired, verify shape)
# ---------------------------------------------------------------------------


def test_spend_returns_correct_shape() -> None:
    """GET /spend must return turns, tidies, models lists."""
    stub = {
        "turns": [{"n": 1, "inT": 0, "out": 512, "cost": 0.02}],
        "tidies": [{"ts": "12:00", "before": 10000, "after": 4000}],
        "models": [{"name": "claude-sonnet-4-6", "tokens": 15000, "cost": 0.1, "color": ""}],
    }
    cp = GatewayControlPlane(get_spend=lambda session_id: stub)
    with _app(cp) as client:
        resp = client.get("/spend")
    assert resp.status_code == 200
    data = resp.json()
    assert data["turns"][0]["n"] == 1
    assert data["tidies"][0]["before"] == 10000
    assert data["models"][0]["name"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Step 5 — GET /capabilities includes ``configured`` field
# ---------------------------------------------------------------------------


def test_capabilities_includes_configured_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /capabilities must include a ``configured`` boolean per item."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()

    fake_cfg = MagicMock()
    cap_state = MagicMock()
    cap_state.enabled = True
    cap_state.configured = False
    cap_state.secret_ref = None
    fake_cfg.capabilities = {"google": cap_state}

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_cfg)

    # connector_status import may fail in test env — suppress gracefully.
    monkeypatch.setattr(
        "hachi.cli.main._InProcessGatewayRuntime.capabilities",
        lambda self: [
            {
                "id": "google",
                "kind": "native_integration",
                "enabled": True,
                "configured": False,
                "secret_ref": None,
                "auth_type": "oauth2",
                "connected": False,
                "status": "disconnected",
            }
        ],
    )

    result = runtime.capabilities()
    item = result[0]
    assert "configured" in item
    assert "auth_type" in item
    assert "connected" in item
    assert "status" in item


def test_capabilities_configured_field_via_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /capabilities HTTP endpoint returns items with ``configured`` key."""

    def _stub() -> list:
        return [
            {
                "id": "slack",
                "kind": "native_integration",
                "enabled": False,
                "configured": True,
                "auth_type": "oauth2",
                "connected": True,
                "status": "connected",
            }
        ]

    cp = GatewayControlPlane(get_capabilities=_stub)
    with _app(cp) as client:
        resp = client.get("/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    item = data[0]
    assert item["id"] == "slack"
    assert item["configured"] is True
    assert item["auth_type"] == "oauth2"


# ---------------------------------------------------------------------------
# Step 6 — POST /memory/facts accepts all three group values
# ---------------------------------------------------------------------------


def test_memory_fact_add_core_memory_group() -> None:
    """POST /memory/facts with group=core_memory returns {id}."""

    def _stub(group: str, text: str) -> dict:
        return {"id": f"fact-{group}-abc123"}

    cp = GatewayControlPlane(add_memory_fact=_stub)
    with _app(cp) as client:
        resp = client.post("/memory/facts", json={"group": "core_memory", "text": "Test fact"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["id"] != ""


def test_memory_fact_add_user_profile_group() -> None:
    """POST /memory/facts with group=user_profile returns {id}."""

    def _stub(group: str, text: str) -> dict:
        return {"id": f"fact-{group}-xyz999"}

    cp = GatewayControlPlane(add_memory_fact=_stub)
    with _app(cp) as client:
        resp = client.post(
            "/memory/facts", json={"group": "user_profile", "text": "Likes dark mode"}
        )
    assert resp.status_code == 200
    assert "id" in resp.json()


def test_memory_fact_add_agent_profile_group() -> None:
    """POST /memory/facts with group=agent_profile returns {id}."""

    def _stub(group: str, text: str) -> dict:
        return {"id": "fact-agent-001"}

    cp = GatewayControlPlane(add_memory_fact=_stub)
    with _app(cp) as client:
        resp = client.post(
            "/memory/facts", json={"group": "agent_profile", "text": "I am a helpful agent"}
        )
    assert resp.status_code == 200
    assert resp.json()["id"] == "fact-agent-001"


def test_memory_fact_add_runtime_group_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """_InProcessGatewayRuntime._VAULT_GROUP_MAP must contain all three FE groups."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    expected_groups = {"core_memory", "user_profile", "agent_profile"}
    assert expected_groups == set(runtime._VAULT_GROUP_MAP.keys()), (
        f"_VAULT_GROUP_MAP missing groups: {expected_groups - set(runtime._VAULT_GROUP_MAP.keys())}"
    )


def test_memory_fact_add_all_three_groups_via_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each of the three FE group names must resolve to a vault upsert method."""
    from hachi.cli.main import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()

    # Build a fake vault with all three upsert methods.
    call_log: list[tuple[str, str]] = []

    def _make_upsert(method_name: str):
        def _upsert(text: str) -> str:
            call_log.append((method_name, text))
            return f"id-{method_name}"

        return _upsert

    fake_vault = MagicMock()
    fake_vault.upsert_fact = _make_upsert("upsert_fact")
    fake_vault.upsert_user_fact = _make_upsert("upsert_user_fact")
    fake_vault.upsert_agent_fact = _make_upsert("upsert_agent_fact")

    fake_agent = MagicMock()
    fake_agent.vault = fake_vault

    with runtime._agents_lock:
        runtime._agents["test-session"] = fake_agent

    for group, _expected_method in [
        ("core_memory", "upsert_fact"),
        ("user_profile", "upsert_user_fact"),
        ("agent_profile", "upsert_agent_fact"),
    ]:
        result = runtime.add_memory_fact(group, f"fact for {group}")
        assert "id" in result, f"No 'id' key for group {group}"
        assert result["id"] != "", f"Empty id for group {group}"

    called_methods = [m for m, _ in call_log]
    assert "upsert_fact" in called_methods
    assert "upsert_user_fact" in called_methods
    assert "upsert_agent_fact" in called_methods


# ---------------------------------------------------------------------------
# Step 7 — Slash-command handling
# ---------------------------------------------------------------------------


def _make_cp_with_chat() -> GatewayControlPlane:
    """Build a minimal control plane with connect + chat + events for message tests."""
    events_store: list = []

    def _connect(session_id: str, req) -> None:
        pass

    def _chat(session_id: str, prompt: str) -> str:
        return f"LLM reply to: {prompt}"

    def _events(session_id: str, after: int, limit: int):
        return events_store

    return GatewayControlPlane(
        on_connect=_connect,
        on_chat=_chat,
        read_events=_events,
    )


def test_slash_model_returns_model_info_without_llm() -> None:
    """/model command must return model info without calling the LLM."""
    cp = _make_cp_with_chat()

    # Create a session first.
    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={
                "client_id": "test-client",
                "surface": "test",
                "protocol_version": "1.0",
            },
        )
        assert create_resp.status_code == 200
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/model"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    # Synthetic slash replies omit session_id — the client already knows the
    # session it posted to, and echoing it risked a literal "None".
    assert "session_id" not in data
    # Must mention a model name (not LLM forwarding).
    response_text = data["response"].lower()
    assert "model" in response_text or "provider" in response_text


def test_slash_help_returns_command_list() -> None:
    """/help must list available commands."""
    cp = _make_cp_with_chat()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/help"},
        )
    assert resp.status_code == 200
    response_text = resp.json()["response"].lower()
    assert "/model" in response_text or "model" in response_text
    assert "/help" in response_text or "help" in response_text


def test_slash_unknown_returns_error_message() -> None:
    """An unknown /command must return an error message (not forward to LLM)."""
    cp = _make_cp_with_chat()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/frobnicator"},
        )
    assert resp.status_code == 200
    response_text = resp.json()["response"].lower()
    assert "unknown" in response_text or "frobnicator" in response_text


# ---------------------------------------------------------------------------
# H4 — /memory and /remember must be real slash commands, not "Unknown command"
# ---------------------------------------------------------------------------


def _make_cp_with_memory() -> tuple[GatewayControlPlane, list[tuple[str, str]], list[str]]:
    """Control plane wired with chat + memory recall + add_memory_fact handlers.

    Returns (control_plane, recall_calls, added_facts) so tests can assert on
    what the slash-command handler actually invoked.
    """
    recall_calls: list[tuple[str, str]] = []  # (query, top_k) as strings for easy asserts
    added_facts: list[str] = []

    def _connect(session_id: str, req) -> None:
        pass

    def _chat(session_id: str, prompt: str) -> str:
        return f"LLM reply to: {prompt}"

    def _events(session_id: str, after: int, limit: int):
        return []

    def _recall(query: str, top_k: int) -> list[dict]:
        recall_calls.append((query, str(top_k)))
        return [{"id": "fact-1", "raw_content": f"remembered: {query}", "category": "user_profile"}]

    def _add_fact(group: str, text: str) -> dict:
        added_facts.append(text)
        return {"id": "new-fact-id"}

    cp = GatewayControlPlane(
        on_connect=_connect,
        on_chat=_chat,
        read_events=_events,
        get_memory_recall=_recall,
        add_memory_fact=_add_fact,
    )
    return cp, recall_calls, added_facts


def test_slash_memory_returns_recall_results() -> None:
    """/memory <query> must call memory_recall and surface the results as text."""
    cp, recall_calls, _added = _make_cp_with_memory()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/memory favorite editor"},
        )
    assert resp.status_code == 200
    data = resp.json()
    response_text = data["response"]
    assert recall_calls, "/memory must invoke memory_recall(), not forward to the LLM"
    assert recall_calls[0][0] == "favorite editor"
    assert "remembered: favorite editor" in response_text


def test_slash_memory_without_query_returns_usage_hint() -> None:
    """/memory with no query argument must not crash or silently forward to the LLM."""
    cp, recall_calls, _added = _make_cp_with_memory()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/memory"},
        )
    assert resp.status_code == 200
    assert not recall_calls, "no query given — memory_recall must not be called"
    assert "usage" in resp.json()["response"].lower() or "query" in resp.json()["response"].lower()


def test_slash_remember_adds_a_fact() -> None:
    """/remember <fact> must call add_memory_fact, not forward to the LLM."""
    cp, _recall_calls, added_facts = _make_cp_with_memory()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/remember I prefer dark mode"},
        )
    assert resp.status_code == 200
    assert added_facts == ["I prefer dark mode"], (
        "/remember must call add_memory_fact() with the fact text, not forward to the LLM"
    )
    assert (
        "remember" in resp.json()["response"].lower() or "saved" in resp.json()["response"].lower()
    )


def test_slash_remember_without_fact_returns_usage_hint() -> None:
    """/remember with no fact text must not crash or silently forward to the LLM."""
    cp, _recall_calls, added_facts = _make_cp_with_memory()

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "/remember"},
        )
    assert resp.status_code == 200
    assert not added_facts, "no fact given — add_memory_fact must not be called"
    assert "usage" in resp.json()["response"].lower() or "fact" in resp.json()["response"].lower()


def test_normal_message_not_affected_by_slash_handler() -> None:
    """Normal (non-slash) messages must still be forwarded to the LLM."""
    forwarded_prompts: list[str] = []

    def _connect(session_id: str, req) -> None:
        pass

    def _chat(session_id: str, prompt: str) -> str:
        forwarded_prompts.append(prompt)
        return "LLM says hi"

    def _events(session_id: str, after: int, limit: int):
        return []

    cp = GatewayControlPlane(on_connect=_connect, on_chat=_chat, read_events=_events)

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        resp = client.post(
            f"/sessions/{session_id}/messages",
            json={"prompt": "Hello, what is the weather?"},
        )
    assert resp.status_code == 200
    assert forwarded_prompts == ["Hello, what is the weather?"]
    body = resp.json()
    assert body["response"] == "LLM says hi"
    # The normal (non-slash) path still echoes the real session_id — only the
    # synthetic slash replies omit it. response_model_exclude_none keeps it here.
    assert body.get("session_id") == session_id


def test_slash_not_sent_to_llm() -> None:
    """/model command must NOT invoke the LLM on_chat callback."""
    llm_called: list[str] = []

    def _connect(session_id: str, req) -> None:
        pass

    def _chat(session_id: str, prompt: str) -> str:
        llm_called.append(prompt)
        return "LLM response"

    def _events(session_id: str, after: int, limit: int):
        return []

    cp = GatewayControlPlane(on_connect=_connect, on_chat=_chat, read_events=_events)

    with _app(cp) as client:
        create_resp = client.post(
            "/sessions",
            json={"client_id": "test-client", "surface": "test", "protocol_version": "1.0"},
        )
        session_id = create_resp.json()["session_id"]

        client.post(f"/sessions/{session_id}/messages", json={"prompt": "/model"})

    assert llm_called == [], f"LLM was called with: {llm_called}"


# ---------------------------------------------------------------------------
# Step 8 — attachment_ids augment the forwarded prompt (file-platform wiring)
#
# The frontend uploads files (POST /files) and sends their ids alongside a
# message (POST /sessions/{id}/messages, body {prompt, attachment_ids}). The
# gateway's _build_augmented_prompt() looks each id up in the FileMetaStore and
# appends a context block before forwarding to the LLM. These tests exercise
# that wiring through the HTTP layer — _make_cp_with_chat() echoes the prompt it
# receives, so the response body reveals exactly what reached the LLM.
# ---------------------------------------------------------------------------


def _seed_file_meta(tmp_path, *, file_id, name, media_type, extracted_text_ref=None):
    """Insert one FileMeta row and return a fake HachiPaths pointing at tmp_path."""
    from hachi.core.files.store import FileMeta, FileMetaStore

    store = FileMetaStore(tmp_path / "files.db")
    store.save(
        FileMeta(
            file_id=file_id,
            name=name,
            media_type=media_type,
            size=42,
            extracted_text_ref=extracted_text_ref,
        )
    )
    return SimpleNamespace(files_db=tmp_path / "files.db", blobs_dir=tmp_path / "blobs")


def _post_message(client, prompt, attachment_ids):
    """Create a session and post a message; return the raw response."""
    create = client.post(
        "/sessions",
        json={"client_id": "t", "surface": "test", "protocol_version": "1.0"},
    )
    session_id = create.json()["session_id"]
    return client.post(
        f"/sessions/{session_id}/messages",
        json={"prompt": prompt, "attachment_ids": attachment_ids},
    )


def test_message_with_image_attachment_augments_prompt(tmp_path) -> None:
    """An image attachment_id appends a view_image hint to the forwarded prompt."""
    fake_paths = _seed_file_meta(
        tmp_path, file_id="img1", name="diagram.png", media_type="image/png"
    )
    cp = _make_cp_with_chat()
    with patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths):
        with _app(cp) as client:
            resp = _post_message(client, "what is this?", ["img1"])
    assert resp.status_code == 200
    reply = resp.json()["response"]
    # The original prompt AND the synthesized image block must reach the LLM.
    assert "what is this?" in reply
    assert "[Attached image: diagram.png]" in reply
    assert "view_image" in reply


def test_message_without_attachments_is_not_augmented() -> None:
    """No attachment_ids → the prompt is forwarded verbatim (regression guard)."""
    cp = _make_cp_with_chat()
    with _app(cp) as client:
        resp = _post_message(client, "plain question", [])
    assert resp.status_code == 200
    assert resp.json()["response"] == "LLM reply to: plain question"


def test_message_with_unknown_attachment_id_degrades_gracefully(tmp_path) -> None:
    """An unknown attachment_id is skipped, not fatal — prompt forwarded unchanged."""
    from hachi.core.files.store import FileMetaStore

    FileMetaStore(tmp_path / "files.db")  # empty store → get() returns None
    fake_paths = SimpleNamespace(files_db=tmp_path / "files.db", blobs_dir=tmp_path / "blobs")
    cp = _make_cp_with_chat()
    with patch("hachi.core.paths.get_hachi_paths", return_value=fake_paths):
        with _app(cp) as client:
            resp = _post_message(client, "hello", ["does-not-exist"])
    assert resp.status_code == 200
    assert resp.json()["response"] == "LLM reply to: hello"
