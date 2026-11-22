# T-63 · Split the 1,807-line zustand store into typed slices

|  |  |
|---|---|
| **Source finding** | CF-16 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none — but do **step 1** (render smoke tests) before any split |
| **Blocks** | nothing |
| **Effort** | ~1–2 weeks |
| **Difficulty** | High (wide and mechanical, but the safety net has to be built first) |
| **Files you will touch** | `frontend/src/lib/store/store.ts` → new `frontend/src/lib/store/slices/*.ts`, `frontend/src/lib/store/store.test.ts`, new route render tests, `docs/bug-bank.md` |
| **See also** | [T-65](T-65-chat-ts-kernel-extraction.md) (the other half of the frontend state problem), [T-64](T-64-frontend-fix-false-cycle-comment.md), [T-66](T-66-approval-string-ids.md) |

---

## 1. Brief

`frontend/src/lib/store/store.ts` is **1,807 lines**: one flat zustand store with
**75 state fields** and **100 actions** covering **22 unrelated concerns**, from OAuth
connection status to a chat composer string to a scripted demo run queue. The SSE
handler, ~20 domain loaders and every UI action write into one namespace with no
ownership boundaries.

When you are done, the store is composed from typed slices with one owner per concern,
split one slice per commit — and there are render smoke tests for the four biggest
screens that existed *before* the first split.

## 2. Why this matters

This is the top-churn frontend file, and "no ownership boundaries" is not an aesthetic
complaint — it is the mechanism behind the stale-slice bug class the project has already
hit. Anything can write anything: a domain loader can clobber a field the SSE handler
is mid-update on, and nothing in the type system or the module graph says otherwise.

The second reason is **testability**. The frontend has **24 test files against 100
source files**, and exactly **one** route-level test
(`frontend/src/routes/-index.ApprovalCard.test.tsx`). The four largest screens —
2,187 / 1,472 / 1,283 / 1,214 lines — have no render coverage at all. Splitting a store
those screens depend on, with no test asserting they still render, is how you turn a
mechanical refactor into a week of bisecting blank pages.

So the order matters more than the destination: **safety net first, then slices, one
commit each.** A big-bang split of this file is the single most dangerous change
available in the frontend.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.
>
> Note: the review calls this file `frontend/src/lib/store.ts`. The real path is
> **`frontend/src/lib/store/store.ts`**.

### 3.1 Corrected counts

| Thing | Review said | **Verified** |
|---|---|---|
| Total lines | 1,807 | **1,807** ✓ |
| State fields | ~95 | **75** (`interface State`, `:112-222`) |
| Actions | ~85 | **100** (`interface Actions`, `:227-352`) |
| Concerns | ~16 | **22** (§3.4 — they partition all 75 fields exactly) |
| `dataMode === "live"` forks in actions | ~20 | **14** (`:802`, then 13 in `:1205-1772`) |

### 3.2 ⚠️ `hydrate` is partially REFUTED — it **is** typed

The review says `hydrate: (patch) => set(patch)` "lets any caller overwrite any field",
implying no type. That is wrong. The declaration at `:231` is typed:

```ts
  // live-data hydration (foundation)
  // Shallow-merge a slice of gateway-derived state into the store. Domain
  // loaders call this after mapping a gateway response to UI types.
  hydrate: (patch: Partial<State>) => void;
```

The real defect is in the **implementation** (`:667-676`), which is an unvalidated
bulk `set()` that widens the type to include `Actions`:

```ts
        hydrate: (patch) => {
          if (Array.isArray(patch.messages)) {
            set({
              ...(patch as Partial<State & Actions>),
              messages: capMessages(patch.messages),
            });
            return;
          }
          set(patch as Partial<State & Actions>);
        },
```

Two separate problems, and you should fix both:

1. **The `Actions` widening.** `Partial<State & Actions>` means a caller who passes a
   key colliding with an action name would overwrite a *function* on the store. The
   declared parameter type is `Partial<State>`; the cast to `Partial<State & Actions>`
   is only there to satisfy zustand's setter, and it silently drops the guarantee.
2. **Unvalidated bulk set, no domain boundary.** Any of ~20 loaders can write any of
   the 75 fields in one call. There is no per-domain `hydrate`, so the type system
   cannot express "the approvals loader may only write approvals-shaped state."

State it accurately in the commit message: this is not "untyped", it is "typed then
widened, and unscoped".

