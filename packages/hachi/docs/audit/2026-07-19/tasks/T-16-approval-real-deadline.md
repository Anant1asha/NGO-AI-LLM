# T-16 · Give a pending approval a real deadline, recorded where the request lives

|  |  |
|---|---|
| **Source finding** | CF-4(a) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md), corrected by [CORRECTIONS.md](CORRECTIONS.md) §2 |
| **Severity** | **P2** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | [T-01](T-01-approver-selection-dead-branch.md) — *nothing populates the registry until it lands, so you cannot observe this end-to-end* · [T-15](T-15-approvals-through-control-plane.md) — *it deletes the fake `expiresAt` you would otherwise collide with* |
| **Blocks** | nothing (the frontend countdown is a deliberate follow-up — see §9) |
| **Effort** | ~half a day |
| **Difficulty** | Medium (one small design decision in §5) |
| **Files you will touch** | `src/hachi/core/approvals.py`, `tests/test_action_approval.py`, `docs/bug-bank.md` |

---

## 1. Brief

`PendingApprovalRegistry` stores **no deadline for anything**. The 180-second approval
timeout exists only as a constructor argument on `RegistryApprover`, consumed once and
thrown away inside a `threading.Event.wait()` call. So neither `list_pending()` nor the
`permission.requested` SSE event can tell a client how long it has. When you are done,
each pending entry carries a real creation time and a real expiry, both derived from the
timeout that is actually enforced, and both surfaced on the REST list and the SSE event.

**Backend only.** Rendering a countdown is out of scope (§9).

## 2. Why this matters

[T-15](T-15-approvals-through-control-plane.md) deletes a fabricated deadline. This task
supplies the true one. Between the two, a Hachi user goes from "the countdown is
invented" to "the countdown is what the server will actually do" — which is the whole
governance claim in miniature. Concretely: a person looking at a pending approval today
has no way to know whether they have 5 seconds or 5 minutes to decide, and if they walk
away the request silently auto-denies with rationale `"approval timed out"`
(`core/approvals.py:204`) that nothing on screen predicted.

If your fix ends with a number the server does not enforce, you have rebuilt the bug
T-15 removed.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The entry holds no time at all — `core/approvals.py:88-96`

```python
class _PendingEntry:
    """Internal entry tracking one pending approval request."""

    __slots__ = ("request", "event", "decision")

    def __init__(self, request: PermissionRequest) -> None:
        self.request = request
        self.event: threading.Event = threading.Event()
        self.decision: PermissionDecision | None = None
```

Three slots. No timestamp, no deadline.

### 3.2 `create()` takes only the request — `core/approvals.py:127-136`

```python
    def create(self, request: PermissionRequest) -> str:
        """Store *request* and return its ``request_id``.

        A :class:`threading.Event` is created for each entry so that
        :meth:`wait` can block until :meth:`resolve` is called.
        """
        entry = _PendingEntry(request)
        with self._lock:
            self._entries[request.request_id] = entry
        return cast(str, request.request_id)
```

### 3.3 `list_pending()` returns exactly six keys — `core/approvals.py:138-157`

```python
    def list_pending(self) -> list[dict[str, Any]]:
        """Return all unresolved pending requests as serialisable dicts.

        Each dict contains:
            ``request_id``, ``operation``, ``tool``, ``target``,
            ``reason``, ``policy_summary``.
        """
        with self._lock:
            return [
                {
                    "request_id": e.request.request_id,
                    "operation": e.request.operation,
                    "tool": e.request.tool,
                    "target": e.request.target,
                    "reason": e.request.reason,
                    "policy_summary": e.request.policy_summary,
                }
                for e in self._entries.values()
                if not e.event.is_set()
            ]
```

Note the keys are **snake_case** — that matters for §5.

### 3.4 The timeout is transient — `core/approvals.py:392-397`, then `:473`, then `:200`

```python
    def __init__(
        self,
        registry: PendingApprovalRegistry,
        emit: Callable[[str, dict[str, Any]], None],
        timeout: float = 180.0,
    ) -> None:
```

```python
        request_id = self._build_and_park(action, summary, detail)      # :472
        decision = self._registry.wait(request_id, self._timeout)       # :473
```

```python
        signalled = entry.event.wait(timeout=timeout)                   # :200
        if not signalled:
            # Auto-cleanup on timeout so the entry does not leak.
            self._cleanup(request_id)
            return PermissionDecision(action="deny", rationale="approval timed out")
```

The deadline exists only as a stack-local float inside a blocking call. Nothing that can
be read from outside the thread knows about it. `require_async` (`:495-496`) does the
same thing via `wait_async`.

