# T-32 · Stop the OpenAI facade sharing one session across all callers

|  |  |
|---|---|
| **Source finding** | CF-9 (defect 1) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | **[T-31](T-31-openai-facade-decision.md) — do not start until it has landed.** Under options (c) or (d) this task is thrown away. |
| **Blocks** | nothing |
| **Effort** | ~half a day |
| **Difficulty** | Medium — the code is small; §5 contains one design question you must read before writing anything |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `tests/test_gateway_openai_channels.py` |

---

## 1. Brief

`POST /v1/chat/completions` (non-streaming) passes no `session_key`, so every caller lands in one
server-side session named `"__default__"` — and the facade performs **no ownership check at all**, so a
second bearer holder reaching that session gets no 403. Result: cross-caller conversation bleed and
cross-principal read/write of one agent's memory. When you are done, each caller gets its own session,
and any caller reaching a session it does not own gets a 403 — the same rule the other 10 session-scoped
routes already enforce.

## 2. Why this matters

Every other session-scoped route in the gateway calls `_check_session_ownership`. The facade is the
single exception, and it is also the only route that hands out a **shared** session — so the one place
missing the check is the one place where the check would actually catch something. The failure is not
"two conversations get mixed up in the UI"; it is that a bearer holder can read another principal's
accumulated agent memory and write to it. Hachi's stated moat is an owned, verifiable audit trail. A
route where the audit trail attributes A's actions to B's session is that moat leaking. If your fix
gives each caller a distinct session but still never checks ownership, you have fixed the symptom and
left the hole.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The shared session — `openai_chat_completions`, `src/hachi/gateway/fastapi_app.py:1639-1643`

```python
        if not payload.stream:
            # Full agent turn is synchronous — run in a thread so the event loop stays free.
            result = await anyio.to_thread.run_sync(
                lambda: control_plane.complete_chat(prompt, owner_token_hash=caller_hash)
            )
```

No `session_key` is passed. `complete_chat` defaults it (`src/hachi/gateway/control_plane.py:487-492`):

```python
    def complete_chat(
        self,
        prompt: str,
        *,
        session_key: str = "__default__",
        owner_token_hash: str | None = None,
    ) -> dict[str, Any]:
```

and forwards to `get_or_create_session`, which defaults to the same literal
(`src/hachi/gateway/control_plane.py:448-450`):

```python
    def get_or_create_session(
        self, session_key: str = "__default__", *, owner_token_hash: str | None = None
    ) -> str:
```

`"__default__"` appears **0 times** anywhere under `tests/`. Nothing pins this behaviour.

### 3.2 `complete_chat` is just two calls — this is why the fix is small

`src/hachi/gateway/control_plane.py:506-507`:

```python
        session_id = self.get_or_create_session(session_key, owner_token_hash=owner_token_hash)
        return self.send_message(session_id=session_id, prompt=prompt)
```

The plumbing you need already exists and is already tested
(`tests/test_gateway_openai_changes...` — see §3.5). You are not building a mechanism; you are using
one the route declined to use.

### 3.3 Ownership is stamped on create, never checked on reuse — `src/hachi/gateway/control_plane.py:478-484`

```python
            with self._connections_lock:
                self._api_sessions[session_key] = session_id
            # H6: stamp ownership immediately, mirroring the /sessions create route —
            # facade sessions (OpenAI-compat, channel-inbound) must not be ownerless.
            if owner_token_hash is not None:
                self.set_session_owner(session_id, owner_token_hash)
        assert session_id is not None, "session_id must be set after get_or_create_session"
        return session_id
```

The stamping is inside the `if not known:` branch — it runs **only when the session is created**.
Caller A creates `"__default__"` and stamps it; caller B reuses it and is never compared against the
stored owner.

### 3.4 Zero ownership checks in the facade — `src/hachi/gateway/fastapi_app.py`

`_check_session_ownership` is defined at `:746`:

```python
    def _check_session_ownership(session_id: str, caller_hash: str | None) -> None:
        """Enforce C1 session-ownership policy.

        If the session has an owner set, the caller's token-hash must match.
        ...
        Raises:
            HTTPException: 403 if the caller does not own the session.
        """
        if caller_hash is None:
            # No-auth mode or unconfigured token: skip ownership check.
            return
        owner = control_plane.get_session_owner(session_id)
        if owner is not None and not secrets.compare_digest(owner, caller_hash):
            raise HTTPException(
                status_code=403,
                detail="access denied: session is owned by another caller",
```

It has **10 call sites**: `:817`, `:953`, `:977`, `:997`, `:1089`, `:1099`, `:1124`, `:2518`, `:2944`,
`:2987`. **None of them is inside the facade's `:1593-1813`.**

> **Correction to the audit brief:** it described 12 call sites. The verified count is 10 — the grep
> also matches the definition (`:746`) and a docstring mention (`:2514`). The conclusion is unchanged.

### 3.5 The test that makes this look covered — `tests/test_gateway_openai_channels.py:211-217`

```python
def test_complete_chat_reuses_session_per_key() -> None:
    cp = _control_plane()
    first = cp.complete_chat("a", session_key="k1")
    second = cp.complete_chat("b", session_key="k1")
    assert first["session_id"] == second["session_id"]  # same key -> same session
    other = cp.complete_chat("c", session_key="k2")
    assert other["session_id"] != first["session_id"]  # different key -> different session
```

This calls the control plane **directly with an explicit key**. It proves the isolation mechanism
works — and stays green whether or not the route uses it. Leave it alone; it is a valid unit test of a
valid mechanism. Just do not mistake it for coverage of the route.

### 3.6 Auth is single-token — this constrains the design in §5

`_require_auth` (`src/hachi/gateway/fastapi_app.py:556`) returns the **sha256 of the caller's bearer
token**, and the app is constructed with **one** `auth_token`. So every authenticated caller in a normal
deployment produces the **same** `caller_hash`; in no-auth mode it is `None`. Read §5 before assuming
the token hash is a usable identity.

### 3.7 The request model already accepts extra fields — `src/hachi/gateway/fastapi_app.py:223-227`

```python
class OpenAIChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: list[OpenAIMessage]
    model: str | None = None
    stream: bool = False
```

`extra="allow"` means OpenAI's standard optional **`user`** field is already accepted and preserved by
clients that send it — declaring it explicitly is a one-line, backwards-compatible addition.

## 4. Reproduce the failure

### The bleed (one token, reproducible now)

```bash
# Terminal 1
cd /d/OpenGigantic/hachi
HACHI_GATEWAY_NO_AUTH=1 uv run hachi serve --port 8787

# Terminal 2 — "client A" plants something in the shared session
curl -s -X POST localhost:8787/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Remember this codeword: PLATYPUS. Just acknowledge."}]}'

# Terminal 2 — "client B" is a different OpenAI client that has never said this
curl -s -X POST localhost:8787/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"What codeword were you just given?"}]}'
```

**You will see now:** B's response contains `PLATYPUS`. Two independent stateless requests shared one
server-side session. **You should see after the fix:** B has no knowledge of it.

### The missing 403 (needs the ownership hash overwritten)

The gateway enforces a single bearer token, so a genuine second principal cannot be produced by
configuration alone. **Reuse the established pattern** at `tests/test_gateway_interrupt.py:151-185`
(`test_interrupt_route_ownership_enforced`): create the session with `TOKEN_A`, call
`cp.set_session_owner(sid, HASH_B)` out of band, then assert `TOKEN_A` now gets 403. That pattern is
the repo's accepted way to test ownership and is what §7 uses. **Do not invent a multi-token server.**

**You will see now:** the facade returns 200 and runs the turn regardless of who owns the session — no
403 is reachable, because no check exists. **You should see after the fix:** 403 with
`"access denied: session is owned by another caller"`.

## 5. What "fixed" looks like

> **Design question, answered here so you do not have to answer it:** the session key is
> **`f"openai:{principal}:{conversation}"`**, where `principal` is the caller's token hash (or
> `"anon"` in no-auth mode) and `conversation` is the client-supplied OpenAI `user` field — falling
> back to a fresh per-request UUID when the client sends none.

### Why not the token hash alone

