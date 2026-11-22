"""Tests for MCP/shared-services resilience fixes.

Covers:
  ADV-024 — stale singleton ignores config (config fingerprint check)
  UC-INT-004 — dead MCP pool is detected and re-initialised
  UC-DEV-001 — MCP init hang is bounded by boot_timeout_seconds
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


def _make_config(backend: str = "chroma", graph: bool = False) -> dict[str, Any]:
    return {"memory": {"backend": backend, "graph": graph}}


# ---------------------------------------------------------------------------
# ADV-024 — config fingerprint
# ---------------------------------------------------------------------------


class TestConfigFingerprint:
    """get_or_create must key instances by (brain_dir, memory.backend, memory.graph)."""

    def test_same_config_returns_cached_instance(self, tmp_path) -> None:
        """Two identical calls → same object, no re-init."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        brain_dir = str(tmp_path)

        stub = MagicMock(spec=ProcessSharedServices)
        stub.mcp_manager = MagicMock()
        stub.mcp_manager._servers = {}  # empty pool → healthy

        with patch.object(ProcessSharedServices, "_init", return_value=stub) as mock_init:
            first = ProcessSharedServices.get_or_create(config, brain_dir)
            second = ProcessSharedServices.get_or_create(config, brain_dir)

        assert first is second, "Same config must return the same instance"
        assert mock_init.call_count == 1, "_init must only be called once for identical configs"

    def test_different_backend_returns_distinct_instance(self, tmp_path) -> None:
        """A caller with a different memory.backend must NOT get the chroma instance."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        brain_dir = str(tmp_path)
        config_chroma = _make_config("chroma")
        config_fts5 = _make_config("fts5_only")

        stub_chroma = MagicMock(spec=ProcessSharedServices)
        stub_chroma.mcp_manager = MagicMock()
        stub_chroma.mcp_manager._servers = {}
        stub_fts5 = MagicMock(spec=ProcessSharedServices)
        stub_fts5.mcp_manager = MagicMock()
        stub_fts5.mcp_manager._servers = {}

        def _fake_init(config, bd, *, fingerprint=""):
            if config.get("memory", {}).get("backend") == "fts5_only":
                return stub_fts5
            return stub_chroma

        with patch.object(ProcessSharedServices, "_init", side_effect=_fake_init) as mock_init:
            first = ProcessSharedServices.get_or_create(config_chroma, brain_dir)
            second = ProcessSharedServices.get_or_create(config_fts5, brain_dir)

        assert first is not second, (
            "Different memory.backend values must produce distinct instances — "
            "never silently inherit the wrong backend (ADV-024)"
        )
        assert mock_init.call_count == 2

    def test_different_graph_flag_returns_distinct_instance(self, tmp_path) -> None:
        """memory.graph=True vs False must also produce distinct instances."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        brain_dir = str(tmp_path)
        config_no_graph = _make_config("chroma", graph=False)
        config_graph = _make_config("chroma", graph=True)

        stubs: list[MagicMock] = []

        def _fake_init(config, bd, *, fingerprint=""):
            stub = MagicMock(spec=ProcessSharedServices)
            stub.mcp_manager = MagicMock()
            stub.mcp_manager._servers = {}
            stubs.append(stub)
            return stub

        with patch.object(ProcessSharedServices, "_init", side_effect=_fake_init):
            a = ProcessSharedServices.get_or_create(config_no_graph, brain_dir)
            b = ProcessSharedServices.get_or_create(config_graph, brain_dir)

        assert a is not b

    def test_different_brain_dir_returns_distinct_instance(self, tmp_path) -> None:
        """Different brain_dir paths must produce distinct instances."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        dir_a = str(tmp_path / "a")
        dir_b = str(tmp_path / "b")

        def _fake_init(config, bd, *, fingerprint=""):
            stub = MagicMock(spec=ProcessSharedServices)
            stub.mcp_manager = MagicMock()
            stub.mcp_manager._servers = {}
            return stub

        with patch.object(ProcessSharedServices, "_init", side_effect=_fake_init) as mock_init:
            a = ProcessSharedServices.get_or_create(config, dir_a)
            b = ProcessSharedServices.get_or_create(config, dir_b)

        assert a is not b
        assert mock_init.call_count == 2

    def test_force_reinit_replaces_cached_instance(self, tmp_path) -> None:
        """force_reinit=True must tear down the existing fingerprint entry."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        brain_dir = str(tmp_path)

        def _fake_init(config, bd, *, fingerprint=""):
            stub = MagicMock(spec=ProcessSharedServices)
            stub.mcp_manager = MagicMock()
            stub.mcp_manager._servers = {}
            return stub

        with patch.object(ProcessSharedServices, "_init", side_effect=_fake_init) as mock_init:
            first = ProcessSharedServices.get_or_create(config, brain_dir)
            second = ProcessSharedServices.get_or_create(config, brain_dir, force_reinit=True)

        assert first is not second, "force_reinit must produce a fresh instance"
        assert mock_init.call_count == 2


