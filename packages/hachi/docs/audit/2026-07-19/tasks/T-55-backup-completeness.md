# T-55 · `hachi backup` silently omits most of the user's data — including the entire `.og` memory graph

|  |  |
|---|---|
| **Source finding** | **NEW — not in [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md).** Adjacent to CF-13, which frames this as storage sprawl; it is worse than that. |
| **Severity** | **P1 — DATA LOSS** |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | **[T-53](T-53-jobs-db-path-unification.md)** (mandatory — `jobs.db` is unreachable from `get_hachi_paths()` until it lands) · [T-54](T-54-schema-version-tables.md) (preferred — so a backup records store versions) |
| **Blocks** | nothing |
| **Effort** | ~2 days |
| **Difficulty** | Medium — the enumeration is easy; making it impossible to forget the *next* store is the design work |
| **Files you will touch** | `src/hachi/core/paths.py`, `src/hachi/cli/main.py`, `tests/test_backup_restore.py`, `docs/bug-bank.md` |

---

## 1. Brief

**`hachi backup` copies four things and reports success. A user who backs up, wipes,
and restores loses their skills, their file attachments, their run state, their job
queue, their checkpoints, their schedules — and, on the `fts5_only` memory backend,
their entire memory.** Under that backend the `.og` files in `data_dir/memory/` are the
*canonical* fact store; `hachi backup` does not copy them, so the restore produces an
agent that remembers nothing. Nothing warns. The command prints a green "Backup
created" panel listing what it did copy, which reads as a complete inventory.

`hachi doctor` is equally blind: it checks that four directories exist and never probes
a single database.

When you are done, backup and restore enumerate every store from **one source of truth**
— so a store added tomorrow cannot be silently forgotten — and a full round trip
(backup → wipe → restore) is asserted by a test.

## 2. Why this matters

This is not sprawl and it is not hygiene. It is a backup command that loses data while
reporting success, in a product whose central promise is *portable, owned data*. Every
other finding in this audit costs the user features; this one costs them their history.

The `fts5_only` case is the sharpest, because it is not a degraded mode — it is a
supported, documented backend (`MemoryBackend = Literal["chroma", "in_memory",
"fts5_only"]`, `core/settings.py:77`) selected by users who do not want ChromaDB. For
them `chroma_vault/` is empty or absent and `data_dir/memory/**/*.og` holds everything
the agent knows. `hachi backup` copies the empty vault and skips the real one.

Even on the default backend, the omissions include `skills_dir` — the user's authored
`.og` skills — which is the artefact the entire product positions as the moat.

If the fix you are about to write leaves any store enumerated in a second place, stop
and re-read §5: a list that can drift is how this happened.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 `hachi backup` copies exactly four things — `cli/main.py:5317-5417`

`@app.command("backup")` at `:5317`, `def backup` at `:5318`. Its docstring, `:5329-5340`:

```python
    """Create a timestamped backup of session history and the memory vault.

    Backs up (1) the sessions SQLite database via an online hot-backup, (2) the
    ChromaDB memory-vault directory via a directory copy, and (3) the config-dir
    files ``settings.toml`` and ``device-permissions.og`` (non-secret config only).
    ...
    """
```

The body does precisely that and nothing more:

- `:5365-5379` — `sessions.db` via `SessionStore.backup()` (a real online hot-backup).
- `:5381-5391` — `chroma_vault/` via `shutil.copytree`.
- `:5393-5400` — `for config_file in (paths.global_config_toml, paths.permissions_file):`
- `:5402-5403` — a manifest note that `.env` files are excluded.

There is no other copy in the function. `hachi restore` (`:5420-5520`) is an exact
mirror — `sessions.db` (`:5467-5480`), `chroma_vault/` (`:5482-5494`), the two config
files (`:5496-5506`) — so anything not backed up is also not restorable.

### 3.2 What that leaves behind — a real machine, listed

