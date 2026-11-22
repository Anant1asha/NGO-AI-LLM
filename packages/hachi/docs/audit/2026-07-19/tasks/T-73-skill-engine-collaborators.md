# T-73 · Extract `UsageTracker` / `SkillAuthor` / `EmbeddingRanker` out of `SkillEngine`, and inject the usage path

|  |  |
|---|---|
| **Source finding** | CF-19 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §9 and §12) |
| **Files you will touch** | `src/hachi/og_engine/engine.py`, new modules under `src/hachi/og_engine/`, `tests/`, `docs/bug-bank.md` |

---

## 1. Brief

`SkillEngine` is a single 1,556-line class that mixes six unrelated jobs: parsing/indexing,
BM25 search, lint, usage persistence, skill authoring, and an embedded ChromaDB client. Its
constructor calls `get_hachi_paths()`, so the "pure library" that the `.og` moat lives in
**cannot be instantiated without a Hachi home directory** — even to parse a file.

When you are done, usage persistence, authoring, and embedding rank live in their own
collaborators, and `SkillEngine(usage_path=...)` can be constructed anywhere, including in a
process that has never run Hachi.

## 2. Why this matters

`og_engine` is the moat. Its layering is genuinely clean — see §3.5 — and the review's
comparative analysis calls the enforcement mechanism rarer than it should be even at mature
companies. What it is *not* is embeddable: `get_hachi_paths()` in `__init__` means the very
first line of any integration — `SkillEngine()` — touches the filesystem and resolves
platform-specific state directories. That is the difference between "a `.og` library you can
`pip install`" and "a component of the Hachi app."

The size is the second half. 1,556 lines in one class means every feature that has ever
touched skills landed here, and there is no seam at which to test any of it in isolation.
`get_stale_skills` cannot be tested without a usage file on disk; `enable_embedding_rank`
cannot be tested without ChromaDB; `upsert_skill` cannot be tested without both.

**This task is about constructor coupling and class size — not layering.** If you find
yourself editing `pyproject.toml`'s import-linter config, you have drifted; see §9.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The class — `og_engine/engine.py:326`, body `326-1881` = **1,556 lines**

```python
class SkillEngine:
    """Central registry, retrieval engine, and lifecycle manager for .og skills.

    Maintains a persistent usage database (JSON) that tracks how often each
    skill is loaded, when it was first/last used, and whether it has gone stale.
    ...
    """
```

The file is 1,881 lines; `SkillEngine` is the last thing in it, so the class body runs to
EOF. Everything above it — `_tokenize` (`:137`), `estimate_tokens` (`:183`), `_lint_result`
(`:200`), `lint_og_file` (`:214`) — is already module-level and needs no change.

### 3.2 The coupling — `get_hachi_paths()` inside `__init__`, `engine.py:386-395`

`__init__` is at `:340`. The offending block:

```python
        # Phase 4: Persistent usage tracking (platformdirs state_dir)
        _paths = get_hachi_paths()
        self._usage_path = _paths.skill_usage_json
        self._usage: dict[str, dict[str, Any]] = self._load_usage()
        # Usage-write debounce: skip the disk write when a flush already happened
        # within _usage_flush_interval seconds.  The first call after boot (or after
        # the interval expires) always flushes so tests and one-shot runs see the file.
        self._usage_last_flush: float = 0.0  # monotonic time of last successful _save_usage
        self._usage_flush_interval: float = 30.0  # seconds between successive writes
        self._usage_lock: threading.Lock = threading.Lock()
```

`get_hachi_paths` is imported at module level, `engine.py:35`. Note `:389` — the constructor
does not merely *resolve* a path, it **reads a file from disk** (`_load_usage`).

A **second, unrelated** call sits at `:875-877`, inside `enable_embedding_rank`:

```python
        from hachi.core.paths import get_hachi_paths

        db_path = str(get_hachi_paths().state_dir / "og_skill_embeddings")
```

(A redundant local re-import of a symbol already imported at `:35`.)

### 3.3 The three collaborators are already visible in the method list

**`UsageTracker` — 8 methods + 5 fields.** The only reason `__init__` touches the filesystem:

| Anchor | Method |
|---|---|
| `:979` | `get_usage_counters` |
| `:987` | `reset_usage_counters` |
| `:1704` | `_load_usage` |
| `:1716` | `_save_usage` |
| `:1726` | `record_use` |
| `:1756` | `flush_usage` |
| `:1763` | `get_stale_skills` |
| `:1814` | `get_usage_report` |

Fields: `_usage_path`, `_usage`, `_usage_last_flush`, `_usage_flush_interval`, `_usage_lock`.

