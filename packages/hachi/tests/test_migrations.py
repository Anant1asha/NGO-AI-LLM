"""Tests for apply_migrations — idempotent SQLite column migration (GATE-MIGRATE)."""

from __future__ import annotations

import sqlite3

from hachi.core.migrations import apply_migrations

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_table(conn: sqlite3.Connection, table: str = "test_table") -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id   TEXT PRIMARY KEY,
            name TEXT
        )
        """
    )
    conn.commit()


def _get_columns(conn: sqlite3.Connection, table: str = "test_table") -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestApplyMigrations:
    def test_adds_new_column(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        apply_migrations(conn, "test_table", [("score", "REAL DEFAULT 0")])
        assert "score" in _get_columns(conn)

    def test_adds_multiple_columns(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        apply_migrations(
            conn,
            "test_table",
            [("created_at", "TEXT"), ("updated_at", "TEXT"), ("score", "INTEGER DEFAULT 0")],
        )
        cols = _get_columns(conn)
        assert "created_at" in cols
        assert "updated_at" in cols
        assert "score" in cols

    def test_empty_migrations_no_op(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        cols_before = _get_columns(conn)
        apply_migrations(conn, "test_table", [])
        assert _get_columns(conn) == cols_before


# ---------------------------------------------------------------------------
# GATE-MIGRATE: idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_existing_column_not_duplicated(self):
        """GATE-MIGRATE: apply_migrations is idempotent on existing column."""
        conn = sqlite3.connect(":memory:")
        _create_table(conn)

        # First run: add the column
        apply_migrations(conn, "test_table", [("extra_col", "TEXT")])
        assert "extra_col" in _get_columns(conn)

        # Second run: same migration must not raise
        apply_migrations(conn, "test_table", [("extra_col", "TEXT")])
        # Column still exists, not duplicated
        assert "extra_col" in _get_columns(conn)

    def test_multiple_idempotent_runs(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        migrations = [("col_a", "TEXT"), ("col_b", "INTEGER DEFAULT 0")]

        for _ in range(5):
            apply_migrations(conn, "test_table", migrations)

        cols = _get_columns(conn)
        assert "col_a" in cols
        assert "col_b" in cols

    def test_partial_existing_columns(self):
        """Only the missing column is added; existing one is skipped."""
        conn = sqlite3.connect(":memory:")
        _create_table(conn)

        # Add col_a first
        apply_migrations(conn, "test_table", [("col_a", "TEXT")])
        cols_after_first = _get_columns(conn)
        assert "col_a" in cols_after_first
        assert "col_b" not in cols_after_first

        # Now run with both; col_a should be skipped, col_b added
        apply_migrations(conn, "test_table", [("col_a", "TEXT"), ("col_b", "INTEGER")])
        cols_after_second = _get_columns(conn)
        assert "col_a" in cols_after_second
        assert "col_b" in cols_after_second


# ---------------------------------------------------------------------------
# Original columns untouched
# ---------------------------------------------------------------------------


class TestOriginalColumnsUnchanged:
    def test_original_columns_still_accessible(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        conn.execute("INSERT INTO test_table (id, name) VALUES ('1', 'Alice')")
        conn.commit()

        apply_migrations(conn, "test_table", [("score", "INTEGER DEFAULT 0")])

        row = conn.execute("SELECT id, name, score FROM test_table WHERE id='1'").fetchone()
        assert row is not None
        assert row[0] == "1"
        assert row[1] == "Alice"
        assert row[2] == 0  # default value applied

    def test_data_preserved_after_migration(self):
        conn = sqlite3.connect(":memory:")
        _create_table(conn)
        conn.execute("INSERT INTO test_table (id, name) VALUES ('row1', 'Bob')")
        conn.commit()

        apply_migrations(conn, "test_table", [("notes", "TEXT")])

        rows = conn.execute("SELECT id, name FROM test_table").fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "Bob"


# ---------------------------------------------------------------------------
# RunStateStore uses migrations (integration smoke test)
# ---------------------------------------------------------------------------


class TestRunStateStoreMigrations:
    def test_store_schema_has_expected_columns(self, tmp_path):
        """RunStateStore._init_schema creates the runs table with correct columns."""
        from hachi.core.runtime.store import RunStateStore

        store = RunStateStore(db_path=tmp_path / "runs.db")
        cols = _get_columns(store._conn, "runs")
        expected = {
            "run_id",
            "session_id",
            "status",
            "wait_kind",
            "wait_key",
            "wait_timeout_at",
            "resume_cursor",
            "payload",
            "updated_at",
        }
        assert expected.issubset(cols)
        store.close()

    def test_store_init_idempotent(self, tmp_path):
        """Opening the same DB twice does not fail."""
        from hachi.core.runtime.store import RunStateStore

        db = tmp_path / "runs.db"
        store1 = RunStateStore(db_path=db)
        store1.close()
        store2 = RunStateStore(db_path=db)
        store2.close()
