# T-69 · Crank the mypy ratchet — harvest 65 already-clean files, then burn down the rest

|  |  |
|---|---|
| **Source finding** | CF-17 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none — listed as **independent, safe to run in parallel with anything** |
| **Blocks** | nothing |
| **Effort** | **~1 hour for step 1** (see §5 — it is pure config and roughly doubles coverage), then ongoing |
| **Difficulty** | Low for step 1 · Medium thereafter (each file is its own puzzle) |
| **Files you will touch** | `mypy-strict-gate.ini`, then individual `src/hachi/**` files, `.github/workflows/ci.yml` (comment only), `docs/bug-bank.md` |

---

## 1. Brief

`[tool.mypy] strict = true` is declared repo-wide but nothing enforces it: the blocking gate
is a hand-maintained allowlist of 40 files out of 236. The allowlist has a written ratchet
rule — *add a file once its error count reaches zero* — and the ratchet has not been turned
in a long time.

**Measured today: 65 files under `core/`, `og_engine/`, and `gateway/` already have zero
errors and are not in the gate.** Adding all of them takes it from 40 → 105 files and it
still passes, with **zero code changes**. That is step 1, and it is an hour's work. Steps 2+
are the genuine burn-down of the 27 engine-layer files that still have errors.

## 2. Why this matters

A `strict = true` that nothing checks is worse than no declaration: it tells every reader —
and every agent — that this codebase is strictly typed, while 471 errors sit under it. The
scoped gate is the honest mechanism, and it works: it is blocking on PRs, its baseline is
clean, and it has held. The failure is not the design; it is that **nobody ever turns the
crank**, so the gate's coverage has been frozen at 17% while the tree grew.

That gap is where the repo's expensive bug classes live. Two of the review's confirmed P0s
(a branch that cannot execute; an attribute that never existed) are exactly what strict mypy
catches for free. Note also that `python -m mypy src/hachi` currently reports
`Unused "type: ignore" comment` at `core/runtime/job_handlers.py:400` and `:435` — dead
suppressions accumulating in the un-gated zone, unnoticed.

The goal is not "471 → 0 this week". It is: **the ratchet moves every time someone touches
a file, and the number never goes up.**

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The aspiration — `pyproject.toml:142-145`

