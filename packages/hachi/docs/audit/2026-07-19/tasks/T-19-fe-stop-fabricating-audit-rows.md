# T-19 · Stop the client fabricating audit rows into the server-hydrated audit log

|  |  |
|---|---|
| **Source finding** | CF-4(c) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P1** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none (independent) |
| **Blocks** | nothing |
| **Effort** | ~2 hours |
| **Difficulty** | Low (mechanical — **this is mostly a deletion**) |
| **Files you will touch** | `frontend/src/lib/store/store.ts`, `frontend/src/lib/store/store.test.ts`, `docs/bug-bank.md` |

---

## 1. Brief

Every time a user allows or declines an approval, the web store **invents an
`AuditEntry`** — with a timestamp read off the browser clock — and unshifts it into
`state.auditLog`: the exact same slice that `loadApprovals()` hydrates from the
gateway's `GET /permissions/audit`. The client's fiction and the server's truth share
one array, and the fiction looks *more* authoritative. When you are done,
`state.auditLog` contains only rows the gateway sent.

## 2. Why this matters

This is a recurrence of a rule this repo has already written down. **BB-87** in
`docs/bug-bank.md` says, verbatim:

> **Avoid:** never call `new Date()` when adapting server data that has no timestamp
> field; always store a real `ts: Date.now()` epoch when creating in-memory
> time-sensitive records.

BB-87 fixed the *fetch-time* fabrication in the adapter. It left the *decision-time*
fabrication in the store — and that one is worse, because of a detail worth stating
plainly:

**Server rows deliberately render `ts: "—"`.** The adapter
(`frontend/src/lib/data/domains/approvals.ts:146-154`) sets an em-dash precisely
*because* the backend carries no timestamp. So in the audit table, real gateway rows
show a dash and the client-invented row shows a crisp `14:32:07`. **The fabricated row
looks more trustworthy than the real one.** For a product whose entire pitch is a
verifiable, owned audit trail, that is the worst possible inversion.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The fabrication — `frontend/src/lib/store/store.ts:526-563`, `resolveApproval`

```ts
      const resolveApproval = (
        id: number,
        decision: string,
        color: string
      ) => {
        const a = get().approvals.find((x) => x.id === id);
        const historyEntry: HistoryItem | undefined = a
          ? {
              id,
              icon:
                color === "var(--hachi-danger)" ? "x" : "circle-check",
              request: a.request,
              decision,
              when: "just now",
              ts: Date.now(),
              color,
            }
          : undefined;
        const auditEntry: AuditEntry = {
          ts: new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          op: a?.op ?? "unknown",
          target: a?.action ?? "",
          policy: a?.policy ?? "",
          decision:
            decision === "allowed once"
              ? "allowed once"
              : decision === "always allowed"
              ? "allowed"
              : "declined",
        };
        set((s) => ({
          approvals: s.approvals.filter((x) => x.id !== id),
          history: historyEntry
            ? [historyEntry, ...s.history]
            : s.history,
          auditLog: [auditEntry, ...s.auditLog],
        }));
      };
```

Three writes in one `set`. **Only the third is wrong.**