`%LOCALAPPDATA%\hachi\` on a working install, annotated:

| Entry | In backup? | What it is |
|---|---|---|
| `sessions.db` | ✅ | conversation transcripts |
| `chroma_vault/` | ✅ | semantic memory (Chroma backend only) |
| `settings.toml` | ✅ | config |
| `device-permissions.og` | ✅ | permission tier + grants |
| **`skills/`** | ❌ | **the user's authored `.og` skills** |
| **`brain.og`** | ❌ | **the root skill graph** |
| **`memory/`** | ❌ | **the `.og` memory graph — canonical under `fts5_only`** (§3.3) |
| `runs.db` | ❌ | durable run state; WAITING runs, resume cursors |
| `files.db` | ❌ | file-attachment metadata |
| `blobs/` | ❌ | the attachment payloads themselves |
| `checkpoints/` | ❌ | file-change undo history (`rollback_changes`) |
| `schedules.json` | ❌ | cron/interval/once schedules |
| `skill_usage.json` | ❌ | usage stats driving skill ranking |
| `onboarding_state.json` | ❌ | setup completion state |
| `secrets_metadata.json` | ❌ | secret names/labels (not values) |
| `og_skill_embeddings/` | ❌ | opt-in embedding rank index (derived) |
| `memory_index.db` | ❌ | FTS5 index over `memory/` (derived) |
| `secrets.enc` | ❌ | encrypted secret store fallback (`core/paths.py:60-61`) |
| **`jobs.db`** | ❌ | **in a different root entirely** — [T-53](T-53-jobs-db-path-unification.md) |
| `.env` | ❌ | deliberate, correct, and documented |

Everything below the fourth row is lost on a restore. Two of them (`og_skill_embeddings/`,
`memory_index.db`) are legitimately derived and *should* be skipped — but deliberately,
with a comment, not by omission.

`memory/` does not appear on a default-config machine because `MemorySettings.graph`
defaults `False` (`core/settings.py:87`). It materialises exactly for the users who
enabled the graph or chose `fts5_only` — i.e. the users for whom it matters most.

### 3.3 ⚠️ Under `memory.backend = "fts5_only"` the omitted `.og` files ARE the memory

`resolve_provider` (`core/memory_provider.py:301-302`) returns `FTS5MemoryProvider`,
which has no `.vault`, so boot sets `vault = None`
(`gateway/orchestrator.py:3039`, `gateway/shared_services.py:302-303`). Facts are
written as `.og` nodes by `MemoryWriter` (`core/memory_provider.py:256-265` →
`core/memory_writer.py:140-162`) into `paths.memory_dir` — i.e.
`data_dir/memory/` (`core/paths.py:76-78`) — and read back through `MemoryIndex`, whose
`refresh()` rebuilds entirely from those files (`core/memory_index.py:92-151`).

`chroma_vault/` is never created. So `hachi backup` on that backend copies:
`sessions.db`, a **non-existent or empty** vault directory, and two config files. The
restore yields an agent with a transcript and no memory.

The command reports success either way — the vault branch prints
`"chroma_vault/ (skipped — not yet created)"` into the manifest (`:5391`), which reads
as *"you had none"* rather than *"your memory is somewhere else and I did not look"*.

### 3.4 `hachi doctor` never probes a store — `cli/main.py:4629-4650`

```python
    checks = {
        "python_version": sys.version.split()[0],
        "config_dir_exists": paths.config_dir.exists(),
        "data_dir_exists": paths.data_dir.exists(),
        "state_dir_exists": paths.state_dir.exists(),
        "settings_toml_exists": paths.global_config_toml.exists(),
        "provider_kind": cfg.provider.kind,
        ...
    }
