# T-65 · Extract `chat.ts`'s module-state kernel into `sessionRef` / `streamBuffers` / `costMeter` with one `reset()`

|  |  |
|---|---|
| **Source finding** | CF-16 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (the state being extracted is live during streaming — read §12) |
| **Files you will touch** | `frontend/src/lib/data/domains/chat.ts` → new `frontend/src/lib/data/domains/chat/*.ts`, `frontend/src/lib/data/domains/chat.test.ts`, `docs/bug-bank.md` |
| **See also** | [T-63](T-63-frontend-store-slices.md), [T-64](T-64-frontend-fix-false-cycle-comment.md) |

---

## 1. Brief

`frontend/src/lib/data/domains/chat.ts` is **1,593 lines** and is not really a data
adapter — it is a runtime kernel built on **17 module-level mutables** (16 `let` plus
one mutable `const Set`). That state drives the live session id, the SSE cursor, the
streaming delta buffers, the rAF flush handles and the per-turn cost baselines. None of
it is in the store, so none of it is visible to React devtools, inspectable from the
store, or resettable in one place.

The consequence is already in the file: the **same ~10-line reset sequence is duplicated
in four separate functions**. When you are done, that state lives in three cohesive
objects with a single `reset()`, and the four duplicates are one call.

## 2. Why this matters

Four hand-maintained copies of a reset sequence is a bug waiting for its fifth caller.
Every new "start a fresh conversation" path has to remember all ten assignments in the
right order; miss one — say `_cursor` — and the next SSE fetch replays from a stale
cursor into a new session. That is a cross-session bleed, the exact bug class CF-16
predicts, and nothing in the type system or the tests would catch it.

The invisibility compounds it. When a user reports "the transcript from my last session
appeared in a new one", the state that would explain it is not in the store, so it is
not in any snapshot, log, or devtools view. The first debugging step is reading 1,593
lines.

If the fix you write ends with "the variables are now in an object but each function
still resets its own fields" — you have moved the problem, not solved it. The single
`reset()` is the point.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The 17 module-level mutables

`wc -l frontend/src/lib/data/domains/chat.ts` → **1593**.
`grep -c "^let " …` → **16**, plus one mutable `Set` bound with `const`:

| # | Line | Symbol | Proposed home |
|---:|---:|---|---|
| 1 | `:51` | `_liveSessionId` | `sessionRef` |
| 2 | `:52` | `_sseAbort` | `sessionRef` |
| 3 | `:57` | `_streamSessionId` | `sessionRef` |
| 4 | `:62` | `_cursor` | `sessionRef` |
| 5 | `:86` | `_textLineActive` | `streamBuffers` |
| 6 | `:96` | `_pendingRunLineText` | `streamBuffers` |
| 7 | `:97` | `_runLineRafHandle` | `streamBuffers` |
| 8 | `:98` | `_runLineLastFlushTs` | `streamBuffers` |
| 9 | `:171` | `_deltaBuffer` | `streamBuffers` |
| 10 | `:172` | `_deltaTargetId` | `streamBuffers` |
| 11 | `:173` | `_rafHandle` | `streamBuffers` |
| 12 | `:174` | `_lastFlushTs` | `streamBuffers` |
| 13 | `:271` | `_costCumAtTurnStart` | `costMeter` |
| 14 | `:272` | `_spentAtTurnStart` | `costMeter` |
| 15 | `:275` | `_lastKnownCumCost` | `costMeter` |
| 16 | `:377` | `_hachiMsgId` | `streamBuffers` |
| 17 | `:1088` | `_eventsUnavailable` (`const … = new Set<string>()`) | `sessionRef` |

The review said "~18"; the verified count is **17**. The remaining module-level `const`s
(`:27`, `:71`, `:156`, `:170`, `:1080-1082`) are genuine immutable constants — leave
them alone.

### 3.2 ⚠️ The reset sequence is duplicated in exactly FOUR places — and it is 10 lines, not 3

The review calls it a triple; verified, each site resets **eight** variables plus two
function calls. All four are byte-similar:

**Site 1 — `loadConversationHistory` (`:1306`), the "no sessions left" guard, `:1319-1330`:**

```ts
  if (store.sessions.length === 0) {
    abortSse();
    resetDeltaBuffer();
    _liveSessionId = null;
    persistSessionId(null);
    _cursor = 0;
    _hachiMsgId = null;
    _textLineActive = false;
    _lastKnownCumCost = 0;
    _costCumAtTurnStart = 0;
    _spentAtTurnStart = 0;
    useStore.getState().hydrate({ messages: [], streaming: false, inContext: null });
```

