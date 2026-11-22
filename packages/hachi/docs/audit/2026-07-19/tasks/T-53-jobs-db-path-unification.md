# T-53 · Move `jobs.db` onto the canonical path root (with a move-if-exists migration)

|  |  |
|---|---|
| **Source finding** | CF-13 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) ("do now — the cheapest storage fix") |
| **Severity** | **P1** — real data-visibility bug; the review recommends doing it immediately |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-54](T-54-schema-version-tables.md), [T-55](T-55-backup-completeness.md) — both need `jobs.db` at its final path first |
| **Effort** | ~1 day |
| **Difficulty** | Medium — the path change is four lines; **the migration is the risk** |
| **Files you will touch** | `src/hachi/core/paths.py`, `src/hachi/jobs/queue.py`, `src/hachi/cli/commands/jobs.py`, `tests/test_p1_09_paths.py`, `tests/test_jobs_db_path_migration.py` (new), `docs/DECISIONS.md`, `docs/architecture/03-tech-debt.md`, `docs/bug-bank.md` |

---

## 1. Brief

`jobs.db` resolves under `PlatformDirs("hachi", "opengigantic")` while every other
Hachi path resolves under `PlatformDirs(appname="hachi", appauthor=False)`. On Windows
those are **two different directories**, and the `opengigantic` one contains exactly
one file: `jobs.db`. Nothing built on `get_hachi_paths()` — backup, restore, doctor, any
future export — can see it, because `HachiPaths` has no `jobs_db` property at all.

When you are done, `jobs.db` lives beside its siblings under the canonical root, is
reachable as `get_hachi_paths().jobs_db`, and an existing user's queued jobs have been
moved rather than orphaned.

## 2. Why this matters

This is the cheapest fix in the storage group and it is not cosmetic. `jobs.db` holds
the durable job queue — the dead-letter queue, retry-exhausted handler jobs awaiting
`hachi jobs redrive`, and pending fact-extraction work. It is the one store whose
contents a user might actually need to recover, and it is the one store no recovery
tool can find.

It also silently corrupts every claim built on `get_hachi_paths()`. `hachi doctor`
reports `state_dir_exists: true` and never looks at the other root.
[T-55](T-55-backup-completeness.md) will make `hachi backup` enumerate the stores — and
if it enumerates from `HachiPaths`, `jobs.db` is still invisible. That is why this task
gates the other two.

If the fix you are about to write leaves a user's existing queued jobs behind in the
old directory, stop and re-read §5.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 THREE `PlatformDirs` sites, not two — the audit missed the third

`rg -n "PlatformDirs" src/` returns exactly these:

**(1) The canonical root — `src/hachi/core/paths.py:117-124`:**

```python
def get_hachi_paths() -> HachiPaths:
    dirs = PlatformDirs(appname=APP_NAME, appauthor=False, ensure_exists=False)
    return HachiPaths(
        config_dir=Path(dirs.user_config_path),
        data_dir=Path(dirs.user_data_path),
        cache_dir=Path(dirs.user_cache_path),
        state_dir=Path(dirs.user_state_path),
    )
```

**(2) The job queue's own resolution — `src/hachi/jobs/queue.py:576-582`:**

```python
def _default_db_path() -> Path:
    from platformdirs import PlatformDirs

    dirs = PlatformDirs("hachi", "opengigantic")
    state_dir = Path(dirs.user_state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "jobs.db"
```

Note `:581` — this function **creates** the directory as a side effect. That is why the
orphan root exists on every machine that has ever booted a session.

**(3) ⚠️ The one the audit missed — `src/hachi/cli/commands/jobs.py:16-27`:**

```python
def _open_queue():  # type: ignore[return]
    """Open the default SQLiteJobQueue using standard platform paths."""
    from pathlib import Path

    from platformdirs import PlatformDirs

    from hachi.jobs.queue import SQLiteJobQueue

    # The queue DB lives under the user state dir (not the config dir).
    dirs = PlatformDirs("hachi", "opengigantic")
    db_path = Path(dirs.user_state_dir) / "jobs.db"
    return SQLiteJobQueue(db_path=db_path)
```

