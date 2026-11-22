"""Tests for hachi.gateway.provider_admin — multi-provider config vertical.

Covers:
  - add/list/remove provider round-trips (monkeypatched config path)
  - get_routing synthesizes 12 rows when [routing] is absent
  - kind allowlist accepts all ProviderKind values (e.g. "openrouter")
  - set_routing persists and returns updated matrix
  - list_all_models returns provider-keyed dict
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hachi.core.settings import ProviderSettings, ResolvedConfig
from hachi.gateway.provider_admin import (
    CAPABILITY_ORDER,
    add_or_update_provider,
    get_routing,
    list_all_models,
    list_providers,
    remove_provider,
    set_routing,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs: Any) -> ResolvedConfig:
    """Build a minimal ResolvedConfig with optional overrides."""
    cfg = ResolvedConfig()
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _patch_config(config: ResolvedConfig):
    """Context manager: patch load_effective_config + write_global_config."""
    written: list[ResolvedConfig] = []

    def _fake_load(**_kwargs: Any) -> ResolvedConfig:
        return config

    def _fake_write(cfg: ResolvedConfig, **_kwargs: Any) -> Path:
        # Mutate in-place so subsequent calls see the change
        config.__dict__.update(cfg.__dict__)
        written.append(cfg)
        return Path("/tmp/fake-settings.toml")

    ctx_load = patch("hachi.gateway.provider_admin.load_effective_config", side_effect=_fake_load)
    ctx_write = patch("hachi.gateway.provider_admin.write_global_config", side_effect=_fake_write)
    return ctx_load, ctx_write, written


# ---------------------------------------------------------------------------
# list_providers
# ---------------------------------------------------------------------------


class TestListProviders:
    def test_returns_primary_only_when_no_named_providers(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_providers()
        assert "providers" in result
        names = [p["name"] for p in result["providers"]]
        assert "__primary__" in names

    def test_includes_named_providers(self) -> None:
        cfg = _make_config()
        cfg.providers = {"openrouter": ProviderSettings(kind="openrouter", model="openai/gpt-4o")}
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_providers()
        names = [p["name"] for p in result["providers"]]
        assert "openrouter" in names

    def test_secrets_masked(self) -> None:
        cfg = _make_config()
        cfg.provider.api_key_ref = "ANTHROPIC_API_KEY"
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_providers()
        primary = next(p for p in result["providers"] if p["name"] == "__primary__")
        assert "api_key_ref" not in primary
        assert primary["configured"] is True


# ---------------------------------------------------------------------------
# add_or_update_provider
# ---------------------------------------------------------------------------


class TestAddOrUpdateProvider:
    def test_add_named_provider(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, written = _patch_config(cfg)

        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
        ):
            result = add_or_update_provider(
                "my-groq",
                {"kind": "groq", "model": "llama-3.1-8b-instant"},
            )

        assert result["name"] == "my-groq"
        assert result["kind"] == "groq"
        assert written, "write_global_config must be called"

    def test_add_openrouter_accepted(self) -> None:
        """kind=openrouter must not raise ValueError."""
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
        ):
            result = add_or_update_provider(
                "or1",
                {"kind": "openrouter", "model": "openai/gpt-4o-mini"},
            )
        assert result["kind"] == "openrouter"

    def test_all_valid_kinds_accepted(self) -> None:
        """Every ProviderKind must be accepted by add_or_update_provider."""
        from typing import get_args

        from hachi.core.settings import ProviderKind

        for kind in get_args(ProviderKind):
            cfg = _make_config()
            ctx_load, ctx_write, _ = _patch_config(cfg)
            with (
                ctx_load,
                ctx_write,
                patch("hachi.gateway.provider_admin.CredentialVault"),
                patch("hachi.gateway.provider_admin.create_default_secret_store"),
            ):
                result = add_or_update_provider(
                    f"test-{kind}",
                    {"kind": kind, "model": "any-model"},
                )
            assert result["kind"] == kind, f"kind={kind!r} should be accepted"

    def test_invalid_kind_raises(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="kind"):
            add_or_update_provider("bad", {"kind": "banana", "model": "x"})

    def test_empty_name_raises(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="name"):
            add_or_update_provider("  ", {"kind": "anthropic", "model": "x"})

    def test_api_key_stored_in_vault(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)

        mock_vault = MagicMock()
        mock_vault_cls = MagicMock(return_value=mock_vault)

        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault", mock_vault_cls),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
            patch.dict(os.environ, {}, clear=False),
        ):
            add_or_update_provider(
                "sec-test",
                {"kind": "anthropic", "model": "claude-haiku-4-5", "api_key": "sk-test-1234"},
            )

        mock_vault.set_token.assert_called_once()
        call_args = mock_vault.set_token.call_args[0]
        assert call_args[0] == "provider.sec-test.api_key"
        assert call_args[1] == "sk-test-1234"

    def test_update_primary_provider(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, written = _patch_config(cfg)
        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
        ):
            result = add_or_update_provider(
                "__primary__",
                {"kind": "anthropic", "model": "claude-opus-4-8"},
            )
        assert result["name"] == "__primary__"
        assert result["model"] == "claude-opus-4-8"
        assert written

    def test_base_url_persisted(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, written = _patch_config(cfg)
        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
        ):
            result = add_or_update_provider(
                "local-llm",
                {
                    "kind": "openai-compatible",
                    "model": "mistral-7b",
                    "base_url": "http://localhost:1234/v1",
                },
            )
        assert result["base_url"] == "http://localhost:1234/v1"


# ---------------------------------------------------------------------------
# remove_provider
# ---------------------------------------------------------------------------


class TestRemoveProvider:
    def test_remove_named_provider(self) -> None:
        cfg = _make_config()
        cfg.providers = {"my-ollama": ProviderSettings(kind="ollama", model="llama3.1:8b")}
        ctx_load, ctx_write, written = _patch_config(cfg)
        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
        ):
            result = remove_provider("my-ollama")
        assert result["ok"] is True
        assert written

    def test_remove_primary_raises(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="primary"):
            remove_provider("__primary__")

    def test_remove_nonexistent_raises(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="not found"):
            remove_provider("does-not-exist")


# ---------------------------------------------------------------------------
# get_routing
# ---------------------------------------------------------------------------


class TestGetRouting:
    def test_synthesizes_12_rows_when_routing_is_none(self) -> None:
        """When config.routing is None, all 12 capabilities must appear in the response."""
        cfg = _make_config()
        assert cfg.routing is None  # default
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = get_routing()
        cap_names = {row["name"] for row in result["capabilities"]}
        assert len(cap_names) == 12, f"Expected 12 caps, got: {cap_names}"
        assert cap_names == set(CAPABILITY_ORDER)

    def test_each_row_has_label(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = get_routing()
        for row in result["capabilities"]:
            assert "label" in row
            assert row["label"], f"Empty label for {row['name']!r}"

    def test_default_model_present(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = get_routing()
        assert "default_model" in result
        assert result["default_model"]  # non-empty


# ---------------------------------------------------------------------------
# set_routing
# ---------------------------------------------------------------------------


class TestSetRouting:
    def test_set_routing_persists(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, written = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = set_routing(
                "claude-haiku-4-5",
                {"reasoning": ["claude-opus-4-8"], "coding": ["claude-sonnet-4-6"]},
            )
        assert written, "write_global_config must be called"
        caps_by_name = {row["name"]: row for row in result["capabilities"]}
        assert "claude-opus-4-8" in caps_by_name["reasoning"]["models"]

    def test_unknown_capability_skipped(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, written = _patch_config(cfg)
        with ctx_load, ctx_write:
            # "flying" is not a valid capability — must be silently skipped, not raise
            result = set_routing("claude-haiku-4-5", {"flying": ["some-model"]})
        assert written
        cap_names = {row["name"] for row in result["capabilities"]}
        assert "flying" not in cap_names


# ---------------------------------------------------------------------------
# list_all_models
# ---------------------------------------------------------------------------


class TestListAllModels:
    def test_returns_provider_keyed_dict(self) -> None:
        cfg = _make_config()
        cfg.providers = {"groq": ProviderSettings(kind="groq", model="llama-3.1-8b-instant")}
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_all_models()
        assert "__primary__" in result
        assert "groq" in result

    def test_allowed_models_used_when_set(self) -> None:
        cfg = _make_config()
        cfg.providers = {
            "restricted": ProviderSettings(
                kind="anthropic",
                model="claude-haiku-4-5",
                allowed_models=["claude-haiku-4-5", "claude-sonnet-4-6"],
            )
        }
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_all_models()
        assert result["restricted"] == ["claude-haiku-4-5", "claude-sonnet-4-6"]

    def test_bundled_fallback_for_anthropic(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_all_models()
        primary_models = result["__primary__"]
        # The bundled defaults contain at least one Anthropic model
        assert any("claude" in m for m in primary_models)


# ---------------------------------------------------------------------------
# Security hardening tests (adversarial review fixes)
# ---------------------------------------------------------------------------


class TestProviderNameInjectionRejected:
    """Provider names with path/vault-key traversal chars must be rejected."""

    def test_path_traversal_rejected_add(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="alphanumeric"):
            add_or_update_provider("../evil", {"kind": "anthropic", "model": "x"})

    def test_slash_rejected_add(self) -> None:
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="alphanumeric"):
            add_or_update_provider("my/provider", {"kind": "anthropic", "model": "x"})

    def test_dotdot_rejected_remove(self) -> None:
        cfg = _make_config()
        cfg.providers = {}
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write, pytest.raises(ValueError, match="alphanumeric"):
            remove_provider("../../etc/passwd")

    def test_valid_names_accepted(self) -> None:
        """Hyphens, underscores, alphanumerics must all pass validation."""
        for valid_name in ("my-provider", "my_provider", "Provider1", "abc123"):
            cfg = _make_config()
            ctx_load, ctx_write, _ = _patch_config(cfg)
            with (
                ctx_load,
                ctx_write,
                patch("hachi.gateway.provider_admin.CredentialVault"),
                patch("hachi.gateway.provider_admin.create_default_secret_store"),
            ):
                result = add_or_update_provider(valid_name, {"kind": "anthropic", "model": "x"})
            assert result["name"] == valid_name


class TestHeadersMasked:
    """_mask_provider must mask header values, never echo them."""

    def test_header_values_masked(self) -> None:
        from hachi.gateway.provider_admin import _mask_provider

        ps = ProviderSettings(kind="openai-compatible", model="gpt-4o")
        ps.headers = {"Authorization": "Bearer sk-supersecret", "X-Custom": "my-value"}

        masked = _mask_provider("myp", ps)
        assert masked["headers"] == {"Authorization": "***", "X-Custom": "***"}

    def test_header_keys_preserved(self) -> None:
        from hachi.gateway.provider_admin import _mask_provider

        ps = ProviderSettings(kind="openai-compatible", model="gpt-4o")
        ps.headers = {"X-Key": "v"}
        masked = _mask_provider("p", ps)
        assert "X-Key" in masked["headers"]

    def test_no_raw_values_in_list_providers(self) -> None:
        cfg = _make_config()
        secret_ps = ProviderSettings(kind="openai-compatible", model="gpt-4o")
        secret_ps.headers = {"Authorization": "Bearer sk-1234"}
        cfg.providers = {"my-openai": secret_ps}
        ctx_load, ctx_write, _ = _patch_config(cfg)
        with ctx_load, ctx_write:
            result = list_providers()
        for p in result["providers"]:
            for v in p.get("headers", {}).values():
                assert v == "***", f"Header value was not masked: {v!r}"


class TestNetGuard:
    """is_safe_outbound_url must block private/metadata addresses."""

    def test_metadata_endpoint_blocked(self) -> None:
        from hachi.gateway._net_guard import is_safe_outbound_url

        # AWS/GCP/Azure metadata service
        assert is_safe_outbound_url("http://169.254.169.254/latest/meta-data") is False

    def test_localhost_blocked_by_default(self) -> None:
        from hachi.gateway._net_guard import is_safe_outbound_url

        assert is_safe_outbound_url("http://localhost:11434") is False

    def test_localhost_allowed_when_allow_loopback(self) -> None:
        from hachi.gateway._net_guard import is_safe_outbound_url

        assert is_safe_outbound_url("http://localhost:11434", allow_loopback=True) is True

    def test_file_scheme_blocked(self) -> None:
        from hachi.gateway._net_guard import is_safe_outbound_url

        assert is_safe_outbound_url("file:///etc/passwd") is False

    def test_public_url_allowed(self) -> None:
        from hachi.gateway._net_guard import is_safe_outbound_url

        # api.openai.com is a real public endpoint; test may need network
        # Skip gracefully if DNS is unavailable in the test environment
        try:
            result = is_safe_outbound_url("https://api.openai.com/v1/models")
        except Exception:
            pytest.skip("DNS not available in test environment")
        assert result is True

    def test_api_key_not_in_env_after_add(self) -> None:
        """Adding a provider must NOT leak the raw API key to os.environ."""
        cfg = _make_config()
        ctx_load, ctx_write, _ = _patch_config(cfg)
        raw_key = "sk-leak-test-999"
        vault_key = "provider.leak-test.api_key"

        with (
            ctx_load,
            ctx_write,
            patch("hachi.gateway.provider_admin.CredentialVault"),
            patch("hachi.gateway.provider_admin.create_default_secret_store"),
            patch.dict(os.environ, {}, clear=False),
        ):
            add_or_update_provider(
                "leak-test",
                {"kind": "anthropic", "model": "x", "api_key": raw_key},
            )

        # The raw key must NOT appear in os.environ under the vault key name
        assert os.environ.get(vault_key) != raw_key, "API key was leaked into os.environ"
