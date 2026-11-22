# T-62 · Give `GET /sessions/{id}/messages` and `POST /sessions/cleanup-empty` the ownership check their siblings have

|  |  |
|---|---|
| **Source finding** | CF-15 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 — **and not exploitable today; read §2 before you write the commit message** |
| **Wave** | **1** (cheap; do it regardless of what [T-61](T-61-single-tenant-adr.md) decides) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~2 hours |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `tests/test_session_route_ownership.py` (new), `docs/bug-bank.md` |
| **See also** | [T-61](T-61-single-tenant-adr.md) — the authz-model decision this anticipates |

---

## 1. Brief

Eleven session routes exist. Nine perform a per-session ownership check; two do not —
`GET /sessions/{session_id}/messages` and `POST /sessions/cleanup-empty`. The reason is
**structural, not an oversight of a line**: neither handler declares a `request: Request`
parameter, so neither can call `_require_auth(request)`, so neither can obtain the
caller digest that `_check_session_ownership` needs.

When you are done, both handlers take `request: Request` and apply the same check their
siblings do.

## 2. Why this matters — and an honest severity statement

**This is not exploitable today.** Both routes sit on the `sessions` router, which
carries `dependencies=protected_dependencies` (`fastapi_app.py:713`, defined at `:710`
as `[Depends(_require_auth)]`), so both **do** require a valid bearer token. And there
is exactly one bearer token per process ([T-61](T-61-single-tenant-adr.md) §3.1), so
every authenticated caller is the same principal. There is no second party to be
protected from. Do not write a commit message or a bug-bank entry that implies a
present-day data leak — that would be exactly the kind of overclaiming this audit
exists to correct.

It matters for two other reasons, both real:

1. **It is the trap CF-15 names.** The day a second token exists — a service account, a
   per-integration key, a shared team gateway — these two routes are the ones that were
   never wired, and `/messages` returns a full conversation transcript. Fixing it now
   costs two hours; fixing it later means finding it again, under pressure, after
   someone has shipped the second token.
2. **It is cheap and unconditional.** [T-61](T-61-single-tenant-adr.md) may decide to
   delete the whole ownership system. Even then this fix is not wasted: it makes the
   set of checked routes *uniform*, which is what makes a clean deletion mechanical
   instead of archaeological. Consistency is the cheap thing to buy either way.

If [T-61](T-61-single-tenant-adr.md) has already landed with the **delete** option, this
task is superseded — do not apply it; note that in the file and move on.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The structural cause — no `request` parameter

`GET /sessions/{session_id}/messages` (`gateway/fastapi_app.py:1036-1067`). The
signature is the whole finding:

```python
    @sessions.get("/{session_id}/messages")
    async def get_session_messages(
        session_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> Any:
```

No `request: Request`. `_require_auth` takes one (`:556`), so this handler **cannot
call it**, and therefore cannot obtain the `caller_hash` that
`_check_session_ownership(session_id, caller_hash)` (`:746`) requires. The body goes
straight to the transcript (`:1062-1067`):

```python
        result = await anyio.to_thread.run_sync(
            lambda: control_plane.session_transcript(session_id=session_id, limit=limit)
        )
        if result is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
        return result
```

### 3.2 The second unchecked route

`POST /sessions/cleanup-empty` (`gateway/fastapi_app.py:1003-1030`) — no parameters at
all:

```python
    @sessions.post("/cleanup-empty")
    async def cleanup_empty_sessions() -> Any:
        """Delete all empty sessions (no messages) from the SQLite store.
        ...
        """
```

It deletes empty session rows **globally** via
`_store.delete_empty_sessions()` (`:1021` / `:1027`). It is a destructive, unscoped
operation with no caller identity. Note the mitigation: it only removes sessions with
no messages, so the blast radius is bounded — but the scoping question is the same one.

### 3.3 Both routes ARE authenticated

State this accurately. The router declaration (`:710-713`):

```python
    protected_dependencies = [Depends(_require_auth)]

    system = APIRouter(tags=["system"])
    sessions = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=protected_dependencies)
```

So `_require_auth` **does** run for both routes and a bad token is rejected. What is
missing is only the per-session owner comparison. FastAPI discards a router-level
dependency's return value, which is exactly why the nine checked handlers call
`_require_auth(request)` again themselves.

### 3.4 The nine routes that DO check — the pattern to copy

The idiom is one line, usually at the top of the body:

```python
        _check_session_ownership(session_id, _require_auth(request))
```

