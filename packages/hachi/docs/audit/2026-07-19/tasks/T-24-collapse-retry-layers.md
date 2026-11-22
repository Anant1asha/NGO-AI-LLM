# T-24 · Collapse the stacked retry layers; make resilience the sole retry owner

|  |  |
|---|---|
| **Source finding** | CF-7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **the review UNDERCOUNTS the layers — see [CORRECTIONS.md](CORRECTIONS.md) §4** |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none — but land [T-23-thread-llm-timeout.md](T-23-thread-llm-timeout.md) first if you are doing both, so retries sit on top of a bounded call |
| **Blocks** | nothing |
| **Effort** | ~2 days |
| **Difficulty** | High (needs design judgement — read §5 and §9) |
| **Files you will touch** | `src/hachi/core/loop.py`, `src/hachi/core/resilience.py`, `tests/test_resilience.py`, `tests/test_multi_provider.py`, one new test file |

---

## 1. Brief

A single failing LLM call is retried by **four independent layers** that do not know about
each other, using **two unrelated definitions of "transient"** and **two different backoff
schedules**. Worst case on the streaming path: **21 provider calls and ~12 seconds of
thread-blocking sleep** before an error reaches the user — and each of those 21 is itself
up to 3 HTTP requests inside the Anthropic SDK. When you are done, the resilience layer is
the sole retry owner, there is one `is_transient()` used by everything, and the loop-level
retry is gone.

## 2. Why this matters

Two harms, and the second is the one that actually bites.

**Retry amplification.** A provider that is rate-limiting you gets hit 21 more times per
turn, from a client that then blocks a thread for 12 s. That is the opposite of what a
retry policy is for.

**Two taxonomies means two behaviours for one condition.** `_RETRYABLE_STATUS` in the loop
retries 408, 409 and 529; `_TRANSIENT_STATUS_CODES` in resilience does not. So HTTP 529
("overloaded" — the one Anthropic actually returns under load) is retried by one layer and
treated as terminal by the other. Whether a 529 fails over to your configured fallback model
or just burns loop retries against the same overloaded primary depends on which layer sees
it first. Nobody can reason about that, and no test asserts it.

The point of this task is **one owner, one definition**. If your diff leaves two `is
transient` predicates alive, it has not done the job.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Layer 1 — the loop

`src/hachi/core/loop.py:58-62`:

```python
# Transient HTTP statuses worth retrying on (rate limit, overloaded, gateway errors).
_RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}
_RETRYABLE_HINTS = ("overloaded", "rate limit", "timeout", "timed out", "temporarily", "connection")
_MAX_LLM_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 1.0
```

`loop.py:89-103` — `_is_retryable_llm_error`, detection strategy #1: **HTTP status, falling
back to message-substring matching**:

```python
def _is_retryable_llm_error(exc: Exception) -> bool:
    """Best-effort detection of transient LLM/provider errors (provider-agnostic).

    Checks an HTTP status code (Anthropic/OpenAI SDK exceptions expose
    ``status_code``; httpx exposes ``response.status_code``) and falls back to
    message heuristics for connection/timeout errors that carry no status.
    """
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status in _RETRYABLE_STATUS
    message = str(exc).lower()
    return any(hint in message for hint in _RETRYABLE_HINTS)
```

`loop.py:677-716` — the retry loop inside `_stream_generate` (defined at `:664`):

```python
        delay = _LLM_RETRY_BASE_DELAY                                    # :677
        for attempt in range(1, _MAX_LLM_RETRIES + 1):                   # :678
            ...
            except Exception as exc:
                if (
                    chunks_yielded > 0
                    or attempt >= _MAX_LLM_RETRIES
                    or not _is_retryable_llm_error(exc)
                ):
                    raise
                logger.warning(
                    "LLM stream failed pre-output (attempt %d/%d): %s — retrying in %.1fs", ...
                )
                self.on_event(LLM_RETRY, {"attempt": attempt, "error": str(exc)})
                time.sleep(delay)                                        # :715
                delay *= 2                                               # :716
```

Backoff: **1.0 s, 2.0 s.**

### 3.2 Layer 2 — resilience

