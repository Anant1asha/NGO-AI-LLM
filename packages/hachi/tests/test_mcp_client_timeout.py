from __future__ import annotations

import time

from hachi.core.mcp_client import MCPServerConnection


class _FakeStdin:
    def write(self, _payload: bytes) -> None:
        return None

    def flush(self) -> None:
        return None


class _FakeProcess:
    def __init__(self) -> None:
        self.stdin = _FakeStdin()
        self.stdout = object()

    def poll(self):  # pragma: no cover - used for interface compatibility only
        return None


def test_send_request_times_out_without_stdout_responses() -> None:
    conn = MCPServerConnection("silent", "python", request_timeout_seconds=1.0)
    conn._process = _FakeProcess()  # type: ignore[assignment]

    started = time.time()
    response = conn._send_request("tools/list", {})
    elapsed = time.time() - started

    assert response is None
    assert elapsed < 2.0
