# T-09 · Publish `file.extracted` to the real shared EventBus

|  |  |
|---|---|
| **Source finding** | CF-1 #6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~1–2 hours |
| **Difficulty** | Low (mechanical) — the correct accessor already exists and is used by three other modules |
| **Files you will touch** | `src/hachi/core/runtime/job_handlers.py`, `tests/test_file_extracted_event.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

`_emit_file_extracted` tries to reach the process EventBus by importing a module-level
name `_shared` from `hachi.gateway.orchestrator`. **That name does not exist at module
level** — it is a function-local variable inside `boot_agent`. The `ImportError` is
swallowed, so the function falls through to constructing a brand-new
subscriber-less `EventBus()` and publishes into it. `file.extracted` reaches nobody, ever.

The correct accessor already exists — `ProcessSharedServices.instance()` — and three
other modules already use it. When you are done, `_emit_file_extracted` uses it too, and
the fallback is a `logger.warning` instead of a silent no-op bus.

## 2. Why this matters

`file.extracted` is the signal that an uploaded attachment finished text extraction. It
is the event a UI needs to say "your PDF is ready" and the hook anything downstream would
subscribe to. Publishing it into a throwaway bus is indistinguishable, from the caller's
side, from publishing it correctly — which is exactly CF-1's idiom.

The fix is small and its shape matters more than its size: it keeps the runtime import
(required by layering) but makes it **correct** and **loud**. That is the template for
every other lazy cross-layer lookup in the codebase.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The broken emitter

`src/hachi/core/runtime/job_handlers.py:424-456` — `_emit_file_extracted`:

```python
def _emit_file_extracted(file_id: str, name: str, media_type: str, sidecar_id: str) -> None:
    """Publish ``file.extracted`` via a fresh in-process EventBus call."""
    try:
        from hachi.core.event_bus import EventBus
        from hachi.core.runtime_events import FILE_EXTRACTED, RuntimeEvent, now_iso

        # Fresh bus with no subscribers — publish propagates to any wired bus
        # only if it was injected.  We re-use the shared _shared bus when
        # available (best-effort; not required for correctness).
        bus: Any = None
        try:
            from hachi.gateway.orchestrator import _shared  # type: ignore[attr-defined]

            bus = getattr(_shared, "event_bus", None)
        except Exception:
            pass

        if bus is None:
            bus = EventBus()

        event = RuntimeEvent(
            name=FILE_EXTRACTED,
            payload={...},
            timestamp=now_iso(),
        )
        bus.publish(event)
    except Exception:
        logger.debug("_emit_file_extracted: publish failed (non-fatal)", exc_info=True)
```

The in-code comment at `:430-432` is itself wrong on two counts — publishing into a fresh
`EventBus()` does **not** "propagate to any wired bus", and the `_shared` reuse is not
"best-effort", it is *never*. **Correct the comment as part of the fix.**

Note the `# type: ignore[attr-defined]` at `:435` — someone hit the type error, silenced
it, and moved on. That comment is the tell.

### 3.2 `_shared` is not a module-level name — AST-verified

`hachi/gateway/orchestrator.py`'s module-level assignments are, in full:
`_SWEEP_INTERVAL_SECONDS` (`:2146`), `logger` (`:137`), `_CORE_TOOL_NAMES` (`:206`),
`_GROUP_BY_TOOL_NAME` (`:246`) — plus imports. There is **no module-level `_shared`**.

Its only binding is function-local, `src/hachi/gateway/orchestrator.py:2790-2792`:

```python
    from hachi.gateway.shared_services import ProcessSharedServices

    _shared = ProcessSharedServices.get_or_create(config, str(get_hachi_paths().data_dir))
```

Verify it yourself:

```bash
uv run python -c "
import ast
t = ast.parse(open('src/hachi/gateway/orchestrator.py', encoding='utf-8').read())
names = [x.id for n in t.body if isinstance(n, ast.Assign) for x in n.targets if isinstance(x, ast.Name)]
print(names)
print('_shared at module level?', '_shared' in names)
"
```

So the import at `:435` **always** raises `ImportError`, is swallowed at `:438-439`,
`bus` stays `None`, and `:442` builds `EventBus()` with zero subscribers.
`bus.publish(event)` at `:454` fans out to nothing.

### 3.3 The correct accessor — already used three times

`src/hachi/gateway/shared_services.py:111-125`:

```python
    @classmethod
    def instance(cls) -> ProcessSharedServices | None:
        """Return the most-recently-created singleton, or ``None`` if none exists yet.

        Used by ``resume.py`` and other internal callers that need the process bus
        or wait registry without knowing which config fingerprint was used at boot.
        ...
        """
        with _LOCK:
            if not _INSTANCES:
                return None
            return next(reversed(_INSTANCES.values()))
```

