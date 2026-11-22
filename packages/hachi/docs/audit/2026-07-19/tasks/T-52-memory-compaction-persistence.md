# T-52 · Persist compaction checkpoints so resumed sessions match live ones

|  |  |
|---|---|
| **Source finding** | CF-12 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | [T-48](T-48-memory-package-boundary.md) — land this before the package move |
| **Effort** | ~2 days |
| **Difficulty** | Medium — the write is easy; deciding what a resumed session should *see* is the work (§5) |
| **Files you will touch** | `src/hachi/core/memory.py`, `src/hachi/gateway/orchestrator.py`, `tests/test_compaction_checkpoint_persistence.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

When a session's context exceeds its budget, `MemoryManager` compacts it: the dropped
messages are replaced in `_history` by a **checkpoint** message summarising them. That
checkpoint exists only in the live process's Python list. Session persistence writes
exactly two row types per turn — `user` and `assistant` — so when a session is resumed
later, the compacted middle of the conversation is simply **absent**: the raw messages
were dropped from context and the summary that replaced them was never stored.

A resumed session therefore silently has weaker context than the live one it continues.
Nothing errors and nothing warns.

When you are done, compaction checkpoints are persisted to `SessionStore` as a distinct
row type, `resume_from_session` replays them in order, and a test proves a resumed
session recovers the checkpoint.

## 2. Why this matters

"Resume where you left off" is a promise about *equivalence*. A user who resumes a long
session reasonably expects the agent to know what it knew — and the agent, having no
way to detect the gap, will confidently answer from an incomplete picture rather than
say "I've lost the earlier part of this conversation". That is the silent-degradation
pattern the audit called the project's defining risk: not a missing feature, a feature
quietly doing less than it says.

There is a second, cheaper reason: the summary is *already generated*. A background LLM
job produces a real structured summary, applies it to the in-memory list, and then the
process exits and it is thrown away. Money was spent on a token that is discarded by
design.

If the fix you are about to write does not end with "a resumed session's history
contains the checkpoint text", stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The placeholder is inserted synchronously — `core/memory.py:1218-1221`

Inside `_sliding_window_compact`, the queued branch:

```python
                summary = (
                    "[Context compacted asynchronously. "
                    "Permanent facts are being flushed to Long-Term Memory in the background.]"
                )
```

The no-queue fallback at `:1230` generates the real summary inline instead:

```python
                summary = self._generate_structured_summary(dropped_messages)
```

### 3.2 The checkpoint message — `core/memory.py:1232-1240`

```python
            checkpoint = Message(
                role="user",
                content=(
                    f"[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]\n{summary}"
                ),
            )

            with self._history_lock:
                self._history = anchor + [checkpoint] + recent
```

Note `role="user"` — the checkpoint is disguised as a user message so the LLM sees it,
with the `DO NOT RESPOND` framing doing the work. That detail matters for §5.

### 3.3 The real summary is produced in the background and applied in memory only

Enqueued at `core/memory.py:1197-1211`, guarded by `_compaction_in_flight`:

```python
                if not self._compaction_in_flight:
                    self._compaction_in_flight = True
                    summary_job = Job(
                        job_id="",
                        name="generate_structured_summary",
                        status=JobStatus.PENDING,
                        func=self._run_and_clear_summary_job,
                        args=(dropped_messages,),
                        job_type="background",
                    )
```

`_run_and_clear_summary_job` — `core/memory.py:1378`:

```python
        try:
            summary = self._generate_structured_summary(messages)
            self._apply_summary_to_history(summary)
            return summary
        finally:
            self._compaction_in_flight = False
```

`_apply_summary_to_history` — `core/memory.py:1410` (the audit cites `:1409`; verified,
the `def` is `:1410`). The mutation is at **`:1430`** (the audit cites `:1428`; that is
the sentinel comparison, `:1430` is the write):

```python
        new_content = f"[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]\n{summary}"
        with self._history_lock:
            for msg in self._history:
                if (
                    isinstance(msg.content, str)
                    and self._COMPACTION_PLACEHOLDER_SENTINEL in msg.content
                ):
                    msg.content = new_content
                    logger.debug("Compaction summary applied back to live history checkpoint.")
                    return
