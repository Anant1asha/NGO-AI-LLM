# T-17 · Resolve in-context approvals by `request_id` — and delete the matcher that always picks the wrong one

|  |  |
|---|---|
| **Source finding** | CF-4(b) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). **The review's claim is REFUTED and the real defect is worse** — [CORRECTIONS.md](CORRECTIONS.md) §3 |
| **Severity** | **P1** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | [T-01](T-01-approver-selection-dead-branch.md) — *unobservable until it lands; verify them together* |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium |
| **Files you will touch** | `frontend/src/lib/data/types.ts`, `frontend/src/lib/data/domains/chat.ts`, `frontend/src/lib/data/domains/approvals.ts`, `frontend/src/lib/store/store.ts`, `frontend/src/lib/data/domains/approvals.test.ts` (**new**), `docs/bug-bank.md` |

---

## 1. Brief

> **Read this first, or you will fix the wrong thing.**
> The audit says the `permission.requested` SSE payload "carries no `request_id`". **That
> is false — the id has always been on the wire, and no backend change is needed.**

The real defect is a total field-name mismatch on the frontend. `chat.ts` reads
`payload.request`, `payload.action` and `payload.why` — three keys the backend has never
sent — so the in-context leash is permanently populated with the literal fallback
string `"Permission requested"`. That fallback is then used as a fuzzy-match needle to
decide *which* pending approval the user just approved. It matches nothing, so the
matcher falls through to `approvals[0]` **unconditionally**.

When you are done, the leash carries the real `request_id` from the event, decisions
resolve by exact id, and both `*FirstMatching` functions are deleted.

## 2. Why this matters

The review described this as "if multiple approvals are pending the first one wins."
That is optimistic. The needle never matches, so **the first one wins *always* — even
when it is the wrong one, and even when only one approval is pending** (in which case
it is right by accident, not by design). Combined with
[T-01](T-01-approver-selection-dead-branch.md), the failure mode a user experiences is:
click "Allow" on the request to send an email, and Hachi approves whatever unrelated
gated action happens to be first in the list. In a product whose pitch is *verifiable
governance*, resolving the wrong approval is worse than resolving none.

There is a second, quieter cost: the leash prompt shows the user
`"Permission requested"` where it should show `send_email → priya@studio.co`. The user
is asked to consent to something the UI cannot name.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The backend DOES send `request_id` — three emitters, all agreeing

`core/approvals.py:421-431` (`RegistryApprover._build_and_park`):

```python
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
```

`core/approvals.py:334-344` (`HandlerApprover.require`) and
`core/permissions.py:858-868` (`InteractivePermissionGate._request_decision`) emit the
identical six keys.

### 3.2 SSE serialises the payload verbatim — `gateway/fastapi_app.py:1173-1179`

```python
                        for event in events:
                            cursor = event["sequence"]
                            yield (
                                f"id: {event['sequence']}\n"
                                f"event: {event['event_type']}\n"
                                f"data: {json.dumps(event)}\n\n"
                            )
```

No field filtering, no renaming. **`request_id`, `tool`, `target`, `reason` and
`policy_summary` all reach the browser today.**

### 3.3 The frontend reads three keys that do not exist — `frontend/src/lib/data/domains/chat.ts:617-624`, inside `handleSseMessage`

```ts
    case "permission.requested": {
      const request = typeof payload.request === "string" ? payload.request : "Permission requested";
      const action = typeof payload.action === "string" ? payload.action : "";
      const why = typeof payload.why === "string" ? payload.why : "";
      const msgId = _hachiMsgId ?? 0;
      store.hydrate({
        inContext: { msgId, request, action, why },
      });
```

`payload.request` / `.action` / `.why` are **never** on the wire. The wire carries
`tool` / `target` / `reason`. Result, on every single approval:

- `request === "Permission requested"` (the fallback)
- `action === ""`
- `why === ""`
- `request_id` — **read by nobody, discarded**

The same three values are copied onto the run view at `chat.ts:636`:

```ts
        store.hydrate({ runLeash: { request, action, why }, runStreaming: false });
```

### 3.4 The matcher degenerates to `approvals[0]` — `frontend/src/lib/data/domains/approvals.ts:286-300`

```ts
export async function approveFirstMatching(requestText?: string): Promise<void> {
  const approvals = useStore.getState().approvals;
  if (approvals.length === 0) return;

  let target = approvals[0];
  if (requestText) {
    const needle = requestText.toLowerCase();
    const matched = approvals.find(
      (a) => a.request.toLowerCase().includes(needle) || needle.includes(a.request.toLowerCase())
    );
    if (matched) target = matched;
  }

  await approve(target.id);
}
```