### 3.3 What the store statically imports

`store.ts:10-17` imports six live functions from the chat domain:

```ts
import {
  allowLeashLive,
  denyLeashLive,
  newSessionLive,
  startTaskLive,
  stopStreamingLive,
  switchSessionLive,
} from "../data/domains/chat";
```

and `:18-53` statically imports **33 fixture symbols** from `../data/fixtures`, which
is how the demo data reaches the production bundle. Both facts matter when you decide
where slices live — see [T-64](T-64-frontend-fix-false-cycle-comment.md) for the
first one.

### 3.4 The 22 concerns — the slice plan

These partition all 75 fields exactly. Field names are verbatim from `interface State`.

| # | Slice | Fields |
|---:|---|---|
| 1 | persist | `operator`, `theme` |
| 2 | dataMode | `dataMode` |
| 3 | budget/spend | `spent`, `budget`, `taskSpent`, `spendTurns`, `spendTidies`, `spendModels`, `taskCap`, `dailyCap` |
| 4 | approvals | `approvals` |
| 5 | work queue | `history`, `runs`, `routines`, `finished`, `failed`, `blocked` |
| 6 | memory | `memGroups`, `recall`, `editingFactId`, `editingText` |
| 7 | review | `proposed` |
| 8 | skills/kennel | `skills`, `kennel`, `skillUsage`, `packRoster`, `kennelConsent`, `kennelBrowseOpen` |
| 9 | integrations/MCP | `integrations`, `mcpServers`, `mcpTools` |
| 10 | authoring | `authTargets`, `authSource`, `authSel`, `authMode`, `authAppliedTarget` |
| 11 | OG explorer | `ogNodes`, `ogSel`, `ogView` |
| 12 | activity/audit | `events`, `toolCalls`, `auditLog` |
| 13 | sessions | `sessions` |
| 14 | permissions/safety | `safety`, `askRules`, `allowedFolders`, `allowedCommands`, `opTools` |
| 15 | provider/config-loading | `provider`, `configLoaded`, `loaded`, `reconnecting` |
| 16 | toasts | `toasts` |
| 17 | command palette | `palette` |
| 18 | setup wizard | `setup` |
| 19 | chat/composer | `slashOpen`, `streaming`, `inContext`, `messages`, `composer`, `pendingAttachments` |
| 20 | home UI | `homeInput`, `selectedWork`, `workFilter` |
| 21 | live-run view | `runView`, `runLines`, `runStreaming`, `runDone`, `runLeash`, `runSpent`, `runPack`, `runSteps` |
| 22 | eval loop | `interactions`, `lastUsedModel` |

**Total: 75.** If your slices don't add up to 75, you have dropped or duplicated a field.

### 3.5 The test deficit you are refactoring into

```bash
find frontend/src -name "*.ts" -o -name "*.tsx" | grep -v "\.test\." | wc -l   # -> 100
find frontend/src -name "*.test.ts" -o -name "*.test.tsx" | wc -l              # -> 24
find frontend/src/routes -name "*.test.tsx"                                     # -> 1
```

The single route test is `frontend/src/routes/-index.ApprovalCard.test.tsx`.

Route sizes, verified exactly:

| Route | Lines |
|---|---:|
| `frontend/src/routes/integrations.tsx` | **2187** |
| `frontend/src/routes/work.tsx` | **1472** |
| `frontend/src/routes/og.tsx` | **1283** |
| `frontend/src/routes/memory.tsx` | **1214** |
| `frontend/src/routes/authoring.tsx` | 964 |
| `frontend/src/routes/index.tsx` | 847 |

### 3.6 Tooling you already have

`frontend/package.json` devDependencies include `vitest`, `jsdom`,
`@testing-library/react` and `@testing-library/jest-dom`. Render smoke tests need **no
new dependency**. `vite.config.ts:42-44` already sets `test: { environment: 'jsdom' }`.

`frontend/src/lib/store/store.test.ts` exists and shows the established mocking idiom
(`vi.mock("../data/client", …)` at `:17-27`, `vi.mock("../data/sse", …)` at `:29-31`).
Copy it rather than inventing a harness.

## 4. Reproduce the failure

Nothing malfunctions. This is a structural finding; prove the structure and say so
rather than inventing a failing command.