```toml
[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

Nothing blocking runs against this config. CI's full-tree step
(`.github/workflows/ci.yml:131-133`) uses it and is explicitly `continue-on-error: true`.

### 3.2 Measured reality — `python -m mypy src/hachi`

```
Found 471 errors in 66 files (checked 236 source files)
```

**The review says ~483 errors across 64 files. Corrected: 471 / 66.** (The stale 483/64
figures are also quoted in `.github/workflows/ci.yml:122` — see §6 step 6.)

### 3.3 The blocking gate — `mypy-strict-gate.ini`

Header, verbatim (`:1-5`) — **this is the rule you are institutionalising**:

```ini
# Scoped strict mypy gate — CI enforces zero errors on these files on every PR.
#
# Files here are the currently-clean subset of core/, og_engine/, and gateway/.
# Add a file once its error count reaches zero; the CI job then guards it.
# Full burn-down toward whole-codebase strict continues as a Phase 3 sustained track.
```

Config `:7-10`, then `files =` at `:12` listing `:13-52`.

**The list is 40 files, not the 48 the review and CI both claim.** mypy itself confirms it:

```
$ python -m mypy --config-file mypy-strict-gate.ini
Success: no issues found in 40 source files
```

Composition: **31** `core/` · **2** `core/routing/` · **4** `og_engine/` · **3** `gateway/`.

**Coverage: 40 / 236 = 17%.**

### 3.4 ⚠️ The headline: 65 engine-layer files are ALREADY clean and were never added

Cross-referencing the whole-tree run against the gate list:

| | count |
|---|---:|
| `.py` files under `core/`, `og_engine/`, `gateway/` | **132** |
| …already in the gate | 40 |
| …with ≥1 error (the real burn-down) | **27** |
| …**zero errors, but NOT in the gate** | **65** |

**Verified empirically, not inferred.** A probe gate containing the current 40 plus all 65
clean files:

```
Success: no issues found in 105 source files
```

Coverage would go **17% → 105/236 = 44%** for the cost of editing one `.ini` file.

### 3.5 The real burn-down — 27 engine-layer files, ranked

Every one of these is in `core/`/`og_engine/`/`gateway/`, i.e. in the gate's declared scope:

| errors | file |
|---:|---|
| 1 | `src/hachi/core/archive_safety.py` |
| 1 | `src/hachi/core/credential_vault.py` |
| 1 | `src/hachi/core/graph_recall.py` |
| 1 | `src/hachi/core/memory_vault.py` |
| 1 | `src/hachi/core/models.py` |
| 1 | `src/hachi/core/providers/speech.py` |
| 1 | `src/hachi/core/routing/descriptor.py` |
| 1 | `src/hachi/core/sub_agent.py` |
| 1 | `src/hachi/core/unofficial_providers.py` |
| 1 | `src/hachi/gateway/shared_services.py` |
| 2 | `src/hachi/core/bundled_packs.py` |
| 2 | `src/hachi/core/community_packs.py` |
| 2 | `src/hachi/core/pack_index.py` |
| 2 | `src/hachi/core/runtime/job_handlers.py` |
| 2 | `src/hachi/core/secret_store.py` |
| 3 | `src/hachi/gateway/middleware/trace.py` |
| 4 | `src/hachi/core/obs/logging_setup.py` |
| 4 | `src/hachi/gateway/control_plane.py` |
| 6 | `src/hachi/core/permissions.py` |
| 7 | `src/hachi/core/integrations.py` |
| 8 | `src/hachi/og_engine/engine.py` |
| 9 | `src/hachi/core/loop.py` |
| 11 | `src/hachi/core/memory.py` |
| 11 | `src/hachi/core/rest_adapter.py` |
| 15 | `src/hachi/gateway/workspace.py` |
| 19 | `src/hachi/core/oauth.py` |
| 35 | `src/hachi/gateway/orchestrator.py` |

**Ten files at exactly one error each.** That is a plausible single sitting.

**This table is a snapshot and will rot.** §4 gives you the command that regenerates it —
use that, not this.

> For context on the remaining 39 files with errors (they are outside the gate's declared
> `core/og_engine/gateway` scope, so they are not your target): `cli/main.py` alone carries
> **137** errors — 29% of the repo's total — which is a symptom of
> [T-41](T-41-extract-in-process-runtime.md)'s finding, not something to chase here.

### 3.6 ⚠️ The most load-bearing seam carries a `type: ignore` — and it is NOT yours

`core/runtime/resume.py` reaches into the CLI (`:124`, `import hachi.cli.main as _main_mod`)
and into the gateway (`:189`). That inversion is frozen at `pyproject.toml:209` / `:235`.

Resolving it belongs to [T-42](T-42-retire-core-cli-seam.md) and
[T-68](T-68-import-linter-exemption-burndown.md), **not here.** If you try to type your way
through that seam you will end up redesigning the control plane. Leave `resume.py` alone.

## 4. Reproduce the failure

All of this is mechanically reproducible. Run from the repo root.

```bash
# 1. The gate today: how many files, and is it green?
python -m mypy --config-file mypy-strict-gate.ini

# 2. The whole tree: the real error/file counts.
python -m mypy src/hachi | tail -1

# 3. Coverage arithmetic.
python -c "print(40/236)"
```

**You will see now:** (1) `Success: no issues found in 40 source files`;
(2) `Found 471 errors in 66 files (checked 236 source files)`; (3) `0.169...`.

**You should see after step 1 of the fix:** (1) `Success: no issues found in 105 source
files`; (2) unchanged — you have not fixed any errors yet, only started guarding files that
were already clean.

### The ranking command — use this, not §3.5's snapshot

```bash
# Rank every file by error count, cheapest first.
python -m mypy src/hachi > /tmp/mypy_full.txt 2>&1
grep ": error: " /tmp/mypy_full.txt | sed 's/:[0-9].*//' | sort | uniq -c | sort -n
```

`sed 's/:[0-9].*//'` cuts at the first `path:line` colon, so it works with Windows
backslash paths. Sanity-check it: the counts must sum to the number in the summary line
(471 today) across the number of files it names (66 today).

Narrow it to the gate's declared scope — these are the only files you should be adding:

```bash
grep ": error: " /tmp/mypy_full.txt | sed 's/:[0-9].*//' \
  | tr '\\' '/' | grep -E "^src/hachi/(core|og_engine|gateway)/" \
  | sort | uniq -c | sort -n
