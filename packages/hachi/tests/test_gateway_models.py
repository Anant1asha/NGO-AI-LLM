"""Regression tests for gateway list_models — H6 fix.

Asserts that the gateway ``GET /models`` endpoint:
  1. Returns the currently configured model (always present, even on fallback).
  2. Includes ``claude-opus-4-8`` in the live-discovery path.
  3. Returns the static-fallback list (including ``claude-opus-4-8``) when discovery
     is unavailable (offline / no API key).
  4. Falls back gracefully when ``create_llm_client`` raises unexpectedly.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from hachi.gateway.control_plane import GatewayControlPlane
from hachi.gateway.fastapi_app import create_gateway_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(
    *,
    model: str = "claude-sonnet-4-6",
    kind: str = "anthropic",
    allowed: list[str] | None = None,
) -> SimpleNamespace:
    """Build a minimal config namespace matching what load_effective_config returns."""
    return SimpleNamespace(
        provider=SimpleNamespace(
            kind=kind,
            model=model,
            allowed_models=allowed or [],
            api_key_ref=None,
            api_key_env="ANTHROPIC_API_KEY",
            base_url=None,
        ),
        providers={},
    )


def _make_fake_client(models: list[str]) -> Any:
    """Fake LLM client whose list_models returns the given list."""
    client = MagicMock()
    client.list_models.return_value = models
    client.close = MagicMock()
    return client


def _build_gateway(list_models_fn: Any) -> TestClient:
    """Create a TestClient backed by a GatewayControlPlane with a custom list_models."""
    cp = GatewayControlPlane(list_models=list_models_fn)
    return TestClient(create_gateway_app(cp))


# ---------------------------------------------------------------------------
# Tests — live discovery path
# ---------------------------------------------------------------------------


class TestGatewayModelsLiveDiscovery:
    """Gateway /models returns live results when the provider is reachable."""

    def test_includes_configured_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The configured default model must always appear in the list."""
        cfg = _cfg(model="claude-sonnet-4-6")
        fake_client = _make_fake_client(
            ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]
        )
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: fake_client)

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()
        ids = [m["id"] for m in result]

        assert "claude-sonnet-4-6" in ids, f"Configured model missing from {ids}"

    def test_includes_claude_opus_4_8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """claude-opus-4-8 must be present when returned by live discovery."""
        cfg = _cfg(model="claude-sonnet-4-6")
        fake_client = _make_fake_client(
            ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]
        )
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: fake_client)

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()
        ids = [m["id"] for m in result]

        assert "claude-opus-4-8" in ids, (
            f"claude-opus-4-8 missing from live-discovery result: {ids}"
        )

    def test_recommended_flag_marks_configured_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The currently configured model must be marked recommended=True."""
        cfg = _cfg(model="claude-opus-4-8")
        fake_client = _make_fake_client(
            ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]
        )
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: fake_client)

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()

        recommended = [m for m in result if m.get("recommended")]
        assert len(recommended) == 1, f"Expected exactly one recommended model: {result}"
        assert recommended[0]["id"] == "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Tests — static fallback path
# ---------------------------------------------------------------------------


class TestGatewayModelsStaticFallback:
    """Gateway /models falls back to static list when discovery is unavailable."""

    def test_fallback_includes_opus_4_8(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Static fallback must include claude-opus-4-8 (no stale *-4-5-only list)."""
        cfg = _cfg(model="claude-sonnet-4-6")
        # create_llm_client raises to simulate offline/no-key scenario.
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr(
            "hachi.core.llm.create_llm_client",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("no API key")),
        )

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()
        ids = [m["id"] for m in result]

        assert "claude-opus-4-8" in ids, (
            f"claude-opus-4-8 missing from static fallback: {ids}"
        )

    def test_fallback_includes_configured_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Configured model must appear in fallback even when discovery fails."""
        cfg = _cfg(model="claude-opus-4-8")
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr(
            "hachi.core.llm.create_llm_client",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")),
        )

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()
        ids = [m["id"] for m in result]

        assert "claude-opus-4-8" in ids, (
            f"Configured model claude-opus-4-8 missing from fallback: {ids}"
        )

    def test_empty_discovery_triggers_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When list_models() returns [] (offline but client creates ok), use static."""
        cfg = _cfg(model="claude-sonnet-4-6")
        fake_client = _make_fake_client([])  # empty discovery
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr("hachi.core.llm.create_llm_client", lambda *a, **k: fake_client)

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()
        result = support.list_models()
        ids = [m["id"] for m in result]

        assert "claude-opus-4-8" in ids, (
            f"claude-opus-4-8 missing from empty-discovery fallback: {ids}"
        )
        assert "claude-sonnet-4-6" in ids, (
            f"Configured model missing from empty-discovery fallback: {ids}"
        )


# ---------------------------------------------------------------------------
# Tests — gateway HTTP route integration
# ---------------------------------------------------------------------------


class TestGatewayModelsHTTPRoute:
    """The gateway HTTP GET /models route wires through to list_models correctly."""

    def test_http_route_returns_200_with_model_list(self) -> None:
        """GET /models must return HTTP 200 with a non-empty list including opus-4-8."""
        models_payload = [
            {"id": "claude-haiku-4-5", "label": "claude-haiku-4-5",
             "provider": "anthropic", "recommended": False},
            {"id": "claude-sonnet-4-6", "label": "claude-sonnet-4-6",
             "provider": "anthropic", "recommended": False},
            {"id": "claude-opus-4-8", "label": "claude-opus-4-8",
             "provider": "anthropic", "recommended": True},
        ]

        with _build_gateway(list_models_fn=lambda: models_payload) as client:
            resp = client.get("/models")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        ids = [m["id"] for m in data]
        assert "claude-opus-4-8" in ids, f"claude-opus-4-8 missing from HTTP /models: {ids}"

    def test_http_route_no_hardcoded_stale_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The route must not silently return a stale list that omits claude-opus-4-8.

        This is the primary regression guard for H6: the old list was
        ['claude-haiku-4-5', 'claude-sonnet-4-5'] and missed opus-4-8 entirely.
        """
        # Force Anthropic config with no usable API key so the static fallback is
        # exercised — same isolation pattern as TestGatewayModelsStaticFallback.
        cfg = _cfg(model="claude-sonnet-4-6")
        monkeypatch.setattr("hachi.cli.main.load_effective_config", lambda: cfg)
        monkeypatch.setattr("hachi.cli.main.create_default_secret_store", lambda: object())
        monkeypatch.setattr(
            "hachi.core.llm.create_llm_client",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("no ANTHROPIC_API_KEY")),
        )

        from hachi.cli.main import _InProcessGatewayRuntime

        support = _InProcessGatewayRuntime()

        with _build_gateway(list_models_fn=support.list_models) as http_client:
            resp = http_client.get("/models")

        # Static Anthropic fallback must include opus-4-8.
        assert resp.status_code == 200
        data = resp.json()
        ids = [m["id"] for m in data]
        assert "claude-opus-4-8" in ids, (
            f"H6 regression: claude-opus-4-8 missing from gateway /models: {ids}"
        )