### 3.5 The SSE payload has the same six fields — `core/approvals.py:410-432`, `_build_and_park`

```python
    def _build_and_park(self, action: str, summary: str, detail: str) -> str:
        """Create a :class:`PermissionRequest`, store it, emit the event, return request_id."""
        request = PermissionRequest(
            request_id=uuid.uuid4().hex,
            operation="action",
            tool=action,
            target=summary,
            reason=detail or summary,
            policy_summary=f"action:{action}",
        )
        request_id = self._registry.create(request)
        self._emit(
            "permission.requested",
            {
                "request_id": request_id,
                "operation": request.operation,
                "tool": request.tool,
                "target": request.target,
                "reason": request.reason,
                "policy_summary": request.policy_summary,
            },
        )
        return request_id
```

### 3.6 `PermissionRequest` is a frozen dataclass — `core/permissions.py:46-55`

```python
@dataclass(frozen=True)
class PermissionRequest:
    """A runtime approval request emitted when policy denies a sensitive action."""

    request_id: str
    operation: str
    tool: str
    target: str
    reason: str
    policy_summary: str
```

**Do not add the timestamp here.** It is frozen, it is constructed in three places
(`core/approvals.py:325`, `:412`, `core/permissions.py:849`), and "when this request was
parked in *this* registry" is a registry concern, not a request-identity concern. Put it
on `_PendingEntry` (§3.1).

### 3.7 What the frontend expects, for reference — `frontend/src/lib/data/types.ts:32`

```ts
  expiresAt: number;
```

consumed by `frontend/src/lib/hooks/useCountdown.ts:39`:

```ts
  const ms = Math.max(0, expiresAt - now);
```

with `now = Date.now()` (`:33`). So the UI's unit is **epoch milliseconds**. Relevant
to §5 — but see §9: you are not changing the frontend in this task.

## 4. Reproduce the failure

Fully reproducible from a shell — the registry is a plain in-process object with no
gateway, no LLM, and no I/O:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run python -c "
from hachi.core.approvals import PendingApprovalRegistry, RegistryApprover
from hachi.core.permissions import PermissionRequest

