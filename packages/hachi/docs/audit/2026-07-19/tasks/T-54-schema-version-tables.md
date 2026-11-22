# T-54 · Give every SQLite store a `schema_version` table serviced by `core/migrations.py`

|  |  |
|---|---|
| **Source finding** | CF-13 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | **[T-53](T-53-jobs-db-path-unification.md)** — `jobs.db` must be at its final path first, or you version it twice |
| **Blocks** | [T-55](T-55-backup-completeness.md) — ideally, so a backup records store versions |
| **Effort** | ~3 days |
| **Difficulty** | Medium — the helper is small; the inventory and the "what version is an existing DB?" question are the work |
| **Files you will touch** | `src/hachi/core/migrations.py`, `src/hachi/core/session_store.py`, `src/hachi/core/memory_index.py`, `src/hachi/core/files/store.py`, `src/hachi/core/runtime/store.py`, `src/hachi/jobs/queue.py`, `src/hachi/core/paths.py` (only if you retire `tui_state_db`), `tests/test_migrations.py`, `docs/DECISIONS.md`, `docs/bug-bank.md` |

---

## 1. Brief

**No `schema_version` table exists anywhere in Hachi.** Six SQLite stores hold user
data across two on-disk roots, and none of them records what shape it is in. Two of the
six use the shared `core/migrations.py` helper; the rest carry ad-hoc `PRAGMA
table_info` + `ALTER TABLE` blocks or no migration path at all. There is no way for
code to ask a database "which version are you?", so there is no way to refuse to open
one that is newer than the running build, and no way to write a migration that is not
purely additive.

When you are done, every live store has a `schema_version` table, `core/migrations.py`
owns reading and writing it, and opening a store from a **newer** build fails loudly
instead of corrupting data.

## 2. Why this matters

The product sells *portable, owned data*. Ten stores with no version stamps is the
prototype-grade version of that promise: it works right up until the first schema change
that is not an added column, at which point there is no safe way to tell an old database
from a new one — and the failure mode is silent misreads, not a clean error.

The concrete near-term cost is that **every migration must be additive forever**.
`apply_migrations` can only `ALTER TABLE ... ADD COLUMN` (§3.3). Renaming a column,
changing a type, or splitting a table has no supported path, so the next person who
needs one will either write a bespoke one-off (a seventh migration dialect) or, more
likely, avoid the change and work around the schema. That is how schemas calcify.

This is also the cheapest possible insurance: a version stamp costs one table and one
integer, and it is only cheap *before* you need it.

If the change you are about to write does not end with "opening a future-version
database raises instead of silently proceeding", stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 `schema_version` does not exist as a database concept

```bash
rg -n "schema_version" src/ tests/
```

Every hit is the **observability telemetry envelope** — an unrelated wire-format field:

```
src/hachi/core/obs/envelope.py:59    All fields are optional except ``timestamp``, ``schema_version``, and
src/hachi/core/obs/envelope.py:65        schema_version:   ``"1"`` for this generation of the schema.
src/hachi/core/obs/envelope.py:88    schema_version: str
src/hachi/core/obs/envelope.py:113           "schema_version": self.schema_version,
src/hachi/core/obs/envelope.py:167       schema_version=_SCHEMA_VERSION,
tests/test_obs_envelope.py:67,70,79,87
```

No SQL, no table, no `PRAGMA user_version`. Confirm the second form too:

```bash
rg -n "user_version" src/          # expect: no output
```

### 3.2 The full store inventory — verified

| Store | Path resolution site | Root | Uses `migrations.py`? | Actual migration mechanism |
|---|---|---|---|---|
| `sessions.db` | `core/paths.py:41` | `state_dir` | **no** | ad-hoc `_migrate_schema` — `core/session_store.py:157-182` |
| `tui_state.db` | `core/paths.py:49` | `state_dir` | **no** | **none — nothing opens it** (§3.4) |
| `memory_index.db` | `core/paths.py:83` | `state_dir` | **no** | none — `CREATE ... IF NOT EXISTS` + full rebuild (§3.5) |
| `files.db` | `core/paths.py:93` | `state_dir` | **yes** | `core/files/store.py:407` |
| `runs.db` | `core/runtime/store.py:53` | **`data_dir`** | **yes** | `core/runtime/store.py:94` |
| `jobs.db` | `jobs/queue.py:582` | **`opengigantic` root** ([T-53](T-53-jobs-db-path-unification.md)) | **no** | ad-hoc — `jobs/queue.py:675-677` |

