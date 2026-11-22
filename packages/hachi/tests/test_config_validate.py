"""Tests for config validation: the pure rule checks + the CLI command."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.core.config_validate import validate_config

runner = CliRunner()


def _cfg(
    *,
    kind: str = "anthropic",
    model: str = "claude-haiku-4-5",
    allowed: list[str] | None = None,
    tier: str = "guided",
    max_tokens: int = 8192,
) -> SimpleNamespace:
    return SimpleNamespace(
        provider=SimpleNamespace(
            kind=kind, model=model, allowed_models=allowed or [], api_key_env="ANTHROPIC_API_KEY"
        ),
        permissions=SimpleNamespace(tier=tier),
        agent=SimpleNamespace(max_tokens=max_tokens),
    )


# --- pure validator ------------------------------------------------------
def test_validate_config_all_good() -> None:
    report = validate_config(_cfg(), provider_key_ok=True, provider_key_detail="ok")
    assert report["ok"] is True
    names = {c["name"] for c in report["checks"]}
    assert {"provider_kind", "permission_tier", "max_tokens", "provider_api_key"} <= names


def test_validate_config_unknown_kind_and_tier_fail() -> None:
    report = validate_config(_cfg(kind="bogus", tier="god-mode"))
    by_name = {c["name"]: c["ok"] for c in report["checks"]}
    assert by_name["provider_kind"] is False
    assert by_name["permission_tier"] is False
    assert report["ok"] is False


def test_validate_config_model_allowlist_consistency() -> None:
    # configured model NOT in the allowlist → would be blocked → fail
    bad = validate_config(_cfg(model="gpt-4.1", allowed=["claude-haiku-4-5"]))
    by_name = {c["name"]: c["ok"] for c in bad["checks"]}
    assert by_name["model_allowlist"] is False
    assert bad["ok"] is False

    # configured model in the allowlist → pass
    good = validate_config(_cfg(model="claude-haiku-4-5", allowed=["claude-haiku-4-5"]))
    by_name = {c["name"]: c["ok"] for c in good["checks"]}
    assert by_name["model_allowlist"] is True


def test_validate_config_no_allowlist_skips_that_check() -> None:
    report = validate_config(_cfg(allowed=[]))
    names = {c["name"] for c in report["checks"]}
    assert "model_allowlist" not in names


def test_validate_config_bad_max_tokens() -> None:
    report = validate_config(_cfg(max_tokens=0))
    by_name = {c["name"]: c["ok"] for c in report["checks"]}
    assert by_name["max_tokens"] is False


def test_validate_config_key_failure_marks_overall_bad() -> None:
    report = validate_config(_cfg(), provider_key_ok=False, provider_key_detail="No API key")
    by_name = {c["name"]: c["ok"] for c in report["checks"]}
    assert by_name["provider_api_key"] is False
    assert report["ok"] is False


# --- CLI command ---------------------------------------------------------
def test_cli_config_validate_ok(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _cfg())
    monkeypatch.setattr(
        "hachi.core.onboarding.OnboardingService.validate_provider",
        lambda self, **kw: (True, "key resolved"),
    )
    result = runner.invoke(app, ["config-validate", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is True


def test_cli_config_validate_nonzero_on_problem(monkeypatch) -> None:
    monkeypatch.setattr(
        "hachi.cli.main.load_effective_config",
        lambda: _cfg(model="gpt-4.1", allowed=["claude-haiku-4-5"]),
    )
    monkeypatch.setattr(
        "hachi.core.onboarding.OnboardingService.validate_provider",
        lambda self, **kw: (True, "key resolved"),
    )
    result = runner.invoke(app, ["config-validate", "--json"])
    assert result.exit_code == 1  # CI gate: bad config → non-zero
    payload = json.loads(result.stdout)
    assert payload["ok"] is False


def test_cli_config_validate_human_readable(monkeypatch) -> None:
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _cfg())
    monkeypatch.setattr(
        "hachi.core.onboarding.OnboardingService.validate_provider",
        lambda self, **kw: (True, "key resolved"),
    )
    result = runner.invoke(app, ["config-validate"])
    assert result.exit_code == 0, result.output
    assert "Config validation" in result.output
    assert "provider_kind" in result.output
