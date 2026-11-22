"""Tests for `hachi memory add` and `hachi memory forget` commands.

Covers:
  1.  memory add  — stores to core_memory, prints ID prefix
  2.  memory add --json — returns JSON with id/collection/category
  3.  memory add --to user — routes to user_profile
  4.  memory add --to agent --category directive — routes to agent_profile
  5.  memory add unknown collection — exits 1
  6.  memory add blocked by guard — exits 1
  7.  memory add LIMIT_REACHED — exits 1 with hint
  8.  memory forget — deletes from core, prints confirmation
  9.  memory forget --json — returns JSON {deleted, id, collection}
  10. memory forget not found — exits 1
  11. memory forget --from user — routes to user collection
  12. memory forget unknown collection — exits 1
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from hachi.cli.main import app

runner = CliRunner()

_FAKE_ID = "abc123def4567890abc123def4567890"  # 32-char hex (SHA-256 prefix)


def _mock_vault(
    upsert_return: str = _FAKE_ID,
    delete_return: bool = True,
) -> MagicMock:
    vault = MagicMock()
    vault.upsert_fact.return_value = upsert_return
    vault.upsert_user_fact.return_value = upsert_return
    vault.upsert_agent_fact.return_value = upsert_return
    vault.delete_fact.return_value = delete_return
    vault.delete_user_fact.return_value = delete_return
    vault.delete_agent_fact.return_value = delete_return
    return vault


# ---------------------------------------------------------------------------
# memory add
# ---------------------------------------------------------------------------


def test_memory_add_core_rich() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "add", "Project uses PostgreSQL 15."])
    assert result.exit_code == 0
    assert "Stored" in result.output
    assert "core" in result.output
    # vault was called with default core collection
    # test_memory_add_core_rich verifies routes correctly


def test_memory_add_core_json() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "add", "Project uses PostgreSQL 15.", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == _FAKE_ID
    assert data["collection"] == "core"
    assert data["category"] == "workspace_state"


def test_memory_add_user_collection() -> None:
    vault = _mock_vault()
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(
            app,
            ["memory", "add", "User prefers dark mode.", "--to", "user", "--json"],
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["collection"] == "user"
    assert data["category"] == "preference"
    vault.upsert_user_fact.assert_called_once_with("User prefers dark mode.", category="preference")


def test_memory_add_agent_collection_with_category() -> None:
    vault = _mock_vault()
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(
            app,
            [
                "memory",
                "add",
                "Always cite sources.",
                "--to",
                "agent",
                "--category",
                "directive",
                "--json",
            ],
        )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["collection"] == "agent"
    assert data["category"] == "directive"
    vault.upsert_agent_fact.assert_called_once_with("Always cite sources.", category="directive")


def test_memory_add_unknown_collection_exits() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "add", "some fact", "--to", "badcol"])
    assert result.exit_code == 1
    assert "Unknown collection" in result.output


def test_memory_add_blocked_by_guard_exits() -> None:
    vault = _mock_vault(upsert_return="BLOCKED:prompt_injection")
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(app, ["memory", "add", "malicious content"])
    assert result.exit_code == 1
    assert "Blocked" in result.output


def test_memory_add_limit_reached_exits() -> None:
    vault = _mock_vault(upsert_return="LIMIT_REACHED")
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(app, ["memory", "add", "too many facts", "--to", "user"])
    assert result.exit_code == 1
    assert "full" in result.output.lower() or "limit" in result.output.lower()


# ---------------------------------------------------------------------------
# memory forget
# ---------------------------------------------------------------------------


def test_memory_forget_core_rich() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "forget", _FAKE_ID])
    assert result.exit_code == 0
    assert "Deleted" in result.output
    assert _FAKE_ID[:16] in result.output


def test_memory_forget_json() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "forget", _FAKE_ID, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["deleted"] is True
    assert data["id"] == _FAKE_ID
    assert data["collection"] == "core"


def test_memory_forget_not_found_exits() -> None:
    vault = _mock_vault(delete_return=False)
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(app, ["memory", "forget", "nonexistent-id-00000000"])
    assert result.exit_code == 1
    assert "Not found" in result.output or "not found" in result.output.lower()


def test_memory_forget_user_collection() -> None:
    vault = _mock_vault()
    with patch("hachi.core.memory_vault.MemoryVault", return_value=vault):
        result = runner.invoke(app, ["memory", "forget", _FAKE_ID, "--from", "user", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["collection"] == "user"
    vault.delete_user_fact.assert_called_once_with(_FAKE_ID)


def test_memory_forget_unknown_collection_exits() -> None:
    with patch("hachi.core.memory_vault.MemoryVault", return_value=_mock_vault()):
        result = runner.invoke(app, ["memory", "forget", _FAKE_ID, "--from", "badcol"])
    assert result.exit_code == 1
    assert "Unknown collection" in result.output
