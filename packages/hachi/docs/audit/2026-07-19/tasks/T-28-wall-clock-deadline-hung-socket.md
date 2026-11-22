# T-28 · Make the wall-clock deadline (and cancel) survive a socket that stops delivering chunks

|  |  |
|---|---|
| **Source finding** | CF-7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) ("the loop's wall-clock deadline only checks between chunks — a hung connection defeats it") |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | **[T-23-thread-llm-timeout.md](T-23-thread-llm-timeout.md) — do not start until it has landed** |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/core/loop.py`, one test file |

---

## 1. Brief

`ExecutionLoop._stream_generate` checks the wall-clock deadline **after** each chunk
arrives. The check therefore sits *downstream* of a blocking `next(gen)` call. A socket that
accepts the request and then never delivers another byte blocks inside `next(gen)`
indefinitely, and the deadline never fires — nor does the user's cancel. When you are done,
a stalled stream terminates the turn within a bounded time regardless of whether another
chunk ever arrives.

## 2. Why this matters

This is the failure mode that makes an unattended agent look dead rather than broken. `run()`
defaults to `max_wall_seconds = 600.0` and the product *tells the user* a turn is bounded —
`[TIME LIMIT REACHED] Turn exceeded 600s wall-clock limit.` A stalled socket makes that
message unreachable. The same defect disables the **stop button**: the cancel check sits on
the identical line-of-execution and is defeated identically. A user pressing Stop on a hung
turn gets nothing.

**Sequencing matters here.** T-23 gives the transport a real timeout, which is the *primary*
defence and fixes the majority of real-world stalls at the right layer. This task is the
belt-and-braces for the cases a transport timeout does not cover — most importantly a server
that keeps the connection alive with periodic bytes (SSE keep-alives, whitespace pings) while
producing no content, which never trips a read timeout at all. **Land T-23 first or you will
be building the second line of defence with no first line.**

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The defect

`src/hachi/core/loop.py:664-697` — `_stream_generate`. Its own docstring promises the
behaviour it does not deliver:

```python
    def _stream_generate(self, on_delta: Callable[[str], None], **kwargs: Any) -> LLMResponse:
        """Drive generate_stream(), emit per-chunk callbacks, return the LLMResponse.
        ...
        Checks the cancel flag and wall-clock deadline after each chunk so an
        in-flight generation can be interrupted promptly by cancel() or a timeout.
        """
        delay = _LLM_RETRY_BASE_DELAY
        for attempt in range(1, _MAX_LLM_RETRIES + 1):
            chunks_yielded = 0
            streamed_parts: list[str] = []
            try:
                gen = self._turn_client.generate_stream(**kwargs)        # :682
                while True:
                    try:
                        chunk = next(gen)                                # :685  ← BLOCKS HERE
                    except StopIteration as si:
                        return si.value
                    chunks_yielded += 1
                    streamed_parts.append(chunk)
                    on_delta(chunk)
                    # Cooperative mid-stream cancel: check after each chunk so an
                    # in-flight generation stops as soon as the next chunk arrives.
                    if self._cancel_event.is_set():                      # :693
                        raise _StreamCancelled("".join(streamed_parts))
                    # Wall-clock deadline check inside the stream loop.
                    if self._wall_deadline is not None and time.monotonic() >= self._wall_deadline:
                        raise _StreamTimedOut("".join(streamed_parts))   # :697
```

Read the control flow literally: `:693` and `:696` are only reachable **after** `:685`
returns. The comment at `:691-692` states the constraint honestly — *"stops as soon as the
next chunk arrives"* — which is precisely the bug when the next chunk never arrives.

The `_cancel_event` check at `:693` has the **identical** defect. Both are one problem.

### 3.2 The deadline itself is fine

`src/hachi/core/loop.py:878-883`:

```python
        # Wall-clock deadline for this run() call (None when disabled).
        # Set before anything else so the streaming helper can read it.
        if self.max_wall_seconds > 0:
            self._wall_deadline: float | None = time.monotonic() + self.max_wall_seconds   # :881
        else:
            self._wall_deadline = None
