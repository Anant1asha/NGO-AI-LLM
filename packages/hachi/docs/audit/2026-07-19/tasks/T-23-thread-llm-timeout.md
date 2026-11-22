# T-23 · Thread the configured per-call timeout into LLM client construction

|  |  |
|---|---|
| **Source finding** | CF-7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **the review OVERSTATES the work — read [CORRECTIONS.md](CORRECTIONS.md) §4** |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-28-wall-clock-deadline-hung-socket.md](T-28-wall-clock-deadline-hung-socket.md) — *sequence T-28 after this* |
| **Effort** | ~half a day |
| **Difficulty** | Low (mechanical) — the *default value* is the only judgement call, and §5 makes it |
| **Files you will touch** | `src/hachi/core/llm.py`, `src/hachi/core/resilience.py` (read-only unless you disagree with §5), `tests/test_llm_env_resolution.py` or a new test file |

---

## 1. Brief

`RetryPolicy.timeout_s` is defined, documented in two places, mirrored in the settings
schema, and **read by nothing**. Meanwhile `create_llm_client()` constructs every client
without a timeout. For the Anthropic client that is worse than the review says: because of
how the SDK resolves an explicit `None`, Anthropic calls today have **no timeout at all** —
not the 600 s SDK default. When you are done, `create_llm_client` accepts a timeout, applies
it to the client it builds, and `[routing.resilience].timeout_s` actually reaches the wire.

## 2. Why this matters

Hachi is an *autonomous* agent: it runs unattended, in background jobs, on schedules, and
behind channels. Hang behaviour is not a nicety — an LLM call that never returns parks a
thread forever, and (because the loop is synchronous, see §3.6) parks a gateway threadpool
worker with it. The user sees a spinner that never resolves and no error, ever.

The module docstring already promises this is handled: *"per-call timeout (default 60s, down
from 600s)"*. That promise is documentation of an intent that was never wired. The gap
between the docstring and the wire is the finding.

Do not over-build this. The fix is one keyword argument threaded through one factory
function. If your diff is touching provider classes, `ResilientClient`, or the settings
schema, you have drifted — re-read §4 of CORRECTIONS.md.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 `timeout_s` is dead

`src/hachi/core/resilience.py:1-13` — the module docstring, promising the behaviour:

```python
"""Resilience layer: retry, circuit-breaker, and health tracking.

Closes debt D6 (600s Anthropic default; no retry/breaker). Design doc 13 §5.

``ResilientClient`` decorates any ``BaseLLMClient`` with:
  - per-call timeout (default 60s, down from 600s)
```

`resilience.py:71-88` — `RetryPolicy`, where the field is declared and documented:

```python
class RetryPolicy(BaseModel):
    """Configures retry and circuit-breaker behaviour.

    Args:
        ...
        timeout_s: Per-call timeout in seconds.  Default 60s (down from the 600s SDK default.)
        ...
    """

    model_config = ConfigDict(extra="ignore")

    max_attempts: int = 3
    backoff_base_s: float = 0.5
    timeout_s: float = 60.0            # :86
    breaker_threshold: int = 5
    breaker_cooldown_s: float = 30.0
```

`resilience.py:90-106` — `RetryPolicy.from_config` faithfully loads it from
`[routing.resilience]` into the object, where it stops:

```python
    @classmethod
    def from_config(cls, config: Any) -> RetryPolicy:
        """Extract ``[routing.resilience]`` from a :class:`~hachi.core.settings.ResolvedConfig`."""
```

`src/hachi/core/settings.py:158-172` — `ResilienceSettings`, the config mirror, also dead:

```python
class ResilienceSettings(BaseModel):
    """Retry and circuit-breaker parameters for the routing resilience layer.

    Maps to ``[routing.resilience]`` in ``settings.toml``.
    """
    ...
    timeout_s: float = 60.0            # :170
```

**Proof it is never read** — word-boundary grep across the whole package:

```
$ grep -rnw "timeout_s" src/ --include=*.py
src/hachi/core/mcp_client.py:1091:            timeout_s=float(request_timeout_seconds),
src/hachi/core/resilience.py:77:        timeout_s: Per-call timeout in seconds. ...
src/hachi/core/resilience.py:86:    timeout_s: float = 60.0
src/hachi/core/settings.py:170:    timeout_s: float = 60.0
```