Two use the shared helper. Two hand-roll it. One has none. One does not exist.

The two ad-hoc blocks, verbatim:

`core/session_store.py:165-182` —

```python
        existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(sessions)")}
        ...
            self._conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
            self._conn.execute("ALTER TABLE sessions ADD COLUMN total_tokens INTEGER DEFAULT 0")
            self._conn.execute("ALTER TABLE sessions ADD COLUMN total_cost_usd REAL DEFAULT 0.0")
            self._conn.execute("ALTER TABLE sessions ADD COLUMN owner_token_hash TEXT")
        msg_existing = {row["name"] for row in self._conn.execute("PRAGMA table_info(messages)")}
            self._conn.execute("ALTER TABLE messages ADD COLUMN model TEXT")
```

`jobs/queue.py:675-677` —

```python
            cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "owner_id" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''")
```

Both are `apply_migrations` re-implemented inline. Neither records a version.

### 3.3 ⚠️ `core/migrations.py` has no version concept at all — the finding understates the work

The whole module is 57 lines. `apply_migrations` (`core/migrations.py:22-56`) takes a
`table` and a list of `(column, definition)` pairs and does exactly one thing —
`core/migrations.py:47-56`:

```python
    existing_cols: set[str] = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

    for column, definition in migrations:
        if column in existing_cols:
            continue
        sql = f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        logger.debug("apply_migrations: %s", sql)
        conn.execute(sql)
        conn.commit()
        existing_cols.add(column)
```

So: **additive column adds only.** No drops, no renames, no type changes, no table
creation, no ordering guarantees beyond list order, **and no notion of a version
number.** The module docstring is honest about this (`:3-5`): *"a safe, additive,
idempotent helper for adding new columns"*.

The review's phrasing — "add `schema_version` serviced by `migrations.py`" — therefore
describes a **new capability**, not a new caller. `apply_migrations` migrates the
columns of one table; `schema_version` records the state of a whole database. They are
complementary. You are extending the module, not just calling it more.

### 3.4 `tui_state.db` is a phantom — nothing opens it

```bash
rg -n "tui_state" --glob '!*.pyc' .
```

Every hit in `src/` is the property definition itself (`core/paths.py:48-49`). No
consumer anywhere. It is also already documented as dead:

- `docs/architecture/03-tech-debt.md:150` — *"**Dead `paths.tui_state_db`**
  (`paths.py:48`) — defined, zero consumers."*
- `docs/architecture/22-database-changes.md:44` — *"The dead `tui_state_db` …"*
- `README.md:621` still lists it in the directory tree as *"Textual UI state"* — a
  documented file that has never existed.

**So the real count is five live SQLite stores, not six.** §5 decides what to do with
the phantom.

### 3.5 `memory_index.db` is a derived cache, not a store of record

`MemoryIndex.refresh()` (`core/memory_index.py:92-151`) rebuilds the entire index from
`.og` files on disk — `:135-136`:

```python
            conn.execute("DELETE FROM mem_fts")
            conn.execute("DELETE FROM mem_nodes")
```

— then re-inserts everything parsed. Its schema is created with
`CREATE TABLE IF NOT EXISTS` / `CREATE VIRTUAL TABLE IF NOT EXISTS`
(`core/memory_index.py:25-41`) and never altered.

That makes it categorically different from the other four: **it can always be
regenerated**, so a version mismatch has a trivially correct remedy (delete and
rebuild) that does not exist for `sessions.db`. §5 uses that.

### 3.6 A second schema owner writes into `sessions.db`

`CorrectionLog` (`core/user_profile.py:105-133`) opens its **own** `sqlite3` connection
to `get_hachi_paths().sessions_db` (`:123`, `:127`) and creates a
`profile_corrections` table via `_ensure_table()` (`:135`), independently of
`SessionStore._migrate_schema`.

