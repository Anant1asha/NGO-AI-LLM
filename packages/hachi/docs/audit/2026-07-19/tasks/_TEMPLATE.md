# T-NN · <imperative title: "Fix X", "Extract Y", "Delete Z">

|  |  |
|---|---|
| **Source finding** | CF-N — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P0 \| P1 \| P2 \| P3 |
| **Wave** | 1 (gate-blocking, before public v1) \| 2 (fast-follow, pre-v1.1) |
| **Depends on** | T-XX — *do not start until it has landed* \| none |
| **Blocks** | T-YY \| nothing |
| **Effort** | ~N hours \| ~N days |
| **Difficulty** | Low (mechanical) \| Medium \| High (needs design judgement — read §9) |
| **Files you will touch** | `src/...`, `tests/...` |

---

## 1. Brief

<Two or three sentences. What is broken, and what will be true when you are done.
A reader who stops here must still know what to do.>

## 2. Why this matters

<One paragraph of motivation. This exists so you do not "fix" it in a direction that
misses the point. If the fix you are about to write does not serve this paragraph,
stop and re-read.>

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

<For each site: `path:line`, then the actual quoted code in a fenced block.
Never paraphrase code the implementer has to find.>

## 4. Reproduce the failure

<Exact commands. Copy-pasteable. Then: what you will see now (broken), and what you
would see if it worked. If the failure is not reproducible from a shell — say so
explicitly and give the code-reading path that proves it instead.>

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
```

**You will see now:** <broken output>
**You should see after the fix:** <good output>

## 5. What "fixed" looks like

<The target state, concretely. Include the shape of new signatures/fields/files.
If there is a decision to make, it is made HERE by the task author — not left to
the implementer — unless §9 explicitly flags it as a judgement call.>

## 6. Steps

1. …
2. …
3. …

<Ordered, small, each independently checkable. A step that says "refactor X" is
too big — say what moves where.>

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/<path>.py` (new \| existing)
- **Test name:** `test_<explicit_name>`
- **It must assert:** <the real, observed behaviour — not a mock's return value>
- **It must FAIL before your fix** with: <the expected failure message>

```python
# sketch — adapt to the repo's existing fixtures
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix.
- [ ] <objectively checkable outcome>
- [ ] <objectively checkable outcome>
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- Do not <the adjacent thing a well-meaning agent would drift into>.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — <one-line symptom>

- **Symptom:** …
- **Root cause:** …
- **Fix:** …
- **Avoid:** <the one-line rule that stops this recurring>
- **Locked by:** `tests/<file>.py` — `test_<name>`
```

## 12. Known traps

<Repo-specific landmines for THIS task. Pull from docs/bug-bank.md. Common ones:>

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend
  API types, or CI fails.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots.
