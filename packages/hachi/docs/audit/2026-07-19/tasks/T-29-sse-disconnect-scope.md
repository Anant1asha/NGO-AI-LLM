# T-29 · Stop one SSE viewer's disconnect from killing everyone's turn

> **Best effort-to-value ratio in this pack.** The minimal fix is deleting one line, it loses no
> user capability (the replacement already exists, is ownership-checked, and has 11 tests), and it
> closes a live user-facing correctness bug. If you only do one task from CF-8, do this one.

|  |  |
|---|---|
| **Source finding** | CF-8 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~2 hours (Option A) · ~half a day (Option B) |
| **Difficulty** | Low (mechanical) — the only judgement is picking Option A vs B in §5 |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `tests/test_gateway_sse.py` (+ `src/hachi/gateway/control_plane.py` under Option B) |

---

## 1. Brief

The session-event SSE stream cancels the **whole session's** in-flight turn whenever **any single
connection** to it drops. `request.is_disconnected()` is connection-local; `control_plane.interrupt(session_id)`
is session-global. Closing a browser tab, a proxy blip, a laptop sleep, or a second viewer navigating
away kills generation for every other viewer of that session. When you are done, a dropped SSE
connection will stop *that connection* and nothing else, while the explicit Stop button
(`POST /sessions/{id}/interrupt`) keeps working exactly as it does today.

## 2. Why this matters

Hachi's pitch is an agent that runs unattended and keeps a trustworthy record of what it did. A turn
that silently dies because a network hiccup closed one of possibly several event streams is the exact
opposite: work is lost, the transcript ends mid-thought, and nothing in the audit trail explains why.
The cancel-on-disconnect was added so the Stop button would really stop the server-side worker thread
(comment `P1-4` at `fastapi_app.py:1156-1157`) — but that requirement was **separately and properly
solved** by the dedicated `POST /sessions/{session_id}/interrupt` route. The disconnect hook is now
pure downside. If your fix makes the explicit interrupt route less reliable, you have fixed the wrong
thing.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The bug — `stream_session_events`, `src/hachi/gateway/fastapi_app.py:1155-1159`

Inside the `event_stream()` generator of the route handler `stream_session_events`
(declared at `fastapi_app.py:1109-1116`, path `GET /sessions/{session_id}/stream`):

```python
                    if await request.is_disconnected():
                        # P1-4: on browser disconnect also cancel the server-side turn so
                        # the worker thread stops, not just the coroutine awaiting it.
                        control_plane.interrupt(session_id)
                        break
```

`request` is the **per-connection** Starlette `Request` object (a parameter of this one HTTP request).
`session_id` is a **path parameter** — every viewer of the same conversation passes the same value.
There is nothing between them that narrows the interrupt to the disconnecting viewer.

### 3.2 The replacement already exists — `interrupt_session`, `src/hachi/gateway/fastapi_app.py:984-998`

```python
    @sessions.post("/{session_id}/interrupt", response_model=SessionInterruptResponse)
    async def interrupt_session(session_id: str, request: Request) -> Any:
        """Cancel the in-progress turn for a live session.
        ...
        """
        _check_session_ownership(session_id, _require_auth(request))
        return control_plane.interrupt(session_id)
```

Ownership is enforced at `:997`. This route is what the UI Stop button targets, and it is the reason
deleting the disconnect hook **loses no user capability**.

### 3.3 That route is well tested — `tests/test_gateway_interrupt.py`

**11 tests**, spanning `:51`–`:269`:

| Line | Test | Covers |
|---|---|---|
| `:51` | `test_interrupt_live_session_calls_handler_and_returns_true` | live session, handler wired |
| `:68` | `test_interrupt_unknown_session_returns_false` | unknown id is safe |
| `:77` | `test_interrupt_no_runtime_attached_returns_false` | `on_interrupt=None` |
| `:87` | `test_interrupt_handler_exception_returns_false_not_500` | buggy handler never 5xx |
| `:106` | `test_interrupt_route_live_session_returns_interrupted_true` | the HTTP route |
| `:126` | `test_interrupt_route_unknown_session_returns_interrupted_false` | route, unknown id |
| `:138` | `test_interrupt_route_no_runtime_attached_returns_false` | route, no runtime |
| `:151` | `test_interrupt_route_ownership_enforced` | **403 on foreign caller** |
| `:188` | `test_interrupt_route_requires_auth_when_token_configured` | **401 without bearer** |
| `:222` | `test_interrupt_delivers_correct_session_id` | correct id forwarded |
| `:245` | `test_interrupt_sets_cancel_event_on_real_loop` | the real `ExecutionLoop.cancel()` seam |

