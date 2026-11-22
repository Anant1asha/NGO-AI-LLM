# T-31 · Decide the fate of the OpenAI-compat facade

> ## ⚠ DECISION REQUIRED — THIS IS A PRODUCT DECISION, NOT AN ENGINEERING ONE
>
> **Nothing else in CF-9 starts until this is answered.** [T-32](T-32-facade-session-isolation.md) and
> [T-33](T-33-facade-session-lifecycle.md) are both blocked on it. Do not "just start fixing" — the
> correct amount of engineering here ranges from *zero* to *several days* depending on an answer only
> a product owner can give.
>
> **If you are an implementer and no decision has been recorded: STOP and ask.** Bring this document
> and §5's options table with you.

|  |  |
|---|---|
| **Source finding** | CF-9 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 *if kept* — the facade is currently shipped and unflagged |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-32](T-32-facade-session-isolation.md), [T-33](T-33-facade-session-lifecycle.md) |
| **Effort** | ~half a day to decide (this document) · 0 to ~4 days to execute, depending on the answer |
| **Difficulty** | High (needs design judgement — read §9) |
| **Files you will touch** | This document + [docs/DECISIONS.md](../../../DECISIONS.md). **No source files** until a decision is recorded. |

---

## 1. Brief

Hachi ships an OpenAI-compatible HTTP facade (`POST /v1/chat/completions`, `GET /v1/models`) so users
can point Open WebUI / LibreChat at it. It has **four independent defects**, one of which lets any
bearer holder read and write another principal's agent session. It has **zero frontend consumers** but
is advertised in the README, documented in three places, and covered by 19 tests and 2 bug-bank
entries. When you are done, there is a **recorded decision** in `docs/DECISIONS.md` about whether it is
kept-and-fixed, flag-gated, demoted, or deleted — and the dependent tasks are either unblocked or
cancelled.

## 2. Why this matters

The audit's suggestion — *"if neither is worth it, delete the facade"* — reads as a cheap escape hatch.
**It is not, and §3.1 documents why**: deleting it orphans a README promise, three doc sites, 19 tests,
and two bug-bank entries that the regression law exists to protect. Meanwhile, keeping it as-is means
shipping a route where one user's bearer token reaches another user's agent memory. Both directions
have real cost, which is exactly why this is a decision and not a bug. The wrong outcome here is
*drift*: leaving it shipped, unflagged, undocumented as degraded, and half-fixed. Any of the four
options in §5 is better than that.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Deleting it is NOT cheap — what it would orphan

| What | Where | Says |
|---|---|---|
| README feature list | `README.md:197` | "a generic inbound webhook; point Open WebUI / LibreChat at `/v1/chat/completions`." |
| README API surface | `README.md:395` | "`POST /v1/chat/completions` — OpenAI-compatible (point Open WebUI / LibreChat here)" |
| Architecture map | `ARCHITECTURE.md:161` | "`POST /v1/chat/completions` — OpenAI-compat facade" |
| Config guide | `docs/guides/configuration.md:435` | "`HACHI_OPENAI_RATE_LIMIT` \| `60` \| Max `/v1/chat/completions` requests per minute." |
| Tests | `tests/test_gateway_openai_channels.py` | **19 tests, 336 lines** (shared with the channels webhook — see the trap in §12) |
| Bug bank | `docs/bug-bank.md:1007` (**BB-48**) | facade session ownership stamping |
| Bug bank | `docs/bug-bank.md:1672` (**BB-58**) | model validation + per-principal rate limiting |

The regression law ([CLAUDE.md](../../../../CLAUDE.md) Rule 2) exists to keep BB-48 and BB-58 from
recurring. Deleting the facade deletes their locks. That is a legitimate outcome of a deliberate
decision to remove a feature — but it is *not* a free cleanup.

### 3.2 The surface is genuinely tiny — exactly 2 routes, no flag

```python
# src/hachi/gateway/fastapi_app.py:1593
    openai_compat = APIRouter(tags=["openai"], dependencies=protected_dependencies)
# src/hachi/gateway/fastapi_app.py:1594
    openai_limiter = RateLimiter(_int_env("HACHI_OPENAI_RATE_LIMIT", 60), 60.0)
```

