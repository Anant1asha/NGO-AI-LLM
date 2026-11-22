# T-06 · Make `[memory]` settings actually reach the vault (incl. M2 decay)

|  |  |
|---|---|
| **Source finding** | CF-1 #3 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **corrected by** [CORRECTIONS.md](CORRECTIONS.md) §8 |
| **Severity** | P0 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~4 hours |
| **Difficulty** | Medium (needs a judgement call on the fingerprint — read §5.2) |
| **Files you will touch** | `src/hachi/gateway/shared_services.py`, `src/hachi/gateway/orchestrator.py`, `tests/test_memory_settings_reach_vault.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Three documented `[memory]` settings — `recall_distance_max`, `core_memory_max_entries`,
and `decay_half_life_days` (the M2 recency-decay feature) — are read from config,
validated into a `MemorySettings` object, and then **thrown away**. The vault every
session actually uses is built somewhere else entirely, with a settings-free
`initialize(brain_dir=...)` call.

When you are done, a user who sets `decay_half_life_days = 30.0` in `settings.toml` gets
a vault that was constructed with that value, and a mismatch between configured and
effective settings is a `logger.warning` rather than silence.

## 2. Why this matters

> ### ⚠️ Read this before you touch the `if` at `orchestrator.py:3022`.
> **Fixing that condition alone will NOT deliver the settings.** The review points at an
> unreachable `else` branch; that is only half the story. On the non-Chroma path the
> `else` *does* run and still fails its `isinstance` check, so **neither branch ever
> delivers the three settings.** The real fix target is
> `gateway/shared_services.py:300-307`. See [CORRECTIONS.md](CORRECTIONS.md) §8.

`decay_half_life_days` is the entire M2 feature — shipped, tested at the unit level,
documented in `core/settings.py`, and inert. `recall_distance_max` is the guard that
stops unrelated facts being injected into every turn's context. A user who tunes memory
and observes no change concludes the product does not work, and they are right.

The code makes the opposite claim in a comment. That comment is part of what you are
fixing.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The settings that are silently ignored

`src/hachi/core/settings.py:80-107` — `MemorySettings`:

```python
    recall_distance_max: float | None = 0.85          # :94
    core_memory_max_entries: int = 1000               # :95
    ...
    decay_half_life_days: float | None = None         # :103
```

Their in-file documentation (`:88-103`) describes exactly the behaviour that never
happens.

### 3.2 The branch the review points at — and the lying comment

`src/hachi/gateway/orchestrator.py:3020-3040`:

```python
    # P4-02: reuse shared vault when already initialised (avoids opening a new Chroma
    # PersistentClient per session — up to 100 clients per process before this fix).
    if _shared.vault is not None:
        vault: MemoryVault | None = _shared.vault
        _provider = ChromaMemoryProvider(vault=vault)
    else:
        _provider = resolve_provider(_memory_settings)
        # Issue 10: pass the recall-distance threshold and core-memory cap from the
        # [memory] config into the ChromaDB vault so settings.toml actually controls
        # retrieval behaviour. Non-Chroma backends keep the plain initialize() signature.
        if isinstance(_provider, ChromaMemoryProvider):
            _provider.initialize(
                brain_dir=str(get_hachi_paths().data_dir),
                recall_distance_max=_memory_settings.recall_distance_max,
                core_memory_max_entries=_memory_settings.core_memory_max_entries,
                decay_half_life_days=_memory_settings.decay_half_life_days,
            )
        else:
            _provider.initialize(brain_dir=str(get_hachi_paths().data_dir))
        vault = _provider.vault if isinstance(_provider, ChromaMemoryProvider) else None
    memory.set_vault(vault)
```

The comment at `:3027-3029` — *"so settings.toml actually controls retrieval
behaviour"* — is false and must be corrected with the fix.

### 3.3 Why the `else` is unreachable on the Chroma path

`src/hachi/gateway/orchestrator.py:2790-2792`, ~230 lines **earlier** in the same
function:

```python
    from hachi.gateway.shared_services import ProcessSharedServices

    _shared = ProcessSharedServices.get_or_create(config, str(get_hachi_paths().data_dir))