```

Four directory existence checks (`:4631-4634`). **No database is opened, no store size
is reported, and the `opengigantic` root that holds `jobs.db` is never looked at.**
`doctor` will report a healthy install on a machine whose entire job queue is in a
directory the tool does not know exists.

### 3.5 `HachiPaths` has no way to enumerate stores

`core/paths.py:12-114` declares eighteen individual properties. There is no
`all_stores()`, no registry, no list. Every consumer that wants "all the data" must
hand-write the list — and `hachi backup` did, four items long, in 2024, and it has not
been touched since a store was added.

That is the actual defect. The missing files are the symptom.

### 3.6 Why it survived — the tests assert the four things it does copy

`tests/test_backup_restore.py` has eleven tests. Six assert on what *is* backed up
(`test_backup_creates_sessions_db:78`, `test_backup_copies_chroma_vault:107`,
`test_backup_copies_config_files:126`) and on what is correctly excluded
(`test_backup_excludes_dotenv:145`). Five cover restore semantics and the confirmation
guard.

**Not one test asserts that anything else was backed up**, because the command never
claimed to. The test file mirrors the implementation's assumptions exactly — which is
what makes it useless as a safety net here and why §7 has to assert *completeness*, not
presence.

## 4. Reproduce the failure

Fully reproducible, and worth doing once by hand because the output is the argument.

### 4a. Back up your real install into a scratch directory and list what came out

This **reads** live data and writes only into the temp destination. It does not modify
anything. Note it copies your real `chroma_vault/`, which can be large.

```bash
# Use the scratch dir, NOT the default (which writes into your real state dir).
hachi backup --dest /tmp/hachi-backup-check        # Windows: --dest %TEMP%\hachi-backup-check

# What the backup actually contains:
python -c "
import pathlib, sys
root = pathlib.Path(sys.argv[1])
d = sorted(root.iterdir())[-1]
print('backup dir:', d)
print('contents  :', sorted(p.name for p in d.iterdir()))
" /tmp/hachi-backup-check

# What your install actually contains:
python -c "
from hachi.core.paths import get_hachi_paths
p = get_hachi_paths()
for label, d in (('state_dir', p.state_dir), ('data_dir', p.data_dir), ('config_dir', p.config_dir)):
    print(label, d)
    print('   ', sorted(x.name for x in d.iterdir()) if d.exists() else '(absent)')
"

# And the store the canonical paths cannot even see (until T-53):
python -c "
import pathlib
from platformdirs import PlatformDirs
d = pathlib.Path(PlatformDirs('hachi', 'opengigantic').user_state_dir)
print(d, '->', [x.name for x in d.iterdir()] if d.exists() else 'absent')
"
```

**You will see now:** the backup contains `['chroma_vault', 'device-permissions.og',
'sessions.db', 'settings.toml']` while your install contains fifteen-plus entries — and
`jobs.db` sits alone in a third directory neither listing covers.

**You should see after the fix:** the backup directory contains every non-derived store,
and a `manifest.json` recording what was captured, what was deliberately skipped, and
why.

### 4b. The `fts5_only` data-loss case — CODE-READING PROOF

**This one is not safely reproducible end-to-end without changing your real
`settings.toml` and running a live agent long enough to extract facts. Do not do that
to demonstrate a bug you can prove by reading.** The chain is short and decisive:

```bash
# 1. fts5_only is a supported backend.
rg -n "MemoryBackend = Literal" src/hachi/core/settings.py

# 2. On that backend, boot produces vault=None — no Chroma at all.
rg -n "isinstance\(_provider, ChromaMemoryProvider\) else None" src/hachi/gateway/orchestrator.py

# 3. Facts are written as .og nodes under paths.memory_dir instead.
rg -n -A 6 "class FTS5MemoryProvider" src/hachi/core/memory_provider.py
rg -n "def memory_dir" -A 3 src/hachi/core/paths.py

