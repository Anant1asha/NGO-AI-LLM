# T-22 · Make it structurally impossible for demo fixtures to ship in the production bundle

|  |  |
|---|---|
| **Source finding** | CF-4(e) / CF-16 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). The review's `store.ts:1155-1586` range is **wrong** — see [CORRECTIONS.md](CORRECTIONS.md) §11 and §3.3 below |
| **Severity** | **P2** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none (independent) |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium (one build-tooling decision in §5) |
| **Files you will touch** | `frontend/src/lib/store/store.ts`, `frontend/src/lib/data/client.ts`, `frontend/vite.config.ts`, `scripts/preflight.py` (or a new `scripts/check_bundle.py`), `docs/bug-bank.md` |

---

## 1. Brief

`store.ts` statically imports 394 lines of scripted demo fixtures and references them
**unconditionally** in ternaries, so the bundler cannot tree-shake them: **every
production build of the Hachi web UI contains the demo fiction**, including a hardcoded
email to `priya@studio.co` and a fabricated `$0.02` cost. Thirteen store actions also
carry a scripted mock branch one boolean away from real user paths.

When you are done, fixture data cannot enter a production bundle at all — enforced by a
check in the gate, not by discipline.

## 2. Why this matters

Two distinct risks, and the second is the one to fix first.

1. **Payload.** ~400 lines of fixtures plus 13 inline mock scripts ship to every user.
   Minor.
2. **Blast radius.** The mock branches are gated on `dataMode === "live"` — a **runtime
   boolean**, in the same function, in the same file, as the real behaviour. Any bug
   that leaves `dataMode` unset, any refactor that inverts a condition, and a real user
   sees Hachi confidently claim it emailed `priya@studio.co` for $0.02. That is not a
   hypothetical class of bug in this repo: the store test at
   `frontend/src/lib/store/store.test.ts:1-12` exists **specifically** to pin the
   invariant that the scripted demo run queue never fires in live mode, because someone
   already had to investigate whether it did.

A build-time guard converts "we tested that it doesn't fire" into "it isn't there."

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The static import — `frontend/src/lib/store/store.ts:22-53`

The import ends at `:53`:

```ts
  initialTaskSpent,
} from "../data/fixtures";
```

`frontend/src/lib/data/fixtures.ts` is **394 lines**, and `store.ts:53` is its **only**
importer in the entire app (`rg -rn "data/fixtures" frontend/src` → one hit).

### 3.2 Why it cannot be tree-shaken — `frontend/src/lib/store/store.ts:384-424`

Every binding is referenced unconditionally inside `domainDefaults()`:

```ts
const domainDefaults = (): Omit<State, "operator" | "theme"> => ({
  dataMode: USE_MOCKS ? "mock" : "live",
  spent: USE_MOCKS ? initialSpent : 0,
  budget: USE_MOCKS ? initialBudget : 5.0,
  taskSpent: USE_MOCKS ? initialTaskSpent : 0,
  approvals: USE_MOCKS ? initApprovals() : [],
  …
  auditLog: USE_MOCKS ? auditLog : [],          // :416
  recall: USE_MOCKS ? recall : [],
  sessions: USE_MOCKS ? sessions : [],
  skillUsage: USE_MOCKS ? skillUsage : [],
  …
  opTools: USE_MOCKS ? opTools : [],            // :424
```

~30 ternaries. `USE_MOCKS` is a **computed** export, not a literal
(`frontend/src/lib/data/client.ts:30`):

```ts
export const USE_MOCKS: boolean = String(env.VITE_HACHI_USE_MOCKS).toLowerCase() === "true";
```

Vite statically replaces `import.meta.env.VITE_*`, but `String(x).toLowerCase() === "true"`
is not folded to a literal across the module boundary — so Rollup cannot prove the
`USE_MOCKS ?` arms are dead, every fixture identifier stays live, and the whole module
is retained. **That is the mechanism; fixing it is the job.**

### 3.3 Thirteen mock forks — `store.ts`, verified list

The review's cited range (`1155-1586`) is wrong. The verified forks, each an
`if (get().dataMode === "live") { … return; }` early-exit followed by scripted mock
behaviour:

