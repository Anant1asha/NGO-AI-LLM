"""Tests for the conversational quickstart: provider validation + one-call setup.

The headline non-technical fix is that a missing/invalid provider API key is
caught at setup time rather than on the first chat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hachi.core.config_loader import load_effective_config
from hachi.core.onboarding import (
    OnboardingService,
    default_api_key_env_for,
    default_model_for,
)
from hachi.core.paths import HachiPaths

REPO_ROOT = Path(__file__).resolve().parent.parent


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def _service(tmp_path: Path) -> OnboardingService:
    return OnboardingService(paths=_paths(tmp_path))


# ---- provider defaults ----


def test_provider_defaults() -> None:
    assert default_model_for("anthropic") == "claude-haiku-4-5"
    assert default_api_key_env_for("anthropic") == "ANTHROPIC_API_KEY"
    assert default_api_key_env_for("ollama") == ""


def test_openrouter_provider_supported(tmp_path: Path, monkeypatch) -> None:
    assert default_model_for("openrouter") == "openai/gpt-4o-mini"
    assert default_api_key_env_for("openrouter") == "OPENROUTER_API_KEY"

    service = _service(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    ok, _msg = service.validate_provider(kind="openrouter")
    assert not ok  # needs a key
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    ok, _msg = service.validate_provider(kind="openrouter")
    assert ok


def test_create_llm_client_routes_openrouter() -> None:
    from hachi.core.llm import OpenAICompatibleClient, create_llm_client

    client = create_llm_client({"kind": "openrouter", "model": "openai/gpt-4o-mini"})
    try:
        assert isinstance(client, OpenAICompatibleClient)
        assert "openrouter.ai" in client.base_url
    finally:
        client.close()


# ---- validate_provider ----


def test_validate_provider_anthropic_with_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    ok, msg = _service(tmp_path).validate_provider(kind="anthropic")
    assert ok
    assert "ANTHROPIC_API_KEY" in msg


def test_validate_provider_anthropic_missing_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Stub the secret store so real keyring entries don't interfere with this test.
    from types import SimpleNamespace

    monkeypatch.setattr(
        "hachi.core.secret_store.create_default_secret_store",
        lambda *_a, **_kw: SimpleNamespace(get=lambda _n: None),
    )
    ok, msg = _service(tmp_path).validate_provider(kind="anthropic")
    assert not ok
    assert "ANTHROPIC_API_KEY" in msg  # actionable guidance names the env var


def test_validate_provider_ollama_needs_no_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ok, _msg = _service(tmp_path).validate_provider(kind="ollama")
    assert ok


def test_validate_provider_unknown_kind(tmp_path: Path) -> None:
    ok, msg = _service(tmp_path).validate_provider(kind="banana")
    assert not ok
    assert "anthropic" in msg  # lists valid options


def test_validate_provider_explicit_key_overrides_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    ok, _msg = _service(tmp_path).validate_provider(
        kind="openai-compatible", api_key="explicit-key"
    )
    assert ok


# ---- quick_setup ----


def test_quick_setup_persists_and_clears_needs_setup(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = OnboardingService(paths=paths)
    assert service.needs_setup() is True

    plan = service.quick_setup(kind="ollama", permission_tier="guided")
    assert plan.answers["provider"]["kind"] == "ollama"
    assert plan.answers["provider"]["model"] == "llama3.1"  # sensible default applied

    # Config was written and setup is now considered complete.
    config = load_effective_config(paths=paths)
    assert config.provider.kind == "ollama"
    assert config.permissions.tier == "guided"
    assert service.needs_setup() is False


def test_quick_setup_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _service(tmp_path).quick_setup(kind="banana")


def test_quick_setup_persists_openrouter(tmp_path: Path) -> None:
    # Exercises the full path: validates against settings.ProviderKind Literal and
    # writes config — would raise if "openrouter" weren't a permitted kind.
    paths = _paths(tmp_path)
    service = OnboardingService(paths=paths)
    plan = service.quick_setup(kind="openrouter", permission_tier="guided")
    assert plan.answers["provider"]["kind"] == "openrouter"
    assert load_effective_config(paths=paths).provider.kind == "openrouter"


# ---- install scripts ----


def test_install_scripts_present_and_wired() -> None:
    sh = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    ps = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")
    for script in (sh, ps):
        assert "uv sync" in script
        assert "quickstart" in script  # launches guided setup after install
        assert "astral.sh/uv/install" in script  # bootstraps uv