`denyFirstMatching` at `:307-321` is byte-for-byte identical except for the final
`await decline(target.id)`.

Why it can never match: `a.request` is built by `adaptApproval`
(`approvals.ts:116`) as

```ts
    request: `${tool || operation}`,
```

i.e. `"send_email"`. The needle is `"permission requested"`. Neither string contains the
other. **`matched` is always `undefined`; `target` is always `approvals[0]`.**

The module's own comment block (`approvals.ts:266-276`) states the assumption that is
wrong:

```ts
//    "permission.requested" event. That event carries no request_id
//    (see InContextLeash in types.ts), so we can only match by
//    comparing the `request` text against pending approval `request`
//    fields. This is a best-effort match: if multiple approvals are
//    pending the first one wins.
```

Delete that comment along with the functions.

### 3.5 The type has no id field — `frontend/src/lib/data/types.ts:355-361`

```ts
// ----- in-context leash -----
export interface InContextLeash {
  msgId: number;
  request: string;
  action: string;
  why: string;
}
```

Referenced at `frontend/src/lib/store/store.ts:198` (`inContext: InContextLeash | null`).
The run-view twin is an inline type at `frontend/src/lib/store/store.ts:211`:

```ts
  runLeash: { request: string; action: string; why: string } | null;
```

### 3.6 The call chain into the matcher

`frontend/src/lib/data/domains/chat.ts:1028-1057`:

```ts
export async function allowLeashLive(): Promise<void> {
  const store = useStore.getState();
  const ic = store.inContext;
  if (!ic) return;
  // Clear the leash immediately (optimistic UI update)
  store.hydrate({ inContext: null });
  // Best-effort: POST the decision to the gateway so the backend unblocks.
  // We match by request text since InContextLeash carries no request_id.
  // Errors are soft — the SSE stream continues regardless.
  try {
    await approveFirstMatching(ic.request);
  } catch {
    // Gateway POST failed — SSE stream continues, decision is best-effort
  }
}

export async function denyLeashLive(): Promise<void> {
  const store = useStore.getState();
  const ic = store.inContext;
  store.hydrate({ inContext: null });
  // Best-effort: POST the deny decision to the gateway.
  try {
    await denyFirstMatching(ic?.request);
  } catch {
    // Gateway POST failed — proceed with local stream abort
  }
  // Stop streaming — the user declined the permission.
  stopStreamingLive();
  store.hydrate({ streaming: false });
}
```

Six store actions reach these two functions — all in
`frontend/src/lib/store/store.ts`, each on its `dataMode === "live"` branch:

| Action | Action starts | Live branch | Calls |
|---|---|---|---|
| `icAllow` | `:1347` | `:1349` | `allowLeashLive()` at `:1350` |
| `icAlwaysAllow` | `:1389` | `:1395` | `allowLeashLive()` at `:1404` |
| `icDeny` | `:1419` | `:1421` | `denyLeashLive()` at `:1422` |
| `runAllowLeash` | `:1596` | `:1598` | `allowLeashLive()` at `:1604` |
| `runAlwaysAllow` | `:1620` | `:1622` | `allowLeashLive()` at `:1636` / `:1650` |
| `runDenyLeash` | `:1668` | `:1670` | `denyLeashLive()` at `:1685` |

### 3.7 There is NO test file for this — verified

```
frontend/src/lib/data/domains/
  approvals.ts          ← 12,888 bytes, ZERO tests
  chat.test.ts          ← exists
  config.test.ts        ← exists
  integrations.test.ts  ← exists
  …
```

**`frontend/src/lib/data/domains/approvals.test.ts` does not exist.** The matcher, the
adapters, the numeric-id map and every mutation wrapper in that file are wholly
untested. Creating that file is part of this task (§7).

## 4. Reproduce the failure

**Not reproducible against a live gateway until
[T-01](T-01-approver-selection-dead-branch.md) lands** — with `PolicyApprover` selected
there is never a `permission.requested` event and never a pending approval. Be honest
about that; do not write "verified in the browser" until T-01 is in.

What is mechanically checkable right now:

```bash
# 1. The keys the frontend reads. Expect: payload.request / .action / .why
rg -n "payload\.(request|action|why)" frontend/src/lib/data/domains/chat.ts

# 2. The keys the backend sends. Expect: request_id / operation / tool / target /
#    reason / policy_summary — and NONE of request / action / why.
rg -n -A 10 '"permission.requested"' src/hachi/core/approvals.py src/hachi/core/permissions.py

# 3. request_id is discarded. Expect: NO hit inside the permission.requested case.
rg -n "request_id" frontend/src/lib/data/domains/chat.ts

# 4. No test file exists. Expect: "No such file".
ls frontend/src/lib/data/domains/approvals.test.ts
```

**You will see now:** the two key sets in (1) and (2) are **disjoint**; (3) is silent;
(4) errors.

**You should see after the fix:** (1) reads `payload.tool` / `.target` / `.reason` /
`.request_id`; (3) shows the id being read and stored; (4) lists a real test file.

**End-to-end check, after T-01 lands** — with the gateway running at `guided` tier,
trigger two gated actions so two approvals are pending, then approve the *second* one
from the in-context leash and watch the network tab: the `POST /approvals/{id}` must
carry the id of the approval you clicked, not of `approvals[0]`.

## 5. What "fixed" looks like

No decision required. **No backend change.**

1. `InContextLeash` carries the id (`types.ts:356-361`):

   ```ts
   export interface InContextLeash {
     msgId: number;
     /** Gateway `request_id` from the permission.requested event. Empty when unknown. */
     requestId: string;
     request: string;
     action: string;
     why: string;
   }
   ```

   and the inline `runLeash` type (`store.ts:211`) gains `requestId: string` to match.

2. `chat.ts:617-624` reads the fields the backend actually sends:

   ```ts
   case "permission.requested": {
     const requestId = typeof payload.request_id === "string" ? payload.request_id : "";
     const tool = typeof payload.tool === "string" ? payload.tool : "";
     const target = typeof payload.target === "string" ? payload.target : "";
     const reason = typeof payload.reason === "string" ? payload.reason : "";
     const request = tool || "Permission requested";
     const action = target ? `${tool} → ${target}` : tool;
     const why = reason;
     ...
     store.hydrate({ inContext: { msgId, requestId, request, action, why } });
   ```

   Note `action` is composed the same way `adaptApproval` composes it
   (`approvals.ts:118`: `` `${tool || operation} → ${target}` ``) so the two surfaces
   agree. Keep the `notifyApprovalPending(request)` call at `:626` and the
   `void loadApprovals()` call at `:633` exactly as they are.
   The run-view hydrate at `:636` also passes `requestId`.

3. `approvals.ts` gains an **exact-id** resolver and loses both fuzzy ones:

   ```ts
   /** Resolve a pending approval by its gateway request_id. Returns false if unknown. */
   export async function approveByRequestId(requestId: string): Promise<boolean>
   export async function declineByRequestId(requestId: string, reason?: string): Promise<boolean>
   ```

   Implementation note: the module already keeps the `request_id → numeric id` map
   (`_idByRequestId`, `approvals.ts:47-56`) and `stableNumericId` is what populates it
   during `adaptApproval`. Reuse it — `stableNumericId(requestId)` is idempotent, so
   calling it for an id the loader has already seen returns the same numeric id, and for
   an unseen id it mints one. **Prefer looking the id up rather than minting**, so an
   unknown id can be reported as such (that honesty matters to
   [T-18](T-18-fe-surface-decision-failures.md)).

4. `approveFirstMatching` and `denyFirstMatching` (`approvals.ts:286-321`) are
   **deleted**, along with the section-8 comment block at `:266-276` that documents the
   wrong assumption.

5. `allowLeashLive` / `denyLeashLive` (`chat.ts:1028-1057`) call the new functions with
   `ic.requestId`, and their "we match by request text" comments are corrected.

6. The six store actions in §3.6 are unchanged in shape — they still call
   `allowLeashLive()` / `denyLeashLive()`. **You do not need to touch `store.ts` beyond
   the `runLeash` type at `:211`** unless `runAlwaysAllow` / `icAlwaysAllow` need the id
   for their `/permissions/always-allow` POST (`store.ts:1399-1402`, `:1627-1630`) —
   check whether that endpoint wants it; if not, leave them alone.

## 6. Steps

1. Create `frontend/src/lib/data/domains/approvals.test.ts` with the tests from §7 and
   watch them **fail**.
2. Add `requestId: string` to `InContextLeash` (`types.ts:356-361`) and to the inline
   `runLeash` type (`store.ts:211`). `tsc` will now point at every construction site —
   follow the errors.
