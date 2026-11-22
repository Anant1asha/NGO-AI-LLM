"""Tests for Task 6c credential commands, Task 6d TOKOBOROS shim, and Task 8c og commands.

Uses Typer's CliRunner; monkeypatches env/vault; uses a tmp skills dir for og tests.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from hachi.cli.main import (
    _TOKOBOROS_RENAMES,
    KNOWN_CREDENTIAL_KEYS,
    _apply_tokoboros_shim,
    app,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vault(
    *,
    tokens: dict[str, str] | None = None,
    metadata: list[dict[str, str]] | None = None,
) -> MagicMock:
    """Build a MagicMock CredentialVault with the given stored tokens."""
    tokens = dict(tokens or {})
    meta = list(metadata or [])

    vault = MagicMock()
    vault.get_token.side_effect = lambda key, **kw: tokens.get(key)
    vault.set_token.side_effect = lambda key, value: tokens.update({key: value})
    vault.delete_token.side_effect = lambda key: tokens.pop(key, None)
    vault.list_token_metadata.return_value = meta
    return vault


def _patch_vault(vault: MagicMock):
    """Patch _get_vault in hachi.cli.main to return the given mock vault."""
    return patch("hachi.cli.main._get_vault", return_value=vault)


# ---------------------------------------------------------------------------
# Task 6c — hachi set
# ---------------------------------------------------------------------------


class TestCredSet:
    def test_set_single_pair(self) -> None:
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["set", "ANTHROPIC_API_KEY=sk-abc123"])
        assert result.exit_code == 0
        assert "Saved" in result.output
        assert "ANTHROPIC_API_KEY" in result.output
        vault.set_token.assert_called_once_with("ANTHROPIC_API_KEY", "sk-abc123")

    def test_set_multiple_pairs(self) -> None:
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(
                app, ["set", "ANTHROPIC_API_KEY=sk-abc", "tavily_api_key=tv-xyz"]
            )
        assert result.exit_code == 0
        assert vault.set_token.call_count == 2
        calls = {c.args[0]: c.args[1] for c in vault.set_token.call_args_list}
        assert calls["ANTHROPIC_API_KEY"] == "sk-abc"
        assert calls["tavily_api_key"] == "tv-xyz"

    def test_set_bare_token_rejected(self) -> None:
        """A bare value with no '=' must be rejected with non-zero exit."""
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["set", "no-equals-here"])
        assert result.exit_code != 0
        assert "KEY=value" in result.output or "not a KEY=value" in result.output
        vault.set_token.assert_not_called()

    def test_set_unknown_key_warns_but_proceeds(self) -> None:
        """An unknown key should emit a warning but still be stored."""
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["set", "MY_CUSTOM_KEY=hunter2"])
        assert result.exit_code == 0
        assert "Warning" in result.output or "unknown key" in result.output
        vault.set_token.assert_called_once_with("MY_CUSTOM_KEY", "hunter2")

    def test_set_known_key_no_warning(self) -> None:
        """A key in KNOWN_CREDENTIAL_KEYS must not produce an unknown-key warning."""
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["set", "ANTHROPIC_API_KEY=sk-test"])
        assert "unknown key" not in result.output.lower()
        assert result.exit_code == 0

    def test_set_value_containing_equals(self) -> None:
        """Only the FIRST '=' splits key from value; value may contain more '=' chars."""
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["set", "HACHI_SECRET_PASSPHRASE=a=b=c"])
        assert result.exit_code == 0
        vault.set_token.assert_called_once_with("HACHI_SECRET_PASSPHRASE", "a=b=c")


# ---------------------------------------------------------------------------
# Task 6c — hachi get
# ---------------------------------------------------------------------------


class TestCredGet:
    def test_get_existing_key_masked(self) -> None:
        vault = _make_vault(tokens={"ANTHROPIC_API_KEY": "sk-abcdefghijklmnopqrstuvwxyz"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["get", "ANTHROPIC_API_KEY"])
        assert result.exit_code == 0
        # Must NOT contain the full value
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in result.output
        # Must contain the masked representation pattern
        assert "…" in result.output or "****" in result.output

    def test_get_missing_key_shows_not_set(self) -> None:
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["get", "ANTHROPIC_API_KEY"])
        assert result.exit_code == 0
        assert "not set" in result.output

    def test_get_short_secret_fully_masked(self) -> None:
        """Values shorter than 8 chars must be masked entirely (no leaking chars)."""
        vault = _make_vault(tokens={"tavily_api_key": "short"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["get", "tavily_api_key"])
        assert result.exit_code == 0
        assert "short" not in result.output

    def test_get_never_prints_full_value(self) -> None:
        """Full value must never appear in output regardless of length."""
        secret = "sk-" + ("x" * 50)
        vault = _make_vault(tokens={"ANTHROPIC_API_KEY": secret})
        with _patch_vault(vault):
            result = runner.invoke(app, ["get", "ANTHROPIC_API_KEY"])
        assert secret not in result.output


# ---------------------------------------------------------------------------
# Task 6c — hachi list-keys
# ---------------------------------------------------------------------------


class TestCredListKeys:
    def test_list_keys_shows_all_known_keys(self) -> None:
        vault = _make_vault(metadata=[])
        with _patch_vault(vault):
            result = runner.invoke(app, ["list-keys"])
        assert result.exit_code == 0
        # Every key in the schema must appear
        for key in KNOWN_CREDENTIAL_KEYS:
            assert key in result.output

    def test_list_keys_vault_status(self) -> None:
        vault = _make_vault(
            metadata=[{"name": "ANTHROPIC_API_KEY", "backend": "keyring"}]
        )
        with _patch_vault(vault):
            result = runner.invoke(app, ["list-keys"])
        assert result.exit_code == 0
        assert "SET (vault)" in result.output

    def test_list_keys_env_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A key present in os.environ but not in vault shows SET (env)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-value")
        vault = _make_vault(metadata=[])
        with _patch_vault(vault):
            result = runner.invoke(app, ["list-keys"])
        assert result.exit_code == 0
        assert "SET (env)" in result.output

    def test_list_keys_not_set_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A key absent from both vault and env shows 'not set'."""
        # Ensure the key is not in environ
        monkeypatch.delenv("HACHI_SECRET_PASSPHRASE", raising=False)
        vault = _make_vault(metadata=[])
        with _patch_vault(vault):
            result = runner.invoke(app, ["list-keys"])
        assert result.exit_code == 0
        assert "not set" in result.output

    def test_list_keys_extra_vault_keys_appended(self) -> None:
        """Keys in vault but not in KNOWN_CREDENTIAL_KEYS must still appear."""
        vault = _make_vault(
            metadata=[{"name": "MY_CUSTOM_VENDOR_KEY", "backend": "keyring"}]
        )
        with _patch_vault(vault):
            result = runner.invoke(app, ["list-keys"])
        assert result.exit_code == 0
        assert "MY_CUSTOM_VENDOR_KEY" in result.output


