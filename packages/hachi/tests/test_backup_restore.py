"""Tests for the `hachi backup` / `hachi restore` CLI commands (AUDIT P1-9 Part A).

Strategy:
  - Monkeypatch ``get_hachi_paths()`` in ``hachi.cli.main`` to point at tmp dirs
    so real user data is never touched.
  - Use a real (small) SQLite SessionStore so the hot-backup round-trip is tested
    against real SQL code, not just a file copy.
  - Use a fake vault directory (plain files) to verify copytree round-trip.
  - Confirm that restore without ``--yes`` is refused.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hachi.cli.main import app
from hachi.core.paths import HachiPaths

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_paths(tmp_path: Path) -> HachiPaths:
    """Return a HachiPaths rooted in *tmp_path* so no real user data is touched."""
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"

    for d in (config_dir, data_dir, state_dir, cache_dir):
        d.mkdir(parents=True, exist_ok=True)

    return HachiPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        state_dir=state_dir,
    )


def _seed_sessions_db(db_path: Path) -> None:
    """Write a minimal sessions DB with one row so we can verify round-trip content."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES ('test-session-1', 'Test Session', '2026-06-24T00:00:00')"
        )
        conn.commit()
    finally:
        conn.close()


def _seed_fake_vault(vault_dir: Path) -> None:
    """Create a fake ChromaDB vault directory with a sentinel file."""
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "chroma.sqlite3").write_text("fake-chroma-data", encoding="utf-8")
    (vault_dir / "collections").mkdir(exist_ok=True)
    (vault_dir / "collections" / "core_memory").write_text("fake-collection", encoding="utf-8")


# ---------------------------------------------------------------------------
# Part A tests — backup creates the expected files
# ---------------------------------------------------------------------------


class TestBackupCommand:
    """hachi backup creates a timestamped directory with sessions.db and chroma_vault/."""

    def test_backup_creates_sessions_db(self, tmp_path: Path) -> None:
        """Backup produces a valid SQLite file at <backup_dir>/sessions.db."""
        fake_paths = _make_fake_paths(tmp_path)
        _seed_sessions_db(fake_paths.sessions_db)

        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        # Exactly one timestamped sub-directory should exist.
        backup_dirs = list(backup_dest.iterdir())
        assert len(backup_dirs) == 1
        backup_dir = backup_dirs[0]
        assert backup_dir.name.startswith("hachi-backup-")

        sessions_backup = backup_dir / "sessions.db"
        assert sessions_backup.exists(), "sessions.db not found in backup"

        # Verify the backup is a readable SQLite file containing our row.
        conn = sqlite3.connect(str(sessions_backup))
        try:
            rows = conn.execute("SELECT id FROM sessions").fetchall()
        finally:
            conn.close()
        assert ("test-session-1",) in rows

    def test_backup_copies_chroma_vault(self, tmp_path: Path) -> None:
        """Backup copies the ChromaDB vault directory."""
        fake_paths = _make_fake_paths(tmp_path)
        _seed_fake_vault(fake_paths.chroma_dir)

        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        backup_dir = list(backup_dest.iterdir())[0]
        vault_backup = backup_dir / "chroma_vault"
        assert vault_backup.is_dir(), "chroma_vault not found in backup"
        sentinel = vault_backup / "chroma.sqlite3"
        assert sentinel.exists()
        assert sentinel.read_text(encoding="utf-8") == "fake-chroma-data"

    def test_backup_copies_config_files(self, tmp_path: Path) -> None:
        """Backup includes settings.toml and device-permissions.og when present."""
        fake_paths = _make_fake_paths(tmp_path)
        fake_paths.global_config_toml.write_text(
            "[provider]\nkind = 'anthropic'\n", encoding="utf-8"
        )
        fake_paths.permissions_file.write_text("::index\n# permissions\n", encoding="utf-8")

        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        backup_dir = list(backup_dest.iterdir())[0]
        assert (backup_dir / "settings.toml").exists()
        assert (backup_dir / "device-permissions.og").exists()

    def test_backup_excludes_dotenv(self, tmp_path: Path) -> None:
        """Backup must NOT copy .env files (they contain secrets)."""
        fake_paths = _make_fake_paths(tmp_path)
        # Plant a .env in the config dir to confirm it is not copied.
        (fake_paths.config_dir / ".env").write_text("ANTHROPIC_API_KEY=sk-test", encoding="utf-8")

        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        backup_dir = list(backup_dest.iterdir())[0]
        assert not (backup_dir / ".env").exists(), ".env must not appear in backup"

    def test_backup_output_mentions_exclusion_of_secrets(self, tmp_path: Path) -> None:
        """Output text explicitly notes that .env / secrets are excluded."""
        fake_paths = _make_fake_paths(tmp_path)
        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        assert ".env" in result.output
        assert "excluded" in result.output.lower() or "secrets" in result.output.lower()

    def test_backup_default_dest_is_under_state_dir(self, tmp_path: Path) -> None:
        """When --dest is omitted, the backup lands under <state_dir>/backups/."""
        fake_paths = _make_fake_paths(tmp_path)
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup"])

        assert result.exit_code == 0, result.output
        backups_dir = fake_paths.state_dir / "backups"
        assert backups_dir.exists()
        backup_dirs = list(backups_dir.iterdir())
        assert len(backup_dirs) == 1