# 4. backup never touches memory_dir. Expect: NO output.
rg -n "memory_dir" src/hachi/cli/main.py
```

**You will see now:** steps 1-3 confirm `.og` files under `data_dir/memory/` are the
canonical store on that backend, and step 4 returns **nothing** — `hachi backup` has no
reference to `memory_dir` at all.

**You should see after the fix:** step 4 returns the enumeration site.

### 4c. `doctor` is blind

```bash
hachi doctor --json | python -c "import json,sys; d=json.load(sys.stdin); print([k for k in d if 'exist' in k or 'db' in k])"
```

**You will see now:** `['config_dir_exists', 'data_dir_exists', 'state_dir_exists',
'settings_toml_exists']` — four directory checks, zero databases.
**You should see after the fix:** a per-store entry with presence and size.

## 5. What "fixed" looks like

> ### The design constraint that matters
>
> The bug is not "four files instead of fifteen". It is that **the list lives in
> `cli/main.py` and nothing connects it to the code that creates stores.** Adding the
> eleven missing paths to that function fixes today and guarantees a repeat: the next
> store lands in `core/paths.py` and nobody edits `backup()`.
>
> **The deliverable is a single source of truth that both backup and doctor consume, and
> a test that fails when a new store is added without registering it.** If your change
> is a longer `shutil.copy2` list, you have fixed the symptom.

### Target state

1. **`HachiPaths` gains a store registry** — `core/paths.py`:

   ```python
   @dataclass(frozen=True, slots=True)
   class StoreSpec:
       """One durable artefact Hachi owns."""

       name: str            # "sessions.db", "memory/", ...
       path: Path
       kind: str            # "sqlite" | "dir" | "file"
       derived: bool        # True => rebuildable; skipped by backup, on purpose
       note: str            # why it is derived, or what it holds


   def all_stores(self) -> list[StoreSpec]:
       """Every durable artefact Hachi owns. THE source of truth.

       Backup, restore and doctor all enumerate from here. A new store MUST be
       added to this list — tests/test_backup_restore.py asserts that every path
       property on HachiPaths is either registered here or explicitly exempted.
       """
   ```

   Registered as **not derived** (backed up): `sessions.db`, `jobs.db`, `runs.db`,
   `files.db`, `chroma_vault/`, `memory/`, `blobs/`, `checkpoints/`, `skills/`,
   `brain.og`, `schedules.json`, `skill_usage.json`, `onboarding_state.json`,
   `secrets_metadata.json`, `secrets.enc`, `settings.toml`, `device-permissions.og`.

   Registered as **derived** (skipped, with the reason recorded in the manifest):
   `memory_index.db` (rebuilt by `MemoryIndex.refresh()` from `memory/`),
   `og_skill_embeddings/` (rebuilt by `SkillEngine` from `skills/`).

   **Not registered at all:** `.env` (secrets, deliberately excluded today — keep that
   behaviour and keep the manifest note at `cli/main.py:5403`), `gateway.log`, `Cache/`.

2. **`backup()` iterates `all_stores()`** instead of hardcoding. Keep the existing
   special cases — they are correct and hard-won:
   - `sessions.db` keeps its **online hot-backup** via `SessionStore.backup()`
     (`cli/main.py:5370-5374`). Do not downgrade it to `copy2`; that is what makes it
     safe while the gateway is running.
   - Every other SQLite store needs the same treatment or an explicit acknowledgement
     that a plain copy of a WAL database can be inconsistent. **Prefer
     `sqlite3.Connection.backup()`** for all of them — see the trap in §12.
   - `chroma_vault/` keeps `copytree` and its "stop-the-world snapshot" caveat.

3. **A `manifest.json` in the backup directory**, recording for each store: name, source
   path, captured/skipped, reason if skipped, byte size, and (once
   [T-54](T-54-schema-version-tables.md) lands) its `schema_version`. Restore reads it
   and reports anything the backup did not contain. This is what turns "silently
   incomplete" into "explicitly partial".

4. **`restore()` iterates the same registry**, driven by the manifest. It must remain
   the exact mirror of backup — anything backed up is restorable — and must keep the
   `--yes` confirmation guard (`cli/main.py:5454-5462`) unchanged.

5. **`doctor` probes each store** (`cli/main.py:4629-4650`): presence, size, and for
   SQLite an `PRAGMA integrity_check` or at minimum a successful open. Replace the four
   `*_dir_exists` booleans with a `stores` map. Keep the existing keys as well —
   `doctor --json` is consumed by CI/automation per its own help text
   (`cli/main.py:4562`), so removing keys is a breaking change; **add, do not replace**.

6. **The backup docstring stops understating.** `cli/main.py:5329-5340` currently
   enumerates three things; it becomes a statement that everything non-derived is
   captured, with the exclusions named.

## 6. Steps

1. Confirm [T-53](T-53-jobs-db-path-unification.md) has landed. **If it has not, stop.**
   `jobs.db` is not reachable from `get_hachi_paths()` and cannot be registered — and
   the §7 test fixture (which patches `get_hachi_paths`) would not redirect it to
   `tmp_path`, so your test would read or write the developer's **real** job queue. This
   is the hard dependency, not a preference.
2. Write the regression test from §7 and watch it **fail**.
3. Add `StoreSpec` and `HachiPaths.all_stores()` to `core/paths.py` (§5 item 1).
4. Rewrite `backup()` (`cli/main.py:5317-5417`) to iterate the registry, preserving the
   `sessions.db` hot-backup path and every existing comment
   ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
5. Emit `manifest.json` (§5 item 3).
6. Rewrite `restore()` (`cli/main.py:5420-5520`) to mirror it, reading the manifest and
   reporting gaps. Keep the `--yes` guard byte-identical.
7. Extend `doctor`'s `checks` dict with a `stores` map (§5 item 5) — **additively**.
8. Update the `backup` docstring (§5 item 6).
9. Run the regression tests — they must now pass, including the round trip.
10. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.
11. **Verify by hand against your own install** (§10) — the tests use synthetic paths.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**The acceptance criterion is a full round trip: back up, wipe, restore, assert the data
survived.** Presence-in-the-archive is necessary but not sufficient — a backup that
captures a file the restore ignores is still data loss.

- **File:** `tests/test_backup_restore.py` (**existing** — extend it; it already owns
  this command's coverage and has the right fixtures)
- **Test names:** `test_full_round_trip_preserves_every_registered_store` (the lock),
  `test_backup_captures_the_og_memory_graph`,
  `test_every_hachi_path_is_registered_or_explicitly_exempt`
- **It must assert:** the real, observed filesystem after a real
  backup → wipe → restore cycle, using the file's existing
  `_make_fake_paths(tmp_path)` + `patch("hachi.cli.main.get_hachi_paths", ...)` +
  `CliRunner` pattern (`tests/test_backup_restore.py:28-43`, `:86-87`).
- **It must FAIL before your fix** with:
  `AssertionError: store not restored: memory/ (and 10 others)`

```python
# tests/test_backup_restore.py — extend, reusing _make_fake_paths / _seed_* helpers
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from hachi.cli.main import app


