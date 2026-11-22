# T-25 · Attribute spend to the model that actually served the turn

|  |  |
|---|---|
| **Source finding** | CF-7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **the review implies a 36-site change; it is ZERO — see [CORRECTIONS.md](CORRECTIONS.md) §5** |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium — the *timing* of the stamp is the whole problem, see §5 and §12 |
| **Files you will touch** | `src/hachi/core/llm.py`, `src/hachi/core/resilience.py`, `src/hachi/core/loop.py`, `tests/test_multi_provider.py` or a new test file |

---

## 1. Brief

`ResilientClient` records its `model` attribute **once, at construction, from the primary
client** and never updates it when the fallback chain walks to a different provider. The
execution loop then reads that stale attribute to attribute cost. So when a fallback serves
a turn, the spend is booked against the **primary** model — at the primary's price. When you
are done, `LLMResponse` carries a `served_model`, populated by whichever client actually
produced the response, and the cost tracker prefers it.

## 2. Why this matters

Every strategy document in this repo names *verifiable, owned cost governance* as part of the
moat. This defect corrupts the books **precisely during failover** — the one moment the
system is doing something the user did not choose and most needs an accurate record of. A
Haiku fallback covering for a failing Opus primary is billed as Opus; a spend cap trips
early or late; the per-model breakdown in `/spend` reports usage of a model that served zero
tokens. It is not a rounding error, it is an attribution to the wrong entity.

The fix is small. Resist making it large — see §3.2, which is the reason the review made it
look expensive.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The stale attribute

`src/hachi/core/resilience.py:335-347` — `ResilientClient.__init__`:

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

Set once, from `inner` (the primary). Nothing reassigns it —
`grep -n "self.model" src/hachi/core/resilience.py` returns only this line.

`resilience.py:349-390` — `_call_with_chain` walks past the primary without touching it:

```python
        chain = [(self._inner, self._recorder)] + self._fallbacks       # :365
        ...
        for idx, (client, recorder) in enumerate(chain):                # :370
            if idx > 0:
                logger.warning(
                    "ResilientClient: failing over to fallback[%d] (model=%s)",
                    idx,
                    getattr(client, "model", "unknown"),                # :375
                )

            fn = fn_builder(client)
            try:
                return resilient_call(fn, self._policy, recorder)       # :380
```

Note `:375` — the code *knows* the fallback's model well enough to log it, and still does
not record it.

`src/hachi/core/loop.py:1088-1090` — the read side:

```python
                if self.cost_tracker is not None:
                    model_name = getattr(self._turn_client, "model", "unknown")   # :1089
                    self.cost_tracker.record(model_name, response.usage, feature="chat")
```

`self._turn_client` is the `ResilientClient` (assigned at `loop.py:861` and possibly replaced
by `_resolve_turn_client` at `:863`). So `model_name` is always the primary's id, regardless
of who served the turn. The same `model_name` also feeds `cache_metrics` at `loop.py:1098`.

### 3.2 The change is backward-compatible — it touches ZERO construction sites

The review's framing ("36 construction sites") makes adding a field look expensive. It is
not, because `LLMResponse` is a **pydantic model**, not a dataclass, so a field with a
default is optional at every construction site.

`src/hachi/core/llm.py:118-137`:

```python
class LLMResponse(BaseModel):
    """
    Standardized response returned by any underlying LLM provider.
    """

    content: str = Field(default="", description="The textual response from the model.")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Any tool calls requested by the model."
    )
    usage: TokenUsage = Field(
        default_factory=TokenUsage, description="Token usage for this generation."
    )
    stop_reason: str | None = Field(
        default=None,
        description=(...),
    )
```

Adding `served_model: str | None = None` requires **no edit** at any of the 36 existing
construction sites (verified: `grep -rn "LLMResponse(" src/` → 37 hits, one of which is the
`class` line at `:118`).

Distribution of those 36:

| File | Sites |
|---|---|
| `src/hachi/core/eval/corpus.py` | 26 — **golden fixtures, do not touch (§9)** |
| `src/hachi/core/unofficial_providers.py` | 5 — opt-in provider, out of scope |
| `src/hachi/core/llm.py` | 4 (`:369`, `:656`, `:664`, `:787`) |
| `src/hachi/core/loop.py` | 1 (`:717`, an unreachable type-checker appeaser) |

Only **three** of those should populate the new field.

### 3.3 The three sites that should populate it

**(a) `src/hachi/core/llm.py:348-374` — `AnthropicClient._parse_message`**, a `@staticmethod`
that serves BOTH the non-streaming and streaming Anthropic paths (`generate` returns it at
`:386`; `generate_stream` returns it at `:406` from `stream.get_final_message()`):

```python
    @staticmethod
    def _parse_message(msg: Any) -> LLMResponse:
        """Parse an Anthropic Message object into a standardised LLMResponse."""
        ...
        return LLMResponse(                                             # :369
            content=text_content.strip(),
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )
```

It is a `@staticmethod`, so it has no `self.model` — but it does not need one. **The
Anthropic response object carries the served model itself.** Verified against the installed
`anthropic` 0.105.2:

```
>>> from anthropic.types import Message; sorted(Message.model_fields)
['container', 'content', 'id', 'model', 'role', 'stop_details', 'stop_reason',
 'stop_sequence', 'type', 'usage']
```

So `served_model=getattr(msg, "model", None)` inside `_parse_message` reports what the
**provider says it ran** — strictly better than what the client was configured to ask for.
One edit covers both Anthropic paths.

**(b) `src/hachi/core/llm.py:639-669` — `OpenAICompatibleClient.generate`.** The parsed body
is in scope at `:652`:

```python
        data = response.json()                                          # :652
        ...
        return LLMResponse(                                             # :664
            content=str(content).strip(),
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=stop_reason,
        )
```

`data.get("model")` is the OpenAI chat-completions response field. Fall back to `self.model`
when the endpoint omits it (local servers often do).

**(c) `src/hachi/core/llm.py:671-792` — `OpenAICompatibleClient.generate_stream`**, returning
at `:787`. Here the safe default is `self.model`. If you want the provider-reported value,
**verify first** that the SSE chunks this method parses actually carry `model` before
relying on it — do not assume ([CLAUDE.md](../../../../CLAUDE.md) Rule 4).

### 3.4 The chain re-stamp

Even with (a)–(c), a response can reach the loop with `served_model=None` (the
`chatgpt-web` client, a test double, a provider that omits the field). The resilience layer
should backfill it from the client that produced the response. §5 says where.

## 4. Reproduce the failure

**Not reproducible from a shell against a live provider** (it requires a primary that fails
and a fallback that succeeds). It is reproducible in-process, and this script is the skeleton
of your regression test:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import sys; sys.path.insert(0, "src")
from hachi.core.llm import BaseLLMClient, LLMResponse, TokenUsage
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy


class _Boom(Exception):
    status_code = 503          # transient under resilience._TRANSIENT_STATUS_CODES


class _Fake(BaseLLMClient):
    def __init__(self, model, fail):
        self.model, self._fail, self.max_tokens = model, fail, 4096
    def generate(self, *a, **kw):
        if self._fail:
            raise _Boom("down")
        return LLMResponse(content="ok", usage=TokenUsage(input_tokens=10, output_tokens=5))
    def generate_stream(self, *a, **kw):
        raise NotImplementedError
    def list_models(self):
        return []


policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
primary = _Fake("expensive-primary", fail=True)
fallback = _Fake("cheap-fallback", fail=False)

rc = ResilientClient(
    inner=primary, policy=policy, recorder=HealthRecorder("a", policy),
    fallbacks=[(fallback, HealthRecorder("b", policy))],
)
resp = rc.generate([])

