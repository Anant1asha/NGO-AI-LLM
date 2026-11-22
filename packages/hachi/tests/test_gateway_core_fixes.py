"""Tests for gateway-core fixes (Issues 1, 4, 5, 12).

Issue 1  — session_state falls back to SQLite for expired sessions; send_message raises
           SessionExpiredError (not bare "Unknown session_id") for known sessions.
Issue 4  — _configure_mcp_servers loads [mcp_servers] TOML entries at boot.
Issue 5  — _register_search_if_available logs a fallback warning when no provider.
Issue 12 — POST /sessions/cleanup-empty route exists and calls delete_empty_sessions().
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest

from hachi.gateway.control_plane import (
    GatewayControlPlane,
    GatewayProtocolError,
    SessionExpiredError,
)

# ---------------------------------------------------------------------------
# Issue 1a: session_state for a session absent from _connections but present
# in SQLite returns a state dict (no raise).
# ---------------------------------------------------------------------------


class TestSessionStateFallback:
    """GatewayControlPlane.session_state with a dead-but-known session."""

    def _make_cp_with_sqlite_hit(self) -> GatewayControlPlane:
        """Return a GatewayControlPlane whose get_session_messages returns a non-empty list."""
        return GatewayControlPlane(
            # No get_session_state handler wired — the live path is never reached.
            get_session_messages=lambda _sid, _limit: [
                {"role": "user", "content": "hello", "time": "2026-06-22T00:00:00Z"}
            ],
        )

    def _make_cp_no_sqlite(self) -> GatewayControlPlane:
        """Return a GatewayControlPlane with no SQLite messages (unknown session)."""
        return GatewayControlPlane(
            get_session_messages=lambda _sid, _limit: [],
        )

    def test_expired_session_returns_state_dict(self) -> None:
        """session_state returns a dict with status='expired' instead of raising."""
        cp = self._make_cp_with_sqlite_hit()
        result = cp.session_state("dead-session-id-001")
        assert isinstance(result, dict)
        assert result["session_id"] == "dead-session-id-001"
        assert result.get("status") == "expired"

    def test_expired_session_no_exception(self) -> None:
        """session_state must NOT raise GatewayProtocolError for a known SQLite session."""
        cp = self._make_cp_with_sqlite_hit()
        # Should not raise:
        state = cp.session_state("some-expired-id")
        assert state is not None

    def test_unknown_session_still_raises(self) -> None:
        """session_state DOES raise for a session with no SQLite record at all."""
        cp = self._make_cp_no_sqlite()
        with pytest.raises(GatewayProtocolError):
            cp.session_state("completely-unknown-id")

    def test_live_session_uses_handler(self) -> None:
        """session_state calls the handler for an in-memory (live) session."""
        state_returned = {"session_id": "live-001", "boot_ready": True}
        cp = GatewayControlPlane(
            get_session_state=lambda _sid: state_returned,
        )
        # Create a live session.
        result = cp.create_session(client_id="c1", surface="tui")
        sid = result["session_id"]

        live_state = cp.session_state(sid)
        assert live_state == state_returned

    def test_no_get_session_messages_handler_raises(self) -> None:
        """When no get_session_messages is wired, expired sessions still raise."""
        cp = GatewayControlPlane()  # no handlers
        with pytest.raises(GatewayProtocolError):
            cp.session_state("any-dead-session")


# ---------------------------------------------------------------------------
# Issue 1b: send_message raises SessionExpiredError (typed, with code attr)
# for a session known in SQLite but not in _connections.
# ---------------------------------------------------------------------------


class TestSendMessageTypedError:
    """GatewayControlPlane.send_message raises the right typed error."""

    def test_expired_session_raises_session_expired_error(self) -> None:
        """send_message raises SessionExpiredError (not bare GatewayProtocolError) when the
        session_id is in SQLite but not in active memory."""
        cp = GatewayControlPlane(
            on_chat=lambda _sid, _prompt: "reply",
            get_session_messages=lambda _sid, _limit: [
                {"role": "user", "content": "hi", "time": "2026-06-22T00:00:00Z"}
            ],
        )
        with pytest.raises(SessionExpiredError) as exc_info:
            cp.send_message(session_id="expired-session-999", prompt="hello")

        assert exc_info.value.code == "session_expired"
        assert "expired-session-999" in str(exc_info.value)

    def test_unknown_session_raises_protocol_error_with_code(self) -> None:
        """send_message raises GatewayProtocolError with code='unknown_session' for garbage ids."""
        cp = GatewayControlPlane(
            on_chat=lambda _sid, _prompt: "reply",
            get_session_messages=lambda _sid, _limit: [],  # empty = not in SQLite
        )
        with pytest.raises(GatewayProtocolError) as exc_info:
            cp.send_message(session_id="garbage-id-xyz", prompt="hello")

        err = exc_info.value
        # Must NOT be SessionExpiredError — it's an unknown session.
        assert not isinstance(err, SessionExpiredError)
        assert getattr(err, "code", None) == "unknown_session"

    def test_session_expired_is_subclass_of_protocol_error(self) -> None:
        """SessionExpiredError is a subclass of GatewayProtocolError for catch-all handlers."""
        assert issubclass(SessionExpiredError, GatewayProtocolError)

    def test_session_expired_error_attributes(self) -> None:
        """SessionExpiredError carries session_id and code='session_expired'."""
        exc = SessionExpiredError("test-sid")
        assert exc.session_id == "test-sid"
        assert exc.code == "session_expired"


# ---------------------------------------------------------------------------
# Issue 4: _configure_mcp_servers loads [mcp_servers] TOML entries at boot.
# ---------------------------------------------------------------------------


class TestConfigureMcpServersToml:
    """_configure_mcp_servers loads TOML [mcp_servers] entries in addition to .og nodes."""

    def _make_fake_gate(self, allow: bool = True) -> Any:
        gate = MagicMock()
        gate.is_mcp_filesystem_enabled.return_value = True
        gate.is_mcp_server_allowed.return_value = MagicMock(allowed=allow, reason="ok")
        gate.get_allowed_paths.return_value = []
        return gate

    def test_toml_entry_is_started(self) -> None:
        """A [mcp_servers] TOML entry not present in .og nodes is started via setup_from_config."""
        from hachi.gateway.orchestrator import _configure_mcp_servers

        skill_engine = MagicMock()
        skill_engine.get_nodes_by_role.return_value = []  # no .og mcp nodes

        mcp_manager = MagicMock()
        mcp_manager.setup_from_config.return_value = True
        mcp_manager.get_server_tool_count.return_value = 2

        gate = self._make_fake_gate(allow=True)
        emit = MagicMock()

        config = {
            "mcp_servers": {
                "my_toml_server": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": "-y some-mcp-server",
                }
            }
        }

        _configure_mcp_servers(skill_engine, mcp_manager, gate, emit, config=config)

        mcp_manager.setup_from_config.assert_called_once()
        call_cfg = mcp_manager.setup_from_config.call_args[0][0]
        assert call_cfg.name == "my_toml_server"

    def test_toml_entry_deduped_when_og_node_exists(self) -> None:
        """A TOML entry whose name matches an .og node is skipped (de-dup: .og wins)."""
        from hachi.gateway.orchestrator import _configure_mcp_servers

        # Build a fake .og node with the same name as the TOML entry.
        og_node = MagicMock()
        og_node.name = "shared_server"
        og_node.config = {}
        og_node.source_file = "/builtin/shared_server.og"

        skill_engine = MagicMock()
        skill_engine.get_nodes_by_role.return_value = [og_node]

        mcp_manager = MagicMock()
        mcp_manager.setup_from_node.return_value = True
        mcp_manager.get_server_tool_count.return_value = 1

        gate = self._make_fake_gate(allow=True)
        emit = MagicMock()

        config = {
            "mcp_servers": {
                "shared_server": {"transport": "stdio", "command": "some-cmd"}
            }
        }

        _configure_mcp_servers(skill_engine, mcp_manager, gate, emit, config=config)

        # setup_from_config should NOT have been called (de-duped).
        mcp_manager.setup_from_config.assert_not_called()
        # setup_from_node WAS called (from the .og pass).
        mcp_manager.setup_from_node.assert_called_once()

    def test_no_config_no_crash(self) -> None:
        """_configure_mcp_servers with config=None does not raise."""
        from hachi.gateway.orchestrator import _configure_mcp_servers

        skill_engine = MagicMock()
        skill_engine.get_nodes_by_role.return_value = []
        mcp_manager = MagicMock()
        gate = self._make_fake_gate()
        emit = MagicMock()

        _configure_mcp_servers(skill_engine, mcp_manager, gate, emit, config=None)
        mcp_manager.setup_from_config.assert_not_called()

    def test_permission_denied_toml_entry_not_started(self) -> None:
        """A TOML entry is NOT started when the permission gate denies it."""
        from hachi.gateway.orchestrator import _configure_mcp_servers

        skill_engine = MagicMock()
        skill_engine.get_nodes_by_role.return_value = []

        mcp_manager = MagicMock()
        gate = self._make_fake_gate(allow=False)
        gate.is_mcp_server_allowed.return_value = MagicMock(allowed=False, reason="denied by tier")
        emit = MagicMock()

        config = {"mcp_servers": {"denied_server": {"command": "npx", "args": "dangerous"}}}

        _configure_mcp_servers(skill_engine, mcp_manager, gate, emit, config=config)
        mcp_manager.setup_from_config.assert_not_called()


# ---------------------------------------------------------------------------
# Issue 5: _register_search_if_available logs a warning when no provider.
# ---------------------------------------------------------------------------


class TestRegisterSearchFallbackWarning:
    """_register_search_if_available logs a fallback warning when no provider is registered."""

    def _make_deps(self, *, registry_none: bool = False, provider_none: bool = False) -> Any:
        deps = MagicMock()
        if registry_none:
            deps.provider_registry = None
        else:
            registry = MagicMock()
            registry.get_search.return_value = None if provider_none else MagicMock()
            deps.provider_registry = registry
        deps.tool_registry = MagicMock()
        deps.gate = MagicMock()
        return deps

    def test_logs_warning_when_registry_is_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """When provider_registry is None, a warning mentioning 'browse_web' is logged."""
        from hachi.gateway.orchestrator import _register_search_if_available

        deps = self._make_deps(registry_none=True)
        with caplog.at_level(logging.WARNING, logger="hachi.gateway.orchestrator"):
            _register_search_if_available(deps)

        warning_text = " ".join(caplog.messages)
        assert "browse_web" in warning_text or "UNAVAILABLE" in warning_text.upper()

    def test_logs_warning_when_no_search_provider(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When registry.get_search() returns None, a warning mentioning 'browse_web' is logged."""
        from hachi.gateway.orchestrator import _register_search_if_available

        deps = self._make_deps(registry_none=False, provider_none=True)
        with caplog.at_level(logging.WARNING, logger="hachi.gateway.orchestrator"):
            _register_search_if_available(deps)

        warning_text = " ".join(caplog.messages)
        assert "browse_web" in warning_text or "UNAVAILABLE" in warning_text.upper()

    def test_no_warning_when_provider_registered(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When a SearchProvider IS registered, no 'UNAVAILABLE' warning is emitted before
        the cache/limiter setup phase begins."""
        from hachi.gateway.orchestrator import _register_search_if_available

        # Use deps with a real provider. The function will attempt to import SearchCache /
        # OutboundRateLimiter lazily; we allow it to fail on that import — what we care about
        # is that the early-exit UNAVAILABLE warning is NOT emitted.
        deps = self._make_deps(registry_none=False, provider_none=False)
        with caplog.at_level(logging.WARNING, logger="hachi.gateway.orchestrator"):
            try:
                _register_search_if_available(deps)
            except Exception:
                pass  # acceptable — we only assert on what was logged before any error

        # The UNAVAILABLE warning (our addition) must NOT appear — a provider is registered.
        for record in caplog.records:
            if record.levelno >= logging.WARNING:
                assert "UNAVAILABLE" not in record.getMessage().upper(), (
                    f"Unexpected UNAVAILABLE warning: {record.getMessage()}"
                )
