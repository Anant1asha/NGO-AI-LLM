# T-10 · Attach `session_store` to `ProcessSharedServices` (and stop leaking a SQLite handle per message)

|  |  |
|---|---|
| **Source finding** | CF-1 #7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~2–3 hours |
| **Difficulty** | Medium |
| **Files you will touch** | `src/hachi/gateway/shared_services.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/gateway/fastapi_app.py`, `src/hachi/core/cost.py`, `tests/test_shared_session_store.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Three separate code paths read `ProcessSharedServices.session_store` in order to reuse the
live SQLite store. **The attribute does not exist** — it is on no dataclass field and is
assigned nowhere in `src/`. So every "prefer the shared store" branch is dead, and the
hot message path falls back to constructing a fresh `SessionStore()` **that is never shut
down**, leaking a sqlite3/WAL connection per call.

`boot_agent` already creates the store and hands it to four other consumers. When you are
done it also attaches it to the shared singleton, the three readers use it, and the
remaining fallback closes what it opens.

## 2. Why this matters

This is CF-1 with a resource leak attached. The `getattr` default and the `hasattr` guard
make three dead branches read as careful defensive code, so nobody notices that the
careful path never runs.

The worse half is `fastapi_app.py`: `_resolve_session_store()` is called on the durable
ingress-idempotency path — i.e. **per message** — and returns a brand-new `SessionStore()`
that runs full schema init/migrations and holds `sessions.db-wal` / `-shm` handles open
for the life of the process. On Windows that compounds until the gateway is restarted.

And it is a **recurrence**: `core/cost.py` carries a bug-bank comment describing this
exact bug class in its own previous implementation, and the fix for it reintroduced the
same shape one level down. Your bug-bank entry must say so.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The attribute does not exist

`src/hachi/gateway/shared_services.py:87-105` — the complete field list of the
`@dataclass ProcessSharedServices`:

```python
    skill_engine: Any  # SkillEngine
    mcp_manager: Any  # MCPManager
    vault: Any  # MemoryVault | None
    graph_index: Any  # MemoryIndex | None
    memory_writer: Any  # MemoryWriter | None
    brain_dir: str
    _fingerprint: str = field(default="", repr=False)
    initialized_at: float = field(default_factory=time.monotonic)
    event_bus: Any = field(default=None)  # EventBus | None
    wait_registry: Any = field(default=None)  # WaitConditionRegistry | None
    routing_store: Any = field(default=None)  # RoutingConfigStore | None
    scheduler: Any = field(default=None)  # Scheduler | None
    scheduler_runner_started: bool = field(default=False)
```

**No `session_store`.** `_init` (`:342-350`) does not set one either:

```python
        return cls(
            skill_engine=skill_engine,
            mcp_manager=mcp_manager,
            vault=vault,
            graph_index=graph_index,
            memory_writer=memory_writer,
            brain_dir=brain_dir,
            _fingerprint=fingerprint,
        )
```

Verify no assignment exists anywhere:

```bash
grep -rn "\.session_store\s*=" src/ tests/     # -> no output
```

### 3.2 Reader 1 — the hot path, with the leak

`src/hachi/gateway/fastapi_app.py:420-438` — `_resolve_session_store`:

```python
def _resolve_session_store() -> Any:
    """Return the process-wide ``SessionStore`` (preferred) or a fresh fallback, else None.

    Mirrors the ``ProcessSharedServices`` access pattern used elsewhere in this module so
    durable ingress idempotency (AUDIT P0-3) reads/writes the same database the rest of the
    gateway uses. Patched in tests to point at an isolated DB.
    """
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        store = getattr(shared, "session_store", None) if shared is not None else None
        if store is not None:
            return store
        from hachi.core.session_store import SessionStore

        return SessionStore()
    except Exception:  # pragma: no cover - store is best-effort; never break the turn
        return None