- `POST /v1/chat/completions` — `openai_chat_completions`, `src/hachi/gateway/fastapi_app.py:1596`
- `GET /v1/models` — `openai_models`, `src/hachi/gateway/fastapi_app.py:1800`

Registered unconditionally at `src/hachi/gateway/fastapi_app.py:3003`:

```python
    app.include_router(openai_compat)
```

**There is no feature flag.** The only related configuration is the rate limit
(`HACHI_OPENAI_RATE_LIMIT`, `:1594`).

**Zero frontend consumers.** The only `/v1/` strings under `frontend/src` are in the *generated,
never-imported* `schema.d.ts` (`:1180`, `:1197`) — see [T-38](T-38-openapi-pilot-og-domain.md) for why
that file is inert. Nothing in the product calls this facade; it exists purely for external OpenAI
clients.

---

### 3.3 Defect 1 — cross-principal session sharing · **SEVERITY: worst of the four**

**Two independent failures compound.**

**(a) The non-streaming path passes no `session_key`,** so every caller lands in one shared session.
`src/hachi/gateway/fastapi_app.py:1641-1643`:

```python
            result = await anyio.to_thread.run_sync(
                lambda: control_plane.complete_chat(prompt, owner_token_hash=caller_hash)
            )
```

`complete_chat`'s signature defaults `session_key` (`src/hachi/gateway/control_plane.py:487-492`):

```python
    def complete_chat(
        self,
        prompt: str,
        *,
        session_key: str = "__default__",
        owner_token_hash: str | None = None,
    ) -> dict[str, Any]:
```

which forwards to `get_or_create_session`, itself defaulting to the same literal
(`src/hachi/gateway/control_plane.py:448-450`):

```python
    def get_or_create_session(
        self, session_key: str = "__default__", *, owner_token_hash: str | None = None
    ) -> str:
```

So **every non-streaming request from every caller shares the session keyed `"__default__"`**.

**(b) There is no ownership check anywhere in the facade.** `_check_session_ownership` (defined at
`src/hachi/gateway/fastapi_app.py:746`) has **10 call sites** — `:817`, `:953`, `:977`, `:997`,
`:1089`, `:1099`, `:1124`, `:2518`, `:2944`, `:2987` — and **none** of them falls inside the facade's
`:1593-1813`.

> **Correction to the audit brief:** the review material described "12 call sites". The verified count
> is **10** (`grep -n "_check_session_ownership" src/hachi/gateway/fastapi_app.py` also matches the
> definition at `:746` and a docstring mention at `:2514`). The conclusion is unchanged and is the
> point: **zero** of them are in the facade.

**Why (a) and (b) compound into a security defect, not just conversation bleed:**
`get_or_create_session` stamps an owner **only when it creates the session**
(`src/hachi/gateway/control_plane.py:480-483`):

```python
            # H6: stamp ownership immediately, mirroring the /sessions create route —
            # facade sessions (OpenAI-compat, channel-inbound) must not be ownerless.
            if owner_token_hash is not None:
                self.set_session_owner(session_id, owner_token_hash)
```

Caller A makes the first request; `"__default__"` is created and stamped with A's token hash. Caller B
then requests; the session already exists, so no stamping happens — **and nothing checks B against the
stored owner.** B gets A's session: A's conversation history, A's accumulated agent memory, and the
ability to write to both. No 403 is possible because no check is performed.

This is exactly the hole **BB-48** (`docs/bug-bank.md:1007`) half-closed: BB-48 made facade sessions
*stamped* rather than ownerless, but never added the *check* on reuse. Reading BB-48 alone will make
you think this is fixed. It is not.

---

### 3.4 Defect 2 — session leak → permanent failure at the 101st streaming request

The streaming path mints a **brand-new session key per request**.
`src/hachi/gateway/fastapi_app.py:1635` and `:1668`:

```python
        chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
```
```python
            session_key = f"openai-{chat_id}"
```

A fresh UUID guarantees `get_or_create_session` always misses → `create_session` → `_on_connect` → a
full `boot_agent()` (LLM clients, worker threads, SQLite). **`close_session` is never called anywhere
in the facade** — the only occurrence in the entire file is the `DELETE /sessions/{id}` route at
`src/hachi/gateway/fastapi_app.py:978`.

