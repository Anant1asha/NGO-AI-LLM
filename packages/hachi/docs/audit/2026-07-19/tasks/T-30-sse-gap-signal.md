# T-30 · Tell clients when the event ring dropped events under them

|  |  |
|---|---|
| **Source finding** | CF-8 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none — but land [T-29](T-29-sse-disconnect-scope.md) first if both are in flight; they touch the same SSE handler |
| **Blocks** | nothing |
| **Effort** | ~2-3 days |
| **Difficulty** | Medium — the code change is small; the care is in amending two existing tests correctly (§7) and not over-reaching into history replay (§9) |
| **Files you will touch** | `src/hachi/core/runtime_read_models.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/cli/main.py`, `src/hachi/gateway/control_plane.py`, `src/hachi/gateway/fastapi_app.py`, `openapi/hachi-openapi.json`, `frontend/src/lib/data/schema.d.ts`, `tests/test_runtime_read_models.py`, `tests/test_gateway_runtime_validation.py` |

---

## 1. Brief

Runtime events live in an in-memory list capped at 2,000 entries. When a client's cursor predates the
trim, the read path **silently** hands back the oldest surviving event as though nothing was missed —
the client believes it has a complete stream when it has a hole. When you are done, the events
response carries a `base_sequence` field (the oldest sequence still buffered) so a client can compare
it against its own cursor, detect that events were dropped, and refetch instead of quietly rendering
an incomplete transcript.

## 2. Why this matters

The event stream is what the UI renders *and* what the operator reads as the record of what the agent
did. A silent hole in it is worse than an error: the user sees a plausible, continuous transcript with
missing tool calls or approvals in the middle, and has no way to know. For a product whose stated moat
is a verifiable, owned audit trail, "we lost some events and didn't mention it" is a correctness
failure, not a performance detail. The goal is **not** to make the buffer lossless — that is the
durable-event-log project and is explicitly out of scope. The goal is to make the loss **visible** so
the client can react. If your change makes the buffer bigger but still silent, you have missed the
point.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The trim — `RuntimeReadModelStore.append_event`, `src/hachi/core/runtime_read_models.py:240-251`

```python
    def append_event(self, event: RuntimeEvent) -> None:
        with self._lock:
            self._sequence += 1
            self._events.append(
                RuntimeEventSnapshot(
                    event.name, dict(event.payload), event.timestamp, self._sequence
                )
            )
            # This log is the single source for sequence-based polling (the gateway
            # events endpoint), so keep a generous tail for slow-polling clients.
            if len(self._events) > 2000:
                self._events = self._events[-2000:]
```

Sequence numbers keep counting up (`self._sequence`), but the buffer only retains the last 2,000. So
after 2,001 appends the oldest surviving event has sequence `2`, not `1`.

### 3.2 The silent clamp — `RuntimeReadModelStore.read_events_since`, `src/hachi/core/runtime_read_models.py:426-440`

```python
    def read_events_since(self, after: int, limit: int = 100) -> tuple[RuntimeEventSnapshot, ...]:
        """Events whose sequence is greater than ``after``, oldest→newest, capped at ``limit``.

        The single source for sequence-based polling (the gateway events endpoint).
        O(1) index into the bounded ring-tail: the event at index ``i`` has sequence
        ``base + i`` where ``base = self._events[0].sequence``.  Clamp ``start`` to
        zero for stale clients (``after < base``) to avoid the silent tail-slice wrap
        that a naive ``after - base + 1`` would produce after a trim (BB entry).
        """
        with self._lock:
            if not self._events:
                return ()
            base = self._events[0].sequence
            start = max(0, after - base + 1)
            return tuple(self._events[start : start + limit])
```

`base` is computed and used, then thrown away. `max(0, ...)` is the clamp: a stale client gets the
oldest survivor with **no indication** that anything between its cursor and that survivor is gone.

A repo-wide grep for `gap|truncat|dropped|missed` finds **no gap-signalling mechanism anywhere in the
codebase.** You are adding the first one.

### 3.3 The full chain from store to wire

Five hops. **Every one of them drops `base` today**, so you must thread the value through all of them.

1. **`src/hachi/core/runtime_read_models.py:426`** — `read_events_since` (above). Knows `base`.
2. **`src/hachi/gateway/orchestrator.py:1069-1073`** — `AgentSession.snapshot_events_since`:
   ```python
       def snapshot_events_since(
           self, after: int, limit: int = 100
       ) -> tuple[RuntimeEventSnapshot, ...]:
           """Sequenced events past ``after`` — the single source for gateway polling."""
           return self._read_models.read_events_since(after, limit=limit)
   ```