def _seed_every_store(paths) -> dict[str, str]:
    """Write a unique sentinel into every store so the round trip is verifiable."""
    sentinels: dict[str, str] = {}

    (paths.data_dir / "memory" / "projects").mkdir(parents=True, exist_ok=True)
    (paths.data_dir / "memory" / "core_memory.og").write_text(
        "::node[deploy-target]\n->[:role=fact]\n::dense\nfly.io\n", encoding="utf-8"
    )
    sentinels["memory/core_memory.og"] = "fly.io"

    paths.skills_dir.mkdir(parents=True, exist_ok=True)
    (paths.skills_dir / "my-skill.og").write_text("::index\n# authored\n", encoding="utf-8")
    sentinels["skills/my-skill.og"] = "# authored"

    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    (paths.checkpoints_dir / "cp-1.json").write_text('{"undo": true}', encoding="utf-8")
    sentinels["checkpoints/cp-1.json"] = '"undo"'

    paths.schedules_file.write_text('[{"id": "daily-standup"}]', encoding="utf-8")
    sentinels["schedules.json"] = "daily-standup"

    # ... blobs/, files.db, runs.db, jobs.db, brain.og, skill_usage.json,
    #     onboarding_state.json, secrets_metadata.json — one sentinel each.
    return sentinels