print("served by            :", "cheap-fallback")
print("rc.model (cost reads):", rc.model)
print("resp.served_model    :", getattr(resp, "served_model", "<field does not exist>"))
PY
```

**You will see now:**

```
served by            : cheap-fallback
rc.model (cost reads): expensive-primary
resp.served_model    : <field does not exist>
```

The turn was served by `cheap-fallback` and `loop.py:1089` will book it as
`expensive-primary`.

**You should see after the fix:** `rc.model` may still read `expensive-primary` (that is the
*configured* primary and is fine), but `resp.served_model` must be `cheap-fallback`, and the
loop must record against that.

## 5. What "fixed" looks like

**Step 1 — add the field.** `src/hachi/core/llm.py`, in `LLMResponse` (after `stop_reason`):

```python
    served_model: str | None = Field(
        default=None,
        description=(
            "The model that ACTUALLY produced this response, as reported by the "
            "provider where available. Differs from the client's configured model "
            "when a resilience fallback served the turn; cost must be attributed "
            "to this value, not to the primary."
        ),
    )
```

Defaulted ⇒ zero construction sites change.

**Step 2 — populate at the three production sites** (§3.3), preferring the provider's own
reported value:

- `llm.py:369` → `served_model=getattr(msg, "model", None)`
- `llm.py:664` → `served_model=data.get("model") or self.model`
- `llm.py:787` → `served_model=self.model` (or the stream-reported value, if you verify one exists)

**Step 3 — backfill in the chain.** In `_call_with_chain` (`resilience.py:349`), inside the
loop at `:370-380`, wrap the return so the response is stamped with the client that produced
it when it is not already stamped:

```python
            fn = fn_builder(client)
            try:
                result = resilient_call(fn, self._policy, recorder)
                if isinstance(result, LLMResponse) and result.served_model is None:
                    result.served_model = getattr(client, "model", None)
                return result
```

`isinstance` is required: `_call_with_chain` is generic (`fn_builder` returns
`Callable[[], Any]`) and is used for non-`LLMResponse` operations. `LLMResponse` is already
imported at `resilience.py:27`.

Also stamp the **streaming success path** at `resilience.py:434-442`, which does not go
through `_call_with_chain` at all:

```python
            response = yield from self._inner.generate_stream(...)      # :434
```

…stamp `response.served_model` from `self._inner` if it is `None` before returning at `:442`.

**Step 4 — prefer it at the read site.** `loop.py:1089`:

```python
                    model_name = response.served_model or getattr(
                        self._turn_client, "model", "unknown"
                    )
```

Keeping the `getattr` fallback means no behaviour change for any client that does not
populate the field.

## 6. Steps

1. **Write the regression test from §7 first.** Run it. Watch it fail with
   `AttributeError: 'LLMResponse' object has no attribute 'served_model'` (or an assertion
   on the recorded model name).
2. Add `served_model` to `LLMResponse` (`llm.py`, after `:130-137`).
3. Populate at `llm.py:369`, `:664`, `:787`.
4. Backfill in `resilience.py` `_call_with_chain` (`:370-380`) and on the streaming success
   path (`:434-442`).
5. Prefer it at `loop.py:1089`.
6. Run `tests/test_multi_provider.py` — especially `TestCostAttribution` (`:430`) and
   `TestFailoverUnderLoad` (`:213`) — see §12.
7. Full `uv run python scripts/preflight.py`, report real counts.
8. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_multi_provider.py` (existing — `TestCostAttribution` at `:430`,
  `_FakeClient` at `:57`, `_TransientError` at `:41`) or a new
  `tests/test_served_model_attribution.py`.
- **Test name:** `test_cost_is_attributed_to_the_fallback_that_served_the_turn`
- **It must assert:** the **`CostTracker`'s per-model bucket** — i.e. after a turn where the
  primary fails and a fallback succeeds, `tracker.per_model_snapshot()` has a bucket for the
  fallback model and **no** bucket for the primary. Assert on the tracker's real observed
  state, not on the value of `response.served_model` alone. `served_model` is the mechanism;
  correct books are the behaviour.