The resolution is **duplicated inline** rather than calling `_default_db_path()`. This
is the single most important fact in this spec — see §5's trap.

### 3.2 The two roots, on disk, right now

Verified on a real Windows machine:

```
%LOCALAPPDATA%\hachi\                       ← canonical (get_hachi_paths)
    .env                 blobs\             brain.og            checkpoints\
    chroma_vault\        device-permissions.og                  files.db
    gateway.log          og_skill_embeddings\                   onboarding_state.json
    runs.db              schedules.json     secrets_metadata.json
    sessions.db          settings.toml      skill_usage.json    skills\

%LOCALAPPDATA%\opengigantic\hachi\          ← the orphan root
    jobs.db                                 ← the ONLY file here
```

One directory tree exists solely to hold one database.

### 3.3 `HachiPaths` has no `jobs_db` property

`src/hachi/core/paths.py:12-114` declares properties for `global_config_toml`,
`permissions_file`, `onboarding_state_file`, `skills_dir`, `brain_file`, `sessions_db`
(`:40`), `chroma_dir` (`:44`), `tui_state_db` (`:48`), `schedules_file` (`:52`),
`checkpoints_dir` (`:56`), `secrets_fallback_file` (`:60`), `secrets_metadata_file`
(`:64`), `skill_usage_json` (`:68`), `user_roles_dir` (`:72`), `memory_dir` (`:76`),
`memory_index_db` (`:81`), `blobs_dir` (`:86`), `files_db` (`:91`).

**No `jobs_db`.** Any tool that enumerates stores from `HachiPaths` cannot include it
even in principle.

### 3.4 Only two construction sites — the blast radius is small

```bash
rg -n "SQLiteJobQueue\(" src/
# src/hachi/cli/commands/jobs.py:27       return SQLiteJobQueue(db_path=db_path)
# src/hachi/gateway/orchestrator.py:2586  job_queue: JobQueue = SQLiteJobQueue()
```

`SQLiteJobQueue.__init__` (`jobs/queue.py:613-614`):

```python
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _default_db_path()
```

So the gateway takes the default; the CLI overrides it with its own duplicate
resolution. **Both must change together.**

### 3.5 `runs.db` is the other outlier — `core/runtime/store.py:48-53`

```python
def _default_db_path() -> Path:
    from hachi.core.paths import get_hachi_paths

    paths = get_hachi_paths()
    data_dir: Path = paths.data_dir
    return data_dir / "runs.db"
```

This one *does* use `get_hachi_paths()` — it is on the canonical root — but resolves
under **`data_dir`** while every sibling SQLite store uses `state_dir`
(`sessions.db:41`, `tui_state.db:49`, `memory_index.db:83`, `files.db:93`).

On Windows this is invisible: `user_data_path` and `user_state_path` both map to
`%LOCALAPPDATA%\hachi`, which is why the listing in §3.2 shows `runs.db` and
`sessions.db` side by side. **On Linux they are different directories** (XDG separates
`~/.local/share` from `~/.local/state`), so the split is real for POSIX users. Verify
on your own platform before deciding — §5 makes the call.

### 3.6 The precedent — `tests/test_p1_09_paths.py`

A prior initiative ("P1-09: Path unification") already did exactly this job for
`skill_usage.json` and the roles directory, and left a test file documenting the
invariant. Its module docstring (`:1-7`):

```
P1-09: Path unification — skill-usage DB and RoleResolver use platformdirs.

Invariants:
  1. Fresh env: SkillEngine._usage_path is under get_hachi_paths().state_dir.
  2. RoleResolver: _roles_dir is under get_hachi_paths().data_dir.
  3. RoleResolver legacy shim: an existing ~/.hachi/skills/roles/ dir is checked as fallback.
```

