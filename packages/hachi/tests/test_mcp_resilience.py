"""Tests for MCP retry / circuit-breaker / reconnect resilience (P1-8).

Covers:
  1. A transient failure is retried then succeeds.
  2. The breaker opens after ``breaker_threshold`` consecutive failures and fast-fails.
  3. A dead transport triggers exactly one reconnect attempt before retries.
  4. Happy path returns the tool result unchanged.
  5. Per-server isolation: server A's open breaker does not block server B.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from hachi.core.errors import MCPError
from hachi.core.mcp_client import MCPServerConnection, _MCPTimeoutError
from hachi.core.resilience import HealthRecorder, RetryPolicy

# ---------------------------------------------------------------------------
# Helpers: fake transport + factory
# ---------------------------------------------------------------------------


class FakeTransport:
    """Minimal fake transport that can be configured to succeed or fail.

    ``call_responses`` is a list consumed left-to-right; each element is:
      - a dict  → returned as a successful JSON-RPC response
      - an Exception instance → raised as a transient error
      - None → simulates a timeout (returns None from receive)

    ``alive`` controls ``is_alive``; set it to ``False`` to simulate a dead
    transport without touching process/subprocess internals.
    """

    def __init__(self, *, call_responses: list[Any] | None = None, alive: bool = True) -> None:
        self._responses: list[Any] = list(call_responses or [])
        self._alive = alive
        self.start_calls: int = 0
        self.close_calls: int = 0
        self.send_calls: int = 0
        self.receive_calls: int = 0

    # MCPTransport interface ------------------------------------------------

    def start(self) -> bool:
        self.start_calls += 1
        self._alive = True
        return True

    def send(self, message: dict[str, Any]) -> None:
        self.send_calls += 1

    def receive(self, request_id: Any, timeout_seconds: float) -> dict[str, Any] | None:
        self.receive_calls += 1
        if not self._responses:
            return None
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self) -> None:
        self.close_calls += 1
        self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive

    # Convenience --------------------------------------------------------

    def push(self, item: Any) -> None:
        """Append a response to the queue."""
        self._responses.append(item)


def _ok_response(tool_name: str, text: str, request_id: int = 1) -> dict[str, Any]:
    """Build a well-formed JSON-RPC tools/call success response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": text}]},
    }


def _error_response(message: str, request_id: int = 1) -> dict[str, Any]:
    """Build a JSON-RPC error response."""
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32603, "message": message},
    }


def _make_conn(
    transport: FakeTransport | None = None,
    breaker_threshold: int = 5,
    max_attempts: int = 3,
    cooldown: float = 30.0,
) -> MCPServerConnection:
    """Return a *pre-started* MCPServerConnection backed by a FakeTransport.

    We bypass the real ``start()`` / ``_start_inner()`` path entirely by
    monkey-patching ``_transport`` after construction, then adjusting the retry
    policy to match test parameters.
    """
    conn = MCPServerConnection(name="test-server", command="echo")
    if transport is None:
        transport = FakeTransport()
    conn._transport = transport
    # Override the auto-created policy with test-friendly settings.
    conn._retry_policy = RetryPolicy(
        max_attempts=max_attempts,
        backoff_base_s=0.0,  # no sleep in tests
        timeout_s=5.0,
        breaker_threshold=breaker_threshold,
        breaker_cooldown_s=cooldown,
    )
    # Re-create the recorder with the new policy so thresholds line up.
    conn._health_recorder = HealthRecorder("test-server", conn._retry_policy)
    return conn


# ---------------------------------------------------------------------------
# 1. Transient failure retried then succeeds
# ---------------------------------------------------------------------------


