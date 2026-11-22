# T-66 · Migrate `Approval.id` to the gateway's string `request_id` and delete the translation map

|  |  |
|---|---|
| **Source finding** | CF-16 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** |
| **Wave** | 2 (fast-follow) — **but see §2: the silent-failure half belongs in Wave 1 and is [T-18](T-18-fe-surface-decision-failures.md)** |
| **Depends on** | none. Best sequenced **after** [T-18](T-18-fe-surface-decision-failures.md) so the error surfacing exists before the id model changes under it. |
| **Blocks** | nothing |
| **Effort** | ~3 days |
| **Difficulty** | Medium (mechanical migration; the risk is in the UI components that key on a number) |
| **Files you will touch** | `frontend/src/lib/data/domains/approvals.ts`, `frontend/src/lib/data/types.ts`, `frontend/src/lib/store/store.ts`, `frontend/src/routes/approvals.tsx`, `frontend/src/routes/-index.ApprovalCard.test.tsx`, `frontend/src/lib/data/domains/approvals.test.ts` (new), `docs/bug-bank.md` |
| **See also** | [T-18](T-18-fe-surface-decision-failures.md), [T-01](T-01-approver-selection-dead-branch.md), [T-17](T-17-fe-resolve-approvals-by-request-id.md), [T-63](T-63-frontend-store-slices.md) |

---

## 1. Brief

The gateway identifies a pending approval by a **string** `request_id`. The frontend's
`Approval` type — inherited from the HTML prototype — uses a **number** `id`. Bridging
them is a module-level `Map<string, number>` with a hand-rolled counter and a linear
reverse lookup.

The map has one population point and no persistence, and the code path for a lookup
miss is `if (requestId) { …POST… }` with **no `else`** — the decision POST is silently
skipped while the store has already been mutated to show the decision as applied.

When you are done, `Approval.id` is the gateway's `request_id`, `stableNumericId` and
the map are deleted, and there is no lookup that can miss.

## 2. Why this matters — and exactly how far the claim goes

Two separate defects live here, and they deserve different confidence levels. State them
apart, because conflating them is how a fix targets the wrong thing.

**Defect 1 — the id model (this task).** A translation layer between two id spaces, in
non-persisted module state, with a silent no-op miss path. Even if the miss is
unreachable today, the *shape* is wrong: an approval decision — the single most
consequential action in a governance product — routes through a lookup that is allowed
to fail quietly. Deleting the map removes the failure mode rather than defending it.

**Defect 2 — silent failure (that is [T-18](T-18-fe-surface-decision-failures.md),
Wave 1).** The `catch {}` at `approvals.ts:215-217` swallows every 4xx/5xx, and the
store was already mutated optimistically and is never rolled back. **This half is
reachable today**: any gateway error — a 404 for an approval that already timed out, a
403, a 500 — leaves the UI displaying "allowed" or "declined" while the gateway never
applied the decision. That is a real, present-day integrity gap, and it is why the
error-surfacing work is Wave 1 while this task is Wave 2.

**On the reported "approvals auto-decline shortly after mount" symptom: this is a
hypothesis, and a weak one. Do not repeat it as a diagnosis.** Two things argue against
it, both verified elsewhere in this pack:

- [CORRECTIONS.md](CORRECTIONS.md) §2 — the reported symptom's actual cause was found
  and fixed: **BB-77**, `tickApprovals()` testing `a.expiresAt <= now` where
  `0 <= Date.now()` is always true (fixed at `store.ts:799-812`, locked by
  `store.test.ts:136-159`).
- [CORRECTIONS.md](CORRECTIONS.md) §1 — `RegistryApprover` is unreachable, so
  `GET /approvals` is permanently `{"pending": []}`. Until
  [T-01](T-01-approver-selection-dead-branch.md) lands, `approvals.ts` never receives a
  real approval at all, so no map lookup for a real approval has ever happened.

So: fix this because the id model is wrong and the miss path is undefended, not because
it explains a bug report. Overclaiming here would be worse than underclaiming.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The translation map — `frontend/src/lib/data/domains/approvals.ts:41-64`

