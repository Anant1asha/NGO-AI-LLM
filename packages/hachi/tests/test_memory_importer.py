"""Tests for core.memory_importer — parsers, auto-detect, and ingestion.

All tests are offline: no ChromaDB, no SQLite, no network.
MemoryVault and SessionStore are replaced with lightweight fakes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hachi.core.memory_importer import (
    Conversation,
    Turn,
    _parse_chatgpt,
    _parse_gemini,
    _parse_hermes,
    _sniff_format,
    ingest,
    parse_file,
)

# ---------------------------------------------------------------------------
# Fake stores (no disk I/O)
# ---------------------------------------------------------------------------


class FakeSessionStore:
    def __init__(self) -> None:
        self.sessions: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self._current_id = 0

    def start_session(self, model: str = "test") -> str:
        sid = f"sess{self._current_id}"
        self._current_id += 1
        self.sessions.append({"id": sid, "model": model})
        return sid

    def set_session_title(self, session_id: str, title: str) -> None:
        for s in self.sessions:
            if s["id"] == session_id:
                s["title"] = title

    def log_message(self, session_id: str, role: str, content: str) -> None:
        self.messages.append({"session_id": session_id, "role": role, "content": content})

    def end_session(self, session_id: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


class FakeMemoryVault:
    def __init__(self) -> None:
        self.facts: list[dict[str, str]] = []

    def upsert_fact(self, content: str, category: str = "workspace_state") -> str:
        self.facts.append({"content": content, "category": category})
        return "fake-id"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


CHATGPT_EXPORT = [
    {
        "title": "Fix the login bug",
        "mapping": {
            "a1": {
                "message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text", "parts": ["Why is login broken?"]},
                }
            },
            "a2": {
                "message": {
                    "author": {"role": "assistant"},
                    "content": {
                        "content_type": "text",
                        "parts": ["The session token expires too early."],
                    },
                }
            },
        },
    }
]

GEMINI_CONVERSATIONS_EXPORT = [
    {
        "title": "Plan my day",
        "conversations": [
            {"role": "user", "text": "What should I do today?"},
            {"role": "model", "text": "Start with the standup, then tackle the backlog."},
        ],
    }
]

GEMINI_ACTIVITY_EXPORT = [
    {
        "title": "Searched for Python tips",
        "subtitles": [{"text": "Python performance tips"}],
    }
]

HERMES_FLAT_EXPORT = [
    {"role": "user", "content": "Tell me about the project."},
    {"role": "assistant", "content": "It uses FastAPI and ChromaDB."},
]

HERMES_NESTED_EXPORT = [
    {
        "title": "Refactor auth module",
        "messages": [
            {"role": "user", "content": "How should we refactor auth?"},
            {"role": "assistant", "content": "Extract a middleware layer."},
        ],
    }
]


# ---------------------------------------------------------------------------
# 1. ChatGPT parser
# ---------------------------------------------------------------------------


def test_chatgpt_parses_title() -> None:
    convos = _parse_chatgpt(CHATGPT_EXPORT)
    assert len(convos) == 1
    assert convos[0].title == "Fix the login bug"


def test_chatgpt_parses_turns() -> None:
    turns = _parse_chatgpt(CHATGPT_EXPORT)[0].turns
    assert any(t.role == "user" and "login" in t.content for t in turns)
    assert any(t.role == "assistant" for t in turns)


def test_chatgpt_skips_system_and_tool_roles() -> None:
    data = [
        {
            "title": "Test",
            "mapping": {
                "s": {
                    "message": {
                        "author": {"role": "system"},
                        "content": {"content_type": "text", "parts": ["System prompt"]},
                    }
                }
            },
        }
    ]
    convos = _parse_chatgpt(data)
    assert len(convos) == 0  # no user/assistant turns → skipped


def test_chatgpt_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="array"):
        _parse_chatgpt({"not": "a list"})


# ---------------------------------------------------------------------------
# 2. Gemini parser — conversations format
# ---------------------------------------------------------------------------


def test_gemini_conversations_parses_title() -> None:
    convos = _parse_gemini(GEMINI_CONVERSATIONS_EXPORT)
    assert convos[0].title == "Plan my day"


def test_gemini_conversations_maps_model_to_assistant() -> None:
    turns = _parse_gemini(GEMINI_CONVERSATIONS_EXPORT)[0].turns
    roles = {t.role for t in turns}
    assert "assistant" in roles
    assert "model" not in roles


def test_gemini_activity_log_creates_user_turn() -> None:
    convos = _parse_gemini(GEMINI_ACTIVITY_EXPORT)
    assert len(convos) == 1
    assert convos[0].turns[0].role == "user"
    assert "Python" in convos[0].turns[0].content


# ---------------------------------------------------------------------------
# 3. Hermes parser
# ---------------------------------------------------------------------------


def test_hermes_flat_list_single_convo() -> None:
    convos = _parse_hermes(HERMES_FLAT_EXPORT)
    assert len(convos) == 1
    assert len(convos[0].turns) == 2


def test_hermes_nested_parses_title() -> None:
    convos = _parse_hermes(HERMES_NESTED_EXPORT)
    assert convos[0].title == "Refactor auth module"


def test_hermes_skips_empty_content() -> None:
    data = [{"role": "user", "content": ""}]
    assert _parse_hermes(data) == []


# ---------------------------------------------------------------------------
# 4. Auto-detect (_sniff_format)
# ---------------------------------------------------------------------------


def test_sniff_chatgpt() -> None:
    assert _sniff_format(CHATGPT_EXPORT) == "chatgpt"


def test_sniff_gemini_conversations() -> None:
    assert _sniff_format(GEMINI_CONVERSATIONS_EXPORT) == "gemini"


def test_sniff_hermes_flat() -> None:
    assert _sniff_format(HERMES_FLAT_EXPORT) == "hermes"


def test_sniff_hermes_nested() -> None:
    assert _sniff_format(HERMES_NESTED_EXPORT) == "hermes"


def test_sniff_empty_returns_hermes() -> None:
    assert _sniff_format([]) == "hermes"


# ---------------------------------------------------------------------------
# 5. parse_file
# ---------------------------------------------------------------------------


def test_parse_file_chatgpt(tmp_path: Path) -> None:
    f = tmp_path / "convos.json"
    f.write_text(json.dumps(CHATGPT_EXPORT), encoding="utf-8")
    convos, fmt = parse_file(f, format="auto")
    assert fmt == "chatgpt"
    assert len(convos) == 1


def test_parse_file_explicit_format(tmp_path: Path) -> None:
    f = tmp_path / "c.json"
    f.write_text(json.dumps(HERMES_FLAT_EXPORT), encoding="utf-8")
    convos, fmt = parse_file(f, format="hermes")
    assert fmt == "hermes"


def test_parse_file_unknown_format(tmp_path: Path) -> None:
    f = tmp_path / "c.json"
    f.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown format"):
        parse_file(f, format="grok")


def test_parse_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_file(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# 6. ingest
# ---------------------------------------------------------------------------


def _make_convo(title: str = "Test", n_turns: int = 2) -> Conversation:
    return Conversation(
        title=title,
        turns=[
            Turn(role="user", content=f"user turn {i}")
            if i % 2 == 0
            else Turn(role="assistant", content=f"assistant turn {i}")
            for i in range(n_turns)
        ],
        source="chatgpt",
    )


def test_ingest_creates_sessions() -> None:
    store = FakeSessionStore()
    result = ingest([_make_convo("A"), _make_convo("B")], store, memory_vault=None)
    assert result.sessions_created == 2
    assert len(store.sessions) == 2


def test_ingest_sets_titles() -> None:
    store = FakeSessionStore()
    ingest([_make_convo("My convo")], store)
    assert store.sessions[0].get("title") == "My convo"


def test_ingest_logs_turns() -> None:
    store = FakeSessionStore()
    ingest([_make_convo(n_turns=4)], store)
    assert len(store.messages) == 4


def test_ingest_adds_memory_facts() -> None:
    store = FakeSessionStore()
    vault = FakeMemoryVault()
    result = ingest([_make_convo()], store, memory_vault=vault)
    assert result.memory_facts_added == 1
    assert vault.facts[0]["category"] == "imported_conversation"


def test_ingest_skips_empty_conversations() -> None:
    store = FakeSessionStore()
    empty = Conversation(title="Empty", turns=[])
    result = ingest([empty, _make_convo()], store)
    assert result.skipped == 1
    assert result.sessions_created == 1


def test_ingest_without_vault_skips_facts() -> None:
    store = FakeSessionStore()
    result = ingest([_make_convo()], store, memory_vault=None)
    assert result.memory_facts_added == 0