**`SkillAuthor` — 6 methods.** Writes `.og` files; nothing to do with querying them:

| Anchor | Method |
|---|---|
| `:1157` | `_slugify` (static) |
| `:1168` | `validate_dense` (static) |
| `:1177` | `upsert_skill` |
| `:1385` | `_bump_patch` (static) |
| `:1394` | `import_skill_md` |
| `:1434` | `export_skill` |

**`EmbeddingRanker` — 2 methods + the embedded ChromaDB client.** `engine.py:859-898`:

```python
    def enable_embedding_rank(self, collection_name: str = "og_skill_index") -> None:
        ...
        try:
            import chromadb  # type: ignore[import-untyped]
            from chromadb.config import Settings  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("P3-04: chromadb not installed; embedding rank unavailable")
            return

        from hachi.core.paths import get_hachi_paths

        db_path = str(get_hachi_paths().state_dir / "og_skill_embeddings")
        client = chromadb.PersistentClient(
            path=db_path, settings=Settings(anonymized_telemetry=False)
        )
```

plus `_embedding_search` (`:900`) and the `self._emb_collection` field set at `:897`.

**What stays in `SkillEngine`:** parsing/indexing (`load_directory` `:540`, `load_file`
`:560`), retrieval (`search` `:737`, `peek` `:993`, `resolve_node` `:1049`), the graph/meta
readers (`:1447`-`:1694`), and scope enforcement (`_is_visible` `:416`). That is a coherent
class and it is still large — **that is fine.** Do not chase a line count.

### 3.4 Blast radius — 20 construction sites in `src/`, 61 in tests

`rg -n "SkillEngine\(" src/` → **20** sites: `cli/commands/skill.py` (12), `cli/main.py` (2),
`gateway/orchestrator.py:2802`, `gateway/shared_services.py:281`,
`channels/telegram_commands.py:108`, `cli/commands/mcp.py:50`, `tools/config_tools.py:189`.
`rg -o "SkillEngine\(" tests/ | wc -l` → **61** across 22 files.

**81 call sites. This is why the injected parameter must be defaulted** (§5) — a required
argument means an 81-site diff for a refactor that is supposed to change no behaviour.

### 3.5 Good news — the layering is already clean

`pyproject.toml:179-193`, the `og_engine is pure` contract, has **no `ignore_imports` key at
all**: zero exemptions against nine forbidden packages. `og_engine → core` is the one
permitted direction, and `from hachi.core.paths import get_hachi_paths` uses it legally.

**So there is nothing to fix in the import graph.** The problem is that a *constructor*
resolves environment state — a testability and embeddability problem, not a layering one.
Confirm with `uv run lint-imports` before and after: it must stay
`Contracts: 3 kept, 0 broken`.

### 3.6 ⚠️ `with_role` bypasses `__init__` entirely — `engine.py:535-538`

```python
        view = SkillEngine.__new__(SkillEngine)
        view.__dict__.update(self.__dict__)
        view._agent_role = agent_role
        return view
```

**Any state you move into a collaborator is shared by reference across every view** — which
is correct for usage tracking (one file, one lock) but is a trap if you add construction
logic that `with_role` will never run. Read this method before you touch `__init__`.

## 4. Reproduce the failure

The embeddability failure is real and reproducible in one command.

```bash
# SkillEngine() resolves a Hachi home directory and READS A FILE, at construction.
python -c "
import hachi.og_engine.engine as e, unittest.mock as m
with m.patch.object(e, 'get_hachi_paths', side_effect=RuntimeError('no Hachi home')):
    e.SkillEngine()
"
```

**You will see now:** `RuntimeError: no Hachi home`, raised from `__init__` — before a single
`.og` file has been named. A consumer embedding the `.og` library in a process with no Hachi
installation cannot construct the object at all.

**You should see after the fix:** `SkillEngine(usage_path=Path("/tmp/usage.json"))`
constructs with the same patch in place, because nothing resolves platform paths unless the
caller omitted the argument.

Confirm the rest of §3 mechanically:

```bash
wc -l src/hachi/og_engine/engine.py                       # 1881
rg -n "^class SkillEngine" src/hachi/og_engine/engine.py  # 326  -> body is 1,556 lines
rg -n "get_hachi_paths" src/hachi/og_engine/engine.py     # 35 (import), 387, 875, 877
rg -n "SkillEngine\(" src/ | grep -vc "class SkillEngine" # 20 construction sites
rg -o "SkillEngine\(" tests/ | wc -l                      # 61
uv run lint-imports                                       # 3 kept, 0 broken (baseline)
```

## 5. What "fixed" looks like