def test_full_round_trip_preserves_every_registered_store(tmp_path: Path) -> None:
    """backup -> wipe -> restore must return every non-derived store intact.

    Regression (T-55): `hachi backup` copied only sessions.db, chroma_vault/,
    settings.toml and device-permissions.og, and reported success. Everything else
    — the user's .og skills, the .og memory graph (CANONICAL under the fts5_only
    backend), runs.db, files.db, blobs/, checkpoints/, schedules.json and the
    job queue — was silently lost on restore.
    """
    import shutil

    fake_paths = _make_fake_paths(tmp_path)
    _seed_sessions_db(fake_paths.sessions_db)
    _seed_fake_vault(fake_paths.chroma_dir)
    sentinels = _seed_every_store(fake_paths)

    runner = CliRunner()
    backup_dest = tmp_path / "backups"
    with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
        assert runner.invoke(app, ["backup", "--dest", str(backup_dest)]).exit_code == 0
    backup_dir = next(iter(backup_dest.iterdir()))

    # Wipe every live root — simulate the disaster the command exists for.
    for d in (fake_paths.data_dir, fake_paths.state_dir, fake_paths.config_dir):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True, exist_ok=True)

    with patch("hachi.cli.main.get_hachi_paths", return_value=fake_paths):
        result = runner.invoke(app, ["restore", str(backup_dir), "--yes"])
    assert result.exit_code == 0, result.output

    missing = [
        rel for rel, needle in sentinels.items()
        if not (fake_paths.data_dir / rel).exists()
        and not (fake_paths.state_dir / rel).exists()
    ]
    assert not missing, f"store not restored: {', '.join(missing)}"


def test_backup_captures_the_og_memory_graph(tmp_path: Path) -> None:
    """Under memory.backend=fts5_only the .og files ARE the memory. They must survive."""
    ...  # seed only memory/, back up, assert the .og content is inside the archive


def test_every_hachi_path_is_registered_or_explicitly_exempt() -> None:
    """A new HachiPaths property must be registered in all_stores() or exempted.

    This is the test that stops T-55 recurring: it fails when someone adds a store
    and forgets the registry.
    """
    from hachi.core.paths import HachiPaths

    _EXEMPT = {"cache_dir", "config_dir", "data_dir", "state_dir",
               "user_roles_dir", "journal_shard_path"}
    properties = {
        n for n, v in vars(HachiPaths).items()
        if isinstance(v, property) and not n.startswith("_")
    }
    registered = {s.name for s in _paths_for_test().all_stores()}
    unregistered = properties - _EXEMPT - _registered_property_names(registered)
    assert not unregistered, f"unregistered store paths: {sorted(unregistered)}"