So `sessions.db` has two independent schema authors that do not know about each other.
Whoever owns the `schema_version` row for that file must account for both — a version
number written by `SessionStore` says nothing about whether `profile_corrections`
exists.

### 3.7 Non-SQLite stores, for completeness (not in scope, but do not forget they exist)

- `chroma_vault/` — ChromaDB, `data_dir` (`core/paths.py:44-45`); client at
  `core/memory_vault.py:537`.
- `chroma_vault/attachments/` — a **second** `PersistentClient` rooted inside the first
  client's directory: `tools/file_tools.py:267` and `core/runtime/job_handlers.py:405`.
- `og_skill_embeddings/` — a third `PersistentClient`, `state_dir`
  (`og_engine/engine.py:877-878`), opt-in embedding rank.
- `schedules.json` (`core/paths.py:52-53`), `skill_usage.json` (`:68-69`),
  `onboarding_state.json` (`:28-29`), `secrets_metadata.json` (`:64-65`),
  `checkpoints/` (`:56-57`), `blobs/` (`:86-88`), `memory/**/*.og` (`:76-78`).

ChromaDB manages its own schema and is out of scope. The JSON files are out of scope
for *this* task, but see §9.

## 4. Reproduce the failure

Fully reproducible by grep — the finding is an absence, and grep measures absences well.
**There is no runtime failure to trigger today; the cost is entirely future-tense, and
you should say so rather than inventing a crash.**

```bash
# 1. No SQLite versioning anywhere. Expect: only core/obs/envelope.py (a telemetry
#    wire field, unrelated) and its tests.
rg -n "schema_version" src/ tests/

# 2. The other conventional form. Expect: NO output.
rg -n "user_version" src/

# 3. Who uses the shared helper. Expect: files/store.py:407 and runtime/store.py:94.
rg -n "apply_migrations\(" src/

# 4. Who hand-rolls it instead. Expect: session_store.py and jobs/queue.py.
rg -n "PRAGMA table_info" src/

# 5. The phantom store. Expect: only the property definition in core/paths.py.
rg -n "tui_state" src/
```

**You will see now:** (1) five hits, all telemetry; (2) silence; (3) two callers;
(4) two hand-rolled blocks; (5) a path property with no consumer.

**You should see after the fix:** (2) or a new `schema_version` grep returns a hit per
live store; (3) shows every store going through `core/migrations.py`; (4) returns
nothing outside `core/migrations.py` itself.

Confirm the tables really are absent in a live database — read-only, against your own
`sessions.db`:

```bash
python -c "
import sqlite3
from hachi.core.paths import get_hachi_paths
p = get_hachi_paths().sessions_db
print('db:', p, '->', 'exists' if p.exists() else 'absent')
if p.exists():
    conn = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    print('tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])
    print('user_version:', conn.execute('PRAGMA user_version').fetchone()[0])
    conn.close()
"
```