| # | Action | Live-branch line |
|---|---|---|
| 1 | `startTask` (send) | `:1205` |
| 2 | `retryLastMessage` | `:1310` |
| 3 | `stopStreaming` | `:1332` |
| 4 | `icAllow` | `:1349` |
| 5 | `icAlwaysAllow` | `:1395` |
| 6 | `icDeny` | `:1421` |
| 7 | `openRun` | `:1528` |
| 8 | `runAllowLeash` | `:1598` |
| 9 | `runAlwaysAllow` | `:1622` |
| 10 | `runDenyLeash` | `:1670` |
| 11 | `stopRun` | `:1713` |
| 12 | `switchSession` | `:1756` |
| 13 | `newSession` | `:1772` |

Range is **`:1205-1772`**, and the file is 1,807 lines.

**`store.ts:802` is NOT one of them — do not touch it.** It is the BB-77 fix:

```ts
        tickApprovals: () => {
          // Live approvals have no server-sent expiry (expiresAt=0). Only mock
          // data uses countdowns, so skip the expiry pass entirely in live mode.
          if (get().dataMode === "live") return;
```

Same syntax, different purpose: a correctness guard locked by
`store.test.ts:117-159`. Removing it re-opens BB-77 (live approvals auto-declining in
~1 second).

### 3.4 What the fiction actually contains — `store.ts:1354-1386`, `icAllow`'s mock branch

```ts
          // ── Mock mode: keep existing simulated implementation ──────────────
          const ic = get().inContext;
          if (!ic) return;
          const id = ic.msgId;
          set({ inContext: null });
          addCard(id, {
            key: "send",
            icon: "send",
            title: "Sending email to Priya",
            status: "working",
            cost: 0.0,
            tool: "gmail.send(to='priya@studio.co')",
            detail:
              "To: priya@studio.co\nRe: Q3 deck feedback\n\"Here's the latest — your notes are folded in. Happy to walk through it tomorrow.\"",
            expanded: false,
          });
          setTimeout(() => {
            setCard(id, "send", { status: "done", title: "Sent email to Priya", cost: 0.02 });
```

A hardcoded recipient, a hardcoded email body, and a **fabricated `$0.02` cost** that is
added to `spent` and `taskSpent` at `:1378-1381`. This string is in your production
bundle today — which conveniently makes it the perfect canary for §5.

`startTask`'s mock branch (`:1248-1284`) is the matching setup, ending by planting the
in-context leash *"Hachi wants to send an email to Priya"* (`:1271-1277`).

### 3.5 The flag — `frontend/src/lib/data/client.ts:24-30`

```ts
const env = import.meta.env as Record<string, string | undefined>;

/** Base path/origin for every gateway call. Defaults to the proxied `/api`. */
export const API_BASE: string = (env.VITE_HACHI_GATEWAY_URL || "/api").replace(/\/$/, "");

/** When true, wired domains keep fixtures instead of calling the gateway. */
export const USE_MOCKS: boolean = String(env.VITE_HACHI_USE_MOCKS).toLowerCase() === "true";
```

feeding `dataMode` at `store.ts:384`.

### 3.6 The gate has no bundle check — `scripts/preflight.py:134-139`

```python
    Step(
        "frontend build",
        [["npm", "run", "--prefix", "frontend", "build"]],
        in_quick=False,
        needs_frontend=True,
    ),
```

The build runs; **nothing inspects its output.**

## 4. Reproduce the failure

Fully reproducible, and the proof is a single grep of the built bundle.

```bash
# Build exactly as production does (VITE_HACHI_USE_MOCKS unset).
npm run --prefix frontend build

# Search the emitted assets for demo fiction that must never ship.
rg -o "priya@studio\.co" frontend/dist/assets/*.js | head
rg -c "Sending email to Priya|Summarised 6 PRs" frontend/dist/assets/*.js
```

**You will see now:** matches. `priya@studio.co`, `"Sending email to Priya"` and the
fixture corpus are all present in the production bundle despite `USE_MOCKS` being false
at runtime.