Because it fixes nothing in the deployment that exists. §3.6: the gateway is configured with **one**
`auth_token`, so every authenticated caller hashes to the same value and would land in the same
session — the `"__default__"` bug wearing a different name. In no-auth mode `caller_hash` is `None`,
which would need a literal fallback and reproduce the bug exactly.

### Why not a client-supplied id alone

Because it is optional. A client that omits `user` would collapse to a shared literal — the same bug
again — and a *malicious* client could name any other caller's conversation id. Namespacing by
principal makes the id unforgeable across principals if multi-principal auth ever arrives, at zero cost
today.

### Why the per-request UUID fallback

When the client supplies no stable id, the only safe default is **no sharing at all**. This makes the
non-streaming path behave exactly like the streaming path already does (`f"openai-{chat_id}"` from a
fresh UUID, `src/hachi/gateway/fastapi_app.py:1635`, `:1668`) — a known, shipped behaviour rather than
a new invention. It costs a session boot per request, which is precisely the leak
[T-33](T-33-facade-session-lifecycle.md) closes. **The two tasks are complements: T-32 makes sessions
plentiful, T-33 makes them disposable. Land both.**

Target state:

```python
        # T-32: never share one server-side session across callers. Namespace by
        # principal so ids cannot collide across bearer tokens; use the client's
        # OpenAI `user` field for continuity when supplied, otherwise mint a fresh
        # per-request session (matching the streaming path, closed by T-33).
        principal = caller_hash or "anon"
        conversation = (getattr(payload, "user", None) or "").strip() or f"req-{uuid.uuid4().hex}"
        session_key = f"openai:{principal}:{conversation}"

        session_id = await anyio.to_thread.run_sync(
            lambda: control_plane.get_or_create_session(session_key, owner_token_hash=caller_hash)
        )
        # The check the other 10 session-scoped routes perform. Must run BEFORE the turn.
        _check_session_ownership(session_id, caller_hash)
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.send_message(session_id=session_id, prompt=prompt)
        )
```

Also declare the field explicitly on the request model (`src/hachi/gateway/fastapi_app.py:223-227`) so
it appears in the OpenAPI spec instead of riding on `extra="allow"`:

```python
class OpenAIChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: list[OpenAIMessage]
    model: str | None = None
    stream: bool = False
    user: str | None = None   # OpenAI's stable end-user id; keys the Hachi session (T-32)
```

**Critical ordering constraint:** you must split `complete_chat` into its two underlying calls
(§3.2) so the ownership check lands **between** them. `complete_chat` runs the turn and *then* returns
the session id — checking afterwards means the unauthorized turn already executed, already mutated
memory, and already cost money. A 403 after the fact is not access control.

Apply the same `_check_session_ownership(session_id, caller_hash)` line to the streaming path, right
after `get_or_create_session` at `src/hachi/gateway/fastapi_app.py:1669-1673`. It is a no-op there
today (the key is per-request, so the session is always freshly owned) but it costs one line and makes
"the facade checks ownership" true without exceptions.

## 6. Steps

1. **Confirm [T-31](T-31-openai-facade-decision.md) landed with option (a) or (b).** If it landed with
   (c) or (d), stop — this task is superseded.
2. Write the two regression tests from §7. **Run them. Watch them fail.**
3. Add `user: str | None = None` to `OpenAIChatRequest` (`src/hachi/gateway/fastapi_app.py:223-227`).
4. In `openai_chat_completions`, replace the `complete_chat(...)` call at `:1641-1643` with the
   three-step `get_or_create_session` → `_check_session_ownership` → `send_message` sequence from §5.
5. Add `_check_session_ownership(session_id, caller_hash)` to the streaming path immediately after
   `get_or_create_session` (`:1669-1673`).
6. Re-run the tests. Watch them pass.
7. **BB-4:** the request model changed, so the OpenAPI spec changed. Regenerate both (§12).
8. Add the bug-bank entry (§11) and run the full gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

### 7a. No shared session

- **File:** `tests/test_gateway_openai_channels.py` (existing)
- **Test name:** `test_openai_facade_does_not_share_one_default_session`
- **It must assert:** two separate `POST /v1/chat/completions` requests, driven through the real ASGI
  app, produce **different** server-side session ids — observed by recording the `session_id` the
  control plane actually passed to `on_chat`, not by mocking the route.