```

`store` is **always** `None` (line `:431`), so `:436` runs on every call and the returned
store is **never closed**. The docstring's claim — *"reads/writes the same database the
rest of the gateway uses"* — is the opposite of what happens.

### 3.3 Reader 2 — a `hasattr` guard that is always False

`src/hachi/gateway/fastapi_app.py:1013-1030`, inside `cleanup_empty_sessions`:

```python
        removed = 0
        try:
            from hachi.gateway.shared_services import ProcessSharedServices

            _shared = ProcessSharedServices.instance()
            if _shared is not None and hasattr(_shared, "session_store"):
                _store = _shared.session_store
                if _store is not None and hasattr(_store, "delete_empty_sessions"):
                    removed = _store.delete_empty_sessions()
            else:
                # Fallback: instantiate a fresh store (same DB file).
                from hachi.core.session_store import SessionStore

                _store = SessionStore()
                removed = _store.delete_empty_sessions()
        except Exception:
            _log.warning("cleanup_empty_sessions: failed to delete empty sessions", exc_info=True)
        return {"removed": removed}
```

`hasattr(_shared, "session_store")` is permanently `False`, so the `else` always runs —
another unclosed `SessionStore()`.

### 3.4 Reader 3 — and the BB-42 recurrence

`src/hachi/core/cost.py:87-109` — `_get_shared_session_store`:

```python
def _get_shared_session_store() -> Any:
    """Return the process-wide ``SessionStore`` if one has been booted, else ``None``.

    Mirrors ``hachi.core.runtime.resume._get_process_bus``'s pattern for reaching
    the shared-services singleton from ``core`` without a hard import-time
    dependency on the gateway: the import is lazy and any failure (including the
    module simply not existing at this fingerprint) degrades to ``None``, which
    callers treat as "no shared store yet — open a short-lived fallback".

    BB-42: the previous code imported a ``_get_session_store`` symbol from
    ``hachi.gateway.orchestrator`` that has never existed there, so this lookup
    always raised ``ImportError`` and every call silently fell through to the
    fallback branch.
    """
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        if shared is not None:
            return getattr(shared, "session_store", None)
    except Exception:
        pass
    return None
```

Read `:96-99` and then `:106`. **The docstring describes the bug; the code below it
commits the same bug in a new form.** BB-42 was "imported a symbol that has never
existed"; the fix reintroduced it as "getattr an attribute that has never existed". Same
outcome — the function always returns `None`.

### 3.5 …but `cost.py` gets the *cleanup* right

`src/hachi/core/cost.py:305-321`:

```python
        shared = _get_shared_session_store()
        if shared is not None:
            shared.record_daily_cost(date_str, cost)
        else:
            from hachi.core.session_store import SessionStore

            # BB-42: this short-lived store is never shared, so it must be shut
            # down here — otherwise its sqlite3/WAL connection leaks for the
            # rest of the process lifetime.
            fallback_store = SessionStore()
            try:
                fallback_store.record_daily_cost(date_str, cost)
            finally:
                _shutdown = getattr(fallback_store, "shutdown", None)
                if callable(_shutdown):
                    _shutdown()
```

**This is the correct fallback shape.** `fastapi_app.py:436` and `:1026` do not do it.
Copying this shape to those two sites is part of this task.

### 3.6 The fix point — the store already exists in `boot_agent`

`src/hachi/gateway/orchestrator.py:3008-3009`:

```python
    # Initialize Session Store (Phase 3: cross-session persistence)
    session_store = SessionStore()
```

It is then handed to four consumers, none of which is `_shared`:

| Consumer | Anchor |
|---|---|
| `BootDeps` | `orchestrator.py:3148` — `session_store=session_store` |
| session tools | `orchestrator.py:3275` — `register_session_tools(d.tool_registry, d.session_store)` |
| the session | `orchestrator.py:3464` — `session.set_session_store(session_store, model=model_name)` |
| idle sweep | `orchestrator.py:3603` — `ResidentWorkerThread(..., session_store=session_store, ...)` |

`_shared` is already in scope at that point (bound at `:2792`). The missing line is one
assignment.

## 4. Reproduce the failure

The dead attribute is directly demonstrable:

```bash
uv run python -c "
from hachi.gateway.shared_services import ProcessSharedServices
print('declared fields:', sorted(ProcessSharedServices.__dataclass_fields__))
print('session_store declared?', 'session_store' in ProcessSharedServices.__dataclass_fields__)
"
```

**You will see now:** `session_store declared? False`
**You should see after the fix:** `True`, with `session_store` in the field list.

And that nothing ever assigns it:

```bash
grep -rn "\.session_store\s*=" src/ tests/    # -> no output today
```

The **leak** is not observable from a one-shot shell command — it needs a long-lived
gateway process and a file-handle inspection. The code-reading proof is §3.2: `store` is
`None` at `:431` because the attribute does not exist, so `:436` returns a fresh
`SessionStore()` to a caller that never closes it, on a per-message path. Compare with
`cost.py:311-320`, which explicitly shuts its fallback down for exactly this reason and
cites BB-42 while doing it.

## 5. What "fixed" looks like

### 5.1 Declare the field

`src/hachi/gateway/shared_services.py`, with the other optional fields (`:96-105`):

```python
    # Phase 3 / BB-42: the process-wide SessionStore created by boot_agent. Attached
    # by boot_agent (NOT built in _init) because the store's lifecycle is owned by the
    # session boot, and _init must stay constructible without one.
    session_store: Any = field(default=None)  # SessionStore | None
