# T-27 · Forward `max_tokens` through `ResilientClient` so enabling routing stops weakening the token ceiling

|  |  |
|---|---|
| **Source finding** | CF-1 #10 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **scope corrected by [CORRECTIONS.md](CORRECTIONS.md) §9** |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 hour |
| **Difficulty** | Low (mechanical) — one line of fix, the test is the work |
| **Files you will touch** | `src/hachi/core/resilience.py`, `tests/test_loop_backstop_cancel.py` |
| **Batch with** | [T-05-routing-cost-warnings-arity.md](T-05-routing-cost-warnings-arity.md) and [T-26-routing-boot-failure-visible.md](T-26-routing-boot-failure-visible.md) — three ~1-hour fixes, one commit each, one preflight run |

---

## 1. Brief

`ResilientClient` forwards exactly one attribute from the client it wraps: `model`. The
execution loop's pre-flight token-safety ceiling reads `max_tokens` off the turn client with
a defaulted `getattr`, so through a `ResilientClient` it silently reads **0** — and the
pre-flight check degrades into the post-hoc check it was explicitly written to replace. When
you are done, `ResilientClient` forwards `max_tokens` too, and the ceiling behaves the same
whether or not `[routing]` is enabled.

## 2. Why this matters

**The headline is the asymmetry, not the missing attribute.** With `[routing]` absent, the
turn client is a raw `AnthropicClient`, which exposes `max_tokens`, and the pre-flight
ceiling works exactly as designed. Turn `[routing]` on — a feature about cost and model
selection, i.e. something a *cost-conscious* operator enables — and a safety guardrail
silently gets weaker. The user opted into more control and received less protection, with no
signal.

The guardrail's own docstring explains precisely what is lost: a single generation can cross
the 2,000,000-token ceiling by its own full cost before the next iteration notices. That is
the runaway case the pre-flight check exists for.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The read

`src/hachi/core/loop.py:732-763` — `_safety_ceiling_exceeded`. The docstring states the
design; `:754-756` is where it fails:

```python
    def _safety_ceiling_exceeded(self) -> str | None:
        """Return a reason string if the hard token safety ceiling is hit — or would be
        crossed by the upcoming LLM call — else None.
        ...
        S1: checked PRE-FLIGHT, not just post-hoc. A pure ``snapshot >= ceiling``
        check only ever catches an overrun *after* a call has already happened —
        a single generation can cross the ceiling by its own full token cost before
        the next iteration's check notices. We instead add the upcoming call's
        worst-case token cost (bounded by ``_turn_client.max_tokens``, the
        provider's configured output-token cap) to the current snapshot, so a call
        that *would* cross the ceiling is refused before it starts.
        """
        if self.cost_tracker is None:
            return None
        snap = self.cost_tracker.snapshot()
        # Worst-case tokens the upcoming call could add: its bounded max output
        # tokens (0 if the client doesn't expose one — no client-based estimate
        # possible, falls back to the pure post-hoc check for that call).
        worst_case_next_call = getattr(self, "_turn_client", None)          # :754
        next_call_ceiling_tokens = getattr(worst_case_next_call, "max_tokens", 0) or 0   # :755
        projected = snap.total_tokens + next_call_ceiling_tokens            # :756
        if projected >= self._TOKEN_SAFETY_CEILING:                         # :757
            return (...)
        return None
```

`_TOKEN_SAFETY_CEILING: int = 2_000_000` — `loop.py:384`.

The comment at `:751-753` even documents the degraded mode as an intentional edge case
("0 if the client doesn't expose one"). It was written for exotic clients; in practice the
routed path hits it every turn.

### 3.2 The gap

`src/hachi/core/resilience.py:335-347` — `ResilientClient.__init__` forwards **only** `model`:

```python
    def __init__(
        self,
        inner: BaseLLMClient,
        policy: RetryPolicy,
        recorder: HealthRecorder,
        fallbacks: list[tuple[BaseLLMClient, HealthRecorder]] | None = None,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._recorder = recorder
        self._fallbacks: list[tuple[BaseLLMClient, HealthRecorder]] = fallbacks or []
        # Expose `model` attribute from inner for cost tracking / introspection.
        self.model: str = getattr(inner, "model", "unknown")            # :347
```

