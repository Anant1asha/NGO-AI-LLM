# T-33 · Close OpenAI-facade sessions so the gateway stops leaking toward its cap

|  |  |
|---|---|
| **Source finding** | CF-9 (defect 2) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | **[T-31](T-31-openai-facade-decision.md) — do not start until it has landed.** Under options (c) or (d) this task is thrown away. Land after [T-32](T-32-facade-session-isolation.md) if both are in flight — they touch the same two code paths. |
| **Blocks** | nothing |
| **Effort** | ~half a day |
| **Difficulty** | Low (mechanical) — the insertion point already exists |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `tests/test_gateway_openai_channels.py` |

---

## 1. Brief

Every streaming `POST /v1/chat/completions` request mints a brand-new server-side session from a fresh
UUID, booting a full agent — and **never closes it**. Sessions accumulate against a hard cap of 100 with
no LRU and no eviction, so the 101st streaming request fails and every request after it fails
permanently until the process restarts. When you are done, a facade session is closed when its request
finishes, and the active-session count returns to its baseline.

## 2. Why this matters

This is a denial-of-service reachable by ordinary use of a documented feature: 100 normal requests
against a route the README tells people to point Open WebUI at, and the gateway stops accepting new
sessions — not just facade sessions, but *all* of them, including the web UI's. The failure mode is
also maximally confusing: everything works fine for a while, then nothing works, and a restart "fixes"
it. Each leaked session is not merely a dict entry — it is a booted agent holding LLM clients, worker
threads, and SQLite handles. If your fix caps or evicts sessions instead of closing them, you have
built a workaround for a missing `close_session` call and left the resources held.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 A fresh session per streaming request — `src/hachi/gateway/fastapi_app.py:1635`, `:1666-1673`

```python
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
```

```python
        async def _openai_event_stream() -> AsyncIterator[str]:
            # Create/get the session before starting the turn so we can read its events.
            session_key = f"openai-{chat_id}"
            session_id: str = await anyio.to_thread.run_sync(
                lambda: control_plane.get_or_create_session(
                    session_key, owner_token_hash=caller_hash
                )
            )
```

`chat_id` is a fresh UUID per request, so `session_key` is unique per request, so
`get_or_create_session` **always misses** → `create_session` → `_on_connect` → a full `boot_agent()`.

### 3.2 `close_session` is never called in the facade

The only occurrence in the entire 3,000-line `src/hachi/gateway/fastapi_app.py` is the
`DELETE /sessions/{session_id}` route at `:978`:

```python
        return control_plane.close_session(session_id)
```

Nothing in `:1593-1813` (the facade) closes anything.

### 3.3 The cap is a hard raise with no eviction — `src/hachi/gateway/control_plane.py:314-318`

```python
        with self._connections_lock:
            if len(self._connections) >= self._max_active_sessions:
                raise GatewayProtocolError(
                    f"Maximum active sessions reached ({self._max_active_sessions})."
                )
```

Default 100 (`src/hachi/gateway/control_plane.py:167`: `max_active_sessions: int = 100`), overridable
via `HACHI_GATEWAY_MAX_SESSIONS` (`src/hachi/cli/main.py:2955`). **No LRU. No TTL. No eviction.** Once
full, it stays full.

### 3.4 `close_session` is exactly the right call — `src/hachi/gateway/control_plane.py:509-540`

```python
    def close_session(self, session_id: str) -> dict[str, Any]:
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise GatewayProtocolError("session_id is required")
        was_live = False
        with self._connections_lock:
            if normalized_session_id in self._connections:
                was_live = True
                self._connections.pop(normalized_session_id, None)
                # Prune any api-facade session-key that pointed at this session_id.
                stale_keys = [
                    k for k, v in self._api_sessions.items() if v == normalized_session_id
                ]
                for k in stale_keys:
                    del self._api_sessions[k]
        if was_live and self._on_disconnect is not None:
            self._on_disconnect(normalized_session_id)
        ...
        if not was_live and not deleted:
            raise GatewayProtocolError("Unknown session_id")

        return {"session_id": normalized_session_id, "closed": True}
```

Note `:518-523`: it **already prunes the `_api_sessions` facade-key map** for the closed id. It was
written with facade sessions in mind. It also invokes `_on_disconnect` (the runtime teardown) — which is
what actually releases the booted agent's resources.

**Two behaviours you must know before calling it** (§12 repeats these as traps):
1. It **raises `GatewayProtocolError("Unknown session_id")`** when the session is neither live nor
   deletable — so a double-close raises.