`jobs.db` was missed by that sweep. **Extend that file rather than starting a new
convention** — its `_mock_paths(tmp_path)` helper (`:18-24`) and
`monkeypatch.setattr(module, "get_hachi_paths", ...)` pattern are exactly what you need.

### 3.7 Docs that assert the current (wrong) path

- `docs/DECISIONS.md:1422` — *"Opens the production `SQLiteJobQueue` via
  `PlatformDirs("hachi", "opengigantic")` / `jobs.db`."*
- `docs/architecture/03-tech-debt.md:147` — already flags it as a
  *"Possible `jobs.db` path inconsistency"*. It has been known and unfixed.

Both need updating; the tech-debt entry can be struck.

## 4. Reproduce the failure

Fully reproducible, read-only, decisive.

```bash
# 1. The three PlatformDirs sites. Expect: paths.py:118 (canonical), queue.py:579
#    and cli/commands/jobs.py:25 (both "opengigantic").
rg -n "PlatformDirs" src/

# 2. The two roots resolve differently.
python -c "
from platformdirs import PlatformDirs
canonical = PlatformDirs(appname='hachi', appauthor=False, ensure_exists=False)
jobs = PlatformDirs('hachi', 'opengigantic')
print('canonical state_dir:', canonical.user_state_path)
print('jobs.db  state_dir:', jobs.user_state_dir)
print('same root?         :', str(canonical.user_state_path) == str(jobs.user_state_dir))
"

# 3. HachiPaths cannot even name the file. Expect: NO output.
rg -n "jobs_db" src/hachi/core/paths.py
```

**You will see now:**

```
canonical state_dir: C:\Users\<you>\AppData\Local\hachi
jobs.db  state_dir: C:\Users\<you>\AppData\Local\opengigantic\hachi
same root?         : False
```

and silence from grep (3) — `HachiPaths` has no `jobs_db` property.

**You should see after the fix:** both lines print the same directory (or grep (1)
returns a single `PlatformDirs` site — the canonical one), and grep (3) returns the new
property.

**See the orphan directory for yourself** (read-only):

```bash
python -c "
import pathlib
from platformdirs import PlatformDirs
d = pathlib.Path(PlatformDirs('hachi', 'opengigantic').user_state_dir)
print(d, '->', 'EXISTS' if d.exists() else 'absent')
print('contents:', [p.name for p in d.iterdir()] if d.exists() else [])
"
```

**You will see now:** the directory exists and contains `['jobs.db']` and nothing else.
**You should see after the fix (and one boot):** `jobs.db` gone from that directory,
present under the canonical `state_dir`.

## 5. What "fixed" looks like

> ### ⚠️ TRAP #1 — A PARTIAL FIX SPLITS THE JOBS DB IN TWO
>
> `jobs/queue.py:582` and `cli/commands/jobs.py:26` **both** resolve `jobs.db`, and they
> resolve it independently. Change one and you get two live job databases: the gateway
> writing to the new path while `hachi jobs dead-letter` / `hachi jobs redrive` read the
> old one — silently reporting an empty queue while jobs pile up unseen.
>
> That is strictly worse than today's single misplaced file, because today at least both
> agree.
>
> **Both sites change together, in the same commit.** Verify with
> `rg -n "jobs.db" src/` before you push — every hit must resolve through
> `get_hachi_paths()`.

> ### DECISION REQUIRED — does `runs.db` move too?
>
> **Recommendation: NO — defer it, explicitly.** Add a comment at
> `core/runtime/store.py:52-53` recording that `runs.db` is knowingly under `data_dir`
> while its siblings are under `state_dir`, and that unifying it is deferred.
>
> *Why defer:* `runs.db` is already on the canonical root, so it is **visible** to
> `get_hachi_paths()`-based tooling — the actual bug this task fixes does not apply to
> it. Moving it needs its own migration, on Linux it is a genuine relocation, and
> bundling it doubles the migration surface of a task whose whole value is being small
> and safe. [T-55](T-55-backup-completeness.md) will back it up correctly wherever it
> lives.
>
> If you disagree and move it, do it as a **separate commit** with its own migration and
> its own test, and update [T-54](T-54-schema-version-tables.md)'s inventory table.