- `approvals: …filter(…)` — correct, this is local UI state.
- `history: […]` — correct. `HistoryItem` is a **client-side** concept (the "past
  decisions" list); it already carries `ts: Date.now()` per BB-87's fix and there is no
  server counterpart. **Leave it alone.**
- `auditLog: [auditEntry, ...s.auditLog]` — **wrong.** This slice is server truth.

### 3.2 The same slice is hydrated from the gateway — `frontend/src/lib/data/domains/approvals.ts:170-179`

```ts
    const [approvalsRes, auditRes] = await Promise.all([
      apiGet<GatewayApprovalsResponse>("/approvals"),
      apiGet<GatewayPermissionAudit[]>("/permissions/audit", { limit: 50 }),
    ]);

    const approvals: Approval[] = (approvalsRes.pending ?? []).map(adaptApproval);
    const auditLog: AuditEntry[] = (Array.isArray(auditRes) ? auditRes : []).map(adaptAuditEntry);

    useStore.getState().hydrate({ approvals, auditLog });
```

`hydrate` **replaces** the array, so a fabricated row survives only until the next
`loadApprovals()` — which makes the inconsistency intermittent and therefore harder to
notice than a permanent one.

### 3.3 The server adapter deliberately refuses to fabricate — `frontend/src/lib/data/domains/approvals.ts:146-154`

```ts
  return {
    // Gateway's PermissionAuditSnapshot carries no timestamp field — render "—"
    // rather than fabricate the fetch time as if it were the decision time.
    ts: "—",
    op: raw.operation ?? raw.tool ?? "unknown",
    target: raw.target ?? "",
    policy: raw.reason ?? raw.operation ?? "",
    decision,
  };
```

This is the BB-87 fix. The store fabrication in §3.1 directly contradicts it, in the
same array.

### 3.4 Four callers — `frontend/src/lib/store/store.ts:779-798`

```ts
        // approvals
        allowApproval: (id) => {
          resolveApproval(id, "allowed once", "var(--hachi-success)");
          toast("On it — Hachi is working", "working");
        },
        alwaysApproval: (id) => {
          resolveApproval(id, "always allowed", "var(--hachi-success)");
          toast("Saved — Hachi won't ask again for this", "success");
        },
        declineApproval: (id) => {
          resolveApproval(id, "declined", "var(--hachi-danger)");
          toast("Stayed put — Hachi is resting", "success");
        },
        declineAll: () => {
          const ids = get().approvals.map((a) => a.id);
          ids.forEach((id) =>
            resolveApproval(id, "declined", "var(--hachi-danger)")
          );
          toast("Stayed put — Hachi is resting", "success");
        },
```

`declineAll` calls it once per approval, so declining five approvals injects **five**
fabricated audit rows.

### 3.5 Where it is rendered — `frontend/src/routes/approvals.tsx:357` and `:655-657`

```ts
  const auditLog = useStore((s) => s.auditLog);
```

```tsx
                {auditLog.map((a, i) => (
                  <AuditRow key={i} entry={a} />
                ))}
```

One table, under the heading *"Permission audit log"*
(`aria-label="Permission audit log"`, `:647`) — client fiction and server rows
interleaved with no visual distinction, sorted so the fiction is on top.

### 3.6 The type — `frontend/src/lib/data/types.ts:54-60`

```ts
export interface AuditEntry {
  ts: string;
  op: string;
  target: string;
  policy: string;
  decision: "allowed" | "allowed once" | "declined" | "automatic" | string;
}
```

`ts` is a preformatted display string, which is why the em-dash sentinel works.
**No type change is needed for this task.**

## 4. Reproduce the failure

Reproducible in the browser with fixture data — no gateway, no
[T-01](T-01-approver-selection-dead-branch.md) required.

```bash
# 1. The fabrication.
rg -n "new Date\(\)\.toLocaleTimeString" frontend/src/lib/store/store.ts

# 2. The same slice hydrated from the server.
rg -n "auditLog" frontend/src/lib/data/domains/approvals.ts

# 3. The adapter that refuses to fabricate, in the same file.
rg -n -B 3 '"—"' frontend/src/lib/data/domains/approvals.ts
```

**Manual reproduction:**

1. Open the Leash screen and scroll to the *Permission audit log* table.
2. Note that gateway-sourced rows show `—` in the timestamp column.
3. Allow or decline any approval.
4. A new row appears at the top of that same table with a real-looking
   `HH:MM:SS` timestamp.

**You will see now:** one table, two provenances, and the invented row is the only one
with a timestamp.

**You should see after the fix:** the table contains only rows that came from
`GET /permissions/audit`. The decision still appears immediately in the **Past
decisions** list (`state.history`), which is the client-side surface that is *supposed*
to hold it.

## 5. What "fixed" looks like

No decision required. Delete the fabrication; keep everything else byte-identical.

1. `resolveApproval` (`store.ts:526-563`) no longer constructs an `AuditEntry` and no
   longer writes `auditLog`:

   ```ts
       const resolveApproval = (
         id: number,
         decision: string,
         color: string
       ) => {
         const a = get().approvals.find((x) => x.id === id);
         const historyEntry: HistoryItem | undefined = a ? { … } : undefined;
         // The audit log is server truth, hydrated from GET /permissions/audit
         // (approvals.ts:loadApprovals). Never unshift a client-invented row into it —
         // gateway rows carry no timestamp and render "—", so a fabricated row with a
         // real clock reading looks MORE authoritative than the real ones. See BB-87.
         set((s) => ({
           approvals: s.approvals.filter((x) => x.id !== id),
           history: historyEntry ? [historyEntry, ...s.history] : s.history,
         }));
       };
   ```

2. The `AuditEntry` type import in `store.ts` may become unused — check
   `rg -n "AuditEntry" frontend/src/lib/store/store.ts` before deleting it; the store's
   `State` interface still declares `auditLog: AuditEntry[]`, so it probably stays.

3. The user still gets immediate feedback: the toast (unchanged, `store.ts:782` etc.)
   and the **Past decisions** history row (unchanged). The audit table refreshes on the
   next `loadApprovals()` — which `postDecision` already triggers via
   `invalidate("approvals")` (`approvals.ts:224`).

4. **Nothing else changes.** Do not touch `history`, do not touch `tickApprovals`
   (`store.ts:799-828`), do not touch the adapter.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Delete the `const auditEntry: AuditEntry = { … };` block (`store.ts:544-555`).
3. Delete `auditLog: [auditEntry, ...s.auditLog],` from the `set` (`store.ts:561`).
4. Add the explanatory comment from §5.1 in its place — the next contributor must be
   told *why* the obvious write is absent, or it comes back.
5. Run `rg -n "AuditEntry" frontend/src/lib/store/store.ts` and remove the import only
   if it is genuinely unused (`tsc` will tell you).
6. `npm run --prefix frontend typecheck && npm run --prefix frontend test`, then the
   full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

Runner is **vitest** (`npm run --prefix frontend test` → `vitest run`).

- **File:** `frontend/src/lib/store/store.test.ts` (**existing** — the BB-77 block sits
  at `:117-159`; add a new `describe` next to it)
- **Test names:**
  `resolving an approval does not write into the server-hydrated audit log` and
  `declineAll does not inject one fabricated row per approval`
- **It must assert:** the real, observed store state — that `state.auditLog` is
  **unchanged** (same length, same contents) after `allowApproval` / `declineApproval` /
  `declineAll`, while `state.history` **does** gain a row (proving you deleted the right
  one of the three writes).
- **It must FAIL before your fix** with:
  `AssertionError: expected [ { ts: '14:32:07', … } ] to have a length of 0 but got 1`

```ts
// sketch — adapt to the repo's existing patterns (store.test.ts already has the
// vi.mock block for ../data/client, ../data/sse and ../notifications at :17-37)
describe("audit log is server truth — never client-fabricated (BB-87 recurrence)", () => {
  const seeded: Approval[] = [
    {
      id: 1, icon: "mail", request: "send_email", why: "reply",
      action: "send_email → priya@studio.co", op: "action", policy: "asks first",
      touches: [], risk: "high", scope: "action", expiresAt: 0, totalMs: 0,
    },
  ];

  beforeEach(() => {
    useStore.getState().hydrate({
      dataMode: "live",
      approvals: [...seeded],
      auditLog: [],
      history: [],
    });
  });

  it("resolving an approval does not write into the server-hydrated audit log", () => {
    useStore.getState().allowApproval(1);

    // The audit table is hydrated ONLY from GET /permissions/audit.
    expect(useStore.getState().auditLog).toHaveLength(0);
    // …but the client-side "past decisions" list is still updated.
    expect(useStore.getState().history).toHaveLength(1);
    expect(useStore.getState().approvals).toHaveLength(0);
  });

  it("declineAll does not inject one fabricated row per approval", () => {
    useStore.getState().hydrate({
      approvals: [seeded[0], { ...seeded[0], id: 2 }, { ...seeded[0], id: 3 }],
      auditLog: [],
      history: [],
    });
    useStore.getState().declineAll();
    expect(useStore.getState().auditLog).toHaveLength(0);
    expect(useStore.getState().history).toHaveLength(3);
  });
});
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Likely cause: you did not reset `auditLog` to `[]` in `beforeEach`, or you asserted
> only on length without seeding an approval that `resolveApproval` can find (the
> `const a = get().approvals.find(...)` lookup at `store.ts:531` must succeed for the
> row to carry real values, though the row is unshifted either way).

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist and failed before the fix with `auditLog` length 1 (and 3).
- [ ] `rg -n "new Date\(\)\.toLocaleTimeString" frontend/src/` returns **nothing**.
- [ ] `rg -n "auditLog:" frontend/src/lib/store/store.ts` shows only the `State` declaration and the `domainDefaults` seeding (`:416`) — **no write inside an action**.
- [ ] `state.history` still gains a row on every decision (you deleted one write, not two).
- [ ] The explanatory comment from §5.1 is present so the write is not reintroduced.
- [ ] `npm run --prefix frontend typecheck` is clean.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `history` / `HistoryItem`.** It looks like the same problem — it is
  built in the same object literal, three lines above, and it also contains
  `when: "just now"`. It is **not** the same problem: `history` is a purely client-side
  "past decisions" list with no server counterpart, and its `ts: Date.now()` is BB-87's
  *fix*, not its bug. Deleting it removes real functionality (CLAUDE.md Rule 3).
- **Do not add a timestamp to the backend's permission audit.** Giving
  `PermissionAuditSnapshot` a real `ts` so the table stops rendering `—` is a genuine
  and worthwhile follow-up — and it is a backend change with an OpenAPI regeneration
  (BB-4) and its own test. **Note it, do not do it here.**
- **Do not mark client rows as "local" and keep them.** A provenance badge on a
  fabricated row is still a fabricated row in an audit table; and the moment
  `loadApprovals()` runs, `hydrate` wipes it anyway, so the badge would flicker.
- **Do not touch `tickApprovals`** (`store.ts:799-828`). That is BB-77's code path.
- **Do not start splitting the store into slices.** That is CF-16, Wave 2.
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
### BB-N — Client-fabricated rows in the permission audit log (BB-87 recurrence)

- **Symptom:** Allowing or declining an approval unshifted a locally-invented row — with a `new Date().toLocaleTimeString()` timestamp — into the same `auditLog` slice that `loadApprovals()` hydrates from `GET /permissions/audit`. Because real gateway rows deliberately render `ts: "—"` (they carry no server timestamp), the fabricated row was the ONLY row in the table with a timestamp, i.e. it looked more authoritative than the real ones. `declineAll` injected one per approval.
- **Root cause:** `resolveApproval` in `frontend/src/lib/store/store.ts` did three writes in one `set()`: filter `approvals` (correct), unshift `history` (correct — client-side "past decisions", no server counterpart), and unshift `auditLog` (wrong — server truth). BB-87 had removed the fetch-time fabrication in the adapter but left the decision-time one in the store.
- **Fix:** Deleted the `AuditEntry` construction and the `auditLog` write from `resolveApproval`, leaving a comment explaining why the obvious write is absent. `history` and the toast are unchanged, so the user still gets immediate feedback; the audit table refreshes from the gateway on the next `loadApprovals()`.
- **Avoid:** a store slice hydrated from the server has exactly one writer — the loader. Never unshift a locally-constructed record into it, and never invent a timestamp for a row whose server counterpart has none.
- **Locked by:** `frontend/src/lib/store/store.test.ts` — "resolving an approval does not write into the server-hydrated audit log"
```

## 12. Known traps

- **Three writes, delete one.** The `set((s) => ({ … }))` at `store.ts:556-562` contains
  `approvals`, `history` and `auditLog`. Deleting the wrong one silently breaks either
  the card removal or the past-decisions list, and neither has a strong existing test.
  Your §7 test asserts all three, which is why it is written that way.
- **`store.test.ts` already hydrates a lot of state in its `beforeEach`**
  (`store.test.ts:41-52`) and it does **not** reset `auditLog`/`history`/`approvals`.
  Your new `describe` must seed them itself, or you will inherit whatever the run-related
  block left behind.
- **`AuditEntry` may still be needed as a type import** in `store.ts` — the `State`
  interface declares `auditLog: AuditEntry[]` and `domainDefaults` seeds it from
  fixtures at `:416`. Let `tsc` decide; do not delete the import speculatively (`ruff`'s
  TS equivalent here is `tsc --noEmit`, run by `npm run --prefix frontend typecheck`).
- **`hydrate` masks the bug intermittently.** `loadApprovals` replaces the whole array,
  so a manual browser check right after a page refresh may show a clean table. Trigger a
  decision *without* navigating, and look before the refetch lands.
- **BB-4 does not apply** — no gateway route changes, so no OpenAPI regeneration.
- **This task is frontend-only.** No file under `src/hachi/` should appear in your diff.