`src/hachi/core/resilience.py:33-50` — detection strategy #2: **exception class-name
substring matching, falling back to a status attribute**. A different, smaller status set:

```python
# HTTP status codes / exception patterns that indicate a transient error worth retrying.
_TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

# Exception type names that are transient (matched by class name substring).
_TRANSIENT_EXCEPTION_NAMES: tuple[str, ...] = (
    "timeout",
    "Timeout",
    "RateLimitError",
    "APIConnectionError",
    "ConnectError",
    "ReadTimeout",
    "WriteTimeout",
    "PoolTimeout",
    "RemoteProtocolError",
    "InternalServerError",
    "OverloadedError",
    "ServiceUnavailable",
)
```

`resilience.py:53-63` — `_is_transient`:

```python
def _is_transient(exc: BaseException) -> bool:
    """Return ``True`` when *exc* is likely a transient error worth retrying."""
    cls_name = type(exc).__name__
    for name in _TRANSIENT_EXCEPTION_NAMES:
        if name in cls_name:
            return True
    # httpx / anthropic SDK may embed the status code as an attribute.
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if isinstance(status, int) and status in _TRANSIENT_STATUS_CODES:
        return True
    return False
```

**Divergence, stated plainly: 408, 409 and 529 are retryable at the loop and terminal at
resilience.** The loop inspects the *message*; resilience inspects the *class name*. These
are two unrelated strategies for answering one question.

`resilience.py:278-306` — the retry loop in `resilient_call`:

```python
    for attempt in range(1, policy.max_attempts + 1):
        ...
        except Exception as exc:
            ...
            if not _is_transient(exc) or attempt >= policy.max_attempts:
                raise
            wait = policy.backoff_base_s * (2 ** (attempt - 1))          # :296
            ...
            time.sleep(wait)                                             # :306
```

With the defaults (`max_attempts=3`, `backoff_base_s=0.5`, `resilience.py:84-85`), backoff is
**0.5 s, 1.0 s** — half the loop's schedule, for the same failure.

### 3.3 Layer 3 — the fallback chain

`resilience.py:349-390` — `_call_with_chain` wraps **each** chain element in its own
`resilient_call`:

```python
        chain = [(self._inner, self._recorder)] + self._fallbacks        # :365
        if not include_primary:
            chain = chain[1:]
        ...
        for idx, (client, recorder) in enumerate(chain):                 # :370
            ...
            fn = fn_builder(client)
            try:
                return resilient_call(fn, self._policy, recorder)        # :380
```

### 3.4 Layer 4 — the SDK's own retries (the review missed this)

`anthropic` **0.105.2**, `anthropic/_constants.py:10`:

```python
DEFAULT_MAX_RETRIES = 2
```

`anthropic/_client.py:156` — `Anthropic.__init__`:

```python
        max_retries: int = DEFAULT_MAX_RETRIES,
```

Hachi never overrides it (`core/llm.py:273` passes only `api_key` and `timeout`). So **every
single one of the calls counted below is up to 3 HTTP requests**, with the SDK's own
`INITIAL_RETRY_DELAY = 0.5` / `MAX_RETRY_DELAY = 8.0` backoff (`_constants.py:13-14`) on top
of everything in §3.1–3.3.

### 3.5 The worst case — and why streaming is the bad path

Streaming does **not** run the primary through `resilient_call`. `resilience.py:418-442` —
`ResilientClient.generate_stream` calls the inner client directly:

```python
    def generate_stream(...) -> Generator[str, None, LLMResponse]:
        """Stream text deltas via the primary client (fallback uses generate)."""
        # Streaming complicates the retry/fallback story; we use the primary directly
        # for streaming and fall back to generate() on failure.
        t0 = time.monotonic()
        try:
            response = yield from self._inner.generate_stream(...)       # :434 — no retry
```

…and on failure degrades to non-streaming `generate()` over the chain with the primary
skipped (`resilience.py:451-461`):

```python
                response = self._call_with_chain(
                    lambda c: (
                        lambda: c.generate(...)
                    ),
                    include_primary=False,                               # :460
                )
```

**Arithmetic, with 2 configured fallbacks:**