```

Default `max_wall_seconds: float = 600.0` (`loop.py:399`, stored at `:460`). The value and
the arithmetic are correct — only the *reachability of the check* is broken.

`_StreamTimedOut` is defined at `loop.py:148` and handled in `run()` at `:1067`, emitting
`SESSION_TIME_LIMIT` with the partial text; `_StreamCancelled` at `:136`, handled at `:1055`.
Both handlers are correct and must keep working — this task changes *when* the exception is
raised, not what happens after.

### 3.3 The module is synchronous — asyncio is not available in place

```
$ grep -c "async def" src/hachi/core/loop.py   → 0
```

`_stream_generate` is a plain method driving a plain generator. There is no event loop to
attach `asyncio.wait_for` to. Any solution must work with threads or with the transport.

An existing facility is available: `ExecutionLoop` already owns a
`concurrent.futures.ThreadPoolExecutor` at `loop.py:479` (`self._tool_pool`), shut down in
`shutdown()` at `:662`.

### 3.4 Which providers actually hang today

- **Anthropic:** `core/llm.py:403-405` streams via the SDK context manager:
  ```python
          with self.client.messages.stream(**kwargs) as stream:
              yield from stream.text_stream
  ```
  Before T-23, that client is constructed with `timeout=None`, which httpx interprets as
  **no timeout at all** (see T-23 §3.4 — verified against `anthropic` 0.105.2). So `next(gen)`
  can block forever. **This is the live hang.**
- **OpenAI-compatible:** `core/llm.py:443` builds `httpx.Client(timeout=timeout)` with a
  default of 60 s (`:427`) and streams through `self._http.stream(...)` (`llm.py:699`). A
  dead socket already raises `ReadTimeout` there. **This path is already defended** against
  a fully-silent socket.

The asymmetry is more evidence for the sequencing: T-23 brings Anthropic up to the level
OpenAI-compat already has. **What neither gets from a transport timeout is protection
against a socket that stays alive but produces no content** — that residual case is what
this task closes.

## 4. Reproduce the failure

**Not reproducible against a real provider**, and you must not build a hostile network
endpoint to try. It is reproducible **in-process** with a fake client, and that is exactly
the regression test:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import sys, time, threading; sys.path.insert(0, "src")

# A generator that yields one chunk then blocks forever — a socket that stops delivering.
def hung_stream():
    yield "hello"
    time.sleep(3600)            # stands in for a blocking socket read
    yield "never"               # pragma: no cover

gen = hung_stream()
deadline = time.monotonic() + 2.0

print("first chunk:", next(gen))
t0 = time.monotonic()
done = threading.Event()

def drain():
    try:
        next(gen)               # <-- loop.py:685 lives here
    finally:
        done.set()

threading.Thread(target=drain, daemon=True).start()
done.wait(timeout=4.0)
print(f"deadline was {deadline - t0:.1f}s away; after 4s the drain finished: {done.is_set()}")
print("-> the deadline check at loop.py:696 is downstream of this call and never runs")
PY
```

**You will see now:** `the drain finished: False` — control never returns from `next(gen)`,
so the checks at `:693` and `:696` are unreachable and the 2 s deadline is never evaluated.

**You should see after the fix:** the turn terminates within roughly the deadline, `run()`
returns the `[TIME LIMIT REACHED] Turn exceeded …` string, and the partial text (`"hello"`)
is preserved.

**Code-reading proof**, which is the primary evidence: `loop.py:685` is a blocking call;
`:693` and `:696` are lexically and temporally after it; there is no timer, signal, watchdog
or timeout anywhere between `:682` and `:685`. Nothing in the module can interrupt it.

## 5. What "fixed" looks like

**This section names the options and makes a recommendation. §9 flags what is genuinely a
judgement call.**

**Option A — transport-level timeout (this is T-23, already landed as your dependency).**
Bounds a fully-silent socket at the transport layer, which is where it belongs. **Necessary,
and not sufficient**: it does not fire when the server keeps the connection warm with
keep-alive bytes that carry no content, and it bounds *inter-byte* silence, not total turn
duration.

**Option B — drain the generator on a worker thread; the loop thread waits with a timeout.
← RECOMMENDED.**