### Target state

1. `HachiPaths` gains the missing property, beside `files_db` (`core/paths.py:90-93`):

   ```python
    @property
    def jobs_db(self) -> Path:
        """SQLite database for the durable background job queue."""
        return self.state_dir / "jobs.db"
   ```

2. `jobs/queue.py:576-582` resolves through the canonical helper and performs the
   migration:

   ```python
   def _default_db_path() -> Path:
       """Canonical jobs.db path, migrating from the legacy opengigantic root once.

       Before T-53 this resolved under PlatformDirs("hachi", "opengigantic") — a
       second on-disk root invisible to get_hachi_paths()-based tooling (backup,
       doctor, export). Existing users' queued jobs are moved on first access.
       """
       from hachi.core.paths import get_hachi_paths

       target = get_hachi_paths().jobs_db
       target.parent.mkdir(parents=True, exist_ok=True)
       _migrate_legacy_jobs_db(target)
       return target
   ```

3. `cli/commands/jobs.py:16-27` **calls `_default_db_path()`** instead of duplicating
   the resolution:

   ```python
   def _open_queue():  # type: ignore[return]
       """Open the default SQLiteJobQueue using standard platform paths."""
       from hachi.jobs.queue import SQLiteJobQueue

       return SQLiteJobQueue()
   ```

   Passing no `db_path` makes `SQLiteJobQueue.__init__` (`queue.py:614`) use
   `_default_db_path()` — one resolution, one place, structurally impossible to
   diverge again. Keep the existing comment about the state dir; move it onto
   `_default_db_path`'s docstring.

4. A migration helper, `_migrate_legacy_jobs_db(target)`, with these exact semantics:

   - **No-op if `target` already exists.** Never overwrite a live DB.
   - **No-op if the legacy file does not exist.** Fresh installs pay nothing.
   - Otherwise **move** `jobs.db` and its WAL sidecars — `jobs.db-wal`, `jobs.db-shm` —
     from the legacy root to `target`. WAL mode is enabled at `queue.py:630`, so the
     sidecars can hold committed data. Moving the `.db` alone can lose or corrupt it.
   - Use `shutil.move` (works across volumes; `Path.rename` does not) and swallow
     nothing silently: on failure, log at **WARNING** with both paths and fall back to
     the target (a fresh empty DB) rather than raising — a boot must not die because a
     migration failed. But it must be *visible*, not `logger.debug`.
   - Leave the empty legacy directory behind. Removing directories at boot is a
     footgun for a marginal tidiness gain.
   - **Idempotent and safe under concurrent boots.** The gateway constructs
     `SQLiteJobQueue()` per agent (`orchestrator.py:2586`) and a CLI invocation can race
     it. The `target.exists()` guard is the interlock; make sure the move is the last
     step so a partially-moved state cannot pass it.

5. `docs/DECISIONS.md:1422` and `docs/architecture/03-tech-debt.md:147` updated.

## 6. Steps

1. Write the regression tests from §7 and watch them **fail**.
2. Add the `jobs_db` property to `HachiPaths` (`core/paths.py`), beside `files_db`.
3. Write `_migrate_legacy_jobs_db(target)` in `jobs/queue.py` per §5 item 4, with the
   legacy root resolved by `PlatformDirs("hachi", "opengigantic")` — **that call stays**,
   inside the migration helper only, as the definition of "where the old file was".
4. Rewrite `_default_db_path()` (`jobs/queue.py:576-582`) per §5 item 2.
5. Rewrite `_open_queue()` (`cli/commands/jobs.py:16-27`) per §5 item 3. **Same commit
   as step 4** — Trap #1.
6. `rg -n "PlatformDirs" src/` — expect exactly two hits: `core/paths.py:118` and the
   one inside the migration helper. If `cli/commands/jobs.py` still appears, you have
   the split-database bug.