```

### The harvest command — find the 65 clean-but-ungated files

```bash
python - <<'PY'
import pathlib, re
gate = pathlib.Path("mypy-strict-gate.ini").read_text(encoding="utf-8")
listed = set(re.findall(r"src/hachi/\S+?\.py", gate))
errs = pathlib.Path("/tmp/mypy_full.txt").read_text(encoding="utf-8", errors="replace")
dirty = {l.split(":")[0].replace("\\", "/") for l in errs.splitlines() if ": error: " in l}
allpy = {str(p).replace("\\", "/") for p in pathlib.Path(".").glob("src/hachi/**/*.py")}
eng = {p for p in allpy if p.split("/")[2] in ("core", "og_engine", "gateway")}
clean_ungated = sorted(eng - dirty - listed)
print(f"engine-layer files: {len(eng)}   gated: {len(listed & eng)}   "
      f"dirty: {len(eng & dirty)}   CLEAN BUT UNGATED: {len(clean_ungated)}")
for p in clean_ungated:
    print("   ", p)
PY
```

**You will see now:** `engine-layer files: 132   gated: 40   dirty: 27   CLEAN BUT UNGATED: 65`.

## 5. What "fixed" looks like

There are two distinct pieces of work and they should not be confused.

### Step 1 — the harvest (do this first; it is ~1 hour and is 90% of the value)

Add all 65 already-clean engine-layer files to `mypy-strict-gate.ini`'s `files =` block.
No source changes. Verify with `python -m mypy --config-file mypy-strict-gate.ini` →
`Success: no issues found in 105 source files`.

Keep the existing formatting exactly: one path per line, four-space indent, comma-terminated
except the last. Group by package and keep it sorted so future diffs are readable.

> **Why this is safe and not a shortcut:** these files pass strict mypy *today*. Adding them
> changes nothing about the code — it only means that from now on, a PR that introduces a
> type error in one of them fails CI. That is exactly what the gate is for, and the
> ratchet rule in the header already sanctions it: *"Add a file once its error count reaches
> zero."*

### Step 2 — the burn-down (ongoing)

Work the §4 ranked list from the top. Pick N files with the smallest error counts, fix the
errors **in the code**, add each file to the gate, verify, commit.

A reasonable first batch is the ten single-error files in §3.5. Treat each as its own small
commit — a 10-file batch that goes red is hard to bisect.

### Step 3 — make the ratchet a habit, not a task

Add one line to [CONTRIBUTING.md](../../../../CONTRIBUTING.md)'s PR checklist:

> If a file you touched now has zero mypy errors, add it to `mypy-strict-gate.ini`.

This is what "institutionalise the ratchet" means. Without it, T-69 gets re-filed in six
months against a bigger number.

### Non-goals

- **Do not make the full-tree CI step blocking.** 471 errors would turn main red instantly.
  The scoped gate is the mechanism; widening it is the work.
- **Do not add `# type: ignore` to reach zero.** That is cheating the gate, and mypy already
  reports unused ignores (`job_handlers.py:400`, `:435`) — they rot in place.
- **Do not relax `strict = true`** or add per-module `disallow_*  = false` overrides in
  `mypy-strict-gate.ini`. The gate's whole value is that its files are strict-clean.

## 6. Steps

1. Run the three §4 commands and record the real baseline in your PR description.
2. Run the harvest script. Confirm it reports 65 (or whatever it reports today).
3. Add those files to `mypy-strict-gate.ini` `files =`, sorted, grouped by package.
4. `python -m mypy --config-file mypy-strict-gate.ini` → must be `Success`. If it is **not**,
   stop and read §12 — scoping changes what mypy analyses, and a file clean in the whole-tree
   run can be dirty in the scoped one.