```ts
// ============================================================
// 2. Stable numeric-id mapping (gateway uses string request_id)
//    Module-level: survives across re-renders, stays stable per session.
// ============================================================

/** gateway request_id string → stable UI numeric id */
const _idByRequestId = new Map<string, number>();
let _idCounter = 1000; // start above fixture ids (1, 2, …)

function stableNumericId(requestId: string): number {
  const existing = _idByRequestId.get(requestId);
  if (existing !== undefined) return existing;
  const n = ++_idCounter;
  _idByRequestId.set(requestId, n);
  return n;
}

/** Inverse lookup: UI numeric id → gateway request_id (for POST URL) */
function requestIdForUiId(uiId: number): string | undefined {
  for (const [rid, nid] of _idByRequestId) {
    if (nid === uiId) return rid;
  }
  return undefined;
}
```

Module-level, non-persisted, never cleared. The reverse lookup is a linear scan
(`:60-63`).

### 3.2 Exactly one population point — `approvals.ts:113-114`

Inside `adaptApproval`, the list normaliser:

```ts
  return {
    id: stableNumericId(raw.request_id),
```

`grep -n "stableNumericId" frontend/src/lib/data/domains/approvals.ts` returns the
definition at `:50` and this single call at `:114`. **If an approval reaches the store
without passing through `adaptApproval`, its id is not in the map.**

### 3.3 The miss path — `approvals.ts:201-225`, and it is explicit

```ts
async function postDecision(
  uiId: number,
  action: "approve" | "deny" | "allow_once",
  rationale?: string
): Promise<void> {
  if (!USE_MOCKS) {
    const requestId = requestIdForUiId(uiId);
    if (requestId) {
      try {
        await apiSend<GatewayApprovalActionResponse>(
          "POST",
          `/approvals/${requestId}`,
          { action, rationale: rationale ?? "" }
        );
      } catch {
        // Network errors are surfaced centrally via client.ts reconnect callback.
      }
    }
    // If requestId is unknown (e.g. fixture item), skip the POST — the
    // store action has already updated the UI optimistically.
  }
```

Two silent-success paths, both documented in the code itself:

- **`if (requestId)` with no `else`** (`:208`), and the comment at `:219-220` states the
  behaviour outright.
- **`catch {}`** (`:215-217`) — this one is reachable today (§2, defect 2). The comment
  claims errors are "surfaced centrally via client.ts reconnect callback", which handles
  *network* failures; an HTTP 4xx/5xx is not a network failure and reaches no user.

### 3.4 Callers mutate the store first, unconditionally

```ts
export async function approve(id: number): Promise<void> {        // :231-234
  useStore.getState().allowApproval(id);
  await postDecision(id, "allow_once");
}

export async function allowAlways(id: number): Promise<void> {    // :240-243
  useStore.getState().alwaysApproval(id);
  await postDecision(id, "approve");
}

export async function decline(id: number, reason?: string): Promise<void> {   // :249-252
  useStore.getState().declineApproval(id, reason);
  await postDecision(id, "deny", reason);
}

export async function declineAll(): Promise<void> {               // :258-264
  // Snapshot the current ids before the store action clears them
  const ids = useStore.getState().approvals.map((a) => a.id);
  useStore.getState().declineAll();
  // Fire individual denies in parallel; failures are soft (reconnecting flag)
  await Promise.allSettled(ids.map((id) => postDecision(id, "deny")));
}
```

Store mutation first, in every case; no rollback anywhere. `allowApproval` etc. remove
the row from the store (`store.ts:557`: `approvals: s.approvals.filter((x) => x.id !== id)`),
so the card disappears from the Leash screen regardless of what the gateway did.

### 3.5 How reachable is a map miss? — be precise

In **live** mode (`USE_MOCKS === false`), `state.approvals` has exactly two writers:

- `approvals.ts:175` — `(approvalsRes.pending ?? []).map(adaptApproval)` — populates the map.
- `approvals.ts:183` — `hydrate({ approvals: [], auditLog: [] })` — clears it.