```bash
cd frontend

# 1. Size and shape.
wc -l src/lib/store/store.ts

# 2. Field / action counts (read the interfaces at :112-222 and :227-352).
sed -n '112,222p' src/lib/store/store.ts | grep -c "^  [a-zA-Z_].*:"
sed -n '227,352p' src/lib/store/store.ts | grep -c "^  [a-zA-Z_].*:"

# 3. The hydrate hatch — declared typed, implemented widened.
sed -n '231p;667,676p' src/lib/store/store.ts

# 4. THE IMPORTANT ONE — how little covers the screens you are about to destabilise.
find src/routes -name "*.test.tsx" -o -name "*.test.ts"
wc -l src/routes/integrations.tsx src/routes/work.tsx src/routes/og.tsx src/routes/memory.tsx
```

**You will see now:** (1) 1807; (2) 75 and 100 (the grep is approximate — the
authoritative counts are in §3.1, taken with a brace-depth-aware pass); (3) the typed
declaration and the `as Partial<State & Actions>` casts; (4) **nothing**, and
2187/1472/1283/1214.

**You should see after the fix:** (1) a much smaller `store.ts` that composes slices;
(4) four route smoke tests.

## 5. What "fixed" looks like

1. **Render smoke tests exist first** for `integrations`, `work`, `og` and `memory` —
   before any slice moves. Each mounts the route with a mocked data layer and asserts a
   stable landmark (a heading, a known empty-state string). They are smoke tests, not
   behaviour tests: their job is to fail loudly when a slice split breaks a screen.

2. **One file per slice**, `frontend/src/lib/store/slices/<name>.ts`, each exporting its
   own state type, action type and a zustand slice creator:

   ```ts
   export interface ApprovalsState {
     approvals: Approval[];
   }

   export interface ApprovalsActions {
     allowApproval: (id: number, scope?: string) => void;
     alwaysApproval: (id: number) => void;
     declineApproval: (id: number, reason?: string) => void;
     declineAll: () => void;
     tickApprovals: () => void;
   }

   export const createApprovalsSlice: StateCreator<
     Store, [], [], ApprovalsState & ApprovalsActions
   > = (set, get) => ({ /* … */ });
   ```

3. **`store.ts` becomes a composition root** — `create(persist(...(a, b, c) => ({
   ...createApprovalsSlice(a,b,c), ...createWorkSlice(a,b,c), … })))` — plus the
   `State`/`Actions` union types assembled from the slices. The **public API is
   unchanged**: `useStore` keeps its shape, so no component changes.

4. **Per-domain hydrate.** The global `hydrate` stays for one release (20 loaders call
   it), but each slice gains a scoped one:

   ```ts
   hydrateApprovals: (patch: Partial<ApprovalsState>) => void;
   ```

   and the `as Partial<State & Actions>` widening at `:670`/`:675` is removed —
   `Partial<State>` is what the signature promises, so make the implementation honour it.

5. Observable outcome: **no user-visible change.** Same screens, same behaviour. The
   win is that "who can write `approvals`?" has a one-word answer.

## 6. Steps

**Phase 1 — safety net (do not skip; this is the whole point of the ordering):**

1. Write the four render smoke tests (§7). They must pass on unmodified `main` —
   these are the one test in this pack that is *supposed* to be green before you start.
   Commit them alone.

**Phase 2 — slices, one commit each:**

