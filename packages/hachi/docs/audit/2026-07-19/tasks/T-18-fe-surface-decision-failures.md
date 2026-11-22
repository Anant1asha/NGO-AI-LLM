# T-18 · Stop the approval decision path from swallowing failure

|  |  |
|---|---|
| **Source finding** | CF-4(c) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none (independent) |
| **Blocks** | nothing |
| **Effort** | ~half a day |
| **Difficulty** | Medium (one design decision in §5) |
| **Files you will touch** | `frontend/src/lib/data/domains/approvals.ts`, `frontend/src/lib/data/domains/approvals.test.ts` (**new**, shared with [T-17](T-17-fe-resolve-approvals-by-request-id.md)), `docs/bug-bank.md` |

---

## 1. Brief

`postDecision` in the approvals domain has **two independent silent-failure paths**: a
bare `catch {}` that swallows a failed POST, and an `if (requestId)` guard that skips
the POST entirely when the id cannot be mapped. Its callers fire the optimistic store
mutation *before* awaiting, so the approval card leaves the screen either way. A 404,
a 500, and a full success are indistinguishable to the user — **while the gateway is
still blocked, waiting for a decision that never arrived.**

When you are done, a failed or skipped decision is visible to the user and the approval
does not silently vanish.

## 2. Why this matters

This is the failure mode with the worst shape in the whole approvals chain: the user
performs a governance action, the UI confirms it, and nothing happened. The agent's tool
call stays parked in `PendingApprovalRegistry` until the 180-second timeout
(`src/hachi/core/approvals.py:396`) auto-denies it with rationale
`"approval timed out"` — so the user's *approve* silently becomes a *deny*, three
minutes later, with no explanation on screen. The inverse is just as bad: a failed
*deny* leaves a destructive action free to be approved by the timeout path of some other
surface.

The repo already knows the right answer and applies it two files away — see §3.4.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Two silent paths in one function — `frontend/src/lib/data/domains/approvals.ts:201-225`

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
  // Mark the approvals domain stale so a revisit to /approvals refetches
  // the updated pending list rather than showing the now-stale snapshot.
  invalidate("approvals");
}
```

- **Path 1 — `catch {}` at `:215-217`.** The comment claims failures are "surfaced
  centrally via client.ts reconnect callback". That callback only covers *network*
  failures (`isNetworkError`). A **404** (unknown `request_id` — see
  `src/hachi/gateway/fastapi_app.py:1934-1935`) or a **422** (invalid action,
  `:1927-1931`) or a **500** is an `ApiError`, not a network error, and is swallowed
  entirely.
- **Path 2 — `if (requestId)` at `:208`.** When the numeric→string id lookup misses,
  the POST is **never issued** and the function returns as if it succeeded. The comment
  rationalises it as a fixture case; in live mode it is a real, unreported skip.
- Both paths return `Promise<void>`. **The caller has no way to know which happened.**

### 3.2 The mutation fires before the await — `approvals.ts:227-264`

```ts
export async function approve(id: number): Promise<void> {
  useStore.getState().allowApproval(id);
  await postDecision(id, "allow_once");
}

export async function allowAlways(id: number): Promise<void> {
  useStore.getState().alwaysApproval(id);
  await postDecision(id, "approve");
}

export async function decline(id: number, reason?: string): Promise<void> {
  useStore.getState().declineApproval(id, reason);
  await postDecision(id, "deny", reason);
}

export async function declineAll(): Promise<void> {
  // Snapshot the current ids before the store action clears them
  const ids = useStore.getState().approvals.map((a) => a.id);
  useStore.getState().declineAll();
  // Fire individual denies in parallel; failures are soft (reconnecting flag)
  await Promise.allSettled(ids.map((id) => postDecision(id, "deny")));
}
```

Each store action removes the approval from `state.approvals` and shows a success toast
(`frontend/src/lib/store/store.ts:780-798`):

```ts
        allowApproval: (id) => {
          resolveApproval(id, "allowed once", "var(--hachi-success)");
          toast("On it — Hachi is working", "working");
        },
