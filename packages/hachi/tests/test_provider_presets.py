"""Tests for the added OpenAI-compatible provider presets (Groq, Together, DeepSeek)."""

from __future__ import annotations

import pytest

from hachi.core import onboarding
from hachi.core.llm import OpenAICompatibleClient, create_llm_client


@pytest.mark.parametrize(
    "kind,base",
    [
        ("groq", "https://api.groq.com/openai/v1"),
        ("together", "https://api.together.xyz/v1"),
        ("deepseek", "https://api.deepseek.com/v1"),
        ("openrouter", "https://openrouter.ai/api/v1"),  # regression: still works
    ],
)
def test_preset_creates_openai_compatible_client(kind: str, base: str) -> None:
    client = create_llm_client({"kind": kind, "model": "m"})
    try:
        assert isinstance(client, OpenAICompatibleClient)
        assert client.base_url == base
    finally:
        client.close()


def test_config_base_url_overrides_preset() -> None:
    client = create_llm_client({"kind": "groq", "model": "m", "base_url": "http://localhost:9/v1"})
    try:
        assert client.base_url == "http://localhost:9/v1"
    finally:
        client.close()


@pytest.mark.parametrize(
    "kind,env",
    [
        ("groq", "GROQ_API_KEY"),
        ("together", "TOGETHER_API_KEY"),
        ("deepseek", "DEEPSEEK_API_KEY"),
    ],
)
def test_onboarding_defaults_for_new_kinds(kind: str, env: str) -> None:
    assert kind in onboarding._PROVIDER_KINDS
    assert onboarding.default_api_key_env_for(kind) == env
    assert onboarding.default_model_for(kind)  # non-empty default model


def test_validate_provider_accepts_new_kind(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "x")
    ok, _msg = onboarding.OnboardingService().validate_provider(kind="groq")
    assert ok is True


def test_validate_provider_unknown_kind_still_rejected() -> None:
    ok, msg = onboarding.OnboardingService().validate_provider(kind="totally-made-up")
    assert ok is False
    assert "Unknown provider" in msg