Existing callers: `src/hachi/core/cost.py:104`, `src/hachi/gateway/fastapi_app.py:430`,
`src/hachi/gateway/fastapi_app.py:1017`.

**Copy the shape at `src/hachi/core/cost.py:101-108`:**

```python
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        if shared is not None:
            return getattr(shared, "session_store", None)
    except Exception:
        pass
    return None
```

Copy the **import + `instance()`** shape — *not* the `getattr` on the last line. That
line is its own bug and is [T-10](T-10-shared-session-store.md)'s subject. `event_bus`
**is** a declared field on the dataclass (`shared_services.py:96`), so read it directly:
`shared.event_bus`.

### 3.4 The bus that should receive it

`src/hachi/gateway/orchestrator.py:2793-2796`, immediately after `_shared` is bound:

```python
    # Slice 2.2: publish the EventBus on the shared singleton so resume.py and
    # the observability sink (slice 2.3) can find it via ProcessSharedServices.instance().
    if _event_bus is not None:
        _shared.event_bus = _event_bus
```

The comment names the intended mechanism explicitly: **`ProcessSharedServices.instance()`**.
`_event_bus` is non-`None` only when `[events] bus_funnel = true`
(`orchestrator.py:2727-2730`) — so `shared.event_bus` being `None` is a legitimate
configuration state, not an error, and your fix must distinguish the two.

`FILE_EXTRACTED = "file.extracted"` — `src/hachi/core/runtime_events.py:60`.

## 4. Reproduce the failure

The import failure is directly reproducible:

```bash
uv run python -c "from hachi.gateway.orchestrator import _shared"
```

**You will see now:**

```
ImportError: cannot import name '_shared' from 'hachi.gateway.orchestrator'
```

**You should see after the fix:** the same error from this command — `_shared` is
correctly a local, and you are not adding a module global. What changes is that
`_emit_file_extracted` stops asking for it.

The *effect* (an event published into a bus with no subscribers) is **not** observable
from a shell: `EventBus.publish` on an empty bus succeeds silently. The code-reading
proof is §3.2 — the import raises, `:438-439` swallows it, `:441-442` builds a fresh bus.
The behavioural proof is the §7 test: subscribe to the shared bus, run the emitter,
observe zero deliveries.

## 5. What "fixed" looks like

```python
def _emit_file_extracted(file_id: str, name: str, media_type: str, sidecar_id: str) -> None:
    """Publish ``file.extracted`` on the process-shared EventBus.

    Layering: ``hachi.core.*`` must not import ``hachi.gateway`` at module scope
    (import-linter "the engine must not import the gateway service"). The lazy,
    inside-function import below is the sanctioned seam — it is listed in
    pyproject's ignore_imports for this module. Do NOT hoist it.
    """
    from hachi.core.runtime_events import FILE_EXTRACTED, RuntimeEvent, now_iso

    bus: Any = None
    try:
        from hachi.gateway.shared_services import ProcessSharedServices

        shared = ProcessSharedServices.instance()
        if shared is not None:
            bus = shared.event_bus
    except Exception:
        logger.warning(
            "_emit_file_extracted: could not reach ProcessSharedServices; "
            "file.extracted will not be delivered",
            exc_info=True,
        )

    if bus is None:
        # Legitimate when [events] bus_funnel=false or no session has booted (BB-6) —
        # but the event IS being dropped, so say so rather than publishing into a
        # throwaway bus that reaches nobody.
        logger.warning(
            "_emit_file_extracted: no shared EventBus (bus_funnel disabled or no live "
            "session) — dropping file.extracted for file_id=%s",
            file_id,
        )
        return

    try:
        bus.publish(
            RuntimeEvent(
                name=FILE_EXTRACTED,
                payload={
                    "file_id": file_id,
                    "name": name,
                    "media_type": media_type,
                    "sidecar_id": sidecar_id,
                },
                timestamp=now_iso(),
            )
        )
    except Exception:
        logger.warning("_emit_file_extracted: publish failed", exc_info=True)
```

Three deliberate changes:

1. **`ProcessSharedServices.instance()` replaces the nonexistent `_shared` import.**
2. **The throwaway `EventBus()` is deleted.** Constructing a bus nobody subscribes to is
   not a fallback; it is a way to make a dropped event look delivered. Drop it and say so.
3. **Every swallow becomes a `logger.warning`.** The outer `except Exception: logger.debug`
   at `:455-456` goes too — DEBUG is off in production, so it was equivalent to `pass`.