The cap is 100 (`src/hachi/gateway/control_plane.py:167`, overridable via `HACHI_GATEWAY_MAX_SESSIONS`
at `src/hachi/cli/main.py:2955`), enforced as a **hard raise with no LRU and no eviction**
(`src/hachi/gateway/control_plane.py:314-318`):

```python
        with self._connections_lock:
            if len(self._connections) >= self._max_active_sessions:
                raise GatewayProtocolError(
                    f"Maximum active sessions reached ({self._max_active_sessions})."
                )
```

So the **101st streaming request fails, and every request after it fails, permanently, until the
process restarts.** This is a hard denial-of-service reachable by ordinary use of a documented feature.

---

### 3.5 Defect 3 — all client-supplied history is discarded

`_last_user_text` (`src/hachi/gateway/fastapi_app.py:320-335`) is the **only** thing derived from
`payload.messages`, called once at `:1601`:

```python
        prompt = _last_user_text(payload.messages)
```

```python
def _last_user_text(messages: list[OpenAIMessage]) -> str:
    """Extract the latest user message text from an OpenAI-style message list."""
    for message in reversed(messages):
        if message.role != "user":
            continue
        ...
    return ""
```

System prompts and every prior turn are dropped. An OpenAI client that manages its own conversation
state (which is the whole point of the protocol — it is stateless by design) has its state silently
ignored; Hachi substitutes its own server-side session memory instead. A **system-only** request has no
user message at all and 400s — pinned by `tests/test_gateway_openai_channels.py:41-48`:

```python
def test_openai_chat_requires_user_content() -> None:
    app = create_gateway_app(_control_plane())
    with TestClient(app) as client:
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "system", "content": "you are helpful"}]},
        )
    assert resp.status_code == 400
```

---

### 3.6 Defect 4 — false metering and a false model name

`usage` is hardcoded to zeros (`src/hachi/gateway/fastapi_app.py:1657-1661`):

```python
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
```

Any client that meters, budgets, or bills off `usage` gets zeros for real spend.

The model name is echoed, not reported. `src/hachi/gateway/fastapi_app.py:1637`:

```python
        model_name = payload.model or "hachi"
```

echoed back at `:1649`, `:1687`, `:1750`, and `:1786` while the **configured** model actually serves
the turn. The irony: **BB-58** added *validation* at `:1613-1633` — an unknown model id now 400s
against the `list_all_models` allowlist — so the request's model is carefully checked against a list of
real models and then **never routed to**. A caller asking for `claude-haiku-4-5` may be served by
whatever `[routing]` says, and told it got Haiku.

---

### 3.7 The existing tests give false confidence

`tests/test_gateway_openai_channels.py:211-217`:

```python
def test_complete_chat_reuses_session_per_key() -> None:
    cp = _control_plane()
    first = cp.complete_chat("a", session_key="k1")
    second = cp.complete_chat("b", session_key="k1")
    assert first["session_id"] == second["session_id"]  # same key -> same session
    other = cp.complete_chat("c", session_key="k2")
    assert other["session_id"] != first["session_id"]  # different key -> different session
```

This calls the **control plane directly with an explicit `session_key`** — it never goes through the
route. It proves the isolation *mechanism* works while the route that is supposed to use it does not.
It is green today (with the bug) and will be green after the fix. It is not a lie, but it is not
protection either.

Measured coverage gaps, scoped to `tests/test_gateway_openai_channels.py`:

```
__default__      0 occurrences   (also 0 across the whole tests/ tree)
usage            0 occurrences
prompt_tokens    0 occurrences
session_key      3 occurrences   (all in direct control-plane calls, none via the route)
```

> **Correction to the audit brief:** `usage` and `prompt_tokens` *do* appear elsewhere under `tests/`
> (`test_core_tool_cost_guard.py`, `test_measure_turn.py`, `test_streaming.py`) — those are unrelated
> cost/streaming tests. The accurate claim is that they appear **zero times in the facade's own test
> file**: nothing asserts the facade's `usage` block or its reported model.

---

## 4. Reproduce the failure

Defects 1 and 2 are reproducible; 3 and 4 are visible by inspection of a single response.

