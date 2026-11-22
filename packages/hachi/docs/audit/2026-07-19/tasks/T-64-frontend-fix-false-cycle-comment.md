# T-64 · Fix the false "no cycle" comment in `chat.ts` (and decide how to stop it drifting again)

|  |  |
|---|---|
| **Source finding** | CF-16 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P3 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 hour for the comment. **The lint rule is NOT an hour — read §5.** |
| **Difficulty** | Low (mechanical) for the comment; the guard needs a decision |
| **Files you will touch** | `frontend/src/lib/data/domains/chat.ts`, and (guard) `frontend/src/lib/module-graph.test.ts` (new) |
| **See also** | [T-63](T-63-frontend-store-slices.md), [T-65](T-65-chat-ts-kernel-extraction.md) |

---

## 1. Brief

`chat.ts`'s header comment asserts there is no circular import "because `store.ts` never
statically imports `chat.ts`". `store.ts` statically imports six symbols from `chat.ts`
on lines 10–17. The comment is directly, checkably false.

Trivial to fix and slightly embarrassing — but the reason it is worth a task is that a
**wrong** architectural comment is worse than none: the next person reasoning about
module-init order will trust it, and the cycle it denies is real and load-bearing.

## 2. Why this matters

The comment describes a deliberate strategy ("store.ts calls chat.ts via dynamic
`import()`") that the code no longer follows. Somebody later added six static imports
and did not update the note. That is the CF-17 pattern in miniature: the codebase's
self-description drifting from the codebase, in a file where the drift affects
*module-initialisation order*.

It matters concretely for [T-63](T-63-frontend-store-slices.md): splitting the store
changes init order, and a real cycle that currently happens to resolve can become a
temporal-dead-zone error at runtime — the class of bug that `tsc --noEmit` does not
catch and only the production build or a real page load reveals. Anyone doing that
refactor will read this comment first and conclude there is no cycle to worry about.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**

### 3.1 The claim — `frontend/src/lib/data/domains/chat.ts:1-11`

```ts
// ============================================================
// Hachi Web App — chat / sessions / streaming domain
// Wires: POST /sessions (lazy, once), POST /sessions/{id}/messages,
//        GET /sessions/{id}/stream (SSE), GET /sessions?limit=10
//
// Circular-import strategy:
//   store.ts → (dynamic import) → chat.ts → useStore
//   store.ts live-mode branches call chat.ts functions via dynamic import().
//   chat.ts imports useStore directly for reading/writing state (no cycle
//   because store.ts never statically imports chat.ts).
// ============================================================
```

The false claim is on `:9-10`.

### 3.2 The contradiction — `frontend/src/lib/store/store.ts:10-17`

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

Six symbols, static, top of file. All six exist in `chat.ts`:
`startTaskLive` `:748`, `stopStreamingLive` `:994`, `allowLeashLive` `:1028`,
`denyLeashLive` `:1044`, `switchSessionLive` `:1377`, `newSessionLive` `:1473`.

### 3.3 The other half of the cycle — `chat.ts:16-17`

```ts
import { useStore } from "../../store/store";
import { approveFirstMatching, denyFirstMatching, loadApprovals } from "./approvals";
```

So the real graph is `store.ts ⇄ chat.ts`, statically, in both directions — plus
`approvals.ts → store.ts` (`approvals.ts:9`), making `store → chat → approvals → store`
a second, three-node cycle.

It works today because the imports are used inside function bodies, not at module
top-level, so by the time anything is called both modules are initialised. That is a
property of the current code, not a guarantee.

### 3.4 ⚠️ There is no ESLint in this project

The review (and the audit brief) recommend adding the `import/no-cycle` rule. Verified:

```bash
ls -a frontend | grep -i eslint     # -> nothing
```

- No `.eslintrc*`, no `eslint.config.js`.
- `frontend/package.json` devDependencies: `@tanstack/router-plugin`,
  `@testing-library/jest-dom`, `@testing-library/react`, `@types/react`,
  `@types/react-dom`, `@vitejs/plugin-react`, `jsdom`, `openapi-typescript`,
  `typescript`, `vite`, `vitest`. **No `eslint`, no `eslint-plugin-import`.**
- `scripts` are `dev` / `build` / `test` / `preview` / `typecheck` / `generate:api` /
  `check:api`. **No `lint` script.**
- `scripts/preflight.py:118-139` runs frontend typecheck, vitest, the OpenAPI contract
  check and the build. No lint step exists to hang a rule on.

So "add the `import/no-cycle` ESLint rule" means: add **two** new dev dependencies,
author a config for a 100-file TypeScript+React codebase, add a script, and add a
preflight step. That is not an hour, and it is a
[CLAUDE.md](../../../../CLAUDE.md) Rule 3 dependency decision. §5 gives a
zero-dependency alternative.

## 4. Reproduce the failure

One command. The comment and its contradiction are eleven files apart but both are
plain text.

```bash
cd frontend
sed -n '6,11p' src/lib/data/domains/chat.ts        # the claim
sed -n '10,17p' src/lib/store/store.ts             # the contradiction
```

**You will see now:** a comment saying "store.ts never statically imports chat.ts",
and immediately below it a static `import { … } from "../data/domains/chat";`.

**You should see after the fix:** a comment that describes the real graph.

There is no runtime failure to reproduce — the cycle resolves today. Say that; do not
imply the app is broken.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — only for the guard, not the comment
>
> The comment fix is unconditional: do it. The question is how to stop it drifting again.
>
> **(a) A vitest module-graph assertion — RECOMMENDED, zero new dependencies.**
> A test that parses the import statements of the store/domain modules and asserts the
> known cycles are exactly the documented ones. Runs in the existing `vitest` step
> (`scripts/preflight.py:123`), which is already blocking.
> *For:* no dependency decision, no config to maintain, fails in the gate, and the
> assertion is *specific* — it pins the documented set rather than banning cycles the
> codebase currently has. *Against:* hand-rolled; less thorough than a real
> import-graph linter.
>
> **(b) Adopt ESLint + `eslint-plugin-import` with `import/no-cycle`.**
> *For:* the real tool; catches cycles this file doesn't know about; opens the door to
> other useful rules. *Against:* **two new dev dependencies** (Rule 3 — ask first), a
> config for a 100-file React/TS codebase, a new script, a new preflight step — and the
> rule will **immediately fail** on the two existing cycles in §3.3, so you must either
> fix them (a real refactor, out of scope here) or add suppressions, which is where lint
> rules go to die. This is a legitimate project; it is not this task.
>
> **(c) Comment only, no guard.** *For:* honest and 15 minutes. *Against:* the comment
> drifted once and will drift again.
>
> **Recommendation: (a).** If the team wants ESLint, propose it separately — do not
> smuggle a toolchain decision in under a comment fix.

Target state:

1. `chat.ts:6-11` describes the actual graph. Something like:

   ```ts
   // Circular-import strategy:
   //   store.ts ⇄ chat.ts — BOTH directions are static imports today:
   //     store.ts:10-17 imports the *Live functions from this module;
   //     this module imports useStore from ../../store/store.
   //   There is a second cycle via approvals.ts (store → chat → approvals → store).
   //   These resolve only because every cross-module reference happens inside a
   //   function body, never at module top level. Keep it that way: a top-level
   //   use of an imported binding on either side becomes a TDZ error at runtime
   //   that `tsc --noEmit` will NOT catch (only the production build or a real
   //   page load will).
   ```

   Do not delete the original strategy note — mark it as historical. Rule 3 forbids
   deleting comments; the *point* of this task is that the record should be accurate,
   and "this used to be dynamic" is part of the accurate record.

2. Under (a): `frontend/src/lib/module-graph.test.ts` asserts the documented cycle set.

3. Observable outcome: zero behaviour change. The next person to reason about init order
   is reasoning from true premises.

## 6. Steps

1. Write the guard test from §7 and watch it **fail** (it should fail because the
   documented set in the test doesn't match reality yet — or, if you write the test
   against reality first, watch it fail against the comment's claim; either way, do not
   write the assertion after the fact to match whatever you find).
2. Rewrite `chat.ts:6-11`, preserving the historical note.
3. Grep for the same claim elsewhere — the review says "comments **claim**", plural:
   `grep -rn "no cycle\|never statically imports\|circular" frontend/src/`. Fix every
   instance you find, not just this one.
4. Add the module-graph test (option (a)).
5. `npm run --prefix frontend typecheck && npm run --prefix frontend test`.
6. Run `uv run python scripts/preflight.py` (**full**) and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**

A comment cannot be unit-tested, so the test pins the *fact the comment asserts*. That
is the honest translation of the rule here.

- **File:** `frontend/src/lib/module-graph.test.ts` (**new**)
- **Test name:** `store.ts and chat.ts import each other statically — keep the comment honest`
- **It must assert:** the real, observed import statements read from the source files on
  disk. Not a mock, not a hand-maintained list of module names.
- **It must FAIL before your fix** if you write it as the comment claims —
  `AssertionError: expected store.ts NOT to statically import chat.ts, but it imports allowLeashLive, denyLeashLive, newSessionLive, startTaskLive, stopStreamingLive, switchSessionLive`.
  That failure *is* the proof the comment is wrong; capture it in the commit message.

```ts
// sketch — frontend/src/lib/module-graph.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function staticImportsOf(file: string): string[] {
  const src = readFileSync(resolve(__dirname, file), "utf-8");
  // Static `import … from "…"` only — dynamic import() is deliberately excluded,
  // because a dynamic import does NOT create an initialisation-order cycle.
  return [...src.matchAll(/^import\s[\s\S]*?from\s+["']([^"']+)["'];/gm)].map((m) => m[1]);
}

describe("module graph", () => {
  it("store.ts and chat.ts import each other statically — keep the comment honest", () => {
    // If this ever stops being true, UPDATE THE COMMENT at
    // src/lib/data/domains/chat.ts:6-11 in the same commit.
    expect(staticImportsOf("store/store.ts")).toContain("../data/domains/chat");
    expect(staticImportsOf("data/domains/chat.ts")).toContain("../../store/store");
  });

  it("the store → chat → approvals → store cycle is the documented one", () => {
    expect(staticImportsOf("data/domains/chat.ts")).toContain("./approvals");
    expect(staticImportsOf("data/domains/approvals.ts")).toContain("../../store/store");
  });
});
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Concretely: write the assertions *as the comment claims* first
> (`expect(...).not.toContain(...)`), watch them fail, then invert them to match reality
> and fix the comment. Writing the test to match reality from the start proves nothing.

## 8. Acceptance criteria

- [ ] The guard test from §7 exists, and its comment-shaped form failed first.
- [ ] `grep -rn "no cycle\|never statically imports" frontend/src/` returns nothing false.
- [ ] The original strategy note is preserved as history, not deleted ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- [ ] The comment names both cycles (`store ⇄ chat` and `store → chat → approvals → store`) and the TDZ hazard.
- [ ] `npm run --prefix frontend typecheck` and `test` are green.
- [ ] **No new dependency was added** (option (a)), or a dependency was explicitly approved first (option (b)).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] No `docs/bug-bank.md` entry is required — see §11.

## 9. Out of scope — do NOT

- **Do not break the cycle.** This is the drift, and it is a big one: having proven the
  cycle is real, the obvious next move is to remove it — dynamic-import the six
  functions again, or invert the dependency. That is a genuine refactor of the store's
  live-mode dispatch, it interacts directly with
  [T-63](T-63-frontend-store-slices.md), and it can change module-init order in ways
  only the production build reveals. **Fix the comment. Document the cycle. Stop.**
- **Do not install ESLint on your own initiative.** §3.4 shows there is none;
  [CLAUDE.md](../../../../CLAUDE.md) Rule 3 says don't add a dependency without asking.
  Propose it as its own task.
- **Do not "tidy" the rest of `chat.ts`'s header.** The Wires: block at `:3-4` is
  accurate and useful.
- **Do not touch `chat.ts`'s module-level state** — that is
  [T-65](T-65-chat-ts-kernel-extraction.md), and it is a week of work in the same file.
  Two people editing `chat.ts` in the same cycle will conflict; check whether T-65 is in
  flight before you start.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).

## 10. Verify

```bash
npm run --prefix frontend typecheck
npm run --prefix frontend test
npm run --prefix frontend build          # the step that would catch a real cycle break
uv run python scripts/preflight.py       # before you call it done
```

Run the **full** gate rather than `--quick`: `--quick` skips the frontend build
(`scripts/preflight.py:134-139`), and the build is the only step that would surface a
module-init problem if you accidentally changed the graph. Report the **actual**
counts.

## 11. Bug bank entry

**No bug-bank entry is required for this task** — no user-visible defect existed and
nothing regressed. The bug bank is for autopsies, and inflating it with a comment fix
makes the SessionStart hook's top-entries injection less useful.

If you (or a reviewer) disagree, the entry would be:

```markdown
### BB-N — Architectural comment asserted the opposite of the code

- **Symptom:** `frontend/src/lib/data/domains/chat.ts:9-10` stated "no cycle because store.ts never statically imports chat.ts", while `frontend/src/lib/store/store.ts:10-17` statically imported six symbols from it. A second cycle (store → chat → approvals → store) was undocumented.
- **Root cause:** The dynamic-import strategy the comment described was real once; static imports were added later without updating the note.
- **Fix:** Comment corrected to describe both real cycles and the TDZ hazard, with the historical strategy preserved. A vitest module-graph assertion now fails if the graph changes without the comment changing.
- **Avoid:** an architectural comment that cannot be checked will drift. If a comment asserts a structural fact, assert the same fact in a test in the same commit.
- **Locked by:** `frontend/src/lib/module-graph.test.ts` — `store.ts and chat.ts import each other statically`
```

## 12. Known traps

- **`--quick` skips the frontend build.** See §10. A cycle problem is invisible to
  `tsc --noEmit`.
- **Dynamic `import()` does not create an init-order cycle**, and the regex in §7
  deliberately matches only static `import … from` statements. If you "improve" it to
  catch `import(...)` too, the test starts asserting things that are not hazards.
- **`__dirname` in a Vite/vitest ESM context** may be undefined depending on config.
  If it is, use `new URL(".", import.meta.url)` instead — check how other tests in
  `frontend/src` resolve paths before assuming.
- **`chat.ts` is 1,593 lines and is [T-65](T-65-chat-ts-kernel-extraction.md)'s
  subject.** Coordinate; a one-line comment change that lands under a week-long
  extraction is a guaranteed conflict.
- **The claim may exist in more than one place.** The review says "comments claim"
  (plural). Run the grep in §6 step 3 rather than fixing only the line quoted here.