**You should see after the fix:** **zero** matches, and `scripts/preflight.py` failing
loudly if anyone reintroduces them.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — how to keep fixtures out
>
> **(a) Guard only: add a bundle assertion to the gate.**
> A `check_bundle.py` step that greps `frontend/dist` for known fixture markers and
> exits non-zero.
> *For:* ~30 lines, zero risk, immediately makes the property enforceable.
> *Against:* on its own it turns the gate **red** until someone actually removes the
> fixtures — a guard without a fix is a blocked build.
>
> **(b) Isolate + guard — RECOMMENDED.**
> Make the fixture module reachable only through a **dynamic import** taken on the
> mock path, so Rollup emits it as a separate chunk that a production build never
> references; then add the guard from (a) to keep it that way.
>
> ```ts
> // store.ts — mock seeding becomes an opt-in async step, not a static import
> export async function seedMockFixtures(): Promise<void> {
>   if (!USE_MOCKS) return;
>   const f = await import("../data/fixtures");
>   useStore.getState().hydrate({ … });
> }
> ```
>
> `domainDefaults()` then returns the **live** defaults unconditionally (`[]`, `0`,
> `5.0`) — i.e. exactly the `: else` arm of all ~30 ternaries — and mock mode seeds on
> top at boot.
> *For:* structurally correct; the guard from (a) then passes and *stays* passing;
> the 13 mock forks can be left alone for now. *Against:* mock-mode seeding becomes
> asynchronous, so a mock-mode test that reads the store synchronously at import time
> would need to await the seed.
>
> **(c) Delete mock mode entirely.**
> *For:* smallest final state. *Against:* out of scope and destructive — mock mode is
> real functionality used for offline UI work
> ([CLAUDE.md](../../../../CLAUDE.md) Rule 3: never delete functionality unless told).
>
> **Recommendation: (b).** Land the isolation and the guard **in the same commit** so
> the gate is never red between them.

Target state:

1. `frontend/src/lib/data/fixtures.ts` has **zero static importers**. Verified by
   `rg -rn "from \".*data/fixtures\"" frontend/src` returning nothing.
2. `domainDefaults()` (`store.ts:383-427`) contains **no `USE_MOCKS ?` ternaries** —
   it returns live defaults. `dataMode: USE_MOCKS ? "mock" : "live"` may stay (it is a
   boolean, not fixture data).
3. Mock seeding happens once, behind `await import(...)`, on the mock path only.
4. A **blocking** gate step fails the build when a production bundle contains any
   fixture marker. Add to `scripts/preflight.py` `STEPS`, immediately after the existing
   `"frontend build"` step (`:134-139`) so it runs against fresh output:

   ```python
       Step(
           "frontend bundle purity (no demo fixtures)",
           [["uv", "run", "python", "scripts/check_bundle.py"]],
           in_quick=False,
           needs_frontend=True,
       ),
   ```

   `scripts/check_bundle.py` scans `frontend/dist/assets/*.js` for a small, explicit
   marker list and prints every hit with its file. Start with:
   `priya@studio.co`, `Sending email to Priya`, `Summarised 6 PRs`,
   `reader-1`, `gmail.send(to=`. Keep the list in one obvious constant with a comment
   explaining that adding demo strings means adding them here.
5. The 13 mock forks (§3.3) are **untouched** in this task — see §9.

## 6. Steps

1. Write the regression check from §7 and watch it **fail** against a current
   production build.
2. Add `scripts/check_bundle.py` with the marker list and a clear failure message.
3. Register it in `scripts/preflight.py` `STEPS` after `"frontend build"`.
4. Rewrite `domainDefaults()` (`store.ts:383-427`) to return live defaults with no
   fixture references.
5. Add `seedMockFixtures()` using a dynamic `import("../data/fixtures")`, and call it
   from wherever mock mode boots — find it with `rg -n "bootstrapLiveData\|USE_MOCKS"
   frontend/src` and put the seed alongside, guarded by `USE_MOCKS`.