| Route | Anchor | Note |
|---|---|---|
| `GET /sessions` | `:791-813` | owner-**filters** inline (`:803-812`), does not 403 |
| `GET /sessions/{id}` | `:817` | canonical one-liner |
| `POST /sessions/{id}/messages` | `:953` | |
| `DELETE /sessions/{id}` | `:977` | |
| `POST /sessions/{id}/interrupt` | `:997` | |
| `POST /sessions/{id}/permissions/always-allow` | `:1089` | skipped for the `"current"` sentinel (`:1087-1088`) |
| `GET /sessions/{id}/events` | `:1099` | |
| `GET /sessions/{id}/stream` | `:1124` | |
| `POST /sessions` (create) | `:776`, `:787-788` | *stamps* the owner rather than checking |

Beyond the sessions router, for context: runs check via `_check_run_ownership`
(`:2510`) at `:2548`, `:2575`, `:2634`, with an inline filter on `GET /runs` at
`:2529-2535`; interactions check at `:2944` and `:2987` (the review called these
"approvals" — they are `interactions_router`, `:2914`).

### 3.5 What `_check_session_ownership` does

`gateway/fastapi_app.py:746-770` — reproduced in full because you must not change its
semantics, only its coverage:

```python
    def _check_session_ownership(session_id: str, caller_hash: str | None) -> None:
        """Enforce C1 session-ownership policy.
        ...
        """
        if caller_hash is None:
            # No-auth mode or unconfigured token: skip ownership check.
            return
        owner = control_plane.get_session_owner(session_id)
        if owner is not None and not secrets.compare_digest(owner, caller_hash):
            raise HTTPException(
                status_code=403,
                detail="access denied: session is owned by another caller",
            )
```

Two escape hatches are deliberate and must survive your change: `caller_hash is None`
(no-auth / unit-test mode) returns early, and `owner is None` (legacy/ownerless) is
allowed. Under one token today, the effective behaviour of adding the call is **no
behavioural change at all** — which is precisely why it is safe to land in Wave 1.

## 4. Reproduce the failure

The asymmetry is provable from a shell in one command. There is no *behavioural* failure
to reproduce with a single token — say so rather than inventing one.

```bash
# 1. Two session routes take no Request, so they cannot authorise. Read the signatures.
grep -n "@sessions\." -A 5 src/hachi/gateway/fastapi_app.py | grep -B1 -A4 "async def"

# 2. Count checks vs. session routes. Expect 7 vs 11.
grep -c "_check_session_ownership(" src/hachi/gateway/fastapi_app.py
grep -c "@sessions\." src/hachi/gateway/fastapi_app.py

# 3. Confirm the two named handlers have no `request` parameter.
sed -n '1003,1005p;1036,1041p' src/hachi/gateway/fastapi_app.py
```

**You will see now:** (3) prints
`async def cleanup_empty_sessions() -> Any:` and
`async def get_session_messages(session_id: str, limit: int = Query(...)) -> Any:` —
neither has `request: Request`.

**You should see after the fix:** both signatures include `request: Request`, and
grep (2) counts 9 checks.

**Behavioural proof requires two tokens, which the app does not support** — see §7 for
how the test manufactures the second principal legitimately (by stamping a *different*
owner digest through the control plane, rather than by faking a second bearer).

## 5. What "fixed" looks like

No decision required. The pattern already exists nine times; copy it.

1. `get_session_messages` gains `request: Request` and the standard one-liner:

   ```python
   @sessions.get("/{session_id}/messages")
   async def get_session_messages(
       session_id: str,
       request: Request,
       limit: int = Query(default=200, ge=1, le=1000),
   ) -> Any:
       ...
       _check_session_ownership(session_id, _require_auth(request))
   ```

   Put the check **before** the `session_transcript` call at `:1062` — check before you
   read, so a 403 never costs a SQLite round-trip and never leaks timing.

   **Parameter order matters:** `request: Request` has no default, so it must come
   before `limit`, which does. Putting it last is a `SyntaxError`; FastAPI does not care
   about the order, Python does.

2. `cleanup_empty_sessions` gains `request: Request` and calls `_require_auth(request)`.
   There is no `session_id`, so there is nothing to owner-check — the honest fix here is
   an explicit auth call plus a comment saying the operation is global by design. Do
   **not** invent a per-session scoping semantic for it in this task (§9).