Two definitions and one docstring. The `mcp_client.py:1091` hit is an unrelated keyword on
the MCP transport, not the LLM path. **Zero reads.**

### 3.2 Both official client classes already accept AND apply a timeout

This is the correction that shrinks the task. Nothing needs to be added to either class.

`src/hachi/core/llm.py:252-275` — `AnthropicClient.__init__`:

```python
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5",
        max_tokens: int = 4096,
        timeout: float | None = None,                       # :257
    ):
        """
        ...
            timeout: Per-request timeout in seconds. None uses the SDK default (600s).
        """
        ...
        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)   # :273
```

> ⚠️ **That docstring at `:267` is factually wrong.** See §3.4. Fix it while you are here.

`src/hachi/core/llm.py:421-443` — `OpenAICompatibleClient.__init__`:

```python
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        max_tokens: int = 4096,
        timeout: float = 60.0,                              # :427
        stream_usage: bool = True,
    ):
        ...
        self._http = httpx.Client(timeout=timeout)          # :443
```

**Every non-Anthropic provider already gets 60 s today.** The review's blanket "no LLM
timeout" is false for them. Ollama, Gemini, Groq, DeepSeek, OpenRouter and Together are all
*branches of `create_llm_client`* returning `OpenAICompatibleClient` with a different
`base_url` — they are **not** separate client classes.

There is a **third** client class, but it is opt-in and off by default:
`src/hachi/core/unofficial_providers.py:98`, `ChatGPTWebClient`, whose `__init__` at
`:115-120` takes `session_token` / `model` / `max_tokens` and **no timeout**. It is only
reachable behind `HACHI_UNOFFICIAL=1` (`llm.py:916`). See §9.

### 3.3 The actual gap: `create_llm_client` omits `timeout` at every return

`src/hachi/core/llm.py:859-861` — the signature:

```python
def create_llm_client(
    provider_config: dict[str, Any], secret_store: SecretStore | None = None, max_tokens: int = 4096
) -> BaseLLMClient:
```

**Six** return statements, none passing a timeout (the review said five — it missed the
`chatgpt-web` branch):

| Line | Branch | Class built |
|---|---|---|
| `llm.py:882` | `kind == "anthropic"` | `AnthropicClient` |
| `llm.py:888` | `kind == "ollama"` | `OpenAICompatibleClient` |
| `llm.py:905` | `kind == "gemini"` | `OpenAICompatibleClient` |
| `llm.py:934` | `kind == "chatgpt-web"` | `ChatGPTWebClient` (opt-in — leave alone, §9) |
| `llm.py:944` | `kind in _OPENAI_COMPAT_PRESETS` | `OpenAICompatibleClient` |
| `llm.py:960` | `kind in ("openai-compatible", "openai")` | `OpenAICompatibleClient` |

`llm.py:878-882`:

```python
    if kind == "anthropic":
        # Always prefer ANTHROPIC_API_KEY for this kind so a misconfigured
        # api_key_ref (e.g. the legacy default "OPENAI_API_KEY") doesn't shadow it.
        kind_key = _resolve_api_key("ANTHROPIC_API_KEY") or api_key
        return AnthropicClient(api_key=kind_key, model=model, max_tokens=max_tokens)
```

No `timeout=`. So `AnthropicClient.__init__` uses its own default of `None`.

### 3.4 ⚠️ Anthropic today has NO timeout — not 600 s. Verified empirically.

**This corrects both the review and CORRECTIONS.md §4**, which both say Anthropic "inherits
the SDK's 600 s default". It does not, because `llm.py:273` passes `timeout=timeout`
*explicitly*, and an explicit `None` is a real value to this SDK — not an absent one.

`anthropic` **0.105.2** (verified: `python -c "import anthropic; print(anthropic.__version__)"`).

`anthropic/_constants.py:8-10`:

```python
# default timeout is 10 minutes
DEFAULT_TIMEOUT = httpx.Timeout(timeout=10 * 60, connect=5.0)
DEFAULT_MAX_RETRIES = 2
```