Do **not** touch these. They are the safety net that makes Option A safe.

### 3.4 The second disconnect site — DO NOT TOUCH — `src/hachi/gateway/fastapi_app.py:1727-1731`

Inside `_openai_event_stream` (the OpenAI-compat streaming path):

```python
                    if await request.is_disconnected():
                        turn_task.cancel()
                        # P1-4: also cancel the worker thread, not just the coroutine.
                        control_plane.interrupt(session_id)
                        return
```

**This one is correct and must stay.** Its `session_id` comes from a session minted for this single
request — `session_key = f"openai-{chat_id}"` at `:1668`, where `chat_id` is a fresh UUID from `:1635`.
One request, one session, one connection: connection-local and session-global are the *same scope*
there, so cancelling on disconnect is right. See §9.

### 3.5 No refcounting exists today — `src/hachi/gateway/control_plane.py`

`GatewayControlPlane` already owns the per-session connection registry and its lock (declared at
`control_plane.py:242-244`):

```python
        self._connections: dict[str, dict[str, Any]] = {}
        self._api_sessions: dict[str, str] = {}  # session_key -> session_id (facade sessions)
        self._connections_lock = threading.Lock()
```

used under the lock in `create_session` at `:314-327`, and cleaned up in `close_session` at `:509-540`
(which also prunes `_api_sessions` entries pointing at the id, `:518-523`).

A repo-wide grep for `refcount|ref_count|active_streams|viewer_count|subscriber` over `src/hachi/`
returns **only** unrelated `EventBus` subscriber machinery (`core/event_bus.py`, `core/settings.py:180-183`,
`gateway/orchestrator.py:2595`, `:2707`). **There is no stream refcount anywhere.** If you choose
Option B you are building it from scratch.

### 3.6 Zero existing tests pin the current behaviour

```
$ grep -rn "is_disconnected" tests/ | wc -l
0
```

This is clean ground: no existing assertion says "a disconnect must interrupt the session", so your
regression test can be written straight to the desired behaviour without amending anything. Contrast
with [T-30](T-30-sse-gap-signal.md), which does have to amend tests.

## 4. Reproduce the failure

There are three levels of proof. **Level 1 is genuinely demonstrable and is the one to run.**

### Level 1 — the two-viewer repro (real, end-to-end)

This needs a running gateway and a long-running turn. `HACHI_GATEWAY_NO_AUTH=1` removes the bearer
requirement so `curl` is enough.

```bash
# Terminal 1 — start the gateway (no auth, so curl needs no token)
cd /d/OpenGigantic/hachi
HACHI_GATEWAY_NO_AUTH=1 uv run hachi serve --port 8787

# Terminal 2 — create a session and keep its id
SID=$(curl -s -X POST localhost:8787/sessions \
  -H 'Content-Type: application/json' \
  -d '{"client_id":"viewer","surface":"web","protocol_version":"1.0","capabilities":["events"]}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
echo "$SID"

# Terminal 2 — VIEWER B: attach a stream and leave it open. This is the innocent bystander.
curl -N "localhost:8787/sessions/$SID/stream?poll_interval=1&max_idle_cycles=600"

# Terminal 3 — VIEWER A: attach a second stream to the SAME session, then kill it after 2s.
curl -N "localhost:8787/sessions/$SID/stream?poll_interval=1&max_idle_cycles=600" &
CURL_A=$!

# Terminal 4 — start a long turn (ask for something that takes >10s to generate)
curl -s -X POST "localhost:8787/sessions/$SID/messages" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Count slowly from 1 to 200, one number per line, with a short comment on each."}' &

# Terminal 3 — 2 seconds in, viewer A goes away (tab close / network drop)
sleep 2; kill "$CURL_A"
```

**You will see now:** within ~one poll cycle of killing viewer A, viewer B's stream stops receiving
`text.stream.delta` frames and the turn ends early — the `POST /messages` call returns a truncated
response. Viewer A's disconnect cancelled the shared turn.