class TestRetryOnTransientFailure:
    """The first call raises a transient error; the second attempt succeeds."""

    def test_retry_succeeds_after_transient_error(self) -> None:
        # First call raises _MCPTimeoutError (transient, retried); second succeeds.
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake, max_attempts=3)

        call_count = 0

        def patched(tool_name: str, arguments: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _MCPTimeoutError("connection timed out")
            return "success-result"

        conn._call_tool_once = patched  # type: ignore[method-assign]

        result = conn.call_tool("my_tool", {})
        assert result == "success-result"
        assert call_count == 2

    def test_retries_respect_max_attempts(self) -> None:
        """If all attempts fail with transient errors, exception is raised after max_attempts."""
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake, max_attempts=3)
        call_count = 0

        def always_fail(tool_name: str, arguments: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            raise _MCPTimeoutError("persistent timeout")

        conn._call_tool_once = always_fail  # type: ignore[method-assign]

        with pytest.raises((MCPError, TimeoutError)):
            conn.call_tool("my_tool", {})

        assert call_count == 3  # max_attempts exhausted


# ---------------------------------------------------------------------------
# 2. Breaker opens after threshold failures and fast-fails
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """After ``breaker_threshold`` consecutive failures, the breaker opens."""

    def _exhaust_breaker(self, conn: MCPServerConnection, threshold: int) -> None:
        """Drive exactly ``threshold`` failures to open the breaker."""

        def always_fail(tool_name: str, arguments: dict[str, Any]) -> str:
            raise MCPError("intentional failure")

        conn._call_tool_once = always_fail  # type: ignore[method-assign]

        for _ in range(threshold):
            with pytest.raises((MCPError, Exception)):
                conn.call_tool("boom", {})

    def test_breaker_opens_and_fast_fails(self) -> None:
        threshold = 3
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake, breaker_threshold=threshold, max_attempts=1)

        self._exhaust_breaker(conn, threshold)

        # Breaker should now be open.
        assert conn._health_recorder.snapshot().breaker == "open"

        # Next call must fast-fail with MCPError (not re-try the transport).
        transport_calls: list[int] = []

        def should_not_be_called(tool_name: str, arguments: dict[str, Any]) -> str:
            transport_calls.append(1)
            return "should not reach here"

        conn._call_tool_once = should_not_be_called  # type: ignore[method-assign]

        with pytest.raises(MCPError, match="circuit breaker is open"):
            conn.call_tool("still_broken", {})

        # The transport was NOT touched again.
        assert transport_calls == []

    def test_breaker_does_not_open_before_threshold(self) -> None:
        threshold = 3
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake, breaker_threshold=threshold, max_attempts=1)

        call_count = 0

        def fail_then_succeed(tool_name: str, arguments: dict[str, Any]) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < threshold:
                raise MCPError("transient")
            return "ok"

        conn._call_tool_once = fail_then_succeed  # type: ignore[method-assign]

        # Drive threshold-1 failures (breaker NOT open yet).
        for _ in range(threshold - 1):
            with pytest.raises((MCPError, TimeoutError)):
                conn.call_tool("tool", {})

        # One more call that succeeds resets the consecutive counter.
        result = conn.call_tool("tool", {})
        assert result == "ok"
        assert conn._health_recorder.snapshot().breaker == "closed"


# ---------------------------------------------------------------------------
# 3. Dead transport triggers exactly one reconnect
# ---------------------------------------------------------------------------


class TestReconnectOnDeadTransport:
    """A dead transport causes exactly one reconnect before the tool call proceeds."""

    def test_reconnect_attempted_when_transport_dead(self) -> None:
        fake = FakeTransport(alive=False)  # starts dead
        conn = _make_conn(fake, max_attempts=2)

        reconnect_calls: list[int] = []

        def patched_reconnect() -> None:
            reconnect_calls.append(1)
            # Simulate successful reconnect: mark transport alive.
            fake._alive = True

        conn._try_reconnect = patched_reconnect  # type: ignore[method-assign]

        call_results: list[str] = []

        def succeed_after_reconnect(tool_name: str, arguments: dict[str, Any]) -> str:
            call_results.append("called")
            return "tool-result"

        conn._call_tool_once = succeed_after_reconnect  # type: ignore[method-assign]

        result = conn.call_tool("my_tool", {})
        assert result == "tool-result"
        # Exactly one reconnect was attempted (the outer liveness check).
        assert len(reconnect_calls) == 1

    def test_reconnect_fails_raises_mcp_error(self) -> None:
        """If reconnect fails, MCPError is raised (not a silent pass)."""
        fake = FakeTransport(alive=False)
        conn = _make_conn(fake, max_attempts=2)

        def failing_reconnect() -> None:
            # Reconnect "fails" — transport stays dead.
            pass

        conn._try_reconnect = failing_reconnect  # type: ignore[method-assign]

        with pytest.raises(MCPError):
            conn.call_tool("my_tool", {})

    def test_reconnect_not_called_when_transport_alive(self) -> None:
        """No reconnect is triggered when transport is healthy."""
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake, max_attempts=2)

        reconnect_calls: list[int] = []

        def should_not_reconnect() -> None:
            reconnect_calls.append(1)

        conn._try_reconnect = should_not_reconnect  # type: ignore[method-assign]

        def succeed(tool_name: str, arguments: dict[str, Any]) -> str:
            return "ok"

        conn._call_tool_once = succeed  # type: ignore[method-assign]

        conn.call_tool("my_tool", {})
        assert reconnect_calls == []