7. Extend `tests/test_p1_09_paths.py` with a `jobs.db` invariant (§7 test 1), matching
   the file's existing style.
8. Run the regression tests — they must now pass.
9. Update the two docs (§5 item 5).
10. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Two files: the path invariant belongs with its siblings, the migration needs its own.

- **File 1:** `tests/test_p1_09_paths.py` (**existing** — extend it)
- **Test name:** `test_jobs_db_uses_platformdirs_state_dir`
- **File 2:** `tests/test_jobs_db_path_migration.py` (**new**)
- **Test names:** `test_legacy_jobs_db_is_moved_to_the_canonical_path`,
  `test_migration_never_overwrites_an_existing_target`,
  `test_cli_and_gateway_resolve_the_same_jobs_db`
- **It must assert:** the real, observed file locations — that the DB is created under
  `get_hachi_paths().state_dir`, that a seeded legacy file (with its WAL sidecars) ends
  up at the new path with its **rows intact**, and that the CLI's `_open_queue()` and a
  bare `SQLiteJobQueue()` produce the **same** `_db_path`.
- **It must FAIL before your fix** with:
  - test 1: `AttributeError: 'HachiPaths' object has no attribute 'jobs_db'`
  - the CLI/gateway agreement test: `AssertionError: ...\opengigantic\hachi\jobs.db != ...\hachi\jobs.db`
    — and note this one **also fails on a partial fix**, which is exactly its job.

```python
# tests/test_p1_09_paths.py — extend, matching the file's existing _mock_paths style
def test_jobs_db_uses_platformdirs_state_dir(tmp_path, monkeypatch):
    """jobs.db resolves to state_dir/jobs.db on the canonical root (T-53)."""
    import hachi.jobs.queue as queue_mod

    mock_paths = _mock_paths(tmp_path)
    mock_paths.state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(queue_mod, "get_hachi_paths", lambda: mock_paths, raising=False)

    assert queue_mod._default_db_path() == mock_paths.state_dir / "jobs.db"
```

```python
# tests/test_jobs_db_path_migration.py — new
import sqlite3
from pathlib import Path

import pytest

from hachi.core.paths import HachiPaths


def _mock_paths(tmp_path: Path) -> HachiPaths:
    return HachiPaths(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )


def _seed_legacy_db(path: Path) -> None:
    """Write a legacy jobs.db with one recoverable row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO jobs VALUES ('legacy-1', 'fact_extraction')")
        conn.commit()
    finally:
        conn.close()


def test_legacy_jobs_db_is_moved_to_the_canonical_path(tmp_path, monkeypatch):
    """An existing user's queued jobs move to the new path — they are not orphaned.

    Regression (T-53): jobs.db resolved under PlatformDirs("hachi", "opengigantic"),
    a second on-disk root invisible to every get_hachi_paths()-based tool. Pointing
    it at state_dir without a migration would strand every user's dead-letter queue.
    """
    import hachi.jobs.queue as queue_mod

    mock_paths = _mock_paths(tmp_path)
    legacy = tmp_path / "legacy" / "jobs.db"
    _seed_legacy_db(legacy)

    monkeypatch.setattr(queue_mod, "get_hachi_paths", lambda: mock_paths, raising=False)
    monkeypatch.setattr(queue_mod, "_legacy_jobs_db_path", lambda: legacy, raising=False)

    resolved = queue_mod._default_db_path()

    assert resolved == mock_paths.state_dir / "jobs.db"
    assert resolved.exists(), "jobs.db was not migrated"
    assert not legacy.exists(), "legacy jobs.db was left behind"

    conn = sqlite3.connect(str(resolved))
    try:
        rows = conn.execute("SELECT job_id FROM jobs").fetchall()
    finally:
        conn.close()
    assert ("legacy-1",) in rows, "migrated DB lost its rows"


def test_migration_never_overwrites_an_existing_target(tmp_path, monkeypatch):
    """If a jobs.db already exists at the new path, the legacy file must not clobber it."""
    ...  # seed BOTH, assert the target's own row survives and the legacy file is untouched


def test_cli_and_gateway_resolve_the_same_jobs_db(tmp_path, monkeypatch):
    """The CLI and the gateway must never open two different job databases.

    Guards the partial-fix failure mode: changing jobs/queue.py without
    cli/commands/jobs.py splits the queue in two, and `hachi jobs dead-letter`
    silently reports an empty queue while jobs accumulate elsewhere.
    """
    from hachi.cli.commands.jobs import _open_queue
    from hachi.jobs.queue import SQLiteJobQueue

    ...  # point get_hachi_paths at tmp_path in BOTH modules, then:
    assert _open_queue()._db_path == SQLiteJobQueue()._db_path
```