3. **`src/hachi/cli/main.py:440-450`** — `_InProcessGatewayRuntime.read_events`, which converts
   snapshots into the gateway's `GatewayEvent` DTO:
   ```python
       def read_events(self, session_id: str, after: int, limit: int) -> list[GatewayEvent]:
           snapshots = self._get_agent(session_id).snapshot_events_since(after, limit)
           return [
               GatewayEvent(
                   sequence=snap.sequence,
                   event_type=snap.name,
                   payload=snap.payload,
                   time=snap.timestamp,
               )
               for snap in snapshots
           ]
   ```
   Wired into the control plane at **`src/hachi/cli/main.py:2968`**: `read_events=runtime.read_events if runtime else None`.
4. **`src/hachi/gateway/control_plane.py:554-573`** — the live branch of `read_session_events`, which
   builds the response dict:
   ```python
           if is_live:
               if self._read_events is None:
                   raise GatewayUnavailableError("event stream is not attached")
               batch = self._read_events(session_id, safe_after, safe_limit)
               next_sequence = safe_after
               if batch:
                   next_sequence = batch[-1].sequence
               return {
                   "session_id": session_id,
                   "events": [...],
                   "next_sequence": next_sequence,
               }
   ```
5. **`src/hachi/gateway/fastapi_app.py:1160-1163`** — the SSE loop consuming it:
   ```python
                       try:
                           batch = control_plane.read_session_events(
                               session_id=session_id, after=cursor, limit=100
                           )
   ```
   and the REST twin `get_session_events` at `fastapi_app.py:1092-1107`.

### 3.4 The response model — `src/hachi/gateway/fastapi_app.py:132-135`

```python
class SessionEventsResponse(BaseModel):
    session_id: str
    events: list[GatewayEventPayload]
    next_sequence: int
```

This is one of only **9 operations (out of 100)** in the whole gateway that has a real typed response
schema in the OpenAPI document. Changing it produces a genuine OpenAPI diff. **BB-4 applies** — see §12.

### 3.5 Two existing tests LOCK IN the silent clamp as the contract

`tests/test_runtime_read_models.py:170-226`, under the banner comment:

```python
# --- B4 trim-underflow contract -------------------------------------------
# These tests establish the correctness contract for the O(1) index
# implementation.  A naive `start = after - base + 1` (no guard) would
# silently return a wrong tail slice when `after < base_sequence` — a
# condition that arises on any trimmed buffer (>2000 events appended).
```

The two that matter:

**`test_read_events_since_stale_after_clamps_to_oldest_surviving` (`:203-213`)**

```python
    result = store.read_events_since(after=0)
    # Must start from seq=2 (oldest surviving), not from end-of-buffer.
    assert result[0].sequence == 2
    # Must NOT return a tail slice (the wrong wrap behaviour would yield seq~2001).
    assert result[0].sequence < 100
```

**`test_read_events_since_parity_with_scan_after_trim` (`:216-225`)**

```python
    reference = tuple(s for s in store._events if s.sequence > cursor)[:100]
    result = store.read_events_since(after=cursor, limit=100)
    assert result == reference
```

Both index or compare `read_events_since`'s return value **as a bare tuple**. Its name literally says
`clamps_to_oldest_surviving` — the assertion is that the clamp happens and that nothing else does.
Additionally `tests/test_gateway_runtime_validation.py:133`,
`test_runtime_event_buffer_caps_at_2000_and_handles_sparse_cursors`, asserts the same shape end-to-end
through the runtime:

```python
    a_events = runtime.read_events("session-a", after=0, limit=5000)
    assert len(a_events) == 2000
    assert a_events[0].sequence == 106
```

**Adding a gap signal means AMENDING these tests, not merely adding a new one.** Under
[CLAUDE.md](../../../../CLAUDE.md) Rule 2 this is a **contract correction, not test-weakening**: the
tests assert that a stale read returns the oldest survivor (still true, keep it) *and implicitly* that
nothing tells the caller events were skipped (now wrong). You must **say so explicitly in the commit
message** — e.g. *"amends the B4 trim-underflow contract: clamping stays, silence does not"* — so a
reviewer can see it was deliberate. Do not delete them, do not `skip` them, do not loosen an
assertion that is still valid.

### 3.6 The client-side premise the design rests on is false

The route docstring at `src/hachi/gateway/fastapi_app.py:1119-1121`:

```python
        """Server-Sent Events stream of runtime events — replaces client polling.

        Pushes events as they arrive, then closes after ``max_idle_cycles`` idle
        polls (an EventSource auto-reconnects, so this stays cheap and robust).
        Clients resume with the last ``id`` they saw via the ``after`` query param.
        """
```

The frontend does **not** use `EventSource`. `frontend/src/lib/data/sse.ts:4-5`:

```typescript
// We use fetch + ReadableStream rather than the native EventSource because
// EventSource cannot set an Authorization header. The gateway streams runtime
```

and `frontend/src/lib/data/sse.ts:55`:

```typescript
 * Does NOT auto-reconnect — callers own retry/backoff policy.
```

The consumer is `frontend/src/lib/data/domains/chat.ts:938-939` (`await streamSSE(`/sessions/${sessionId}/stream`, {`).

So **both** halves of the design are unsupported: the idle-close path assumes an auto-reconnect that
does not exist, and the resume-with-`after` path assumes a resume that no one performs automatically.
Fix the stale docstring as part of this task (it is two lines and directly misleads the next reader).
**Do not rewrite the frontend's reconnect policy here** — see §9.

### 3.7 Follow-up, NOT part of this task: history replay uses a second sequence space

`GatewayControlPlane._synthesize_history_events` (`src/hachi/gateway/control_plane.py:588-649`) rebuilds
events from the stored transcript at **message granularity**, in a **separate sequence space starting
at 0**:

```python
        messages = self._get_session_messages(session_id, 500) or []
        events: list[dict[str, Any]] = []
        seq = 0
```

(`:599` caps at 500 messages; `:601` is `seq = 0`; `:649` paginates *after* building the whole list:
`return [e for e in events if e["sequence"] > after][:limit]`).

Consequence: a client that streams live (sequences from the in-memory ring), disconnects, then
refetches once the session is no longer live gets **colliding `id:` cursors** — sequence 7 from history
is a different event than sequence 7 from the live ring. Record this in §11's bug-bank entry as a known
adjacent defect and **leave it alone** (§9).

## 4. Reproduce the failure

**The gap is not observable from a shell today — that is the entire bug.** There is no output to look
at, because the missing events are exactly what is absent. What you *can* do is prove the mechanism
deterministically at the unit level, which is what the tests in §7 do permanently.

### The deterministic proof (run this)

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run python -c "
from hachi.core.runtime_read_models import RuntimeReadModelStore
from hachi.core.settings import RuntimeEvent

store = RuntimeReadModelStore()
for i in range(2100):
    store.append_event(RuntimeEvent(name=f'e{i}', payload={'i': i}, timestamp='t'))

batch = store.read_events_since(after=5, limit=3)
print('client cursor was: 5')
print('oldest event actually returned:', batch[0].sequence)
print('events silently skipped:', batch[0].sequence - 1 - 5)
print('anything in the return value that says so?', batch[0])
"
```

> Confirm `RuntimeEvent`'s import path and constructor signature before running — grep
> `class RuntimeEvent` (it is re-exported via `hachi.core.settings`, and `runtime_read_models.py`
> consumes it). If the constructor differs, adapt; the point of the snippet is the three printed lines,
> not the import.

**You will see now:** the client asked for everything after sequence 5 and received events starting at
sequence ~101. Roughly 95 events vanished, and the returned tuple contains **nothing** that indicates
it — no flag, no base, no count. The caller cannot distinguish this from "sequence 6..100 never
existed".

**You should see after the fix:** the same call also exposes the oldest retained sequence (`base_sequence`),
so the caller can evaluate `base_sequence > after + 1` and know a gap occurred, how big it was, and that
it should refetch rather than render.

### End-to-end (optional, slow)

Reaching 2,000 real runtime events through a live gateway requires a very long agent session; it is not
a practical repro loop. Use the unit-level proof above and the tests in §7. Say in your report that
this is what you did — do not claim an end-to-end reproduction you did not run.

## 5. What "fixed" looks like

`GET /sessions/{session_id}/events` and the SSE stream both expose the oldest sequence still held, so a
client can detect a gap:

```python
class SessionEventsResponse(BaseModel):
    session_id: str
    events: list[GatewayEventPayload]
    next_sequence: int
    base_sequence: int   # oldest sequence still retained; 0 when the buffer is empty