6. Delete the now-unused static import block (`store.ts:22-53`).
7. `npm run --prefix frontend build` and re-run the grep from §4 — expect zero hits.
8. Run mock mode manually (`VITE_HACHI_USE_MOCKS=true npm run --prefix frontend dev`) and
   confirm the demo still works. **Do not skip this** — it is the functionality you must
   not break.
9. Run the full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the check, watch it FAIL, then write the fix, then watch it PASS.

This one is unusual: the regression lock is a **build artifact check**, not a unit test,
because the property being protected ("this string is not in the shipped bundle") cannot
be expressed in vitest. Write both.

- **File 1 (the lock):** `scripts/check_bundle.py` (**new**), registered in
  `scripts/preflight.py`
- **File 2 (the unit test):** `tests/test_bundle_guard.py` (**new**) — pins the checker
  itself so it cannot silently become a no-op (e.g. by pointing at a directory that does
  not exist and passing vacuously).
- **They must assert:** the real, observed bundle contents — that no file under
  `frontend/dist/assets/` contains any marker, **and** that the checker fails loudly when
  `frontend/dist` is missing or contains no JS (rather than passing).
- **It must FAIL before your fix** with a message naming the file and the marker, e.g.
  `frontend/dist/assets/index-abc123.js contains demo fixture marker 'priya@studio.co'`.

```python
# tests/test_bundle_guard.py — sketch; adapt to the repo's existing fixtures
def test_checker_flags_a_marker(tmp_path) -> None:
    """The guard must actually detect demo fiction, not pass vacuously."""
    from scripts.check_bundle import find_markers

    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-deadbeef.js").write_text("const a='gmail.send(to=\\'priya@studio.co\\')';")

    hits = find_markers(tmp_path)
    assert hits, "guard did not flag a known demo-fixture marker"


def test_checker_refuses_to_pass_on_an_empty_dist(tmp_path) -> None:
    """A missing or empty bundle must be an error, not a silent pass."""
    from scripts.check_bundle import find_markers

    with pytest.raises(FileNotFoundError):
        find_markers(tmp_path / "does-not-exist")
```

> If your check passes before you write the fix, the check is wrong. Do not proceed.
> The most likely cause: you ran it against a stale or absent `frontend/dist`. Build
> first, then check — that is exactly what `test_checker_refuses_to_pass_on_an_empty_dist`
> is for.

## 8. Acceptance criteria

- [ ] The guard from §7 exists, is registered in `scripts/preflight.py`, and **failed** against a pre-fix production build naming a real marker.
- [ ] `rg -rn "data/fixtures" frontend/src` returns **no static import** (only the dynamic `import(...)`).
- [ ] `rg -n "USE_MOCKS \?" frontend/src/lib/store/store.ts` returns at most the `dataMode` line.
- [ ] `npm run --prefix frontend build && rg -c "priya@studio\.co" frontend/dist/assets/*.js` returns **zero**.
- [ ] Mock mode still works end-to-end: `VITE_HACHI_USE_MOCKS=true` seeds fixtures and the demo run plays. **Manually verified — say so in your report.**
- [ ] `store.ts:802` (`tickApprovals`, BB-77) is **unchanged**.
- [ ] All 13 mock forks (§3.3) are **unchanged**.
- [ ] `npm run --prefix frontend typecheck` is clean and `store.test.ts` passes.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not remove the 13 mock branches by hand.** They live inside 13 large store
  actions, and moving mock behaviour behind the data layer (mock adapters) is the
  Wave-2 CF-16 store-slice work. Trimming them here means a ~600-line diff through the
  most churn-prone file in the frontend, with one route-level test to catch mistakes.
  **Scope this task to the bundle guard plus fixture isolation.** Say so in the commit
  message so the next reader knows the branches were left deliberately.
- **Do not touch `store.ts:802`.** It looks identical to a mock fork and it is the BB-77
  fix (§3.3). Removing it makes live approvals auto-decline again.
- **Do not delete `fixtures.ts` or mock mode.** It is real functionality for offline UI
  work ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- **Do not start splitting the store into slices.** CF-16, Wave 2.