**Site 2 — `switchSessionLive` (`:1377`), `:1379-1391`:**

```ts
  abortSse();
  resetDeltaBuffer();
  _hachiMsgId = null;
  _textLineActive = false;

  // 2. Switch session id and reset cursor
  _liveSessionId = sessionId;
  persistSessionId(sessionId); // FIX 2
  _cursor = 0;
  _lastKnownCumCost = 0;
  _costCumAtTurnStart = 0;
  _spentAtTurnStart = 0;
```

Note this one sets `_liveSessionId` to a **new** id rather than `null` — so the
extracted API needs both `reset()` and `resetTo(sessionId)`.

**Site 3 — `deleteSessionLive` (`:1437`), `:1447-1462`:**

```ts
  if (_liveSessionId === sessionId) {
    abortSse();
    resetDeltaBuffer();
    _liveSessionId = null;
    persistSessionId(null); // FIX 2
    _cursor = 0;
    _hachiMsgId = null;
    _textLineActive = false;
    _lastKnownCumCost = 0;
    _costCumAtTurnStart = 0;
    _spentAtTurnStart = 0;
    useStore.getState().hydrate({
      messages: [],
      streaming: false,
      inContext: null,
    });
  }
```

**Site 4 — `newSessionLive` (`:1473`), `:1474-1486`:**

```ts
export function newSessionLive(): void {
  abortSse();
  resetDeltaBuffer();
  _liveSessionId = null;
  persistSessionId(null); // FIX 2: clear persisted id
  _cursor = 0;
  _hachiMsgId = null;
  _textLineActive = false;
  _lastKnownCumCost = 0;
  _costCumAtTurnStart = 0;
  _spentAtTurnStart = 0;
  useStore.getState().hydrate({
    messages: [],
```

Sites 1, 3 and 4 are **identical**. Site 2 differs only in the session id. That is the
strongest possible argument for one function.

### 3.3 The mutables are written from many more places than the four resets

`_textLineActive` alone is assigned at `:113`, `:450`, `:459`, `:468`, `:476`, `:484`,
`:515`, `:536`, `:637`, `:770`, plus the four resets. `_hachiMsgId` at `:707`, `:763`,
`:846`, `:918`, `:974`, `:1007`, plus the resets. `_cursor` at `:358`, `:867`, `:943`,
`:1355`, `:1426`, plus the resets.

So this is not "move four blocks" — the extraction touches roughly 40 assignment sites.
Plan for that; it is why the estimate is a week rather than a day.

### 3.4 The public surface you must not break

`chat.ts` exports 15 functions (`grep -n "^export "`): `buildTurnKey` `:77`,
`startTaskLive` `:748`, `stopStreamingLive` `:994`, `abortSseLive` `:1016`,
`allowLeashLive` `:1028`, `denyLeashLive` `:1044`, `extractInjectedAttachments` `:1179`,
`reconstructMessagesFromEvents` `:1205`, `loadConversationHistory` `:1306`,
`switchSessionLive` `:1377`, `deleteSessionLive` `:1437`, `newSessionLive` `:1473`,
`cleanupEmptySessionsLive` `:1497`, `loadSessions` `:1511`, `loadSessionMessages` `:1557`.

Six of them are statically imported by the store (`store.ts:10-17`). Keep every export
name and signature.

### 3.5 There is already a test file

`frontend/src/lib/data/domains/chat.test.ts` exists — use it, and read it first for the
established mocking of `../client` and `../sse`.

## 4. Reproduce the failure

The duplication is provable in one command; the *consequence* needs the §7 test.

```bash
cd frontend

# 1. Size and the 17 mutables.
wc -l src/lib/data/domains/chat.ts
grep -c "^let " src/lib/data/domains/chat.ts
grep -n "^const _" src/lib/data/domains/chat.ts        # the mutable Set at :1088

# 2. The four reset sites — look for the _cursor/_hachiMsgId/_textLineActive run.
grep -n "_cursor = 0" src/lib/data/domains/chat.ts

# 3. The full write surface you are about to move.
grep -c "_textLineActive = \|_hachiMsgId = \|_cursor = " src/lib/data/domains/chat.ts
```