```

`_COMPACTION_PLACEHOLDER_SENTINEL` is `"[Context compacted asynchronously."`
(`core/memory.py:1376`). The mutation is `msg.content = ...` on an object in the live
`_history` list. **Nothing writes it anywhere else.**

### 3.4 Session persistence writes only user/assistant — `gateway/orchestrator.py:1711-1716`

```python
        if self._session_store and self._session_id:
            try:
                self._session_store.log_message(self._session_id, "user", user_input)
                self._session_store.log_message(
                    self._session_id, "assistant", response or "", model=self.model_name or None
                )
```

Two rows per turn. `log_message` (`core/session_store.py:630-637`) accepts an arbitrary
`role: str` — its docstring says *"'user', 'assistant', or 'tool'"* (`:648`) — and the
`messages` table (`core/session_store.py:92-101`) declares `role TEXT NOT NULL` with
**no CHECK constraint**. So a new role value is schema-legal with no migration.

**The checkpoint is never logged.** `rg -n "log_message" src/` returns no call with a
checkpoint or system role.

### 3.5 Resume filters out anything that is not user/assistant — `gateway/orchestrator.py:675-684`

```python
        for row in rows:
            role = str(row.get("role", ""))
            content = row.get("content") or ""
            if role not in {"user", "assistant"} or not content:
                continue
            seeded.append(Message(role=role, content=content))
            transcript.append((role, content))

        self._resumed_transcript = transcript
        return self.memory.seed_history(seeded)
```

**`:678` is the second half of the fix.** Persisting a checkpoint row without widening
this allow-set changes nothing.

### 3.6 ⚠️ The comment names a method that does not exist

`core/memory.py:1185-1191`:

```python
                # HIGH-015: Enqueue the structured summary LLM call as a background job
                # instead of blocking prepare_for_turn().  A lightweight placeholder
                # checkpoint is inserted immediately so the history stays valid and the
                # loop continues.  The background job will update the checkpoint text
                # only when callers explicitly request it via get_pending_summaries(); in
                # practice the placeholder is sufficient for continuity because the
                # model has seen the full history and carries it in its own context.
```

`get_pending_summaries` **does not exist anywhere in the repository**:

```bash
rg -n "get_pending_summaries" .
# .\src\hachi\core\memory.py:1189:  ... via get_pending_summaries(); in
```

Exactly one hit — this comment. There is no such method on `MemoryManager`, no caller,
no test, no doc. The comment describes a design that was never built (the real
mechanism is the sentinel-scan apply-back in §3.3), and it actively misleads anyone
trying to find where summaries are collected. **Correcting it is part of this task.**

The same comment's closing claim — *"the placeholder is sufficient for continuity
because the model has seen the full history and carries it in its own context"* — is
true for a **live** session and false for a **resumed** one. That sentence is the exact
assumption this task invalidates; rewrite it rather than deleting it
([CLAUDE.md](../../../../CLAUDE.md) Rule 3).

### 3.7 Why it survived — the tests assert the in-memory path only

`tests/test_compaction_summary_applyback.py` covers all four in-process behaviours
(placeholder replaced, no-op when re-compacted, synchronous fallback, in-place mutation
on the same `Message` object) — its module docstring, `:1-13`, enumerates them. Every
assertion is against `_history`. **No test asserts that a checkpoint survives a
`SessionStore` round trip**, because until now nothing claimed it should.

## 4. Reproduce the failure

The absence of a persistence call is decisive by grep; the resume consequence needs a
round trip. Both are given. **A full end-to-end reproduction requires an LLM-backed
session long enough to trigger compaction, so the shell steps below prove the mechanism
rather than staging a real conversation — do not pretend a `hachi run` one-liner
demonstrates this.**

```bash
# 1. Every log_message call in the codebase. Expect: only "user", "assistant"
#    (plus "tool" in tests). No checkpoint / system row anywhere.
rg -n "log_message\(" src/

# 2. The resume filter that would drop a checkpoint even if it were persisted.
#    Expect: role not in {"user", "assistant"} -> continue
rg -n "role not in" src/hachi/gateway/orchestrator.py