### Defect 1 — cross-principal bleed (needs two bearer tokens)

The gateway enforces a **single** bearer token, so a true two-principal test needs the ownership hash
to be overwritten out-of-band — the pattern `tests/test_gateway_interrupt.py:151-185`
(`test_interrupt_route_ownership_enforced`) already uses. **Copy that pattern**; do not invent a
two-token server.

The *conversation-bleed* half is reproducible with one token, because a single shared session is the
mechanism:

```bash
# Terminal 1
cd /d/OpenGigantic/hachi
HACHI_GATEWAY_NO_AUTH=1 uv run hachi serve --port 8787

# Terminal 2 — "client A" tells the agent a secret, non-streaming
curl -s -X POST localhost:8787/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Remember this codeword: PLATYPUS. Just acknowledge."}]}'

# Terminal 2 — "client B", a completely separate OpenAI client, asks for it
curl -s -X POST localhost:8787/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What codeword were you just given?"}]}'
```

**You will see now:** the second response knows `PLATYPUS`. Two unrelated stateless requests shared one
server-side session. **You should see after a fix:** the second request has no idea — separate callers
get separate sessions, and a caller reaching another's session gets 403.

### Defect 2 — the session leak

```bash
# with the gateway running as above, lower the cap so this is quick
# (restart the gateway with HACHI_GATEWAY_MAX_SESSIONS=5)
for i in $(seq 1 7); do
  echo "--- request $i ---"
  curl -s -N -X POST localhost:8787/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d '{"stream":true,"messages":[{"role":"user","content":"hi"}]}' | head -2
done
curl -s localhost:8787/readiness | python -m json.tool | grep active_connections
```

**You will see now:** `active_connections` climbs by one per **streaming** request and never falls;
past the cap, requests fail with *"Maximum active sessions reached"* and keep failing.
**You should see after a fix:** `active_connections` returns to its baseline after each streaming
request completes.

> `GET /readiness` reports `active_connections` (`src/hachi/gateway/control_plane.py:275-281`) — that is
> the observable counter to watch, and the one [T-33](T-33-facade-session-lifecycle.md)'s regression
> test asserts on.

### Defects 3 and 4 — read one response body

Send any request with a system prompt, a prior assistant turn, and an explicit `model`. The reply's
`usage` block is all zeros and its `model` echoes what you asked for; the prior turns had no effect.
No special setup needed.

## 5. What "fixed" looks like

> **DECISION REQUIRED.** Pick one. Record it in [docs/DECISIONS.md](../../../DECISIONS.md) with a date
> and a rationale, then update this file's header to name the chosen option so the dependent tasks read
> unambiguously.

| | Option | Effort | Ships | Risk |
|---|---|---|---|---|
| **(a)** | **Keep and fix** | ~2-4 days | A correct facade | Defect 3 is an open design question (§9) |
| **(b)** | **Keep, flag-gate, document reduced semantics** | ~1 day | An honest opt-in facade | Fewest promises broken; still carries defect 3 forever |
| **(c)** | **Demote to a non-agentic passthrough** | ~2 days | An honest OpenAI proxy | Loses "an agent behind an OpenAI URL" |
| **(d)** | **Delete, and remove the README promise** | ~half a day | Less surface | Orphans §3.1's docs, 19 tests, 2 BB entries |

### (a) Keep and fix — RECOMMENDED, *conditional*