```

So the card disappears and the user is told it worked — **before the network call is
even attempted**, and regardless of its outcome.

### 3.3 The only consumer — `frontend/src/routes/approvals.tsx:19-25`

```ts
import {
  loadApprovals,
  approve,
  allowAlways,
  decline,
  declineAll as declineAllMutation,
} from "../lib/data/domains/approvals";
```

Plus the in-context path, which reaches `approve`/`decline` indirectly through
`approveFirstMatching` / `denyFirstMatching` (`approvals.ts:286-321`) — see
[T-17](T-17-fe-resolve-approvals-by-request-id.md), which replaces those.

### 3.4 The in-repo precedent for doing this right — `frontend/src/lib/store/store.ts:1395-1412`

```ts
          if (get().dataMode === "live") {
            // Persist always-allow rule to the gateway; surface failure honestly.
            void (async () => {
              try {
                await apiSend("POST", `/sessions/current/permissions/always-allow`, {
                  request: _ic.request,
                  action: _ic.action,
                });
                // On success, let the live stream continue as "allow once" would
                void allowLeashLive();
                toast("Always allowed — Hachi won't ask again for this", "success");
              } catch {
                // Endpoint returned an error — tell the user, don't silently proceed
                toast("Could not save always-allow rule — please try again", "blocked");
              }
            })();
            return;
          }
```

**Await first, mutate on success, toast `"blocked"` on failure.** The same shape exists
at `store.ts:1622-1642` (`runAlwaysAllow`). This is the pattern to copy — it is already
the house style, `postDecision` just predates it. The same rule was written down as
**BB-78**: *"never wire a destructive UI action to a bare store mutation; always mirror
the add-path pattern (Live function → gateway → store-on-2xx)."*

### 3.5 The toast API you will use — `frontend/src/lib/store/store.ts:240`

```ts
  showToast: (message: string, tone?: Toast["tone"], action?: Toast["action"]) => void;
```

with `tone` from `frontend/src/lib/data/types.ts:300`:

```ts
  tone?: "success" | "working" | "blocked" | "info";
```

`"blocked"` is the failure tone.

## 4. Reproduce the failure

Reproducible in the browser without any backend change, because you can force the 404
path directly. It does **not** require [T-01](T-01-approver-selection-dead-branch.md) —
a fixture-seeded approval is enough to exercise the id-miss path.

```bash
# 1. Confirm both silent paths exist.
rg -n -A 24 "async function postDecision" frontend/src/lib/data/domains/approvals.ts