Proof that nothing else provides it:

```
$ grep -n "max_tokens\|__getattr__" src/hachi/core/resilience.py
(no output)
```

No `max_tokens` attribute, no `__getattr__` passthrough. So
`getattr(resilient_client, "max_tokens", 0)` → `0` → `projected == snap.total_tokens` → the
pre-flight check is exactly the post-hoc check.

### 3.3 Scope — this ONLY bites when the router is active

`src/hachi/core/loop.py:857-863`:

```python
        # P1-2: Classify the turn and resolve a (possibly tiered) client via the router.
        ...
        # When router is None, _turn_client stays as llm_client (byte-for-byte back-compat).
        self._turn_client = self.llm_client                             # :861
        if self.router is not None:
            self._resolve_turn_client(user_input_for_turn)              # :863
```

With `router is None`, `_turn_client` is the raw client. `AnthropicClient` sets
`self.max_tokens = max_tokens` at `llm.py:275`; `OpenAICompatibleClient` at `llm.py:433`. So
the ceiling works.

With a router, `_resolve_turn_client` (`loop.py:601`) installs a `ResilientClient` — built by
`core/routing/router.py:203` and `:266` — and the attribute vanishes.

**That asymmetry is the finding.** Say it that way in the commit message: *enabling
`[routing]` silently weakens a safety guardrail.*

## 4. Reproduce the failure

Fully reproducible, no network, no boot:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import sys; sys.path.insert(0, "src")
from hachi.core.llm import BaseLLMClient, LLMResponse
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy


class _Fake(BaseLLMClient):
    def __init__(self):
        self.model, self.max_tokens = "m", 8192
    def generate(self, *a, **kw): return LLMResponse()
    def generate_stream(self, *a, **kw): yield ""
    def list_models(self): return []


raw = _Fake()
policy = RetryPolicy()
rc = ResilientClient(inner=raw, policy=policy, recorder=HealthRecorder("p", policy))

print("raw client max_tokens (router OFF) :", getattr(raw, "max_tokens", 0) or 0)
print("ResilientClient      (router ON)   :", getattr(rc,  "max_tokens", 0) or 0)
PY
```

**You will see now:**

```
raw client max_tokens (router OFF) : 8192
ResilientClient      (router ON)   : 0
```

That `0` is what `loop.py:755` reads. `projected = snap.total_tokens + 0`, so the check at
`:757` compares the ceiling against the *already-recorded* snapshot — the exact post-hoc
behaviour the S1 docstring at `:740-746` says it replaced.

**You should see after the fix:** `8192` on both lines.

## 5. What "fixed" looks like

One line, beside the existing `model` forward at `resilience.py:347`:

```python
        # Expose `model` attribute from inner for cost tracking / introspection.
        self.model: str = getattr(inner, "model", "unknown")
        # Expose `max_tokens` too: the loop's pre-flight token-safety ceiling reads it
        # off the turn client (loop.py:755). Without it the ceiling silently degrades
        # to a post-hoc check whenever [routing] is enabled.
        self.max_tokens: int = getattr(inner, "max_tokens", 0) or 0
```

Keep the `getattr` default so a client without the attribute still constructs — that is the
same defensive posture as the `model` line and matches the loop's own `or 0`.

### Do NOT add a blanket `__getattr__`

Delegating every unknown attribute to `self._inner` is the "clean" answer and it is the wrong
one here:

- It is far broader than the finding — it changes attribute resolution for **every** caller
  of every `ResilientClient`, forever.
- It **masks** the next missing attribute instead of surfacing it. The whole reason this bug
  survived is that a defaulted `getattr` turned a missing attribute into a plausible zero.
  A `__getattr__` institutionalises that failure mode.
- It interacts badly with `hasattr`-based feature detection elsewhere in the codebase
  (e.g. `supports_vision`, which `ResilientClient` implements *deliberately* as an explicit
  property at `resilience.py:474-476`).

Forward the two attributes explicitly. If a third is needed later, forward that explicitly
too.

## 6. Steps

1. **Write the regression test from §7 first.** Run it. Watch it fail.
2. Add the `self.max_tokens` line at `resilience.py:347`.
3. Re-run the test.
4. Run `uv run python scripts/preflight.py --quick`, then the full gate.
5. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_loop_backstop_cancel.py` (existing — it already owns the ceiling
  tests; see the trap below)