`anthropic/_client.py:145-156` — `Anthropic.__init__` takes keyword-only `timeout`, default
`not_given`:

```python
    def __init__(
        self,
        *,
        api_key: str | None = None,
        ...
        timeout: float | Timeout | None | NotGiven = not_given,        # :155
        max_retries: int = DEFAULT_MAX_RETRIES,                        # :156
```

`anthropic/_base_client.py:932-943` — the resolution. The default is applied **only when the
argument was not given**:

```python
        if not is_given(timeout):
            # if the user passed in a custom http client with a non-default
            # timeout set then we use that timeout.
            ...
            if http_client and http_client.timeout != HTTPX_DEFAULT_TIMEOUT:
                timeout = http_client.timeout
            else:
                timeout = DEFAULT_TIMEOUT
```

…and whatever `timeout` then is goes straight to httpx at `_base_client.py:959-963`:

```python
        self._client = http_client or SyncHttpxClientWrapper(
            base_url=base_url,
            timeout=cast(Timeout, timeout),
        )
```

`is_given(None)` is **True**, so `None` skips the default branch entirely. Confirmed by
running against the installed package:

```
$ python -c "..."
is_given(None) = True
is_given(not_given) = False
client.timeout with timeout=None ->  None
httpx client timeout             ->  Timeout(timeout=None)
client.timeout default           ->  Timeout(connect=5.0, read=600, write=600, pool=600)
client.timeout with 60.0         ->  60.0
```

`httpx.Timeout(timeout=None)` means **wait forever**.

And the SDK's *other* safety net is disabled by the same value. `anthropic/resources/messages/messages.py:987`:

```python
        if not stream and not is_given(timeout) and self._client.timeout == DEFAULT_TIMEOUT:
            timeout = self._client._calculate_nonstreaming_timeout(
                max_tokens, MODEL_NONSTREAMING_TOKENS.get(model, None)
            )
```

The guard requires `self._client.timeout == DEFAULT_TIMEOUT`. Hachi's client has
`timeout=None`, so this branch never fires and the 600 s non-streaming ceiling
(`_base_client.py:731-744`) is **also** off.

**Net: on `main` today, an Anthropic call — streaming or not — can hang indefinitely.**
That is the real severity of CF-7, and it is what makes this a Wave-1 task rather than
housekeeping.

Verify it yourself before you start (Rule 4 — do not take my word for it):

```bash
python -c "
import anthropic
c = anthropic.Anthropic(api_key='sk-test', timeout=None)
print('explicit None ->', repr(c._client.timeout))
print('omitted       ->', repr(anthropic.Anthropic(api_key='sk-test')._client.timeout))
"
```

### 3.5 The only place any LLM timeout is applied today

`src/hachi/core/memory_vault.py:304`:

```python
            _llm_client_instance = AnthropicClient(timeout=30.0)
```

So **background memory extraction times out at 30 s while user-facing chat can hang
forever.** The two other bare constructions —
`src/hachi/core/sub_agent.py:685` (`AnthropicClient(model=model, max_tokens=4096)`) and
`src/hachi/tools/memory_tools.py:120` (`AnthropicClient()`) — have no timeout either.

### 3.6 Why a hang costs a worker

`grep -c "async def" src/hachi/core/loop.py` → **0**.
`grep -c "async def" src/hachi/core/resilience.py` → **0**.

Both modules are fully synchronous. A blocked socket read is a blocked OS thread.

## 4. Reproduce the failure

**The hang itself is not reproducible from a shell without a hostile/hung endpoint**, and
you should not build one. Two things *are* directly reproducible, and together they are the
proof:

**(a) The configured value never reaches the client** — copy-pasteable:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
python - <<'PY'
import sys; sys.path.insert(0, "src")
from hachi.core.llm import create_llm_client

c = create_llm_client({"kind": "anthropic", "model": "claude-haiku-4-5"})
print("anthropic client.timeout   ->", repr(c.client.timeout))

