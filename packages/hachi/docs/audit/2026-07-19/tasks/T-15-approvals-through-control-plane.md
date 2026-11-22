# T-15 · Route the approvals REST surface through the control plane, and delete the fabricated `expiresAt`

|  |  |
|---|---|
| **Source finding** | CF-4(a) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). **Downgraded P1 → P2** by [CORRECTIONS.md](CORRECTIONS.md) §2 |
| **Severity** | **P2** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none to *build*; it is only *observable* once [T-01](T-01-approver-selection-dead-branch.md) lands |
| **Blocks** | [T-16](T-16-approval-real-deadline.md) |
| **Effort** | ~half a day |
| **Difficulty** | Low (mechanical — copy an existing pattern) |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `src/hachi/gateway/control_plane.py`, `src/hachi/cli/main.py`, `openapi/hachi-openapi.json`, `frontend/src/lib/data/schema.d.ts` (generated), `tests/test_gateway_auth_default.py`, `docs/bug-bank.md` |

---

## 1. Brief

The approvals router is the **only** router in `fastapi_app.py` that bypasses
`GatewayControlPlane` and reaches straight into the process-global approval registry.
While it is there, it also injects a **fabricated** `expiresAt` field — a 60-second
window that corresponds to nothing, and understates the real 180 s timeout by 3×.
When you are done, `GET /approvals` and `POST /approvals/{id}` go through
`control_plane.*` like every other route, and no field on the wire is invented.

## 2. Why this matters

> **Read this before you write a commit message or a release note.**
> **This is an honesty and layering cleanup, NOT a bug fix. Deleting the fabricated
> `expiresAt` is behaviourally a no-op.** The frontend already discards the field —
> `frontend/src/lib/data/domains/approvals.ts:113-126` hardcodes `expiresAt: 0` with a
> comment explaining the server sends no expiry — and the real auto-decline defect was
> **BB-77** in `docs/bug-bank.md`, already found and fixed. Do not claim a user-facing
> win here. If your PR description says "fixes approvals expiring early", it is wrong.