# 3. The method the code says callers use to collect summaries.
#    Expect: exactly ONE hit — the comment itself.
rg -n "get_pending_summaries" .
```

**You will see now:** (1) two `log_message` roles, neither a checkpoint;
(2) the allow-set at `orchestrator.py:678`; (3) a single hit inside a comment at
`core/memory.py:1189`, proving `get_pending_summaries()` does not exist.

**You should see after the fix:** (1) a third `log_message` call carrying the
checkpoint role; (2) an allow-set that includes it; (3) no hit at all — the comment is
corrected.

The round trip — this exercises the real `SessionStore` against a temp DB:

```bash
python - <<'PY'
import tempfile, pathlib
from hachi.core.session_store import SessionStore

db = pathlib.Path(tempfile.mkdtemp()) / "sessions.db"
store = SessionStore(db_path=str(db))
sid = store.start_session(model="test")

store.log_message(sid, "user", "first message")
# This is what compaction produces today — and what is NEVER written:
CHECKPOINT = "[CONTEXT CHECKPOINT — REFERENCE ONLY, DO NOT RESPOND TO THIS]\n## Active Task ..."
store.log_message(sid, "assistant", "reply")

rows = store.get_session_messages(sid)
print("roles persisted:", [r["role"] for r in rows])
print("checkpoint present:", any(CHECKPOINT[:20] in (r["content"] or "") for r in rows))
store.shutdown()
PY
```

**You will see now:** `roles persisted: ['user', 'assistant']`, `checkpoint present: False`.
**You should see after the fix:** the production compaction path adds a third row, and
`resume_from_session` seeds it back into `_history`.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> Persisting the checkpoint is trivial. Deciding **which** checkpoint, and **what a
> resumed session sees**, is not. Pick before you type:
>
> **(A) Persist the checkpoint once, and UPDATE the row when the real summary lands. — RECOMMENDED.**
> `_sliding_window_compact` logs the placeholder row immediately (so a crash before the
> background job finishes still leaves a marker), and `_apply_summary_to_history`
> (`core/memory.py:1410`) updates that same row when the real summary arrives — mirroring
> exactly what it already does to the in-memory `Message`.
> *For:* the persisted transcript converges on the same content the live session holds;
> a crash mid-compaction leaves an honest "context was compacted here" marker rather
> than a silent hole; symmetrical with the existing sentinel apply-back, so there is one
> mechanism, not two.
> *Against:* needs an `UPDATE` path on `SessionStore`, which today is append-only for
> messages. That is a real new method (see the trap in §12) and it is where the effort
> in this task actually goes.
>
> **(B) Persist only the final summary, when the background job completes.**
> *For:* no `UPDATE` needed; one row, always the real content.
> *Against:* if the process dies between compaction and job completion — the exact
> window that makes this bug matter — **nothing** is persisted and the gap is silent
> again. It optimises away the failure mode you are fixing.
>
> **(C) Persist the dropped raw messages instead of the summary.**
> *For:* no information loss at all; resume could replay the true history.
> *Against:* the raw messages were dropped *because* they exceeded the context budget.
> Replaying them on resume reproduces the overflow immediately, and the very next turn
> re-compacts them — at the cost of another summarisation LLM call. It also inflates
> `sessions.db` with content the design deliberately discarded. Do not choose this.
>
> **Recommendation: (A).** The rest of this spec assumes it.
>
> **Second decision — the role value.** Use a distinct role, not `"user"`.
> `"system"` is the natural name and is schema-legal (§3.4). Do **not** reuse `"user"`
> merely because the in-memory `Message` does (`core/memory.py:1233`): a persisted
> `user` row is indistinguishable from something the human typed, and it will appear as
> a user message in `GET /sessions/{id}/messages` and in `hachi session show`. The
> in-memory role can stay `"user"` (that is an LLM-API concern); the persisted role must
> be honest about provenance.

### Target state

1. `SessionStore` gains a narrow update capability — e.g.
   `update_message_content(message_id, content)` — returning the row id from
   `log_message` (or a dedicated `log_checkpoint` that returns its id). Keep the surface
   minimal; this is not a general message-mutation API.
2. `_sliding_window_compact` persists the checkpoint right after splicing it into
   `_history` (`core/memory.py:1240`), recording the returned row id on the manager so
   the background job can find it.
3. `_apply_summary_to_history` (`core/memory.py:1410`) updates that row alongside the
   in-memory `Message`, under the same `_history_lock` acquisition it already takes.
   When the row id is absent (no session store bound — the legacy/test path), it is a
   no-op, exactly as the in-memory apply-back already no-ops when the placeholder is
   gone (`:1433-1438`).
4. `resume_from_session` (`gateway/orchestrator.py:675-684`) widens `:678`'s allow-set
   to include the checkpoint role and seeds it as a `Message(role="user", ...)` — the
   same disguise the live path uses, so the LLM sees it identically.
5. `SessionStore` is documented as **the single durable transcript**. Add that sentence
   to the class docstring: `_history` is the live working set, `.og` memory is extracted
   facts, and `sessions.db` is the record. Today a reader has to infer it.
6. The `get_pending_summaries()` comment (`core/memory.py:1185-1191`) is corrected to
   describe the sentinel apply-back that actually exists, and its "the placeholder is
   sufficient for continuity" claim is amended to note that this held only for live
   sessions and is why resumed sessions were weaker.

**Explicitly NOT in the target state:** rendering checkpoints in the chat UI. §9.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add the narrow update path to `SessionStore` (§5 item 1), with its own unit test for
   the `UPDATE` alone.
3. Persist the checkpoint in `_sliding_window_compact` after `:1240`, storing the
   returned row id on `MemoryManager`. It needs a `SessionStore` reference — check how
   `MemoryManager` is wired at boot before inventing a new injection path; prefer the
   existing `set_*` setter idiom (`core/memory.py:566-572`) over a constructor change.
4. Update the persisted row from `_apply_summary_to_history` (`:1410-1432`), inside the
   existing lock, no-oping when no row id is recorded.
5. Widen the resume allow-set at `gateway/orchestrator.py:678`.
6. Correct the comment at `core/memory.py:1185-1191` (§5 item 6) — **rewrite, do not
   delete** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
7. Add the "single durable transcript" sentence to `SessionStore`'s class docstring.
8. Run the regression test — it must now pass.
9. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_compaction_checkpoint_persistence.py` (**new**)
- **Test names:** `test_compaction_checkpoint_survives_a_session_round_trip` (the lock),
  `test_background_summary_updates_the_persisted_checkpoint`, and
  `test_persisted_checkpoint_is_not_logged_as_a_user_message`
