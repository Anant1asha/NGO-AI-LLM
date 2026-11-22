# 25 — Migration Strategy

> Phase 2 / Gate B. How schema and data evolve safely. Closes Gate-A debt **D9**. Seams are
> `file:line`.

## 1. The one mechanism — a shared additive migration helper

Promote `SessionStore._migrate_schema` (`session_store.py:108-129` — the only working migration
today) into a reusable helper applied to **all** SQLite stores:

```python
# core/migrations.py (new)
def apply_migrations(conn: sqlite3.Connection, table: str, columns: list[ColumnSpec]) -> None:
    """Idempotent additive migration: PRAGMA table_info → ADD COLUMN for each missing column.
    The exact pattern SessionStore already uses, generalized. No version table, no down-migrations."""
```

Applied at each store's `_init_db`: `sessions.db`, `jobs.db` (`queue.py:498` — currently no ALTER
path), `memory_index.db` (`memory_index.py:25` — same gap), and the new `runs`/`files` stores.
This is the prerequisite that lets D and E add columns to existing user databases without silent
failure.

## 2. Scope discipline (per §4a)

We deliberately do **not** adopt a migration framework (Alembic/Yoyo) or down-migrations:

- All changes are **additive columns / new tables** (`CREATE TABLE IF NOT EXISTS` + `ADD COLUMN`).
- A new install and an upgraded install converge to the same schema.
- Down-migrations are unnecessary for additive changes on a single-node, single-user store.
- Trigger to revisit: the first non-additive change (column rename/drop) or a multi-tenant/server
  backend — at which point a real framework is justified. The helper is the seam.

## 3. Table placement decisions

- **`runs`** co-locates in `sessions.db` (shares the session FK, WAL, backup machinery) rather
  than a separate DB — fewer files, one backup covers run-state with its session.
- **`files`** uses its own `files.db` (independent lifecycle, larger churn) + `blobs_dir` for
  bytes.
- **`attachments`** Chroma collection is additive to the vault.

## 4. Data migrations (code-level, not schema)

- **`MODEL_PRICING` → `ModelRegistry`**: the 5 existing families migrate **verbatim** into the
  bundled defaults table; a test pins equality. No on-disk change; `CostTracker` switches its
  lookup source.
- **`func=` jobs → `handler_name=` jobs** ([16](16-durable-execution.md)): a code change, not a
  data migration — existing in-flight `func` jobs were already non-durable, so there is nothing to
  migrate; new jobs are durable.
- **ChromaDB metadata additions** are not back-filled on existing records (documented limitation);
  new writes carry new fields.

## 5. Rollback & safety

- Every store keeps WAL; `sessions.db` (now incl. `runs`) has online `backup()`
  (`session_store.py:537`); a backup helper is extended to `files.db` and the vault
  ([05](05-risk-assessment.md) M5 follow-through).
- Migrations run inside the store's transaction; a failed `ADD COLUMN` rolls back without
  corrupting the table.
- The `jobs.db` `appauthor` path inconsistency (Gate-A D15) is verified and normalized **before**
  any new column lands, so the helper targets the right file.

## 6. Test gate

A migration test boots each store against a **pre-existing prior-schema DB snapshot** and asserts:
(a) clean upgrade, (b) old rows readable, (c) new columns present and defaulted, (d) no data loss.
This is the regression guard the current bare-`CREATE` stores lack.