| | calls | sleep |
|---|---|---|
| primary stream (direct, no retry) | 1 | 0 |
| fallback[0] via `resilient_call` (3 attempts) | 3 | 0.5 + 1.0 = 1.5 s |
| fallback[1] via `resilient_call` (3 attempts) | 3 | 0.5 + 1.0 = 1.5 s |
| **per loop attempt** | **7** | **3.0 s** |
| × 3 loop attempts (`_MAX_LLM_RETRIES`) | **21** | 9.0 s |
| + loop backoff (1.0 + 2.0) | | 3.0 s |
| **TOTAL** | **21 provider calls** | **~12 s** |

**Use 12 s, not the review's 16 s** — 16 s is not reproducible from these constants.
And with §3.4, those 21 calls are up to **63 HTTP requests**.

### 3.6 Both sleeps block a real OS thread

```
$ grep -c "async def" src/hachi/core/loop.py         → 0
$ grep -c "async def" src/hachi/core/resilience.py   → 0
```

Both modules are fully synchronous, so `time.sleep` is not blocking an event loop *directly*.
But turns are driven from the gateway, so each of these sleeps parks a threadpool worker for
its duration. Twelve seconds of parked worker per failing turn, multiplied by concurrent
sessions, is the actual capacity cost.

## 4. Reproduce the failure

**Not reproducible against a live provider**, and you should not build a hostile endpoint.
It is provable two ways, both real.

**(a) The divergent taxonomies — copy-pasteable, no network:**

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import sys; sys.path.insert(0, "src")
from hachi.core.loop import _is_retryable_llm_error
from hachi.core.resilience import _is_transient

class Overloaded(Exception):
    status_code = 529          # what Anthropic returns under load

class Conflict(Exception):
    status_code = 409

for exc in (Overloaded("overloaded_error"), Conflict("conflict")):
    print(f"{type(exc).__name__:12} status={exc.status_code}  "
          f"loop={_is_retryable_llm_error(exc)!s:5}  resilience={_is_transient(exc)!s}")
