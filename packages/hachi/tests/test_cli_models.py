"""Tests for the `hachi models` CLI command — lists provider-exposed models
(live), narrowed by the allowed_models guardrail, marking the active model."""

from __future__ import annotations

import json
from types import SimpleNamespace

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


class _FakeClient:
    def __init__(self, models: list[str]) -> None:
        self._models = models
        self.closed = False

    def list_models(self) -> list[str]:
        return self._models

    def close(self) -> None:
        self.closed = True


def _cfg(*, model: str = "claude-haiku-4-5", allowed: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        provider=SimpleNamespace(
            kind="anthropic",
            model=model,
            allowed_models=allowed or [],
            api_key_ref=None,
            api_key_env="ANTHROPIC_API_KEY",
            base_url=None,
        ),
        providers={},
    )


def _patch(monkeypatch, cfg: SimpleNamespace, discovered: list[str]) -> _FakeClient:
    client = _FakeClient(discovered)
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
    # create_llm_client is imported inside the command → patch it at its source.
    monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: client)
    return client


def test_models_lists_discovered(monkeypatch) -> None:
    client = _patch(monkeypatch, _cfg(), ["claude-haiku-4-5", "claude-sonnet-4-5"])
    result = runner.invoke(app, ["models", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "provider"
    assert payload["current"] == "claude-haiku-4-5"
    assert "claude-sonnet-4-5" in payload["models"]
    assert payload["restricted"] is False
    assert client.closed is True  # client is always closed


def test_models_allowlist_caps_and_marks_restricted(monkeypatch) -> None:
    _patch(monkeypatch, _cfg(allowed=["claude-haiku-4-5"]), ["a", "b", "claude-haiku-4-5"])
    result = runner.invoke(app, ["models", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "allowlist"
    assert payload["restricted"] is True
    assert payload["models"] == ["claude-haiku-4-5"]  # discovery-only entries excluded


def test_models_discovery_unavailable_shows_current(monkeypatch) -> None:
    _patch(monkeypatch, _cfg(), [])  # list_models returns [] (offline / no key)
    result = runner.invoke(app, ["models", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "configured"
    assert payload["models"] == ["claude-haiku-4-5"]


def test_models_human_readable_marks_current(monkeypatch) -> None:
    _patch(monkeypatch, _cfg(), ["claude-haiku-4-5", "claude-sonnet-4-5"])
    result = runner.invoke(app, ["models"])
    assert result.exit_code == 0, result.output
    assert "claude-sonnet-4-5" in result.output
    assert "(current)" in result.output


# ---------------------------------------------------------------------------
# P-06 — a missing API key is the expected first-run state, not a crash.
#
# `models` built the LLM client OUTSIDE its try/except, so
# AnthropicClient.__init__ raising ValueError escaped as a Rich traceback and
# the command exited 1. The "live discovery unavailable (offline or no API key)"
# branch further down was unreachable. Precedent for the correct shape:
# the TUI/memory list path (~line 870) wraps construction in try/except.
# ---------------------------------------------------------------------------


def _patch_client_build_failure(
    monkeypatch,
    message: str = "ANTHROPIC_API_KEY must be provided or set in the environment.",
) -> None:
    """Make client construction fail the way it does with no credential present."""
    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _cfg())
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())

    def _raise(*_args, **_kwargs):
        raise ValueError(message)

    # create_llm_client is imported inside the command, so patch it at its source.
    monkeypatch.setattr("hachi.core.llm.create_llm_client", _raise)


def test_models_without_api_key_exits_zero(monkeypatch) -> None:
    """The command must degrade to the configured model, not crash."""
    _patch_client_build_failure(monkeypatch)

    result = runner.invoke(app, ["models", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["source"] == "configured"
    assert payload["models"] == ["claude-haiku-4-5"]
    assert "ANTHROPIC_API_KEY" in (payload["discovery_error"] or "")


def test_models_missing_key_shows_the_reason_not_a_traceback(monkeypatch) -> None:
    """Human-readable output must be a one-line reason, not a stack trace.

    `assert "Traceback" not in result.output` was vacuous: CliRunner catches the
    exception, so pre-fix output was "" and the assertion passed trivially. The
    load-bearing check is `result.exception is None`.
    """
    _patch_client_build_failure(monkeypatch)

    result = runner.invoke(app, ["models"])

    assert result.exit_code == 0, result.output
    assert result.exception is None, f"an exception escaped: {result.exception!r}"
    assert "live discovery unavailable" in result.output
    assert "ANTHROPIC_API_KEY" in result.output


def test_models_misconfiguration_is_not_reported_as_a_missing_key(monkeypatch) -> None:
    """A typo'd provider config must not masquerade as "no API key yet".

    Both states end at source == "configured", so the reason has to survive to
    the caller — otherwise a user with a broken `kind` or `base_url` is told to
    do the one thing that will not fix it.
    """
    _patch_client_build_failure(monkeypatch, message="Unknown provider kind: bogus")

    result = runner.invoke(app, ["models", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["discovery_error"] == "Unknown provider kind: bogus"


def test_models_closes_the_client_when_discovery_fails(monkeypatch) -> None:
    """A failing close() must not escape, and a working one must still run.

    The close sits inside the same try as construction; if it were left in a
    sibling `finally`, a dead HTTP session would re-raise the very traceback
    this change removes.
    """
    client = _FakeClient([])
    client.list_models = lambda: (_ for _ in ()).throw(RuntimeError("network down"))

    monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: _cfg())
    monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
    monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: client)

    result = runner.invoke(app, ["models", "--json"])

    assert result.exit_code == 0, result.output
    assert result.exception is None
    assert client.closed is True, "client was not closed when discovery raised"