**You should see after the fix:** killing viewer A changes nothing for viewer B. Deltas keep arriving
and the turn runs to completion. Only an explicit
`curl -X POST localhost:8787/sessions/$SID/interrupt` stops it.

> If `hachi serve` is not usable in your environment, Level 1 is still the definition of correct
> behaviour — fall back to Level 2 and say so in your report rather than skipping verification.

### Level 2 — the automated proof (what §7 turns into a permanent test)

See §7. `tests/test_gateway_sse.py` already drives this endpoint with `TestClient.stream`, so the
harness exists.

### Level 3 — the code-reading proof (always valid, no environment needed)

`session_id` is a **path parameter** of `stream_session_events` (`fastapi_app.py:1110`), so two viewers
of one conversation supply the same value; `request` is that handler's per-connection `Request`.
`control_plane.interrupt(session_id)` resolves through `_connections[session_id]` — a **session**
record, not a connection record (`control_plane.py:242`). Therefore the blast radius of one
connection's `is_disconnected()` is the entire session, by construction. This holds no matter what
the runtime is doing.

## 5. What "fixed" looks like

**A decision is needed between two options. The recommendation is Option A.**

### Option A — delete the disconnect-triggered interrupt (RECOMMENDED)

Remove the `control_plane.interrupt(session_id)` call from the disconnect branch, keeping the `break`
so the generator still exits and stops writing to a dead socket:

```python
                    if await request.is_disconnected():
                        # T-29: a disconnect is CONNECTION-scoped; the turn is SESSION-scoped.
                        # Stop this stream only. Cancelling the turn is an explicit user action
                        # via POST /sessions/{session_id}/interrupt (ownership-checked).
                        break
```

- **Cost:** a turn started by a user who then closes every tab keeps running to completion, consuming
  tokens. It is still cancellable at any time via the interrupt route, and it still terminates on its
  own.
- **Benefit:** two lines changed, no new state, no new lock discipline, no new failure mode. Every
  behaviour the disconnect hook was introduced for is already delivered by
  `POST /sessions/{session_id}/interrupt` — which, unlike the disconnect hook, is **ownership-checked**
  (`:997`) and **tested 11 ways** (§3.3).
- **Why this wins:** the current code trades a rare, cheap problem (an abandoned turn burns some
  tokens) for a common, expensive one (any connection blip destroys a shared turn). Option A reverses
  that trade at near-zero risk. Ship it now; Option B remains available later if multi-viewer
  auto-stop is ever actually wanted.

### Option B — refcount streams per session, interrupt only at zero

Add stream refcounting to `GatewayControlPlane`, beside the existing `_connections` state and under
the existing `_connections_lock`:

```python
# in __init__, beside self._connections (control_plane.py:242-244)
self._stream_refs: dict[str, int] = {}

def attach_stream(self, session_id: str) -> int:
    """Register an event-stream viewer. Returns the new viewer count."""
    with self._connections_lock:
        count = self._stream_refs.get(session_id, 0) + 1
        self._stream_refs[session_id] = count
        return count

def detach_stream(self, session_id: str) -> int:
    """Deregister an event-stream viewer. Returns the remaining viewer count."""
    with self._connections_lock:
        count = max(0, self._stream_refs.get(session_id, 0) - 1)
        if count:
            self._stream_refs[session_id] = count
        else:
            self._stream_refs.pop(session_id, None)
        return count
```

`stream_session_events` calls `attach_stream` before yielding `": connected\n\n"`, calls
`detach_stream` in the generator's existing `finally:` block (`fastapi_app.py:1187-1192`), and
interrupts **only** when `detach_stream(...) == 0`. `close_session` (`control_plane.py:509-540`) must
also `self._stream_refs.pop(session_id, None)` inside the lock so a closed session leaves no entry.

- **Cost:** new mutable shared state with a leak risk in every path that can skip the `finally:`
  (crashes, cancellation, server shutdown); a stuck non-zero count silently disables the stop-on-close
  behaviour, and a stuck zero re-creates today's bug for the next viewer. It needs its own tests for
  attach/detach/close-session/double-detach.
- **Benefit:** preserves "closing the last tab stops the run", which some users may expect.
- **Choose this only if** a product owner explicitly asks for last-viewer-leaves-stops-the-turn. It is
  a real feature with real cost — not the safe default.