### The constructor seam — do this first, it is the whole point of the task

```python
    def __init__(
        self,
        agent_role: str = "*",
        node_cap: int = 5000,
        *,
        usage_path: Path | None = None,
    ) -> None:
```

- `usage_path=None` (the default) → resolve `get_hachi_paths().skill_usage_json` exactly as
  today. **All 81 existing call sites keep working, byte-identical.**
- `usage_path=<Path>` → use it, and **never call `get_hachi_paths()`**.

That single change makes the class embeddable and gives every test a real isolation seam. It
is worth landing on its own, before any extraction.

Do the same for `enable_embedding_rank` — add `db_path: Path | None = None`, defaulting to
today's `state_dir / "og_skill_embeddings"`, and drop the redundant local re-import at `:875`.

### The three collaborators

New modules beside `engine.py`: `og_engine/usage.py`, `og_engine/authoring.py`,
`og_engine/embedding.py`. Each owns its own state and takes its dependencies as arguments —
no module-level path resolution, no `get_hachi_paths()` in any constructor.

```python
class UsageTracker:
    """Persistent skill-usage counters. Owns the JSON file, the lock, and the debounce."""

    def __init__(self, usage_path: Path) -> None: ...
    def record(self, name: str) -> None: ...
    def flush(self) -> None: ...
    def counters(self) -> dict[str, int]: ...
    def reset(self) -> None: ...
    def stale(self, stale_days: int = 30, *, known: Iterable[str]) -> list[dict[str, Any]]: ...
    def report(self) -> dict[str, Any]: ...
```

`SkillEngine` composes them and **keeps its existing public methods as thin delegations**:

```python
    def record_use(self, name: str) -> None:
        self._usage.record(name)
```

**Delegate; do not remove.** Public methods on `SkillEngine` are called from 20 places in
`src/` and 61 in tests. This refactor must be invisible from outside — that is what makes it
reviewable and what lets you verify it with the existing suite.

### Sequencing — four independently landable commits

1. **`usage_path` injection.** ~20 lines changed, zero behaviour change, immediate payoff.
2. **`EmbeddingRanker`.** The cleanest cut: two methods, one field, an optional dependency
   already isolated behind `try: import chromadb`.
3. **`UsageTracker`.** The most valuable: it is the only reason the constructor touched disk.
4. **`SkillAuthor`.** The largest (`upsert_skill` alone is `:1177-1384`) and the least
   entangled — it writes files and does not participate in query paths.

**Stopping after (1) is a legitimate outcome.** It resolves the finding's actual complaint.
Stopping after (3) resolves the finding entirely.

### Explicit non-goals

- **Not a line-count exercise.** `SkillEngine` will still be ~900 lines afterwards, and the
  remainder — parse, index, search, resolve — is one coherent job.
- **No behaviour changes.** Not the BM25 weights, not the debounce interval, not the scope
  rules. If a test changes, you did something else.
- **No new dependencies.** ChromaDB stays optional and lazily imported exactly as it is.

## 6. Steps

1. `uv run lint-imports` and the full suite — record the baseline.
2. Write the §7 test. Watch it fail with `RuntimeError: no Hachi home`.
3. Add the keyword-only `usage_path` parameter; resolve via `get_hachi_paths()` only when it
   is `None`. Run the full suite. **Commit.**
4. Add `db_path` to `enable_embedding_rank`; delete the redundant import at `:875`. Full
   suite. **Commit.**
5. Create `og_engine/embedding.py` with `EmbeddingRanker`; move `:859-923`; leave
   `enable_embedding_rank` / `_embedding_search` on `SkillEngine` as delegations. Full suite.
   **Commit.**
6. Create `og_engine/usage.py` with `UsageTracker`; move the 8 methods and 5 fields from
   §3.3; delegate. **Read §3.6 first** — `with_role` shares `__dict__` by reference, so the
   tracker instance must be shareable and its lock must stay a single object. Full suite.
   **Commit.**
7. Create `og_engine/authoring.py` with `SkillAuthor`; move the 6 methods; delegate. Full
   suite. **Commit.**
8. `uv run lint-imports` → still `3 kept, 0 broken`. Full `uv run python scripts/preflight.py`.
   Report real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_og_engine.py` (**existing** — it already owns `SkillEngine`; do not
  start a new file)
- **Test names:** `test_engine_constructs_without_a_hachi_home`,
  `test_injected_usage_path_is_used_verbatim`
- **It must assert:** the real, observed behaviour — that construction succeeds with
  `get_hachi_paths` unavailable, and that a supplied path is the file actually written. Not
  that a mock was called.
- **It must FAIL before your fix** with `RuntimeError: no Hachi home` raised from
  `SkillEngine.__init__` (and, for the second test, `TypeError: __init__() got an unexpected
  keyword argument 'usage_path'`).

```python
# sketch — adapt to the repo's existing fixtures
import json
from pathlib import Path
from unittest import mock