- **It must assert:** the real, observed transcript — the row is in `sessions.db` after
  compaction, and `resume_from_session` puts its text back into `_history`. Not that a
  mock store was called.
- **It must FAIL before your fix** with:
  `AssertionError: no checkpoint row persisted; roles were ['user', 'assistant']`

```python
# sketch — adapt to the repo's existing fixtures.
# tests/test_compaction_summary_applyback.py has the established pattern for
# driving compaction with InMemoryJobQueue + a fake LLM client — reuse it.
from pathlib import Path

from hachi.core.llm import Message
from hachi.core.memory import MemoryManager
from hachi.core.session_store import SessionStore

_SENTINEL = MemoryManager._COMPACTION_PLACEHOLDER_SENTINEL
_CHECKPOINT_MARKER = "[CONTEXT CHECKPOINT"


def test_compaction_checkpoint_survives_a_session_round_trip(tmp_path: Path) -> None:
    """A compaction checkpoint must be in the durable transcript, not only in RAM.

    Regression (T-52): compaction replaced dropped messages with a checkpoint that
    lived only in MemoryManager._history. Session persistence wrote user/assistant
    rows only, so a resumed session silently lost the compacted middle of the
    conversation with no error and no warning.
    """
    store = SessionStore(db_path=str(tmp_path / "sessions.db"))
    try:
        session_id = store.start_session(model="test")

        mgr = MemoryManager(max_active_messages=6)
        mgr.set_session_store(store, session_id)      # the wiring you add in step 3
        for i in range(12):
            mgr.add_message(Message(role="user", content=f"message {i}"))
            mgr.add_message(Message(role="assistant", content=f"reply {i}"))
        mgr.prepare_for_turn()                        # triggers _sliding_window_compact

        rows = store.get_session_messages(session_id, limit=200)
        roles = [r["role"] for r in rows]
        assert any(_CHECKPOINT_MARKER in (r["content"] or "") for r in rows), (
            f"no checkpoint row persisted; roles were {roles}"
        )
    finally:
        store.shutdown()


def test_persisted_checkpoint_is_not_logged_as_a_user_message(tmp_path: Path) -> None:
    """The checkpoint must be distinguishable from something the human typed."""
    ...  # assert the row's role is the dedicated checkpoint role, not "user"


def test_background_summary_updates_the_persisted_checkpoint(tmp_path: Path) -> None:
    """When the real summary lands, the persisted row converges on it."""
    ...  # run the queued summary job, then assert the sentinel is gone from the DB row
```