The `# type: ignore[attr-defined]` disappears with the bad import. If mypy complains
about `shared.event_bus` being `Any`, that is the dataclass's declared type
(`event_bus: Any = field(default=None)`, `shared_services.py:96`) — do not add a new
ignore.

**Layering — do NOT hoist the import.** `pyproject.toml` `[tool.importlinter]`, contract
*"the engine must not import the gateway service (freeze known seams)"* (`:213-237`),
lists `hachi.core.runtime.job_handlers -> hachi.gateway.orchestrator` in
`ignore_imports`. Your fix points at `hachi.gateway.shared_services` instead. **Check
whether that edge is already allowed**: the same list contains
`hachi.core.cost -> hachi.gateway.shared_services` and
`hachi.core.runtime.resume -> hachi.gateway.shared_services`, but **not**
`hachi.core.runtime.job_handlers -> hachi.gateway.shared_services`. Because
`allow_indirect_imports = "true"` and the contract checks direct edges, you will likely
need to add that entry — run `uv run lint-imports` and let it tell you. If you must add
it, add it **next to the existing seams with the same SEAM comment**, and say so in the
PR.

> This is exactly the **CF-17** complaint — runtime imports escaping the linter. The fix
> does not pretend to resolve CF-17: it keeps the runtime import, because layering
> requires it, but makes it **correct** and **loud**. State that trade-off in your commit
> message so the next reviewer does not "clean it up" by hoisting.

## 6. Steps

1. Write the regression test from §7 first. Run it. Watch it fail.
2. Rewrite `_emit_file_extracted` (`job_handlers.py:424-456`) per §5, including the
   corrected docstring/comment.
3. Run `uv run lint-imports`. If the `job_handlers -> shared_services` edge is rejected,
   add it to the frozen-seams `ignore_imports` list in `pyproject.toml` with a SEAM
   comment matching the neighbours.
4. Run the test. Watch it pass.
5. Run `uv run python scripts/preflight.py`. Report real counts.
6. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_file_extracted_event.py` (new)
- **Test names:** `test_file_extracted_reaches_the_shared_bus`,
  `test_file_extracted_warns_when_no_shared_bus`
- **It must assert:** a subscriber registered on the **shared** bus actually receives the
  event — i.e. real delivery, not that `publish` was called on a mock.
- **It must FAIL before your fix** with:
  `AssertionError: assert [] != []` / `assert 0 == 1` — the subscriber received nothing
  because the emitter published into its own throwaway bus.

```python
# sketch — adapt to the repo's existing fixtures
import logging

import pytest

from hachi.core.event_bus import EventBus
from hachi.core.runtime_events import FILE_EXTRACTED, RuntimeEvent
from hachi.core.runtime.job_handlers import _emit_file_extracted
from hachi.gateway.shared_services import ProcessSharedServices


@pytest.fixture
def shared_with_bus(tmp_path):
    """A real ProcessSharedServices carrying a real EventBus, like boot_agent builds."""
    ProcessSharedServices.clear()
    shared = ProcessSharedServices.get_or_create(
        {"memory": {"backend": "in_memory"}},   # avoid opening ChromaDB — see §12
        str(tmp_path),
        force_reinit=True,
    )
    shared.event_bus = EventBus()
    yield shared
    ProcessSharedServices.clear()


def test_file_extracted_reaches_the_shared_bus(shared_with_bus) -> None:
    received: list[RuntimeEvent] = []
    shared_with_bus.event_bus.subscribe(FILE_EXTRACTED, received.append)

    _emit_file_extracted("f-1", "report.pdf", "application/pdf", "sidecar-1")

    assert received, (
        "file.extracted never reached the shared EventBus — the emitter published "
        "into a freshly-constructed subscriber-less bus"
    )
    assert received[0].name == FILE_EXTRACTED
    assert received[0].payload["file_id"] == "f-1"
    assert received[0].payload["sidecar_id"] == "sidecar-1"