5. Commit step 1 on its own. It is a config-only change and should be reviewable in a minute.
6. Correct the stale numbers in `.github/workflows/ci.yml:121-130` (it says 483 errors / 64
   files / 48 gated) to whatever is true after your change. **Only the numbers** — the
   fictional-owner language in the same comment belongs to
   [T-67](T-67-governance-drift-cleanup.md); if T-67 has not landed, leave it and say so.
7. Then start step 2: ranked list, smallest first, one file per commit.
8. Run the FULL `uv run python scripts/preflight.py` and report the real counts.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**For step 1 the right instrument is not a pytest unit test — it is the gate itself.** The
assertion "these 105 files are strict-clean" is exactly what
`python -m mypy --config-file mypy-strict-gate.ini` computes, it already runs blocking in
`scripts/preflight.py:77-80` and in CI (`.github/workflows/ci.yml:138-140`, PR-only), and a
pytest wrapper around it would be slower, duplicated, and would test mypy rather than your
change. **Do not write one.**

There is, however, one thing the gate cannot check and that is worth locking: **that the
ratchet does not silently run backwards.** A `files =` list is easy to shrink in a hurry.

- **File:** `tests/test_p1_14_mypy_gate.py` (**existing** — it already owns this subject; do
  not start a new file)
- **Test name:** `test_strict_gate_covers_at_least_the_ratchet_floor`
- **It must assert:** the parsed `files =` block of `mypy-strict-gate.ini` contains at least
  N entries, where N is the count after your change (105), and that every listed path
  exists on disk. Assert against the real file, not a fixture.
- **It must FAIL before your fix** with `AssertionError: gate covers 40 files, floor is 105`.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

# The ratchet floor. This number may only ever go UP. If a change makes it go down,
# that is the bug this test exists to catch — do not lower it to go green.
STRICT_GATE_FLOOR = 105


def test_strict_gate_covers_at_least_the_ratchet_floor() -> None:
    """mypy-strict-gate.ini is a ratchet: coverage only increases.

    Regression: the gate's own header says 'add a file once its error count reaches
    zero', but 65 already-clean files had never been added — coverage sat at 40/236
    while the tree grew.
    """
    root = Path(__file__).resolve().parent.parent
    ini = root / "mypy-strict-gate.ini"
    listed = [
        line.strip().rstrip(",")
        for line in ini.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("src/hachi/")
    ]
    assert len(listed) >= STRICT_GATE_FLOOR, (
        f"gate covers {len(listed)} files, floor is {STRICT_GATE_FLOOR} — "
        "the ratchet may only turn one way"
    )
    missing = [p for p in listed if not (root / p).is_file()]
    assert not missing, f"gate lists files that do not exist: {missing}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Raise `STRICT_GATE_FLOOR` in the same commit as each step-2 batch — that is the ratchet.

## 8. Acceptance criteria

- [ ] The §7 test exists and failed before the fix with `gate covers 40 files, floor is 105`.
- [ ] `python -m mypy --config-file mypy-strict-gate.ini` reports `Success: no issues found in 105 source files` (or more).
- [ ] No `# type: ignore` was added to any file to get it into the gate.
- [ ] `mypy-strict-gate.ini` still has `strict = true` and no per-module relaxations.
- [ ] Every path in `files =` exists on disk (the §7 test checks this).
- [ ] The stale `483 errors / 64 files / 48 clean` numbers in `.github/workflows/ci.yml:121-130` are corrected, or explicitly deferred to [T-67](T-67-governance-drift-cleanup.md).
- [ ] `core/runtime/resume.py` was **not** touched.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not chase `cli/main.py`'s 137 errors.** It is 29% of the repo's total and it is
  outside the gate's declared `core/og_engine/gateway` scope. Its errors are a symptom of the
  file's size, which is [T-41](T-41-extract-in-process-runtime.md)'s subject. Typing a
  5,524-line module that is about to be split in half is wasted work.
- **Do not touch `core/runtime/resume.py`.** §3.6 — its `type: ignore` resolves via
  [T-42](T-42-retire-core-cli-seam.md), and "just add the annotation" leads straight into
  redesigning the control plane.