```

Client-side rule (this is the contract you are creating — document it in the field's description):

> A gap occurred iff `base_sequence > after + 1`, where `after` is the cursor the client sent.
> `base_sequence == 0` means the buffer is empty and no gap can be inferred.

**Design decision, made here so you do not have to make it:** thread the value through as a **separate
scalar**, not by changing `read_events_since`'s return *type*.

Add a sibling accessor to `RuntimeReadModelStore`:

```python
    def oldest_sequence(self) -> int:
        """Oldest sequence still retained in the ring, or 0 when empty.

        Clients compare this against their own cursor to detect events dropped by
        the 2000-entry trim in :meth:`append_event`.
        """
        with self._lock:
            return self._events[0].sequence if self._events else 0
```

Rationale: `read_events_since` returns a `tuple[RuntimeEventSnapshot, ...]` that several call sites
index and compare directly (§3.5). Changing it to return a pair would ripple through those call sites
*and* break the two tests structurally rather than contractually. A separate accessor keeps the
existing tuple contract intact, so the test amendments are additive assertions rather than rewrites.

> **Race note:** `oldest_sequence()` and `read_events_since()` take the lock separately, so a trim can
> land between them. That is acceptable here — the effect is at worst a *false positive* gap signal
> (base moved forward), which causes a harmless refetch. Do **not** "fix" this by holding the lock
> across both calls from outside the class; if you want atomicity, add one method that returns both
> under a single lock and use it everywhere. Either is fine — state which you chose.

Then carry it through §3.3's hops 2→5 and into `SessionEventsResponse`. Hop 3
(`_InProcessGatewayRuntime.read_events`) returns a `list[GatewayEvent]` with no room for a scalar, so
add a sibling runtime method (e.g. `read_events_base(session_id) -> int`) and wire it as a new
`GatewayControlPlane` constructor kwarg next to `read_events` at `src/hachi/cli/main.py:2968` —
following the existing `Callable | None` handler pattern used by every other seam in that constructor.
Default it to `None` and emit `base_sequence: 0` when unwired, so the many tests that build a
`GatewayControlPlane` by hand keep working.

Also in scope, because it is two lines and actively misleading: correct the `EventSource` claim in the
`stream_session_events` docstring (§3.6) to state that the frontend uses `fetch` + `ReadableStream` and
does not auto-reconnect.

## 6. Steps

1. Add `oldest_sequence()` to `RuntimeReadModelStore` (`src/hachi/core/runtime_read_models.py`, next to
   `read_events_since`).
2. Amend the two tests in `tests/test_runtime_read_models.py` per §7 — **first**, and watch the new
   assertions fail.
3. Add `snapshot_events_base()` to `AgentSession` (`src/hachi/gateway/orchestrator.py`, next to
   `snapshot_events_since` at `:1069`) delegating to `oldest_sequence()`.
4. Add `read_events_base(session_id)` to `_InProcessGatewayRuntime` (`src/hachi/cli/main.py`, next to
   `read_events` at `:440`).
5. Add a `read_events_base: Callable[[str], int] | None = None` constructor kwarg to
   `GatewayControlPlane` (`src/hachi/gateway/control_plane.py`), store it as `self._read_events_base`,
   and include `"base_sequence"` in the **live** branch of `read_session_events` (`:554-573`).
   Emit `0` when the handler is `None`.
6. In the **history** branch (`:575-586`), emit `base_sequence: 0` explicitly. History replay has its
   own sequence space (§3.7) and no trim, so there is nothing meaningful to report — but the field must
   be present so the response shape is uniform.
7. Wire `read_events_base=runtime.read_events_base if runtime else None` at `src/hachi/cli/main.py:2968`.
8. Add `base_sequence: int` to `SessionEventsResponse` (`src/hachi/gateway/fastapi_app.py:132-135`) with
   a docstring stating the gap rule from §5.
9. Fix the stale `EventSource` docstring at `src/hachi/gateway/fastapi_app.py:1119-1121`.
10. Amend `tests/test_gateway_runtime_validation.py:133` per §7.
11. **BB-4:** regenerate the OpenAPI spec and the frontend types (§12).
12. Add the bug-bank entry (§11) and run the full gate (§10).

> **Not in these steps, deliberately:** consuming `base_sequence` in the frontend. Shipping the signal
> is this task; acting on it is a frontend change with its own UX decision (refetch silently? show a
> "some events were dropped" marker?). See §9.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

### 7a. The new test (the primary lock)

- **File:** `tests/test_runtime_read_models.py` (existing)
- **Test name:** `test_read_events_since_exposes_gap_after_trim`
- **It must assert:** on a really-trimmed store, `oldest_sequence()` returns the true oldest retained
  sequence (`2` after 2,001 appends) and is strictly greater than a stale client's `after + 1` — i.e.
  a gap is now *detectable*, computed from real appended events, not from a mock.
- **It must FAIL before your fix** with: `AttributeError: 'RuntimeReadModelStore' object has no attribute 'oldest_sequence'`

```python
# sketch — adapt to the repo's existing `_ev(...)` helper at the top of the file
def test_read_events_since_exposes_gap_after_trim() -> None:
    """T-30: a stale cursor must be able to DETECT the trim, not just be clamped past it."""
    store = RuntimeReadModelStore()
    for i in range(2001):
        store.append_event(_ev(f"e{i}", {}))

    after = 0
    batch = store.read_events_since(after=after, limit=5)
    base = store.oldest_sequence()

    # Clamping still happens — unchanged contract.
    assert batch[0].sequence == 2
    # ...and it is now DETECTABLE: base > after + 1 means events were dropped.
    assert base == 2
    assert base > after + 1, "a stale cursor must be able to detect the gap"