- **It must FAIL before your fix** with something like:
  `AssertionError: assert 'cheap-fallback' in {'expensive-primary': ...}`

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

from hachi.core.cost import CostTracker            # confirm the real import path
from hachi.core.llm import LLMResponse, TokenUsage
from hachi.core.resilience import HealthRecorder, ResilientClient, RetryPolicy


def test_cost_is_attributed_to_the_fallback_that_served_the_turn() -> None:
    """When the primary fails and a fallback serves the turn, spend must be booked
    against the FALLBACK.

    ResilientClient.model is captured once from the primary at construction
    (resilience.py:347) and never updated as _call_with_chain walks the chain, so
    loop.py:1089 booked failover spend at the primary's identity and price.
    """
    policy = RetryPolicy(max_attempts=1, backoff_base_s=0.0)
    primary = _FakeClient([_TransientError("503")], model="expensive-primary")
    fallback = _FakeClient([_ok("cheap-fallback")], model="cheap-fallback")

    rc = ResilientClient(
        inner=primary,
        policy=policy,
        recorder=HealthRecorder("a", policy),
        fallbacks=[(fallback, HealthRecorder("b", policy))],
    )

    response = rc.generate([])
    assert response.served_model == "cheap-fallback"

    # The behaviour that matters: the books.
    tracker = CostTracker()
    model_name = response.served_model or getattr(rc, "model", "unknown")
    tracker.record(model_name, TokenUsage(input_tokens=100, output_tokens=50))

    per_model = tracker.per_model_snapshot()
    assert "cheap-fallback" in per_model
    assert "expensive-primary" not in per_model, "spend booked against a model that served nothing"
```

Add a **second** test driving a real `ExecutionLoop` turn end-to-end through a
`ResilientClient`, asserting `tracker.per_model_snapshot()` after `loop.run(...)` — that is
the one that pins `loop.py:1089` itself rather than re-implementing it in the test.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, asserts on `CostTracker.per_model_snapshot()`, and
      failed before the fix.
- [ ] `LLMResponse.served_model` exists with `default=None`; `git diff --stat` shows **no**
      changes under `src/hachi/core/eval/`.
- [ ] The §4 reproduction script prints `resp.served_model: cheap-fallback`.
- [ ] `loop.py:1089` prefers `response.served_model` and still falls back to the client
      attribute.
- [ ] A response that goes through `ResilientClient.generate_stream` (`resilience.py:418`) is
      also stamped — the streaming path does not go through `_call_with_chain`.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts), and the
      **`eval regression` step in particular is green** (see §9).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `src/hachi/core/eval/corpus.py`.** It holds 26 of the 36 `LLMResponse(...)`
  construction sites, and they are **golden eval fixtures**. Because the new field is
  defaulted, none of them needs editing — and editing them churns the eval baseline that
  `scripts/preflight.py` gates on (`Step("eval regression", …)`). This is the single most
  likely way to turn a one-day task into a week. If you find yourself opening `corpus.py`,
  close it.
- **Do not "fix" `ResilientClient.model` at `resilience.py:347` by mutating it** as the chain
  walks. It is tempting and it is wrong: `self.model` is shared per-client state, the chain
  can be re-entered concurrently, and mutating it makes the attribute race across turns.
  [CLAUDE.md](../../../../CLAUDE.md)'s security guardrails already say *no mutation of shared
  loop state per turn*. Put the value on the **response**, which is per-call.
- **Do not add `served_model` to the 5 sites in `core/unofficial_providers.py`.** That
  provider is opt-in behind `HACHI_UNOFFICIAL=1`; the chain backfill (§5, step 3) covers it.
- **Do not change pricing, `CostTracker`, or the `provider_map`.** Attribution is the bug;
  the price table is fine.
- **Do not restructure the retry/fallback logic** — that is
  [T-24-collapse-retry-layers.md](T-24-collapse-retry-layers.md), and you will be editing the
  same 40 lines. Keep the diffs separable.
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
uv run pytest tests/test_multi_provider.py tests/test_resilience.py -q
uv run hachi eval run       # the golden-corpus gate — must stay green
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — Failover spend was booked against the primary model, not the fallback that served the turn

- **Symptom:** when a provider failed and a configured fallback served the turn, `/spend`
  and the per-model breakdown showed usage for the **primary** model — at the primary's
  price — and zero for the model that actually ran. Cost caps tripped early or late during
  exactly the failover windows where the numbers matter most.
- **Root cause:** `ResilientClient.__init__` captures `self.model` once from the primary
  (`core/resilience.py:347`) and `_call_with_chain` (`:349-390`) never updates it while
  walking the chain — even though it reads the fallback's model to *log* the failover at
  `:375`. `core/loop.py:1089` then attributes cost via
  `getattr(self._turn_client, "model", "unknown")`.
- **Fix:** added `served_model: str | None = None` to `LLMResponse` (`core/llm.py:118`,
  a pydantic BaseModel — a defaulted field touches zero of the 36 construction sites),
  populated from the provider's own reported model at `llm.py:369` / `:664` / `:787`,
  backfilled from the serving client inside `_call_with_chain` and on the streaming success
  path, and preferred at `loop.py:1089`.
- **Avoid:** identity of *who served a call* belongs on the RESPONSE (per-call), never on a
  long-lived client attribute (shared, and stale the moment a chain fails over). Any
  `getattr(client, "model", ...)` on a decorated client is suspect.
- **Locked by:** `tests/test_multi_provider.py` —
  `test_cost_is_attributed_to_the_fallback_that_served_the_turn`
```