Move the `next(gen)` call into a worker (`self._tool_pool` at `loop.py:479` already exists,
or a dedicated single-use thread), have it push chunks onto a `queue.Queue`, and have
`_stream_generate` do `q.get(timeout=…)` with the timeout computed from
`self._wall_deadline`. The main loop thread then becomes responsive to **both** the deadline
and `self._cancel_event` on a bounded interval, whatever the socket does.

Why this one:

- It fixes the cancel path and the deadline path with **one** change — they are the same
  defect (§3.1).
- It requires no new dependency, no signals (which are main-thread-only and useless in the
  gateway's worker threads), and no async conversion.
- It preserves the existing exception contract exactly: raise `_StreamTimedOut` /
  `_StreamCancelled` with `"".join(streamed_parts)` as before, and `run()`'s handlers at
  `loop.py:1055` / `:1067` keep working untouched.

Its honest cost: **the worker thread stays blocked** on the dead socket after the loop thread
gives up. That is a bounded leak, and it is bounded *by Option A* — the transport timeout from
T-23 eventually raises inside the worker and it exits. This is the concrete reason T-23 is a
hard dependency rather than a suggestion. Make the worker a daemon so it can never block
interpreter shutdown, and make sure a leaked worker cannot call `on_delta` after the turn has
ended (guard the callback with the turn's cancel/timeout state, or drain into the queue only
and let the loop thread own all callbacks — prefer the latter, it is simpler to reason about).

**Option C — a watchdog thread that closes the underlying HTTP stream.** Would genuinely
unblock the read rather than abandoning it. Rejected as the primary approach: it requires
reaching through `BaseLLMClient` into provider-specific transport internals (the Anthropic SDK
stream context manager vs. an `httpx` streaming response), which breaks the client
abstraction and is different code per provider. Mention it in the commit message as
considered-and-rejected.

**Whichever you choose, do not change:** the deadline arithmetic (`loop.py:880-883`), the
exception types (`:136`, `:148`), the `run()` handlers (`:1055`, `:1067`), or the
partial-text semantics. The user-visible contract is right; only the reachability of the
check is wrong.

## 6. Steps

1. **Confirm T-23 has landed.** `grep -n "timeout" src/hachi/core/llm.py` — `create_llm_client`
   must pass a timeout to `AnthropicClient`. If it does not, stop and do T-23 first.
2. **Write the regression test from §7 first.** Run it. Watch it hang, then fail on the
   test-level timeout.
3. Implement Option B inside `_stream_generate` (`loop.py:664-697`): worker drains `gen` into
   a `queue.Queue`; the loop thread does a bounded `get`, and on each wakeup evaluates
   `self._cancel_event` and `self._wall_deadline` — **before** consuming the next chunk, so
   the checks are no longer downstream of the blocking call.
4. Keep the raise sites semantically identical: `_StreamCancelled(...)` /
   `_StreamTimedOut(...)` carrying `"".join(streamed_parts)`.
5. Make the worker a daemon thread and ensure it cannot invoke `on_delta` after the loop
   thread has abandoned the stream.
6. Verify the cancel path too — add a second test for `cancel()` against a hung stream.
7. Run the FULL suite. This touches the hot path of every turn in the product; a scoped run
   is not evidence ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
8. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_loop_backstop_cancel.py` (existing — it already owns the cancel and
  backstop tests and has the loop fixtures you need)
- **Test name:** `test_wall_deadline_fires_when_stream_stops_delivering_chunks`
- **It must assert:** a real `ExecutionLoop.run()` against a client whose `generate_stream`
  yields one chunk and then blocks **returns** — with the `[TIME LIMIT REACHED]` string and
  the partial text — within a bounded time. Assert on the returned value and on measured
  elapsed time being below a generous ceiling. This is real observed behaviour, not a mock's
  return value.
- **It must FAIL before your fix** by **hanging** until the test-level timeout kills it.

### ⚠️ A test that can hang forever is worse than no test

Use a short `max_wall_seconds` (e.g. 1.0) and bound the block with an `threading.Event.wait`
rather than a bare `time.sleep`, so a failing run cannot wedge CI. Check whether the repo has
`pytest-timeout` available before relying on a `@pytest.mark.timeout` decorator — **do not
add it as a dependency** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3); if it is absent, bound
the fake's block itself (e.g. `event.wait(10.0)`) so the worst case is a slow test, not a
hung one.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

import threading
import time

from hachi.core.llm import BaseLLMClient, LLMResponse


class _HungStreamLLM(BaseLLMClient):
    """Yields one chunk, then stalls — a socket that accepts and stops delivering."""

    def __init__(self) -> None:
        self.model = "m"
        self.max_tokens = 4096
        self.released = threading.Event()   # bounded: the fake never blocks forever

    def generate(self, *a, **kw) -> LLMResponse:
        return LLMResponse(content="ok")

    def generate_stream(self, *a, **kw):
        yield "hello"
        self.released.wait(10.0)            # stands in for a blocking socket read
        return LLMResponse(content="hello")

    def list_models(self):
        return []


def test_wall_deadline_fires_when_stream_stops_delivering_chunks() -> None:
    """A stream that stops delivering chunks must not defeat the wall-clock deadline.

    The deadline check at loop.py:696 sits AFTER the blocking next(gen) at :685, so a
    socket that never delivers another chunk blocks the loop thread forever and the
    turn never times out. The cancel check at :693 has the identical defect.
    """
    llm = _HungStreamLLM()
    loop = ExecutionLoop(
        llm,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        max_wall_seconds=1.0,
    )
    loop.add_user_message("go")

    t0 = time.monotonic()
    try:
        result = loop.run(max_iterations=1)
    finally:
        llm.released.set()          # never leave the fake's worker parked
    elapsed = time.monotonic() - t0

    assert "[TIME LIMIT REACHED]" in result, result
    assert "hello" in result, "the partial text before the stall must be preserved"
    assert elapsed < 5.0, f"deadline was 1.0s; run() took {elapsed:.1f}s"
```

Add the sibling test for cancel — same fake, call `loop.cancel()` from a timer thread after
the first chunk, assert `run()` returns `[CANCELLED] hello` promptly. **Both defects are the
same line of code; both need a lock.**

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The most likely cause of a false pass: a fake whose `generate_stream` does not actually
> block (e.g. `time.sleep(0.1)`), which lets the existing post-chunk check fire normally.

## 8. Acceptance criteria

- [ ] T-23 has landed (verified, not assumed).
- [ ] Both regression tests from §7 exist and hung/failed before the fix.
- [ ] `run()` returns `[TIME LIMIT REACHED]` within a bounded time against a stalled stream,
      **with partial text preserved**.
- [ ] `cancel()` interrupts a stalled stream and returns `[CANCELLED] <partial>`.
- [ ] The exception types (`_StreamCancelled` `loop.py:136`, `_StreamTimedOut` `:148`) and
      `run()`'s handlers (`:1055`, `:1067`) are **unchanged**.
- [ ] Any worker thread introduced is a **daemon** and cannot invoke `on_delta` after the
      turn ends.
- [ ] No new runtime dependency.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts) —
      **FULL suite, not scoped**.
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not convert `core/loop.py` to async.** Zero `async def` today (§3.3). "Use
  `asyncio.wait_for`" is the reflex answer and it means rewriting the loop and every caller —
  a multi-week change. Solve it with threads or the transport.