```

`get_or_create` → `_init` **always** builds the vault. `src/hachi/gateway/shared_services.py:296-307`:

```python
        # --- MemoryVault (shared Chroma client) ---
        vault: Any = None
        _raw_memory = config.get("memory", {})
        _memory_settings = MemorySettings.model_validate(_raw_memory)
        _provider = resolve_provider(_memory_settings)
        _provider.initialize(brain_dir=brain_dir)
        if isinstance(_provider, ChromaMemoryProvider):
            vault = _provider.vault
            # Mark as the process-shared vault so an individual AgentSession never
            # closes it on shutdown — only shutdown_all() (atexit) closes it once.
            if vault is not None:
                vault.is_shared = True
```

Note `:299` — it **already parses `MemorySettings`** and then calls
`initialize(brain_dir=brain_dir)` with none of them. The vault is returned at
`shared_services.py:345`:

```python
        return cls(
            skill_engine=skill_engine,
            mcp_manager=mcp_manager,
            vault=vault,
            ...
        )
```

So by the time `boot_agent` reaches `:3022`, `_shared.vault is not None` on the default
(`chroma`) backend, and the settings-carrying `else` is skipped.

### 3.4 …and why the `else` fails even when it DOES run

On `backend = "in_memory"` or `"fts5_only"`, `resolve_provider` returns an
`InMemoryProvider` / `FTS5MemoryProvider`, `_shared.vault` is `None`, so the `else`
runs — and `isinstance(_provider, ChromaMemoryProvider)` is `False`, so control lands on
`orchestrator.py:3038`:

```python
            _provider.initialize(brain_dir=str(get_hachi_paths().data_dir))
```

Settings dropped again. **Neither branch ever delivers them.**

(That path is arguably correct — those providers' `initialize` signatures are
`(self, brain_dir: str) -> None` at `memory_provider.py:185` and `:244` and they have no
recall/decay machinery — but it means the `else` is not the fix site.)

### 3.5 The only signature that accepts the settings

`src/hachi/core/memory_provider.py:113-144` — only `ChromaMemoryProvider.initialize`
takes them:

```python
    def initialize(
        self,
        brain_dir: str,
        *,
        recall_distance_max: float | None = None,
        core_memory_max_entries: int | None = None,
        decay_half_life_days: float | None = None,
    ) -> None:
        ...
        if self._vault is None:
            from hachi.core.memory_vault import MemoryVault

            _kwargs: dict[str, Any] = {"brain_dir": brain_dir}
            if recall_distance_max is not None:
                _kwargs["recall_distance_max"] = recall_distance_max
            ...
            self._vault = MemoryVault(**_kwargs)
```

The base ABC is `initialize(self, brain_dir: str) -> None` (`memory_provider.py:40`), so
you **must** keep the `isinstance` narrowing — do not add the kwargs unconditionally or
mypy-strict and the non-Chroma providers both break.

### 3.6 Second trap — the fingerprint does not include these settings

`src/hachi/gateway/shared_services.py:52-63`:

```python
def _config_fingerprint(config: dict[str, Any], brain_dir: str) -> str:
    """Return a stable cache key for a (config, brain_dir) pair.

    Only the fields that affect *shared* service construction are included:
    ``memory.backend``, ``memory.graph``, and ``brain_dir``.  All other
    per-session config keys are irrelevant to the singleton.
    """
    memory = config.get("memory", {}) if isinstance(config.get("memory"), dict) else {}
    backend = str(memory.get("backend", "chroma"))
    graph = str(bool(memory.get("graph", False)))
    raw = f"{brain_dir}|{backend}|{graph}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

Once you make the vault carry the settings, that docstring becomes **wrong**: the three
settings now *do* affect shared-service construction. Two sessions in one process with
different `[memory]` recall settings would share one vault built from whichever booted
first, and a hot-reload of `settings.toml` would not pick up a change.

## 4. Reproduce the failure

**This is not reproducible from a shell without instrumentation** — the settings are
silently dropped, no exception is raised, and nothing is logged. There is no CLI command
that prints the vault's effective `recall_distance_max`.

The code-reading proof is §3.3: `boot_agent` calls `ProcessSharedServices.get_or_create`
at `:2792`, whose `_init` unconditionally builds and returns a vault
(`shared_services.py:300-307`, `:345`), which makes `_shared.vault is not None` true at
`:3022`, which skips the only branch that passes the settings.