# ---------------------------------------------------------------------------
# Task 6c — hachi unset
# ---------------------------------------------------------------------------


class TestCredUnset:
    def test_unset_removes_from_vault(self) -> None:
        vault = _make_vault(tokens={"ANTHROPIC_API_KEY": "sk-old"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["unset", "ANTHROPIC_API_KEY"])
        assert result.exit_code == 0
        assert "Removed" in result.output
        vault.delete_token.assert_called_once_with("ANTHROPIC_API_KEY")

    def test_unset_notes_lingering_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When an env var of the same name still exists, a note must be shown."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-value")
        vault = _make_vault(tokens={"ANTHROPIC_API_KEY": "vault-value"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["unset", "ANTHROPIC_API_KEY"])
        assert result.exit_code == 0
        # The note about shadowing must be present
        output_lower = result.output.lower()
        assert "shadow" in output_lower or "environment variable" in output_lower


# ---------------------------------------------------------------------------
# Task 6c — keys sub-app aliases
# ---------------------------------------------------------------------------


class TestKeysSubApp:
    def test_keys_set_alias(self) -> None:
        vault = _make_vault()
        with _patch_vault(vault):
            result = runner.invoke(app, ["keys", "set", "ANTHROPIC_API_KEY=sk-test"])
        assert result.exit_code == 0
        assert "Saved" in result.output

    def test_keys_get_alias(self) -> None:
        vault = _make_vault(tokens={"ANTHROPIC_API_KEY": "sk-abcdefghijkl"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["keys", "get", "ANTHROPIC_API_KEY"])
        assert result.exit_code == 0
        assert "sk-abcdefghijkl" not in result.output

    def test_keys_list_alias(self) -> None:
        vault = _make_vault(metadata=[])
        with _patch_vault(vault):
            result = runner.invoke(app, ["keys", "list"])
        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output

    def test_keys_unset_alias(self) -> None:
        vault = _make_vault(tokens={"tavily_api_key": "tv-test"})
        with _patch_vault(vault):
            result = runner.invoke(app, ["keys", "unset", "tavily_api_key"])
        assert result.exit_code == 0
        assert "Removed" in result.output


# ---------------------------------------------------------------------------
# Task 6d — TOKOBOROS_ → HACHI_ back-compat shim
# ---------------------------------------------------------------------------


class TestTokoborosShim:
    def test_shim_copies_old_to_new(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TOKOBOROS_* set and HACHI_* absent → HACHI_* is populated."""
        monkeypatch.setenv("TOKOBOROS_STT_API_KEY", "stt-value")
        monkeypatch.delenv("HACHI_STT_API_KEY", raising=False)

        _apply_tokoboros_shim()

        assert os.environ.get("HACHI_STT_API_KEY") == "stt-value"

    def test_shim_does_not_overwrite_existing_hachi_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When HACHI_* is already set, the shim must NOT overwrite it."""
        monkeypatch.setenv("TOKOBOROS_TTS_API_KEY", "old-tts")
        monkeypatch.setenv("HACHI_TTS_API_KEY", "existing-tts")

        _apply_tokoboros_shim()

        assert os.environ.get("HACHI_TTS_API_KEY") == "existing-tts"

    def test_shim_emits_warning(self, monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
        """Migrating a key must log a deprecation warning."""
        import logging

        monkeypatch.setenv("TOKOBOROS_SMTP_USER", "user@example.com")
        monkeypatch.delenv("HACHI_SMTP_USER", raising=False)

        with caplog.at_level(logging.WARNING, logger="hachi.cli.main"):
            _apply_tokoboros_shim()

        assert any("TOKOBOROS_SMTP_USER" in msg for msg in caplog.messages)

    def test_shim_no_op_when_old_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When the TOKOBOROS_* var is absent, the HACHI_* var must not be created."""
        monkeypatch.delenv("TOKOBOROS_SMTP_HOST", raising=False)
        monkeypatch.delenv("HACHI_SMTP_HOST", raising=False)

        _apply_tokoboros_shim()

        assert "HACHI_SMTP_HOST" not in os.environ

    def test_shim_covers_all_renames(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every key in _TOKOBOROS_RENAMES must be handled by the shim."""
        for old, new in _TOKOBOROS_RENAMES.items():
            monkeypatch.setenv(old, f"value-for-{old}")
            monkeypatch.delenv(new, raising=False)

        _apply_tokoboros_shim()

        for old, new in _TOKOBOROS_RENAMES.items():
            assert os.environ.get(new) == f"value-for-{old}", (
                f"Shim did not copy {old!r} → {new!r}"
            )


# ---------------------------------------------------------------------------
# Task 8c — og history + rollback round-trip
# ---------------------------------------------------------------------------


class TestOgHistoryRollback:
    """Round-trip tests for hachi og history and hachi og rollback."""

    def test_og_history_empty(self, tmp_path: Path) -> None:
        """history command on a skill with no history exits 0 and reports nothing."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            result = runner.invoke(app, ["og", "history", "no-such-skill"])

        assert result.exit_code == 0
        assert "No history" in result.output

    def test_og_history_shows_versions(self, tmp_path: Path) -> None:
        """After recording versions, history command lists them."""
        from hachi.core.og_history import record_version

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        record_version(
            "my-skill",
            "::version 1.0.0\n::name my-skill\n",
            "human",
            "initial",
            skills_dir=skills_dir,
        )
        record_version(
            "my-skill",
            "::version 1.0.1\n::name my-skill\n",
            "agent",
            "minor fix",
            skills_dir=skills_dir,
        )

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            result = runner.invoke(app, ["og", "history", "my-skill"])

        assert result.exit_code == 0
        assert "1" in result.output
        assert "2" in result.output
        assert "initial" in result.output
        assert "minor fix" in result.output

    def test_og_rollback_restores_content(self, tmp_path: Path) -> None:
        """Rollback rewrites the skill file with the historical snapshot."""
        from hachi.core.og_history import record_version

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        v1_content = "::version 1.0.0\n::name my-skill\n::dense original content\n"
        v2_content = "::version 1.0.1\n::name my-skill\n::dense updated content\n"

        record_version("my-skill", v1_content, "human", "initial", skills_dir=skills_dir)
        record_version("my-skill", v2_content, "agent", "update", skills_dir=skills_dir)

        # Write the current (v2) file
        skill_file = skills_dir / "my-skill.og"
        skill_file.write_text(v2_content, encoding="utf-8")

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            result = runner.invoke(app, ["og", "rollback", "my-skill", "--version", "1"])

        assert result.exit_code == 0
        assert "Rolled back" in result.output

        # File content must match v1 snapshot
        actual = skill_file.read_text(encoding="utf-8")
        assert actual == v1_content

    def test_og_rollback_records_new_version(self, tmp_path: Path) -> None:
        """After rollback, a new human-authored version is recorded in history."""
        from hachi.core.og_history import list_versions, record_version

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        v1_content = "::version 1.0.0\n::name skill-a\n::dense v1\n"
        v2_content = "::version 1.0.1\n::name skill-a\n::dense v2\n"

        record_version("skill-a", v1_content, "human", "initial", skills_dir=skills_dir)
        record_version("skill-a", v2_content, "agent", "update", skills_dir=skills_dir)

        skill_file = skills_dir / "skill-a.og"
        skill_file.write_text(v2_content, encoding="utf-8")

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            runner.invoke(app, ["og", "rollback", "skill-a", "--version", "1"])

        versions = list_versions("skill-a", skills_dir=skills_dir)
        assert len(versions) == 3
        last = versions[-1]
        assert last["author"] == "human"
        assert "rollback" in last["summary"]

    def test_og_rollback_nonexistent_version_errors(self, tmp_path: Path) -> None:
        """Rollback to a version that doesn't exist must exit non-zero."""
        from hachi.core.og_history import record_version

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        record_version("skill-b", "::name skill-b\n", "human", "v1", skills_dir=skills_dir)

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            result = runner.invoke(app, ["og", "rollback", "skill-b", "--version", "99"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_og_rollback_creates_learned_subdirectory_target(self, tmp_path: Path) -> None:
        """Rollback targets an existing learned/<name>.og file when it's the current location."""
        from hachi.core.og_history import record_version

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        learned_dir = skills_dir / "learned"
        learned_dir.mkdir()

        v1_content = "::version 1.0.0\n::name skill-c\n::dense v1\n"
        v2_content = "::version 1.0.1\n::name skill-c\n::dense v2\n"

        record_version("skill-c", v1_content, "human", "initial", skills_dir=skills_dir)
        record_version("skill-c", v2_content, "agent", "update", skills_dir=skills_dir)

        # The current file lives in learned/
        skill_file = learned_dir / "skill-c.og"
        skill_file.write_text(v2_content, encoding="utf-8")

        with patch("hachi.cli.main.get_hachi_paths") as mock_paths:
            mock_paths.return_value.skills_dir = skills_dir
            result = runner.invoke(app, ["og", "rollback", "skill-c", "--version", "1"])

        assert result.exit_code == 0
        assert skill_file.read_text(encoding="utf-8") == v1_content