# ---------------------------------------------------------------------------
# 4. Happy path returns result unchanged
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Successful calls pass through the resilience layer unchanged."""

    def test_result_returned_verbatim(self) -> None:
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake)

        conn._call_tool_once = lambda t, a: "hello from the tool"  # type: ignore[method-assign]

        result = conn.call_tool("greet", {"name": "world"})
        assert result == "hello from the tool"

    def test_multiline_result_returned_verbatim(self) -> None:
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake)

        multiline = "line 1\nline 2\nline 3"
        conn._call_tool_once = lambda t, a: multiline  # type: ignore[method-assign]

        result = conn.call_tool("multiline_tool", {})
        assert result == multiline

    def test_success_records_into_health_recorder(self) -> None:
        fake = FakeTransport(alive=True)
        conn = _make_conn(fake)

        conn._call_tool_once = lambda t, a: "ok"  # type: ignore[method-assign]

        conn.call_tool("healthy_tool", {})
        snap = conn._health_recorder.snapshot()
        assert snap.consecutive_failures == 0
        assert snap.breaker == "closed"


# ---------------------------------------------------------------------------
# 5. Per-server isolation: server A breaker does not block server B
# ---------------------------------------------------------------------------


class TestPerServerIsolation:
    """Each server has its own HealthRecorder; a tripped breaker on A is invisible to B."""

    def _open_breaker(self, conn: MCPServerConnection, threshold: int) -> None:
        """Drive exactly ``threshold`` failures through the connection to open its breaker."""

        def always_fail(tool_name: str, arguments: dict[str, Any]) -> str:
            raise MCPError("forced failure")

        conn._call_tool_once = always_fail  # type: ignore[method-assign]
        for _ in range(threshold):
            with pytest.raises((MCPError, TimeoutError)):
                conn.call_tool("fail", {})

    def test_server_b_unaffected_by_server_a_open_breaker(self) -> None:
        threshold = 3
        conn_a = _make_conn(FakeTransport(alive=True), breaker_threshold=threshold, max_attempts=1)
        conn_b = _make_conn(FakeTransport(alive=True), breaker_threshold=threshold, max_attempts=1)

        self._open_breaker(conn_a, threshold)

        # A is open.
        assert conn_a._health_recorder.snapshot().breaker == "open"
        # B is still closed.
        assert conn_b._health_recorder.snapshot().breaker == "closed"

        # Calling via B succeeds.
        conn_b._call_tool_once = lambda t, a: "server-b-result"  # type: ignore[method-assign]
        result = conn_b.call_tool("any_tool", {})
        assert result == "server-b-result"

        # A still fast-fails.
        with pytest.raises(MCPError, match="circuit breaker is open"):
            conn_a.call_tool("any_tool", {})

    def test_separate_health_recorders(self) -> None:
        """Verify that conn_a and conn_b literally have different recorder instances."""
        conn_a = _make_conn(FakeTransport(alive=True))
        conn_b = _make_conn(FakeTransport(alive=True))
        assert conn_a._health_recorder is not conn_b._health_recorder


# ---------------------------------------------------------------------------
# Bonus: _call_tool_once parses responses correctly (independent of resilience)
# ---------------------------------------------------------------------------


class TestCallToolOnceUnit:
    """Unit-level tests for the raw single-shot invocation helper."""

    def _conn_with_transport(self, transport: FakeTransport) -> MCPServerConnection:
        conn = MCPServerConnection(name="unit-server", command="echo")
        conn._transport = transport
        return conn

    def test_no_response_raises_timeout_error(self) -> None:
        fake = FakeTransport(alive=True)
        conn = self._conn_with_transport(fake)

        # _send_request returns None → _call_tool_once raises _MCPTimeoutError (transient).
        with patch.object(conn, "_send_request", return_value=None):
            with pytest.raises(_MCPTimeoutError):
                conn._call_tool_once("tool", {})

    def test_error_response_raises_mcp_error(self) -> None:
        fake = FakeTransport(alive=True)
        conn = self._conn_with_transport(fake)

        with patch.object(
            conn, "_send_request", return_value={"error": {"message": "server fault"}}
        ):
            with pytest.raises(MCPError, match="server fault"):
                conn._call_tool_once("tool", {})

    def test_text_content_extracted_correctly(self) -> None:
        fake = FakeTransport(alive=True)
        conn = self._conn_with_transport(fake)

        success = {
            "result": {
                "content": [
                    {"type": "text", "text": "first"},
                    {"type": "text", "text": "second"},
                ]
            }
        }
        with patch.object(conn, "_send_request", return_value=success):
            result = conn._call_tool_once("tool", {})
        assert result == "first\nsecond"

    def test_response_truncated_at_limit(self) -> None:
        from hachi.core.mcp_client import _MCP_RESPONSE_MAX_CHARS, _MCP_TRUNCATION_MARKER

        fake = FakeTransport(alive=True)
        conn = self._conn_with_transport(fake)

        long_text = "x" * (_MCP_RESPONSE_MAX_CHARS + 500)
        success = {"result": {"content": [{"type": "text", "text": long_text}]}}
        with patch.object(conn, "_send_request", return_value=success):
            result = conn._call_tool_once("tool", {})

        assert len(result) > _MCP_RESPONSE_MAX_CHARS  # includes truncation marker
        assert _MCP_TRUNCATION_MARKER.split("{")[0] in result or "TRUNCATED" in result
