from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from hachi.cli.main import _InProcessGatewayRuntime
from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.onboarding import looks_like_env_var_name, persist_provider_api_key
from hachi.core.paths import HachiPaths
from hachi.core.settings import ResolvedConfig
from hachi.gateway.control_plane import GatewayProtocolError


class _FakeStore:
    """In-memory SecretStore double that records writes."""

    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.saved.get(name)

    def set(self, name: str, value: str, metadata=None) -> None:
        self.saved[name] = value

    def delete(self, name: str) -> None:
        self.saved.pop(name, None)

    def list_metadata(self) -> list:
        return []

    def healthcheck(self) -> dict:
        return {}


class _FakeConfig:
    def __init__(self) -> None:
        self.provider = SimpleNamespace(
            kind="anthropic",
            model="claude-haiku-4-5",
            base_url=None,
            api_key_ref=None,
            api_key_env="ANTHROPIC_API_KEY",
        )
        self.permissions = SimpleNamespace(tier="guided")
        self.memory = SimpleNamespace(
            enable_session_history=True,
            enable_semantic_memory=True,
        )

    def model_dump(self, mode: str = "python", exclude_none: bool = True):
        return {
            "provider": {
                "kind": self.provider.kind,
                "model": self.provider.model,
                "base_url": self.provider.base_url,
                "api_key_ref": self.provider.api_key_ref,
                "api_key_env": self.provider.api_key_env,
            },
            "permissions": {"tier": self.permissions.tier},
            "memory": {
                "enable_session_history": self.memory.enable_session_history,
                "enable_semantic_memory": self.memory.enable_semantic_memory,
            },
        }


def test_update_provider_accepts_supported_kinds(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()
    cfg.provider.kind = "openai-compatible"
    cfg.provider.model = "gpt-4.1-mini"

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    anthropic = runtime.update_provider(
        {"provider": {"kind": "anthropic", "model": "gpt-4.1-mini"}}
    )
    assert anthropic["provider"]["kind"] == "anthropic"
    assert anthropic["provider"]["model"] == "claude-haiku-4-5"

    openai = runtime.update_provider(
        {"provider": {"kind": "openai-compatible", "model": "gpt-4.1-mini"}}
    )
    assert openai["provider"]["kind"] == "openai-compatible"

    ollama = runtime.update_provider(
        {
            "provider": {
                "kind": "ollama",
                "model": "qwen2.5-coder:7b",
                "base_url": "http://127.0.0.1:11434",
            }
        }
    )
    assert ollama["provider"]["kind"] == "ollama"
    assert ollama["provider"]["base_url"] == "http://127.0.0.1:11434"


def test_update_provider_persists_raw_api_key_securely(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()
    store = _FakeStore()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: store)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # register for auto-cleanup

    result = runtime.update_provider(
        {"provider": {"kind": "anthropic", "api_key": "sk-ant-secret-1234567890"}}
    )

    # Raw key persisted to the secret store + process env under the env-var NAME.
    assert store.saved["ANTHROPIC_API_KEY"] == "sk-ant-secret-1234567890"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-secret-1234567890"
    # Config records only the NAME — the raw secret never lands in the config.
    assert result["provider"]["api_key_ref"] == "ANTHROPIC_API_KEY"
    assert result["provider"]["api_key_env"] == "ANTHROPIC_API_KEY"


def test_update_provider_treats_raw_key_in_api_key_ref_as_secret(monkeypatch) -> None:
    # Backward-compat: older web clients sent the raw key as `api_key_ref`.
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()
    store = _FakeStore()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: store)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    result = runtime.update_provider(
        {"provider": {"kind": "anthropic", "api_key_ref": "sk-ant-raw-9876543210"}}
    )

    assert store.saved["ANTHROPIC_API_KEY"] == "sk-ant-raw-9876543210"
    assert result["provider"]["api_key_ref"] == "ANTHROPIC_API_KEY"


def test_update_provider_preserves_env_name_api_key_ref(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()
    store = _FakeStore()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: store)

    result = runtime.update_provider(
        {"provider": {"kind": "anthropic", "api_key_ref": "ANTHROPIC_API_KEY"}}
    )

    # A legitimate reference NAME passes through unchanged; nothing is stored.
    assert result["provider"]["api_key_ref"] == "ANTHROPIC_API_KEY"
    assert store.saved == {}


def test_looks_like_env_var_name() -> None:
    assert looks_like_env_var_name("ANTHROPIC_API_KEY")
    assert looks_like_env_var_name("OPENAI_API_KEY")
    assert not looks_like_env_var_name("sk-ant-abc123")
    assert not looks_like_env_var_name("lower_case")
    assert not looks_like_env_var_name("")


def test_persist_provider_api_key(monkeypatch) -> None:
    store = _FakeStore()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    name = persist_provider_api_key("anthropic", "sk-ant-xyz", secret_store=store)

    assert name == "ANTHROPIC_API_KEY"
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-xyz"
    assert store.saved["ANTHROPIC_API_KEY"] == "sk-ant-xyz"


def test_persist_provider_api_key_blank_and_keyless_are_noops() -> None:
    store = _FakeStore()
    assert persist_provider_api_key("anthropic", "   ", secret_store=store) is None
    # ollama has no conventional env var → nothing to persist
    assert persist_provider_api_key("ollama", "whatever", secret_store=store) is None
    assert store.saved == {}


