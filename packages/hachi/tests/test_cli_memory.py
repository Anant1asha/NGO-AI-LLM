"""Tests for the `hachi memory` CLI — search/stats over the MemoryVault.

The vault is faked (ChromaDB + an embedding model are heavy and not needed to
test the command's plumbing/formatting). The command imports MemoryVault inside
the function, so the fake is patched at its source module."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()


class _FakeCol:
    def __init__(self, n: int) -> None:
        self._n = n

    def count(self) -> int:
        return self._n


class _FakeVault:
    def __init__(self) -> None:
        self.collection = _FakeCol(3)
        self.user_collection = _FakeCol(2)
        self.agent_profile = _FakeCol(1)
        self.delegation_collection = _FakeCol(0)
        self.quarantine_collection = _FakeCol(0)

    def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
        return [
            {
                "id": "c1",
                "raw_content": "Project uses FastAPI",
                "category": "workspace_state",
                "timestamp": "2026-06-07",
            }
        ]

    def search_user_profile(self, query: str, top_k: int = 10) -> list[dict]:
        return [
            {
                "id": "u1",
                "raw_content": "Prefers dark mode",
                "category": "preference",
                "timestamp": "2026-06-07",
            }
        ]


def _patch(monkeypatch) -> None:
    monkeypatch.setattr("hachi.core.memory_vault.MemoryVault", _FakeVault)


def test_memory_search_core_json(monkeypatch) -> None:
    _patch(monkeypatch)
    result = runner.invoke(app, ["memory", "search", "framework", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scope"] == "core memory"
    assert payload["results"][0]["raw_content"] == "Project uses FastAPI"


def test_memory_search_profile_flag(monkeypatch) -> None:
    _patch(monkeypatch)
    result = runner.invoke(app, ["memory", "search", "mode", "--profile", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["scope"] == "user profile"
    assert "dark mode" in payload["results"][0]["raw_content"]


def test_memory_search_human_readable(monkeypatch) -> None:
    _patch(monkeypatch)
    result = runner.invoke(app, ["memory", "search", "framework"])
    assert result.exit_code == 0, result.output
    assert "Project uses FastAPI" in result.output
    assert "match(es)" in result.output


def test_memory_search_no_results(monkeypatch) -> None:
    class _EmptyVault(_FakeVault):
        def semantic_search(self, query: str, top_k: int = 5) -> list[dict]:
            return []

    monkeypatch.setattr("hachi.core.memory_vault.MemoryVault", _EmptyVault)
    result = runner.invoke(app, ["memory", "search", "nothing"])
    assert result.exit_code == 0
    assert "No core memory facts matched" in result.output


def test_memory_stats(monkeypatch) -> None:
    _patch(monkeypatch)
    result = runner.invoke(app, ["memory", "stats", "--json"])
    assert result.exit_code == 0, result.output
    stats = json.loads(result.stdout)
    assert stats["core_memory"] == 3
    assert stats["user_profile"] == 2
    assert stats["delegation_log"] == 0
