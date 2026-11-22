"""P2-05: MemoryWriter typed-node write path tests.

Verifies:
- MemoryNode objects are written to the correct .og file by role
- Duplicate node names are not duplicated (idempotent write)
- New files get a ::meta header
- Existing files are appended to
- Episode nodes go to journal/<session_id>.og
- write_episode() creates the right node
- MemoryManager.set_memory_writer() is wired
- MemoryManager.write_episode() delegates to writer
"""

from __future__ import annotations

from pathlib import Path

from hachi.core.memory_writer import (
    MemoryNode,
    MemoryWriter,
    _read_node_ids,
    _route,
    _slugify,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _writer(tmp_path: Path) -> MemoryWriter:
    return MemoryWriter(memory_dir=tmp_path / "memory")


def _node(role: str, name: str = "test-fact", dense: str = "A test fact.") -> MemoryNode:
    return MemoryNode(name=name, role=role, dense=dense, keywords=["test"])


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def test_route_preference_to_profile(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    node = _node("preference")
    assert _route(node, mem_dir) == mem_dir / "profile.og"


def test_route_rule_to_agent(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    assert _route(_node("rule"), mem_dir) == mem_dir / "agent.og"


def test_route_event_to_journal(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    n = MemoryNode(name="ep", role="event", dense="something", session_id="sess123")
    assert _route(n, mem_dir) == mem_dir / "journal" / "sess123.og"


def test_route_fact_with_project_slug(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    n = MemoryNode(name="db-schema", role="fact", dense="Uses PostgreSQL.", project_slug="billing")
    assert _route(n, mem_dir) == mem_dir / "projects" / "billing.og"


def test_route_fact_no_project_to_core(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    assert _route(_node("fact"), mem_dir) == mem_dir / "core_memory.og"


def test_route_person(tmp_path: Path) -> None:
    mem_dir = tmp_path / "memory"
    n = MemoryNode(name="alice", role="person", dense="Alice is the PM.", person_slug="alice")
    assert _route(n, mem_dir) == mem_dir / "people" / "alice.og"


# ---------------------------------------------------------------------------
# Write nodes
# ---------------------------------------------------------------------------


def test_write_creates_file_with_meta_header(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    node = _node("preference", name="timezone", dense="User is in UTC+5:30.")
    count = w.write_nodes([node])
    assert count == 1
    target = tmp_path / "memory" / "profile.og"
    assert target.exists()
    text = target.read_text()
    assert "::meta" in text
    assert "::node[timezone]" in text
    assert "UTC+5:30" in text


def test_write_multiple_roles_to_different_files(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    nodes = [
        _node("preference", name="name", dense="User is Alice."),
        _node("rule", name="no-emojis", dense="Do not use emojis."),
    ]
    count = w.write_nodes(nodes)
    assert count == 2
    assert (tmp_path / "memory" / "profile.og").exists()
    assert (tmp_path / "memory" / "agent.og").exists()


def test_write_idempotent_duplicate_node(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    node = _node("preference", name="timezone", dense="UTC+5:30")
    w.write_nodes([node])
    w.write_nodes([node])
    text = (tmp_path / "memory" / "profile.og").read_text()
    # Should only appear once
    assert text.count("::node[timezone]") == 1


def test_write_appends_to_existing_file(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    w.write_nodes([_node("preference", name="name", dense="Alice")])
    w.write_nodes([_node("preference", name="role", dense="Engineer")])
    text = (tmp_path / "memory" / "profile.og").read_text()
    assert "::node[name]" in text
    assert "::node[role]" in text


def test_write_creates_parent_dirs(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    node = MemoryNode(name="proj-fact", role="fact", dense="Uses Python 3.11.", project_slug="main")
    w.write_nodes([node])
    assert (tmp_path / "memory" / "projects" / "main.og").exists()


def test_write_returns_zero_for_empty_list(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    assert w.write_nodes([]) == 0


# ---------------------------------------------------------------------------
# Episode
# ---------------------------------------------------------------------------


def test_write_episode_creates_journal_file(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    w.write_episode("sess-abc", "User asked about billing migration.", ["billing", "session"])
    journal = tmp_path / "memory" / "journal" / "sess-abc.og"
    assert journal.exists()
    text = journal.read_text()
    assert "episode-sess-abc" in text
    assert "billing migration" in text


def test_write_episode_with_no_keywords(tmp_path: Path) -> None:
    w = _writer(tmp_path)
    w.write_episode("sess-xyz", "Short session.")
    journal = tmp_path / "memory" / "journal" / "sess-xyz.og"
    assert journal.exists()


# ---------------------------------------------------------------------------
# node-ID reader
# ---------------------------------------------------------------------------


def test_read_node_ids_empty_file(tmp_path: Path) -> None:
    f = tmp_path / "empty.og"
    f.write_text("")
    assert _read_node_ids(f) == set()


def test_read_node_ids_missing_file(tmp_path: Path) -> None:
    assert _read_node_ids(tmp_path / "missing.og") == set()


def test_read_node_ids_finds_all_nodes(tmp_path: Path) -> None:
    f = tmp_path / "t.og"
    f.write_text("::node[foo]\n::dense\ntext\n\n::node[bar]\n::dense\ntext2\n")
    ids = _read_node_ids(f)
    assert ids == {"foo", "bar"}


# ---------------------------------------------------------------------------
# Slugify
# ---------------------------------------------------------------------------


def test_slugify_basic() -> None:
    assert _slugify("User name") == "user-name"


def test_slugify_strips_special_chars() -> None:
    # Consecutive unsafe chars collapse to a single dash
    assert _slugify("project: billing/v2") == "project-billing-v2"


def test_slugify_max_len() -> None:
    long = "a" * 100
    assert len(_slugify(long, max_len=10)) <= 10


def test_slugify_empty_returns_node() -> None:
    assert _slugify("") == "node"


# ---------------------------------------------------------------------------
# MemoryManager integration
# ---------------------------------------------------------------------------


def test_memory_manager_set_memory_writer(tmp_path: Path) -> None:
    from hachi.core.memory import MemoryManager

    mm = MemoryManager()
    w = _writer(tmp_path)
    mm.set_memory_writer(w)
    assert mm._memory_writer is w


def test_memory_manager_write_episode(tmp_path: Path) -> None:
    from hachi.core.memory import MemoryManager

    mm = MemoryManager()
    w = _writer(tmp_path)
    mm.set_memory_writer(w)
    mm.write_episode("sess-001", "Test episode.")
    assert (tmp_path / "memory" / "journal" / "sess-001.og").exists()


def test_memory_manager_write_episode_noop_without_writer() -> None:
    from hachi.core.memory import MemoryManager

    mm = MemoryManager()
    mm.write_episode("sess-999", "No writer attached.")  # must not raise