reg = PendingApprovalRegistry()
RegistryApprover(reg, emit=lambda *_: None, timeout=180.0)
reg.create(PermissionRequest(
    request_id='req-1', operation='action', tool='send_email',
    target='priya@studio.co', reason='reply to Q3 deck', policy_summary='action:send_email',
))
print(reg.list_pending()[0])
"
```

**You will see now:**

```
{'request_id': 'req-1', 'operation': 'action', 'tool': 'send_email', 'target': 'priya@studio.co', 'reason': 'reply to Q3 deck', 'policy_summary': 'action:send_email'}
```

Six keys. Nothing about time — even though a `RegistryApprover` with a 180 s timeout is
sitting right there.

**You should see after the fix:** the same six keys plus `created_at` and `expires_at`,
with `expires_at - created_at == 180000` (ms) for a default-timeout approver, and both
absent (or `None`) for an entry parked without a timeout.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — the wire unit
>
> **(a) Epoch milliseconds (integer) — RECOMMENDED.**
> `expires_at: 1752969600000`.
> *For:* it is exactly what `useCountdown` (`useCountdown.ts:39`) subtracts from
> `Date.now()`, so the frontend adapter is a rename with no parsing; it is unambiguous
> about timezone; it round-trips through JSON as a number.
> *Against:* inconsistent with `control_plane._now_iso()` (`gateway/control_plane.py:81`),
> which the *gateway* uses for its own envelope fields.
>
> **(b) ISO-8601 string.** `expires_at: "2026-07-19T20:15:00+00:00"`.
> *For:* matches the gateway's other timestamps and is human-readable in a curl.
> *Against:* the consumer has to `Date.parse()` it, and the deleted fabrication in
> [T-15](T-15-approvals-through-control-plane.md) was ISO — reusing the format invites
> "wasn't this already here?" confusion in review.
>
> **Recommendation: (a), epoch milliseconds.** Keep the key names **snake_case**
> (`created_at`, `expires_at`) to match the other six keys in `list_pending()` (§3.3);
> the frontend adapter already renames every field it consumes.

Target state:

1. `_PendingEntry` records when it was parked and when it dies:

   ```python
   class _PendingEntry:
       """Internal entry tracking one pending approval request."""

       __slots__ = ("request", "event", "decision", "created_at_ms", "expires_at_ms")

       def __init__(self, request: PermissionRequest, timeout: float | None = None) -> None:
           self.request = request
           self.event: threading.Event = threading.Event()
           self.decision: PermissionDecision | None = None
           self.created_at_ms: int = int(time.time() * 1000)
           self.expires_at_ms: int | None = (
               self.created_at_ms + int(timeout * 1000) if timeout is not None else None
           )
   ```

2. `create()` accepts the timeout that will actually be enforced:

   ```python
   def create(self, request: PermissionRequest, timeout: float | None = None) -> str:
   ```

   **Keep `timeout` optional and defaulted.** `create()` is public API (the module
   docstring at `core/approvals.py:12-15` names it as consumed by the gateway) and
   `tests/test_action_approval.py` calls it positionally.

3. `list_pending()` gains two keys, and its docstring is updated to list them:

   ```python
                   "created_at": e.created_at_ms,
                   "expires_at": e.expires_at_ms,     # None when parked without a timeout
   ```

4. `_build_and_park` passes the approver's real timeout and puts the same two values on
   the SSE payload:

   ```python
           request_id = self._registry.create(request, timeout=self._timeout)
           self._emit(
               "permission.requested",
               {
                   ...,
                   "created_at": ...,
                   "expires_at": ...,
               },
           )
   ```

   To avoid recomputing the clock (and drifting by a millisecond between the entry and
   the event), have `create()` return the id and read the values back — the simplest
   honest way is a small private accessor, e.g. `self._registry.deadline_for(request_id)`
   returning `(created_at_ms, expires_at_ms)`, or have `_build_and_park` read
   `list_pending()`. Pick whichever is smaller; **do not call `time.time()` twice.**

5. `HandlerApprover` (`core/approvals.py:317-344`) is **unchanged** — it never parks
   anything in the registry and has no timeout. Its `permission.requested` payload keeps
   six keys. Consumers must treat both new keys as optional.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `time` to the imports in `core/approvals.py` (it currently imports `threading`,
   `uuid`, `anyio` — `:44-49`).
3. Extend `_PendingEntry.__slots__` and `__init__` (`:88-96`) with `created_at_ms` and
   `expires_at_ms`.
4. Add the optional `timeout` parameter to `PendingApprovalRegistry.create` (`:127`)
   and pass it through to `_PendingEntry`.
5. Add `created_at` / `expires_at` to the dict in `list_pending()` (`:146-154`) and
   update its docstring (`:139-143`) — that docstring is the published contract.
6. Add whatever minimal accessor step 4 of §5 needs, then update
   `RegistryApprover._build_and_park` (`:410-432`) to pass `timeout=self._timeout` and
   emit both fields.
7. Update the module docstring's "Public API consumed by Agent B" block
   (`core/approvals.py:12-15`) if the `create` signature is named there.
8. Run the full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_action_approval.py` (**existing** — add to
  `class TestRegistryApprover`, which starts at `:222`)
- **Test name:** `test_pending_entry_carries_the_deadline_that_is_actually_enforced`
- **It must assert:** the real relationship between the advertised deadline and the
  enforced one — that `expires_at - created_at` equals the approver's `timeout`
  converted to milliseconds, and that both are present on the `permission.requested`
  payload. **Not** that "a key exists" — the whole failure mode of the deleted
  fabrication was a key that existed and meant nothing.
- **It must FAIL before your fix** with:
  `KeyError: 'expires_at'` (from `list_pending()[0]["expires_at"]`).

