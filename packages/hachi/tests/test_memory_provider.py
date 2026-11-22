"""Tests for the pluggable memory provider system.

Covers:
- InMemoryProvider: upsert / search / delete / shutdown
- resolve_provider factory: chroma → ChromaMemoryProvider, in_memory → InMemoryProvider
- memory_tools null-vault guards: all tool callables return the graceful degradation message
"""

from __future__ import annotations

from hachi.core.memory_provider import (
    ChromaMemoryProvider,
    InMemoryProvider,
    MemoryProvider,
    resolve_provider,
)
from hachi.core.settings import MemorySettings

# ---------------------------------------------------------------------------
# InMemoryProvider — upsert / search / delete / shutdown
# ---------------------------------------------------------------------------


def _provider() -> InMemoryProvider:
    p = InMemoryProvider()
    p.initialize(brain_dir="/tmp/unused")
    return p


def test_inmemory_upsert_returns_id() -> None:
    p = _provider()
    fid = p.upsert("the project uses FastAPI")
    assert isinstance(fid, str)
    assert len(fid) > 0


def test_inmemory_search_finds_exact_match() -> None:
    p = _provider()
    p.upsert("the project uses FastAPI", category="architecture")
    results = p.search("FastAPI project")
    assert len(results) >= 1
    assert any("FastAPI" in r["content"] for r in results)


def test_inmemory_search_returns_empty_for_no_match() -> None:
    p = _provider()
    p.upsert("unrelated fact about bananas")
    results = p.search("XYZ_TOTALLY_UNRELATED_KEYWORD_12345")
    assert results == []


def test_inmemory_delete_removes_fact() -> None:
    p = _provider()
    fid = p.upsert("fact to delete")
    assert p.delete(fid) is True
    results = p.search("fact to delete")
    assert not any(r["id"] == fid for r in results)


def test_inmemory_delete_unknown_id_returns_false() -> None:
    p = _provider()
    assert p.delete("nonexistent-id-zzz") is False


def test_inmemory_search_respects_top_k() -> None:
    p = _provider()
    for i in range(10):
        p.upsert(f"shared keyword fact number {i}")
    results = p.search("keyword fact", top_k=3)
    assert len(results) <= 3


def test_inmemory_shutdown_clears_all_facts() -> None:
    p = _provider()
    p.upsert("fact one")
    p.upsert("fact two")
    p.shutdown()
    # After shutdown, no facts remain.
    assert p.search("fact") == []


def test_inmemory_implements_provider_interface() -> None:
    """InMemoryProvider satisfies the MemoryProvider ABC contract."""
    p = InMemoryProvider()
    assert isinstance(p, MemoryProvider)


def test_inmemory_result_has_expected_keys() -> None:
    p = _provider()
    p.upsert("hello world", category="test_cat")
    results = p.search("hello")
    assert results, "Expected at least one result"
    for key in ("id", "content", "raw_content", "category"):
        assert key in results[0], f"Missing key '{key}' in result"
    assert results[0]["category"] == "test_cat"


# ---------------------------------------------------------------------------
# resolve_provider factory
# ---------------------------------------------------------------------------


def test_resolve_provider_chroma_returns_chroma_provider() -> None:
    settings = MemorySettings(backend="chroma")
    provider = resolve_provider(settings)
    assert isinstance(provider, ChromaMemoryProvider)


def test_resolve_provider_in_memory_returns_inmemory_provider() -> None:
    settings = MemorySettings(backend="in_memory")
    provider = resolve_provider(settings)
    assert isinstance(provider, InMemoryProvider)


def test_resolve_provider_default_is_chroma() -> None:
    settings = MemorySettings()
    assert settings.backend == "chroma"
    provider = resolve_provider(settings)
    assert isinstance(provider, ChromaMemoryProvider)


# ---------------------------------------------------------------------------
# memory_tools null-vault guards
# ---------------------------------------------------------------------------


def test_memory_tools_save_degrades_gracefully_when_vault_is_none() -> None:
    """save_memory returns informational message, not AttributeError, when vault=None."""
    from unittest.mock import MagicMock

    from hachi.tools.memory_tools import register_memory_tools

    registry = MagicMock()
    registered: dict[str, object] = {}

    def _capture(schema: dict, fn: object, **_kwargs: object) -> None:
        registered[schema["name"]] = fn

    registry.register.side_effect = _capture
    register_memory_tools(registry, vault=None)

    save_fn = registered["core_save_memory"]
    result = save_fn(facts=[{"content": "test fact"}])  # type: ignore[operator]
    assert "not available" in result.lower()


def test_memory_tools_search_degrades_gracefully_when_vault_is_none() -> None:
    from unittest.mock import MagicMock

    from hachi.tools.memory_tools import register_memory_tools

    registry = MagicMock()
    registered: dict[str, object] = {}

    def _capture(schema: dict, fn: object, **_kwargs: object) -> None:
        registered[schema["name"]] = fn

    registry.register.side_effect = _capture
    register_memory_tools(registry, vault=None)

    search_fn = registered["core_search_memory"]
    result = search_fn(query="anything", top_k=5)  # type: ignore[operator]
    assert "not available" in result.lower()


def test_memory_tools_delete_degrades_gracefully_when_vault_is_none() -> None:
    from unittest.mock import MagicMock

    from hachi.tools.memory_tools import register_memory_tools

    registry = MagicMock()
    registered: dict[str, object] = {}

    def _capture(schema: dict, fn: object, **_kwargs: object) -> None:
        registered[schema["name"]] = fn

    registry.register.side_effect = _capture
    register_memory_tools(registry, vault=None)

    delete_fn = registered["core_delete_memory"]
    result = delete_fn(fact_id="abc123")  # type: ignore[operator]
    assert "not available" in result.lower()