You can make it visible in a scratch REPL (do **not** commit this):

```bash
uv run python -c "
from hachi.core.memory_provider import ChromaMemoryProvider, resolve_provider
from hachi.core.settings import MemorySettings
s = MemorySettings.model_validate({'decay_half_life_days': 30.0, 'recall_distance_max': 0.5})
p = resolve_provider(s)
p.initialize(brain_dir='<a tmp dir>')          # exactly what shared_services.py:301 does
print(type(p).__name__)
print('half_life ->', getattr(p.vault, 'decay_half_life_days', '<attr missing>'))
print('distance  ->', getattr(p.vault, 'recall_distance_max', '<attr missing>'))
"
```

**You will see now:** the `MemoryVault` defaults, not `30.0` / `0.5`.
**You should see after the fix:** the configured values — because
`shared_services._init` will have passed them.

**The stored names are private** — `src/hachi/core/memory_vault.py:500-507`:

```python
        self._recall_distance_max: float | None = recall_distance_max
        ...
        self._core_memory_max_entries: int = max(1, core_memory_max_entries)
        ...
        self._decay_half_life_days: float | None = decay_half_life_days
```

The constructor parameters are at `:403-405`. Read the private names in the diagnostic
snippet above, but **do not** read `_`-prefixed state from shipped code or from your
regression test — add read-only properties instead (§5.4, §6 step 2). (Note the snippet
uses `getattr(..., default)` purely as a *diagnostic*; see
[T-14](T-14-ban-getattr-own-types.md) for why it must not appear in shipped code.)

## 5. What "fixed" looks like

### 5.1 Thread the settings through `_init` (the actual fix)

`src/hachi/gateway/shared_services.py:296-307` becomes:

```python
        # --- MemoryVault (shared Chroma client) ---
        vault: Any = None
        _raw_memory = config.get("memory", {})
        _memory_settings = MemorySettings.model_validate(_raw_memory)
        _provider = resolve_provider(_memory_settings)
        if isinstance(_provider, ChromaMemoryProvider):
            # The three [memory] retrieval controls (Issue 10 + M2 decay) are only
            # honoured if they are passed HERE — this is the vault every session
            # actually uses (boot_agent reuses _shared.vault).
            _provider.initialize(
                brain_dir=brain_dir,
                recall_distance_max=_memory_settings.recall_distance_max,
                core_memory_max_entries=_memory_settings.core_memory_max_entries,
                decay_half_life_days=_memory_settings.decay_half_life_days,
            )
            vault = _provider.vault
            if vault is not None:
                vault.is_shared = True
        else:
            _provider.initialize(brain_dir=brain_dir)
```

### 5.2 DECISION — the fingerprint

**Add the three settings to `_config_fingerprint`.** They now affect shared-service
construction, which is the documented criterion for inclusion (`shared_services.py:55-57`).
Leaving them out means the singleton's cache key lies about what the singleton contains.

```python
    raw = (
        f"{brain_dir}|{backend}|{graph}"
        f"|{memory.get('recall_distance_max')}"
        f"|{memory.get('core_memory_max_entries')}"
        f"|{memory.get('decay_half_life_days')}"
    )
```

Update the docstring at `:55-57` to match.

**Cost of including them:** a config change to any of the three produces a *new*
`ProcessSharedServices` instance, i.e. a second ChromaDB `PersistentClient` against the
same on-disk store, and the old one stays in `_INSTANCES` until `shutdown_all()`. That is
the exact resource problem P4-02 was written to avoid.

**Why include them anyway:** in the shipped single-user product these settings change
only when the user edits `settings.toml` and restarts, so the multi-instance case is rare
and bounded — whereas a stale-cache bug here is silent and indistinguishable from the bug
you are fixing. Correctness beats a rare extra client.

Read the raw dict keys (`memory.get(...)`), **not** the validated model, so the
fingerprint stays a pure function of the input config with no default-inflation — the
same reasoning as `backend`/`graph` above it.

### 5.3 Fix the false comment, keep the branch honest