Notes for whoever writes this for real:

- Drive compaction the way `tests/test_compaction_summary_applyback.py` does — it
  already has `_FakeLLMClient` and `InMemoryJobQueue`/`JobWorker` wiring. **Reuse it;
  do not invent a second harness.**
- `mgr.prepare_for_turn()` is the method that triggers compaction; confirm the exact
  entry point in `core/memory.py` before writing the test rather than trusting this
  sketch.
- Test 1 is the behavioural lock. Test 3 is the one that will catch a partial
  implementation that persists the placeholder and never converges.
- No ChromaDB is needed anywhere here. Keep it that way — §12 (BB-3).

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_compaction_checkpoint_survives_a_session_round_trip` failed before the fix with `roles were ['user', 'assistant']`.
- [ ] `rg -n "get_pending_summaries" .` returns **nothing** — the phantom-method comment is corrected.
- [ ] A compaction checkpoint appears in `sessions.db` with a role that is **not** `"user"`.
- [ ] `resume_from_session` seeds the checkpoint back into `_history` (assert on `mgr.history`, not on the DB).
- [ ] When the background summary job completes, the persisted row no longer contains `_COMPACTION_PLACEHOLDER_SENTINEL`.
- [ ] `SessionStore`'s class docstring states it is the single durable transcript.
- [ ] The `GET /sessions/{id}/messages` response and `hachi session show` were checked by hand — a checkpoint row must not render as a user turn (§12).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not start the package move.** [T-48](T-48-memory-package-boundary.md) relocates
  `core/memory.py`. Doing both hides this change inside a rename.
- **Do not render checkpoints in the chat UI.** A "context was compacted here" marker
  in the conversation view is a defensible product idea and a separate, frontend-owned
  change with its own design review. This task makes the data exist; it does not
  surface it. Confirm only that it does not *accidentally* surface (§12).
- **Do not persist the dropped raw messages** (§5 option C). They were dropped for a
  reason.
- **Do not build a general message-mutation API on `SessionStore`.** The messages table
  is append-only today and that is a property worth keeping. Add the narrowest possible
  update — one column, one row, one caller.
- **Do not "fix" the `role="user"` disguise on the in-memory `Message`**
  (`core/memory.py:1233`). It is how the checkpoint reaches the LLM and changing it
  alters prompt shape. The persisted role is a separate concern.
- **Do not touch the `_compaction_in_flight` guard** (`core/memory.py:1197-1216`) or the
  `_MAX_COMPACT_PASSES` retry loop (`:1243-1262`). Compaction policy is not in scope;
  only the persistence of its output is.
- **Do not fix other memory findings you notice.** `_session_id` is
  [T-50](T-50-memory-session-provenance.md); `delete_fact` is
  [T-51](T-51-memory-delete-tri-store.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** You are adding a row type to `sessions.db`
that many surfaces read: `GET /sessions/{id}/messages` (`gateway/fastapi_app.py:1037`),
history replay (`gateway/control_plane.py:599-634`), `hachi session show`
(`cli/commands/session.py:87`, `:280`, `:547`), and session search. Any test that
asserts a message *count* on a compacted session will change. A scoped run over
`tests/test_compaction_*.py` will pass and prove nothing.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Resumed sessions silently lost their compacted context

- **Symptom:** A resumed long session had weaker context than the live session it
  continued. The compacted middle of the conversation was simply absent — the raw
  messages had been dropped from context and the checkpoint that replaced them was
  never stored. No error, no warning; the agent answered confidently from an
  incomplete picture.
- **Root cause:** `MemoryManager._sliding_window_compact` spliced a checkpoint
  `Message` into `_history` (`core/memory.py:1232-1240`), and the background
  `_run_and_clear_summary_job` → `_apply_summary_to_history` mutated `msg.content`
  **in the in-memory list only** (`core/memory.py:1430`). Session persistence wrote
  exactly two rows per turn — `log_message(..., "user", ...)` and `"assistant"`
  (`gateway/orchestrator.py:1713-1716`) — so the checkpoint never reached
  `sessions.db`. `resume_from_session` additionally filtered anything outside
  `{"user", "assistant"}` (`gateway/orchestrator.py:678`), so persisting alone would
  not have been enough. A stale comment (`core/memory.py:1189`) pointed readers at a
  `get_pending_summaries()` method that has never existed anywhere in the repo.
- **Fix:** Persist the checkpoint as a dedicated non-user role row when compaction
  fires; update that row in place when the background summary lands (mirroring the
  existing sentinel apply-back); widen the resume allow-set; document `SessionStore` as
  the single durable transcript; correct the phantom-method comment.
- **Avoid:** if state is only in a Python list, it does not survive a restart — say so
  out loud in the code. And never leave a comment naming a method that does not exist:
  it sends the next reader hunting for a mechanism that was never built.
- **Locked by:** `tests/test_compaction_checkpoint_persistence.py` — `test_compaction_checkpoint_survives_a_session_round_trip`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. `conftest.py` warms the
  chromadb PyO3 native module at import so it loads exactly once per process; patching
  it out breaks every later chromadb test in the process. Nothing in this task needs
  chromadb — `MemoryManager` compaction runs without a vault. Keep the tests
  Chroma-free.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Do not reach
  through it to find the `SessionStore`; wire it into `MemoryManager` explicitly (§6
  step 3).
- **`log_message` defers its COMMIT.** `core/session_store.py:638-644`: the `INSERT`
  runs immediately but the `COMMIT` is batched by `_BATCH_SIZE`, a timer, or an explicit
  `flush_sync()`. A test that opens a *second* connection to assert the row exists will
  see nothing. `get_session_messages` calls `flush_sync()` first (`:864`) — use it, and
  do not "fix" the batching.
- **A `system` row will appear in `GET /sessions/{id}/messages`.**
  `gateway/fastapi_app.py:1037` returns the rows as stored. History **replay** is safe —
  `gateway/control_plane.py:602-634` handles only `user` and `assistant` and falls
  through silently on anything else — but the raw messages endpoint does not filter.
  Check the frontend's rendering of an unknown role before you ship, and check
  `hachi session show` (`cli/commands/session.py:87`).
- **`_apply_summary_to_history` may find no placeholder** and returns silently
  (`core/memory.py:1433-1438`) when a later compaction rebuilt `_history`. Your DB
  update must handle the same case — the row id may point at a checkpoint that is no
  longer live. Update it anyway (the summary is still the truthful content for that
  point in the transcript); do not skip the write just because the in-memory scan
  missed.
- **The background job runs on a worker thread.** `_apply_summary_to_history` takes
  `_history_lock` (`:1424`) for the in-memory mutation. `SessionStore` has its own
  `_lock`. Do **not** hold `_history_lock` across the SQLite write — the LLM call is
  already deliberately kept outside the lock (`:1388-1390`) and the same reasoning
  applies to I/O.
- **`role` has no CHECK constraint** (`core/session_store.py:92-101`), so a new value
  needs no schema migration — but it also means nothing will stop a typo. Define the
  role string as a module-level constant and use it at all three sites (write, update,
  resume filter).