- **Do not add a bundle-analyzer dependency** (`rollup-plugin-visualizer` and friends).
  A grep over `dist/assets/*.js` needs nothing new
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 3: don't add a dependency without asking).
- **Do not change `VITE_HACHI_USE_MOCKS`'s name or semantics.** It is documented in
  `client.ts:16-21` and used by dev workflows.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).

## 10. Verify

```bash
npm run --prefix frontend typecheck
npm run --prefix frontend test                # vitest
npm run --prefix frontend build               # then re-run the §4 grep
uv run python scripts/preflight.py --quick    # inner loop (skips the build + guard)
uv run python scripts/preflight.py            # before you call it done — this runs the guard
```

Note `--quick` **skips** the frontend build, and therefore your new guard. The guard only
runs on the full gate. Report the **actual** pass/fail counts, and state explicitly that
you re-ran the §4 grep against a fresh build. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Demo fixtures shipped in every production web bundle (untree-shakable by construction)

- **Symptom:** `npm run build` with `VITE_HACHI_USE_MOCKS` unset still emitted the entire 394-line fixture corpus plus scripted demo strings — including `gmail.send(to='priya@studio.co')`, "Sending email to Priya" and a fabricated $0.02 cost — into the production bundle.
- **Root cause:** `frontend/src/lib/store/store.ts` statically imported `../data/fixtures` and referenced every binding unconditionally inside `domainDefaults()` (~30 `USE_MOCKS ? fixture : liveDefault` ternaries). `USE_MOCKS` is a *computed* export (`String(import.meta.env.VITE_HACHI_USE_MOCKS).toLowerCase() === "true"`), not a literal, so Rollup could not constant-fold the ternaries, could not prove the fixture arms dead, and retained the whole module. Nothing in the gate inspected build output.
- **Fix:** `domainDefaults()` now returns live defaults unconditionally; mock seeding moved behind a dynamic `import("../data/fixtures")` on the `USE_MOCKS` path, so the fixtures become a chunk a production build never references. Added `scripts/check_bundle.py` as a blocking preflight step that greps `frontend/dist/assets/*.js` for demo markers and fails the gate on any hit.
- **Avoid:** a `flag ? demoData : realData` ternary keeps demoData alive in the bundle unless the flag folds to a literal — put demo data behind a dynamic import, and assert on the built artifact rather than trusting the bundler.
- **Locked by:** `scripts/check_bundle.py` (preflight step "frontend bundle purity"), pinned by `tests/test_bundle_guard.py` — `test_checker_flags_a_marker`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`store.ts:802` is a trap by design.** `if (get().dataMode === "live") return;` in
  `tickApprovals` is the BB-77 guard, not a mock fork. Its `store.test.ts:117-159` lock
  will catch you, but read the comment first rather than after.
- **Guard-before-fix turns the gate red.** Land `scripts/check_bundle.py` and the
  fixture isolation in **one commit**, or the repo has a failing blocking gate in
  between.
- **`--quick` does not run your guard.** It skips `"frontend build"` (`in_quick=False`,
  `preflight.py:137`) and therefore the step after it. Do not conclude "green" from a
  quick run.
- **`store.test.ts` runs in mock-adjacent territory.** It hydrates `dataMode: "live"`
  explicitly (`store.test.ts:43`) and mocks `../data/client` with `USE_MOCKS: false`
  (`:17-26`), so it should be unaffected. **If it goes red, read it before editing** —
  its opening comment (`:1-12`) explains that it exists to pin the scripted-queue
  invariant, and adjusting it to accommodate a lazy seed is a **test-setup update, not a
  weakening** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Say which it was in the
  commit message.
- **`initApprovals()` is a function, not a constant** (`fixtures.ts:46`) — it computes
  `expiresAt` from `Date.now()` at call time. Under a lazy seed it is called later than
  before; that is fine for the demo but worth knowing if a mock countdown looks off.
- **Marker list maintenance.** A guard whose marker list nobody updates rots into a
  no-op. Put the list in one named constant with a comment: *"if you add a demo string
  to fixtures.ts or a mock branch, add a marker here."*
- **`frontend/dist` may be gitignored and stale.** The guard must fail on a missing or
  empty `dist` rather than pass vacuously — that is what the second test in §7 pins.
