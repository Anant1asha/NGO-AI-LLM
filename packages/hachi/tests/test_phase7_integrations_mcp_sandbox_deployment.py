from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from hachi.core.mcp_client import MCPServerConnection
from hachi.core.sandbox import SandboxExecutor
from hachi.integrations.google.client import GoogleHTTPClient
from hachi.integrations.notion.databases import NotionDatabases
from hachi.integrations.notion.service import NotionService
from hachi.integrations.slack.chat import SlackChat
from hachi.integrations.slack.service import SlackService
from hachi.tools.os_tools import _raw_run_terminal_command


class _FakeVaultNoTokens:
    def get_token(self, _name: str, prompt_if_missing: bool = False) -> str | None:
        return None


def test_slack_service_missing_credentials_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.credential_vault.CredentialVault",
        lambda: _FakeVaultNoTokens(),
    )

    service = SlackService()
    with pytest.raises(ValueError, match="Missing Slack Bot Token"):
        _ = service.headers


def test_notion_service_missing_credentials_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.credential_vault.CredentialVault",
        lambda: _FakeVaultNoTokens(),
    )

    service = NotionService()
    with pytest.raises(ValueError, match="Missing Notion API key"):
        _ = service.headers


def test_google_client_revoked_or_expired_scope_failure_propagates(monkeypatch) -> None:
    client = GoogleHTTPClient(scopes=["openid", "email"])
    monkeypatch.setattr(
        client.oauth,
        "get_google_credentials",
        lambda _scopes: (_ for _ in ()).throw(RuntimeError("revoked scopes")),
    )

    with pytest.raises(RuntimeError, match="revoked scopes"):
        _ = client._get_headers()


def test_slack_chat_handles_rate_limit_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.credential_vault.CredentialVault",
        lambda: _FakeVaultNoTokens(),
    )

    chat = SlackChat()
    monkeypatch.setattr(
        chat, "_post", lambda *_a, **_k: (_ for _ in ()).throw(Exception("429 rate_limited"))
    )

    result = chat.send_message("C123", "hello")
    assert "Failed to send Slack message" in result
    assert "429" in result


def test_notion_search_handles_partial_payload_and_5xx(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.credential_vault.CredentialVault",
        lambda: _FakeVaultNoTokens(),
    )

    databases = NotionDatabases()

    monkeypatch.setattr(
        databases,
        "_post",
        lambda *_a, **_k: {
            "results": [
                {
                    "object": "page",
                    "id": "abc",
                    "url": "https://example.com/page/abc",
                }
            ]
        },
    )
    partial = databases.search_workspace("status")
    assert "[PAGE] Untitled" in partial

    monkeypatch.setattr(
        databases, "_post", lambda *_a, **_k: (_ for _ in ()).throw(Exception("503 upstream"))
    )
    failed = databases.search_workspace("status")
    assert "Failed to search Notion workspace" in failed
    assert "503" in failed


class _Reader:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _Stderr:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _StartupFailProcess:
    def __init__(self, stderr: bytes) -> None:
        self.stdin = object()
        self.stdout = _Reader([])
        self.stderr = _Stderr(stderr)

    def poll(self) -> int | None:
        return 1

    def terminate(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> None:
        return None


def test_mcp_start_fails_when_executable_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.mcp_client.subprocess.Popen",
        lambda *_a, **_k: (_ for _ in ()).throw(FileNotFoundError()),
    )

    conn = MCPServerConnection("missing", "definitely-not-a-real-executable")
    assert conn.start() is False


def test_mcp_start_fails_closed_on_stderr_only_startup_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.core.mcp_client.subprocess.Popen",
        lambda *_a, **_k: _StartupFailProcess(b"fatal startup error"),
    )
    monkeypatch.setattr("hachi.core.mcp_client.time.sleep", lambda *_a, **_k: None)

    conn = MCPServerConnection("stderr-only", "fake")
    assert conn.start() is False