Do [T-32](T-32-facade-session-isolation.md) (defect 1) and
[T-33](T-33-facade-session-lifecycle.md) (defect 2) — each about half a day, each small and
well-bounded — then run a **separate design pass** on defect 3 before touching it. Fix defect 4's
`model` echo alongside T-32/T-33 (report the served model, or drop the field's pretence); real `usage`
from `CostTracker` is a nice-to-have that can follow.

**Recommend (a) if** anyone is actually pointing an OpenAI client at Hachi, or if the README promise is
load-bearing for adoption. The two security-relevant defects are genuinely cheap to close, and the
feature is a real differentiator ("your agent, behind an OpenAI URL").

### (b) Keep, but opt-in behind a flag

Wrap `app.include_router(openai_compat)` (`src/hachi/gateway/fastapi_app.py:3003`) in an env check
(e.g. `HACHI_ENABLE_OPENAI_COMPAT`, default **off**), and rewrite the four doc sites in §3.1 to state
the reduced semantics plainly: *history is not honoured, `usage` is not reported, the served model may
differ from the requested one.* **Still do T-32 and T-33** — a flag does not excuse cross-principal
access for the users who turn it on.

**Recommend (b) if** nobody is currently using it but you do not want to break the promise. It is the
lowest-cost honest position.

### (c) Demote to a non-agentic passthrough

Forward `payload.messages` straight to the configured LLM client and return its real response and real
`usage`. This **fixes defects 1, 2, 3 and 4 simultaneously** — no session, so nothing to share, leak, or
discard, and honest metering falls out for free. The cost is that the facade stops being Hachi: no
tools, no memory, no governance. It becomes a thin proxy.

**Recommend (c) if** the goal was ever "let people use their existing OpenAI tooling", rather than "let
people drive the *agent* from OpenAI tooling". Note it makes the README's framing wrong in a different
way, so §3.1's doc sites still need editing.

### (d) Delete

Remove both routes, the router, the rate limiter, the 19 tests, and the four doc references; mark BB-48
and BB-58 as superseded rather than deleting them.

**Recommend (d) only if** a product owner affirmatively says the facade is not part of the product. Do
not choose it because it is the least code — §3.1 is the reason.

## 6. Steps

**Phase 1 — decide (this task).**

1. Read §3 in full, especially §3.3 and §3.4. Do not skim: (a) and (b) of defect 1 compound, and that
   is the whole severity argument.
2. Establish the one fact this decision actually turns on: **is anyone using it?** Check deployment
   notes, support threads, and whether `HACHI_OPENAI_RATE_LIMIT` has ever been set in a real
   environment. If the answer is "no evidence of use", (b) and (d) become much more attractive.
3. Take §5's table to the product owner. Get an answer.
4. Record it in [docs/DECISIONS.md](../../../DECISIONS.md): the option, the date, the rationale, and
   which of the four defects the decision leaves standing.
5. Update this file's header to name the chosen option.

**Phase 2 — execute (depends entirely on the answer).**

- **(a) or (b):** unblock [T-32](T-32-facade-session-isolation.md) and
  [T-33](T-33-facade-session-lifecycle.md). Under (b), also add the flag and rewrite the four doc sites
  from §3.1. Do **not** open a task for defect 3 yet — see §9.
- **(c):** close T-32 and T-33 as superseded; write a new task for the passthrough rewrite. It needs
  its own regression tests proving no session is created (assert `active_connections` is unchanged) and
  that `usage` reflects real token counts.
- **(d):** close T-32 and T-33 as won't-fix; write a deletion task that also covers the four doc sites
  and supersedes BB-48/BB-58.

## 7. Regression test — WRITE THIS FIRST

**This task produces a decision, not a code change, so it has no regression test of its own.** That is
not an exemption from [CLAUDE.md](../../../../CLAUDE.md) Rule 2 — it is the reason this task is
separated from T-32/T-33, which each carry a real failing-test-first requirement:

- [T-32](T-32-facade-session-isolation.md) — `test_openai_facade_does_not_share_one_default_session`
  (and an ownership-403 test).
- [T-33](T-33-facade-session-lifecycle.md) — `test_openai_streaming_closes_its_session`.

**If you find yourself writing production code while executing this task, you are in the wrong task.**

The one artefact this task must produce is a dated entry in
[docs/DECISIONS.md](../../../DECISIONS.md).

## 8. Acceptance criteria

- [ ] A dated decision entry exists in `docs/DECISIONS.md` naming one of (a)/(b)/(c)/(d).
- [ ] The entry states, explicitly, which of the four defects the decision leaves standing and why that
      is acceptable.
- [ ] This file's header names the chosen option.
- [ ] [T-32](T-32-facade-session-isolation.md) and [T-33](T-33-facade-session-lifecycle.md) are each
      either unblocked or closed with a reason.
- [ ] **No source file was modified by this task.** `git diff --stat -- src/` is empty.
- [ ] If the decision is (b), (c), or (d): a follow-up task exists covering the four documentation
      sites in §3.1 — the README promise must not outlive the feature it describes.

## 9. Out of scope — do NOT

- **DO NOT spec defect 3 (multi-turn history) as an ordinary task.** This is the most important
  instruction in this document. "Honour `payload.messages`" sounds like plumbing and is not: the OpenAI
  protocol is *stateless with client-owned history*, Hachi is *stateful with server-owned memory*, and
  there is no obviously-right reconciliation. Do you replay the client's history into the session on
  every request (duplicating memory, unbounded cost)? Diff it against the session and append only what
  is new (fragile, and wrong when a client edits history — which is a normal OpenAI client behaviour)?
  Honour the system prompt but not prior turns (arbitrary)? Ignore history and *document* it (today's
  behaviour, minus the dishonesty)? **Each answer produces a different product.** It needs a design
  pass with a written rationale, not a ticket that says "pass messages through".
- **Do not start T-32 or T-33 before the decision is recorded.** Under (c) or (d) that work is thrown
  away.
- **Do not fix defects 1 and 2 "while you are in here".** They have their own specs, their own
  regression tests, and their own bug-bank entries.
- **Do not touch the channels webhook** (`POST /channels/{channel}/inbound`,
  `src/hachi/gateway/fastapi_app.py:1818` onward). It shares a test file and the same
  `get_or_create_session` helper, so it looks adjacent — but it keys sessions **per sender**, which is
  a different (and more defensible) design. It is not part of this decision.
- **Do not "fix" the model echo by removing BB-58's validation** at `:1613-1633`. The validation is
  correct; what is wrong is that the validated model is then not routed to. Removing the check would
  regress BB-58.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

This task changes no source, so the gate is not the verification — the recorded decision is. Still
confirm you left the tree clean:

```bash
git diff --stat -- src/          # must be empty
git status --short               # only docs/ changes expected
```

If the decision was (a) or (b) and you also landed T-32/T-33 in the same branch:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

**Not applicable to this task** — a decision is not a bug fix, and inventing a `BB-N` for it would
pollute the bank that [CLAUDE.md](../../../../CLAUDE.md) tells everyone to read before debugging.

The bug-bank entries belong to the tasks that fix the actual defects:
- Defect 1 → [T-32](T-32-facade-session-isolation.md) §11
- Defect 2 → [T-33](T-33-facade-session-lifecycle.md) §11

If the decision is **(d) delete**, add a line to the existing **BB-48** (`docs/bug-bank.md:1007`) and
**BB-58** (`docs/bug-bank.md:1672`) marking them superseded by the removal, with the date and a pointer
to the `docs/DECISIONS.md` entry. Do **not** delete those entries — the bank is a history, not a
to-do list.

## 12. Known traps

- **BB-4 applies to options (b), (c), and (d)** — all three change the gateway's route set or response
  shapes. After any of them, run:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  npm run --prefix frontend generate:api
  ```
  or `scripts/preflight.py`'s "openapi <-> frontend contract" step (`scripts/preflight.py:124-131`)
  fails, and so does CI. Option (a) as executed by T-32/T-33 also touches response behaviour — check
  each task's §12.
- **`tests/test_gateway_openai_channels.py` covers TWO features.** Its 19 tests span both the OpenAI
  facade *and* the generic channels webhook (`test_channel_inbound_*`). Under option (d) you must
  delete only the facade half. Deleting the file wholesale silently removes channels coverage.
- **BB-48 will mislead you.** `docs/bug-bank.md:1007` reads as though facade session ownership was
  fixed. It fixed *stamping*, never *checking* (§3.3). Read the "Fix" section carefully before
  concluding defect 1 is already handled.
- **BB-58 will mislead you too.** `docs/bug-bank.md:1672` reads as though the requested model is now
  honoured. It is only *validated* (`:1613-1633`); the configured model still serves the turn (§3.6).
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant to the §4 repros
  against a cold gateway.
- **The facade's rate limiter is per-principal, not global** (BB-58, `:1604-1611`). If you are
  reproducing the session leak with many sequential requests under one token, you will hit
  `HACHI_OPENAI_RATE_LIMIT` (default 60/min) before the 100-session cap. Raise it or lower
  `HACHI_GATEWAY_MAX_SESSIONS`, as §4 does.
