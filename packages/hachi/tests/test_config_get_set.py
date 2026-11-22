"""Tests for `hachi config-get` and `hachi config-set`.

These tests exercise the **real** ``ResolvedConfig`` shape. The previous version
of this file (WB-N07 in the 2026-06-18-v2 audit) mocked a flat ``SimpleNamespace``
with ``safety_tier`` / ``max_tokens`` / ``session_cost_cap_usd`` as top-level
attributes — a shape the real ``ResolvedConfig`` never had (it exposes
``permissions.tier``, ``agent.max_tokens``, and ``limits.max_session_cost_usd``).
That false-green let ``config-get`` ship a 100%-reproducible ``AttributeError``
crash while the suite stayed green. The rule going forward: use the real type,
and prove persistence with a real config-file round-trip.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.core.paths import HachiPaths
from hachi.core.settings import ResolvedConfig, default_config

runner = CliRunner()

_ENV_VARS = (
    "HACHI_MAX_SESSION_COST_USD",
    "HACHI_PERMISSION_TIER",
    "HACHI_MAX_TOKENS",
    "HACHI_MODEL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OLLAMA_HOST",
)


def _real_cfg() -> ResolvedConfig:
    """A REAL ResolvedConfig with known values — the actual type the command sees."""
    cfg = default_config()
    cfg.provider.model = "claude-sonnet-4-6"
    cfg.permissions.tier = "guided"
    cfg.agent.max_tokens = 8192
    cfg.limits.max_session_cost_usd = 5.0
    return cfg


def _patch_cfg(cfg: ResolvedConfig | None = None):
    return patch("hachi.cli.main.load_effective_config", return_value=cfg or _real_cfg())


def _patch_write():
    return patch("hachi.cli.main.write_global_config")


def _patch_workspace():
    return patch("hachi.cli.main.get_workspace_dir", return_value=Path("/home/user/.hachi"))


def _tmp_paths(tmp: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp / "config",
        data_dir=tmp / "data",
        cache_dir=tmp / "cache",
        state_dir=tmp / "state",
    )


# ─── config-get (real ResolvedConfig — would crash on any wrong attribute path) ──


class TestConfigGet:
    def test_no_key_lists_all_canonical(self) -> None:
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get"])
        assert result.exit_code == 0, result.output
        assert "provider.model" in result.output
        assert "permissions.tier" in result.output
        assert "agent.max_tokens" in result.output
        assert "limits.max_session_cost_usd" in result.output

    def test_specific_canonical_key(self) -> None:
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get", "permissions.tier"])
        assert result.exit_code == 0, result.output
        assert "guided" in result.output

    def test_alias_key_resolves(self) -> None:
        # The documented short name must still work (maps to permissions.tier).
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get", "safety_tier"])
        assert result.exit_code == 0, result.output
        assert "guided" in result.output

    def test_json_no_key_emits_dict(self) -> None:
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider.model"] == "claude-sonnet-4-6"
        assert data["permissions.tier"] == "guided"
        assert data["agent.max_tokens"] == 8192
        assert data["limits.max_session_cost_usd"] == 5.0

    def test_json_cost_cap_via_alias(self) -> None:
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get", "session_cost_cap_usd", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["session_cost_cap_usd"] == 5.0

    def test_unknown_key_exits_1(self) -> None:
        with _patch_cfg(), _patch_workspace():
            result = runner.invoke(app, ["config-get", "no.such.key"])
        assert result.exit_code == 1
        assert "Unknown key" in result.output


# ─── config-set (mutates the REAL nested config object) ──────────────────────


class TestConfigSet:
    def test_set_provider_model(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write() as mock_write:
            result = runner.invoke(app, ["config-set", "provider.model", "claude-opus-4-8"])
        assert result.exit_code == 0, result.output
        assert cfg.provider.model == "claude-opus-4-8"
        mock_write.assert_called_once_with(cfg)

    def test_set_safety_tier_alias_maps_to_permissions_tier(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "safety_tier", "sandbox"])
        assert result.exit_code == 0, result.output
        assert cfg.permissions.tier == "sandbox"

    def test_set_permissions_tier_canonical(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "permissions.tier", "unrestricted"])
        assert result.exit_code == 0, result.output
        assert cfg.permissions.tier == "unrestricted"

    def test_set_tier_invalid_exits_1(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "safety_tier", "danger"])
        assert result.exit_code == 1
        assert "sandbox" in result.output

    def test_set_max_tokens_alias(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "max_tokens", "16384"])
        assert result.exit_code == 0, result.output
        assert cfg.agent.max_tokens == 16384

    def test_set_max_tokens_non_int_exits_1(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "max_tokens", "not-a-number"])
        assert result.exit_code == 1

    def test_set_cost_cap_alias(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "session_cost_cap_usd", "2.5"])
        assert result.exit_code == 0, result.output
        assert cfg.limits.max_session_cost_usd == 2.5

    def test_set_cost_cap_canonical(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "limits.max_session_cost_usd", "3"])
        assert result.exit_code == 0, result.output
        assert cfg.limits.max_session_cost_usd == 3.0

    def test_set_negative_cost_cap_exits_1(self) -> None:
        cfg = _real_cfg()
        # A leading '-' is parsed as an option, so a negative value needs the
        # '--' separator to reach the command's own >= 0 validation.
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "session_cost_cap_usd", "--", "-1"])
        assert result.exit_code == 1
        assert ">= 0" in result.output or "session_cost_cap_usd" in result.output

    def test_set_unknown_key_exits_1(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(app, ["config-set", "no.such.key", "value"])
        assert result.exit_code == 1
        assert "Cannot set" in result.output

    def test_json_output_on_success(self) -> None:
        cfg = _real_cfg()
        with _patch_cfg(cfg), _patch_write():
            result = runner.invoke(
                app, ["config-set", "provider.model", "claude-haiku-4-5", "--json"]
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["key"] == "provider.model"
        assert data["value"] == "claude-haiku-4-5"


# ─── Round-trip against a real settings.toml (catches persistence, not just mutation) ──


class TestConfigRoundTrip:
    def test_cost_cap_persists_to_limits_section(self, tmp_path: Path, monkeypatch) -> None:
        """A cost cap set via the alias must land in the [limits] section the
        orchestrator actually reads (limits.max_session_cost_usd), so it is enforced."""
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        paths = _tmp_paths(tmp_path)
        with (
            patch("hachi.cli.main.get_hachi_paths", return_value=paths),
            patch("hachi.core.config_loader.get_hachi_paths", return_value=paths),
            patch("hachi.cli.main.get_workspace_dir", return_value=tmp_path),
        ):
            set_res = runner.invoke(app, ["config-set", "session_cost_cap_usd", "2.5"])
            assert set_res.exit_code == 0, set_res.output

            toml_text = paths.global_config_toml.read_text(encoding="utf-8")
            assert "[limits]" in toml_text
            assert "max_session_cost_usd" in toml_text

            get_res = runner.invoke(app, ["config-get", "session_cost_cap_usd", "--json"])
            assert get_res.exit_code == 0, get_res.output
            assert json.loads(get_res.output)["session_cost_cap_usd"] == 2.5

    def test_safety_tier_persists_and_reloads(self, tmp_path: Path, monkeypatch) -> None:
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        paths = _tmp_paths(tmp_path)
        with (
            patch("hachi.cli.main.get_hachi_paths", return_value=paths),
            patch("hachi.core.config_loader.get_hachi_paths", return_value=paths),
            patch("hachi.cli.main.get_workspace_dir", return_value=tmp_path),
        ):
            set_res = runner.invoke(app, ["config-set", "safety_tier", "sandbox"])
            assert set_res.exit_code == 0, set_res.output

            toml_text = paths.global_config_toml.read_text(encoding="utf-8")
            assert "[permissions]" in toml_text
            assert "sandbox" in toml_text

            get_res = runner.invoke(app, ["config-get", "permissions.tier"])
            assert get_res.exit_code == 0, get_res.output
            assert "sandbox" in get_res.output

    def test_empty_limits_not_written_when_no_cap(self, tmp_path: Path, monkeypatch) -> None:
        """Setting an unrelated key must not write an empty [limits] table."""
        for var in _ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        paths = _tmp_paths(tmp_path)
        with (
            patch("hachi.cli.main.get_hachi_paths", return_value=paths),
            patch("hachi.core.config_loader.get_hachi_paths", return_value=paths),
            patch("hachi.cli.main.get_workspace_dir", return_value=tmp_path),
        ):
            set_res = runner.invoke(app, ["config-set", "provider.model", "claude-opus-4-8"])
            assert set_res.exit_code == 0, set_res.output
            toml_text = paths.global_config_toml.read_text(encoding="utf-8")
            assert "[limits]" not in toml_text