```python
# sketch — adapt to the repo's existing fixtures
def test_pending_entry_carries_the_deadline_that_is_actually_enforced(self) -> None:
    """The advertised deadline must equal the timeout RegistryApprover really waits.

    Regression: the registry stored no deadline; the 180 s timeout lived only as a
    stack-local inside threading.Event.wait(), so the gateway invented a 60 s one.
    """
    events: list[tuple[str, dict]] = []
    registry = PendingApprovalRegistry()
    approver = RegistryApprover(
        registry, emit=lambda name, payload: events.append((name, payload)), timeout=30.0
    )

    # Park a request without blocking: drive _build_and_park directly.
    request_id = approver._build_and_park("send_email", "priya@studio.co", "reply")

    entry = next(e for e in registry.list_pending() if e["request_id"] == request_id)
    assert entry["expires_at"] - entry["created_at"] == 30_000

    name, payload = events[0]
    assert name == "permission.requested"
    assert payload["expires_at"] == entry["expires_at"]
    assert payload["created_at"] == entry["created_at"]


def test_entry_parked_without_a_timeout_reports_no_deadline(self) -> None:
    """An honest absence, not a fabricated default."""
    registry = PendingApprovalRegistry()
    registry.create(
        PermissionRequest(
            request_id="req-1", operation="action", tool="t",
            target="x", reason="r", policy_summary="p",
        )
    )
    assert registry.list_pending()[0]["expires_at"] is None
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix with `KeyError: 'expires_at'`.
- [ ] `list_pending()` returns **eight** keys, and its docstring lists all eight.
- [ ] `expires_at - created_at` equals the `RegistryApprover` timeout in ms — verified for a non-default timeout, not just 180 s.
- [ ] `expires_at` is `None` (not a fabricated default) when `create()` is called without a timeout.
- [ ] `time.time()` is called **once** per parked request — the entry and the SSE payload report the identical value.
- [ ] `HandlerApprover`'s `permission.requested` payload is unchanged (still six keys).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not render a countdown.** The obvious next move — map `expires_at` in
  `frontend/src/lib/data/domains/approvals.ts:113-126` (which currently hardcodes
  `expiresAt: 0`), unblock `tickApprovals`, restore the countdown bar — is a **separate
  follow-up** and deliberately not in this task. Reason: `tickApprovals`
  (`frontend/src/lib/store/store.ts:799-812`) is the exact code path of **BB-77**, where
  a live approval auto-declined in ~1 second. Re-enabling it needs its own failing test
  and its own review. Note the follow-up; do not do it here.
- **Do not add a timestamp to `PermissionRequest`** (`core/permissions.py:46-55`). It is
  frozen, has three construction sites, and this is registry state, not request identity.
- **Do not make the registry expire entries itself.** Today expiry happens as a side
  effect of `Event.wait()` timing out (`core/approvals.py:200-204`), which auto-cleans
  the entry. Adding a reaper thread or a `list_pending()` filter that drops expired rows
  is a behaviour change with a concurrency surface — out of scope.
- **Do not touch `_cleanup` semantics** (`core/approvals.py:232-239`) or the
  timeout-deny rationale string; `tests/test_action_approval.py:262-271` pins them.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking (`time` is stdlib — fine).

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
### BB-N — Pending approvals carried no deadline; the enforced 180 s timeout was unreadable from outside the waiting thread

- **Symptom:** No client could tell how long an approval had left. `GET /approvals` returned six fields, none temporal, and the `permission.requested` SSE event the same — so the gateway invented a 60 s `expiresAt` to fill the gap and the web UI hardcoded `expiresAt: 0` and hid the countdown entirely.
- **Root cause:** `_PendingEntry` (`core/approvals.py`) had three slots — request, event, decision — and no time. The timeout was a `RegistryApprover.__init__` argument consumed once as a stack-local inside `threading.Event.wait(timeout=…)`, so it existed only for the duration of the blocking call and was never recorded anywhere readable.
- **Fix:** `_PendingEntry` now records `created_at_ms` and `expires_at_ms`; `PendingApprovalRegistry.create()` accepts the timeout that will actually be enforced; `list_pending()` and the `permission.requested` payload surface both as `created_at` / `expires_at` (epoch ms, `None` when no timeout was supplied).
- **Avoid:** if a value governs behaviour, record it where the state lives — a policy that exists only as a stack-local inside a blocking call cannot be reported, and the gap will be filled with a fabrication.
- **Locked by:** `tests/test_action_approval.py` — `test_pending_entry_carries_the_deadline_that_is_actually_enforced`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`__slots__` is not optional here.** `_PendingEntry` declares
  `__slots__ = ("request", "event", "decision")` (`:91`). If you assign
  `self.created_at_ms` without adding it to `__slots__`, you get
  `AttributeError: '_PendingEntry' object has no attribute 'created_at_ms'` at runtime,
  not at import.
- **No existing test should need amending — check that claim.** The tests that read
  `list_pending()` are `tests/test_action_approval.py:273-297`
  (`test_list_pending_returns_unresolved_requests`). If they assert on the *exact* dict
  or on `len(keys)`, they will legitimately need updating for the two new keys — that
  is a contract addition, not a weakening. If they only assert on specific keys, they
  stay green. **Read them before you edit, and say which case it was in the commit
  message** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **`create()` is called positionally in tests** (`registry.create(request)`), so the
  new parameter must be keyword-friendly *and* defaulted. Do not make it positional-only
  or required.
- **Two callers, one signature.** `create()` is called from
  `RegistryApprover._build_and_park` (`:420`) only, in production. But the module
  docstring advertises it as public API for the gateway — keep it backward compatible.
- **Clock choice:** use `time.time()` (wall clock) not `time.monotonic()`. A deadline
  that a *browser* renders must be comparable to `Date.now()`. Monotonic is correct for
  measuring the wait; wall clock is correct for reporting it. Do not swap the one inside
  `Event.wait()`.
- **[T-15](T-15-approvals-through-control-plane.md) must land first**, or you will be
  adding `expires_at` while `fastapi_app.py:1899` still injects `expiresAt` — two
  competing deadline fields on the same object.
