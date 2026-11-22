"""Tests for the Google Workspace tool registration wire-up.

All tests are fully offline — no real OAuth calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRegistry:
    """Minimal ToolRegistry stub that records register() calls."""

    def __init__(self) -> None:
        self._tools: dict = {}
        self._groups: dict = {}

    def register(self, schema: dict, fn, group: str | None = None) -> None:
        name = schema.get("name", "?")
        self._tools[name] = {"schema": schema, "fn": fn, "group": group}
        if group:
            self._groups[name] = group


def _make_fake_hub(tool_names: list[str]) -> MagicMock:
    hub = MagicMock()

    def _register_tools(registry: _FakeRegistry) -> None:
        for name in tool_names:
            registry.register(
                {
                    "name": name,
                    "description": f"stub {name}",
                    "input_schema": {"type": "object", "properties": {}},
                },
                lambda: "ok",
            )

    hub.register_tools.side_effect = _register_tools
    return hub


# ---------------------------------------------------------------------------
# Unit tests for register_google_tools
# ---------------------------------------------------------------------------


class TestRegisterGoogleToolsNoCredentials:
    def test_returns_false_when_no_client_id(self, monkeypatch) -> None:
        # Force "not configured" deterministically: the resolver also reads a project
        # .env, so clearing only os.environ is no longer sufficient in a repo that ships one.
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: None)
        from hachi.tools.google_tools import register_google_tools

        registry = _FakeRegistry()
        result = register_google_tools(registry)
        assert result is False

    def test_registers_stub_when_no_client_id(self, monkeypatch) -> None:
        # Force "not configured" deterministically: the resolver also reads a project
        # .env, so clearing only os.environ is no longer sufficient in a repo that ships one.
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: None)
        from hachi.tools.google_tools import register_google_tools

        registry = _FakeRegistry()
        register_google_tools(registry)
        assert "google_not_configured" in registry._tools

    def test_stub_tagged_google_group(self, monkeypatch) -> None:
        # Force "not configured" deterministically: the resolver also reads a project
        # .env, so clearing only os.environ is no longer sufficient in a repo that ships one.
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: None)
        from hachi.tools.google_tools import register_google_tools

        registry = _FakeRegistry()
        register_google_tools(registry)
        assert registry._tools["google_not_configured"]["group"] == "google"

    def test_stub_returns_helpful_message(self, monkeypatch) -> None:
        # Force "not configured" deterministically: the resolver also reads a project
        # .env, so clearing only os.environ is no longer sufficient in a repo that ships one.
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.setattr("hachi.core.oauth._google_client_id", lambda: None)
        from hachi.tools.google_tools import register_google_tools

        registry = _FakeRegistry()
        register_google_tools(registry)
        fn = registry._tools["google_not_configured"]["fn"]
        msg = fn()
        assert "GOOGLE_CLIENT_ID" in msg


class TestRegisterGoogleToolsWithCredentials:
    def test_returns_true_when_client_id_set(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
        fake_hub = _make_fake_hub(["google_send_email", "google_list_emails"])
        with patch("hachi.integrations.google.GoogleIntegrationHub", return_value=fake_hub):
            from hachi.tools import google_tools

            registry = _FakeRegistry()
            result = google_tools.register_google_tools(registry)
        assert result is True

    def test_mounts_hub_when_client_id_only_in_dotenv(self, monkeypatch, tmp_path) -> None:
        # config_dir/.env scenario: GOOGLE_CLIENT_ID is NOT in os.environ but IS in a project
        # .env (e.g. written by `hachi setup`). Registration must still mount the real hub —
        # the regression fix: it now resolves the same lazy way the OAuth flow does.
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        (tmp_path / ".env").write_text("GOOGLE_CLIENT_ID=dotenv-only-id\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        fake_hub = _make_fake_hub(["google_send_email"])
        with patch("hachi.integrations.google.GoogleIntegrationHub", return_value=fake_hub):
            from hachi.tools import google_tools

            registry = _FakeRegistry()
            result = google_tools.register_google_tools(registry)
        assert result is True
        assert "google_send_email" in registry._tools

    def test_mounts_hub_tools_when_client_id_set(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
        tool_names = ["google_send_email", "google_list_emails", "google_create_event"]
        fake_hub = _make_fake_hub(tool_names)
        with patch("hachi.integrations.google.GoogleIntegrationHub", return_value=fake_hub):
            from hachi.tools import google_tools

            registry = _FakeRegistry()
            google_tools.register_google_tools(registry)
        for name in tool_names:
            assert name in registry._tools

    def test_tools_tagged_google_group(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
        tool_names = ["google_send_email"]
        fake_hub = _make_fake_hub(tool_names)
        with patch("hachi.integrations.google.GoogleIntegrationHub", return_value=fake_hub):
            from hachi.tools import google_tools

            registry = _FakeRegistry()
            google_tools.register_google_tools(registry)
        # After registration, tool should be tagged "google" in _groups
        assert registry._tools.get("google_send_email") is not None
        assert registry._groups.get("google_send_email") == "google"

    def test_hub_register_tools_called_once(self, monkeypatch) -> None:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-client-id")
        fake_hub = _make_fake_hub([])
        with patch("hachi.integrations.google.GoogleIntegrationHub", return_value=fake_hub):
            from hachi.tools import google_tools

            registry = _FakeRegistry()
            google_tools.register_google_tools(registry)
        fake_hub.register_tools.assert_called_once()


# ---------------------------------------------------------------------------
# GOOGLE_TOOL_NAMES coverage check
# ---------------------------------------------------------------------------


def test_google_tool_names_are_all_strings() -> None:
    from hachi.tools.google_tools import GOOGLE_TOOL_NAMES

    assert all(isinstance(n, str) for n in GOOGLE_TOOL_NAMES)
    assert len(GOOGLE_TOOL_NAMES) > 0


def test_google_tool_names_all_prefixed_google() -> None:
    from hachi.tools.google_tools import GOOGLE_TOOL_NAMES

    assert all(n.startswith("google_") for n in GOOGLE_TOOL_NAMES)


# ---------------------------------------------------------------------------
# Orchestrator group dict sanity check (no real boot needed)
# ---------------------------------------------------------------------------


def test_orchestrator_group_dict_includes_google_tools() -> None:
    """_GROUP_BY_TOOL_NAME must map every GOOGLE_TOOL_NAMES entry to 'google'."""
    from hachi.gateway.orchestrator import _GROUP_BY_TOOL_NAME
    from hachi.tools.google_tools import GOOGLE_TOOL_NAMES

    for name in GOOGLE_TOOL_NAMES:
        assert name in _GROUP_BY_TOOL_NAME, f"{name!r} missing from _GROUP_BY_TOOL_NAME"
        assert _GROUP_BY_TOOL_NAME[name] == "google"
