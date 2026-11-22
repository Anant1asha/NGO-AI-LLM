from __future__ import annotations

from pathlib import Path

import pytest

from hachi.core.config_loader import load_effective_config, write_global_config
from hachi.core.onboarding import OnboardingService
from hachi.core.paths import HachiPaths


def _paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def _base_plan() -> dict:
    return {
        "tier": "lightning",
        "steps": ["welcome", "provider", "safety", "finish"],
        "answers": {},
        "enable_memory": False,
        "show_integrations": False,
        "show_advanced": False,
    }


def test_apply_setup_rejects_invalid_provider_kind(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["answers"] = {"provider": {"kind": "not-a-provider", "model": "x"}}

    with pytest.raises(ValueError, match="provider.kind must be one of"):
        service.apply_setup(payload)


def test_apply_setup_normalizes_stale_model_when_provider_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HACHI_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    paths = _paths(tmp_path)
    baseline = load_effective_config(paths=paths)
    baseline.provider.kind = "openai-compatible"
    baseline.provider.model = "gpt-4.1-mini"
    write_global_config(baseline, paths=paths)

    service = OnboardingService(paths=paths)
    payload = _base_plan()
    payload["answers"] = {"provider": {"kind": "anthropic", "model": "gpt-4.1-mini"}}

    service.apply_setup(payload)

    updated = load_effective_config(paths=paths)
    assert updated.provider.kind == "anthropic"
    assert updated.provider.model == "claude-haiku-4-5"


def test_apply_setup_rejects_invalid_permission_tier(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["answers"] = {"permission_tier": "root"}

    with pytest.raises(ValueError, match="permission_tier must be one of"):
        service.apply_setup(payload)


def test_apply_setup_rejects_non_boolean_memory_flags(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["answers"] = {"memory": {"enable_session_history": "false"}}

    with pytest.raises(ValueError, match="memory.enable_session_history must be a boolean"):
        service.apply_setup(payload)


def test_apply_setup_rejects_invalid_tier_value(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["tier"] = "turbo"

    with pytest.raises(ValueError):
        service.apply_setup(payload)


def test_apply_setup_rejects_invalid_step_name(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["steps"] = ["welcome", "provider", "safety", "warp", "finish"]

    with pytest.raises(ValueError):
        service.apply_setup(payload)


def test_apply_setup_rejects_non_boolean_integration_flags(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["answers"] = {"integrations": {"slack": "enabled"}}

    with pytest.raises(ValueError, match="integrations.slack must be a boolean"):
        service.apply_setup(payload)


def test_apply_setup_rejects_non_boolean_integration_enabled_field(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload["answers"] = {"integrations": {"slack": {"enabled": "yes"}}}

    with pytest.raises(ValueError, match="integrations.slack.enabled must be a boolean"):
        service.apply_setup(payload)


def test_apply_setup_rejects_missing_required_tier(tmp_path: Path) -> None:
    service = OnboardingService(paths=_paths(tmp_path))
    payload = _base_plan()
    payload.pop("tier")

    with pytest.raises(ValueError):
        service.apply_setup(payload)
