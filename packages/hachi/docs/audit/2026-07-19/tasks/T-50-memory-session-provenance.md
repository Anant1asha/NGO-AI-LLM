# T-50 · Set `MemoryManager._session_id` so extracted facts carry real provenance

|  |  |
|---|---|
| **Source finding** | CF-12 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** — a real bug, not a refactor |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-48](T-48-memory-package-boundary.md) — land this before the package move so the diff stays reviewable |
| **Effort** | ~1 day |
| **Difficulty** | Low (the fix is three lines; the test is the work) |
| **Files you will touch** | `src/hachi/core/memory.py`, `src/hachi/gateway/orchestrator.py`, `tests/test_memory_session_provenance.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

`MemoryManager._session_id` is **read once and assigned never**. The single occurrence
in the 1,561-line `core/memory.py` is a `getattr(self, "_session_id", "")` with a
default that masks the missing attribute, so every background fact-extraction job is
enqueued with `session_id=""`. That empty string propagates all the way into the `.og`
memory graph: the `->[:evidence=session:...]` provenance edge is **omitted entirely**,
and every `event` node routes to `journal/unknown.og` instead of
`journal/<session-id>.og`.

When you are done, `MemoryManager` is told its session id at boot, extracted nodes
carry a real `evidence=session:` edge, event nodes land in the right journal file, and
a test asserts a non-empty session id on the extraction payload.

## 2. Why this matters

Every strategy document in this repo sells **verifiable, portable, owned** memory. The
`.og` graph is the artefact that claim rests on, and `evidence=session:<id>` is the
edge that makes a remembered fact traceable back to the conversation that produced it.
That edge has never been written for any fact the agent extracted on its own. The
provenance story — the thing that distinguishes this product's memory from a vector
blob — is broken at the first hop, in the one place a user cannot see it.

The routing damage is the visible half: `journal/unknown.og` accumulates every event
node from every session ever, in one flat file, while
`gateway/orchestrator.py:1835` writes *session-close episodes* to the correct
`journal/<real-id>.og`. The same directory contains both correct and broken routing,
which is why nobody noticed.

If the fix you are about to write does not end with "a fact extracted during session
`abc123` carries `->[:evidence=session:abc123]` on disk", stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The read — `core/memory.py:609`, in `MemoryManager.sync_turn`

```python
            session_id_val: str = getattr(self, "_session_id", "") or ""
            job = Job(
                job_id="",  # Assigned by queue
                name="fact_extraction",
                handler_name="extract_fact",
                payload={
                    "session_id": session_id_val,
                    "text": combined,
                    "typed": bool(self._memory_writer),
                },
                status=JobStatus.PENDING,
                job_type="sync",
            )