```

The dataclass is neither frozen nor slotted (`shared_services.py:66`), so adding the
field is safe and no construction site needs to change — every existing `cls(...)` call
supplies keywords only.

**Do not build a `SessionStore` inside `_init`.** `_init` runs on `get_or_create`, which
is called from paths that must not own the store's lifecycle, and it would open a second
connection to the same DB. Attach the one `boot_agent` already made.

### 5.2 Attach it at boot

`src/hachi/gateway/orchestrator.py`, immediately after `:3009`:

```python
    session_store = SessionStore()
    # P4-x: publish on the process singleton so the gateway's ingress-idempotency path
    # and core/cost.py reuse THIS store instead of opening (and leaking) a fresh
    # sqlite3/WAL connection per call. See BB-42 and its successor.
    _shared.session_store = session_store
```

### 5.3 Read it directly, and close what you open

**`fastapi_app.py:420-438`:**

```python
        shared = ProcessSharedServices.instance()
        store = shared.session_store if shared is not None else None
        if store is not None:
            return store
```

`getattr(..., None)` → direct attribute read. Once the field is declared, a typo becomes
an `AttributeError` instead of a silent `None` — that is the point (see
[T-14](T-14-ban-getattr-own-types.md)).

The fallback at `:434-436` still returns an unclosed store to a caller that cannot close
it. **Fix the contract, not just the branch.** Two acceptable shapes:

- *Preferred:* have `_resolve_session_store` return `None` when there is no shared store,
  and let the (single) caller skip idempotency recording rather than open a DB per
  message. Check the call site before choosing this — if idempotency is load-bearing for
  AUDIT P0-3, do not silently disable it.
- *Otherwise:* make the function a `contextlib.contextmanager` that yields the shared
  store unchanged and shuts down a fallback in its `finally`, mirroring
  `cost.py:311-320`. This changes the call site; keep the change mechanical.

Pick one, say which in the PR, and cover it with the §7 leak test.

**`fastapi_app.py:1013-1030`:** replace `hasattr(_shared, "session_store")` with a direct
`_shared.session_store is not None` check, and shut down the fallback in a `finally` the
way `cost.py` does. The `hasattr(_store, "delete_empty_sessions")` guard at `:1020` is
also a `getattr`-family smell — `SessionStore` either has that method or the code is
broken; grep and delete the guard if it does.

**`core/cost.py:106`:** `return getattr(shared, "session_store", None)` →
`return shared.session_store`. Then **update the BB-42 docstring above it** so it records
the recurrence instead of implying the class of bug was solved.

### 5.4 Make the failure loud (required)

In `fastapi_app._resolve_session_store`, the outer `except Exception: return None`
(`:437-438`) is marked `# pragma: no cover - store is best-effort; never break the turn`.
Keep the never-break behaviour, lose the silence:

```python
    except Exception:  # never break the turn — but never fail silently either
        _log.warning(
            "_resolve_session_store: could not resolve a SessionStore; durable ingress "
            "idempotency is disabled for this request",
            exc_info=True,
        )
        return None
```

## 6. Steps