**You will see now:** the table list contains `sessions`, `messages`,
`profile_corrections` and friends — **no `schema_version`** — and
`user_version: 0` (SQLite's default; nothing ever set it).

**You should see after the fix:** a `schema_version` table with one row.

## 5. What "fixed" looks like

Three decisions are made here by the task author.

### Decision 1 — a `schema_version` **table**, not `PRAGMA user_version`

*Why not the pragma:* it is a bare integer with no room for a timestamp or the app
version that wrote it, it is invisible to a `.dump`, and it is easy to clobber. A table
survives backup/restore visibly (which matters for
[T-55](T-55-backup-completeness.md)) and can be inspected with `sqlite3` by a user
debugging their own data — the "owned data" promise, applied to the metadata too.

Schema:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
    id             INTEGER PRIMARY KEY CHECK (id = 1),   -- exactly one row, ever
    version        INTEGER NOT NULL,
    app_version    TEXT    NOT NULL,                     -- hachi version that wrote it
    updated_at     TEXT    NOT NULL
);
```

The `CHECK (id = 1)` makes "exactly one row" a database-enforced invariant rather than a
convention.

### Decision 2 — every existing database is version **1**

An existing `sessions.db` in the wild has no version stamp, so the helper must *infer*
one. **Do not attempt schema archaeology** (probing for the presence of `owner_token_hash`
to distinguish generations). It is guesswork, it is untestable against real user data
you do not have, and the additive migrations already make every historical shape
forward-compatible.

Rule: **if the table is absent, stamp `version = 1` and proceed.** Version 1 means "the
schema as it existed when T-54 landed". Every future change increments from there.

Say this explicitly in the ADR — a future reader must not mistake `version = 1` for
"this database is pristine".

### Decision 3 — delete the `tui_state_db` phantom rather than version it

`core/paths.py:47-49` has no consumers (§3.4). Do **not** add a version table to a
database that is never opened. Delete the property, and fix the `README.md:621`
directory tree that documents it.

*If* deleting it turns out to break something (it should not — grep is unambiguous),
leave it and add a one-line comment saying it is reserved and unused. Do not create the
file just to version it.

### Target state

1. `core/migrations.py` gains two functions beside `apply_migrations`, keeping the
   module the single home for schema evolution:

   ```python
   SCHEMA_VERSION_TABLE = "schema_version"


   def ensure_schema_version(conn: sqlite3.Connection, *, current: int) -> int:
       """Create the schema_version table if absent and return the DB's version.

       An unstamped (pre-T-54) database is stamped as version 1 — "the schema as it
       existed when versioning was introduced" — NOT as `current`. See §5 Decision 2.

       Raises:
           SchemaTooNewError: when the stored version exceeds *current*, i.e. the
               database was written by a newer build of Hachi.
       """


   def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
       """Record *version* as the database's schema version. Call after a migration."""
   ```

   Plus a `SchemaTooNewError` in the same module (or `core/errors.py` if the taxonomy
   there fits — check `core/errors.py` before inventing a new exception).

2. **Fail loudly on a future version.** `ensure_schema_version` raises when
   `stored > current`. This is the single behaviour that justifies the whole task: a
   user who downgrades Hachi gets a clear error instead of a store being read with the
   wrong assumptions. Every store's `__init__` lets it propagate — do **not** catch it
   and continue.

3. Each live store calls `ensure_schema_version(conn, current=N)` in its schema-init
   path, immediately after `CREATE TABLE IF NOT EXISTS` and before any `apply_migrations`:

   | Store | Call site | Current version |
   |---|---|---|
   | `sessions.db` | `core/session_store.py:_migrate_schema` (`:157`) | 1 |
   | `files.db` | `core/files/store.py:__init__` (`:402-409`) | 1 |
   | `runs.db` | `core/runtime/store.py:_init_schema` (`:90-94`) | 1 |
   | `jobs.db` | `jobs/queue.py:_init_db` (around `:675`) | 1 |
   | `memory_index.db` | `core/memory_index.py:_init_db` (`:84-86`) | 1 — see item 4 |

4. **`memory_index.db` gets the "rebuild on mismatch" remedy**, not a hard failure.
   It is a derived cache (§3.5): on any version mismatch, drop the tables, re-create
   them, stamp the new version, and let the next `refresh()` repopulate from `.og`. This
   is strictly better than raising, and it is only safe *because* it is derived — do not
   generalise it to the other four.

5. **The two ad-hoc migration blocks migrate to `apply_migrations`**
   (`core/session_store.py:165-182`, `jobs/queue.py:675-677`). They are already the same
   algorithm; expressing them as `(column, definition)` lists removes two dialects and
   makes the version bump obvious the next time someone adds a column.

6. `docs/DECISIONS.md` gains an ADR: the table shape, the version-1 rule, the
   fail-on-newer policy, the cache exception for `memory_index.db`, and the retirement
   of `tui_state_db`.

## 6. Steps

1. Confirm [T-53](T-53-jobs-db-path-unification.md) has landed. If not, **stop** — you
   would stamp a version into a database that is about to move, and the migration in
   T-53 would carry a half-versioned file across roots.
2. Write the ADR in `docs/DECISIONS.md` (§5 item 6). It is the durable artefact.
3. Write the regression tests from §7 and watch them **fail**.
4. Add `SCHEMA_VERSION_TABLE`, `ensure_schema_version`, `set_schema_version` and
   `SchemaTooNewError` to `core/migrations.py`. **Do not change `apply_migrations`'s
   signature or behaviour** — it has two live callers and its own tests
   (`tests/test_migrations.py`).
5. Wire the five live stores (§5 item 3), one store per step, running
   `uv run pytest -q tests/test_migrations.py` after each.
6. Add the rebuild-on-mismatch path for `memory_index.db` (§5 item 4).
7. Convert `core/session_store.py:165-182` and `jobs/queue.py:675-677` to
   `apply_migrations` calls (§5 item 5). Preserve every existing comment
   ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
8. Delete `HachiPaths.tui_state_db` (`core/paths.py:47-49`), fix `README.md:621`, and
   strike the entry at `docs/architecture/03-tech-debt.md:150`.
9. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.
10. **Verify against a real, pre-existing database by hand** — see §10. No test covers
    a database written by an older build.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_migrations.py` (**existing** — extend it; it already owns this
  module's coverage)
- **Test names:** `test_every_live_sqlite_store_records_a_schema_version`,
  `test_unstamped_database_is_stamped_as_version_one`,
  `test_opening_a_future_version_database_raises`
- **It must assert:** the real, observed database contents — that a freshly constructed
  store has a `schema_version` row on disk, that a pre-existing unstamped DB gets
  version 1 (not the current version), and that a DB stamped with a higher version makes
  the store's constructor **raise**.
- **It must FAIL before your fix** with:
  - `ImportError: cannot import name 'ensure_schema_version' from 'hachi.core.migrations'`
  - and once the helper exists but a store is not wired,
    `AssertionError: sessions.db has no schema_version table`

```python
# tests/test_migrations.py — extend, matching the file's existing style
import sqlite3
from pathlib import Path

import pytest


def _tables(db: Path) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_every_live_sqlite_store_records_a_schema_version(tmp_path: Path) -> None:
    """Every SQLite store Hachi owns must stamp its schema version on creation.

    Regression (T-54): no schema_version table existed anywhere. Six stores held
    user data across two roots with no way to ask a database what shape it was in,
    so no non-additive migration was possible and a downgraded build would read a
    newer schema silently.
    """
    from hachi.core.files.store import FileMetaStore
    from hachi.core.runtime.store import RunStateStore
    from hachi.core.session_store import SessionStore
    from hachi.jobs.queue import SQLiteJobQueue

    built: dict[str, Path] = {}

    sessions = tmp_path / "sessions.db"
    store = SessionStore(db_path=str(sessions))
    store.shutdown()
    built["sessions.db"] = sessions

    files = tmp_path / "files.db"
    FileMetaStore(files)
    built["files.db"] = files

    runs = tmp_path / "runs.db"
    RunStateStore(db_path=runs)
    built["runs.db"] = runs

    jobs = tmp_path / "jobs.db"
    SQLiteJobQueue(db_path=jobs).shutdown()
    built["jobs.db"] = jobs

    for name, path in built.items():
        assert "schema_version" in _tables(path), f"{name} has no schema_version table"


def test_unstamped_database_is_stamped_as_version_one(tmp_path: Path) -> None:
    """A pre-T-54 database is version 1 — not the current version (§5 Decision 2)."""
    from hachi.core.migrations import ensure_schema_version

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
        conn.commit()
        assert ensure_schema_version(conn, current=7) == 1
    finally:
        conn.close()


def test_opening_a_future_version_database_raises(tmp_path: Path) -> None:
    """A database written by a NEWER build must fail loudly, not be read regardless."""
    from hachi.core.migrations import SchemaTooNewError, ensure_schema_version, set_schema_version

    db = tmp_path / "future.db"
    conn = sqlite3.connect(str(db))
    try:
        ensure_schema_version(conn, current=1)
        set_schema_version(conn, 99)
        with pytest.raises(SchemaTooNewError):
            ensure_schema_version(conn, current=1)
    finally:
        conn.close()


def test_memory_index_rebuilds_instead_of_raising_on_version_mismatch(tmp_path: Path) -> None:
    """memory_index.db is a derived cache: a mismatch rebuilds, it does not raise."""
    ...  # stamp a bogus version, construct MemoryIndex, assert it opened and refresh() works
```

Notes:

- `test_every_live_sqlite_store_records_a_schema_version` is the lock. Adding a sixth
  store later without a version stamp must break it — so build the list from real store
  constructors, not from a hardcoded list of filenames.
- `test_opening_a_future_version_database_raises` is the one that justifies the task.
  Keep it even if you restructure the others.
- None of these need chromadb. Keep it that way — §12 (BB-3).

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and `test_every_live_sqlite_store_records_a_schema_version` failed before the fix.
- [ ] All **five live** stores (`sessions.db`, `files.db`, `runs.db`, `jobs.db`, `memory_index.db`) create a `schema_version` table on first open.
- [ ] An unstamped pre-existing database is stamped **version 1**, not the current version.
- [ ] Opening a store whose stored version exceeds the build's `current` **raises** — verified for at least `sessions.db` and `runs.db`.
- [ ] `memory_index.db` rebuilds on mismatch rather than raising, and the rebuilt index returns the same search results.
- [ ] `rg -n "PRAGMA table_info" src/` returns hits only inside `core/migrations.py` — both ad-hoc blocks converted.
- [ ] `HachiPaths.tui_state_db` is gone; `README.md:621` and `docs/architecture/03-tech-debt.md:150` updated.
- [ ] An ADR in `docs/DECISIONS.md` records the table shape, the version-1 rule, the fail-on-newer policy, and the cache exception.
- [ ] **Verified by hand against a real pre-existing `sessions.db`** — it opened, stamped version 1, and existing sessions still list (§10).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not move `runs.db` to `state_dir`.** [T-53](T-53-jobs-db-path-unification.md)
  explicitly deferred that. Version it where it is; the inventory table in §3.2 records
  the anomaly.
- **Do not begin the storage consolidation.** CF-13's longer-term recommendation is one
  state SQLite + Chroma + blobs. That is ~2 weeks and needs its own ADR. This task makes
  consolidation *possible* by giving every store a version to migrate from; it does not
  start it.
- **Do not version the JSON files.** `schedules.json`, `skill_usage.json`,
  `onboarding_state.json`, `secrets_metadata.json` also have no version field. Real
  finding, different task, different mechanism.
- **Do not touch ChromaDB.** The three `PersistentClient` roots (§3.7) manage their own
  schema. Adding a Hachi version stamp beside them is meaningless.
- **Do not change `apply_migrations`'s signature or behaviour.** Two live callers and an
  existing test file depend on it. **Add** functions; do not refactor the one that works.
- **Do not attempt schema archaeology** to infer a "true" version for existing
  databases (§5 Decision 2). Stamp 1 and move on.
- **Do not add a rollback/downgrade path.** `apply_migrations` is additive-only by
  design and this task does not change that. Fail-on-newer is the whole downgrade story.
- **Do not create `tui_state.db`** in order to have something to version (§5 Decision 3).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. `sqlite3` is stdlib; no migration
  framework (alembic, yoyo) is warranted for five tables of additive columns — and
  adding one would need a decision, not a commit.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** You are adding code to the constructor of
every SQLite store in the product. `SessionStore` is built by the gateway, the CLI, the
eval harness and dozens of tests; `SQLiteJobQueue` is constructed once per agent
(`gateway/orchestrator.py:2586`). A `SchemaTooNewError` that escapes where it should not
— or an `ensure_schema_version` that forgets to commit — will surface as unrelated
failures across the suite.

**Then verify by hand, because no test covers a real legacy database.** Back up your own
`sessions.db` first, then:

```bash
python -c "
import shutil
from hachi.core.paths import get_hachi_paths
p = get_hachi_paths().sessions_db
shutil.copy2(p, str(p) + '.pre-t54')
print('backed up ->', str(p) + '.pre-t54')
"
hachi session list          # opens the real store; must succeed and list your sessions
python -c "
import sqlite3
from hachi.core.paths import get_hachi_paths
conn = sqlite3.connect(f'file:{get_hachi_paths().sessions_db}?mode=ro', uri=True)
print(conn.execute('SELECT * FROM schema_version').fetchall())
"
```

Expect one row at version 1, and your existing sessions still listed.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — No SQLite store recorded a schema version; every migration had to be additive forever

- **Symptom:** No latent runtime failure, but no database in Hachi could answer "what
  shape am I?". A downgraded build would open a newer schema and read it silently with
  the wrong assumptions, and no non-additive migration (rename, retype, split) had any
  safe path.
- **Root cause:** No `schema_version` table or `PRAGMA user_version` existed anywhere —
  the only repo hits for the string were the unrelated obs telemetry envelope
  (`core/obs/envelope.py:88`). `core/migrations.py` provided `apply_migrations`, which
  does `ALTER TABLE ... ADD COLUMN` only and has **no version concept**; only 2 of the 5
  live stores called it, while `sessions.db` and `jobs.db` hand-rolled the same
  `PRAGMA table_info` + `ALTER` algorithm inline and `memory_index.db` had no migration
  path at all. A sixth declared store, `tui_state.db`, had zero consumers.
- **Fix:** Added `ensure_schema_version` / `set_schema_version` / `SchemaTooNewError` to
  `core/migrations.py`, backed by a one-row `schema_version` table. Every live store
  stamps on open; an unstamped legacy DB is stamped version 1; a stored version higher
  than the build's raises. `memory_index.db` — a derived cache rebuilt from `.og` —
  rebuilds on mismatch instead. Both ad-hoc migration blocks converted to
  `apply_migrations`; the dead `tui_state_db` property removed.
- **Avoid:** stamp a version into a store the day you create it. Retrofitting versions
  onto databases already in users' hands means guessing what they contain — the only
  honest answer is "version 1, meaning whatever shipped before we started counting".
- **Locked by:** `tests/test_migrations.py` — `test_every_live_sqlite_store_records_a_schema_version`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Nothing here needs
  chromadb, but the suite runs in one process and `conftest.py`'s warm-up must stay
  intact. Do not add module patching to these tests.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Store constructors
  run during boot; `ensure_schema_version` must depend on nothing but its connection.
- **`sessions.db` has two independent schema owners** (§3.6): `SessionStore` and
  `CorrectionLog` (`core/user_profile.py:105-133`), which opens its own connection and
  creates `profile_corrections`. Decide explicitly who owns the version row — the
  answer is `SessionStore`, and `CorrectionLog`'s table must be folded into that
  version's definition, or its `_ensure_table()` will keep creating tables behind the
  version's back.
- **`log_message` defers its COMMIT** (`core/session_store.py:638-644`). If
  `ensure_schema_version` writes without committing, a crash before the next batch flush
  loses the stamp and the DB looks unstamped again. Commit the stamp explicitly —
  `apply_migrations` already commits per ALTER (`core/migrations.py:55`); follow that.
- **`FileMetaStore` opens a fresh connection per operation** (`core/files/store.py:411-414`)
  and closes it in `__init__` (`:409`). Your version check must happen on the same
  connection as the `CREATE TABLE`, inside that `try/finally`.
- **`SQLiteJobQueue` holds one persistent connection** (`jobs/queue.py:621`) guarded by
  an `RLock` (`:620`), and `_conn()` (`:653-662`) is re-entrant. Do not open a second
  connection for the version check — reuse `self._db_conn`.
- **`RunStateStore._init_schema` runs inside `self._lock`** (`core/runtime/store.py:90-94`).
  Put the version call inside the same block; do not add a second lock acquisition.
- **A raising constructor is a boot failure.** `SchemaTooNewError` is the point of the
  task, but it must produce an actionable message — which file, which version it found,
  which version this build supports, and that the fix is to upgrade Hachi (or restore a
  backup). A bare exception class name in a stack trace is not enough for a user whose
  agent will not start.
- **`memory_index.db` is the only store where deleting the data is correct.** Do not
  let that reasoning leak into the others by copy-paste; put the rebuild logic in
  `MemoryIndex`, not in `core/migrations.py`.