and the initial value is `[]` (`store.ts:388`: `approvals: USE_MOCKS ? initApprovals() : []`).
So **every approval in the store in live mode came through `adaptApproval`** and is in
the map. Additionally, `chat.ts:633` and `:646` call `void loadApprovals()` on the
`permission.requested` / `permission.decided` SSE events, and the module comment at
`approvals.ts:323-330` documents this as deliberate:

> *"No synthetic-id entries are created — the registry is the single source of truth,
> which keeps the approve/deny POST (`/approvals/{request_id}`) working."*

In **mock** mode, fixture ids (1, 2, …) are genuinely absent from the map — but
`postDecision` short-circuits at `:206` (`if (!USE_MOCKS)`) and never attempts a POST,
by design.

**Honest conclusion:** the surviving miss path is a **module re-evaluation while the
store survives** — i.e. Vite HMR during development, where `approvals.ts` reloads
(clearing `_idByRequestId`) but the zustand store persists in memory. That is dev-only.
So defect 1 is a **latent** structural defect, not a demonstrated production bug. Fix it
because the shape is indefensible for an approval decision, and say exactly that in the
commit message.

### 3.6 What has to change with the type

`Approval.id` is a `number` in `frontend/src/lib/data/types.ts` and threads through:

- the store's action signatures (`store.ts:259-262`):
  `allowApproval: (id: number, scope?: string) => void`, `alwaysApproval: (id: number) => void`,
  `declineApproval: (id: number, reason?: string) => void`
- the store bodies that filter on it (`store.ts:557`, `:810` — the latter is the BB-77
  `tickApprovals` fix)
- `frontend/src/routes/approvals.tsx` (695 lines) and the one existing route test,
  `frontend/src/routes/-index.ApprovalCard.test.tsx`
- fixture approvals in `frontend/src/lib/data/fixtures.ts` (`initApprovals`)

## 4. Reproduce the failure

Defect 2 (`catch {}`) is reproducible; defect 1 (the map miss) is not, outside HMR — say
so rather than inventing a scenario.

```bash
cd frontend

# 1. One population point, one linear reverse lookup.
grep -n "stableNumericId\|_idByRequestId\|requestIdForUiId" src/lib/data/domains/approvals.ts

# 2. The two silent-success paths, both self-documented.
sed -n '201,225p' src/lib/data/domains/approvals.ts

# 3. Store-first, no rollback.
sed -n '231,264p' src/lib/data/domains/approvals.ts

# 4. Only adaptApproval writes approvals in live mode.
grep -rn "approvals:" src/lib/ src/routes/ --include=*.ts --include=*.tsx | grep -v "\.test\."
```

**You will see now:** (1) the definition at `:50`, the single call at `:114`, and the
`for` loop at `:60-63`; (2) `if (requestId)` with no `else` and a bare `catch {}`;
(3) four exported mutators that all call a store action before the POST; (4) two writers
in `approvals.ts` plus the store's own filters.

**You should see after the fix:** grep (1) returns **nothing** — no map, no counter, no
reverse lookup.

**Defect 2 is reproducible in a unit test** (a mocked `apiSend` that rejects with a 500
→ assert the store still shows the approval as pending, or that an error was surfaced).
That is [T-18](T-18-fe-surface-decision-failures.md)'s test; do not duplicate it here.

## 5. What "fixed" looks like

No decision required — the gateway's id is the id.

1. `Approval.id` becomes `string` in `frontend/src/lib/data/types.ts`, and
   `adaptApproval` (`approvals.ts:102-127`) assigns it directly:

   ```ts
   return {
     id: raw.request_id,
     ...
   };
   ```

2. `stableNumericId` (`:50-56`), `requestIdForUiId` (`:59-64`), `_idByRequestId` (`:47`)
   and `_idCounter` (`:48`) are **deleted**, along with the section header at `:41-44`.