2. Create `frontend/src/lib/store/slices/` and move **one** slice. Start with **toasts**
   (#16) or **command palette** (#17): single field, few actions, no `dataMode` fork, no
   cross-slice reads. Prove the composition pattern on something trivial.
3. Run `npm run --prefix frontend typecheck && npm run --prefix frontend test` after
   **every** slice. Commit each one separately with the slice name in the message.
4. Work outward in dependency order. Leave for last: **chat/composer** (#19),
   **live-run view** (#21) and **work queue** (#5) — they carry the `dataMode` forks and
   the cross-slice reads.
5. When a slice's actions read another slice's state, use `get()` rather than importing
   across slices. Cross-slice *imports* recreate the coupling you are removing.
6. Remove the `Partial<State & Actions>` casts in `hydrate` (`:670`, `:675`) and add
   per-domain hydrate functions as each slice lands.
7. Run `uv run python scripts/preflight.py` (**full**) at the end and report the real
   counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**

This task is a refactor, so the tests are a **safety net** rather than a red-then-green
lock. Two kinds, and both are required:

**(a) Route render smoke tests — these must pass BEFORE you start.**

- **Files:** `frontend/src/routes/integrations.test.tsx`, `work.test.tsx`,
  `og.test.tsx`, `memory.test.tsx` (**new**)
- **Test name:** `test`-style vitest `it("renders without crashing", …)`
- **They must assert:** the real rendered DOM contains a stable landmark. Not that a
  component function returned truthy.

**(b) A store-contract test that DOES go red first.**

- **File:** `frontend/src/lib/store/store.test.ts` (**existing**)
- **Test name:** `hydrate cannot overwrite an action`
- **It must FAIL before your fix** with something like
  `AssertionError: expected typeof store.declineAll to be 'function', got 'string'` —
  because today `set(patch as Partial<State & Actions>)` will happily write a string
  over the `declineAll` function.

```ts
// (a) sketch — frontend/src/routes/work.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// Mirror the existing mocks in src/lib/store/store.test.ts:17-35
vi.mock("../lib/data/client", () => ({
  USE_MOCKS: false,
  apiGet: vi.fn().mockResolvedValue(undefined),
  apiSend: vi.fn().mockResolvedValue(undefined),
  registerReconnectCallback: vi.fn(),
  isNetworkError: () => false,
  API_BASE: "/api",
  authHeaders: () => ({}),
  ApiError: class ApiError extends Error {},
}));
vi.mock("../lib/data/sse", () => ({ streamSSE: vi.fn() }));

describe("work route", () => {
  it("renders without crashing", () => {
    // Import after the mocks so the module graph picks them up.
    const { RouteComponent } = require("./work");
    render(<RouteComponent />);
    // Pick a landmark that exists in BOTH the empty and populated states.
    expect(screen.getByRole("heading", { name: /work/i })).toBeInTheDocument();
  });
});
```

```ts
// (b) sketch — append to frontend/src/lib/store/store.test.ts
it("hydrate cannot overwrite an action", () => {
  // Regression: hydrate is DECLARED as (patch: Partial<State>) => void but the
  // implementation casts to Partial<State & Actions> and bulk-set()s, so a stray
  // key could replace a store action with arbitrary data.
  const before = useStore.getState().declineAll;

  // @ts-expect-error — this is exactly the call the runtime must reject.
  useStore.getState().hydrate({ declineAll: "clobbered" });

  const after = useStore.getState().declineAll;
  expect(typeof after).toBe("function");
  expect(after).toBe(before);
});
```

> If the (a) tests fail on unmodified `main`, fix the **test**, not the route — you have
> not started refactoring yet, so a red smoke test means your harness is wrong.
> If the (b) test passes before your fix, the test is wrong. Do not proceed.
>
> On the `require()` in (a): TanStack Router route files export a `Route` object via
> `createFileRoute`; check how `-index.ApprovalCard.test.tsx` imports its subject and
> follow that, rather than assuming a `RouteComponent` export exists.

## 8. Acceptance criteria

- [ ] Four route render smoke tests exist and passed **before** the first slice moved.
- [ ] The `hydrate cannot overwrite an action` test exists and failed before the fix.
- [ ] `frontend/src/lib/store/slices/` contains one file per concern, and the slices' fields sum to **exactly 75** — no field dropped, none duplicated.
- [ ] `frontend/src/lib/store/store.ts` is a composition root; `wc -l` is a small fraction of 1,807.
- [ ] `grep -n "as Partial<State & Actions>" frontend/src/lib/store/store.ts` returns **nothing**.
- [ ] `useStore`'s public shape is unchanged — **zero** component files edited.
- [ ] Each slice landed as its own commit.
- [ ] `npm run --prefix frontend typecheck` and `npm run --prefix frontend test` are green.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not split the route files.** This is the drift: you will be staring at
  `integrations.tsx` (2,187 lines) while writing its smoke test, and splitting it will
  feel like the same job. It is not — it is a much larger change with a different blast
  radius, and doing both at once makes every regression ambiguous. Write the smoke test,
  leave the route alone.
- **Do not move mock/live behind the data layer in this task.** CF-16 recommends it and
  it is right, but the 14 `dataMode === "live"` forks (`:802` + `:1205-1772`) and the
  33 statically-imported fixture symbols (`:18-53`) are a *separate* refactor. Doing it
  during the split means every regression could be either change. Slices first.
- **Do not change any action's behaviour** while moving it. Move the body verbatim;
  if it needs fixing, do that in a follow-up commit that touches nothing else.
- **Do not fix the false cycle comment here** — that is
  [T-64](T-64-frontend-fix-false-cycle-comment.md), and it is one line.
- **Do not change `Approval.id` to a string here** — that is
  [T-66](T-66-approval-string-ids.md). If you move the approvals slice first you will be
  tempted; resist, or the two changes become one unreviewable diff.
- **Do not extract chat.ts's module state** — that is
  [T-65](T-65-chat-ts-kernel-extraction.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not add a dependency without asking — `vitest` + `jsdom` + `@testing-library/react`
  are already present (§3.6).

## 10. Verify

```bash
npm run --prefix frontend typecheck
npm run --prefix frontend test
npm run --prefix frontend build
uv run python scripts/preflight.py           # before you call it done
```

`scripts/preflight.py` runs frontend typecheck (`:118-122`), vitest (`:123`), the
OpenAPI contract check (`:124-131`) and the production build (`:134-139`). Run the
**full** gate, not `--quick` — `--quick` skips the frontend build, and a build-only
failure (a circular import that `tsc --noEmit` tolerates but Rollup does not) is exactly
the failure mode a store split produces. Report the **actual** counts.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `hydrate` widened its own type and could overwrite store actions

- **Symptom:** Any of ~20 domain loaders could write any of the store's 75 fields in a single call, and a key colliding with an action name would replace that action's *function* with arbitrary data.
- **Root cause:** `frontend/src/lib/store/store.ts` was one flat 1,807-line store (75 fields, 100 actions, 22 concerns). `hydrate` was declared `(patch: Partial<State>) => void` (`:231`) but implemented as `set(patch as Partial<State & Actions>)` (`:670`, `:675`) — the cast existed to satisfy zustand's setter and silently dropped the guarantee the signature made. There were no domain boundaries, so nothing could express "this loader may only write approvals-shaped state".
- **Fix:** Store split into typed slices under `lib/store/slices/`, one owner per concern, with per-domain hydrate functions and the `Partial<State & Actions>` casts removed. Public `useStore` shape unchanged; no component touched.
- **Avoid:** a cast that widens a parameter beyond its declared type is a silent contract break. If a library's setter needs a wider type than your API promises, narrow at the boundary — don't widen the promise. And never refactor a store four untested 1,200+-line screens depend on without landing render smoke tests first.
- **Locked by:** `frontend/src/lib/store/store.test.ts` — `hydrate cannot overwrite an action`
```

## 12. Known traps

- **Slice count is a checksum.** 75 fields, 22 slices, and the table in §3.4 partitions
  them exactly. If your total is 74 or 76, find the discrepancy before continuing — a
  silently dropped field becomes `undefined` at runtime and typechecks fine if anything
  reads it as optional.
- **`domainDefaults()` (`:384-435`) is the fixture seeding layer**, with ~36
  `USE_MOCKS ? fixture : []` ternaries. Each slice needs its own defaults function, and
  the `USE_MOCKS` ternaries must move with the fields they seed — not be "simplified"
  away (that is the out-of-scope mock/live refactor).
- **`persist` only persists `operator` + `theme`** (see the file header at `:1-5`).
  Whatever composition you build must keep the `partialize` behaviour identical, or you
  will start persisting the whole store to localStorage — including chat messages.
- **13 of the 14 `dataMode === "live"` forks live in `:1205-1772`**, i.e. in the
  chat/run/work actions. `store.test.ts`'s existing tests exist precisely to pin that
  the scripted demo queue never fires in live mode (see its header comment at `:1-13`).
  Those tests must keep passing untouched — they are your best signal that the
  dangerous slices moved correctly.
- **`store.ts` statically imports `chat.ts`** (`:10-17`), and `chat.ts` imports
  `useStore` (`chat.ts:16`). That cycle exists today and works; splitting the store
  changes the module-init order and can turn a tolerated cycle into a real TDZ error at
  runtime. This is the failure `npm run build` catches and `tsc --noEmit` does not —
  see §10, and see [T-64](T-64-frontend-fix-false-cycle-comment.md).
- **BB-4:** if anything you touch changes the API surface, regenerate the OpenAPI spec
  and `frontend/src/lib/data/schema.d.ts` — `check:api` does a `git diff --exit-code`.
  A store split should not, but the contract step is blocking, so verify rather than
  assume.