## 12. Known traps

- **Timing trap — stamp where the response is PRODUCED, not where it is read.** By the time
  execution reaches `loop.py:1089`, the identity is already gone: `_call_with_chain` returns
  `resilient_call(...)`'s value opaquely as `Any` (`resilience.py:380`, signature `-> Any` at
  `:354`), and the chain index is known **only inside the loop at `:370`**. There is no way
  to recover "which client served this" at the read site. If your diff only touches
  `loop.py`, it cannot work.

- **`_parse_message` is a `@staticmethod`** (`llm.py:348`). You cannot reach `self.model`
  from it. You do not need to — the Anthropic `Message` object carries `.model` (verified,
  §3.3(a)). Do **not** convert it to an instance method just to get `self`; that changes a
  signature two call sites (`:386`, `:406`) and any test doubles depend on.

- **Streaming bypasses `_call_with_chain` on the happy path.** `resilience.py:434` calls
  `self._inner.generate_stream` directly. A stamp added only inside `_call_with_chain` will
  leave every successful streaming turn — i.e. almost every real turn — unstamped, and the
  `or` fallback at `loop.py:1089` will hide it. Stamp both paths, and make sure your test
  covers a streaming turn.

- **`_call_with_chain` is generic.** Its `fn_builder` is
  `Callable[[BaseLLMClient], Callable[[], Any]]` (`resilience.py:351`). Guard the stamp with
  `isinstance(result, LLMResponse)` or you will set an attribute on unrelated return values.

- **`tests/test_multi_provider.py:259`** replaces `_call_with_chain` wholesale:
  ```python
          client._call_with_chain = _patched  # type: ignore[method-assign]
  ```
  Your stamp lives in the real method, so that test exercises a copy without it. If you rely
  on that test for coverage you will get a false green. Write a new test rather than
  extending that one.
- **`tests/test_multi_provider.py:430`, `TestCostAttribution`** tests `CostTracker` with
  explicit model strings and never goes through `ResilientClient` — so it passes today
  despite the bug and will pass after the fix. It is not evidence either way.
- **`tests/test_resilience.py:368`, `test_model_attribute_exposed`** pins
  `ResilientClient.model` == the primary's model. That is still correct after this fix
  (the *configured* primary is what that attribute means) — **do not change it**. If it goes
  red you have mutated `self.model`, which §9 forbids.

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