# ---------------------------------------------------------------------------
# UC-INT-004 — MCP health check and re-init on dead pool
# ---------------------------------------------------------------------------


class TestMCPHealthCheck:
    """A dead MCP pool must be detected and trigger re-init."""

    def _stub_with_dead_server(self) -> MagicMock:
        """Return a ProcessSharedServices stub whose MCP pool has one dead server."""
        dead_server = MagicMock()
        dead_server.is_alive = False

        mcp_manager = MagicMock()
        mcp_manager._servers = {"gmail": dead_server}

        stub = MagicMock()
        stub.mcp_manager = mcp_manager
        return stub

    def _stub_with_healthy_pool(self) -> MagicMock:
        """Return a stub whose MCP pool is fully alive."""
        live_server = MagicMock()
        live_server.is_alive = True

        mcp_manager = MagicMock()
        mcp_manager._servers = {"gmail": live_server}

        stub = MagicMock()
        stub.mcp_manager = mcp_manager
        return stub

    def test_dead_mcp_pool_triggers_reinit(self, tmp_path) -> None:
        """If a cached instance has a dead MCP server, get_or_create must re-init."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        brain_dir = str(tmp_path)

        dead_stub = self._stub_with_dead_server()
        fresh_stub = self._stub_with_healthy_pool()

        init_returns = [dead_stub, fresh_stub]

        def _fake_init(config, bd, *, fingerprint=""):
            return init_returns.pop(0)

        with patch.object(ProcessSharedServices, "_init", side_effect=_fake_init) as mock_init:
            # Prime the cache with a dead-pool instance.
            first = ProcessSharedServices.get_or_create(config, brain_dir)
            # Simulate the server dying after the first init.
            first.mcp_manager._servers["gmail"].is_alive = False

            # Second call should detect the dead pool and re-init.
            second = ProcessSharedServices.get_or_create(config, brain_dir)

        assert mock_init.call_count == 2, (
            "A dead MCP pool must trigger re-initialisation (UC-INT-004)"
        )
        assert second is not first

    def test_healthy_mcp_pool_does_not_reinit(self, tmp_path) -> None:
        """A healthy pool must be returned directly without re-init."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        brain_dir = str(tmp_path)

        healthy_stub = self._stub_with_healthy_pool()

        with patch.object(ProcessSharedServices, "_init", return_value=healthy_stub) as mock_init:
            first = ProcessSharedServices.get_or_create(config, brain_dir)
            second = ProcessSharedServices.get_or_create(config, brain_dir)

        assert first is second
        assert mock_init.call_count == 1, "A healthy pool must not trigger re-init"

    def test_empty_mcp_pool_is_considered_healthy(self, tmp_path) -> None:
        """An MCPManager with no servers (not yet set up) must not cause re-init loops."""
        from hachi.gateway.shared_services import ProcessSharedServices

        ProcessSharedServices.clear()
        config = _make_config("chroma")
        brain_dir = str(tmp_path)

        stub = MagicMock()
        stub.mcp_manager = MagicMock()
        stub.mcp_manager._servers = {}  # no servers configured

        with patch.object(ProcessSharedServices, "_init", return_value=stub) as mock_init:
            first = ProcessSharedServices.get_or_create(config, brain_dir)
            second = ProcessSharedServices.get_or_create(config, brain_dir)

        assert first is second
        assert mock_init.call_count == 1

    def test_mcp_pool_healthy_classmethod_behaviour(self) -> None:
        """Unit-test _mcp_pool_healthy directly for all edge cases."""
        from hachi.gateway.shared_services import ProcessSharedServices

        # Empty servers → healthy
        m_empty = MagicMock()
        m_empty._servers = {}
        assert ProcessSharedServices._mcp_pool_healthy(m_empty) is True

        # All alive → healthy
        live = MagicMock()
        live.is_alive = True
        m_live = MagicMock()
        m_live._servers = {"s": live}
        assert ProcessSharedServices._mcp_pool_healthy(m_live) is True

        # One dead → unhealthy
        dead = MagicMock()
        dead.is_alive = False
        m_dead = MagicMock()
        m_dead._servers = {"s": dead}
        assert ProcessSharedServices._mcp_pool_healthy(m_dead) is False

        # is_alive raises → treat as dead
        broken = MagicMock()
        type(broken).is_alive = property(lambda _self: (_ for _ in ()).throw(RuntimeError("oops")))
        m_broken = MagicMock()
        m_broken._servers = {"s": broken}
        assert ProcessSharedServices._mcp_pool_healthy(m_broken) is False

        # No _servers attribute → assume healthy (unknown manager type)
        class _NoServers:
            pass

        assert ProcessSharedServices._mcp_pool_healthy(_NoServers()) is True