3. Rewrite the `permission.requested` case in `chat.ts:617-640` per §5.2.
4. Add `approveByRequestId` / `declineByRequestId` to `approvals.ts`.
5. Point `allowLeashLive` / `denyLeashLive` (`chat.ts:1038`, `:1050`) at them; fix the
   surrounding comments.
6. Delete `approveFirstMatching`, `denyFirstMatching` and the section-8 comment block.
   Confirm with `rg -n "FirstMatching" frontend/src` that nothing else referenced them.
7. Fix any remaining `tsc` errors (mock-mode `inContext` constructions in `store.ts`
   — e.g. `:1271-1277` — will need `requestId: ""`).
8. `npm run --prefix frontend typecheck && npm run --prefix frontend test`, then the
   full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Runner is **vitest** (`npm run --prefix frontend test` → `vitest run`).

- **File:** `frontend/src/lib/data/domains/approvals.test.ts` (**new — it does not
  exist today**)
- **Test names:**
  `resolves the approval the user clicked, not approvals[0]` and
  `maps the real SSE field names onto the in-context leash`
- **They must assert:** the real POST target — that with **two** pending approvals, a
  decision on the second one issues `POST /approvals/<second request_id>`. Assert on the
  URL passed to a mocked `apiSend`, not on store state (store state would pass even with
  the bug because the wrong approval is still *removed* optimistically).
- **They must FAIL before your fix** with:
  `AssertionError: expected "POST", "/approvals/req-A", … but got "/approvals/req-B"` —
  i.e. `approvals[0]` was resolved instead of the one clicked. And for the second test:
  `AssertionError: expected 'Permission requested' to be 'send_email'`.

```ts
// sketch — adapt to the repo's existing patterns (see store.test.ts:17-37 for the
// canonical vi.mock block for ../client, ../sse and ../../notifications)
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiSend = vi.fn().mockResolvedValue({ resolved: true });
vi.mock("../client", () => ({
  USE_MOCKS: false,
  apiGet: vi.fn().mockResolvedValue({ pending: [] }),
  apiSend,
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  ApiError: class ApiError extends Error {},
}));

import { useStore } from "../../store/store";

describe("in-context approval resolution (CF-4b)", () => {
  beforeEach(() => {
    apiSend.mockClear();
    // Hydrate TWO pending approvals via the real loader path so the
    // request_id -> numeric id map is populated the way production populates it.
    // (import { loadApprovals } and drive apiGet, OR call the exported adapter.)
  });

  it("resolves the approval the user clicked, not approvals[0]", async () => {
    // ... seed pending: [{request_id: "req-A", tool: "write_file", ...},
    //                    {request_id: "req-B", tool: "send_email",  ...}]
    // ... set inContext to the SECOND one (requestId: "req-B")
    await allowLeashLive();
    expect(apiSend).toHaveBeenCalledWith("POST", "/approvals/req-B", expect.anything());
  });
});
```

For the second test, `handleSseMessage` (`chat.ts:559`) is **not exported**. Two honest
options — pick one and say which in the commit message:

- **Export it.** A test-visibility-only export, no behaviour change. Recommended: it is
  the seam under test and the file already exports six other internals for testing
  (`buildTurnKey`, `reconstructMessagesFromEvents`, …).
- **Test through the store.** Drive the real SSE path and assert on
  `useStore.getState().inContext`. Higher fidelity, more mocking.

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The most likely cause: you seeded only ONE pending approval, in which case
> `approvals[0]` is right by accident.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist in a **new** `approvals.test.ts`, and failed before the fix.
- [ ] `rg -n "FirstMatching" frontend/src` returns **nothing**.
- [ ] `rg -n "payload\.(request|action|why)\b" frontend/src/lib/data/domains/chat.ts` returns **nothing**.
- [ ] `InContextLeash.requestId` exists and is populated from `payload.request_id`.
- [ ] With two approvals pending, approving the second issues `POST /approvals/<second id>`.
- [ ] The leash prompt shows the real tool/target, not `"Permission requested"`.
- [ ] **No file under `src/hachi/` was modified.** This task is frontend-only.
- [ ] `npm run --prefix frontend typecheck` is clean.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change the backend.** The `request_id` is already on the wire (§3.1/§3.2).
  If you find yourself editing `core/approvals.py` or `fastapi_app.py`, you have
  followed the review instead of [CORRECTIONS.md](CORRECTIONS.md) §3 — stop.