**You will see now:** (1) 1593 and 16 `let`s plus `_eventsUnavailable`; (2) **four**
hits at `:1324`, `:1387`, `:1452`, `:1478`; (3) a count in the high thirties.

**You should see after the fix:** grep (1) shows a much smaller `chat.ts` with the
mutables gone; grep (2) shows one `reset()` implementation.

**The behavioural proof is §7's test**, which drives two of the four paths and asserts
they leave identical state. Today it passes by luck (the copies happen to agree); the
test's job is to make that luck structural. Be honest about that in the commit message:
you are not fixing an observed bug, you are removing the mechanism that would produce
one.

## 5. What "fixed" looks like

1. Three cohesive modules under `frontend/src/lib/data/domains/chat/`:

   ```ts
   // sessionRef.ts — which session are we on, and where in its event log
   export const sessionRef = {
     get liveSessionId(): string | null { … },
     get cursor(): number { … },
     abortController: null as AbortController | null,
     setSession(id: string | null): void { … },   // also persists to sessionStorage
     advanceCursor(seq: number): void { … },
     reset(): void { … },
   };

   // streamBuffers.ts — everything that accumulates during a stream
   export const streamBuffers = {
     hachiMsgId: null as number | null,
     textLineActive: false,
     reset(): void { … },      // must cancel outstanding rAF handles
   };

   // costMeter.ts — per-turn cost baselines
   export const costMeter = {
     baseline(cumCost: number, spent: number): void { … },
     delta(cumCost: number): number { … },
     reset(): void { … },
   };
   ```

2. **One reset, two entry points**, because §3.2 site 2 needs a target session:

   ```ts
   export function resetLiveSession(nextSessionId: string | null): void {
     abortSse();
     streamBuffers.reset();
     costMeter.reset();
     sessionRef.reset();
     sessionRef.setSession(nextSessionId);   // persists (or clears) sessionStorage
   }
   ```

   All four sites call it. Sites 1/3/4 pass `null`; site 2 passes `sessionId`. The
   `useStore.getState().hydrate({ messages: [], … })` call stays at the call sites —
   it is UI state, not kernel state, and site 2 deliberately does not do it.

3. **`resetDeltaBuffer()`'s rAF cancellation must move intact.** `_rafHandle` (`:173`)
   and `_runLineRafHandle` (`:97`) are `requestAnimationFrame` handles; a reset that
   drops them without cancelling leaks a pending flush that will write into the *next*
   session's message. Read the existing `resetDeltaBuffer` before you rewrite it.

4. Every export in §3.4 keeps its name and signature. **Zero changes outside
   `chat.ts` and its new sibling files** — `store.ts` must not need editing.

5. Observable outcome: no user-visible change. The win is that "reset the live session"
   is one function and the kernel is three inspectable objects.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Create `frontend/src/lib/data/domains/chat/costMeter.ts` first — it is the smallest
   (3 variables, `:271`, `:272`, `:275`) and the most isolated. Move it, run
   `npm run --prefix frontend test`, commit.
3. `sessionRef.ts` next (`:51`, `:52`, `:57`, `:62`, `:1088`). Fold `persistSessionId`
   (`:29`) and the `SESSION_STORAGE_KEY` (`:27`) into it — the session id and its
   persistence belong together. ~15 call sites.
4. `streamBuffers.ts` last (the other 8). This is the risky one: it is live during
   streaming and touches ~25 sites. Move it in one commit, not incrementally.
5. Add `resetLiveSession(nextSessionId)` and replace all four blocks
   (`:1319-1330`, `:1379-1391`, `:1447-1462`, `:1474-1486`) with a call. Preserve each
   site's surrounding `hydrate(...)` exactly — they differ (site 2 has none).
6. Verify nothing outside `chat.ts` changed: `git diff --stat` should show only
   `chat.ts`, the new `chat/` files, and the test.
7. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `frontend/src/lib/data/domains/chat.test.ts` (**existing**)
- **Test name:** `every session-reset path leaves identical kernel state`
- **It must assert:** the real, observed post-reset state after driving the actual
  exported functions — `newSessionLive()` and `deleteSessionLive()` — not that a helper
  was called. The whole finding is that four hand-copied blocks could disagree, so the
  assertion has to compare their *outcomes*.
- **It must FAIL before your fix** with
  `TypeError: getKernelSnapshot is not a function` (the introspection point doesn't
  exist yet) — which is the honest failure: today there is **no way to observe** the
  kernel, and that is half the defect.