def test_update_provider_rejects_invalid_kind_and_blank_model(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="provider.kind must be"):
        runtime.update_provider({"provider": {"kind": "not-real"}})

    with pytest.raises(GatewayProtocolError, match="provider.model cannot be empty"):
        runtime.update_provider({"provider": {"model": "   "}})


def test_update_provider_currently_accepts_malformed_base_url(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    result = runtime.update_provider(
        {
            "provider": {
                "kind": "openai-compatible",
                "model": "gpt-4.1-mini",
                "base_url": "not-a-url",
            }
        }
    )

    # QA finding: malformed base_url is accepted verbatim today.
    assert result["provider"]["base_url"] == "not-a-url"


def test_validate_provider_reports_expected_warnings_and_errors() -> None:
    runtime = _InProcessGatewayRuntime()

    invalid = runtime.validate_provider({"provider": {"kind": "", "model": ""}})
    assert invalid["ok"] is False
    assert any("provider.kind" in item for item in invalid["errors"])
    assert any("provider.model" in item for item in invalid["errors"])

    remote_missing_auth = runtime.validate_provider(
        {"provider": {"kind": "openai-compatible", "model": "gpt-4.1-mini"}}
    )
    assert remote_missing_auth["ok"] is True
    assert any("api_key_ref or api_key_env" in item for item in remote_missing_auth["warnings"])

    ollama_missing_base = runtime.validate_provider(
        {"provider": {"kind": "ollama", "model": "llama3.1:8b"}}
    )
    assert ollama_missing_base["ok"] is True
    assert any("base_url is recommended" in item for item in ollama_missing_base["warnings"])


def test_update_permissions_rejects_invalid_tier(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="permissions.tier must be"):
        runtime.update_permissions({"permissions": {"tier": "root"}})


def test_update_permissions_accepts_supported_tiers(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    for tier in ("sandbox", "guided", "unrestricted"):
        result = runtime.update_permissions({"permissions": {"tier": tier}})
        assert result["permissions"]["tier"] == tier


def test_update_memory_is_idempotent_for_noop_payload(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    baseline = runtime.update_memory({"memory": {}})
    repeated = runtime.update_memory({"memory": {}})

    assert baseline["memory"] == repeated["memory"]
    assert baseline["memory"]["enable_session_history"] is True
    assert baseline["memory"]["enable_semantic_memory"] is True


def test_update_memory_partial_write_preserves_other_fields(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _FakeConfig()

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    result = runtime.update_memory({"memory": {"enable_session_history": False}})

    assert result["memory"]["enable_session_history"] is False
    assert result["memory"]["enable_semantic_memory"] is True


# --- "Ask before…" persistence (PUT /config/permissions ask_before) ----------


def _real_cfg() -> ResolvedConfig:
    """A real ResolvedConfig so permissions.ask_before is a true AskBeforeSettings."""
    return ResolvedConfig()


def test_update_permissions_persists_ask_before_rule(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _real_cfg()
    captured: list[ResolvedConfig] = []
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", captured.append)

    result = runtime.update_permissions({"permissions": {"ask_before": {"delete_files": False}}})

    assert result["permissions"]["ask_before"]["delete_files"] is False
    # Untouched rules keep their default (on).
    assert result["permissions"]["ask_before"]["network_egress"] is True
    assert result["permissions"]["ask_before"]["spend_over_threshold"] is True
    # The same config object was handed to write_global_config (persisted).
    assert captured and captured[0].permissions.ask_before.delete_files is False


def test_update_permissions_tier_and_ask_before_together(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _real_cfg()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    result = runtime.update_permissions(
        {"permissions": {"tier": "sandbox", "ask_before": {"network_egress": False}}}
    )

    assert result["permissions"]["tier"] == "sandbox"
    assert result["permissions"]["ask_before"]["network_egress"] is False


def test_update_permissions_rejects_unknown_ask_before_key(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _real_cfg()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="not a recognised rule"):
        runtime.update_permissions({"permissions": {"ask_before": {"format_disk": True}}})


def test_update_permissions_rejects_non_bool_ask_before_value(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _real_cfg()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="must be a boolean"):
        runtime.update_permissions({"permissions": {"ask_before": {"delete_files": "yes"}}})


def test_update_permissions_rejects_non_object_ask_before(monkeypatch) -> None:
    runtime = _InProcessGatewayRuntime()
    cfg = _real_cfg()
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.write_global_config", lambda _config: None)

    with pytest.raises(GatewayProtocolError, match="ask_before must be an object"):
        runtime.update_permissions({"permissions": {"ask_before": ["delete_files"]}})


def test_ask_before_round_trips_through_settings_toml(tmp_path) -> None:
    """A toggle written by the handler is read back verbatim after a fresh load."""
    paths = HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )

    cfg = load_effective_config(paths=paths)
    cfg.permissions.ask_before.delete_files = False
    cfg.permissions.tier = "unrestricted"
    write_global_config(cfg, paths=paths)

    reloaded = load_effective_config(paths=paths)
    assert reloaded.permissions.ask_before.delete_files is False
    assert reloaded.permissions.ask_before.network_egress is True
    assert reloaded.permissions.ask_before.spend_over_threshold is True
    assert reloaded.permissions.tier == "unrestricted"