PY
```

**You will see now:**

```
Overloaded    status=529  loop=True   resilience=False
Conflict      status=409  loop=True   resilience=False
```

Two layers, one exception, opposite answers.

**You should see after the fix:** identical values in both columns — because both columns
call the same function.

**(b) The call amplification** is provable by code reading only; §3.5 is that proof, and
the §7 regression test converts it into an executable assertion by counting invocations on a
fake client. Do not try to demonstrate it against a real provider.

## 5. What "fixed" looks like

**Target: the resilience layer is the sole retry owner.**

1. **One shared predicate.** Promote a single `is_transient(exc) -> bool` to be the only
   answer in the codebase. It should be the **union** of the two current strategies —
   class-name matching *and* status matching — over the **union** of the status sets
   (`{408, 409, 429, 500, 502, 503, 504, 529}`), keeping `_RETRYABLE_HINTS` message matching
   as the last resort for exceptions carrying neither. Dropping 529 would be a behaviour
   regression on the provider Hachi ships with by default.

   It lives in `core/resilience.py` (`core/loop.py` already imports from `core/resilience`'s
   neighbourhood; `resilience.py:26` imports *from* `llm.py`, so keep the new symbol in
   `resilience.py` and import it into `loop.py`, never the reverse — see §12).

2. **Delete the loop-level retry.** `loop.py:677-716`: `_stream_generate` becomes a single
   pass — drive the generator, propagate the exception. `_MAX_LLM_RETRIES`,
   `_LLM_RETRY_BASE_DELAY`, `_RETRYABLE_STATUS`, `_RETRYABLE_HINTS` and
   `_is_retryable_llm_error` all become dead and should go with it.

   ⚠️ **Preserve the `LLM_RETRY` runtime event.** `loop.py:714` emits it
   (`self.on_event(LLM_RETRY, {...})`) and UI surfaces consume it. Re-emit it from the
   resilience layer — `resilient_call` already has an `on_failover` hook invoked at
   `resilience.py:304-305` — so the user-visible "retrying…" signal does not disappear.
   Grep `LLM_RETRY` before deleting anything.

3. **Make streaming retry properly.** With the loop's retry gone, a *pre-stream* failure
   (`chunks_yielded == 0`) has no retry at all unless resilience handles it. Route the
   primary streaming attempt through the same policy, keeping the existing H7 guarantee
   documented at `resilience.py:359-363`: **a stream that already emitted output must never
   be re-invoked** (double-print / double-bill). The `chunks_yielded > 0` condition at
   `loop.py:701-706` encodes exactly that rule — move the rule, do not lose it.

4. **Decide what happens to the SDK's own `max_retries`.** This is a real decision and it is
   yours to make and to state. Two defensible answers:
   - Set `max_retries=0` on `anthropic.Anthropic(...)` (`llm.py:273`) so the resilience layer
     is genuinely the only retrier and the call budget is exactly `max_attempts × chain`.
   - Leave it at 2 and *document* that the effective budget is 3× the resilience budget.

   Pick one. **State the choice and the reasoning in the commit message** — a reviewer
   cannot evaluate "resilience is the sole retry owner" without knowing which.

**Target worst case after the fix**, with 2 fallbacks and `max_attempts=3`: 3 (primary) + 3
+ 3 = **9 provider calls**, ~4.5 s of sleep — down from 21 / 12 s. Put your actual numbers
in the commit message.

## 6. Steps

1. **Write the regression tests from §7 first.** Run them. Watch them fail.
2. Add the unified `is_transient()` to `core/resilience.py` (union of both status sets +
   class-name matching + message-hint fallback). Keep `_is_transient` as an alias or
   rename call sites — do not leave two implementations.
3. Point `resilient_call` (`resilience.py:294`) at it. Run `tests/test_resilience.py`.
   `TestIsTransient` (`:87-107`) should still pass; if a case flips, that is the union
   working — check each one deliberately.
4. Point `loop.py` at the same function, deleting `_is_retryable_llm_error` (`:89`) and its
   two constants (`:59-60`).
5. Grep `LLM_RETRY` and re-home its emission onto `resilient_call`'s `on_failover` hook
   (`resilience.py:304-305`) before you delete `loop.py:714`.
6. Delete the retry loop in `_stream_generate` (`loop.py:677-716`), preserving the
   already-emitted-output rule (§5.3).
7. Route primary streaming through the policy so pre-stream failures are still retried once
   the loop no longer does it.
8. Decide the SDK `max_retries` question (§5.4). Implement and document.
9. Rerun `tests/test_resilience.py` and `tests/test_multi_provider.py` in full — see §12.
10. Full `uv run python scripts/preflight.py`, report real counts.
11. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Two tests. The first is the honest, durable one; the second is the taxonomy pin.

- **File:** `tests/test_resilience.py` (existing — it already has `_FakeClient` at `:32`,
  `_TransientError` at `:62`, `_PermanentError` at `:68`, and `TestResilientClient` at `:281`)
- **Test 1 name:** `test_streaming_failure_does_not_amplify_provider_calls`
- **It must assert:** the **observed number of invocations on a fake client** for a single
  `ExecutionLoop` turn whose provider always fails. Count calls on the fake, not mock
  `call_count` on a patched internal. This is the assertion that makes amplification
  regressions impossible.
- **It must FAIL before your fix** with something like:
  `AssertionError: expected <= 9 provider calls, got 21`
- **Test 2 name:** `test_one_transient_taxonomy_for_loop_and_resilience`
- **It must assert:** for HTTP 529 and 408 (and one class-name-only case such as
  `ReadTimeout`), the loop's predicate and the resilience predicate return the **same**
  answer. After the fix that is trivially true because there is one function — so assert it
  as "the loop module exposes no second predicate", e.g. that `hachi.core.loop` has no
  `_is_retryable_llm_error` attribute and `hachi.core.resilience.is_transient` is what it uses.
- **It must FAIL before your fix** with: `True != False` for status 529.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

import pytest


class _AlwaysFailsCounting:
    """A client that fails every call and counts how many it received."""

    def __init__(self, model: str = "m") -> None:
        self.model = model
        self.max_tokens = 4096
        self.calls = 0

    def _boom(self):
        self.calls += 1
        exc = RuntimeError("overloaded")
        exc.status_code = 529          # retryable under BOTH taxonomies today
        raise exc

    def generate(self, *a, **kw):
        self._boom()

    def generate_stream(self, *a, **kw):
        self._boom()
        yield ""   # pragma: no cover — never reached


def test_streaming_failure_does_not_amplify_provider_calls() -> None:
    """One failing turn must not fan out into 21 provider calls.

    Loop-level retry x resilience-level retry x fallback chain multiply: 3 x (1 + 3 + 3).
    After collapsing to a single retry owner the budget is max_attempts x chain length.
    """
    # Build a ResilientClient with 2 fallbacks over counting fakes, wrap it in an
    # ExecutionLoop with backoff_base_s=0.0 (keep the test fast; the assertion is on
    # CALL COUNT, not wall time), run one turn, and sum the counters.
    ...
    total = primary.calls + fb1.calls + fb2.calls
    assert total <= 9, f"expected <= 9 provider calls, got {total}"


@pytest.mark.parametrize("status", [408, 409, 429, 500, 502, 503, 504, 529])
def test_one_transient_taxonomy_for_loop_and_resilience(status: int) -> None:
    """There must be exactly ONE definition of 'transient' in the codebase.

    Before the fix, loop._RETRYABLE_STATUS retried 408/409/529 and
    resilience._TRANSIENT_STATUS_CODES did not — so failover behaviour for an
    Anthropic 529 depended on which layer observed the error first.
    """
    import hachi.core.loop as loop_mod
    from hachi.core.resilience import is_transient

    exc = RuntimeError("boom")
    exc.status_code = status
    assert is_transient(exc) is True

    assert not hasattr(loop_mod, "_is_retryable_llm_error"), (
        "the loop still owns a second retry predicate"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Set `backoff_base_s=0.0` in the test policy so you are asserting on **call count**, never
> on elapsed wall time — a timing assertion here will be flaky on CI.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist and failed before the fix (state the observed
      pre-fix call count in the commit message).
- [ ] Exactly one `is_transient`-style predicate exists in `src/`;
      `grep -rn "_RETRYABLE_STATUS\|_RETRYABLE_HINTS\|_is_retryable_llm_error" src/` returns
      nothing.
- [ ] The union status set retries **529** (and 408, 409) — no behaviour regression on the
      default provider.
- [ ] `_MAX_LLM_RETRIES` / `_LLM_RETRY_BASE_DELAY` are gone from `core/loop.py`.
- [ ] The `LLM_RETRY` runtime event is still emitted on a retry (grep proves an emitter
      exists; a test asserts it fires).
- [ ] A stream that has already emitted output is still never re-invoked (the H7 rule at
      `resilience.py:359-363` survives).
- [ ] The SDK `max_retries` decision is implemented **and stated in the commit message**.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not make `core/loop.py` or `core/resilience.py` async.** Both are 100% synchronous
  (§3.6) and "the sleeps block a thread" makes async look like the fix. Converting either
  module is a multi-week change touching every caller. The fix here is *fewer sleeps*, not
  *non-blocking sleeps*.
- **Do not touch the circuit breaker.** `HealthRecorder`, `breaker_threshold`,
  `breaker_cooldown_s` and the half-open hysteresis are a *separate*, working mechanism
  (`tests/test_resilience.py:180-279` covers it). You will be reading that code constantly;
  leave it alone.
- **Do not remove the fallback chain.** It is a product feature, not a retry layer. Layer 3
  is only a problem because it *multiplies* with layers 1, 2 and 4 — collapsing 1 into 2 is
  the fix.
- **Do not change `timeout_s` plumbing** — that is
  [T-23-thread-llm-timeout.md](T-23-thread-llm-timeout.md).
- **Do not change cost attribution** while you are inside `resilience.py` — the
  `self.model` staleness at `:347` is
  [T-25-served-model-cost-attribution.md](T-25-served-model-cost-attribution.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking (no `tenacity`, no `backoff` — the repo has
  a working implementation).
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Targeted (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_resilience.py tests/test_multi_provider.py \
              tests/test_loop_backstop_cancel.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done. Because this task deletes
a retry path used across the whole product, a scoped run is **not** sufficient evidence —
run the FULL suite ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — Four stacked retry layers turned one failed LLM call into 21 provider calls and ~12s of blocked thread

- **Symptom:** a transient provider failure took ~12 seconds to surface as an error, during
  which a gateway worker thread was parked, and the provider received up to 21 calls (up to
  63 HTTP requests) for a single turn. Whether an Anthropic 529 failed over to the configured
  fallback model was nondeterministic-looking.
- **Root cause:** four independent retriers with no knowledge of each other —
  (1) `core/loop.py:677-716` `_stream_generate`, 3 attempts, backoff 1.0/2.0s;
  (2) `core/resilience.py:278-306` `resilient_call`, 3 attempts, backoff 0.5/1.0s;
  (3) the fallback chain (`resilience.py:349`) wrapping *each* element in (2); and
  (4) the `anthropic` SDK's own `DEFAULT_MAX_RETRIES = 2` (`_constants.py:10`), never
  overridden. Worse, (1) and (2) used unrelated definitions of "transient":
  `loop._RETRYABLE_STATUS` = `{408,409,429,500,502,503,504,529}` with message-substring
  fallback, vs `resilience._TRANSIENT_STATUS_CODES` = `{429,500,502,503,504}` with
  exception-class-name matching — so 408/409/529 retried at one layer and were terminal at
  the other. Streaming made it worst-case: `ResilientClient.generate_stream` (`:434`) calls
  the primary directly with no retry, then degrades to `generate()` over the chain with
  `include_primary=False` (`:460`).
- **Fix:** resilience is the sole retry owner. One `is_transient()` (union of both status
  sets + class-name + message-hint fallback) used by everything; the loop-level retry
  deleted; the `LLM_RETRY` event re-emitted from `resilient_call`'s `on_failover` hook so the
  UI signal survives; the H7 "never re-invoke a stream that already emitted output" rule
  preserved.
- **Avoid:** exactly one component may own retry for a given operation. When adding a
  resilience wrapper around existing code, DELETE the retry it replaces in the same commit —
  and check the vendor SDK, which usually retries too.
- **Locked by:** `tests/test_resilience.py` —
  `test_streaming_failure_does_not_amplify_provider_calls`,
  `test_one_transient_taxonomy_for_loop_and_resilience`
```