- **It must FAIL before your fix** with: `AssertionError: assert 1 == 2` (one distinct session id
  recorded, because both requests landed in `"__default__"`).

```python
# sketch — adapt to the file's existing _control_plane() helper
def test_openai_facade_does_not_share_one_default_session() -> None:
    """T-32: two facade callers must not land in the same server-side session."""
    seen: list[str] = []

    def _on_chat(session_id: str, prompt: str) -> str:
        seen.append(session_id)
        return f"echo:{prompt}"

    cp = GatewayControlPlane(on_chat=_on_chat)
    app = create_gateway_app(cp)
    with TestClient(app) as client:
        for text in ("first caller", "second caller"):
            resp = client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": text}]},
            )
            assert resp.status_code == 200

    assert len(set(seen)) == 2, f"both callers shared one session: {seen}"
```

### 7b. Ownership is enforced

- **File:** `tests/test_gateway_openai_channels.py` (existing)
- **Test name:** `test_openai_facade_rejects_foreign_session_owner`
- **It must assert:** a real 403 from the route when the resolved session is owned by a different
  token hash — using the `set_session_owner` out-of-band pattern from
  `tests/test_gateway_interrupt.py:151-185`.
- **It must FAIL before your fix** with: `assert 200 == 403` — the facade currently runs the turn
  regardless of owner.

```python
# sketch — mirrors tests/test_gateway_interrupt.py::test_interrupt_route_ownership_enforced
def test_openai_facade_rejects_foreign_session_owner() -> None:
    """T-32: the facade must perform the ownership check the other 10 routes perform."""
    import hashlib

    _TOKEN_A = "token-a"
    _HASH_B = hashlib.sha256(b"token-b").hexdigest()

    cp = GatewayControlPlane(on_chat=lambda _sid, prompt: f"echo:{prompt}")
    app = create_gateway_app(cp, auth_token=_TOKEN_A)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {_TOKEN_A}"}
        body = {"user": "conversation-1", "messages": [{"role": "user", "content": "hi"}]}

        first = client.post("/v1/chat/completions", json=body, headers=headers)
        assert first.status_code == 200

        # Re-point that session's owner at a different principal.
        session_id = cp.get_or_create_session(
            f"openai:{hashlib.sha256(_TOKEN_A.encode()).hexdigest()}:conversation-1"
        )
        cp.set_session_owner(session_id, _HASH_B)

        denied = client.post("/v1/chat/completions", json=body, headers=headers)
        assert denied.status_code == 403
```

> The `session_key` string in 7b mirrors your §5 implementation. If you change the key format, change
> it here too — and prefer extracting the key construction into a small named helper so the test does
> not hand-rebuild it. Do **not** relax the test to "any non-200" to avoid the coupling.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and failed before the fix with the stated messages.
- [ ] `"__default__"` is no longer reachable from `POST /v1/chat/completions` — grep the facade range
      to confirm no call omits `session_key`.
- [ ] `_check_session_ownership` is called on **both** facade paths, **before** `send_message` runs.
- [ ] The 19 pre-existing tests in `tests/test_gateway_openai_channels.py` still pass — including
      `test_complete_chat_reuses_session_per_key` (`:211`), which must remain untouched.
- [ ] `openapi/hachi-openapi.json` reflects the new `user` field and
      `frontend/src/lib/data/schema.d.ts` was regenerated (BB-4, §12).
- [ ] `npm run --prefix frontend check:api` exits clean.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not fix the session leak.** Your per-request-UUID fallback will visibly create a session per
  request and you will want to close it. That is [T-33](T-33-facade-session-lifecycle.md), which has
  its own regression test asserting `active_connections` returns to baseline. Land this first, then
  that.
- **Do not touch multi-turn history** (`_last_user_text`, `src/hachi/gateway/fastapi_app.py:320-335`).
  Adding a `user` field will make you think "now I can thread the conversation properly". You cannot —
  [T-31](T-31-openai-facade-decision.md) §9 explains why that is an open design question and
  explicitly forbids speccing it as an ordinary task.
