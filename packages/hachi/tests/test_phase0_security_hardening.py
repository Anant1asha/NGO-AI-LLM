from __future__ import annotations

import os
import sys
from pathlib import Path

from hachi.core.loop import ToolRegistry
from hachi.core.mcp_client import MCPServerConnection
from hachi.core.rest_adapter import UniversalRestAdapter
from hachi.tools.os_tools import _raw_run_shell_script, _raw_run_terminal_command


class _FakeVault:
    def __init__(self, values: dict[str, str]):
        self._values = values

    def get_token(self, name: str) -> str | None:
        return self._values.get(name)


def test_run_terminal_command_rejects_shell_operators(tmp_path: Path) -> None:
    result = _raw_run_terminal_command("echo hello && echo world", cwd=str(tmp_path))
    assert "Shell operators are not allowed" in result


def test_run_terminal_command_executes_single_argv(tmp_path: Path) -> None:
    command = f'"{sys.executable}" -c "print(12345)"'
    result = _raw_run_terminal_command(command, cwd=str(tmp_path))
    assert "12345" in result
    assert "Exit Code: 0" in result


def test_run_terminal_command_supports_pwd_builtin(tmp_path: Path) -> None:
    result = _raw_run_terminal_command("pwd", cwd=str(tmp_path))
    assert str(tmp_path.resolve()) in result
    assert "Exit Code: 0" in result


def test_run_terminal_command_mkdir_creates_directory(tmp_path: Path) -> None:
    new_dir = tmp_path / "abvc"
    result = _raw_run_terminal_command(f"mkdir {new_dir}", cwd=str(tmp_path))
    assert "Exit Code: 0" in result
    assert new_dir.is_dir()


