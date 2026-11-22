"""Shared SQLite migration helper.

Provides ``apply_migrations`` — a safe, additive, idempotent helper for adding
new columns to existing tables.  Used by all SQLite stores in Hachi to close
debt D9 (each store had its own ad-hoc migration logic).

Usage::

    from hachi.core.migrations import apply_migrations

    apply_migrations(conn, "sessions", [("new_col", "TEXT"), ("other_col", "INTEGER")])
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def apply_migrations(
    conn: sqlite3.Connection,
    table: str,
    migrations: list[tuple[str, str]],
) -> None:
    """Apply additive column migrations to *table* on *conn*.

    Each migration is a ``(column_name, column_definition)`` pair.  A column is
    only added when it does not already exist in the table schema; the call is
    therefore idempotent and safe to run at every boot.

    Args:
        conn:       An open SQLite connection.  The caller retains ownership;
                    this function does NOT commit or close.
        table:      The table to migrate.
        migrations: Ordered list of ``(column, definition)`` pairs to add.
                    Example: ``[("created_at", "TEXT"), ("score", "REAL DEFAULT 0")]``

    Raises:
        sqlite3.OperationalError: If the table does not exist or the ALTER fails
                                   for a reason other than "duplicate column".
    """
    if not migrations:
        return

    existing_cols: set[str] = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

    for column, definition in migrations:
        if column in existing_cols:
            continue
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        logger.debug("apply_migrations: %s", sql)
        conn.execute(sql)
        conn.commit()
        existing_cols.add(column)
