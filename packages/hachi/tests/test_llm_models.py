"""Tests for live model discovery + the allowlist guardrail.

Covers the pure resolver/guard helpers and the per-client ``list_models`` (which
must never raise — it returns [] when discovery is unavailable).
"""

from __future__ import annotations

from typing import Any

from hachi.core.llm import (
    OpenAICompatibleClient,
    can_switch_model,
    resolve_available_models,
)


# --- pure helpers --------------------------------------------------------
def test_resolve_prefers_allowlist_as_hard_cap() -> None:
    models = resolve_available_models(
        discovered=["a", "b", "c"],
        allowed=["b", "x"],
        current="b",
    )
    # Allowlist wins over discovery; discovery-only "a"/"c" are excluded.
    assert models == ["b", "x"]


def test_resolve_uses_discovery_when_no_allowlist() -> None:
    models = resolve_available_models(discovered=["a", "b"], allowed=[], current="a")
    assert models == ["a", "b"]


def test_resolve_always_includes_current_first_when_missing() -> None:
    models = resolve_available_models(discovered=["b", "c"], allowed=[], current="a")
    assert models[0] == "a"
    assert set(models) == {"a", "b", "c"}


def test_resolve_dedupes_preserving_order() -> None:
    models = resolve_available_models(discovered=["a", "a", "b", "b"], allowed=[], current="")
    assert models == ["a", "b"]


def test_can_switch_unrestricted_when_allowlist_empty() -> None:
    assert can_switch_model("anything", []) is True


def test_can_switch_enforced_by_allowlist() -> None:
    assert can_switch_model("claude-haiku-4-5", ["claude-haiku-4-5"]) is True
    assert can_switch_model("gpt-4.1", ["claude-haiku-4-5"]) is False


# --- client list_models --------------------------------------------------
class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_openai_compatible_list_models_parses_and_sorts(monkeypatch) -> None:
    client = OpenAICompatibleClient(base_url="http://x/v1", model="m")
    try:
        monkeypatch.setattr(
            client._http,
            "get",
            lambda *a, **k: _FakeResponse({"data": [{"id": "zeta"}, {"id": "alpha"}, {}]}),
        )
        assert client.list_models() == ["alpha", "zeta"]
    finally:
        client.close()


def test_openai_compatible_list_models_swallows_errors(monkeypatch) -> None:
    client = OpenAICompatibleClient(base_url="http://x/v1", model="m")
    try:

        def _boom(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError("network down")

        monkeypatch.setattr(client._http, "get", _boom)
        assert client.list_models() == []  # never raises
    finally:
        client.close()