Either way, the definition of done is identical: **viewer A disconnecting must not interrupt a turn
that viewer B is still watching.**

## 6. Steps

Assuming **Option A**. (For Option B, replace steps 3–4 with the refcount work in §5 and add tests for
`attach_stream`/`detach_stream`/`close_session` cleanup.)

1. Read `src/hachi/gateway/fastapi_app.py` around `:1109-1198` and confirm the disconnect branch is
   still at `:1155-1159`. Confirm the second, correct site is still at `:1727-1731` — you are not
   touching it.
2. Write the regression test from §7 into `tests/test_gateway_sse.py`. **Run it. Watch it fail.**
   Follow §7's "prove the test reaches the branch" instruction before you trust the failure.
3. Delete the single line `control_plane.interrupt(session_id)` at `:1158`.
4. Replace the now-stale `P1-4` comment at `:1156-1157` with the `T-29` comment from §5 Option A.
   (Rule 3: do not delete the comment outright — replace it, so the reasoning stays in the file.)
5. Re-run the test. Watch it pass.
6. Run `uv run pytest -q tests/test_gateway_sse.py tests/test_gateway_interrupt.py` and confirm the
   11 interrupt tests are still green — they are the proof that the explicit Stop path is untouched.
7. Add the bug-bank entry from §11.
8. Run the full gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_gateway_sse.py` (existing — it already has the fixture pattern you need)
- **Test name:** `test_stream_disconnect_does_not_interrupt_other_viewers`
- **It must assert:** that after one SSE connection to a session is dropped, `on_interrupt` was
  **never invoked** — observed through a real `GatewayControlPlane` wired with a recording
  `on_interrupt` handler, driven through the real ASGI app. Not a mock's return value: the assertion
  is on the list of session ids the control plane actually forwarded.
- **It must FAIL before your fix** with: `AssertionError: assert ['<session-id>'] == []` — i.e. the
  disconnect *did* deliver an interrupt.

```python
# sketch — adapt to the existing fixtures at the top of tests/test_gateway_sse.py
def test_stream_disconnect_does_not_interrupt_other_viewers() -> None:
    """T-29: an SSE disconnect is connection-scoped; it must not cancel the session turn."""
    interrupted: list[str] = []

    def _on_interrupt(session_id: str) -> dict[str, object]:
        interrupted.append(session_id)
        return {"interrupted": True}

    cp = GatewayControlPlane(read_events=_read_events, on_interrupt=_on_interrupt)
    app = create_gateway_app(cp)
    client = TestClient(app)
    session_id = client.post(
        "/sessions",
        json={
            "client_id": "viewer-a",
            "surface": "web",
            "protocol_version": "1.0",
            "capabilities": ["events"],
        },
    ).json()["session_id"]

    # Viewer A attaches, reads one frame, then abandons the stream mid-flight.
    # max_idle_cycles is high so the stream does NOT close on its own — the only
    # way out of the loop is the disconnect branch under test.
    with client.stream(
        "GET",
        f"/sessions/{session_id}/stream",
        params={"poll_interval": 0, "max_idle_cycles": 600},
    ) as response:
        assert response.status_code == 200
        next(response.iter_lines())  # consume one frame, then bail out of the block

    # Viewer B is still watching this session: the turn must not have been cancelled.
    assert interrupted == [], (
        "SSE disconnect interrupted the session-global turn; it is connection-scoped"
    )