- **Do not use `signal.alarm` / `SIGALRM`.** Main-thread-only, POSIX-only, and turns are
  driven from gateway worker threads. It will appear to work in a test and do nothing in
  production. It is also Unix-only, and this repo is developed on Windows.
- **Do not reach into provider transport internals** to close the socket (Option C). It
  breaks the `BaseLLMClient` abstraction and needs different code for the Anthropic SDK's
  stream context manager (`llm.py:403-405`) than for `httpx` streaming (`llm.py:699`).
- **Do not change `max_wall_seconds`' default of 600.0** (`loop.py:399`), nor the deadline
  arithmetic at `:880-883`. They are correct.
- **Do not restructure the retry loop** that `_stream_generate` sits inside
  (`loop.py:677-716`) — that is
  [T-24-collapse-retry-layers.md](T-24-collapse-retry-layers.md), and if both are in flight
  you will conflict. Coordinate: whoever lands second rebases.
- **Judgement call left to you:** the exact wakeup interval for the bounded `get` (a
  granularity/CPU trade-off) and whether to reuse `self._tool_pool` (`loop.py:479`) or spawn
  a dedicated thread per stream. Reusing the pool risks starving tool execution if streams
  hold workers; a dedicated daemon thread per stream is simpler to reason about and is the
  safer default. **State your choice and the reason in the commit message.**
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking — including `pytest-timeout`.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Targeted (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_loop_backstop_cancel.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done. This change is on the hot
path of **every** turn in the product — a scoped run is not sufficient evidence. Run the
FULL suite and report its counts, and watch specifically for new flakiness (a
threading-related change that makes 1-2 unrelated tests intermittently fail is a real
regression, not noise).

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — A stalled stream defeated both the wall-clock deadline and the stop button

- **Symptom:** a turn whose provider accepted the request and then stopped delivering chunks
  hung indefinitely. The 600s wall-clock limit never fired, `[TIME LIMIT REACHED]` was never
  returned, and pressing Stop did nothing. From the UI the agent looked dead, not failed.
- **Root cause:** in `ExecutionLoop._stream_generate` (`core/loop.py:664`), both the cancel
  check (`:693`) and the deadline check (`:696`) sit AFTER the blocking `chunk = next(gen)`
  at `:685`. They are only reachable once another chunk arrives — the comment at `:691-692`
  says so ("as soon as the next chunk arrives"). Nothing between `:682` and `:685` could
  interrupt the read. The module is fully synchronous (`grep -c "async def"` → 0), so no
  asyncio timeout was available in place. It was worst on Anthropic, whose client was built
  with `timeout=None` = no transport timeout at all (see the T-23 entry); the OpenAI-compat
  path already had a 60s httpx read timeout.
- **Fix:** the generator is drained on a daemon worker thread into a bounded queue; the loop
  thread waits with a timeout derived from `_wall_deadline` and evaluates cancel + deadline
  on every wakeup, so neither check is downstream of a blocking read. Exception types and
  `run()`'s handlers (`:1055`, `:1067`) are unchanged, so partial-text semantics are
  preserved.
- **Avoid:** a timeout/cancel check placed after a blocking call is not a timeout — it is a
  post-condition. Any "check the deadline each iteration" loop must be able to wake up
  WITHOUT the thing it is waiting for. And a transport-level timeout is the first line of
  defence, not an optional extra.
- **Locked by:** `tests/test_loop_backstop_cancel.py` —
  `test_wall_deadline_fires_when_stream_stops_delivering_chunks`
```

## 12. Known traps

- **Sequence after T-23.** If you land this first, the worker thread you introduce will park
  forever on Anthropic (`timeout=None` = no timeout), converting a hang into a **thread
  leak** — measurably worse under load. T-23 is what reaps it. Verify T-23 is in before you
  start.

- **`OpenAICompatibleClient` is already defended** against a fully-silent socket
  (`httpx.Client(timeout=60.0)`, `llm.py:427`/`:443`). If you write your test against a real
  OpenAI-compat client you may see a `ReadTimeout` and conclude the bug does not exist. Test
  with a **fake** that blocks in Python (§7), which is provider-agnostic and is the honest
  reproduction.

- **A test that hangs forever will wedge CI.** Bound the fake's block itself
  (`threading.Event().wait(10.0)`), do not rely on a test-runner timeout that may not be
  installed, and always release the fake in a `finally:`.

- **Do not let a leaked worker call `on_delta` after the turn ended.** It would append text to
  a conversation that has already returned — a data-corruption bug worse than the hang.
  Prefer having the worker only enqueue, and the loop thread own every callback.

- **Threading changes surface latent flakiness.** After the change, run the full suite
  **twice**. If a previously-stable unrelated test starts failing intermittently, that is
  yours.

- **`_partial_text` vs `streamed_parts`.** `run()`'s handlers build the final string as
  `"".join(self._partial_text) + exc.partial_text` (`loop.py:1058`, `:1068`). If you
  restructure where chunks accumulate, both halves must stay correct or the user loses
  partial output on timeout — which is exactly what the current design goes out of its way to
  preserve.

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