Notes:

- Factor the legacy location into a tiny `_legacy_jobs_db_path()` helper so the test can
  monkeypatch it. Do **not** let the migration test write to the developer's real
  `%LOCALAPPDATA%\opengigantic\hachi\` — that is their actual job queue.
- `test_cli_and_gateway_resolve_the_same_jobs_db` is the one that catches Trap #1. Keep
  it even if you restructure the others.
- Add a WAL-sidecar case: seed `jobs.db-wal` alongside and assert it moved too.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and `test_jobs_db_uses_platformdirs_state_dir` failed before the fix with `AttributeError: ... no attribute 'jobs_db'`.
- [ ] `rg -n "PlatformDirs" src/` returns exactly **two** hits: `core/paths.py` and the migration helper in `jobs/queue.py`. **`cli/commands/jobs.py` must not appear.**
- [ ] `get_hachi_paths().jobs_db` exists and equals `state_dir / "jobs.db"`.
- [ ] `_open_queue()` and a bare `SQLiteJobQueue()` resolve to the identical path (test 3).
- [ ] The migration moves `jobs.db` **and** `jobs.db-wal` / `jobs.db-shm`, preserves rows, never overwrites an existing target, and logs at WARNING (not DEBUG) on failure.
- [ ] Verified by hand on a machine with a real legacy `jobs.db`: after one boot the file is under the canonical `state_dir`, `hachi jobs dead-letter` still works, and the legacy directory is empty.
- [ ] `docs/DECISIONS.md:1422` and `docs/architecture/03-tech-debt.md:147` updated.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not move `runs.db`.** §5's decision. It is already on the canonical root, so it
  is not affected by the bug being fixed here. If you move it, it is a separate commit
  with its own migration and test — and it changes
  [T-54](T-54-schema-version-tables.md)'s inventory table.
- **Do not add `schema_version` to `jobs.db` while you are here.** That is
  [T-54](T-54-schema-version-tables.md), and it is explicitly sequenced **after** this
  task so it runs against the final path. Adding it now means adding it twice.
- **Do not extend `hachi backup` to include `jobs.db`.** That is
  [T-55](T-55-backup-completeness.md), which depends on this landing first. Very
  tempting once you add the `jobs_db` property — resist.
- **Do not delete the legacy directory.** Leave the empty folder. Removing directories
  during boot is a footgun with no upside.
- **Do not "tidy" the other paths.** `chroma_dir`, `memory_dir` and `blobs_dir` are
  under `data_dir` by design (they are data, not state). Do not sweep them.
- **Do not change `SQLiteJobQueue`'s schema, WAL settings, or `_recover_running`
  behaviour.** This task moves a file. Nothing else.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. `shutil` is stdlib; `platformdirs` is
  already a dependency.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** Every gateway-booting test constructs
`SQLiteJobQueue()` (`gateway/orchestrator.py:2586`), so the migration helper runs on
each one. A migration that raises, or that races two concurrent boots, will surface as
an unrelated-looking failure somewhere else in the suite —
`tests/test_job_queue.py`, `tests/test_p2_02_job_queue.py`,
`tests/test_job_dead_letter.py` and `tests/test_retention_sweep.py` all construct
queues with explicit `tmp_path` DBs and will *not* catch it.

**Then verify by hand on a real machine**, because no test covers the real legacy root:
check the orphan directory before and after one `hachi run` boot, and confirm
`hachi jobs dead-letter` still reads the queue.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `jobs.db` lived on a second platformdirs root, invisible to every path-based tool

- **Symptom:** `jobs.db` resolved under `%LOCALAPPDATA%\opengigantic\hachi\` while every
  other Hachi file lived under `%LOCALAPPDATA%\hachi\`. The orphan directory existed on
  every machine and contained exactly one file. Nothing built on `get_hachi_paths()` —
  `hachi backup`, `hachi restore`, `hachi doctor` — could see the durable job queue,
  including its dead-letter contents.
- **Root cause:** `jobs/queue.py::_default_db_path()` called
  `PlatformDirs("hachi", "opengigantic")` (and created the directory as a side effect)
  while `core/paths.py::get_hachi_paths()` used
  `PlatformDirs(appname="hachi", appauthor=False)`. `HachiPaths` had no `jobs_db`
  property at all, so the file could not even be named by the canonical API. The
  resolution was **duplicated inline** a third time in
  `cli/commands/jobs.py::_open_queue()`.
- **Fix:** Added `HachiPaths.jobs_db` (`state_dir / "jobs.db"`); pointed
  `_default_db_path()` at it with a move-if-exists migration that relocates the legacy
  DB and its WAL sidecars once, never overwriting an existing target; deleted the
  duplicated resolution in the CLI so both entry points share one code path.
- **Avoid:** resolve every user-data path through `get_hachi_paths()` — never construct
  `PlatformDirs` outside `core/paths.py`. And when two entry points resolve the same
  file independently, changing one of them splits the store: fix both in the same
  commit and pin it with a test that asserts they agree.
- **Locked by:** `tests/test_jobs_db_path_migration.py` — `test_cli_and_gateway_resolve_the_same_jobs_db`
```