1. Write the regression tests from §7 first. Run them. Watch them fail.
2. Add the `session_store` field to `ProcessSharedServices` (§5.1).
3. Assign it in `boot_agent` right after `orchestrator.py:3009` (§5.2).
4. `fastapi_app.py:431` — direct read; `:434-436` — fix the fallback lifecycle (§5.3).
5. `fastapi_app.py:1018-1027` — direct read; shut the fallback down.
6. `core/cost.py:106` — direct read; update the BB-42 docstring to record the recurrence.
7. `fastapi_app.py:437-438` — `logger.warning` (§5.4).
8. Run the tests. Watch them pass.
9. Run `uv run python scripts/preflight.py`. Report real counts.
10. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_shared_session_store.py` (new)
- **Test names:** `test_shared_services_declares_session_store`,
  `test_resolve_session_store_returns_the_shared_instance`,
  `test_resolve_session_store_does_not_leak_a_new_store_per_call`
- **It must assert:** **object identity** — that the resolver returns *the same object*
  that was attached, and that repeated calls do not mint new ones. An assertion that "a
  store was returned" passes against today's bug.
- **It must FAIL before your fix** with:
  `AssertionError: assert 'session_store' in {...}` on the first, and
  `AssertionError: assert <SessionStore at 0x…> is <SessionStore at 0x…>` on the second.

```python
# sketch — adapt to the repo's existing fixtures
import pytest

from hachi.gateway.shared_services import ProcessSharedServices


class _FakeStore:
    """Stands in for SessionStore — identity is all these tests care about."""

    def __init__(self) -> None:
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1


@pytest.fixture
def shared(tmp_path):
    ProcessSharedServices.clear()
    s = ProcessSharedServices.get_or_create(
        {"memory": {"backend": "in_memory"}},   # no ChromaDB — see §12
        str(tmp_path),
        force_reinit=True,
    )
    yield s
    ProcessSharedServices.clear()


def test_shared_services_declares_session_store() -> None:
    assert "session_store" in ProcessSharedServices.__dataclass_fields__, (
        "three call sites read ProcessSharedServices.session_store; it is declared nowhere"
    )


def test_resolve_session_store_returns_the_shared_instance(shared) -> None:
    from hachi.gateway.fastapi_app import _resolve_session_store

    store = _FakeStore()
    shared.session_store = store
    assert _resolve_session_store() is store, (
        "the resolver built a fresh SessionStore instead of reusing the shared one"
    )


def test_resolve_session_store_does_not_leak_a_new_store_per_call(shared) -> None:
    from hachi.gateway.fastapi_app import _resolve_session_store

    shared.session_store = _FakeStore()
    assert _resolve_session_store() is _resolve_session_store()
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

Add a fourth test for `core/cost.py`: attach a fake store, call
`_get_shared_session_store()`, assert identity. It fails today for the same reason.

If you take the context-manager option in §5.3, adapt the second and third tests to the
new call shape and add one asserting the *fallback* store's `shutdown()` was called
exactly once.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `"session_store" in ProcessSharedServices.__dataclass_fields__` is `True`.
- [ ] `grep -rn "getattr(.*session_store" src/` returns nothing.
- [ ] `grep -rn 'hasattr(.*"session_store"' src/` returns nothing.
- [ ] `_resolve_session_store()` returns the identical object attached by `boot_agent`.
- [ ] Every `SessionStore()` fallback that this code opens is shut down (mirroring
      `core/cost.py:311-320`), or the fallback is removed.
- [ ] The `except Exception: return None` in `_resolve_session_store` emits a
      `logger.warning`.
- [ ] The BB-42 docstring in `core/cost.py:96-99` records the recurrence.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not move `SessionStore` construction into `ProcessSharedServices._init`.** Its
  lifecycle is owned by `boot_agent` (which also hands it to `BootDeps`,
  `register_session_tools`, `set_session_store`, and the idle sweep). Building a second
  one in `_init` opens a second connection to `sessions.db` — the very problem you are
  fixing.
- **Do not add `session_store` to `_config_fingerprint`.** The fingerprint keys
  *construction* inputs (`shared_services.py:52-63`); the store is attached after the
  fact. (Contrast [T-06](T-06-memory-settings-reach-vault.md), where the memory settings
  genuinely *do* change what `_init` builds.)