import pytest


def test_engine_constructs_without_a_hachi_home(tmp_path: Path) -> None:
    """The .og library must be embeddable — no Hachi home required to construct.

    Regression: SkillEngine.__init__ called get_hachi_paths() and read the usage
    JSON from disk, so `SkillEngine()` failed outright in any process that had
    never run Hachi — even to parse a single .og file.
    """
    import hachi.og_engine.engine as engine_mod

    with mock.patch.object(
        engine_mod, "get_hachi_paths", side_effect=RuntimeError("no Hachi home")
    ):
        engine = engine_mod.SkillEngine(usage_path=tmp_path / "usage.json")

    assert engine.node_count() == 0


def test_injected_usage_path_is_used_verbatim(tmp_path: Path) -> None:
    """An injected usage path is the file that actually gets written."""
    from hachi.og_engine.engine import SkillEngine

    usage = tmp_path / "nested" / "usage.json"
    engine = SkillEngine(usage_path=usage)
    engine.record_use("some-skill")
    engine.flush_usage()

    assert usage.is_file(), "record_use/flush_usage did not write the injected path"
    assert "some-skill" in json.loads(usage.read_text(encoding="utf-8"))


def test_with_role_view_shares_the_usage_tracker() -> None:
    """with_role() bypasses __init__ via __new__ + __dict__.update.

    Views must share one tracker (one file, one lock) — not get a second one.
    """
    from hachi.og_engine.engine import SkillEngine

    engine = SkillEngine()
    view = engine.with_role("orchestrator")
    engine.record_use("shared-skill")

    assert view.get_usage_counters().get("shared-skill") == 1
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> `test_with_role_view_shares_the_usage_tracker` passes today (shared `__dict__`) and must
> **keep** passing — it is the guard against §3.6's trap, not a new requirement.

## 8. Acceptance criteria

- [ ] The §7 tests exist; the first two failed before the fix.
- [ ] `SkillEngine(usage_path=...)` constructs with `get_hachi_paths` unavailable.
- [ ] `rg -n "get_hachi_paths" src/hachi/og_engine/engine.py` shows **no call inside `__init__`** when `usage_path` is supplied; the redundant local re-import at `:875` is gone.
- [ ] All 20 `src/` construction sites and 61 test sites are **unchanged** — the parameter is defaulted (`git diff --stat` proves it).
- [ ] Every public method that existed on `SkillEngine` still exists, with the same signature.
- [ ] `uv run lint-imports` reports `Contracts: 3 kept, 0 broken`, and the `og_engine is pure` contract still has **zero** `ignore_imports`.
- [ ] `with_role()` views still share one usage tracker (§7 third test).
- [ ] ChromaDB is still lazily imported and still optional — `enable_embedding_rank` still logs and returns on `ImportError`.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `pyproject.toml`'s import-linter config.** §3.5: the `og_engine is pure`
  contract is clean with zero exemptions. This is constructor coupling, not layering. Adding
  an exemption "to make the extraction easier" would trade the repo's cleanest contract for a
  refactor's convenience. Layering burn-down is
  [T-68](T-68-import-linter-exemption-burndown.md).
- **Do not change any retrieval behaviour.** BM25 weights, `_tokenize`, `_prefix_matched_qids`
  (`:448`), scope rules in `_is_visible` (`:416`) — all untouched. The eval harness
  (`hachi eval run`, blocking in preflight) will catch a change in retrieval ranking, and
  that failure is genuinely hard to debug from inside a big refactor.
- **Do not "fix" `with_role`'s `__new__` + `__dict__.update`.** It is deliberate (a shared,
  no-copy view) and documented at `:516-533`. Replacing it with a real constructor changes
  sharing semantics for every sub-agent.
- **Do not make ChromaDB a hard dependency**, and do not move the `try: import chromadb`
  higher. `enable_embedding_rank` degrades gracefully today and must keep doing so.
- **Do not touch the eval corpus or golden fixtures.** [CORRECTIONS.md](CORRECTIONS.md) §5 —
  they are golden inputs; editing them churns the eval baseline.
- **Do not fix `og_engine/engine.py`'s 8 mypy errors** or the `vulture` finding at
  `engine.py:650` (unsatisfiable ternary) while you are in the file. Those belong to
  [T-69](T-69-mypy-burndown-ratchet.md) and the advisory backlog. **Note them and move on.**