What it *does* buy: the layering rule ("every REST route goes through the control
plane") becomes true without exception, so the seam stays testable and the next
approvals feature has one obvious place to live. And a governance product stops
shipping a timestamp it made up. [T-16](T-16-approval-real-deadline.md) then adds the
*real* deadline on the foundation this task lays.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The direct import that bypasses the seam — `gateway/fastapi_app.py:33-36`

```python
# UC-PERM-006: approvals inbox REST surface. core/approvals.py is a foundation
# module that is always present, so these imports are direct.
from hachi.core.approvals import get_approval_registry
from hachi.core.permissions import PermissionDecision
```

### 3.2 The fabrication — `gateway/fastapi_app.py:1873-1901`, `get_approvals`

```python
    @approvals_router.get("")
    async def get_approvals() -> Any:
        """List all pending permission requests.

        Returns:
            A JSON object ``{"pending": [...]}`` with every unresolved request
            from the approval registry.  Each entry includes ``expiresAt``
            (MED-021) — an ISO-8601 timestamp so that the frontend countdown
            timer can render.
        """
        if not _APPROVALS_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="Approvals module not yet available — Agent A module pending.",
            )
        import datetime as _dt

        # MED-021: annotate each pending request with a conservative expiresAt.
        # The real per-request timeout is tracked inside RegistryApprover; here
        # we use a 60 s window that covers the default approval timeout.  Forward-
        # compatible: if the registry ever adds expiresAt itself, we skip injection.
        _default_ttl_s = 60
        _now = _dt.datetime.now(_dt.UTC)
        _expires_at = (_now + _dt.timedelta(seconds=_default_ttl_s)).isoformat()
        pending = get_approval_registry().list_pending()
        for item in pending:
            if "expiresAt" not in item:
                item["expiresAt"] = _expires_at
        return {"pending": pending}
```

Three separate untruths in one function:

1. The docstring at `:1877-1881` promises `expiresAt` as a real deadline.
2. `_default_ttl_s = 60` at `:1894` — the comment says it "covers the default approval
   timeout". It does not: the real default is **180.0 s**
   (`core/approvals.py:392-397`), so the fabrication understates it by **3×**.
3. `_expires_at` is computed **once per request**, at fetch time — so every pending
   approval, regardless of when it was actually created, gets the same
   `now + 60s`. It is a clock reading, not a deadline. (Same rule as **BB-87**.)

### 3.3 The decision route, same bypass — `gateway/fastapi_app.py:1903-1936`

```python
    @approvals_router.post("/{request_id}")
    async def post_approval_decision(
        request_id: str,
        payload: ApprovalActionRequest,
    ) -> Any:
        ...
        decision = PermissionDecision(action=payload.action, rationale=payload.rationale)
        resolved = get_approval_registry().resolve(request_id, decision)
        if not resolved:
            raise HTTPException(status_code=404, detail=f"Unknown request_id: {request_id}")
        return {"resolved": True}
```

### 3.4 The pattern to copy — every other router

```python
        return control_plane.permission_audit(limit)                    # :1392
        return control_plane.runtime_events(session_id=..., limit=...)  # :1205
        return control_plane.session_state(session_id)                  # :818
```

And on the control-plane side, `gateway/control_plane.py:801-803`:

```python
    def permission_audit(self, limit: int = 50) -> Any:
        handler = self._require_handler(self._get_permission_audit, "permission audit")
        return handler(max(1, min(limit, 500)))
```

with `_require_handler` at `gateway/control_plane.py:248-251`:

```python
    def _require_handler(self, handler: Any, operation: str) -> Any:
        if handler is None:
            raise GatewayUnavailableError(f"{operation} is not attached")
        return handler
```

`GatewayControlPlane.__init__` (`gateway/control_plane.py:85-119+`) takes ~30 injected
callables, one per operation, and they are wired in `_build_gateway_control_plane`
(`cli/main.py:2950-3000`), e.g. `cli/main.py:2977`:

```python
        get_permission_audit=runtime.permission_audit if runtime else None,
```

The runtime side is `_InProcessGatewayRuntime.permission_audit`
(`cli/main.py:530-535`).

### 3.5 The real timeout — `core/approvals.py:392-397`, `RegistryApprover.__init__`

```python
    def __init__(
        self,
        registry: PendingApprovalRegistry,
        emit: Callable[[str, dict[str, Any]], None],
        timeout: float = 180.0,
    ) -> None:
```

Consumed transiently at `core/approvals.py:473` → `PendingApprovalRegistry.wait` →
`entry.event.wait(timeout=timeout)` at `:200`. **The registry stores no deadline
field.** That is why an honest `expiresAt` is [T-16](T-16-approval-real-deadline.md)
and not this task.

### 3.6 The frontend already ignores the field — `frontend/src/lib/data/domains/approvals.ts:107-126`

```ts
  // The gateway's PermissionRequest model (src/hachi/core/permissions.py) has no
  // expiry/timeout/ttl/expires_at field — the 180 s server-side timeout is enforced
  // via threading.Event.wait() and never communicated to the client. We cannot
  // fabricate a meaningful countdown. expiresAt=0 / totalMs=0 signals "no expiry
  // sent", which the ApprovalCard uses to hide the countdown bar entirely rather
  // than show a misleading 0/0 display.
  return {
    ...
    expiresAt: 0,   // no server-sent expiry — countdown bar hidden (see comment above)
    totalMs: 0,
  };
```

`GatewayPendingApproval` (`approvals.ts:16-23`) does not even declare `expiresAt`.
This is the proof that deleting it is a no-op.

## 4. Reproduce the failure

There is no user-visible failure to reproduce — that is the point of §2. What you can
mechanically demonstrate is the layering exception and the fabrication:

```bash
# 1. The approvals router is the only one reaching past the control plane.
#    Expect: hits ONLY inside the approvals router block (~:1897 and ~:1933).
rg -n "get_approval_registry\(\)" src/hachi/gateway/fastapi_app.py

# 2. Every other route goes through the seam. Expect: ~80+ hits.
rg -c "control_plane\." src/hachi/gateway/fastapi_app.py

# 3. The fabricated field exists only on the server side — the frontend never reads it.
rg -n "expiresAt" src/ frontend/src/lib/data/domains/approvals.ts

# 4. The 60 s constant contradicts the real default.
rg -n "_default_ttl_s|timeout: float = 180.0" src/
```

**You will see now:** (1) two hits inside the approvals router; (3) the server injects
`expiresAt` while `approvals.ts:124` hardcodes `expiresAt: 0`; (4) `60` on the gateway
side against `180.0` in `core/approvals.py`.

**You should see after the fix:** (1) returns **nothing** from `fastapi_app.py`;
(3) returns no hits in `src/`; (4) returns only the `180.0` default.

## 5. What "fixed" looks like

No decision required. Follow the established pattern exactly.

1. **`GatewayControlPlane` gains two methods**, alongside `permission_audit`:

   ```python
   def pending_approvals(self) -> Any:
       handler = self._require_handler(self._list_pending_approvals, "pending approvals")
       return handler()

   def resolve_approval(self, request_id: str, action: str, rationale: str = "") -> bool:
       handler = self._require_handler(self._resolve_approval, "approval decision")
       return bool(handler(request_id, action, rationale))
   ```

   with matching `__init__` parameters
   `list_pending_approvals: Callable[[], list[dict[str, Any]]] | None = None` and
   `resolve_approval: Callable[[str, str, str], bool] | None = None`.

2. **`_InProcessGatewayRuntime` grows the two handlers** (`cli/main.py`, near
   `permission_audit` at `:530`) — these are the *only* places
   `get_approval_registry()` is touched from the gateway edge:

   ```python
   def pending_approvals(self) -> list[dict]:
       return get_approval_registry().list_pending()

   def resolve_approval(self, request_id: str, action: str, rationale: str = "") -> bool:
       return get_approval_registry().resolve(
           request_id, PermissionDecision(action=action, rationale=rationale)
       )
   ```

3. **Wired in `_build_gateway_control_plane`** (`cli/main.py:2963+`), next to
   `get_permission_audit=`. Note these are runtime-independent (the registry is a
   process singleton), so wire them unconditionally rather than
   `... if runtime else None`.

4. **The routes become thin**, and the docstring stops promising `expiresAt`:

   ```python
   @approvals_router.get("")
   async def get_approvals() -> Any:
       """List all pending permission requests.

       Returns:
           ``{"pending": [...]}`` with every unresolved request from the approval
           registry. Entries carry no deadline — the server-side timeout is not
           currently exposed (see T-16).
       """
       ...
       return {"pending": control_plane.pending_approvals()}
   ```

5. **`get_approval_registry` is no longer imported by `fastapi_app.py`.** Keep the
   `PermissionDecision` import only if something else in that module still needs it —
   check with `rg -n "PermissionDecision" src/hachi/gateway/fastapi_app.py` before
   deleting; unused imports fail `ruff`.

6. **`_APPROVALS_AVAILABLE` and the 503 branch stay as-is.** It is dead-ish ceremony
   (`_APPROVALS_AVAILABLE = True` at `:47`), but removing it is a separate decision —
   see §9.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `pending_approvals` / `resolve_approval` to `_InProcessGatewayRuntime`
   (`cli/main.py`), importing `get_approval_registry` and `PermissionDecision` there.
3. Add the two `__init__` parameters and the two methods to `GatewayControlPlane`
   (`gateway/control_plane.py`), copying the `permission_audit` shape exactly.
4. Wire both in `_build_gateway_control_plane` (`cli/main.py:2963+`).
5. Rewrite `get_approvals` (`fastapi_app.py:1873`) to call
   `control_plane.pending_approvals()`. **Delete** lines `:1888-1900` (`import datetime
   as _dt` through the `item["expiresAt"] = _expires_at` loop) and the `expiresAt`
   sentence from the docstring at `:1879-1881`.
6. Rewrite `post_approval_decision` (`fastapi_app.py:1903`) to call
   `control_plane.resolve_approval(request_id, payload.action, payload.rationale)`.
   Keep the 422 validation and the 404-on-unknown-id behaviour byte-identical.
7. Remove the now-unused import at `fastapi_app.py:35`.
8. **Regenerate the OpenAPI spec and the frontend types** — see §12, this is BB-4 and
   CI will fail without it.
9. Amend `tests/test_gateway_auth_default.py` (§12) — it monkeypatches the old symbol.
10. Run the full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_gateway_auth_default.py` (**existing** — add to
  `class TestApprovalsEndpoints`, which starts at `:335`)
- **Test name:** `test_get_approvals_does_not_fabricate_expires_at`
- **It must assert:** the real response body — that `GET /approvals` returns each
  pending entry with **exactly** the keys the registry produced, and specifically that
  `"expiresAt" not in entry`. Assert against a **fresh dict built inside the test**, not
  against the object handed to the stub (see the aliasing trap in §12).
- **It must FAIL before your fix** with:
  `AssertionError: assert 'expiresAt' not in {'request_id': 'req-1', 'tool': 'write_file', 'target': '/tmp/x', 'expiresAt': '2026-07-19T…'}`

```python
# sketch — adapt to the repo's existing fixtures
def test_get_approvals_does_not_fabricate_expires_at(
    self, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gateway must not invent a deadline the registry never recorded.

    Regression: get_approvals() injected expiresAt = now + 60s per request, while the
    real RegistryApprover timeout is 180 s and the registry stores no deadline at all.
    """
    # Build the payload fresh so the route cannot mutate the object we assert against.
    def _list_pending() -> list[dict]:
        return [{"request_id": "req-1", "tool": "write_file", "target": "/tmp/x"}]

    monkeypatch.setattr("hachi.gateway.fastapi_app._APPROVALS_AVAILABLE", True)

    cp = GatewayControlPlane(list_pending_approvals=_list_pending)
    app = create_gateway_app(cp, auth_token=_TOKEN)
    client = TestClient(app)

    resp = client.get("/approvals", headers={"Authorization": f"Bearer {_TOKEN}"})
    assert resp.status_code == 200
    entry = resp.json()["pending"][0]
    assert "expiresAt" not in entry
    assert set(entry) == {"request_id", "tool", "target"}
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> (The most likely cause is the aliasing trap in §12 — you asserted against the same
> dict the route mutated.)

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix with `assert 'expiresAt' not in {...}`.
- [ ] `rg -n "get_approval_registry" src/hachi/gateway/fastapi_app.py` returns **nothing**.
- [ ] `rg -n "expiresAt" src/` returns **nothing**.
- [ ] Both approvals routes call `control_plane.*`; no router in `fastapi_app.py` reaches past the seam.
- [ ] `POST /approvals/{unknown}` still returns **404**, and an invalid `action` still returns **422**.
- [ ] `npm run --prefix frontend check:api` passes (regenerated spec + types committed).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not add a real `expiresAt` here.** That needs a `created_at` on `_PendingEntry`
  and is [T-16](T-16-approval-real-deadline.md). Adding a placeholder "real-ish"
  deadline in this task recreates the exact fabrication you are deleting.
- **Do not touch the frontend.** `approvals.ts` already sets `expiresAt: 0` and its
  comment is correct. Changing the countdown UI is downstream of T-16.
- **Do not delete `_APPROVALS_AVAILABLE` / the 503 branch.** It is vestigial
  (hardcoded `True` at `fastapi_app.py:47`), and removing it is defensible — but it is a
  behaviour change to a documented status code, and `tests/test_gateway_auth_default.py`
  patches it in three places. Note it, move on.
- **Do not split `fastapi_app.py` into per-domain routers.** That is CF-6, ~2 weeks,
  Wave 2. You are moving two functions, not restructuring the module.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `GET /approvals` fabricated an `expiresAt` deadline the registry never recorded

- **Symptom:** Every pending approval came back with `expiresAt = <fetch time> + 60s`, identical across all entries in a response and unrelated to when the request was actually created. Cosmetic only — the frontend discarded the field (`approvals.ts` hardcodes `expiresAt: 0`), so nothing rendered from it. NOT the cause of the BB-77 auto-decline.
- **Root cause:** `get_approvals()` in `gateway/fastapi_app.py` injected a hardcoded 60 s TTL to satisfy a countdown the UI never consumed. The real `RegistryApprover` timeout is 180 s (`core/approvals.py`) and `PendingApprovalRegistry` stores no deadline field at all, so there was nothing truthful to report. The route also reached `get_approval_registry()` directly — the only router in the file bypassing `GatewayControlPlane`.
- **Fix:** Added `pending_approvals()` / `resolve_approval()` to `GatewayControlPlane`, backed by `_InProcessGatewayRuntime` handlers; both approvals routes now go through the seam. Deleted the TTL injection and the `expiresAt` promise in the docstring. Regenerated the OpenAPI spec and frontend types.
- **Avoid:** never synthesise a field the backing store does not hold — a fabricated timestamp reads as more authoritative than an honestly absent one. If a client needs a deadline, add it to the store first.
- **Locked by:** `tests/test_gateway_auth_default.py` — `test_get_approvals_does_not_fabricate_expires_at`
```

## 12. Known traps

- **BB-4 — you MUST regenerate the contract.** The fabricated docstring is baked into
  the committed spec at `openapi/hachi-openapi.json:3257` and into the generated
  `frontend/src/lib/data/schema.d.ts:1244`. `preflight.py` runs
  `npm run --prefix frontend check:api`, which does
  `openapi-typescript … && git diff --exit-code`. **Editing the docstring without
  regenerating fails CI.** Regenerate and commit both files.
- **An existing test will legitimately need amending — this is a contract change, not a
  weakening.** `tests/test_gateway_auth_default.py:385-406`
  `test_get_approvals_returns_pending_list_with_token` does:

  ```python
      monkeypatch.setattr(
          "hachi.gateway.fastapi_app.get_approval_registry",
          lambda: fake_registry,
      )
  ```

  Once the route goes through the control plane, that symbol is gone and the patch is a
  no-op. Rewrite it to inject `list_pending_approvals=` on `GatewayControlPlane`.
  Same for the `POST` tests below it (`:408`, and the helper
  `_make_app_with_fake_registry` at `:338-369`).
  **[CLAUDE.md](../../../../CLAUDE.md) Rule 2 forbids weakening a test to go green; it
  does not forbid updating a test whose patch target you deliberately moved.** Say so
  explicitly in the commit message.
- **Aliasing trap — the current test is blind to the bug.** `:406` asserts
  `body["pending"] == pending`, where `pending` is the *same list object* the route
  mutated in place (`item["expiresAt"] = _expires_at`). The assertion therefore passes
  *because* of the fabrication, not despite it. Your new test must build its payload in
  a factory function (see §7) or deep-copy it.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`GatewayControlPlane()` is constructed bare in several tests** (e.g.
  `tests/test_gateway_auth_default.py:348`, `:372`, `:379`). Your new `__init__`
  parameters must therefore default to `None`, and the routes must surface
  `GatewayUnavailableError` the same way the other unattached handlers do — do not make
  them required.