```

> **Prove the test reaches the branch before you trust it.** Run it against **unmodified** code and
> confirm it fails with `interrupted == ['<session-id>']`. If it *passes* pre-fix, the harness never
> made `request.is_disconnected()` return `True` and the test proves nothing — it would go green after
> your change for the wrong reason. In that case switch to driving the app with
> `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` and cancelling the surrounding
> `anyio` task, or assert directly on the generator, and note in your report which harness you used
> and why.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix with `interrupted == ['<sid>']`.
- [ ] `control_plane.interrupt(...)` no longer appears inside `stream_session_events` in
      `src/hachi/gateway/fastapi_app.py`.
- [ ] The disconnect branch still `break`s, so an abandoned connection stops streaming (no writes to a
      dead socket, no leaked generator).
- [ ] The second disconnect site in `_openai_event_stream` (`~:1727-1731`) is **byte-for-byte
      unchanged** — verify with `git diff`.
- [ ] All 11 tests in `tests/test_gateway_interrupt.py` still pass — the explicit Stop path is intact.
- [ ] All 4 pre-existing tests in `tests/test_gateway_sse.py` still pass.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch the second `is_disconnected` site at `fastapi_app.py:1727-1731`** (inside
  `_openai_event_stream`). A pattern-matching agent will find it and "helpfully" apply the same fix.
  That would be a regression: that session is minted per request (`f"openai-{chat_id}"`, `:1668`), so
  interrupting on disconnect there is correct and prevents a genuinely orphaned turn. §3.4 explains
  why. If you changed it, revert it.
- Do not also implement the gap signal, the 50 ms poll replacement, or durable events. Those are the
  rest of CF-8 and belong to [T-30](T-30-sse-gap-signal.md) — which you should not start here.
- Do not "improve" the interrupt route, its ownership check, or its response model while you are in
  the file.
- Do not change `poll_interval` / `max_idle_cycles` defaults or the idle-close behaviour.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). In particular the 11 tests in
  `tests/test_gateway_interrupt.py` must stay exactly as they are.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_gateway_sse.py tests/test_gateway_interrupt.py   # focused
uv run python scripts/preflight.py --quick                                   # inner loop
uv run python scripts/preflight.py                                           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`):

```markdown
### BB-89 — One SSE viewer disconnecting cancelled the whole session's turn

- **Symptom:** closing a browser tab, a proxy blip, or a second viewer navigating away stopped
  generation mid-turn for every other viewer of the same session. The transcript ended
  mid-sentence with nothing in the audit trail explaining why.
- **Root cause:** in `stream_session_events` (`gateway/fastapi_app.py`), the disconnect branch
  called `control_plane.interrupt(session_id)`. `request.is_disconnected()` is CONNECTION-local;
  `session_id` is a path parameter shared by every viewer, so a connection-scoped trigger fired a
  session-scoped cancel. Added as "P1-4" so the Stop button would kill the worker thread — but that
  requirement was already met by the dedicated, ownership-checked
  `POST /sessions/{session_id}/interrupt` route.
- **Fix:** dropped the `interrupt()` call from the disconnect branch; the `break` remains so the
  abandoned stream still closes. Turn cancellation is now an explicit user action only.
- **Avoid:** never trigger session-scoped side effects from a connection-scoped signal. Before
  calling `interrupt`/`close`/`cancel` with a `session_id`, ask whether the thing that triggered it
  is owned by ONE connection or by the session. (The mirror site in `_openai_event_stream` is
  correct precisely because its session is minted per request.)
- **Locked by:** `tests/test_gateway_sse.py` — `test_stream_disconnect_does_not_interrupt_other_viewers`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-4 does NOT apply to Option A.** You are changing behaviour *inside* a handler, not the route
  set or any response shape, so the OpenAPI spec and `frontend/src/lib/data/schema.d.ts` are
  unaffected. Do not regenerate them — a spurious regeneration diff will make `check:api` noisy for
  the next person. **If you choose Option B and expose `attach_stream`/`detach_stream` as HTTP
  routes (you should not — they belong on the control plane, called from the existing handler),
  BB-4 applies in full.**
- **The `finally:` block at `fastapi_app.py:1187-1192` is the generator's only guaranteed cleanup**
  (it cancels `_trigger_task`). Under Option B, `detach_stream` must go there, not after the `break`,
  or every non-disconnect exit path leaks a refcount.
- **`max_idle_cycles` is why the existing SSE tests terminate.** The pre-existing tests pass
  `max_idle_cycles: 1` so the stream self-closes. Your test needs the opposite — a high value — so
  that the *only* way out of the loop is the disconnect branch you are testing.
- **`GatewayControlPlane.interrupt()` never raises.** It returns `{"interrupted": false}` for unknown
  sessions and swallows handler exceptions (`tests/test_gateway_interrupt.py:87`). So the current bug
  is completely silent — there is no error in any log to grep for. Do not go looking for one.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — irrelevant to the unit tests
  here, which use a hand-wired `GatewayControlPlane`, but relevant if you attempt the Level 1 repro
  against a cold gateway.