def test_file_extracted_warns_when_no_shared_bus(caplog) -> None:
    ProcessSharedServices.clear()          # BB-6: no singleton at all
    with caplog.at_level(logging.WARNING):
        _emit_file_extracted("f-2", "x.txt", "text/plain", "sidecar-2")
    assert any("file.extracted" in r.message for r in caplog.records), (
        "a dropped event must be loud — this is the 'make failure visible' half of the fix"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second test is the "make it loud" half and is **not optional** — it is what stops
this regressing into a silent drop again.

Check `EventBus.subscribe`'s real signature at `src/hachi/core/event_bus.py:87-93`
(`pattern`, `handler`, `mode="sync"`, `name=None`) before writing the sketch — the
handler receives a `RuntimeEvent`.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist, and failed before the fix.
- [ ] `grep -rn "from hachi.gateway.orchestrator import _shared" src/` returns nothing.
- [ ] `grep -n "EventBus()" src/hachi/core/runtime/job_handlers.py` returns nothing (the
      throwaway bus is gone).
- [ ] A subscriber on `ProcessSharedServices.instance().event_bus` receives
      `file.extracted`.
- [ ] Every former swallow in `_emit_file_extracted` is a `logger.warning`; no
      `logger.debug`-only path remains.
- [ ] The wrong comment at `job_handlers.py:430-432` is corrected.
- [ ] `uv run lint-imports` passes (add the seam entry if required, with a comment).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not hoist the `hachi.gateway.shared_services` import to module scope.** It is
  forbidden by the import-linter contract at `pyproject.toml:213-237` and would fail the
  gate. The lazy in-function import is the sanctioned pattern.
- **Do not "fix" the layering properly** by introducing a control-plane protocol owned by
  `core`. That is the burn-down noted in the `ignore_imports` comment and is owned by
  [T-68](T-68-import-linter-exemption-burndown.md) (with
  [T-42](T-42-retire-core-cli-seam.md) for the `core→cli` seam). You are correcting a
  broken lookup, not re-architecting the seam.
- **Do not add a module-level `_shared` to `orchestrator.py`** to make the original
  import work. That would make `boot_agent` mutate module state and reintroduce exactly
  the shared-mutable-global pattern `ProcessSharedServices` exists to replace.
- **Do not fix `getattr(shared, "session_store", None)` in `core/cost.py:106`** while you
  are in there — that is [T-10](T-10-shared-session-store.md).
- **Do not touch `handle_auto_extract`** (`job_handlers.py:~390-421`), the caller. Its own
  `except Exception: logger.debug` sites around ChromaDB indexing are a separate finding.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run lint-imports                          # layering — run this one explicitly
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — `file.extracted` was published into a throwaway EventBus and reached nobody

- **Symptom:** the `file.extracted` runtime event never arrived — no SSE delivery, no
  subscriber invocation — after an attachment finished text extraction. No error was
  logged, because the publish itself "succeeded".
- **Root cause:** `_emit_file_extracted` (`core/runtime/job_handlers.py`) did
  `from hachi.gateway.orchestrator import _shared` inside a try/except. `_shared` is not
  a module-level name in `orchestrator.py` (AST-verified: the only module-level assigns
  are `logger`, `_SWEEP_INTERVAL_SECONDS`, `_CORE_TOOL_NAMES`, `_GROUP_BY_TOOL_NAME`) —
  it is a local inside `boot_agent`. The `ImportError` was swallowed, `bus` stayed
  `None`, and the code then constructed a fresh subscriber-less `EventBus()` and
  published into that. The correct accessor, `ProcessSharedServices.instance()`, already
  existed and was already used by `core/cost.py` and `gateway/fastapi_app.py`. A
  `# type: ignore[attr-defined]` on the bad import had silenced the type checker.
- **Fix:** switched to `ProcessSharedServices.instance().event_bus`, deleted the
  throwaway `EventBus()` fallback (a bus with no subscribers is a dropped event, not a
  degraded one), and turned every swallow into a `logger.warning` — including an
  explicit warning when there is no shared bus at all.
- **Avoid:** never import a private name from another module's *function* scope and
  assume it is a module global — grep for a module-level binding first. And never
  "degrade" by constructing an empty sink: a publish into a subscriber-less bus is
  indistinguishable from success at the call site. When a `# type: ignore[attr-defined]`
  is needed to make an import type-check, the import is probably wrong.
- **Locked by:** `tests/test_file_extracted_event.py` —
  `test_file_extracted_reaches_the_shared_bus`
```

## 12. Known traps

- **BB-6:** `ProcessSharedServices` is `None` before a session boots. `instance()`
  returning `None` is a normal state, not an error — handle it explicitly (that is the
  second test).
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Related: build your test's
  singleton with `{"memory": {"backend": "in_memory"}}` so `_init` does **not** construct
  a ChromaDB `PersistentClient` (`shared_services.py:300-307`) — you only need the bus.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- `tests/conftest.py:75-90` autouse-clears `_INSTANCES` **before every test**, so a
  singleton created in a module-scoped fixture will be gone by the time your test body
  runs. Create it inside a function-scoped fixture (as sketched).
- `event_bus` is typed `Any` on the dataclass (`shared_services.py:96`) — mypy will not
  catch a typo in the attribute name. Read it in exactly one place.
- `EventBus.publish` assigns a monotonic sequence number and fans out under a lock
  (`event_bus.py:62-66`); async subscribers dispatch through the job queue. Your test's
  `subscribe(..., mode="sync")` default runs inline, which is what you want.