# ---------------------------------------------------------------------------
# UC-DEV-001 — MCP boot timeout
# ---------------------------------------------------------------------------


class TestMCPBootTimeout:
    """MCP boot must fail gracefully when the server hangs past boot_timeout_seconds."""

    def test_hanging_start_fails_within_timeout(self) -> None:
        """A server that hangs in start() must return False and not block."""
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection("slow-server", "python", boot_timeout_seconds=0.3)

        # Patch _start_inner to hang forever.
        hang_event = threading.Event()

        def _hang_forever() -> bool:
            hang_event.wait(timeout=60)  # blocks until test teardown
            return True

        conn._start_inner = _hang_forever  # type: ignore[method-assign]

        started = time.monotonic()
        result = conn.start()
        elapsed = time.monotonic() - started

        # Signal the hang to unblock (cleanup).
        hang_event.set()

        assert result is False, "A hanging boot must return False (UC-DEV-001)"
        assert elapsed < 1.0, (
            f"start() must return within boot_timeout + overhead, got {elapsed:.2f}s"
        )

    def test_start_succeeds_when_inner_returns_quickly(self) -> None:
        """start() passes through the True result from a fast _start_inner."""
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection("fast-server", "python", boot_timeout_seconds=5.0)
        conn._start_inner = lambda: True  # type: ignore[method-assign]

        result = conn.start()
        assert result is True

    def test_start_propagates_false_from_inner(self) -> None:
        """A _start_inner that returns False (e.g. exe missing) propagates to caller."""
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection("failing-server", "nope", boot_timeout_seconds=5.0)
        conn._start_inner = lambda: False  # type: ignore[method-assign]

        result = conn.start()
        assert result is False

    def test_boot_timeout_default_is_positive(self) -> None:
        """Sanity: the class-level default must be a positive float."""
        from hachi.core.mcp_client import MCPServerConnection

        assert MCPServerConnection.DEFAULT_BOOT_TIMEOUT_SECONDS > 0

    def test_boot_timeout_kwarg_is_stored(self) -> None:
        """Explicitly supplied boot_timeout_seconds is stored on the instance."""
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection("test", "python", boot_timeout_seconds=42.0)
        assert conn._boot_timeout_seconds == pytest.approx(42.0)

    def test_hanging_boot_kills_subprocess(self, monkeypatch) -> None:
        """When boot times out the subprocess (if spawned) must be killed."""
        from hachi.core.mcp_client import MCPServerConnection

        conn = MCPServerConnection("slow-kill", "python", boot_timeout_seconds=0.2)

        killed = threading.Event()

        class _FakeProc:
            def kill(self) -> None:
                killed.set()

        # Simulate _start_inner having started a subprocess that then hangs.
        def _hang_and_set_proc() -> bool:
            conn._process = _FakeProc()  # type: ignore[assignment]
            time.sleep(60)
            return True

        conn._start_inner = _hang_and_set_proc  # type: ignore[method-assign]

        result = conn.start()

        assert result is False
        # Give the kill a moment to be called (the timeout thread may still be running).
        killed.wait(timeout=1.0)
        assert killed.is_set(), "kill() must be called on the subprocess when boot times out"