- **Test name:** `test_token_safety_ceiling_is_preflight_through_a_resilient_client`
- **It must assert:** the **observed number of LLM calls** made by a real `ExecutionLoop`
  turn whose `_turn_client` is a `ResilientClient`. With the ceiling patched low and a fake
  reporting large per-call usage, the pre-flight check must refuse the call that *would*
  cross the ceiling — so the call count is strictly lower than under post-hoc-only
  behaviour. Assert on call count, not on `getattr(rc, "max_tokens")`.
- **It must FAIL before your fix** with something like:
  `AssertionError: expected 1 call (pre-flight refused the 2nd), got 2`

### ⚠️ The existing test is green today and proves nothing about the routed path

`tests/test_loop_backstop_cancel.py:268-...`,
`test_token_safety_ceiling_is_preflight_not_post_hoc`, uses a fake client that **does**
expose `max_tokens` — `:282`:

```python
    llm.max_tokens = 50  # worst-case output tokens for the NEXT call
```

So it exercises the ceiling correctly and passes, while the routed path is inert. **Your new
test must go through a real `ResilientClient`** — copy the existing test's structure, then
wrap the fake:

```python
    rc = ResilientClient(inner=llm, policy=RetryPolicy(max_attempts=1, backoff_base_s=0.0),
                         recorder=HealthRecorder("p", policy))
```

…and hand `rc` to `ExecutionLoop` instead of `llm`.