c2 = create_llm_client({"kind": "openrouter", "model": "m"})
print("openai-compat http timeout ->", repr(c2._http.timeout))
PY
```

Requires `ANTHROPIC_API_KEY` to be set to anything non-empty (the constructor raises without
one at `llm.py:270-271`; `ANTHROPIC_API_KEY=sk-test` is enough — no network call is made).

**You will see now:**

```
anthropic client.timeout   -> None
openai-compat http timeout -> Timeout(timeout=60.0)
```

`None` = no timeout. The asymmetry is the bug.

**You should see after the fix:** both report the configured value (60 s by default), e.g.
`Timeout(timeout=60.0)` / `60.0`.

**(b) The config value is inert** — set `[routing.resilience] timeout_s = 5` in a settings
file, boot, and observe that no client anywhere reports a 5 s timeout. The code-reading
proof is §3.1: the word-boundary grep shows two definitions, one docstring, zero reads.

## 5. What "fixed" looks like

`create_llm_client` grows a **keyword-only** parameter with a default, and passes it to the
two official client classes:

```python
def create_llm_client(
    provider_config: dict[str, Any],
    secret_store: SecretStore | None = None,
    max_tokens: int = 4096,
    *,
    timeout_s: float = 60.0,
) -> BaseLLMClient:
```

- **Keyword-only** (after `*`). A positional parameter would silently reorder arguments for
  any caller passing `max_tokens` positionally. Grep first: `grep -rn "create_llm_client(" src/ tests/`
  — there are 11 call sites in `src/` and 9 in `tests/` today.
- **Defaulted**, so all 20 existing call sites keep compiling untouched.
- Name it `timeout_s` to match `RetryPolicy.timeout_s` / `ResilienceSettings.timeout_s`.

Apply it at four of the six returns:

- `llm.py:882` → `AnthropicClient(..., timeout=timeout_s)`
- `llm.py:888`, `:905`, `:944`, `:960` → `OpenAICompatibleClient(..., timeout=timeout_s)`
- `llm.py:934` (`chatgpt-web`) → **leave alone**, see §9.

**Chosen default: 60.0 seconds.** State this explicitly in your commit message. Rationale:
it is what the module docstring already promises, what `RetryPolicy.timeout_s` already
declares, and what every OpenAI-compatible provider already gets — so it makes Anthropic
*consistent with the rest of the product* rather than introducing a new number.

Also **fix the wrong docstring** at `llm.py:267`:

```python
            timeout: Per-request timeout in seconds. None uses the SDK default (600s).
```

→ something true, e.g.: *"Per-request timeout in seconds. `None` is passed through to the
SDK verbatim, which httpx interprets as NO timeout — pass a number."* This one-line
correction is in scope; it is the thing that made two audits get this wrong.

### Wiring the config value (the second half)

`RetryPolicy.from_config` already loads `[routing.resilience].timeout_s` into a `RetryPolicy`.
The router builds clients — `src/hachi/core/routing/router.py:301`:

```python
        return create_llm_client({"kind": desc.provider, "model": desc.id})
```

Pass the policy's `timeout_s` through there. **Pass the float, not the policy object** —
see the circular-import trap in §12.

If threading the value from the policy to `router.py:301` turns out to require restructuring,
land the `create_llm_client` parameter + its default first (that alone removes the
infinite-hang), and note the remaining config wiring in the commit message.

## 6. Steps

1. **Write the regression test from §7 first.** Run it. Watch it fail with
   `assert None == 60.0` (or equivalent).
2. Add the keyword-only `timeout_s: float = 60.0` parameter to `create_llm_client`
   (`llm.py:859-861`).
3. Pass `timeout=timeout_s` at `llm.py:882`, `:888`, `:905`, `:944`, `:960`.
4. Correct the `AnthropicClient.__init__` docstring at `llm.py:267`.
5. Re-run the test. It should pass.
6. Wire `RetryPolicy.timeout_s` → `create_llm_client(..., timeout_s=...)` at
   `core/routing/router.py:301`. Pass **the float**, never the `RetryPolicy` object.
7. Run the full suite and check §12's behaviour warning: hunt for long non-streaming
   generations in tests/eval fixtures that previously relied on unbounded waiting.
8. Add the bug-bank entry (§11).
9. Full `uv run python scripts/preflight.py`, report real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_llm_env_resolution.py` (existing — it already calls
  `create_llm_client` at `:17` with a fake key, so the fixture pattern is there) or a new
  `tests/test_llm_timeout.py`.
