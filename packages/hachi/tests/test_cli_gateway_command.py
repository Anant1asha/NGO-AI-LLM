from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from hachi.cli.main import _apply_quick_setup_if_needed, app

runner = CliRunner()


def test_gateway_command_starts_and_stops_server(monkeypatch) -> None:
    server_state: dict[str, object] = {
        "started": False,
        "stopped": False,
        "host": None,
        "port": None,
    }

    class FakeServer:
        def __init__(
            self, _control_plane, host: str, port: int, auth_token: str | None = None
        ) -> None:
            server_state["host"] = host
            server_state["port"] = port
            server_state["auth_token"] = auth_token

        def start(self) -> int:
            server_state["started"] = True
            return 9001

        def stop(self) -> None:
            server_state["stopped"] = True

    def _raise_interrupt() -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.GatewayHTTPServer", FakeServer)
    monkeypatch.setattr("hachi.cli.main._wait_until_interrupted", _raise_interrupt)
    monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN", "test-token")

    result = runner.invoke(app, ["gateway", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 0
    assert server_state["started"] is True
    assert server_state["stopped"] is True
    assert server_state["host"] == "0.0.0.0"
    assert server_state["port"] == 9000
    assert server_state["auth_token"] == "test-token"


def test_gateway_command_returns_error_when_server_fails(monkeypatch) -> None:
    class FailingServer:
        def __init__(
            self, _control_plane, host: str, port: int, auth_token: str | None = None
        ) -> None:
            self._host = host
            self._port = port
            self._auth_token = auth_token

        def start(self) -> int:
            raise OSError("port already in use")

        def stop(self) -> None:
            return None

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.GatewayHTTPServer", FailingServer)

    result = runner.invoke(app, ["gateway", "--port", "9000"])

    assert result.exit_code == 1
    assert "Failed to start gateway server" in result.stdout


def test_gateway_command_requires_auth_token_for_non_loopback_host(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)

    result = runner.invoke(app, ["gateway", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 1
    assert "HACHI_GATEWAY_API_TOKEN_FILE" in result.stdout


def test_gateway_command_reads_auth_token_from_file(monkeypatch, tmp_path: Path) -> None:
    server_state: dict[str, object] = {}
    token_file = tmp_path / "gateway-token.txt"
    token_file.write_text("file-secret-token", encoding="utf-8")

    class FakeServer:
        def __init__(
            self, _control_plane, host: str, port: int, auth_token: str | None = None
        ) -> None:
            server_state["host"] = host
            server_state["port"] = port
            server_state["auth_token"] = auth_token

        def start(self) -> int:
            return 9001

        def stop(self) -> None:
            return None

    def _raise_interrupt() -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.GatewayHTTPServer", FakeServer)
    monkeypatch.setattr("hachi.cli.main._wait_until_interrupted", _raise_interrupt)
    monkeypatch.delenv("HACHI_GATEWAY_API_TOKEN", raising=False)
    monkeypatch.setenv("HACHI_GATEWAY_API_TOKEN_FILE", str(token_file))

    result = runner.invoke(app, ["gateway", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 0
    assert server_state["auth_token"] == "file-secret-token"


def test_gateway_command_passes_runtime_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_gateway_http_server(host: str, port: int, attach_runtime: bool) -> None:
        captured["host"] = host
        captured["port"] = port
        captured["attach_runtime"] = attach_runtime

    monkeypatch.setattr("hachi.cli.main._run_gateway_http_server", _fake_run_gateway_http_server)

    result = runner.invoke(app, ["gateway", "--port", "8999", "--no-runtime"])

    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8999
    assert captured["attach_runtime"] is False


def test_run_command_launches_tui_in_local_mode(monkeypatch) -> None:
    state: dict[str, object] = {
        "cockpit_launched": False,
    }

    def _fake_launch_cockpit(**kwargs) -> None:  # noqa: ANN003
        state["cockpit_launched"] = True

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.ensure_device_permissions", lambda _console: None)
    monkeypatch.setattr("hachi.cli.main._launch_cockpit", _fake_launch_cockpit)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert state["cockpit_launched"] is True


def test_bare_invocation_launches_tui(monkeypatch) -> None:
    state: dict[str, object] = {"cockpit_launched": False}

    def _fake_launch_cockpit(**kwargs) -> None:  # noqa: ANN003
        state["cockpit_launched"] = True

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.ensure_device_permissions", lambda _console: None)
    monkeypatch.setattr("hachi.cli.main._launch_cockpit", _fake_launch_cockpit)

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert state["cockpit_launched"] is True


def test_run_repl_skips_gateway_bootstrap(monkeypatch) -> None:
    state: dict[str, bool] = {
        "run_repl_called": False,
        "gateway_started": False,
    }

    def _fake_run_repl() -> None:
        state["run_repl_called"] = True

    def _fake_start_gateway_server(
        host: str = "127.0.0.1",
        port: int = 0,
        attach_runtime: bool = False,
    ):
        state["gateway_started"] = True
        raise AssertionError("gateway should not start for --repl")

    monkeypatch.setattr("hachi.cli.main.ensure_workspace", lambda: None)
    monkeypatch.setattr("hachi.cli.main._apply_quick_setup_if_needed", lambda: None)
    monkeypatch.setattr("hachi.cli.main._pre_flight_check", lambda: True)
    monkeypatch.setattr("hachi.cli.main.ensure_device_permissions", lambda _console: None)
    monkeypatch.setattr("hachi.cli.main._run_repl", _fake_run_repl)
    monkeypatch.setattr("hachi.cli.main._start_gateway_server", _fake_start_gateway_server)

    result = runner.invoke(app, ["run", "--repl"])

    assert result.exit_code == 0
    assert state["run_repl_called"] is True
    assert state["gateway_started"] is False


def test_apply_quick_setup_runs_only_when_needed(monkeypatch) -> None:
    state: dict[str, int] = {
        "best_provider": 0,
        "build": 0,
        "apply": 0,
    }

    class FakeOnboardingService:
        def __init__(self) -> None:
            self._needs_setup = True

        def needs_setup(self) -> bool:
            return self._needs_setup

        def best_provider_from_env(self) -> dict:
            state["best_provider"] += 1
            return {
                "kind": "anthropic",
                "model": "claude-haiku-4-5",
                "api_key_env": "ANTHROPIC_API_KEY",
            }

        def build_tier_plan(self, tier: str, answers: dict) -> dict:
            state["build"] += 1
            assert tier == "lightning"
            assert answers["permission_tier"] == "guided"
            return {"tier": tier, "answers": answers}

        def apply_setup(self, plan: dict) -> None:
            state["apply"] += 1
            assert plan["tier"] == "lightning"

    monkeypatch.setattr("hachi.cli.main.OnboardingService", FakeOnboardingService)
    _apply_quick_setup_if_needed()

    assert state == {"best_provider": 1, "build": 1, "apply": 1}


def test_apply_quick_setup_skips_when_already_configured(monkeypatch) -> None:
    state: dict[str, int] = {
        "detect": 0,
        "build": 0,
        "apply": 0,
    }

    class FakeOnboardingService:
        def needs_setup(self) -> bool:
            return False

        def detect_environment(self) -> dict[str, bool]:
            state["detect"] += 1
            return {}

        def build_tier_plan(self, tier: str, answers: dict) -> dict:
            state["build"] += 1
            return {}

        def apply_setup(self, plan: dict) -> None:
            state["apply"] += 1

    monkeypatch.setattr("hachi.cli.main.OnboardingService", FakeOnboardingService)
    _apply_quick_setup_if_needed()

    assert state == {"detect": 0, "build": 0, "apply": 0}


def test_doctor_command_reports_environment(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    settings_toml = config_dir / "settings.toml"

    for directory in (config_dir, data_dir, state_dir):
        directory.mkdir()
    settings_toml.write_text("[provider]\nkind='anthropic'\n", encoding="utf-8")

    fake_paths = SimpleNamespace(
        config_dir=config_dir,
        data_dir=data_dir,
        state_dir=state_dir,
        global_config_toml=settings_toml,
        skills_dir=data_dir / "skills",
    )
    fake_config = SimpleNamespace(
        provider=SimpleNamespace(kind="anthropic", model="claude-haiku-4-5", api_key_env=None),
        permissions=SimpleNamespace(tier="guided"),
    )

    class FakeOnboardingService:
        def __init__(self, paths) -> None:
            self.paths = paths

        def needs_setup(self) -> bool:
            return False

        def validate_provider(self, *, kind, api_key_env=None):
            return (True, "ok")

        def detect_environment(self) -> dict[str, bool]:
            return {"anthropic_env": True}

    class FakeSecretStore:
        def healthcheck(self) -> dict[str, str]:
            return {"backend": "memory", "status": "ok"}

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: fake_paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_config)
    monkeypatch.setattr("hachi.cli.main.OnboardingService", FakeOnboardingService)
    monkeypatch.setattr(
        "hachi.cli.main.create_default_secret_store",
        lambda paths=None: FakeSecretStore(),
    )
    # Exercise the safety/limits surfacing deterministically.
    monkeypatch.setenv("HACHI_MAX_SESSION_COST_USD", "5.0")
    monkeypatch.setenv("HACHI_ALLOW_OUTBOUND_SECRETS", "true")
    monkeypatch.delenv("HACHI_MAX_SESSION_TOKENS", raising=False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "provider_kind" in result.stdout
    assert "anthropic" in result.stdout
    assert "secret_backend" in result.stdout
    assert "environment_detection" in result.stdout
    # skills_health is reported; with no skills dir it degrades gracefully.
    assert "skills_health" in result.stdout
    assert "no skills directory yet" in result.stdout
    # MCP count + the new safety/limits posture section.
    assert "mcp_servers_declared" in result.stdout
    assert "safety_and_limits" in result.stdout
    assert "5.0" in result.stdout  # cost cap echoed
    # The outbound-secret guard is reported disabled when the override is set.
    assert '"outbound_secret_guard": "disabled"' in result.stdout
    assert "session_token_cap" in result.stdout


def test_doctor_json_is_parseable(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    for directory in (config_dir, data_dir):
        directory.mkdir()
    settings_toml = config_dir / "settings.toml"
    settings_toml.write_text("[provider]\nkind='anthropic'\n", encoding="utf-8")

    fake_paths = SimpleNamespace(
        config_dir=config_dir,
        data_dir=data_dir,
        state_dir=tmp_path / "state",
        global_config_toml=settings_toml,
        skills_dir=data_dir / "skills",
    )
    fake_config = SimpleNamespace(
        provider=SimpleNamespace(kind="anthropic", model="claude-haiku-4-5", api_key_env=None),
        permissions=SimpleNamespace(tier="guided"),
    )

    class FakeOnboardingService:
        def __init__(self, paths) -> None:
            self.paths = paths

        def needs_setup(self) -> bool:
            return False

        def validate_provider(self, *, kind, api_key_env=None):
            return (True, "ok")

        def detect_environment(self) -> dict[str, bool]:
            return {"anthropic_env": True}

    class FakeSecretStore:
        def healthcheck(self) -> dict[str, str]:
            return {"backend": "memory", "status": "ok"}

    monkeypatch.setattr("hachi.cli.main.get_hachi_paths", lambda: fake_paths)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_config)
    monkeypatch.setattr("hachi.cli.main.OnboardingService", FakeOnboardingService)
    monkeypatch.setattr(
        "hachi.cli.main.create_default_secret_store", lambda paths=None: FakeSecretStore()
    )

    # Narrow console: --json must emit via plain print() so the payload is NOT
    # soft-wrapped to the terminal width (which would break json.loads).
    result = runner.invoke(app, ["doctor", "--json"], env={"COLUMNS": "40"})
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["provider_kind"] == "anthropic"
    assert "safety_and_limits" in payload
    assert payload["safety_and_limits"]["tracing"] in ("off", "true", "false")
    assert "mcp_servers_declared" in payload


def test_security_audit_json_reports_findings_and_exit_code(monkeypatch, tmp_path: Path) -> None:
    permissions_file = tmp_path / "device-permissions.og"
    permissions_file.write_text("", encoding="utf-8")

    fake_config = SimpleNamespace(
        permissions=SimpleNamespace(tier="unrestricted"),
        capabilities={
            "slack": SimpleNamespace(enabled=True, secret_ref=None),
            "notion": SimpleNamespace(enabled=False, secret_ref=None),
        },
    )

    class FakePermissionGate:
        def __init__(self, _permissions_file: Path) -> None:
            self._term = SimpleNamespace(allow_all=True)

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_config)
    monkeypatch.setattr("hachi.cli.main.get_permissions_file", lambda: permissions_file)
    monkeypatch.setattr("hachi.cli.main.PermissionGate", FakePermissionGate)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("HACHI_REST_ALLOWLIST", raising=False)
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "false")

    # Force a narrow console: --json must emit via plain print() so the payload
    # is NOT soft-wrapped to the terminal width (which would break json.loads).
    result = runner.invoke(
        app, ["security-audit", "--json", "--fail-on-high"], env={"COLUMNS": "40"}
    )

    assert result.exit_code == 2
    # The machine-readable payload parses straight from stdout (regression: was
    # routed through console.print, which wrapped long lines mid-token).
    payload = json.loads(result.stdout)
    check_ids = {finding["check_id"] for finding in payload["findings"]}

    assert payload["status"] == "fail"
    assert payload["exit_code"] == 2
    assert "oauth.google_client_id_missing" in check_ids
    assert "permissions.unrestricted_tier" in check_ids
    assert "terminal.allow_all" in check_ids
    assert "rest.allowlist_missing" in check_ids
    assert "sandbox.process_backend" in check_ids


def _security_audit_fixture(monkeypatch, tmp_path: Path) -> None:
    """Point security-audit at a config that reliably produces findings."""
    permissions_file = tmp_path / "device-permissions.og"
    permissions_file.write_text("", encoding="utf-8")

    fake_config = SimpleNamespace(
        permissions=SimpleNamespace(tier="unrestricted"),
        capabilities={},
    )

    class FakePermissionGate:
        def __init__(self, _permissions_file: Path) -> None:
            self._term = SimpleNamespace(allow_all=True)

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: fake_config)
    monkeypatch.setattr("hachi.cli.main.get_permissions_file", lambda: permissions_file)
    monkeypatch.setattr("hachi.cli.main.PermissionGate", FakePermissionGate)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("HACHI_REST_ALLOWLIST", raising=False)
    # A developer machine with HACHI_SANDBOX_BACKEND=container and no Docker
    # flips the sandbox finding to `sandbox.container_unavailable`, which would
    # make the ignore-checks tests depend on the host's setup.
    monkeypatch.delenv("HACHI_SANDBOX_BACKEND", raising=False)
    monkeypatch.setenv("HACHI_REST_ALLOW_PRIVATE", "false")


def test_security_audit_ignore_checks_excludes_findings(monkeypatch, tmp_path: Path) -> None:
    """--ignore-checks suppresses named checks so CI can gate on the rest.

    Regression for the open-source launch blocker: the PR security gate ran
    --fail-on-medium, but `sandbox.process_backend` describes the *runner's*
    deployment posture and can never be resolved by a contributor's diff, so
    every external PR was red for reasons unrelated to its contents. CI now
    ignores that one check id while keeping the strict gate for everything else.
    """
    _security_audit_fixture(monkeypatch, tmp_path)

    result = runner.invoke(
        app,
        [
            "security-audit",
            "--json",
            "--fail-on-medium",
            "--ignore-checks",
            "sandbox.process_backend",
        ],
        env={"COLUMNS": "40"},
    )

    payload = json.loads(result.stdout)
    check_ids = {finding["check_id"] for finding in payload["findings"]}

    # The ignored check is gone from the report entirely (not merely de-counted),
    # so the JSON a CI consumer reads matches what was actually gated on.
    assert "sandbox.process_backend" not in check_ids
    # Everything not ignored still reports.
    assert "oauth.google_client_id_missing" in check_ids
    assert "rest.allowlist_missing" in check_ids
    # The echoed contract is what CI reads to know what it gated on.
    assert payload["ignored_checks"] == ["sandbox.process_backend"]
    assert payload["ignored_checks_unmatched"] == []
    # Still fails on the remaining highs — filtering must not clear the gate.
    assert payload["exit_code"] == 2
    assert payload["status"] == "fail"


def test_security_audit_reports_ignore_ids_that_matched_nothing(
    monkeypatch, tmp_path: Path
) -> None:
    """A typo'd or renamed check id must be visible, not silently a no-op.

    `--ignore-checks "sandbox.process back-end"` previously echoed the requested
    string while the real finding survived — so the log said "ignored" and the
    gate still failed, with nothing pointing at the mismatch.
    """
    _security_audit_fixture(monkeypatch, tmp_path)

    result = runner.invoke(
        app,
        [
            "security-audit",
            "--json",
            "--fail-on-medium",
            "--ignore-checks",
            "sandbox.process back-end",
        ],
        env={"COLUMNS": "40"},
    )

    payload = json.loads(result.stdout)
    check_ids = {finding["check_id"] for finding in payload["findings"]}
    assert "sandbox.process_backend" in check_ids, "the real check must survive a typo"
    assert payload["ignored_checks_unmatched"] == ["sandbox.process back-end"]
    assert payload["exit_code"] == 2


def test_security_audit_ignore_checks_can_clear_the_gate(monkeypatch, tmp_path: Path) -> None:
    """Ignoring every remaining finding makes the gate pass — deterministically.

    Pins the property CI relies on: the gate outcome is a function of the
    ignore set, not of whether Docker happens to be on the runner.
    """
    _security_audit_fixture(monkeypatch, tmp_path)

    all_ids = (
        "oauth.google_client_id_missing,permissions.unrestricted_tier,"
        "terminal.allow_all,rest.allowlist_missing,sandbox.process_backend"
    )
    result = runner.invoke(
        app,
        ["security-audit", "--json", "--fail-on-medium", "--ignore-checks", all_ids],
        env={"COLUMNS": "40"},
    )

    payload = json.loads(result.stdout)
    assert payload["findings"] == []
    assert payload["exit_code"] == 0, payload
    assert result.exit_code == 0


def test_security_audit_ignore_checks_tolerates_whitespace(monkeypatch, tmp_path: Path) -> None:
    """A comma list with stray spaces is accepted (people write them in YAML)."""
    _security_audit_fixture(monkeypatch, tmp_path)

    result = runner.invoke(
        app,
        [
            "security-audit",
            "--json",
            "--fail-on-medium",
            "--ignore-checks",
            " terminal.allow_all , sandbox.process_backend ",
        ],
        env={"COLUMNS": "40"},
    )

    payload = json.loads(result.stdout)
    check_ids = {finding["check_id"] for finding in payload["findings"]}
    assert "terminal.allow_all" not in check_ids
    assert "sandbox.process_backend" not in check_ids