- **Do not refactor `SessionStore` itself** — not its schema, not its migrations, not its
  WAL settings. The leak is at the call sites.
- **Do not fix the other `getattr` sites you will pass** (e.g.
  `getattr(fallback_store, "shutdown", None)` at `cost.py:318`, or `getattr(agent,
  "reindex_skills", None)` in `cli/main.py`). Those belong to
  [T-14](T-14-ban-getattr-own-types.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). If an existing test patches
  `_resolve_session_store` (its docstring says *"Patched in tests to point at an isolated
  DB"*), keep that seam working.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. This change makes a previously-dead branch live on
the hot message path — scoped runs will not surface cross-module regressions
(CLAUDE.md Rule 2). Run the FULL suite.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — `ProcessSharedServices.session_store` was read in three places and declared in none (BB-42 recurrence)

- **Symptom:** every "prefer the process-shared SessionStore" branch was dead. The
  gateway's durable ingress-idempotency path opened a brand-new `SessionStore()` **per
  message** — full schema init/migrations, and never shut down — holding a
  `sessions.db-wal`/`-shm` handle open for the life of the process. Windows gateways
  accumulated handles until restart.
- **Root cause:** `ProcessSharedServices` had no `session_store` field and nothing ever
  assigned one (`grep -rn "\.session_store\s*=" src/` → no hits), yet three sites read
  it: `gateway/fastapi_app.py` `_resolve_session_store` via
  `getattr(shared, "session_store", None)`, `gateway/fastapi_app.py`
  `cleanup_empty_sessions` via a `hasattr(_shared, "session_store")` guard, and
  `core/cost.py` `_get_shared_session_store` via another defaulted `getattr`. All three
  therefore always took the fallback. `boot_agent` already created the store and passed
  it to `BootDeps`, `register_session_tools`, `set_session_store`, and the idle sweep —
  but never attached it to `_shared`.
- **This is a BB-42 recurrence.** BB-42 was "imported a `_get_session_store` symbol that
  has never existed"; its fix reintroduced the same failure as "getattr an attribute
  that has never existed" — and the docstring describing BB-42 sits four lines above the
  new instance in `core/cost.py`.
- **Fix:** declared `session_store: Any = field(default=None)` on the dataclass, attached
  the store in `boot_agent` right after it is constructed, converted all three reads to
  direct attribute access (so a future typo is an `AttributeError`, not a silent `None`),
  made every remaining short-lived fallback shut itself down in a `finally` (mirroring
  the correct shape already in `core/cost.py`), and turned the resolver's blanket
  `except Exception: return None` into a `logger.warning`.
- **Avoid:** `getattr(x, "field", None)` / `hasattr(x, "field")` against one of OUR OWN
  types is not defensive — it converts "this attribute was never implemented" into a
  silently-taken fallback. Read declared attributes directly and let `AttributeError`
  be loud. And when you fix a bug of this class, grep for the *shape*, not just the
  symbol — BB-42 came back through a different syntax.
- **Locked by:** `tests/test_shared_session_store.py` —
  `test_resolve_session_store_returns_the_shared_instance`
```

## 12. Known traps

- **BB-6:** `ProcessSharedServices` is `None` before a session boots — `instance()`
  returning `None` is normal, and `_resolve_session_store` must still behave.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Related: build the singleton
  in tests with `{"memory": {"backend": "in_memory"}}` so `_init` skips ChromaDB
  entirely (`shared_services.py:300-307`).
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- `tests/conftest.py:75-90` autouse-clears `_INSTANCES` before every test; create your
  singleton inside a function-scoped fixture.
- The dataclass is **not** frozen and **not** slotted (`shared_services.py:66`) — adding a
  field is safe, and assigning an undeclared attribute would also "work", which is
  precisely how three readers came to reference a field nobody declared. Declaring it is
  what makes mypy and the reader agree.
- `SessionStore` opens SQLite in WAL mode; on Windows an unclosed handle blocks deletion
  of `sessions.db-wal`. If a test leaves one open, later tests can fail with "database is
  locked" or "disk image is malformed". Prefer the `_FakeStore` in §7 over a real store
  wherever identity is all you are asserting.