```ts
// sketch — append to frontend/src/lib/data/domains/chat.test.ts,
// reusing that file's existing vi.mock() setup for ../client and ../sse.
import { describe, expect, it } from "vitest";

describe("live-session reset", () => {
  it("every session-reset path leaves identical kernel state", async () => {
    // Regression: the ~10-line reset sequence (abortSse, resetDeltaBuffer,
    // _liveSessionId, persistSessionId, _cursor, _hachiMsgId, _textLineActive,
    // _lastKnownCumCost, _costCumAtTurnStart, _spentAtTurnStart) was duplicated
    // by hand in FOUR functions. A fifth caller — or an edit to three of the four
    // — would silently leave a stale cursor and replay a previous session's
    // events into a new one.
    const chat = await import("./chat");

    await chat.switchSessionLive("session-a");
    chat.newSessionLive();
    const afterNew = chat.getKernelSnapshot();

    await chat.switchSessionLive("session-b");
    await chat.deleteSessionLive("session-b");
    const afterDelete = chat.getKernelSnapshot();

    expect(afterDelete).toEqual(afterNew);
    expect(afterNew.liveSessionId).toBeNull();
    expect(afterNew.cursor).toBe(0);
    expect(afterNew.hachiMsgId).toBeNull();
    expect(afterNew.textLineActive).toBe(false);
  });
});
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
>
> Two notes on `getKernelSnapshot`: (1) exporting an introspection function is
> **deliberate and worth it** — the invisibility of this state is part of the finding,
> and a read-only snapshot is how you make it debuggable. Return a frozen plain object;
> do not expose the mutable references. (2) `deleteSessionLive` calls
> `apiSend("DELETE", …)` at `:1442` and returns early on a rejection — make sure the
> mocked `apiSend` **resolves**, or the reset block at `:1447` never runs and your test
> passes for the wrong reason.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and it failed before the fix.
- [ ] `grep -c "^let " frontend/src/lib/data/domains/chat.ts` returns **0**.
- [ ] `grep -n "_cursor = 0" frontend/src/lib/data/domains/chat.ts` returns **one** site (inside `reset()`).
- [ ] All four former reset blocks are a single call to `resetLiveSession(...)`.
- [ ] The rAF handles are **cancelled** on reset, not merely nulled.
- [ ] All 15 exports in §3.4 keep their names and signatures; `git diff --stat` shows no file outside `chat.ts`, `chat/`, and the test.
- [ ] `npm run --prefix frontend typecheck`, `test` and `build` are green.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not move this state into the zustand store.** This is the drift, and it is
  seductive: CF-16 complains the kernel is "invisible to devtools and the store", so
  putting it *in* the store looks like the fix. It is not, for two reasons. (1) This
  state mutates per animation frame — `_rafHandle`, `_lastFlushTs`, `_deltaBuffer` — and
  routing it through zustand would trigger a React re-render cascade on every SSE delta;
  the rAF batching at `:170-174` exists specifically to avoid that. (2) It would land in
  the same store [T-63](T-63-frontend-store-slices.md) is splitting. Extract into
  modules with a `reset()`; that is what CF-16 actually recommends.
- **Do not change any streaming behaviour.** The flush interval (`FLUSH_MIN_INTERVAL_MS`
  `:170`), the run-line cap (`RUN_LINES_MAX` `:156`) and the page-size constants
  (`:1080-1082`) are tuned. Move the mutables; leave the tuning.
- **Do not touch `reconstructMessagesFromEvents`** (`:1205-1305`). It is 100 lines of
  event-replay logic that only *reads* the cursor. It is also where the field-name
  mismatch from [CORRECTIONS.md](CORRECTIONS.md) §3 lives (`:617-624`), which is
  `T-17`'s territory — leave it for that task.
- **Do not fix the false cycle comment** at `:6-11` — that is
  [T-64](T-64-frontend-fix-false-cycle-comment.md). If both land in the same cycle,
  coordinate: you will both be editing this file's first 20 lines.
- **Do not split `chat.ts`'s functions** into more modules than the three state objects.
  A 1,593-line file becoming ten files in one PR is unreviewable. Extract the state,
  stop; the functions can follow later.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not add a dependency without asking.

## 10. Verify

```bash
npm run --prefix frontend typecheck
npm run --prefix frontend test
npm run --prefix frontend build
uv run python scripts/preflight.py       # before you call it done
```

Run the **full** gate, not `--quick`: `--quick` skips the frontend build
(`scripts/preflight.py:134-139`), and `chat.ts` sits inside a static import cycle with
`store.ts` ([T-64](T-64-frontend-fix-false-cycle-comment.md) §3.2-3.3). Splitting it
into new modules changes module-init order, and an init-order break is invisible to
`tsc --noEmit`. Report the **actual** counts.

**Manual check worth doing** if a gateway is already running: start a task, switch
sessions mid-stream, then start a new session. Watch for text from the first session
appearing in the third. That is the failure this task prevents, and no unit test fully
covers it.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — chat.ts's live-session reset was hand-duplicated in four functions

- **Symptom:** No confirmed user-visible failure — this is the mechanism, caught before it fired. Any fifth "start a fresh session" path, or an edit applied to three of the four existing ones, would leave a stale `_cursor` and replay the previous session's SSE events into the new session (cross-session transcript bleed), with none of the responsible state visible in the store or devtools.
- **Root cause:** `frontend/src/lib/data/domains/chat.ts` (1,593 lines) kept 17 module-level mutables (16 `let` + one mutable `Set`) as a runtime kernel. The ~10-line reset sequence — `abortSse()`, `resetDeltaBuffer()`, `_liveSessionId`, `persistSessionId`, `_cursor`, `_hachiMsgId`, `_textLineActive`, `_lastKnownCumCost`, `_costCumAtTurnStart`, `_spentAtTurnStart` — was copied verbatim into four functions (`loadConversationHistory`, `switchSessionLive`, `deleteSessionLive`, `newSessionLive`). Three copies were byte-identical; the fourth differed only in the session id.
- **Fix:** Extracted `sessionRef` / `streamBuffers` / `costMeter` under `lib/data/domains/chat/`, with one `resetLiveSession(nextSessionId)` that all four sites call. rAF handles are cancelled on reset rather than nulled. A read-only `getKernelSnapshot()` makes the state inspectable.
- **Avoid:** duplicated reset logic is a latent state bug with a scheduled arrival date. If more than two call sites reset the same set of variables, that set is an object and the reset is its method — do it before the third copy, not after the fourth.
- **Locked by:** `frontend/src/lib/data/domains/chat.test.ts` — `every session-reset path leaves identical kernel state`
```