3. Observable outcome under one token: **nothing changes**. Under two, `/messages`
   returns 403 for a foreign session instead of the transcript.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Add `request: Request` to `get_session_messages` (`:1037-1040`), positioned before
   `limit`.
3. Add `_check_session_ownership(session_id, _require_auth(request))` as the first
   statement of the body, above the `anyio.to_thread.run_sync` call at `:1062`.
4. Add `request: Request` to `cleanup_empty_sessions` (`:1004`) and call
   `_require_auth(request)` at the top of the body, with a one-line comment stating the
   operation is intentionally global.
5. Run the regression test — it must now pass.
6. Regenerate the OpenAPI spec and the frontend types (BB-4 — see §12); the added
   parameter changes the schema.
7. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_session_route_ownership.py` (**new**)
- **Test name:** `test_session_messages_denies_a_foreign_owner`
- **It must assert:** the real, observed HTTP response — a 403 from a live `TestClient`
  when the session carries a *different* owner digest. Not that a function was called.
- **How to get a second principal honestly:** the app supports one bearer, so you cannot
  authenticate as a second caller. Stamp a foreign owner directly through the control
  plane (`set_session_owner(session_id, "<some other digest>")`) and then request the
  session with the one real token. That is a faithful simulation of the future state
  CF-15 warns about, and it is the same technique the ownership code itself would face.
- **It must FAIL before your fix** with `assert 200 == 403` — because today the handler
  cannot see the caller at all and returns the transcript unconditionally.

```python
# sketch — adapt to the repo's existing gateway fixtures
from __future__ import annotations

from fastapi.testclient import TestClient

from hachi.gateway.fastapi_app import create_gateway_app

TOKEN = "test-token"
FOREIGN_OWNER_DIGEST = "0" * 64      # a digest that is not sha256(TOKEN)


def _bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_session_messages_denies_a_foreign_owner() -> None:
    """GET /sessions/{id}/messages must apply the ownership check its siblings do.

    Regression: the handler's signature was (session_id, limit) with no
    `request: Request`, so it could not call _require_auth() and therefore could
    not obtain the caller digest _check_session_ownership() needs. Not exploitable
    under a single bearer token — this pins the invariant before a second one exists.
    """
    control_plane = _build_control_plane()          # existing helper
    app = create_gateway_app(control_plane, auth_token=TOKEN, bind_host="127.0.0.1")
    client = TestClient(app)

    session_id = client.post(
        "/sessions", json={"client_id": "t", "surface": "test"}, headers=_bearer()
    ).json()["session_id"]

    # Simulate the future two-principal world: this session belongs to someone else.
    control_plane.set_session_owner(session_id, FOREIGN_OWNER_DIGEST)

    resp = client.get(f"/sessions/{session_id}/messages", headers=_bearer())
    assert resp.status_code == 403, (
        f"expected 403, got {resp.status_code}. GET /sessions/{{id}}/messages returns "
        "the full transcript without checking session ownership."
    )


