# 22 — Database Changes

> Phase 2 / Gate B. Aggregates the persistence changes implied by docs 12–21. All changes are
> **additive** and applied via the shared migration helper ([25](25-migration-strategy.md)).
> Seams are `file:line`.

## 1. New SQLite tables

| Table | Store | Initiative | Key columns |
|---|---|---|---|
| `runs` | `RunStateStore` (new, `core/runtime/store.py`) | D | `run_id` PK, `session_id` FK, `status`, `wait_kind`, `wait_key`, `wait_timeout_at`, `resume_cursor`, `payload` (json), `updated_at` |
| `files` | `FileMetaStore` (new, `core/files/*`) | E | `file_id` PK (sha256), `name`, `media_type`, `size`, `status`, `extracted_text_ref`, `created_at` |

Both reuse `SessionStore`'s production patterns: WAL (`session_store.py:63`), single-connection +
lock, online `backup()` (`session_store.py:537`), and the additive `apply_migrations` helper.

## 2. New ChromaDB collection

| Collection | Initiative | Purpose |
|---|---|---|
| `attachments` (account-namespaced) | E | extracted file-text chunks, merged via the existing RRF `semantic_search` (`memory_vault.py:785`) |

Additive to the 5 existing collections (`memory_vault.py:216`); no change to existing collections.

## 3. Modified data ownership (no schema break)

- **Model pricing** moves from the `MODEL_PRICING` dict (`cost.py:19-25`) into the
  `ModelRegistry` defaults table; values migrate **verbatim** (pinned by test). `CostTracker`
  reads pricing from the registry. No on-disk schema; this is a code-level data move.
- **Event log** stays in-memory (cap 2000, `runtime_read_models.py:247`) — **persistence is
  deferred** (the C seam). No new table now.

## 4. Migration-helper retrofit (closes debt D9)

`jobs.db` (`queue.py:498`) and `memory_index.db` (`memory_index.py:25`) currently use bare
`CREATE TABLE IF NOT EXISTS` with no `ALTER` path. The new `apply_migrations(conn, table, cols)`
helper ([25](25-migration-strategy.md)) is applied to **all** SQLite stores, so future additive
columns reach existing user DBs. This is a prerequisite for the `runs`/`files` tables to evolve
safely.

## 5. Path additions

`paths.py:19` gains `blobs_dir` (file bytes), `files_db`, `runs_db` (or co-locate `runs` in
`sessions.db` — decided in [25](25-migration-strategy.md) §3). The dead `tui_state_db`
(`paths.py:48`) is removed. The possible `jobs.db` `appauthor` inconsistency (Gate-A D15) is
verified and normalized.

## 6. What could break (and the guard)

- **New tables on existing installs.** *Guard:* additive `CREATE IF NOT EXISTS` + `apply_migrations`;
  a test runs the boot path against a *pre-existing* DB snapshot and asserts clean upgrade.
- **Pricing move changes a cost number.** *Guard:* test asserts registry pricing == old
  `MODEL_PRICING` for the 5 existing families.
- **FK integrity** for `runs.session_id`. *Guard:* the same FK-ordering discipline that the prior
  SessionStore batching work required (sync `start_session` before dependent writes).

## 7. Deferred

Event-log persistence; cloud/Postgres backends (the `StorageProvider`/store interfaces are the
seam); cross-store transactions. Single-node SQLite remains the target ([05](05-risk-assessment.md) R11).