## 12. Known traps

- **This state is live during streaming.** `streamBuffers` is mutated from inside the
  SSE event handler on every delta. If you introduce an indirection that allocates per
  access, you will regress streaming performance in a way no test measures. Plain object
  property access is fine; getters that rebuild state are not.
- **rAF handles must be cancelled, not dropped.** `_rafHandle` (`:173`) and
  `_runLineRafHandle` (`:97`). A pending `requestAnimationFrame` callback that fires
  after a reset will write buffered text into whatever message is current — i.e. the new
  session's. Read the existing `resetDeltaBuffer` implementation before rewriting it.
- **`persistSessionId` writes `sessionStorage`** (`:27-29`, key `"hachi.liveSessionId"`),
  and `_liveSessionId` is *initialised from it* at `:51`
  (`readPersistedSessionId()`). Moving the session id without moving its persistence
  produces a kernel whose in-memory and persisted values disagree across a refresh.
  Move them together.
- **Site 2 (`switchSessionLive`) is the odd one out**: it sets a new id rather than
  clearing, and it does **not** call `hydrate({ messages: [] })`. If you fold the
  hydrate into `resetLiveSession`, you will blank the transcript on every session switch
  before the new one loads. Keep hydrate at the call sites.
- **`_eventsUnavailable`** (`:1088`) is a `Set` bound with `const` — the binding is
  constant, the contents are not. It is a per-session negative cache; if `reset()` does
  not clear it, a session that once 404'd on `/events` stays permanently marked
  unavailable across a new session with the same id.
- **`chat.ts` is in a static import cycle with `store.ts`.** See §10 and
  [T-64](T-64-frontend-fix-false-cycle-comment.md) §3.2-3.3. New sibling modules that
  import `useStore` extend that cycle; prefer keeping `useStore` access in `chat.ts`
  itself and having the three kernel modules be store-free. That also makes them
  trivially unit-testable.
- **`store.ts:10-17` statically imports six of your exports.** Renaming or re-pathing any
  of them means editing the store, which §5 forbids for this task.