```

The `Job` payload spans `:610-621`; `"session_id": session_id_val` is `:615`.

### 3.2 There is exactly ONE occurrence of `_session_id` in the whole file, and it is that read

```bash
rg -n "_session_id" src/hachi/core/memory.py
# 609:            session_id_val: str = getattr(self, "_session_id", "") or ""
```

One hit. Confirm the negative too:

- `MemoryManager.__init__` (`core/memory.py:491-564`) sets `_history`, `_task_ledger`,
  `_active_skill`, `_skill_start_index`, `_max_active_messages`, `_max_active_tokens`,
  `_last_user_query`, `vault`, `job_queue`, `strict_errors`, `_memory_writer`,
  `_llm_client`, `_compaction_in_flight`, `_history_lock`. **Not `_session_id`.**
- There is no setter. `set_vault` (`:566`) and `set_memory_writer` (`:570`) exist as
  precedent; there is no `set_session_id`.
- Nothing assigns it from outside. `rg -n "memory\._session_id|memory_manager\._session_id" src/ tests/`
  returns **nothing**. (`gateway/orchestrator.py:652` assigns
  `self._session_id` on **`AgentSession`** — a different class. Do not confuse them.)

`getattr(self, "_session_id", "")` on an attribute the class never defines always
returns `""`. The `or ""` after it is dead code guarding against a `None` that cannot
occur.

### 3.3 The `getattr`-on-your-own-type pattern is what hid it

Had this been `self._session_id`, the first call to `sync_turn` would have raised
`AttributeError` in 2024 and been fixed the same day. The `getattr` default converted a
loud crash into a silent empty string. This is the exact pattern
[T-14](T-14-ban-getattr-own-types.md) bans — cross-link it in your commit message, and
if T-14 has already landed, this site is a violation its lint should have caught.

### 3.4 Where the empty value goes — the complete chain

The **only live extraction path** is the durable one. Verified: `_run_fact_extraction`
(`core/memory.py:639`) and `_run_typed_extraction` (`:663`) have **no callers in
`src/`** — only tests reach them. `sync_turn`'s no-queue branch (`:629-637`) just logs
a warning and returns. So `:609` is the single point where provenance is decided.

1. `core/memory.py:615` — payload `"session_id": ""`.
2. `core/runtime/job_handlers.py:168` — `payload: dict[str, Any] = {"session_id": session_id, "typed": typed}`.
3. `core/runtime/job_handlers.py:197-203`:
   ```python
        result: str = extract_facts(
            text,
            vault=ctx.vault,
            llm_client=ctx.llm_client,
            memory_writer=ctx.memory_writer,
            session_id=session_id or "",
        )
   ```
4. `core/memory.py:338-349` — the typed path builds nodes:
   ```python
            nodes.append(
                MemoryNode(
                    name=name,
                    role=role,
                    dense=str(raw.get("dense", ""))[:200],
                    keywords=list(raw.get("keywords", [])),
                    session_id=session_id,
                    ...
   ```
   `session_id=session_id` is `:344`.
5. `core/memory.py:351` — `written = memory_writer.write_nodes(nodes, session_id=session_id)`.

### 3.5 The two on-disk consequences — `core/memory_writer.py`

**(a) The provenance edge is not written at all.** `_node_block`, `:76-77`:

```python
    if session_id or node.session_id:
        lines.append(f"->[:evidence=session:{node.session_id or session_id}]")
```

With both empty the condition is `False` and the line is skipped. The `.og` node has
**no** `evidence` edge — not an empty one, none. Graph consumers cannot distinguish
"this fact has no session" from "this fact predates provenance".

**(b) Event nodes all collapse into one file.** `_route`, `:112-114`:

```python
    if role == "event":
        session = node.session_id or "unknown"
        return memory_dir / "journal" / f"{session}.og"
```

Every `event` node extracted from every session, ever, appends to
`memory/journal/unknown.og`.

Meanwhile `gateway/orchestrator.py:1835` writes session-close episodes correctly:

```python
                self.memory.write_episode(self._session_id, _summary)
```

— because `write_episode` (`core/memory.py:688-693`) takes the id as a *parameter*
from `AgentSession`, which has it. Same directory, same writer, two different
provenance outcomes.

### 3.6 The value exists three frames up — `gateway/orchestrator.py`

`AgentSession._session_id` is initialised at `:566` (`self._session_id: str | None = None`)
and assigned at `:652`, inside `set_session_store`:

```python
    def set_session_store(self, store: SessionStore, model: str = "unknown"):
        """Bind a SessionStore and start a new persistent session.

        Args:
            store: The SQLite-backed session store.
            model: The LLM model name for this session's metadata.
        """
        self._session_store = store
        self._session_id = store.start_session(model=model)
```

The session's own `MemoryManager` is `self.memory`. The fix is to tell it.

### 3.7 Why it survived — no test asserts a non-empty session id

`tests/test_durable_fact_extraction.py` exercises the enqueue path but asserts on
`text`/`typed`, not on `session_id`. `tests/test_p2_05_memory_writer.py` constructs
`MemoryNode(session_id=...)` **by hand** with a real value, so the writer's routing and
edge emission are covered — but nothing checks that the *production* caller supplies
one. That is the gap your regression test closes.

## 4. Reproduce the failure

The premise is mechanically checkable and decisive; the on-disk consequence needs a
short script. Both are given.

```bash
# 1. One occurrence of _session_id in the whole 1,561-line file — and it is a READ.
#    Expect: exactly one line, the getattr at :609.
rg -n "_session_id" src/hachi/core/memory.py

# 2. Nothing ever assigns it on a MemoryManager. Expect: NO output.
#    (orchestrator.py:652 assigns AgentSession._session_id — a different class.)
rg -n "memory\._session_id|memory_manager\._session_id" src/ tests/

# 3. There is no setter. Expect: set_vault and set_memory_writer only.
rg -n "def set_" src/hachi/core/memory.py
```

**You will see now:** (1) a single `getattr` read; (2) silence; (3) no
`set_session_id`. Together with `MemoryManager.__init__` (`:491-564`) not defining the
attribute, that proves the payload's `session_id` is always `""`.

Confirm the attribute genuinely does not exist — this is safe to run, `MemoryManager()`
does no I/O:

```bash
python -c "from hachi.core.memory import MemoryManager; m = MemoryManager(); print('has _session_id:', hasattr(m, '_session_id'))"
```

**You will see now:** `has _session_id: False`
**You should see after the fix:** `has _session_id: True` (initialised to `""`, then
assigned at boot).

And the on-disk consequence — this writes only into a temp directory:

```bash
python - <<'PY'
import tempfile, pathlib
from hachi.core.memory_writer import MemoryNode, MemoryWriter

d = pathlib.Path(tempfile.mkdtemp())
w = MemoryWriter(memory_dir=d)
# Exactly what extract_facts builds today: session_id="" from the empty payload.
w.write_nodes([MemoryNode(name="deploy-target", role="fact",
                          dense="the deploy target is fly.io")], session_id="")
w.write_nodes([MemoryNode(name="shipped-v1", role="event",
                          dense="shipped v1")], session_id="")
for p in sorted(d.rglob("*.og")):
    print("---", p.relative_to(d))
    print(p.read_text(encoding="utf-8"))
PY
```

**You will see now:** the fact node has **no** `->[:evidence=session:...]` line at all,
and the event node was written to `journal/unknown.og`.
**You should see after the fix** (re-run with a real id in place of `""`): the fact
node carries `->[:evidence=session:<id>]` and the event node lands in
`journal/<id>.og`.

## 5. What "fixed" looks like

No decision is required here; the shape is dictated by the existing `set_vault` /
`set_memory_writer` precedent.

1. `MemoryManager.__init__` declares the attribute so it is a real field, not a
   `getattr` guess:

   ```python
        # Session provenance: stamped onto every extracted MemoryNode so the .og
        # graph carries `evidence=session:<id>` edges and event nodes route to
        # journal/<session-id>.og.  Set by AgentSession.set_session_store().
        self._session_id: str = ""
   ```

2. A setter beside the existing two (`core/memory.py:566-572`):

   ```python
    def set_session_id(self, session_id: str) -> None:
        """Bind the owning session's id for memory-node provenance (T-50)."""
        self._session_id = session_id or ""
   ```

3. `core/memory.py:609` loses the `getattr`:

   ```python
            session_id_val: str = self._session_id
   ```

   Keep the surrounding comment block (`:600-606`) intact.

4. `AgentSession.set_session_store` (`gateway/orchestrator.py:644-652`) tells the
   manager:

   ```python
        self._session_store = store
        self._session_id = store.start_session(model=model)
        # T-50: propagate provenance so extracted facts carry evidence=session:<id>.
        if self.memory is not None:
            self.memory.set_session_id(self._session_id)
   ```

   Use whatever null-guard matches how `self.memory` is actually initialised on
   `AgentSession` — check before you write; do not assume it is always present at this
   point in boot.

5. Observable outcome: a fact extracted during a live session produces an `.og` node
   containing `->[:evidence=session:<that session's id>]`, and an `event` node lands in
   `memory/journal/<that session's id>.og` rather than `journal/unknown.og`.

**Explicitly NOT in the target state:** a migration that back-fills provenance onto
existing `unknown.og` nodes, or a merge of `journal/unknown.og` into per-session files.
See §9.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `self._session_id: str = ""` to `MemoryManager.__init__` with the comment from
   §5 item 1.
3. Add `set_session_id` beside `set_memory_writer` (`core/memory.py:570-572`).
4. Replace the `getattr` at `:609` with a direct attribute read.
5. Call `self.memory.set_session_id(...)` from `AgentSession.set_session_store`
   (`gateway/orchestrator.py:652`), immediately after `self._session_id` is assigned.
6. Check `resume_from_session` (`gateway/orchestrator.py:654`) — it does **not**
   reassign `self._session_id` (it reads `source_session_id` as a parameter), so no
   second call is needed there. Verify this yourself rather than trusting the sentence.
7. Run the regression test — it must now pass.
8. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_memory_session_provenance.py` (**new**)
- **Test names:** `test_sync_turn_enqueues_job_with_real_session_id` (the behavioural
  lock) and `test_written_node_carries_evidence_session_edge` (the on-disk proof)
- **It must assert:** the real, observed values — the `session_id` on the enqueued
  `Job.payload`, and the literal `->[:evidence=session:<id>]` text in the `.og` file on
  disk. Not that a mock was called.
- **It must FAIL before your fix** with:
  - test 1: `AssertionError: assert '' == 'sess-abc123'` — the payload carries an
    empty string today.
  - test 2 passes even before the fix **if you pass the id explicitly**, so it must
    drive the id through `MemoryManager`, not hand it to `write_nodes` directly.
    Written as below it fails with
    `AttributeError: 'MemoryManager' object has no attribute 'set_session_id'`.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path
from typing import Any

from hachi.core.memory import MemoryManager
from hachi.core.memory_writer import MemoryNode, MemoryWriter


class _CapturingQueue:
    """Minimal JobQueue stand-in that records what was enqueued."""

    def __init__(self) -> None:
        self.jobs: list[Any] = []

    def enqueue(self, job: Any) -> str:
        self.jobs.append(job)
        return "job-1"


def test_sync_turn_enqueues_job_with_real_session_id() -> None:
    """The fact-extraction job must carry the owning session's id.

    Regression (T-50): MemoryManager._session_id was read via
    getattr(self, "_session_id", "") and never assigned, so every extraction job
    was enqueued with session_id="" — .og nodes got no evidence=session: edge and
    every event node routed to journal/unknown.og.
    """
    queue = _CapturingQueue()
    mgr = MemoryManager(job_queue=queue)
    mgr.set_vault(object())          # sync_turn returns early without a vault
    mgr.set_session_id("sess-abc123")

    mgr.sync_turn(
        "I always deploy to fly.io, remember that.",
        "Noted — fly.io is your deploy target.",
    )

    assert queue.jobs, "no extraction job was enqueued"
    assert queue.jobs[0].payload["session_id"] == "sess-abc123"


def test_written_node_carries_evidence_session_edge(tmp_path: Path) -> None:
    """A node written with the manager's session id gets the provenance edge on disk."""
    writer = MemoryWriter(memory_dir=tmp_path)
    writer.write_nodes(
        [MemoryNode(name="deploy-target", role="fact", dense="deploy target is fly.io")],
        session_id="sess-abc123",
    )
    written = (tmp_path / "core_memory.og").read_text(encoding="utf-8")
    assert "->[:evidence=session:sess-abc123]" in written


def test_event_nodes_route_to_the_real_session_journal(tmp_path: Path) -> None:
    """Event nodes must not all collapse into journal/unknown.og."""
    writer = MemoryWriter(memory_dir=tmp_path)
    writer.write_nodes(
        [MemoryNode(name="shipped-v1", role="event", dense="shipped v1",
                    session_id="sess-abc123")],
        session_id="sess-abc123",
    )
    assert (tmp_path / "journal" / "sess-abc123.og").exists()
    assert not (tmp_path / "journal" / "unknown.og").exists()
```

> Test 1 is the behavioural lock — keep it even if you restructure the others.
> Tests 2 and 3 document the on-disk contract and will still pass if someone later
> reverts the plumbing, which is why test 1 must exist.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_sync_turn_enqueues_job_with_real_session_id` failed before the fix with `assert '' == 'sess-abc123'`.
- [ ] `rg -n "getattr\(self, \"_session_id\"" src/` returns **nothing**.
- [ ] `MemoryManager.__init__` declares `self._session_id: str = ""`.
- [ ] `AgentSession.set_session_store` calls `self.memory.set_session_id(...)`.
- [ ] A live session's extracted fact produces an `.og` node containing `->[:evidence=session:<id>]` (verify manually once with the §4 script, using a real id).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not write a migration for `journal/unknown.og`.** There is existing on-disk data
  in that file whose true session is unrecoverable. Back-filling it would mean
  *fabricating* provenance — in a product whose pitch is verifiable provenance. Leave
  the file alone; new nodes route correctly from the fix forward. If someone wants the
  historical data reconciled, that is a gardener task
  ([T-08](T-08-memory-gardener.md)) and it must be honest about what it does not know.
- **Do not start the package move.** [T-48](T-48-memory-package-boundary.md) relocates
  `core/memory.py` to `core/memory/manager.py`. If you do both, the three-line fix
  becomes invisible inside a rename. This is the most likely drift on this task — you
  will be editing a file that T-48 is about to move and it will feel efficient to
  combine them. It is not.
- **Do not fix `delete_fact`.** You will be reading `memory_writer.py` closely and will
  notice it has no deletion path at all. That is
  [T-51](T-51-memory-delete-tri-store.md).
- **Do not fix the other `getattr`-on-own-type sites.** [T-14](T-14-ban-getattr-own-types.md)
  owns the sweep. Fix this one because it is the bug; note the rest.
- **Do not "clean up" `_run_fact_extraction` / `_run_typed_extraction`** because §3.4
  shows they have no production callers. They are exercised by tests and deleting them
  is a separate scope call.
- **Do not widen the payload.** Adding `turn_id`, `user_id` or anything else to the
  extraction job is a different change with a different review.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** This changes the routing of every `event`
node the agent writes: files that used to land in `journal/unknown.og` now land in
`journal/<id>.og`. Any test that asserts on memory-directory contents, on
`load_memory_dir` results, or on graph-recall output may see a different file layout.
`tests/test_p2_05_memory_writer.py`, `tests/test_p3_01_memory_graph.py` and
`tests/test_knowledge_graph_recall.py` are the likely candidates — but a scoped run
over those three is not sufficient, because the extraction path also runs inside
gateway-booting tests.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `.og` memory provenance always empty: `MemoryManager._session_id` was never assigned

- **Symptom:** No fact the agent extracted for itself ever carried an
  `->[:evidence=session:<id>]` edge in the `.og` memory graph, and every `event` node
  from every session appended to a single `memory/journal/unknown.og` instead of
  `journal/<session-id>.og`. Nothing errored. Session-close *episodes* routed
  correctly, which made the breakage invisible — the same directory held both correct
  and broken output.
- **Root cause:** `MemoryManager.sync_turn` read the session id with
  `getattr(self, "_session_id", "")` (`core/memory.py:609`) — the only occurrence of
  `_session_id` in the 1,561-line file, and a read. `__init__` never defined the
  attribute and no setter existed, so the `getattr` default always won and the
  extraction job was enqueued with `session_id=""`. That empty string flowed through
  `handle_extract_fact` → `extract_facts` → `MemoryNode(session_id="")` →
  `MemoryWriter.write_nodes`, where `_node_block` skips the evidence edge entirely
  when the id is falsy and `_route` falls back to `journal/unknown.og`.
- **Fix:** Declared `self._session_id: str = ""` in `MemoryManager.__init__`, added
  `set_session_id()` beside the existing `set_vault`/`set_memory_writer` setters,
  replaced the `getattr` with a direct attribute read, and had
  `AgentSession.set_session_store` propagate the real id right after
  `store.start_session()`.
- **Avoid:** never `getattr(self, "_own_attribute", default)` on your own class — it
  converts an `AttributeError` you would fix in minutes into a silent default you ship
  for a year. If an attribute is optional, declare it in `__init__` with its default.
- **Locked by:** `tests/test_memory_session_provenance.py` — `test_sync_turn_enqueues_job_with_real_session_id`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. `conftest.py` warms the
  chromadb PyO3 native module at import so it loads exactly once per process; patching
  it out drops the compiled extension and every later chromadb test in the process
  dies with *"cannot load module more than once"*. The §7 tests need **no** chromadb —
  `sync_turn` only checks `if not self.vault:` (`core/memory.py:591`), so a bare
  `object()` sentinel is enough. Keep it that way.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Do not reach
  through it to find the session id — the value is already on `AgentSession` at the
  exact moment you need it (§3.6).
- **`AgentSession._session_id` and `MemoryManager._session_id` are different
  attributes on different classes.** Greps for `_session_id` return 41 hits in
  `gateway/orchestrator.py` alone, all of them the `AgentSession` one. Do not "find"
  the assignment there and conclude the bug is already fixed.
- **`set_session_store` may run before `self.memory` is assembled** depending on boot
  ordering. Read the construction order in `boot_agent` before adding the call, and
  guard accordingly — an `AttributeError` at boot is a worse bug than the one you are
  fixing.
- **`resume_from_session` (`gateway/orchestrator.py:654`) does not reassign
  `self._session_id`** — it takes `source_session_id` as a parameter and seeds history
  from it. Verify this yourself; if that ever changes, the propagation call needs to
  move.
- **`journal/unknown.og` may already be large** on a developer machine with history.
  Do not delete it as part of "testing the fix". It is real user data with no
  recoverable provenance (§9).