```python
# sketch — adapt to the repo's existing fixtures (see the sibling test at :268)
from __future__ import annotations

from hachi.core.cost import CostTracker
from hachi.core.loop import ExecutionLoop
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy


def test_token_safety_ceiling_is_preflight_through_a_resilient_client(monkeypatch) -> None:
    """Enabling [routing] must not weaken the pre-flight token ceiling.

    ResilientClient forwarded only `model` (resilience.py:347), so the loop's
    getattr(_turn_client, "max_tokens", 0) at loop.py:755 read 0 and the pre-flight
    check silently degraded to the post-hoc check it was written to replace.
    """
    monkeypatch.setattr(ExecutionLoop, "_TOKEN_SAFETY_CEILING", 100)
    tracker = CostTracker()

    llm = _RunawayTokenLLM(tokens_per_call=90)   # reuse the module's existing fake
    llm.max_tokens = 50                          # worst-case output tokens for the NEXT call

    policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
    routed = ResilientClient(inner=llm, policy=policy, recorder=HealthRecorder("p", policy))
    assert getattr(routed, "max_tokens", 0) == 50, "ResilientClient did not forward max_tokens"

    loop = ExecutionLoop(
        routed,
        _noop_registry(),
        SubAgentMemory(),
        base_system_prompt="x",
        cost_tracker=tracker,
        max_tokens=0,
        max_wall_seconds=0.0,
    )
    loop.add_user_message("go")
    result = loop.run(max_iterations=50)

    assert "[BUDGET LIMIT REACHED]" in result
    assert "ceiling" in result.lower()
    # 90 recorded + 50 worst-case = 140 >= 100 ⇒ the SECOND call must be refused.
    assert llm.calls == 1, f"pre-flight should refuse the 2nd call; got {llm.calls}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The most likely cause of a false pass: handing the bare fake to `ExecutionLoop` instead of
> the `ResilientClient` wrapper. The `assert getattr(routed, "max_tokens", 0) == 50` line
> above is there to fail loudly if you do.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, drives a real `ResilientClient`, and failed before
      the fix.
- [ ] The §4 reproduction script prints `8192` on both lines.
- [ ] `ResilientClient` gained **`max_tokens` only** — `grep -n "__getattr__"
      src/hachi/core/resilience.py` still returns nothing.
- [ ] The existing `test_token_safety_ceiling_is_preflight_not_post_hoc` still passes,
      unmodified.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add `__getattr__` to `ResilientClient`.** Re-read §5. This is the specific thing a
  well-meaning agent will do here, and it is the wrong shape of fix.
- **Do not change `_TOKEN_SAFETY_CEILING`** (`loop.py:384`, 2,000,000). The value is fine;
  the plumbing was broken.
- **Do not "harden" the other `getattr` calls on `_turn_client`** you will notice while
  reading `loop.py` — in particular `getattr(self._turn_client, "model", "unknown")` at
  `:1089`, which is a real and *different* bug covered by
  [T-25-served-model-cost-attribution.md](T-25-served-model-cost-attribution.md). Keep the
  diffs separable.
- **Do not touch the retry/fallback logic** while you are inside `resilience.py` — that is
  [T-24-collapse-retry-layers.md](T-24-collapse-retry-layers.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Targeted (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_loop_backstop_cancel.py tests/test_resilience.py \
              tests/test_multi_provider.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — Enabling `[routing]` silently degraded the pre-flight token-safety ceiling to a post-hoc check

- **Symptom:** with routing enabled, a single runaway generation could cross the 2,000,000-token
  safety ceiling by its own full cost before anything noticed. With routing disabled the same
  ceiling refused the call up front. No error, no log — the guardrail just got weaker when a
  cost feature was switched on.
- **Root cause:** `ResilientClient.__init__` forwarded only `model` from the wrapped client
  (`core/resilience.py:347`); there is no `max_tokens` attribute and no `__getattr__`. The
  loop's pre-flight check reads
  `getattr(worst_case_next_call, "max_tokens", 0) or 0` (`core/loop.py:755`), so it got 0,
  making `projected == snap.total_tokens` — literally the post-hoc check the S1 docstring at
  `loop.py:740-746` says it replaced. With `router is None`, `loop.py:861` leaves
  `_turn_client` as the raw `AnthropicClient` (which has `max_tokens`, `llm.py:275`), so the
  bug was invisible in the default configuration. `tests/test_loop_backstop_cancel.py:268`
  covered the ceiling with a fake that DID expose `max_tokens` — green while the routed path
  was inert.
- **Fix:** forward `max_tokens` explicitly beside `model` in `ResilientClient.__init__`.
  Deliberately NOT a blanket `__getattr__` — that would mask the next missing attribute the
  same way a defaulted `getattr` masked this one.
- **Avoid:** a decorator/wrapper class must forward every attribute its callers read, and a
  `getattr(obj, name, <default>)` against your OWN type is a code smell: it converts a
  missing attribute into a plausible value instead of an error. When wrapping, test through
  the wrapper, never against the bare inner object.
- **Locked by:** `tests/test_loop_backstop_cancel.py` —
  `test_token_safety_ceiling_is_preflight_through_a_resilient_client`
```

## 12. Known traps

- **The existing ceiling test is a false friend.**
  `tests/test_loop_backstop_cancel.py:268`, `test_token_safety_ceiling_is_preflight_not_post_hoc`,
  passes today and will pass after the fix. It sets `llm.max_tokens = 50` at `:282` on a bare
  fake. It is **not** evidence that the routed path works. Leave it alone and add a new test
  that goes through `ResilientClient`.

- **This is another `getattr`-masking instance.** The generic rule — never
  `getattr(x, "attr", default)` against a type you own — is
  [T-14-ban-getattr-own-types.md](T-14-ban-getattr-own-types.md). Fix this instance here;
  do not start a repo-wide sweep.

- **`supports_vision` shows the intended pattern.** `resilience.py:474-476` implements it as
  an explicit `@property` delegating to the inner client. That is the house style for
  forwarding through `ResilientClient` — explicit, one attribute at a time. Follow it.

- **`ResilientClient` is built in two places** in `core/routing/router.py` (`:203` and `:266`).
  You do not need to change either — the fix is in the constructor — but if you are tracing
  the routed path, those are the sites.

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