```

Notes for whoever writes this for real:

- `test_every_hachi_path_is_registered_or_explicitly_exempt` is the one that makes this
  fix durable. Get its exempt-set right and keep it small — every name in it is a
  decision you are recording, so add a comment per entry.
- The wipe step is what distinguishes this from the existing tests. Without it a
  backup that captures files the restore ignores still passes.
- Reuse `_make_fake_paths`, `_seed_sessions_db` and `_seed_fake_vault` from the file's
  existing helpers (`:28`, `:46`, `:62`). Do not write a second harness.
- **`jobs.db` will not be redirected by `patch("hachi.cli.main.get_hachi_paths", ...)`
  until [T-53](T-53-jobs-db-path-unification.md) lands** — see §12. That is the
  dependency, made concrete.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and `test_full_round_trip_preserves_every_registered_store` failed before the fix listing the unrestored stores.
- [ ] `HachiPaths.all_stores()` exists and is the **only** enumeration; `rg -n "sessions.db" src/hachi/cli/main.py` shows no hardcoded store list in `backup()`/`restore()`.
- [ ] The round trip preserves: `skills/`, `brain.og`, `memory/`, `runs.db`, `files.db`, `blobs/`, `checkpoints/`, `schedules.json`, `skill_usage.json`, `onboarding_state.json`, `secrets_metadata.json`, `secrets.enc`, `jobs.db`, plus the original four.
- [ ] Derived stores (`memory_index.db`, `og_skill_embeddings/`) are skipped **deliberately**, and the manifest records why.
- [ ] `.env` is still excluded and the manifest still says so (`cli/main.py:5403`).
- [ ] `manifest.json` exists in the backup and lists every store as captured or skipped-with-reason.
- [ ] `sessions.db` still uses the **online hot-backup**, not a plain file copy; every other SQLite store is copied consistently (§12).
- [ ] `hachi doctor --json` reports per-store presence and size, **without removing** any existing key.
- [ ] `test_every_hachi_path_is_registered_or_explicitly_exempt` fails if a new `HachiPaths` property is added without registering it (verify by temporarily adding a dummy property).
- [ ] **Verified by hand on a real install** (§10) — backup into a scratch dir, inspect the manifest, confirm your `skills/` and (if present) `memory/` are inside.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not back up `.env` or secret *values*.** The current exclusion is correct and
  deliberate (`cli/main.py:5335-5336`, `:5402-5403`). `secrets_metadata.json` (names and
  labels) and `secrets.enc` (the encrypted fallback store, `core/paths.py:60-61`) are
  registered because they are already encrypted or non-sensitive — but say so in the
  manifest, and if you are unsure about `secrets.enc`, **ask** rather than deciding
  quietly. Backing up secrets is a security decision, not a completeness decision.
- **Do not add compression, encryption, or remote upload.** A backup that is complete
  and boring is the deliverable. Archive format changes are a separate product decision.
- **Do not add incremental or scheduled backups.** Same reason.
- **Do not move `runs.db` to `state_dir`** because it looks out of place while you
  enumerate. [T-53](T-53-jobs-db-path-unification.md) deferred that explicitly. Register
  it where it is.
- **Do not add `schema_version` to any store.** That is
  [T-54](T-54-schema-version-tables.md). If it has landed, *read* the versions into the
  manifest; do not write them.
- **Do not fix the memory-backend seam.** You will notice while tracing §3.3 that
  `fts5_only` sets `vault=None`. That is
  [T-49](T-49-memory-provider-seam-decision.md).
- **Do not remove `doctor`'s existing keys.** `--json` is documented for CI consumption
  (`cli/main.py:4562`); adding is safe, replacing is a breaking change.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
  The eleven existing tests in `tests/test_backup_restore.py` must all still pass
  unchanged; they assert behaviour you are extending, not replacing.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. `shutil`, `sqlite3` and `json` are
  stdlib; no archive library is needed for a directory copy.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** You are adding a method to `HachiPaths`, which
is imported by nearly every module in the product, and changing two CLI commands that
several test files invoke. `tests/test_p1_09_paths.py` and `tests/test_backup_restore.py`
are the obvious candidates and they are not sufficient.

**Then verify by hand, because every test uses synthetic paths:**

```bash
hachi backup --dest /tmp/hachi-t55-check     # Windows: --dest %TEMP%\hachi-t55-check
python -c "
import json, pathlib, sys
d = sorted(pathlib.Path(sys.argv[1]).iterdir())[-1]
m = json.loads((d / 'manifest.json').read_text(encoding='utf-8'))
for s in m['stores']:
    print(f\"{s['status']:9} {s['name']:26} {s.get('reason','')}\")
" /tmp/hachi-t55-check
```

Confirm your `skills/` is captured, `.env` is absent, the two derived stores are listed
as skipped **with a reason**, and — if you run `memory.graph=true` or `fts5_only` —
that `memory/` is present with your `.og` files inside it.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `hachi backup` silently omitted most user data, including the entire .og memory graph

- **Symptom:** `hachi backup` printed a green "Backup created" panel and copied only
  four things: `sessions.db`, `chroma_vault/`, `settings.toml` and
  `device-permissions.og`. A user who backed up, wiped and restored lost their authored
  `.og` skills, `brain.og`, `runs.db`, `files.db`, `blobs/`, `checkpoints/`,
  `schedules.json`, `skill_usage.json`, `onboarding_state.json`, `secrets_metadata.json`,
  `secrets.enc` and the entire job queue. **Under `memory.backend = "fts5_only"` — where
  `data_dir/memory/**/*.og` is the CANONICAL fact store and no Chroma vault exists — the
  restore produced an agent that remembered nothing.** `hachi doctor` was equally blind:
  four directory-existence checks and no database probe.
- **Root cause:** `backup()` (`cli/main.py`) hardcoded a four-item list written before
  most stores existed, and nothing connected it to `core/paths.py` where stores are
  declared. `HachiPaths` exposed eighteen path properties and no way to enumerate them,
  so every consumer had to hand-maintain its own list — and this one was never updated.
  `jobs.db` was additionally on a second platformdirs root and unreachable from
  `get_hachi_paths()` at all (BB-N / T-53).
- **Fix:** Added `HachiPaths.all_stores()` returning `StoreSpec` records (name, path,
  kind, derived, note) as the single source of truth. `backup`, `restore` and `doctor`
  all enumerate from it. Backup emits a `manifest.json` recording what was captured and
  what was deliberately skipped and why; restore reads it and reports gaps.
  `sessions.db` keeps its online hot-backup; other SQLite stores use
  `sqlite3.Connection.backup()` so WAL contents are consistent.
- **Avoid:** a backup command must never hardcode what to copy. Enumerate from the same
  declaration the stores are created from, and add a test that fails when a new store is
  declared without being registered — otherwise "backup" degrades into "backup of
  whatever existed the day it was written", silently, with a success message.
- **Locked by:** `tests/test_backup_restore.py` — `test_full_round_trip_preserves_every_registered_store`
```

## 12. Known traps

- **⚠️ `jobs.db` is invisible to the test fixture until [T-53](T-53-jobs-db-path-unification.md).**
  `tests/test_backup_restore.py` redirects everything by patching
  `hachi.cli.main.get_hachi_paths` (`:86`, `:115`, `:137`, …). `jobs.db` does **not**
  come from `get_hachi_paths()` — it comes from `PlatformDirs("hachi", "opengigantic")`
  inside `jobs/queue.py:576-582`. A test written before T-53 lands would therefore
  operate on the **developer's real job queue**. This is the hard dependency; do not
  work around it by special-casing `jobs.db` in the backup.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. The existing tests use a
  **fake** vault directory of plain files (`tests/test_backup_restore.py:62-67`) rather
  than a real Chroma store — follow that pattern. Nothing here needs chromadb loaded.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir` (`core/paths.py:32-33`).
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. `all_stores()` must
  depend on nothing but `HachiPaths`' own fields.
- **Copying a live WAL SQLite file with `shutil.copy2` can produce a corrupt or stale
  backup.** `sessions.db` avoids this via `SessionStore.backup()` (`core/session_store.py:986`,
  called from `cli/main.py:5372`). `runs.db` (`core/runtime/store.py:75`) and `jobs.db`
  (`jobs/queue.py:630`) are **also** WAL. Use `sqlite3.Connection.backup()` for them —
  or, at minimum, copy the `-wal` and `-shm` sidecars alongside and say in the manifest
  that the copy is not guaranteed consistent under a running gateway.
- **`restore` currently `rmtree`s the live `chroma_vault/` before copying**
  (`cli/main.py:5487-5489`). If you generalise that to directories like `skills/`, a
  restore from a partial backup **deletes** the user's skills and then does not replace
  them. Restore only what the manifest says is present, and never delete a target whose
  source is absent.
- **The backup destination defaults to `<state_dir>/backups/`** (`cli/main.py:5347-5348`),
  which is **inside** the tree you are now enumerating. Exclude it explicitly, or the
  first backup-of-a-backup will recurse. This did not matter when only four files were
  copied; it matters now.
- **`gateway.log` and `Cache/` exist under the state dir** on a real install and are
  neither `HachiPaths` properties nor stores. Do not sweep the directory — enumerate the
  registry. A directory sweep would capture logs (which can contain prompt text) into a
  backup users may share.
- **`doctor --json` is documented for CI** (`cli/main.py:4562`). Adding a `stores` key is
  safe; renaming or removing `config_dir_exists` and friends is a breaking change for
  anyone parsing it.