def test_run_terminal_command_mkdir_nested(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    result = _raw_run_terminal_command(f"mkdir {nested}", cwd=str(tmp_path))
    assert "Exit Code: 0" in result
    assert nested.is_dir()


def test_run_terminal_command_rm_removes_file(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello")
    result = _raw_run_terminal_command(f"rm {f}", cwd=str(tmp_path))
    assert "Exit Code: 0" in result
    assert not f.exists()


def test_run_terminal_command_cp_copies_file(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("data")
    dst = tmp_path / "dst.txt"
    result = _raw_run_terminal_command(f"cp {src} {dst}", cwd=str(tmp_path))
    assert "Exit Code: 0" in result
    assert dst.read_text() == "data"


def test_run_terminal_command_mv_moves_file(tmp_path: Path) -> None:
    src = tmp_path / "old.txt"
    src.write_text("content")
    dst = tmp_path / "new.txt"
    result = _raw_run_terminal_command(f"mv {src} {dst}", cwd=str(tmp_path))
    assert "Exit Code: 0" in result
    assert dst.read_text() == "content"
    assert not src.exists()


def test_run_terminal_command_echo(tmp_path: Path) -> None:
    result = _raw_run_terminal_command("echo hello world", cwd=str(tmp_path))
    assert "hello world" in result
    assert "Exit Code: 0" in result


def test_run_terminal_command_cat_reads_file(tmp_path: Path) -> None:
    f = tmp_path / "read_me.txt"
    f.write_text("file contents here")
    result = _raw_run_terminal_command(f"cat {f}", cwd=str(tmp_path))
    assert "file contents here" in result
    assert "Exit Code: 0" in result


def test_run_terminal_command_which_finds_python(tmp_path: Path) -> None:
    result = _raw_run_terminal_command("which python", cwd=str(tmp_path))
    # Either found (exit 0) or not found (exit 1) — just must not crash.
    assert "Exit Code:" in result


def test_run_shell_script_executes_multi_line_output(tmp_path: Path) -> None:
    if os.name == "nt":
        script = 'Write-Output "hello"\nWrite-Output "world"'
    else:
        script = 'echo "hello"\necho "world"'
    result = _raw_run_shell_script(script, cwd=str(tmp_path))
    assert "hello" in result
    assert "world" in result
    assert "Exit Code: 0" in result


def test_run_shell_script_rejects_empty_script(tmp_path: Path) -> None:
    result = _raw_run_shell_script("   ", cwd=str(tmp_path))
    assert "Error" in result


def test_run_shell_script_rejects_invalid_cwd() -> None:
    result = _raw_run_shell_script("echo ok", cwd="/nonexistent/path/xyz")
    assert "Error" in result


def test_run_shell_script_handles_nonzero_exit(tmp_path: Path) -> None:
    if os.name == "nt":
        script = "exit 1"
    else:
        script = "exit 1"
    result = _raw_run_shell_script(script, cwd=str(tmp_path))
    assert "Exit Code: 1" in result


def test_read_file_returns_directory_listing_for_directory(tmp_path: Path) -> None:
    folder = tmp_path / "sample"
    folder.mkdir()
    (folder / "a.txt").write_text("a", encoding="utf-8")
    (folder / "sub").mkdir()

    from hachi.tools.os_tools import _raw_read_file

    result = _raw_read_file(str(folder))
    assert "Directory listing for" in result
    assert "- sub/" in result
    assert "- a.txt" in result


def test_mcp_env_is_scrubbed(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-leak")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    conn = MCPServerConnection(name="x", command="python")
    env = conn._build_subprocess_env()

    assert "ANTHROPIC_API_KEY" not in env
    assert "PATH" in env


def test_rest_adapter_blocks_private_hosts() -> None:
    registry = ToolRegistry()
    adapter = UniversalRestAdapter(registry)

    adapter._register_single_api(
        tool_name="private_probe",
        api_def={
            "method": "GET",
            "endpoint": "http://127.0.0.1:8000/health",
            "headers": "{}",
            "schema": "{}",
        },
        node_name="test-node",
    )

    result = registry._tools["private_probe"]()
    assert "Blocked by outbound policy" in result


def test_rest_adapter_requires_allowlist_for_secret_interpolation() -> None:
    # BB-53: an unset/empty allowlist now fails CLOSED for every host, not just
    # for secret-interpolating calls — so this scenario (no allowlist configured,
    # secret interpolation attempted) is blocked by the broader allowlist gate.
    registry = ToolRegistry()
    adapter = UniversalRestAdapter(
        registry,
        vault=_FakeVault({"api_token": "super-secret"}),
        allowed_hosts=[],
    )

    adapter._register_single_api(
        tool_name="token_call",
        api_def={
            "method": "GET",
            "endpoint": "https://example.com/api",
            "headers": '{"Authorization":"Bearer {api_token}"}',
            "schema": "{}",
        },
        node_name="test-node",
    )

    result = registry._tools["token_call"]()
    assert "HACHI_REST_ALLOWLIST is not configured" in result


def test_rest_allowlist_wildcard_matches_subdomains_only() -> None:
    assert UniversalRestAdapter._host_in_allowlist("api.example.com", ["*.example.com"]) is True
    assert UniversalRestAdapter._host_in_allowlist("example.com", ["*.example.com"]) is False
    assert UniversalRestAdapter._host_in_allowlist("api.evil.com", ["*.example.com"]) is False


def test_rest_adapter_blocks_dns_resolution_failures(monkeypatch) -> None:
    registry = ToolRegistry()
    adapter = UniversalRestAdapter(registry, allowed_hosts=["api.example.com"])
    # DNS resolution is performed by net_guard (the single SSRF source of truth),
    # which rest_adapter delegates to — patch getaddrinfo where it actually runs.
    monkeypatch.setattr(
        "hachi.core.net_guard.socket.getaddrinfo",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("dns failure")),
    )

    adapter._register_single_api(
        tool_name="dns_fail",
        api_def={
            "method": "GET",
            "endpoint": "https://api.example.com/v1/status",
            "headers": "{}",
            "schema": "{}",
        },
        node_name="test-node",
    )

    result = registry._tools["dns_fail"]()
    assert "Blocked by outbound policy" in result
    assert "DNS resolution failed" in result


def test_rest_adapter_rejects_host_header_override_tricks() -> None:
    registry = ToolRegistry()
    adapter = UniversalRestAdapter(registry, allowed_hosts=["api.example.com"])

    adapter._register_single_api(
        tool_name="host_header_trick",
        api_def={
            "method": "GET",
            "endpoint": "https://api.example.com/v1/status",
            "headers": '{"Host":"{api_token}"}',
            "schema": "{}",
        },
        node_name="test-node",
    )

    result = registry._tools["host_header_trick"]()
    assert "Host-routing headers are blocked by outbound policy" in result


def test_rest_adapter_allows_private_egress_when_explicitly_enabled(monkeypatch) -> None:
    class _FakeResponse:
        status_code = 200
        text = "ok"

        def raise_for_status(self) -> None:
            return

        def json(self) -> dict[str, str]:
            return {"ok": "true"}

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            return

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return

        def request(self, **_kwargs):
            return _FakeResponse()

    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "true")
    monkeypatch.setattr("hachi.core.rest_adapter.httpx.Client", _FakeClient)

    # BB-53: an empty allowlist now fails closed regardless of HACHI_REST_ALLOW_PRIVATE
    # (allow-private only affects net_guard's IP check, not the allowlist gate) — this
    # test is specifically about the private-egress opt-in, so give it an explicit
    # allowlist entry for the host under test.
    registry = ToolRegistry()
    adapter = UniversalRestAdapter(registry, allowed_hosts=["127.0.0.1"])

    adapter._register_single_api(
        tool_name="private_allowed",
        api_def={
            "method": "GET",
            "endpoint": "http://127.0.0.1:9000/health",
            "headers": "{}",
            "schema": "{}",
        },
        node_name="test-node",
    )

    result = registry._tools["private_allowed"]()
    # SEC-002: the response is framed as untrusted data; assert the payload survives.
    assert '"ok"' in result and "true" in result