- **Do not split `load_file` (`:560-716`) or `upsert_skill` (`:1177-1384`).** They are long,
  they are on the list of things you might want to improve, and they are not this task.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run lint-imports                          # must stay 3 kept, 0 broken
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite after every one of the four commits, not just at the end.** 61 test call
sites construct this class; a shared-state mistake in step 6 shows up as an unrelated test
failing in a different module, and bisecting that across a four-commit refactor is painful.

Watch the **`eval regression`** step specifically (`scripts/preflight.py:117`). It replays the
real agent loop, so it is the check most likely to catch an accidental retrieval-behaviour
change — the failure mode this refactor is most exposed to.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `SkillEngine.__init__` resolved a Hachi home, so the "pure" .og library was not embeddable

- **Symptom:** `SkillEngine()` raised in any process without a Hachi installation — the
  constructor called `get_hachi_paths()` and then READ the usage JSON from disk before any
  .og file was named. Tests could not isolate usage state without monkeypatching platform
  paths, and `get_stale_skills` / `get_usage_report` were untestable without a real home dir.
- **Root cause:** persistent usage tracking was added straight onto the class that owns
  parsing and retrieval, and its file path was resolved in `__init__` rather than injected.
  The class passed import-linter (`og_engine -> core` is the one permitted direction), so
  the coupling was invisible to the architectural rail — it was a *constructor* dependency
  on environment state, not an import-layer violation.
- **Fix:** added a defaulted keyword-only `usage_path: Path | None = None` (so all 81
  existing construction sites were untouched) and extracted `UsageTracker` / `SkillAuthor` /
  `EmbeddingRanker` as collaborators, with `SkillEngine`'s public methods kept as thin
  delegations.
- **Avoid:** a constructor must not resolve environment state. Inject the path (defaulted, so
  no call site changes) and let composition roots decide. import-linter cannot see this class
  of coupling — if a "pure" library cannot be constructed under
  `mock.patch(..., side_effect=RuntimeError)` on its path resolver, it is not pure.
  Related trap: `SkillEngine.with_role()` builds views via `__new__` + `__dict__.update`, so
  extracted collaborators are shared by reference and must be safe to share.
- **Locked by:** `tests/test_og_engine.py` — `test_engine_constructs_without_a_hachi_home`, `test_with_role_view_shares_the_usage_tracker`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3 — chromadb.** `enable_embedding_rank` imports chromadb lazily and
  `tests/conftest.py` warms it at import so the PyO3 extension loads exactly once. **Never**
  `patch.dict(sys.modules)` over chromadb to test `EmbeddingRanker` — it poisons every later
  test in the process. Inject a fake client through the new seam instead; that is one of the
  reasons to extract it.
- **⚠️ `with_role` (`:535-538`) bypasses `__init__`.** `SkillEngine.__new__` +
  `__dict__.update(self.__dict__)` means every extracted collaborator is shared by reference
  across all views. That is correct for `UsageTracker` (one file, one `threading.Lock`) — but
  any construction logic you add to `__init__` will simply never run for a view.
- **BB-51 — the corrupt-usage-file quarantine.** `_load_usage` (`:1704-1714`) calls
  `quarantine_corrupt_file(self._usage_path)` on a parse failure *before* returning `{}`, so
  the next `_save_usage` cannot silently clobber a recoverable file. **Carry that into
  `UsageTracker` verbatim.** Losing it re-opens a fixed data-loss bug.
- **The usage write is debounced and lock-guarded** (`_usage_flush_interval = 30.0` at `:394`,
  `_usage_lock` at `:395`, `_save_usage` at `:1716-1724` using `atomic_write_json`). Preserve
  the debounce semantics exactly, including the comment at `:390-392` explaining that the
  first call after boot always flushes so tests and one-shot runs see the file.
- **`cli/commands/skill.py` constructs `SkillEngine()` twelve times** — once per command.
  Signature-compatibility is not optional; a required parameter is a 12-site diff in one file
  alone.
- **`gateway/shared_services.py:281` caches the engine.** [CORRECTIONS.md](CORRECTIONS.md) §8
  records that `_config_fingerprint` (`shared_services.py:52-63`) keys only on
  `brain_dir|backend|graph` — so a differently-constructed engine may **not** produce a new
  cached instance on hot reload. Do not rely on reconstruction to pick up a new `usage_path`.
- **`og_engine/engine.py` has 8 pre-existing mypy errors** and one `vulture` finding at
  `:650`. Both are pre-existing and **not yours** — do not let the strict-gate ratchet
  ([T-69](T-69-mypy-burndown-ratchet.md)) pull you into typing a file you are mid-refactor on.