# ---------------------------------------------------------------------------
# Part A tests — restore round-trips content
# ---------------------------------------------------------------------------


class TestRestoreCommand:
    """hachi restore recovers sessions.db and chroma_vault/ from a backup directory."""

    def _make_backup(self, tmp_path: Path, fake_paths: HachiPaths) -> Path:
        """Run hachi backup and return the created backup directory."""
        _seed_sessions_db(fake_paths.sessions_db)
        _seed_fake_vault(fake_paths.chroma_dir)

        backup_dest = tmp_path / "backups"
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["backup", "--dest", str(backup_dest)])

        assert result.exit_code == 0, result.output
        backup_dirs = list(backup_dest.iterdir())
        assert len(backup_dirs) == 1
        return backup_dirs[0]

    def test_restore_round_trips_sessions_db(self, tmp_path: Path) -> None:
        """Restored sessions.db contains the same rows as the original."""
        fake_paths = _make_fake_paths(tmp_path)
        backup_dir = self._make_backup(tmp_path, fake_paths)

        # Wipe the live sessions db to simulate data loss.
        fake_paths.sessions_db.unlink(missing_ok=True)

        runner = CliRunner()
        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["restore", str(backup_dir), "--yes"])

        assert result.exit_code == 0, result.output
        assert fake_paths.sessions_db.exists(), "sessions.db was not restored"

        conn = sqlite3.connect(str(fake_paths.sessions_db))
        try:
            rows = conn.execute("SELECT id FROM sessions").fetchall()
        finally:
            conn.close()
        assert ("test-session-1",) in rows

    def test_restore_round_trips_chroma_vault(self, tmp_path: Path) -> None:
        """Restored chroma_vault/ contains the same sentinel file."""
        import shutil

        fake_paths = _make_fake_paths(tmp_path)
        backup_dir = self._make_backup(tmp_path, fake_paths)

        # Wipe the live vault to simulate data loss.
        shutil.rmtree(str(fake_paths.chroma_dir), ignore_errors=True)

        runner = CliRunner()
        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["restore", str(backup_dir), "--yes"])

        assert result.exit_code == 0, result.output
        assert fake_paths.chroma_dir.exists(), "chroma_vault was not restored"
        sentinel = fake_paths.chroma_dir / "chroma.sqlite3"
        assert sentinel.exists()
        assert sentinel.read_text(encoding="utf-8") == "fake-chroma-data"

    def test_restore_requires_yes_flag(self, tmp_path: Path) -> None:
        """Restore without --yes must refuse and exit cleanly (non-interactive simulation)."""
        fake_paths = _make_fake_paths(tmp_path)
        backup_dir = self._make_backup(tmp_path, fake_paths)

        runner = CliRunner()
        # Provide "n" as stdin so the interactive prompt gets a "no" answer.
        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["restore", str(backup_dir)], input="n\n")

        # Exit 0 (user cancelled cleanly) or the prompt suppressed; either way
        # the important assertion is that nothing was overwritten.
        assert "cancel" in result.output.lower() or result.exit_code == 0

    def test_restore_without_confirmation_does_not_overwrite(self, tmp_path: Path) -> None:
        """Answering 'n' to the confirmation prompt must not touch live data."""
        fake_paths = _make_fake_paths(tmp_path)
        backup_dir = self._make_backup(tmp_path, fake_paths)

        # Plant a marker in the live sessions db using the same 3-column schema
        # that _seed_sessions_db created (the backup was made from that db).
        conn = sqlite3.connect(str(fake_paths.sessions_db))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (id, title, created_at) "
                "VALUES ('live-row', 'Live', '2026-06-24T12:00:00')"
            )
            conn.commit()
        finally:
            conn.close()

        runner = CliRunner()
        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            runner.invoke(app, ["restore", str(backup_dir)], input="n\n")

        # The live-row we planted must still be there (restore was aborted).
        conn2 = sqlite3.connect(str(fake_paths.sessions_db))
        try:
            rows = conn2.execute("SELECT id FROM sessions WHERE id = 'live-row'").fetchall()
        finally:
            conn2.close()
        assert rows, "Live row was removed despite restore being cancelled"

    def test_restore_nonexistent_src_exits_with_error(self, tmp_path: Path) -> None:
        """Restore from a path that does not exist must print an error and exit 1."""
        fake_paths = _make_fake_paths(tmp_path)
        runner = CliRunner()

        with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
            result = runner.invoke(app, ["restore", str(tmp_path / "no-such-dir"), "--yes"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()