2. It also calls `self._delete_session(...)` (`:531-535`), removing the **persisted transcript** so the
   conversation disappears from the recent-sessions list. For an ephemeral per-request facade session
   that is desirable; know that it happens.

### 3.5 The insertion point already exists — `src/hachi/gateway/fastapi_app.py:1765-1776`

`_openai_event_stream` already has a `finally:` block that tears down its tasks:

```python
            finally:
                _sse_trigger_task.cancel()
                try:
                    await _sse_trigger_task
                except asyncio.CancelledError:
                    pass
                if not turn_task.done():
                    turn_task.cancel()
                    try:
                        await turn_task
                    except asyncio.CancelledError:
                        pass
```

This is where the close belongs. It is the only place guaranteed to run on the normal exit path, the
`turn_done` break, and an exception.

### 3.6 The observable counter — `src/hachi/gateway/control_plane.py:273-281`

`readiness()` reports the live session count, which is what your regression test asserts on:

```python
        with self._connections_lock:
            active = len(self._connections)
        return {
            ...
            "active_connections": active,
```

Exposed at `GET /readiness`.

### 3.7 Nothing tests this

`tests/test_gateway_openai_channels.py` (19 tests, 336 lines) contains no assertion about session
counts, `close_session`, or `active_connections`. The streaming tests exercise the SSE frames only.
Clean ground — no existing assertion to fight.

## 4. Reproduce the failure

Genuinely reproducible from a shell. Lower the cap so it takes seconds instead of a hundred requests.

```bash
# Terminal 1 — small cap makes the leak obvious fast
cd /d/OpenGigantic/hachi
HACHI_GATEWAY_NO_AUTH=1 HACHI_GATEWAY_MAX_SESSIONS=5 uv run hachi serve --port 8787

# Terminal 2 — baseline
curl -s localhost:8787/readiness | python -m json.tool | grep active_connections

# Terminal 2 — seven STREAMING requests (stream:true is the leaking path)
for i in $(seq 1 7); do
  echo "--- request $i ---"
  curl -s -N -X POST localhost:8787/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"stream":true,"messages":[{"role":"user","content":"say hi"}]}' | head -3
  curl -s localhost:8787/readiness | python -m json.tool | grep active_connections
done
```

**You will see now:** `active_connections` increases by one after **every** streaming request and never
comes back down. Once it reaches 5, further requests fail with
`Maximum active sessions reached (5)` — and keep failing, including requests from other surfaces,
until you restart the process.

**You should see after the fix:** `active_connections` rises during a request and returns to the
baseline after it completes. Seven requests in a row against a cap of 5 all succeed.

> If `hachi serve` is unavailable in your environment, the §7 test asserts the same property in-process
> via `GET /readiness` — use that and say so in your report rather than claiming a shell repro you did
> not run.

## 5. What "fixed" looks like

A facade session is closed when its request finishes, in the `finally:` block that already exists.

```python
            finally:
                _sse_trigger_task.cancel()
                try:
                    await _sse_trigger_task
                except asyncio.CancelledError:
                    pass
                if not turn_task.done():
                    turn_task.cancel()
                    try:
                        await turn_task
                    except asyncio.CancelledError:
                        pass
                # T-33: this session was minted for THIS request (session_key is a
                # fresh UUID) — release it, or the 100-session cap fills permanently.
                # close_session raises on an already-closed id; a leaked session is
                # far worse than a swallowed teardown error, so never let this
                # propagate into the response stream.
                try:
                    await anyio.to_thread.run_sync(
                        lambda: control_plane.close_session(session_id)
                    )
                except Exception:
                    logger.warning(
                        "OpenAI facade: failed to close session %s", session_id, exc_info=True
                    )
```

Requirements this must satisfy:

- **Runs on every exit path** — normal completion, the `turn_done` break, the client-disconnect `return`
  at `:1727-1731`, and any exception. The existing `finally:` gives you all four.
- **Never raises into the response.** `close_session` raises `GatewayProtocolError` on an unknown id
  (§3.4). The stream may already have sent bytes, so an exception here corrupts the response for no
  benefit. Log it.
- **Off the event loop.** `close_session` invokes `_on_disconnect` → runtime teardown, which can block.
  Use `anyio.to_thread.run_sync`, matching how the same handler already calls
  `get_or_create_session` (`:1669-1673`) and `send_message` (`:1705-1707`).