3. `postDecision` loses its lookup entirely:

   ```ts
   async function postDecision(
     requestId: string,
     action: "approve" | "deny" | "allow_once",
     rationale?: string
   ): Promise<void> {
     if (!USE_MOCKS) {
       await apiSend<GatewayApprovalActionResponse>(
         "POST", `/approvals/${requestId}`, { action, rationale: rationale ?? "" }
       );
     }
     invalidate("approvals");
   }
   ```

   Note what is gone: the `if (requestId)` guard has nothing to guard, so the silent-skip
   branch **cannot be written**. That is the structural win.

   **The `try/catch` is deliberately absent here** — error handling is
   [T-18](T-18-fe-surface-decision-failures.md)'s contract. If T-18 has landed, match
   whatever it established. If it has not, leave the rejection propagating to the caller
   rather than re-adding a bare `catch {}`, and note it.

4. Store action signatures take `string`; `store.ts:557` and `:810` filter on strings.
   `===` on strings is correct — no other change needed in those bodies.

5. Fixtures (`initApprovals`) use string ids (e.g. `"fixture-1"`), which also removes
   the `_idCounter = 1000 // start above fixture ids` hack's reason to exist.

6. Observable outcome: no user-visible change. Every decision POST now targets an id the
   UI actually holds.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Change `Approval.id` to `string` in `frontend/src/lib/data/types.ts` and run
   `npm run --prefix frontend typecheck`. **Let the type errors be your work list** —
   this is the one task where `tsc` enumerates the change set for you. Write the list
   down before fixing any of it.
3. Fix `adaptApproval` (`:113-114`) to pass `raw.request_id` through.
4. Delete `:41-64` (the whole mapping section).
5. Rewrite `postDecision` (`:201-225`) per §5, and update the four callers
   (`:231`, `:240`, `:249`, `:258`) to pass ids straight through.
6. Update the store's three action signatures (`store.ts:259-262`) and the two filter
   bodies (`:557`, `:810`).
7. Update fixtures to string ids; check `initApprovals` in
   `frontend/src/lib/data/fixtures.ts`.
8. Update `frontend/src/routes/approvals.tsx` and
   `frontend/src/routes/-index.ApprovalCard.test.tsx`. Check for React `key={a.id}` —
   string keys are fine, but a `key` that was doing arithmetic is not.
9. `grep -rn "\.id\s*[-+*/]" frontend/src/routes/approvals.tsx` — any arithmetic or
   comparison (`<`, `>`, sorting) on the id is now a string operation and must be
   removed or re-based on another field.
10. Run the regression test — it must now pass.
11. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `frontend/src/lib/data/domains/approvals.test.ts` (**new** — this domain has
  no test file today)
- **Test names:** `a decision POSTs to the gateway's request_id` and
  `a decision cannot be silently skipped`
- **It must assert:** the real, observed `apiSend` call — the URL contains the gateway's
  `request_id` string — and that a decision on an approval the module never normalised
  still attempts the POST. Both drive the exported `approve`/`decline` functions, not
  internals.
- **It must FAIL before your fix** with:
  - test 1: `AssertionError: expected apiSend to be called with "/approvals/req-abc-123", but received "/approvals/1001"` — today the store holds `1001` and the URL is built from a reverse lookup.
  - test 2: `AssertionError: expected apiSend to have been called, but it was not called` — the store id is not in the map, so `if (requestId)` is false and the POST is skipped.