# 2. Confirm the store mutation runs before the await.
rg -n -B 1 -A 3 "^export async function (approve|allowAlways|decline)\b" frontend/src/lib/data/domains/approvals.ts
```

**Manual reproduction** (dev server + gateway running):

1. Open the Leash screen with at least one approval visible.
2. In devtools, block or fail the request: Network → right-click →
   *Block request URL* on `**/approvals/**` (or stop the gateway process).
3. Click **Allow**.

**You will see now:** the card disappears, the toast says *"On it — Hachi is working"*,
and the network panel shows the POST failing (or never firing). Nothing on screen
indicates a problem. The agent, meanwhile, is still blocked.

**You should see after the fix:** the card stays (or returns), and a `"blocked"`-tone
toast says the decision could not be delivered.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — optimistic-with-rollback, or non-optimistic?
>
> **(a) Non-optimistic: await the POST, mutate the store only on success — RECOMMENDED.**
> *For:* it is already the house style (§3.4, and BB-78 states it as a rule); there is
> exactly one state transition so no rollback logic can drift; a failed decision is
> impossible to mistake for a success. *Against:* the card sits for one round-trip
> (typically <100 ms on loopback — this is a local-first product, the latency argument
> the review raises is weak here).
>
> **(b) Optimistic with rollback: mutate, POST, and re-insert the approval on failure.**
> *For:* instant feedback. *Against:* `resolveApproval` (`store.ts:526-563`) also pushes
> a `HistoryItem` **and** an `AuditEntry` — a correct rollback must un-push both, and
> [T-19](T-19-fe-stop-fabricating-audit-rows.md) is about to delete the audit push, so
> the two tasks would collide. Genuinely harder to get right than it looks.
>
> **Recommendation: (a).** It is smaller, matches the existing pattern, and cannot
> half-roll-back.

Target state:

1. `postDecision` **reports its outcome** instead of returning `void`:

   ```ts
   type DecisionOutcome = "ok" | "unknown-id" | "failed";

   async function postDecision(
     uiId: number,
     action: "approve" | "deny" | "allow_once",
     rationale?: string
   ): Promise<DecisionOutcome>
   ```

   - mocks → `"ok"` (unchanged behaviour for `USE_MOCKS`)
   - id lookup miss → `"unknown-id"` (**no longer silent**)
   - `apiSend` throws → `"failed"`
   - 2xx → `"ok"`

   Keep `invalidate("approvals")` firing on every path — a stale refetch is correct
   after a failure too.

2. The three wrappers await first, mutate second, and toast honestly:

   ```ts
   export async function approve(id: number): Promise<void> {
     const outcome = await postDecision(id, "allow_once");
     if (outcome === "ok") {
       useStore.getState().allowApproval(id);
       return;
     }
     useStore.getState().showToast(
       "Couldn't send that decision — Hachi is still waiting. Try again.",
       "blocked",
     );
   }
   ```

   The success toast keeps living inside the store action (`store.ts:782`), so you do
   not have to move it.

3. `declineAll` reports **partial** failure. `Promise.allSettled` over the new
   `DecisionOutcome` lets you count: if any outcome is not `"ok"`, toast
   `"blocked"` naming how many did not go through, and do **not** clear those
   approvals. Simplest correct version: resolve each id individually, collect the
   successes, and call `declineApproval(id)` only for those — do not call the bulk
   `declineAll()` store action optimistically.

4. Both stale comments (`:216` "surfaced centrally via client.ts", `:219-220` "skip the
   POST … the store action has already updated the UI optimistically") are **corrected,
   not deleted** — they are the reasoning that produced the bug, and the next reader
   needs to see the new rule instead.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add the `DecisionOutcome` type and change `postDecision`'s return type
   (`approvals.ts:201-225`); return the four outcomes per §5.1.
3. Rewrite `approve` (`:231`), `allowAlways` (`:240`) and `decline` (`:249`) to await
   first and mutate on `"ok"` only.
4. Rewrite `declineAll` (`:258`) per §5.3.
5. Fix the two misleading comments.
6. Check the call sites in `frontend/src/routes/approvals.tsx` — they `await` these
   functions today; confirm nothing there assumed a synchronous store update.
7. `npm run --prefix frontend typecheck && npm run --prefix frontend test`, then the
   full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Runner is **vitest** (`npm run --prefix frontend test` → `vitest run`).

- **File:** `frontend/src/lib/data/domains/approvals.test.ts` — **new**. [T-17](T-17-fe-resolve-approvals-by-request-id.md) also creates this file; whoever lands first creates it, the other adds a `describe` block. Coordinate.
- **Test names:**
  `keeps the approval and warns when the decision POST fails` and
  `does not silently drop the approval when the request_id is unmapped`
- **They must assert:** the real, observed outcome of a failure — that after a rejected
  `apiSend`, the approval is **still in `useStore.getState().approvals`** and a toast
  with tone `"blocked"` was raised. Assert on store state, not on a mock's return value.
- **They must FAIL before your fix** with:
  `AssertionError: expected [] to have a length of 1 but got +0` — the approval was
  removed optimistically despite the POST failing.

```ts
// sketch — adapt to the repo's existing patterns (see store.test.ts:17-37 for the
// canonical vi.mock block for ../client, ../sse and ../../notifications)
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiSend = vi.fn();
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
import { approve } from "./approvals";

describe("approval decisions must not fail silently (CF-4c)", () => {
  beforeEach(() => {
    apiSend.mockReset();
    // seed exactly one pending approval through the real loader/adapter path so the
    // request_id -> numeric id map is populated the way production populates it
  });

  it("keeps the approval and warns when the decision POST fails", async () => {
    apiSend.mockRejectedValue(new Error("500 Internal Server Error"));

    const id = useStore.getState().approvals[0].id;
    await approve(id);

    // The gateway is still blocked — the card must NOT have vanished.
    expect(useStore.getState().approvals).toHaveLength(1);
    expect(
      useStore.getState().toasts.some((t) => t.tone === "blocked")
    ).toBe(true);
  });

  it("does not silently drop the approval when the request_id is unmapped", async () => {
    await approve(999999); // never seen by stableNumericId
    expect(apiSend).not.toHaveBeenCalled();
    expect(
      useStore.getState().toasts.some((t) => t.tone === "blocked")
    ).toBe(true);
  });
});
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Likely cause: you asserted on the toast only. Today's code *does* toast — a
> **success** toast. Assert on the `"blocked"` tone and on `approvals.length`.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist and failed before the fix with the approval removed despite a rejected POST.
- [ ] `rg -n "catch \{\s*\}" frontend/src/lib/data/domains/approvals.ts` returns **nothing** (no bare swallow left in this file).
- [ ] `postDecision` returns an outcome; no caller ignores it.
- [ ] A rejected `apiSend` leaves the approval in `state.approvals` and raises a `"blocked"` toast.
- [ ] An unmapped `uiId` raises a `"blocked"` toast instead of returning silently.
- [ ] `declineAll` does not clear approvals whose POST failed.
- [ ] `USE_MOCKS` behaviour is unchanged (still no network call, still optimistic).
- [ ] `npm run --prefix frontend typecheck` is clean.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not fix the fuzzy matcher.** `approveFirstMatching` / `denyFirstMatching`
  (`approvals.ts:286-321`) call `approve`/`decline` and therefore sit directly on top of
  your change — the temptation to "just fix the id thing while I'm here" is real. That
  is [T-17](T-17-fe-resolve-approvals-by-request-id.md). Keep the diffs separable; if
  T-17 has already landed, your wrappers are called through
  `approveByRequestId`/`declineByRequestId` instead, which is fine and needs no extra
  work.
- **Do not delete the client-fabricated `AuditEntry`** inside `resolveApproval`
  (`store.ts:526-563`) even though moving the mutation behind a successful POST makes it
  tempting. That is [T-19](T-19-fe-stop-fabricating-audit-rows.md).
- **Do not add a global "failed request" banner or an error-boundary redesign.** A
  `"blocked"` toast is the established convention (§3.4).
- **Do not change `client.ts`'s reconnect callback** to cover `ApiError`. That widens
  the blast radius to every domain in the app.
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

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Approval decisions failed silently: the card vanished while the gateway stayed blocked

- **Symptom:** Clicking Allow or Decline always removed the approval card and showed a success toast, even when the `POST /approvals/{id}` returned 404/422/500 or was never issued at all. The agent remained blocked until the 180 s server-side timeout auto-denied it — so a user's *approve* silently became a *deny*, three minutes later, with nothing on screen.
- **Root cause:** `postDecision` in `frontend/src/lib/data/domains/approvals.ts` had two silent paths: a bare `catch {}` (justified by a comment claiming client.ts surfaced failures centrally — it only surfaces *network* errors, not `ApiError` status codes) and an `if (requestId)` guard that skipped the POST entirely on an id-map miss. It returned `Promise<void>`, so callers could not distinguish the three outcomes. `approve`/`allowAlways`/`decline` also ran the optimistic store mutation *before* awaiting.
- **Fix:** `postDecision` now returns `"ok" | "unknown-id" | "failed"`; the wrappers await it and mutate the store only on `"ok"`, raising a `"blocked"`-tone toast otherwise. `declineAll` clears only the approvals whose POST succeeded.
- **Avoid:** never `catch {}` a mutation whose success the UI has already claimed. Mutate on 2xx (BB-78's rule), and if you must be optimistic, roll back every field the optimistic write touched.
- **Locked by:** `frontend/src/lib/data/domains/approvals.test.ts` — "keeps the approval and warns when the decision POST fails"
```

## 12. Known traps

- **`store.test.ts:17-37` is the canonical mock block** for `../data/client`,
  `../data/sse` and `../notifications`. Copy it — the store imports all three at module
  scope.
- **`isNetworkError` matters.** The current comment is *half* right: `client.ts` does
  route genuine network failures into the reconnect banner. Your change must not
  double-report those. Decide once: either let network errors fall into `"failed"` and
  toast (simple, slight duplication with the banner), or check `isNetworkError(err)` and
  skip the toast for those. Say which you chose in the commit message.
- **`declineAll` snapshots ids before mutating** (`approvals.ts:259-260`) precisely
  because the store action clears the list. If you invert the order, keep that snapshot
  — reading `approvals` after the mutation gives you an empty array.
- **`invalidate("approvals")` (`approvals.ts:224`) must keep firing on every path**,
  including failures. Dropping it on the failure branch leaves a stale cached list on
  the next visit.
- **No existing test covers this file** (`approvals.test.ts` does not exist), so nothing
  should break. If something in `frontend/src/routes/approvals.tsx` or its test
  (`frontend/src/routes/-index.ApprovalCard.test.tsx`) goes red, it is asserting the
  optimistic behaviour — read it carefully before touching it, and if it genuinely
  encodes "card disappears immediately", updating it is a **contract correction, not a
  weakening** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Say so in the commit message.
- **BB-4 does not apply** — no gateway route changes, so no OpenAPI regeneration.