- **Confirm the logger.** Grep for an existing module-level `logger` in
  `src/hachi/gateway/fastapi_app.py` and use it. Do not introduce a new logging configuration.

**Non-streaming path:** if [T-32](T-32-facade-session-isolation.md) landed first, requests that supply
no `user` field now also mint a per-request session, and those leak too. Close them the same way —
in a `try/finally` around the `send_message` call — but **only** when the session was minted for this
request. A session keyed by a client-supplied `user` id is meant to persist for continuity; closing it
would destroy the conversation memory that key exists to provide.

Make the distinction explicit rather than inferring it:

```python
        # T-32 sets this when it fell back to a per-request UUID key.
        ephemeral = not client_supplied_conversation_id
```

If T-32 has **not** landed, the non-streaming path still uses the shared `"__default__"` session — do
**not** close that one. Closing a shared session out from under other callers is a worse bug than the
one you are fixing. Scope yourself to the streaming path and note the follow-up.

## 6. Steps

1. **Confirm [T-31](T-31-openai-facade-decision.md) landed with option (a) or (b).** If (c) or (d),
   stop — this task is superseded.
2. Check whether [T-32](T-32-facade-session-isolation.md) has landed. It determines whether the
   non-streaming path is in scope (§5).
3. Write the regression test from §7. **Run it. Watch it fail.**
4. Add the guarded `close_session` call to the existing `finally:` block at
   `src/hachi/gateway/fastapi_app.py:1765-1776`.
5. If T-32 landed: add the same guarded close to the non-streaming path, **only** for ephemeral
   (per-request-UUID) sessions.
6. Re-run the test. Watch it pass.
7. Add the bug-bank entry (§11) and run the full gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_gateway_openai_channels.py` (existing)
- **Test name:** `test_openai_streaming_closes_its_session`
- **It must assert:** the gateway's real `active_connections` count (read from `GET /readiness`, backed
  by `len(self._connections)`) returns to its pre-request baseline after a streaming request completes
  — and, in a second phase, that N sequential streaming requests never approach the cap. This asserts
  the observable resource state, not that a mock was called.
- **It must FAIL before your fix** with: `AssertionError: assert 1 == 0` on the first phase (one leaked
  session), and on the second phase with the route returning an error once the lowered cap is reached.

```python
# sketch — adapt to the file's existing streaming helpers (_streaming_control_plane)
def test_openai_streaming_closes_its_session() -> None:
    """T-33: a facade session is minted per streaming request and must be released."""
    cp = _streaming_control_plane()
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        baseline = client.get("/readiness").json()["active_connections"]

        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={"stream": True, "messages": [{"role": "user", "content": "hi"}]},
        ) as response:
            assert response.status_code == 200
            "".join(response.iter_text())  # drain to completion so `finally:` runs

        after = client.get("/readiness").json()["active_connections"]

    assert after == baseline, f"streaming request leaked a session ({baseline} -> {after})"


def test_openai_streaming_does_not_approach_the_session_cap() -> None:
    """T-33: N sequential streaming requests must not accumulate sessions."""
    cp = _streaming_control_plane()
    # Lower the cap so a leak fails fast and unambiguously.
    cp._max_active_sessions = 3          # if this private poke feels wrong, pass
                                         # max_active_sessions=3 to the constructor instead
    app = create_gateway_app(cp)

    with TestClient(app) as client:
        for i in range(6):
            with client.stream(
                "POST",
                "/v1/chat/completions",
                json={"stream": True, "messages": [{"role": "user", "content": f"turn {i}"}]},
            ) as response:
                assert response.status_code == 200, f"request {i} failed — sessions leaked"
                "".join(response.iter_text())

        assert client.get("/readiness").json()["active_connections"] == 0