```ts
// sketch — frontend/src/lib/data/domains/approvals.test.ts
// Mirror the mocking idiom in src/lib/store/store.test.ts:17-35.
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiSend = vi.fn().mockResolvedValue({ resolved: true });

vi.mock("../client", () => ({
  USE_MOCKS: false,
  apiGet: vi.fn().mockResolvedValue({ pending: [] }),
  apiSend,
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));
vi.mock("../live", () => ({ registerLoader: vi.fn() }));
vi.mock("../cache", () => ({ invalidate: vi.fn() }));

import { useStore } from "../../store/store";
import { approve } from "./approvals";

beforeEach(() => {
  apiSend.mockClear();
});

describe("approval decisions", () => {
  it("a decision POSTs to the gateway's request_id", async () => {
    useStore.getState().hydrate({
      approvals: [{ id: "req-abc-123", request: "send_email", /* …minimal Approval… */ } as never],
    });

    await approve("req-abc-123" as never);

    expect(apiSend).toHaveBeenCalledTimes(1);
    expect(apiSend.mock.calls[0][1]).toBe("/approvals/req-abc-123");
  });

  it("a decision cannot be silently skipped", async () => {
    // An approval that never passed through adaptApproval (SSE-delivered, HMR,
    // or any future writer). Under the old id model its numeric id was absent
    // from the module-level _idByRequestId map, so postDecision's
    // `if (requestId)` guard was false and the POST was skipped with no error —
    // while the store had already been mutated to show the decision as applied.
    useStore.getState().hydrate({
      approvals: [{ id: "req-never-normalised", request: "shell", /* … */ } as never],
    });

    await approve("req-never-normalised" as never);

    expect(apiSend).toHaveBeenCalledTimes(1);
  });
});
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
>
> Getting test 1 to fail *correctly* takes care: before the fix, `Approval.id` is a
> `number`, so seeding the store with a string id will not typecheck. Seed it the way
> the pre-fix code would — run a `loadApprovals()` against a mocked
> `apiGet` returning `{ pending: [{ request_id: "req-abc-123", … }] }`, read the numeric
> id back out of the store, and call `approve(thatNumber)`. Then assert the URL. That
> version fails on the *URL*, which is the real contract, and it survives the type
> change.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and both cases failed before the fix.
- [ ] `grep -n "stableNumericId\|_idByRequestId\|_idCounter\|requestIdForUiId" frontend/src/lib/data/domains/approvals.ts` returns **nothing**.
- [ ] `Approval.id` is `string` in `frontend/src/lib/data/types.ts`, and the three store action signatures match.
- [ ] `postDecision` has no `if (requestId)` guard — the branch is structurally impossible.
- [ ] No bare `catch {}` was re-added around the decision POST (see §5.3 and [T-18](T-18-fe-surface-decision-failures.md)).
- [ ] `frontend/src/routes/-index.ApprovalCard.test.tsx` passes with string ids.
- [ ] No arithmetic or ordering comparison is performed on `Approval.id` anywhere.
- [ ] `npm run --prefix frontend typecheck`, `test` and `build` are green.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not build the error-surfacing UI.** This is the drift, and it is a strong pull:
  you will be standing inside `postDecision` looking at a bare `catch {}` that is
  demonstrably worse than the thing you came to fix. It is
  [T-18](T-18-fe-surface-decision-failures.md), it is Wave 1, and it may already be
  done. Doing both here produces a diff where a type migration and an error-handling
  redesign are indistinguishable. Delete the map; leave the error contract to T-18.
- **Do not add rollback of the optimistic store mutation.** Same reason — that is the
  decision T-18 makes (roll back vs. never-optimistic vs. explicit pending state).
  Whatever it chooses, this task must not pre-empt it.
- **Do not touch `approveFirstMatching` / `denyFirstMatching`** (`:286-321`). Their
  fuzzy text matching is broken for a *different* reason — the field-name mismatch in
  `chat.ts:617-624` documented in [CORRECTIONS.md](CORRECTIONS.md) §3 — and fixing it is
  [T-17](T-17-fe-resolve-approvals-by-request-id.md). They will keep compiling after
  your change because they route through `approve`/`decline`.
- **Do not "fix" the `expiresAt: 0` hardcode** at `:124`. The comment at `:107-112`
  explains it correctly and [CORRECTIONS.md](CORRECTIONS.md) §2 confirms the reasoning.
  Changing it re-opens BB-77.
- **Do not split the approvals slice out of the store** — that is
  [T-63](T-63-frontend-store-slices.md). If both are in flight, coordinate: you are both
  editing `store.ts:259-262` and `:557`.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). `-index.ApprovalCard.test.tsx` will need its fixture ids changed from numbers to strings; that is a contract change, not a weakening — say so in the commit message.
- Do not add a dependency without asking.

## 10. Verify

```bash
npm run --prefix frontend typecheck      # your work list — run it first, after step 2
npm run --prefix frontend test
npm run --prefix frontend build
uv run python scripts/preflight.py       # before you call it done
```

Run the **full** gate. Report the **actual** counts.

**End-to-end verification is currently impossible and you should not pretend
otherwise.** Per [CORRECTIONS.md](CORRECTIONS.md) §1, `GET /approvals` returns
`{"pending": []}` on every build until [T-01](T-01-approver-selection-dead-branch.md)
lands, so there is no real approval to decide. If T-01 has landed, do the manual check:
trigger a gated action, confirm the card appears on the Leash screen, click Allow, and
verify in the gateway log that `POST /approvals/{request_id}` arrived with the same id
the card was rendered from.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Approval decisions routed through a numeric-id translation map whose miss path silently skipped the POST

- **Symptom:** Latent, not confirmed in production. An approval whose id was absent from a module-level translation map would have its decision POST skipped entirely — `if (requestId) { …POST… }` with no `else` — while the store had already been mutated to show the decision as applied, so the card vanished from the Leash screen and the gateway never received the decision. (Reachable in practice only via Vite HMR clearing the map while the store survived; in live mode every approval in the store had passed through the normaliser that populates it.)
- **Root cause:** `Approval.id` was a `number` inherited from the HTML prototype while the gateway identifies approvals by a string `request_id`. `frontend/src/lib/data/domains/approvals.ts` bridged them with `_idByRequestId = new Map<string, number>()` (`:47`), a counter starting at 1000 to clear the fixture ids, and a linear reverse lookup `requestIdForUiId` (`:59-64`). The map had exactly one population point — `adaptApproval` at `:114` — and was module-level and non-persisted.
- **Fix:** `Approval.id` is the gateway's `request_id` string. `stableNumericId`, `_idByRequestId`, `_idCounter` and `requestIdForUiId` deleted; `postDecision` takes the request id directly, so the silent-skip branch is structurally impossible to write.
- **Avoid:** never translate between two id spaces for a consequential action. If a lookup can miss, the miss must be an error — and if the id you need is the one the server gave you, keep it. Prototype-derived types are not a contract; the server's is.
- **Locked by:** `frontend/src/lib/data/domains/approvals.test.ts` — `a decision POSTs to the gateway's request_id`
```

## 12. Known traps

- **`tsc` is your work list, but it is not complete.** Type errors will find every
  `number`-typed usage; they will **not** find a React `key={a.id}` that still works, a
  `sort((a, b) => a.id - b.id)` that now returns `NaN`, or a `Number(a.id)` coercion.
  Run the grep in §6 step 9 as well.
- **Seeding the store to make the test fail correctly is the hard part.** Before the
  fix, string ids will not typecheck. Drive `loadApprovals()` with a mocked `apiGet`
  instead of hand-seeding — see the §7 note.
- **`store.ts:810` is the BB-77 fix** (`tickApprovals`, `:799-812`), locked by
  `store.test.ts:136-159`. You are changing the type of the field it filters on. Those
  tests must keep passing; if one goes red, you have changed `tickApprovals`' semantics,
  which is out of scope.
- **`declineAll` snapshots ids before clearing** (`:259-261`). With string ids the
  snapshot still works, but confirm the `Promise.allSettled` at `:263` still receives
  the right count — `allSettled` swallows rejections, which after T-18 may no longer be
  the desired behaviour.
- **Mock mode short-circuits before the POST** (`:206`, `if (!USE_MOCKS)`). A test that
  forgets to mock `USE_MOCKS: false` will pass without ever calling `apiSend`, proving
  nothing. The mock block in §7 sets it explicitly — keep it.
- **`chat.ts:633`/`:646` call `loadApprovals()` from the SSE handler.** After your
  change those still work unmodified, but `chat.ts` is
  [T-65](T-65-chat-ts-kernel-extraction.md)'s subject — coordinate if both are in flight.
- **BB-4:** this task does not change a gateway route, so the OpenAPI contract step
  should be unaffected — but `check:api` does a `git diff --exit-code` on
  `frontend/src/lib/data/schema.d.ts`, so verify rather than assume.