At `orchestrator.py:3027-3029`, replace the "so settings.toml actually controls
retrieval behaviour" comment with the truth: the settings are applied by
`ProcessSharedServices._init`; this branch is the no-shared-vault fallback and mirrors
it. Then either keep the `else` branch as-is (it is now a genuine mirror) or, if you
prefer one owner, delete the duplication and let `boot_agent` always take the shared
vault. **Prefer keeping it** — deleting a fallback is a Rule 3 functionality removal, and
the branch is reachable in tests that clear the singleton.

### 5.4 Make the failure loud (required)

After `memory.set_vault(vault)` at `orchestrator.py:3040`, add a settings-vs-vault
reconciliation warning:

First add three read-only properties to `MemoryVault` (next to the existing accessors),
because the state is private (`memory_vault.py:500-507`) and neither production code nor
a test should reach into `_`-prefixed attributes:

```python
    @property
    def decay_half_life_days(self) -> float | None:
        return self._decay_half_life_days

    @property
    def recall_distance_max(self) -> float | None:
        return self._recall_distance_max

    @property
    def core_memory_max_entries(self) -> int:
        return self._core_memory_max_entries
```

Then reconcile at boot:

```python
    if vault is not None and vault.decay_half_life_days != _memory_settings.decay_half_life_days:
        logger.warning(
            "[memory] decay_half_life_days=%s was configured but the live vault "
            "reports %s — memory settings are not reaching the vault",
            _memory_settings.decay_half_life_days,
            vault.decay_half_life_days,
        )
```

**Do not write this check as a defaulted `getattr`** — that is exactly the idiom
[T-14](T-14-ban-getattr-own-types.md) bans, and it would turn a missing property into a
silent pass. Read the property directly and let an `AttributeError` be loud.

## 6. Steps

1. Add the three read-only properties to `MemoryVault` (§5.4) — the test in §7 needs
   them.
2. Write the regression test from §7. Run it. Watch it fail.
3. Edit `shared_services._init` per §5.1.
4. Edit `_config_fingerprint` + its docstring per §5.2.
5. Correct the comment at `orchestrator.py:3027-3029` per §5.3.
6. Add the reconciliation warning per §5.4.
7. Run the test. Watch it pass.
8. Run `uv run python scripts/preflight.py`. Report real counts — expect vault/Chroma
   tests to be the sensitive ones.
9. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_memory_settings_reach_vault.py` (new)
- **Test names:** `test_shared_vault_carries_configured_memory_settings`,
  `test_fingerprint_changes_when_recall_settings_change`
- **It must assert:** the **live vault object** on `ProcessSharedServices` reports the
  configured values. Assert against the vault, not against `MemorySettings` (which
  obviously round-trips) and not against a mock's recorded kwargs (which proves only that
  you called something).
- **It must FAIL before your fix** with:
  `AssertionError: assert None == 30.0` (the vault carries `MemoryVault`'s default
  because `initialize()` was called with `brain_dir` only).

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

import pytest

from hachi.gateway.shared_services import ProcessSharedServices, _config_fingerprint


@pytest.fixture(autouse=True)
def _clean_singleton():
    ProcessSharedServices.clear()
    yield
    ProcessSharedServices.shutdown_all()


def test_shared_vault_carries_configured_memory_settings(tmp_path: Path) -> None:
    config = {
        "memory": {
            "backend": "chroma",
            "recall_distance_max": 0.42,
            "core_memory_max_entries": 77,
            "decay_half_life_days": 30.0,
        }
    }
    shared = ProcessSharedServices.get_or_create(config, str(tmp_path), force_reinit=True)
    vault = shared.vault
    assert vault is not None, "chroma backend must produce a vault"

    # These are the read-only properties added in §5.4 over the private
    # _decay_half_life_days / _recall_distance_max / _core_memory_max_entries.
    assert vault.decay_half_life_days == 30.0
    assert vault.recall_distance_max == 0.42
    assert vault.core_memory_max_entries == 77


def test_fingerprint_changes_when_recall_settings_change(tmp_path: Path) -> None:
    base = {"memory": {"backend": "chroma"}}
    tuned = {"memory": {"backend": "chroma", "decay_half_life_days": 30.0}}
    assert _config_fingerprint(base, str(tmp_path)) != _config_fingerprint(tuned, str(tmp_path))
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second test is the guard against the §3.6 trap — it fails today because the
fingerprint ignores those keys.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `ProcessSharedServices.get_or_create({...memory settings...}).vault` reports the
      configured `recall_distance_max`, `core_memory_max_entries`, and
      `decay_half_life_days`.
- [ ] `_config_fingerprint` includes the three settings and its docstring says so.
- [ ] The false comment at `orchestrator.py:3027-3029` is corrected.
- [ ] A mismatch between configured and effective memory settings emits a
      `logger.warning` at boot.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not "fix" the `if _shared.vault is not None:` condition** at
  `orchestrator.py:3022` by inverting it or by forcing the `else`. That re-opens P4-02
  (one ChromaDB `PersistentClient` per session, up to ~100 per process) and still would
  not fix the non-Chroma path. The vault must stay shared.
- **Do not add recall/decay parameters to `InMemoryProvider` / `FTS5MemoryProvider`.**
  They have no recall-distance or decay machinery; widening the ABC signature is a
  separate design change.
- **Do not touch `episodic_top_k` or `graph_recall`** (`settings.py:98`, `:107`). They
  are consumed elsewhere and are not part of this finding. If you find they are *also*
  dead, note it and move on — do not expand scope.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done. This change touches the
shared ChromaDB singleton — a scoped run will not catch cross-module regressions
(CLAUDE.md Rule 2). Run the FULL suite.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — `[memory]` recall/decay settings never reached the vault (M2 decay was inert)

- **Symptom:** `recall_distance_max`, `core_memory_max_entries`, and
  `decay_half_life_days` had no effect. Setting `decay_half_life_days = 30.0` changed
  nothing — the M2 recency-decay feature was inert for every user, silently.
- **Root cause:** the only code that passed those settings lived in
  `boot_agent`'s `else` branch (`gateway/orchestrator.py`), reached only when
  `_shared.vault is None`. But `boot_agent` calls
  `ProcessSharedServices.get_or_create()` ~230 lines earlier, whose `_init`
  unconditionally builds the vault with a settings-free
  `_provider.initialize(brain_dir=brain_dir)` — so on the default `chroma` backend the
  branch was unreachable. On the non-Chroma backends the `else` DID run but failed its
  `isinstance(_provider, ChromaMemoryProvider)` check and fell to a plain
  `initialize()`. **Neither branch ever delivered the settings.** An in-code comment
  claimed the opposite ("so settings.toml actually controls retrieval behaviour").
  Compounding it, `_config_fingerprint` keyed only on `brain_dir|backend|graph`, so
  changing any of the three did not even produce a new singleton.
- **Fix:** passed the three settings in `ProcessSharedServices._init` — the site that
  builds the vault every session actually uses — added them to `_config_fingerprint`,
  corrected the false comment, and added a boot-time `logger.warning` when the
  configured value and the live vault's value disagree.
- **Avoid:** when a setting is applied in a branch, prove the branch is reachable on the
  DEFAULT path before believing the feature works. A settings object that is parsed and
  then never passed anywhere is a dead feature; grep the parse site for a corresponding
  consumer.
- **Locked by:** `tests/test_memory_settings_reach_vault.py` —
  `test_shared_vault_carries_configured_memory_settings`
```

## 12. Known traps

- **BB-3:** never `patch.dict(sys.modules)` over `chromadb` — the native PyO3 extension
  cannot be re-initialised once dropped, and it poisons every later vault test in the
  process. `tests/conftest.py:66-70` warms it deliberately; do not defeat that.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Your test must call
  `get_or_create(..., force_reinit=True)` explicitly.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-5:** `paths.workspace_dir` does not exist — use `get_hachi_paths().skills_dir` /
  `.data_dir`.
- `tests/conftest.py:75-90` autouse-clears `_INSTANCES` **before every test** and
  `shutdown_all()`s at session end. If your test leaks an open `PersistentClient`, later
  vault tests fail with "database disk image is malformed" on the *next* run. Always use
  `tmp_path` as `brain_dir`.
- `ProcessSharedServices` is a plain `@dataclass` (`shared_services.py:66`) — not frozen,
  not slotted. Adding fields is safe; that is not the constraint here.
- `MemoryVault` construction is lazy (PERF-05, see the module docstring at
  `memory_vault.py:31-40`): the `PersistentClient` and each collection are created on
  first access. Constructing a vault in a test does **not** open Chroma; touching a
  collection does.