## 12. Known traps

- **⚠️ Trap #1 — the split database.** Restated because it is the one that ships a worse
  bug than the one you are fixing: `jobs/queue.py:582` and `cli/commands/jobs.py:26`
  must change together. `hachi jobs dead-letter` reading a different DB than the gateway
  writes is silent — it reports an empty queue, which looks like good news.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Nothing here needs
  chromadb, but the full suite runs in one process and the warm-up in `conftest.py` must
  stay intact — do not add module patching to the tests you write.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir`. Do not invent
  new `HachiPaths` properties beyond `jobs_db`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. `_default_db_path`
  is called during boot; it must depend on nothing but `get_hachi_paths()`.
- **WAL sidecars carry committed data.** `SQLiteJobQueue` sets `PRAGMA journal_mode=WAL`
  (`jobs/queue.py:630`) and `synchronous=NORMAL` (`:634`). Moving `jobs.db` without
  `jobs.db-wal` can silently drop recent commits. Move all three; assert on it.
- **`shutil.move`, not `Path.rename`.** The legacy and canonical roots can be on
  different volumes on some Windows setups; `rename` raises `OSError` across devices.
- **The migration runs on every boot and every CLI invocation.** Keep it to two
  `exists()` checks in the common case. Do not add a version file, a marker, or a
  database read — the target's existence *is* the marker.
- **`_default_db_path` creates a directory today** (`jobs/queue.py:581`). Preserve that:
  `SQLiteJobQueue.__init__` (`:613-621`) opens the connection immediately and will fail
  if the parent does not exist.
- **`import-linter` layering:** `hachi.jobs` may not import `hachi.cli`, `hachi.tui` or
  `hachi.gateway` (`pyproject.toml:198-205`, `:216-222`). Importing
  `hachi.core.paths` from `hachi.jobs.queue` is `jobs → core`, which is allowed. Do not
  invert it by putting job-queue knowledge into `core/paths.py` beyond the one property.