## 12. Known traps

- **Import direction.** `core/resilience.py:26` already does
  `from hachi.core.llm import BaseLLMClient, LLMResponse, Message`. Put the shared
  `is_transient` in `resilience.py` and import it into `loop.py`. Do **not** put it in
  `llm.py` and import from `resilience.py` — and never make `llm.py` import
  `resilience.py`.

- **Tests that will need AMENDING (not weakening):**
  - `tests/test_resilience.py:87-107`, `TestIsTransient` — four tests pinning the *current*
    narrow status set (`test_transient_by_status_code`, `test_non_transient_by_status_code`,
    `test_transient_by_class_name`, `test_generic_exception_not_transient`). Under the union
    set, `test_non_transient_by_status_code` may legitimately flip if it uses 408/409/529.
    **Read it, decide deliberately, and if you change it say in the commit message that you
    widened the taxonomy on purpose.** Do not silently relax an assertion.
  - `tests/test_resilience.py:281-374`, `TestResilientClient` — 8 tests over the chain,
    including `test_stream_failover_does_not_reinvoke_primary` (`:325`), which pins the H7
    rule you must preserve. If that one goes red, you have broken the rule, not the test.
  - `tests/test_multi_provider.py:213-326`, `TestFailoverUnderLoad` — note `:259`:
    ```python
            client._call_with_chain = _patched  # type: ignore[method-assign]
    ```
    It replaces `_call_with_chain` with a hand-rolled reimplementation. **If you change
    `_call_with_chain`'s signature or semantics, this test keeps passing against a stale
    copy of the old behaviour.** Update the replacement, or the test silently stops testing
    the code.

- **`LLM_RETRY` disappears if you just delete `loop.py:714`.** Grep it across `src/` and
  `frontend/` before deleting. A silently-vanished runtime event is a UI regression that no
  Python test will catch.

- **Timing assertions are flaky.** Assert on call counts with `backoff_base_s=0.0`, never on
  elapsed seconds.

- **The 16 s figure in the review is wrong.** The constants compute to ~12 s. Use 12 s, and
  put your own measured post-fix number in the commit message.

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