```

> **Prefer the constructor over the private poke.** `GatewayControlPlane.__init__` takes
> `max_active_sessions` (`src/hachi/gateway/control_plane.py:167`); pass it there and drop the
> `cp._max_active_sessions = 3` line. The sketch shows the poke only because
> `_streaming_control_plane()` is an existing zero-argument helper — extend the helper rather than
> reaching into a private attribute.

> **Drain the stream.** The `finally:` block only runs when the generator is exhausted or closed. A
> test that opens the stream and never reads it may not exercise your fix, and would go green for the
> wrong reason. Confirm the pre-fix failure message matches what §7 predicts before you trust it.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix with a leaked-session assertion.
- [ ] `active_connections` returns to baseline after a streaming `POST /v1/chat/completions`.
- [ ] N sequential streaming requests against a lowered cap all succeed.
- [ ] The close is inside the existing `finally:` and cannot raise into the response stream.
- [ ] The close runs off the event loop (`anyio.to_thread.run_sync`).
- [ ] If T-32 landed: sessions keyed by a client-supplied `user` id are **not** closed — only
      per-request ephemeral ones. Add a test asserting a `user`-keyed session survives two requests.
- [ ] The 19 pre-existing tests in `tests/test_gateway_openai_channels.py` still pass.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add LRU eviction, a TTL, or a session reaper to `GatewayControlPlane`.** This is the
  adjacent thing you will be tempted by: `:314-318` raises with no eviction and adding one *looks* like
  the general fix. It is not — it is a workaround that leaves booted agents holding LLM clients, worker
  threads, and SQLite handles until something evicts them, and it papers over any future leak instead
  of surfacing it. The bug is a missing `close_session` call, and that is all you are fixing.
- **Do not raise `max_active_sessions` or change its default.** Same reasoning: it converts "fails at
  100" into "fails at 1000".
- **Do not close the shared `"__default__"` session** if T-32 has not landed. Other callers are inside
  it (that is defect 1); closing it mid-flight is strictly worse than the leak.
- **Do not close `user`-keyed sessions.** They exist precisely to persist across requests.
- **Do not "fix" the disconnect handling** at `src/hachi/gateway/fastapi_app.py:1727-1731`. That
  `control_plane.interrupt(session_id)` is **correct** in this handler because the session is
  per-request — see [T-29](T-29-sse-disconnect-scope.md) §3.4, which explicitly protects it.
- **Do not touch the channels webhook** (`:1818` onward). Its sessions are keyed per sender and are
  meant to persist.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_gateway_openai_channels.py

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`, and coordinate with any sibling task landing first):

```markdown
### BB-N — OpenAI-facade streaming leaked one booted session per request until the cap jammed

- **Symptom:** after ~100 streaming `POST /v1/chat/completions` requests the gateway rejected ALL new
  sessions — including the web UI's — with "Maximum active sessions reached (100)", permanently,
  until the process was restarted. `GET /readiness` showed `active_connections` climbing
  monotonically and never falling.
- **Root cause:** the streaming path mints `session_key = f"openai-{chat_id}"` from a fresh UUID per
  request, so `get_or_create_session` always missed and booted a full agent — and `close_session` was
  never called anywhere in the facade. The cap at `GatewayControlPlane.create_session` is a hard
  raise with no LRU and no eviction, so the leak was terminal rather than degrading.
- **Fix:** call `close_session(session_id)` in `_openai_event_stream`'s existing `finally:` block,
  off the event loop via `anyio.to_thread.run_sync`, guarded so a teardown error cannot raise into a
  partially-sent response stream.
- **Avoid:** if a code path CREATES a session, that same path owns closing it — put the close in the
  `finally:` at the point of creation, not in a reaper. A hard cap with no eviction turns any session
  leak into a permanent outage, so treat "who closes this?" as part of writing the create.
- **Locked by:** `tests/test_gateway_openai_channels.py` — `test_openai_streaming_closes_its_session`,
  `test_openai_streaming_does_not_approach_the_session_cap`
```

## 12. Known traps

- **BB-4 does NOT apply.** You are changing lifecycle behaviour inside an existing handler — no route
  is added or removed and no response shape changes. Do **not** regenerate the OpenAPI spec or the
  frontend types; a spurious regeneration diff makes `check:api` noisy for the next person.
  (It *does* apply to [T-32](T-32-facade-session-isolation.md), which changes the request model.)
- **`close_session` raises on an unknown id** (`src/hachi/gateway/control_plane.py:537-538`:
  `raise GatewayProtocolError("Unknown session_id")`). A double-close, or a close after the session was
  already torn down, raises. Always guard it.
- **`close_session` also deletes the persisted transcript** (`:531-535`, via `self._delete_session`), so
  the conversation disappears from the recent-sessions list. For an ephemeral per-request facade session
  that is what you want — but know it happens, and do not apply the same call to `user`-keyed or
  channel sessions where the transcript is the point.
- **`close_session` calls `_on_disconnect`, which can block** (runtime teardown of a booted agent). Run
  it in a thread, as the handler already does for its other control-plane calls.
- **The `finally:` block runs only if the generator is exhausted or closed.** If a test opens the
  stream without draining it, your fix may never execute — which is why §7 insists on draining and on
  confirming the pre-fix failure.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant to the §4 shell repro,
  not to the unit tests.