- **Do not make CI's full-tree mypy step blocking.** 471 errors ⇒ main red immediately.
- **Do not refactor code to make it easier to type.** Adding annotations is in scope;
  restructuring a function so its type is simpler is a different change with a different
  review. Annotate what is there ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- **Do not touch the eval corpus or golden fixtures** to satisfy a type. [CORRECTIONS.md](CORRECTIONS.md)
  §5 — editing them churns the eval baseline.
- **Do not silence with `Any`.** `Dict[str, Any]` everywhere passes strict and buys nothing.
  If a real type is genuinely unknowable, leave the file out of the gate and move on.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
python -m mypy --config-file mypy-strict-gate.ini   # the specific gate for this task
uv run python scripts/preflight.py --quick          # inner loop
uv run python scripts/preflight.py                  # before you call it done
```

For **step 1** the full suite genuinely cannot regress — you changed one `.ini` file and no
Python. Run it anyway once, so the number in your report is real rather than reasoned.

For **step 2** the full suite matters a great deal: adding annotations routinely surfaces
that a function was being called with a type it never handled. Report the **actual**
pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — A ratchet nobody turns is not a ratchet

- **Symptom:** `[tool.mypy] strict = true` was declared repo-wide while 471 errors sat under
  it, and the blocking scoped gate (`mypy-strict-gate.ini`) covered 40 of 236 source files
  (17%). 65 files under `core/`/`og_engine/`/`gateway/` were **already strict-clean** and had
  simply never been added — coverage was frozen while the tree grew.
- **Root cause:** the gate's ratchet rule ("add a file once its error count reaches zero")
  lived only in the ini header, with no step in the PR flow that made anyone act on it. The
  gate stayed green the whole time, so nothing ever signalled that it had stopped growing.
- **Fix:** harvested the 65 clean files into the gate (40 -> 105 files, 17% -> 44% coverage,
  zero code changes), then burned down the remaining engine-layer files smallest-first, and
  added a ratchet-floor test plus a CONTRIBUTING checklist line so the crank gets turned by
  default.
- **Avoid:** a gate whose coverage is a hand-maintained list needs a mechanical floor, or it
  silently stops growing. Before assuming a burn-down is expensive, measure how much of it is
  already done: `python -m mypy src/hachi`, rank per file, and diff against the allowlist.
- **Locked by:** `tests/test_p1_14_mypy_gate.py` — `test_strict_gate_covers_at_least_the_ratchet_floor`
```

## 12. Known traps

- **BB-1 (Windows):** the `mypy` `.exe` shim fails with OS error 4551. Use
  `python -m mypy` — every command in this spec already does.
- **⚠️ A file clean in the whole-tree run can be dirty in the scoped run.** Scoping changes
  which modules mypy analyses and therefore which types resolve. The whole-tree count is a
  **proxy**; `python -m mypy --config-file mypy-strict-gate.ini` is the **authority**. Add
  files, then run the gate — and if it goes red, remove the offender and move on rather than
  fighting it. (For the specific 65-file harvest this was verified end-to-end: the probe
  reported `Success: no issues found in 105 source files`. Later batches carry no such
  guarantee.)
- **`mypy-strict-gate.ini`'s `files =` paths are relative to the invocation directory.**
  Always run from the repo root, forward slashes, comma-separated. A path typo does not error
  loudly — mypy quietly checks fewer files and still says `Success`. The §7 existence check
  is what catches that.
- **`.mypy_cache/` at the repo root can serve stale results** after you edit the config. If a
  number looks impossible, delete it and re-run before debugging your change.
- **Do not run `mypy` inside `.claude/worktrees/`.** There are 15 stale full-repo worktrees
  there; a stray run picks up the wrong tree and reports numbers that do not match anything.
  (Cleanup is [T-74](T-74-repo-hygiene-sweep.md)'s job.)
- **The CI strict-gate step is PR-only** — `.github/workflows/ci.yml:140` is
  `if: github.event_name == 'pull_request'`. A push straight to main does not run it. Rely on
  `scripts/preflight.py`, where it is unconditional and blocking (`preflight.py:77-80`).
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Relevant if you take on
  `core/memory_vault.py` (1 error) or `og_engine/engine.py` (8) — both touch chromadb, and
  the tempting "just stub the import" fix poisons later tests.