def test_session_messages_still_serves_the_owner() -> None:
    """The fix must not break the normal single-principal path."""
    control_plane = _build_control_plane()
    app = create_gateway_app(control_plane, auth_token=TOKEN, bind_host="127.0.0.1")
    client = TestClient(app)

    session_id = client.post(
        "/sessions", json={"client_id": "t", "surface": "test"}, headers=_bearer()
    ).json()["session_id"]

    resp = client.get(f"/sessions/{session_id}/messages", headers=_bearer())
    assert resp.status_code in (200, 404)   # 404 = no persisted messages yet; never 403
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The most likely reason it passes early: `set_session_owner` is a **silent no-op** when
> the session is not in `control_plane._connections` ([T-61](T-61-single-tenant-adr.md) §3.3a),
> so your foreign digest never lands and `get_session_owner` returns `None`, which means
> *allow*. Assert `control_plane.get_session_owner(session_id) == FOREIGN_OWNER_DIGEST`
> right after stamping it — if that assertion fails, your test setup is wrong, not the
> route.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_session_messages_denies_a_foreign_owner` failed before the fix with `assert 200 == 403`.
- [ ] `test_session_messages_still_serves_the_owner` passes — the normal path is unchanged.
- [ ] `grep -c "_check_session_ownership(" src/hachi/gateway/fastapi_app.py` returns **9** (was 7; the definition line is one of the counted hits).
- [ ] Every `@sessions.`-decorated handler either takes `request: Request` or has a comment saying why it does not.
- [ ] The OpenAPI spec and `frontend/src/lib/data/schema.d.ts` are regenerated and committed (BB-4).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not fix the ownership *model*.** That is [T-61](T-61-single-tenant-adr.md), and
  it is exactly what you will drift into once you notice that
  `set_session_owner` silently no-ops and that a missing owner means allow. Both are
  true, both are documented in T-61 §3.3, and neither is this task. You are adding two
  call sites to an existing check, nothing more.
- **Do not add per-session scoping to `cleanup-empty`.** It is global by design
  (`:1005-1011` says "Delete all empty sessions"). Turning it into a per-owner
  operation is a behaviour change to a destructive endpoint that the frontend calls;
  it needs its own decision. Authenticate it, comment it, stop.
- **Do not touch `_check_session_ownership` itself** (`:746-770`). Its two early-return
  escape hatches look like holes and are not — they are the no-auth/unit-test path and
  the legacy-session policy, and ~14 other call sites depend on both.
- **Do not "clean up" the `"current"` sentinel exception** at `:1087-1088`. It is
  deliberate and commented at `:1069-1074`.
- **Do not widen this to the runs or interactions routers.** They already check
  (§3.4); re-auditing them is scope creep.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run hachi gateway-openapi --output openapi/hachi-openapi.json
npm run --prefix frontend check:api
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Run the **full** suite. `GET /sessions/{id}/messages` is the transcript endpoint the web
UI hits on every session switch (`frontend/src/lib/data/domains/chat.ts` —
`loadSessionMessages`), so a signature change there is felt by frontend contract tests
as well as backend ones. Report the **actual** pass/fail counts. "Looks done" is not
done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Two session routes could not authorise, because their handlers took no Request

- **Symptom:** `GET /sessions/{session_id}/messages` returned a full transcript, and `POST /sessions/cleanup-empty` deleted empty session rows globally, without the per-session ownership check the other nine session routes perform. **Not exploitable as shipped** — both routes are bearer-authenticated by the router-level dependency (`fastapi_app.py:710`/`:713`) and exactly one token exists per process, so there is no second principal to be protected from.
- **Root cause:** Structural, not a forgotten line. `get_session_messages(session_id, limit)` and `cleanup_empty_sessions()` declared no `request: Request` parameter, so neither could call `_require_auth(request)` and neither could obtain the caller digest that `_check_session_ownership(session_id, caller_hash)` needs. FastAPI discards a router-level dependency's return value, which is why the nine checked handlers re-call `_require_auth` themselves.
- **Fix:** Both handlers take `request: Request` (before the defaulted params); `/messages` calls `_check_session_ownership(session_id, _require_auth(request))` before touching the transcript store; `cleanup-empty` calls `_require_auth(request)` and documents that it is global by design.
- **Avoid:** when a per-request check needs a value only a `Request` can supply, a handler without a `Request` parameter cannot be checked *at all* — the omission is invisible in a route-by-route review because there is no missing line to spot. Audit signatures, not just bodies.
- **Locked by:** `tests/test_session_route_ownership.py` — `test_session_messages_denies_a_foreign_owner`
```

## 12. Known traps

- **BB-4 (this task will hit it):** any gateway route change ⇒ regenerate the OpenAPI
  spec **and** the frontend API types, or CI fails.
  `scripts/preflight.py:124-131` runs `hachi gateway-openapi` + `npm run check:api` as a
  **blocking** step, and `check:api` does a `git diff --exit-code` — an unregenerated
  `frontend/src/lib/data/schema.d.ts` fails the gate.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`src/hachi/gateway/fastapi_app.py` IS in the strict mypy gate**
  (`mypy-strict-gate.ini` lists it). Your edit must be strict-clean — annotate
  `request: Request` properly and do not leave an implicit `Any`.
- **Python parameter ordering, not FastAPI's.** `request: Request` has no default and
  must precede `limit: int = Query(...)`. Getting this wrong is a `SyntaxError` at
  import, which will look like a broken test collection rather than a signature mistake.
- **`set_session_owner` silently no-ops** when the session is absent from
  `control_plane._connections` (`control_plane.py:381-383`). This will make your test
  setup fail silently — assert the stamp landed before asserting the 403. See the §7
  warning.
- **`caller_hash is None` means "skip"** (`:762-764`). If your test builds the app with
  `create_gateway_app(cp)` and no `auth_token`, `_require_auth` returns `None` (`:586-591`)
  and the check is skipped — your test will pass for the wrong reason. Always pass
  `auth_token=` **and** `bind_host=` in this test.