- **Do not fix `usage` or the echoed model name** (`:1637`, `:1657-1661`). Defect 4, separate work.
- **Do not touch the channels webhook** (`src/hachi/gateway/fastapi_app.py:1818` onward). It uses the
  same `get_or_create_session` helper and shares this test file, so it looks adjacent — but it already
  keys per sender, which is a defensible design. Changing it is unrequested behaviour change.
- **Do not remove or relax BB-58's model validation** at `:1613-1633`.
- **Do not change `get_or_create_session`'s or `complete_chat`'s `"__default__"` defaults** in
  `control_plane.py`. Other callers rely on the signature; the fix belongs at the call site that failed
  to pass a key. Changing a shared default to fix one caller is exactly the kind of blast-radius
  mistake that produces a new bug-bank entry.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_gateway_openai_channels.py tests/test_gateway_interrupt.py

# BB-4 — MANDATORY, the request model changed
uv run hachi gateway-openapi --output openapi/hachi-openapi.json
npm run --prefix frontend generate:api

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`, and coordinate with any sibling task landing first):

```markdown
### BB-N — OpenAI facade shared one `"__default__"` session across all callers, unchecked

- **Symptom:** two unrelated OpenAI clients calling `POST /v1/chat/completions` (non-streaming) got
  each other's conversation history and each other's accumulated agent memory. No 403 was reachable
  for a caller who did not own the session.
- **Root cause:** two failures that compound. (1) The route called
  `control_plane.complete_chat(prompt, owner_token_hash=...)` without a `session_key`, so every
  caller resolved to the `"__default__"` default in `complete_chat`/`get_or_create_session`.
  (2) `_check_session_ownership` had 10 call sites in `fastapi_app.py` and NONE inside the facade —
  and `get_or_create_session` stamps `owner_token_hash` only when it CREATES a session, so every
  later caller reused a session owned by someone else with nothing comparing them.
  BB-48 fixed the *stamping* half in an earlier pass and reads as though the issue was closed; the
  *checking* half was never added.
- **Fix:** the facade now keys sessions `f"openai:{principal}:{conversation}"` (token hash, plus the
  client's OpenAI `user` field or a fresh per-request UUID), and calls `_check_session_ownership`
  BETWEEN `get_or_create_session` and `send_message` on both paths.
- **Avoid:** a `session_key` parameter with a shared literal default is a loaded gun — any call site
  that forgets it silently joins a global session. When you add a route that resolves a session id,
  the ownership check is part of resolving it, not an optional extra. And an ownership check must run
  BEFORE the side effect, never after: `complete_chat` returns the session id only once the turn has
  already run.
- **Locked by:** `tests/test_gateway_openai_channels.py` —
  `test_openai_facade_does_not_share_one_default_session`,
  `test_openai_facade_rejects_foreign_session_owner`
```

## 12. Known traps

- **BB-4 — THIS TASK CHANGES A GATEWAY REQUEST SHAPE.** Declaring `user` on `OpenAIChatRequest` alters
  the OpenAPI document. Run both:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  npm run --prefix frontend generate:api
  ```
  or `scripts/preflight.py`'s "openapi <-> frontend contract" step (`scripts/preflight.py:124-131`)
  fails, and so does CI.
- **`_check_session_ownership` is a no-op when `caller_hash is None`** (`:762-764`, no-auth mode). Your
  ownership test **must** configure `auth_token=` on the app or it will pass vacuously. This is the
  single most likely way to write a test that proves nothing here.
- **You cannot check ownership after `complete_chat`.** It runs the turn and returns
  `{"session_id", "response"}` — by then the unauthorized work is done. Split it (§3.2, §5).
- **The turn runs in a worker thread** via `anyio.to_thread.run_sync` (`:1641`). `get_or_create_session`
  can block on a full `boot_agent()`, so keep it inside `run_sync` too — do not "simplify" it onto the
  event loop.
- **BB-48 (`docs/bug-bank.md:1007`) will make you think this is already fixed.** Read its "Fix" section
  carefully: it added owner *stamping* for facade sessions, not owner *checking*.
- **`tests/test_gateway_openai_channels.py` covers two features.** Roughly half its 19 tests are
  `test_channel_inbound_*` for the generic channels webhook. Do not let a change here break them.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant to the §4 shell repro,
  not to the unit tests.