```

### 7b. The two amendments (§3.5) — contract correction, not weakening

- **File:** `tests/test_runtime_read_models.py`
- **`test_read_events_since_stale_after_clamps_to_oldest_surviving` (`:203`)** — keep every existing
  assertion (the clamp is still correct). **Add** an assertion that `store.oldest_sequence() == 2`, and
  update the docstring from "must not wrap" to "must not wrap, and the caller must be able to detect
  the skip".
- **`test_read_events_since_parity_with_scan_after_trim` (`:216`)** — the `result == reference` parity
  assertion stays valid **only because §5 chose not to change `read_events_since`'s return type.** Add
  a line asserting `store.oldest_sequence() == store._events[0].sequence` so the new accessor is
  covered by the parity contract too. If you deviated from §5 and changed the return type, this test
  breaks structurally and you must rewrite it — say so loudly in the commit message and re-read §5's
  rationale first.
- **File:** `tests/test_gateway_runtime_validation.py`,
  **`test_runtime_event_buffer_caps_at_2000_and_handles_sparse_cursors` (`:133`)** — keep the existing
  end-to-end assertions (`len == 2000`, `a_events[0].sequence == 106`); **add** an assertion that the
  runtime's new base accessor reports `106` for that session, proving the value survives the hop from
  store to runtime.

### 7c. The wire test

- **File:** `tests/test_gateway_sse.py` (existing) or a new
  `tests/test_gateway_events_gap_signal.py` — your call, but state which.
- **Test name:** `test_session_events_response_carries_base_sequence`
- **It must assert:** `GET /sessions/{id}/events` returns a body containing `base_sequence`, driven
  through the real ASGI app with a hand-wired `GatewayControlPlane` (the pattern at
  `tests/test_gateway_sse.py:22-36`).
- **It must FAIL before your fix** with: `KeyError: 'base_sequence'`.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7a exists, and failed before the fix with `AttributeError`.
- [ ] The three amended tests (§7b) still assert the clamp behaviour they always asserted — nothing was
      loosened or removed — and additionally assert the new signal.
- [ ] The commit message explicitly states that the B4 trim-underflow contract was **amended** (clamping
      stays; silence does not) and why that is a contract correction, not test-weakening.
- [ ] `GET /sessions/{session_id}/events` returns `base_sequence` on both the live and history branches.
- [ ] The SSE stream route's response path is unaffected in shape (it emits `id:`/`event:`/`data:`
      frames, not the JSON envelope) — but its docstring no longer claims `EventSource` auto-reconnect.
- [ ] `openapi/hachi-openapi.json` contains `base_sequence` in `SessionEventsResponse`, and
      `frontend/src/lib/data/schema.d.ts` was regenerated (BB-4, §12).
- [ ] `npm run --prefix frontend check:api` exits clean.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not fix the history-replay sequence-space collision (§3.7).** You will be reading
  `control_plane.py:588-649` while wiring the history branch, and the `seq = 0` at `:601` is a visible,
  tempting bug. Renumbering history into the live sequence space changes what every stored transcript
  replays as — that is a separate design decision with its own migration question. Record it in the
  bug-bank entry and move on.
- **Do not make the buffer durable or bigger.** Persisting events to the existing SQLite substrate is
  the ~1-week durable-log project from CF-8, not this task. Raising `2000` to a larger number papers
  over the symptom and still ships silently.
- **Do not replace the 50 ms poll** (`fastapi_app.py:1140-1146`, `_poll_trigger`) with per-connection
  `asyncio.Queue`s. Same finding, different task, much larger blast radius.
- **Do not change the disconnect-interrupt behaviour** at `fastapi_app.py:1155-1159` — that is
  [T-29](T-29-sse-disconnect-scope.md). If both are in flight, land T-29 first and rebase.
- **Do not implement the frontend's gap handling.** Shipping the field is this task. Deciding what the
  UI does with it (silent refetch vs. a visible "some events were dropped" marker) is a UX decision;
  file it as a follow-up.
- **Do not "fix" `sse.ts` to auto-reconnect.** The comment at `:55` is a deliberate design choice
  ("callers own retry/backoff policy"), not an oversight. Correcting the *backend docstring* that
  misdescribes it is in scope; changing the frontend's policy is not.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Amending per §7b is allowed **and required**; deleting is
  not.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_runtime_read_models.py tests/test_gateway_runtime_validation.py tests/test_gateway_sse.py

# BB-4 — MANDATORY after the response-shape change, or CI fails
uv run hachi gateway-openapi --output openapi/hachi-openapi.json
npm run --prefix frontend generate:api

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`, and coordinate if
[T-29](T-29-sse-disconnect-scope.md) lands first):