- **Test name:** `test_create_llm_client_applies_timeout_to_anthropic_sdk_client`
- **It must assert:** the **real** `anthropic.Anthropic` instance built by
  `create_llm_client` reports the configured timeout — i.e. read
  `client.client.timeout` (the SDK object's own attribute), not a value you passed in and
  echoed back. Assert on the SDK, not on a mock.
- **It must FAIL before your fix** with: `AssertionError: assert None == 60.0`

Add a second assertion (or second test) for `OpenAICompatibleClient`, reading
`client._http.timeout`, so the two paths are pinned symmetrically — and so a future change
cannot regress the one that currently works.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

import httpx

from hachi.core.llm import AnthropicClient, OpenAICompatibleClient, create_llm_client


def test_create_llm_client_applies_timeout_to_anthropic_sdk_client(monkeypatch) -> None:
    """A per-call timeout must reach the Anthropic SDK client.

    Before the fix, create_llm_client omitted `timeout`, so AnthropicClient's own
    default of None was passed to anthropic.Anthropic(). An explicit None is a
    *given* value to that SDK, so it is forwarded to httpx as "no timeout" —
    Anthropic calls could hang indefinitely.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    client = create_llm_client({"kind": "anthropic", "model": "claude-haiku-4-5"})
    assert isinstance(client, AnthropicClient)

    # Read the SDK object's own resolved timeout — not the argument we passed.
    resolved = client.client.timeout
    assert resolved is not None, "Anthropic SDK client has NO timeout — calls can hang forever"
    seconds = resolved.read if isinstance(resolved, httpx.Timeout) else float(resolved)
    assert seconds == 60.0


def test_create_llm_client_applies_timeout_to_openai_compatible(monkeypatch) -> None:
    """The OpenAI-compatible path already had 60s; pin it so it cannot silently regress."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    client = create_llm_client({"kind": "openrouter", "model": "m"})
    assert isinstance(client, OpenAICompatibleClient)

    resolved = client._http.timeout
    seconds = resolved.read if isinstance(resolved, httpx.Timeout) else float(resolved)
    assert seconds == 60.0
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Specifically: if `test_create_llm_client_applies_timeout_to_anthropic_sdk_client` passes
> before the fix, you are probably asserting on `AnthropicClient`'s constructor argument
> instead of on `client.client.timeout`.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, asserts on the real SDK client's `timeout`, and
      failed before the fix.
- [ ] `create_llm_client` has a **keyword-only**, defaulted `timeout_s` parameter and all
      20 existing call sites (11 in `src/`, 9 in `tests/`) still work unmodified.
- [ ] The reproduction script in §4(a) prints a non-`None` timeout for the Anthropic path.
- [ ] The wrong docstring at `llm.py:267` is corrected.
- [ ] `[routing.resilience].timeout_s` reaches a built client (or, if deferred, the commit
      message says so explicitly and why).
- [ ] The chosen default (60.0 s) is stated in the commit message.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add a timeout to `ChatGPTWebClient`** (`core/unofficial_providers.py:98`,
  reachable only via `llm.py:934` behind `HACHI_UNOFFICIAL=1`). It is a reverse-engineered,
  opt-in, off-by-default provider with a different transport. You will notice it while
  editing the six returns and it will feel like an omission. Leave it; note it and move on.
- **Do not touch `ResilientClient`, `resilient_call`, or the retry constants.** The retry
  layers are a real problem and they are
  [T-24-collapse-retry-layers.md](T-24-collapse-retry-layers.md). Your diff here should not
  contain the word `retry`.
- **Do not "fix" the wall-clock deadline** in `core/loop.py`. It is genuinely broken (a hung
  socket defeats it) and it is
  [T-28-wall-clock-deadline-hung-socket.md](T-28-wall-clock-deadline-hung-socket.md), which
  is sequenced **after** this task precisely because a real transport timeout is the primary
  defence and T-28 is belt-and-braces on top.
- **Do not change `memory_vault.py:304`'s 30 s.** It works. Making everything uniform is a
  judgement call nobody asked for.
- **Do not add a `timeout` parameter to `BaseLLMClient`** or otherwise change the abstract
  interface. Two concrete classes already have it.
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
uv run pytest tests/test_llm_env_resolution.py tests/test_provider_presets.py \
              tests/test_unofficial_providers.py tests/test_multi_provider.py \
              tests/test_resilience.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — Anthropic LLM calls had NO timeout (not 600s); the configured `timeout_s` was never read

- **Symptom:** an Anthropic chat turn could hang indefinitely — spinner forever, no error,
  a parked thread per hung call. Setting `[routing.resilience] timeout_s` changed nothing.
- **Root cause:** two independent gaps. (1) `create_llm_client` (`core/llm.py:859`) omitted
  `timeout` at all six returns, so `AnthropicClient.__init__`'s own default of `None` was
  used. (2) That `None` was passed *explicitly* to `anthropic.Anthropic(timeout=...)`
  (`llm.py:273`), and in `anthropic` 0.105.2 an explicit `None` is a **given** value:
  `_base_client.py:932` only substitutes `DEFAULT_TIMEOUT` when `not is_given(timeout)`, and
  `is_given(None)` is True. So httpx received `Timeout(None)` = wait forever. The SDK's
  secondary non-streaming ceiling is gated on `self._client.timeout == DEFAULT_TIMEOUT`
  (`resources/messages/messages.py:987`) and was therefore also disabled.
  `RetryPolicy.timeout_s` (`core/resilience.py:86`) and `ResilienceSettings.timeout_s`
  (`core/settings.py:170`) had **zero** readers — a word-boundary grep across `src/` returns
  only the two definitions and one docstring.
- **Fix:** `create_llm_client` takes a keyword-only `timeout_s: float = 60.0` and applies it
  to both official client classes. `AnthropicClient`'s docstring — which claimed `None` meant
  "the SDK default (600s)" — corrected.
- **Avoid:** when an SDK distinguishes "not given" from `None` (a `NotGiven` sentinel),
  passing `None` is NOT the same as omitting the argument. Verify against the installed
  package (CLAUDE.md Rule 4) — both a review and a corrections pass got this wrong from the
  docstring alone. And: a config field with zero readers is a lie; grep `-w` for every new
  settings field.
- **Locked by:** `tests/test_llm_env_resolution.py` —
  `test_create_llm_client_applies_timeout_to_anthropic_sdk_client`
```

## 12. Known traps

- **Circular import — pass the float, not the policy.** `core/resilience.py:26` already
  imports from `core/llm.py`:

  ```python
  from hachi.core.llm import BaseLLMClient, LLMResponse, Message
  ```

  Having `llm.py` import `RetryPolicy` back from `resilience.py` creates a cycle. Type the
  new parameter as `float`, not `RetryPolicy`. If you want the type for annotation only, use
  `TYPE_CHECKING` — but you should not need it.

- **Keyword-only, or you break callers.** `create_llm_client(provider_config, secret_store,
  max_tokens)` — a positional insertion silently shifts `max_tokens`. Run
  `grep -rn "create_llm_client(" src/ tests/` before editing the signature. Note
  `core/routing/router.py:301` calls it with only a dict, and
  `core/sub_agent.py:681` calls it as `create_llm_client(provider_config, max_tokens=4096)`.

- **Behaviour warning: 60 s can break something that 600 s (or ∞) tolerated.** A long
  non-streaming generation — a big `max_tokens` completion, an eval fixture, an authoring
  call — that previously waited will now raise. Before you land it: grep tests and eval
  fixtures for non-streaming `generate(` calls with large `max_tokens`, run the **full**
  suite (not a scoped run), and state the chosen default in the commit message so a
  reviewer can push back on the number rather than on the mechanism.

- **A test asserting the argument instead of the SDK proves nothing.** `AnthropicClient`
  stores nothing you can read back; you must reach `client.client.timeout`. Note
  `anthropic.Anthropic` normalises: a float stays a float, an omitted value becomes an
  `httpx.Timeout`. Handle both in the assertion (see the §7 sketch).

- **Do not re-guess the `anthropic` API.** The facts in §3.4 were verified against the
  installed `anthropic` 0.105.2 at
  `C:\Users\opsin\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\anthropic\`.
  If you need a fact not listed there, read that source — do not recall it
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 4).

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