def test_mcp_reader_ignores_malformed_json_and_overwrites_duplicate_ids() -> None:
    conn = MCPServerConnection("reader", "python")
    conn._process = type(
        "P",
        (),
        {
            "stdout": _Reader(
                [
                    b"not-json\n",
                    b'{"jsonrpc":"2.0","id":7,"result":{"value":"first"}}\n',
                    b'{"jsonrpc":"2.0","id":7,"result":{"value":"second"}}\n',
                ]
            )
        },
    )()

    conn._stdout_reader()

    with conn._response_cv:
        assert conn._responses[7]["result"]["value"] == "second"


def test_mcp_tools_payload_normalization_deduplicates_and_skips_invalid_entries() -> None:
    payload = [
        {"name": "ok_one", "description": "first"},
        {"name": "ok_one", "description": "duplicate"},
        {"name": " ", "description": "blank"},
        {"description": "missing-name"},
        "not-a-dict",
        {"name": "ok_two", "description": "second"},
    ]

    normalized = MCPServerConnection._normalize_tools_payload(payload)

    assert [tool["name"] for tool in normalized] == ["ok_one", "ok_two"]


def test_sandbox_reports_missing_uv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("hachi.core.sandbox.shutil.which", lambda *_a, **_k: None)
    fake_python = tmp_path / "bin" / "python"
    fake_python.parent.mkdir(parents=True, exist_ok=True)
    fake_python.write_text("", encoding="utf-8")
    monkeypatch.setattr("sys.executable", str(fake_python))

    executor = SandboxExecutor.__new__(SandboxExecutor)

    with pytest.raises(EnvironmentError, match="uv"):
        SandboxExecutor._resolve_uv(executor)


def test_sandbox_invalid_execution_path_returns_structured_failure(tmp_path: Path) -> None:
    root_file = tmp_path / "sandbox-root-file"
    root_file.write_text("not a directory", encoding="utf-8")

    executor = SandboxExecutor.__new__(SandboxExecutor)
    executor.sandbox_root = root_file
    executor._uv_path = "uv"

    result = executor.execute("print('x')")

    assert result.success is False
    assert result.exit_code == -1
    assert "Sandbox execution crashed" in result.stderr


def test_sandbox_timeout_maps_to_timeout_result(monkeypatch, tmp_path: Path) -> None:
    executor = SandboxExecutor.__new__(SandboxExecutor)
    executor.sandbox_root = tmp_path
    executor._uv_path = "uv"

    def _raise_timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd=["uv", "run"], timeout=1, output=b"", stderr=b"")

    monkeypatch.setattr("hachi.core.sandbox.subprocess.run", _raise_timeout)

    result = executor.execute("while True: pass", timeout=1)

    assert result.success is False
    assert result.exit_code == 124
    assert "timed out" in result.stderr.lower()


def test_run_terminal_command_handles_quoted_argument_with_spaces(tmp_path: Path) -> None:
    command = f'"{sys.executable}" -c "print(__import__(\'sys\').argv[1])" "hello world"'

    result = _raw_run_terminal_command(command, cwd=str(tmp_path))

    assert "hello world" in result
    assert "Exit Code: 0" in result


def test_dockerfile_exposes_gateway_runtime_command() -> None:
    text = Path("Dockerfile").read_text(encoding="utf-8")

    assert 'hachi", "gateway"' in text
    assert '--host", "0.0.0.0"' in text
    assert "--runtime" in text


def test_compose_enforces_auth_persistence_and_restart_contract() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "HACHI_GATEWAY_API_TOKEN_FILE" in text
    # P0-4: persistent state/config now use NAMED volumes targeting the non-root user's
    # home. The previous `/root` bind mounts were unwritable by the non-root container user
    # (uid 10001), so `docker compose up` could not actually persist anything.
    assert "hachi-state:/home/hachi/.local/state/hachi" in text
    assert "hachi-config:/home/hachi/.config/hachi" in text
    assert "HACHI_GATEWAY_BASE_URL: http://hachi:8787" in text
    assert text.count("restart: unless-stopped") >= 2