```markdown
### BB-N — Trimmed runtime-event ring dropped events with no signal to the client

- **Symptom:** a client resuming with a cursor older than the 2,000-entry trim boundary received a
  continuous-looking event stream that silently omitted everything between its cursor and the oldest
  retained event. Missing tool calls / approvals in the middle of a transcript with no error, no
  warning, and no way for the client to tell.
- **Root cause:** `RuntimeReadModelStore.read_events_since` (`core/runtime_read_models.py`) computed
  `base = self._events[0].sequence`, clamped `start = max(0, after - base + 1)`, then discarded
  `base`. Every hop after it (`AgentSession.snapshot_events_since` →
  `_InProcessGatewayRuntime.read_events` → `GatewayControlPlane.read_session_events` →
  `SessionEventsResponse`) carried only the events, never the base. A repo-wide grep for
  `gap|truncat|dropped|missed` confirmed no gap signal existed anywhere.
- **Fix:** added `RuntimeReadModelStore.oldest_sequence()` and threaded it through all five hops to a
  new `base_sequence` field on `SessionEventsResponse`. A client detects a gap iff
  `base_sequence > after + 1`.
- **Avoid:** when a read path silently repairs a caller's bad/stale input, the repair MUST be
  reported back. Clamping is fine; clamping in silence is a data-integrity bug.
- **Also noted, NOT fixed (follow-up):** `GatewayControlPlane._synthesize_history_events` replays
  stored transcripts in a SEPARATE sequence space starting at `seq = 0`, so live cursors and history
  cursors collide for a client that streams, disconnects, then refetches.
- **Locked by:** `tests/test_runtime_read_models.py` — `test_read_events_since_exposes_gap_after_trim`
  (plus amended `test_read_events_since_stale_after_clamps_to_oldest_surviving` and
  `test_read_events_since_parity_with_scan_after_trim`)
```

## 12. Known traps

- **BB-4 — THIS TASK CHANGES A GATEWAY RESPONSE SHAPE.** `SessionEventsResponse` is one of only 9
  operations in the whole spec with a real typed schema, so your change *will* produce an OpenAPI diff.
  You **must** run both:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  npm run --prefix frontend generate:api
  ```
  or `scripts/preflight.py`'s "openapi <-> frontend contract" step (`scripts/preflight.py:124-131`)
  fails, and so does CI.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`GatewayControlPlane` has ~60 optional `Callable | None` constructor kwargs.** Dozens of tests
  construct it with only a couple of them. Your new `read_events_base` kwarg **must** default to `None`
  and the code **must** emit `base_sequence: 0` when it is unwired — otherwise you break a large number
  of unrelated tests and will be tempted to "fix" them, which is scope creep and looks like
  test-weakening.
- **The history branch has no ring and no trim.** Emit `base_sequence: 0` there rather than inventing a
  value. Do not attempt to make history and live agree — see §3.7 and §9.
- **`read_events_since` is called under `self._lock`; `oldest_sequence` must take the lock too.** Do not
  read `self._events[0]` without it — `append_event` mutates the list from the agent's worker thread.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Relevant only if you try an
  end-to-end repro against a cold gateway.