- **Do not migrate `Approval.id` from `number` to `string`.** The numeric-id map
  (`approvals.ts:42-64`) exists because the prototype's `Approval.id` is a number
  (`types.ts:22`). Deleting that translation layer is the right long-term move and is
  part of the Wave-2 CF-16 store work — it touches every approval component and would
  swamp this change. Resolve *through* the map; leave the map.
- **Do not fix the swallowed POST failure** in `postDecision`
  (`approvals.ts:201-225`). That is [T-18](T-18-fe-surface-decision-failures.md) and it
  edits the same function — coordinate, but keep the diffs separable.
- **Do not remove the client-fabricated audit row.** That is
  [T-19](T-19-fe-stop-fabricating-audit-rows.md).
- **Do not add a countdown** now that ids work. Deadlines are
  [T-16](T-16-approval-real-deadline.md), and re-enabling `tickApprovals` is the BB-77
  code path.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
npm run --prefix frontend typecheck
npm run --prefix frontend test               # vitest
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.
Say explicitly whether you verified end-to-end against a live gateway, and if not, say
that it is blocked on [T-01](T-01-approver-selection-dead-branch.md).

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — In-context approvals always resolved `approvals[0]`; the SSE field names never matched

- **Symptom:** Clicking Allow/Deny on an in-context leash prompt resolved the wrong pending approval whenever more than one was pending, and the prompt itself always read "Permission requested" instead of naming the tool and target.
- **Root cause:** Two layered defects. (1) `chat.ts` handled `permission.requested` by reading `payload.request` / `.action` / `.why` — three keys the backend has never emitted; the wire carries `request_id` / `tool` / `target` / `reason`. All three fell back to their defaults, and `request_id` was discarded entirely. (2) Because `InContextLeash` had no id, `allowLeashLive`/`denyLeashLive` resolved via `approveFirstMatching(ic.request)`, a fuzzy text match whose needle was therefore always the literal `"Permission requested"`. It matched nothing, so the `let target = approvals[0]` fallback fired unconditionally — the first pending approval was resolved every time, right only by coincidence when exactly one was pending.
- **Fix:** Added `requestId` to `InContextLeash` and the `runLeash` type; `chat.ts` now reads `request_id` / `tool` / `target` / `reason`; added `approveByRequestId` / `declineByRequestId` resolving through the existing `request_id → numeric id` map; deleted `approveFirstMatching` and `denyFirstMatching`. Backend unchanged.
- **Avoid:** never resolve a server-side record by fuzzy-matching its display text — carry the server's identifier. And when adapting an event payload, check the emitter's actual keys; a `typeof x === "string" ? x : fallback` guard silently converts a wrong field name into a plausible default.
- **Locked by:** `frontend/src/lib/data/domains/approvals.test.ts` — "resolves the approval the user clicked, not approvals[0]"
```

## 12. Known traps

- **This is unobservable end-to-end until
  [T-01](T-01-approver-selection-dead-branch.md) lands.** Nothing emits
  `permission.requested` in a default build, so a manual browser check will show you
  nothing either way. Verify with the unit tests, and re-verify together with T-01.
- **`store.test.ts:17-37` is the canonical mock block** for `../data/client`,
  `../data/sse` and `../notifications`. Copy it rather than inventing your own — the
  store imports all three at module scope and the test will explode on import otherwise.
- **`approvals.ts` self-registers a loader on import** (`registerLoader("approvals",
  loadApprovals)` at `:193`). Importing it in a test triggers that side effect. Harmless,
  but if you see a stray loader firing, that is why.
- **`_idByRequestId` and `_idCounter` are module-level and persist across tests in the
  same file** (`approvals.ts:47-48`). Two tests seeding the same `request_id` share a
  numeric id; two tests seeding different ids get monotonically increasing numbers.
  Do not assert on specific numeric ids.
- **One existing test may legitimately need amending.**
  `frontend/src/lib/store/store.test.ts:84` does
  `useStore.getState().hydrate({ runLeash: { request: "x", action: "y", why: "z" } })`.
  Adding `requestId` to the `runLeash` type makes that object incomplete and `tsc` will
  flag it. Adding `requestId: ""` is **a type conformance update, not a weakening**
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2) — say so in the commit message.
- **Do not "fix" `notifyApprovalPending(request)`** (`chat.ts:626`) into something
  fancier. It will start showing the real tool name for free once §5.2 lands; that is
  the whole change.
- **BB-4 does not apply** — no gateway route changes, so no OpenAPI regeneration.
