# T-70 · Mirror `src/` under `tests/` and rename the 55 batch-named files by subject

|  |  |
|---|---|
| **Source finding** | CF-18 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P3 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none |
| **Blocks** | nothing — but it **collides with everything**. Read the box below. |
| **Effort** | ~1 week spread out (the directory move is one sitting; the renames are opportunistic) |
| **Difficulty** | Medium — mechanically simple, operationally hazardous |
| **Files you will touch** | ~300 files under `tests/`, `pyproject.toml` (possibly), `docs/bug-bank.md` |

---

> ## ⛔ SCHEDULE THIS AS A DEDICATED FEATURE-FREEZE WINDOW
>
> This task moves **308 test files**. Every other in-flight task in this pack adds or amends
> tests, and a rename collides with an edit as a delete-plus-add — git will not merge it, it
> will present it as a conflict on a file that no longer exists.
>
> [README.md](README.md) already lists this alongside
> [T-41](T-41-extract-in-process-runtime.md) as one of the two tasks needing a dedicated
> window. **Announce the freeze, land the move in one commit, unfreeze.** Do not start this
> "in the background" while Wave 1 is running.
>
> The renames (§5 part 2) are the opposite: deliberately spread out and opportunistic.
> Do not batch them into the freeze window.

---

## 1. Brief

All 308 test files sit flat in `tests/`, and 55 of them are named after the remediation batch
that produced them (`test_p4_03_parallel_tools.py`, `test_g3_turn_lock.py`,
`test_backend_fixes_issues.py`) rather than the subject they test. Finding "the tests for
module X" is archaeology.

When you are done, `tests/` mirrors `src/hachi/`'s package structure, batch-named files are
being renamed by subject as they are touched, and the 29 files that compute paths from
`__file__` no longer break when a file moves.

## 2. Why this matters

The suite is this project's contract — [CLAUDE.md](../../../../CLAUDE.md) Rule 2 makes it
the thing that decides whether a change lands. A contract you cannot navigate gets worked
around: the specific failure mode is an agent that cannot find the existing tests for a
module, writes a new file, and ships a duplicate suite that drifts from the original. At
308 files and agent-velocity authorship, that is not hypothetical.

The naming problem is the sharper half. `test_g3_turn_lock.py` tells you which *audit wave*
produced it and nothing about what it protects. Six months on, "g3" means nothing to anyone,
and the file is functionally invisible to anyone working on session locking.

Note what this task is **not**: it is not a fix for the suite's other CF-18 problems.
Parallel execution is [T-71](T-71-injected-clocks-restore-parallelism.md); wiring-blindness
is [T-13](T-13-feature-liveness-smoke.md). This task is findability, and only findability.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**

### 3.1 The tree is completely flat

```
tests/test_*.py directly in tests/ (non-recursive) : 308
tests/test_*.py recursive                          : 308      <- identical
tests/*.py       (i.e. + conftest.py)              : 309
subdirectories of tests/                           : __pycache__/, fixtures/
tests/fixtures/ contents                           : sample_skill.og   (one file)
tests/__init__.py                                  : DOES NOT EXIST
```

Recursive and non-recursive counts being identical is the proof: there is no nesting at all.
`tests/fixtures/` holds exactly one data file; `tests/__pycache__/` is build output.

### 3.2 The 55 batch-named files, by group

**Phase ids `test_p<N>_<NN>_*` — 27 files**

```
test_p1_06_qualified_ids      test_p2_07a_ogpack            test_p3_07_ops_hygiene
test_p1_07_retrieval          test_p2_07b_pack_index        test_p4_01_multi_agent_v2
test_p1_09_paths              test_p2_08_composer           test_p4_02_shared_services
test_p1_14_mypy_gate          test_p2_12_agent_packs        test_p4_03_parallel_tools
test_p2_02_job_queue          test_p2_14_suggestion_chips   test_p4_06_m4_cutover
test_p2_03b_benchmark_suite   test_p3_01_memory_graph       test_p5_01_conformance
test_p2_03c_cost_latency      test_p3_02_memory_gardener    test_p5_02_skill_new
test_p2_04_memory_index       test_p3_04_embedding_rank     test_p5_04_git_sync
test_p2_05_memory_writer      test_p3_06_sdk_v0             test_p5_05_memoir
```

**Audit waves `test_g<N>_*` — 7 files**

```
test_g1_wave1        test_g3_session_store   test_g3_vault_lazy     test_g5_cleanups
test_g3_compaction   test_g3_turn_lock       test_g4_security_depth
```

**`*_fixes` — 5 files**

```
test_backend_fixes_issues   test_gateway_core_fixes   test_memory_fixes
test_slack_notion_fixes     test_voice_pipeline_fixes
```

**`phase*` — 3 files**

```
test_loop_phase5   test_phase0_security_hardening   test_phase7_integrations_mcp_sandbox_deployment
```

**slice / batch — 2 files**

```
test_b10_episodic_recall_offload   test_slice22_wiring
```

**`*_hardening` wave — 9 files** (excluding `test_phase0_security_hardening`, counted above)

```
test_calendar_tasks_hardening           test_og_engine_hardening      test_security_hardening
test_contacts_planning_meet_hardening   test_os_tools_hardening
test_drive_docs_sheets_hardening        test_permission_gate_hardening
test_gmail_hardening                    test_scheduler_hardening
```

**Borderline — 2 files.** Judgement calls; `_gaps` describes a remediation batch, but both
files do have a coherent subject. Rename only if the new name is genuinely better.

```
test_client_gaps   test_cockpit_gaps
```

**Total: 27 + 7 + 5 + 3 + 2 + 9 + 2 = 55.**

### 3.3 ⚠️ 29 files compute paths from `__file__` — every one breaks on a move

This is the single largest mechanical hazard, and it is invisible until the suite runs.
`rg -l "Path\(__file__\)" tests/ | wc -l` → **29 files, 34 call sites**, in two shapes:

**Shape A — reach `tests/fixtures/` (13 files, 13 sites).** Breaks if the test moves down a
level while `fixtures/` stays put.

```python
Path(__file__).parent / "fixtures" / "sample_skill.og"
```

`test_cli_skill_assert:14` · `test_cli_skill_changelog:14` · `test_cli_skill_deps:14` ·
`test_cli_skill_graph:14` · `test_cli_skill_report:18` · `test_cli_skill_search:14` ·
`test_cli_skill_show:14` · `test_g5_cleanups:24` · `test_graph_viz:21` · `test_og_engine:17` ·
`test_og_lint:17` · `test_og_parser:13` · `test_og_scope_rbac:21`

**Shape B — reach the repo root (16 files, 21 sites).** After a one-level move,
`.parent.parent` resolves to `tests/` instead of the repo root, and the path silently points
at nothing.

```python
Path(__file__).parent.parent / "src" / "hachi" / ...      # and .resolve().parent.parent, .resolve().parents[1]
```

`test_brain_constraints:30` · `test_core_tool_cost_guard:24` · `test_docker_assets:14` ·
`test_docs_cli_reference:23` · `test_eventbus_reactivity:87,106,123,134,234` (**5 sites**) ·
`test_measure_turn:24` · `test_memory_reliability:411` · `test_model_registry_json:25` ·
`test_onboarding_quickstart:21` · `test_p1_14_mypy_gate:16` · `test_p2_03c_cost_latency:27` ·
`test_p2_12_agent_packs:23` · `test_p4_02_shared_services:188,218` (**2 sites**) ·
`test_p5_01_conformance:19` · `test_routing_registry:71` · `test_scheduler_hardening:112`

### 3.4 ⚠️ No `tests/__init__.py`, and pytest is in default `prepend` import mode

`pyproject.toml:147-153`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "."]
norecursedirs = ["tokoboros", "*.egg", ".git", ".venv", "node_modules", "build", "dist"]
addopts = "--dist=loadfile"
```

No `--import-mode` is set, so pytest uses `prepend`: with no `__init__.py` files, every test
module is imported as a **top-level module keyed by its basename**. The moment two files in
different subdirectories share a basename — `tests/core/test_memory.py` and
`tests/tools/test_memory.py` — collection dies with:

```
import file mismatch: ... unique basename for your test file modules
```

This is *the* classic failure of a flat→nested test move. §5 tells you how to avoid it.

### 3.5 One hazard that does NOT exist — good news

`rg -n "^\s*(from|import)\s+test_" tests/` returns **nothing**. No test module imports
another. Every file is independently relocatable.

### 3.6 The reference to update — `norecursedirs`

`pyproject.toml:150` lists `"tokoboros"` (BB-7's directory junction). It is unaffected by
this move, but re-read it before touching pytest config, and **do not remove it** —
[T-67](T-67-governance-drift-cleanup.md) §3.3 explains why it must stay.

## 4. Reproduce the failure

There is nothing failing at runtime. The "failure" is findability, and it is measurable.

```bash
# The tree is flat: these two numbers being equal IS the finding.
ls tests/test_*.py | wc -l
find tests -name 'test_*.py' -type f | wc -l

# 55 batch-named files.
ls tests/ | grep -cE '^test_(p[0-9]+_[0-9]+|g[0-9]+|b[0-9]+|.*_fixes|.*phase|.*slice|.*_hardening|.*_gaps)'

# The move hazards.
rg -l "Path\(__file__\)" tests/ | wc -l     # 29 — every one breaks on a move
ls tests/__init__.py                        # absent -> basename collisions are fatal
rg -n "^\s*(from|import)\s+test_" tests/    # empty -> no cross-test imports. Good.

# Try to answer "where are the tests for core/session_store.py?" from the filename alone.
ls tests/ | grep -i session
```

**You will see now:** `308` and `308`; a batch-name count in the mid-50s; 29 files with
`Path(__file__)`; no `tests/__init__.py`; no cross-imports; and a `grep -i session` that
returns a partial, name-luck-dependent answer while `test_g3_session_store.py` is only found
by chance.

**You should see after the fix:** `find tests -name 'test_*.py' | wc -l` unchanged at 308,
`ls tests/test_*.py | wc -l` far smaller, `ls tests/core/` answering the question directly,
and `rg -l "Path\(__file__\)" tests/` showing paths resolved through a shared helper.

## 5. What "fixed" looks like

### Part 1 — the structural move (one commit, inside the freeze window)

`tests/` mirrors `src/hachi/`:

```
tests/
  conftest.py
  fixtures/sample_skill.og
  core/          core/runtime/   core/routing/   core/providers/
  og_engine/     gateway/        cli/            tui/
  tools/         jobs/           channels/       integrations/
  client/        sdk/
```

**Before moving anything, do these three things — in this order:**

1. **Add `tests/__init__.py` and one in every new subdirectory.** With `prepend` import mode
   this is what makes `tests.core.test_memory` and `tests.tools.test_memory` distinct
   modules. Without it the move is a landmine that only detonates on the second same-named
   file. *(Alternative: set `addopts = "--import-mode=importlib"`. That also solves it and
   needs no `__init__.py`, but it changes import semantics for all 308 files at once — a much
   bigger blast radius during a freeze. **Recommendation: `__init__.py`.** If you choose
   `importlib`, say so in the commit message and run the full suite before moving a single
   file.)*

2. **Kill Shape B (§3.3) first, in a separate commit, before the move.** Add to
   `tests/conftest.py`:

   ```python
   REPO_ROOT = Path(__file__).resolve().parent.parent
   FIXTURES = Path(__file__).resolve().parent / "fixtures"
   ```

   and convert all 34 call sites to import them. `conftest.py` stays at `tests/` root, so
   both constants remain correct no matter how deep a test ends up. **This commit is
   independently valuable and independently reviewable** — the suite must be green after it
   and before any file moves.

3. **Use `git mv`, one command per file**, so git records renames and `git log --follow`
   keeps working. Do not delete-and-recreate.

Then move, in one commit, with **no content edits mixed in**. A reviewer must be able to
confirm the diff is pure renames.

### Part 2 — the renames (opportunistic, NOT in the freeze window)

**Rename by subject as you touch a file, not in a big bang.** A 55-file rename commit
rewrites `git blame`'s entry point for 55 files at once and buys nothing that the same
renames spread over a month do not.

Mapping principle: name for the module under test, mirroring `src/`.

| From | To |
|---|---|
| `test_g3_turn_lock.py` | `tests/gateway/test_turn_lock.py` |
| `test_p2_02_job_queue.py` | `tests/jobs/test_queue.py` |
| `test_p3_04_embedding_rank.py` | `tests/og_engine/test_embedding_rank.py` |
| `test_backend_fixes_issues.py` | split by subject — it is a batch, not a unit |

The `*_fixes` and `*_gaps` files are the hard ones: they are batches by construction and
several probably want splitting rather than renaming. **Split only when you are already in
the file for another reason.**

### Explicit non-goals

- **Do not change a single test's behaviour.** Not an assertion, not a fixture, not a
  parametrisation. If the pass/fail count changes, you did something else.
- **Do not delete `tests/fixtures/`** or move `sample_skill.og`.
- **Do not touch `conftest.py`'s existing content** beyond adding the two constants. It warms
  chromadb (BB-3) and sets `HACHI_DISABLE_DOTENV_AUTOLOAD` (BB-2) — both load-bearing.

## 6. Steps

1. **Commit 1 (pre-freeze):** add `REPO_ROOT` / `FIXTURES` to `tests/conftest.py`; convert
   all 34 `Path(__file__)` sites in the 29 files from §3.3. Run the FULL suite. Green.
2. Announce the freeze. Confirm no sibling task has uncommitted test edits.
3. **Commit 2:** add `tests/__init__.py` and the per-package `__init__.py` files. Full suite.
   Green. (This alone can change collection — verify before moving anything.)
4. Write the §7 test. Watch it fail.
5. **Commit 3:** `git mv` every file into its mirrored directory. **No content edits.**
6. Run the FULL suite. The pass/fail/skip counts must be **identical** to step 1's. Any
   change means a file lost a fixture or a path.
7. `git log --follow` a moved file to confirm history survived.
8. Unfreeze.
9. Renames (part 2) proceed opportunistically from here, one file at a time, forever.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

**A conventional unit test is the wrong instrument for "did 308 files move safely" — the
right check is the suite's own collection count, before and after.** But there *is* a real,
lasting invariant worth locking, and it is the one that prevents the tree drifting flat
again: **every test file lives in a directory that mirrors a real `src/hachi` package.**

- **File:** `tests/test_test_tree_layout.py` (**new**; keep it at `tests/` root — it is about
  the tree, not about a package)
- **Test names:** `test_every_test_file_mirrors_a_src_package`,
  `test_no_test_basename_collisions`
- **It must assert:** against the real on-disk tree — that each `test_*.py`'s parent
  directory (relative to `tests/`) corresponds to an existing `src/hachi/...` package, and
  that no two test files share a basename (the §3.4 hazard, made permanent).
- **It must FAIL before your fix** with a list of 308 files sitting at `tests/` root that
  mirror no package.

```python
# sketch — adapt to the repo's existing fixtures
from collections import Counter
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src" / "hachi"

# Files legitimately at tests/ root: cross-cutting suites that belong to no one package.
ROOT_ALLOWED = {"test_test_tree_layout.py"}


def test_every_test_file_mirrors_a_src_package() -> None:
    """tests/ mirrors src/hachi/. A file at the root belongs to no module — say which.

    Regression: all 308 test files sat flat in tests/, so 'where are the tests for
    module X' had no mechanical answer and duplicate suites drifted apart.
    """
    orphans = []
    for path in TESTS.rglob("test_*.py"):
        rel = path.relative_to(TESTS)
        if rel.parent == Path("."):
            if path.name not in ROOT_ALLOWED:
                orphans.append(str(rel))
            continue
        if not (SRC / rel.parent).is_dir():
            orphans.append(f"{rel}  (no src/hachi/{rel.parent})")
    assert not orphans, "test files that mirror no src package:\n  " + "\n  ".join(orphans)


def test_no_test_basename_collisions() -> None:
    """pytest runs in 'prepend' import mode: two same-named modules collide fatally."""
    names = Counter(p.name for p in TESTS.rglob("test_*.py"))
    dupes = {n: c for n, c in names.items() if c > 1}
    assert not dupes, f"duplicate test basenames (needs __init__.py or importlib mode): {dupes}"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> `test_every_test_file_mirrors_a_src_package` will list ~308 orphans on the first run.
> That list **is** the work queue for the move — keep the output.

## 8. Acceptance criteria

- [ ] The §7 tests exist and `test_every_test_file_mirrors_a_src_package` failed before the move, listing ~308 orphans.
- [ ] `find tests -name 'test_*.py' -type f | wc -l` is **still 308** — nothing was lost or duplicated.
- [ ] **The full-suite pass / fail / skip counts are byte-identical before and after the move.** Paste both.
- [ ] `git log --follow` works on at least three spot-checked moved files (rename detection survived).
- [ ] `rg -l "Path\(__file__\)" tests/` no longer shows the 29 files computing repo-root or fixture paths by hand.
- [ ] `tests/__init__.py` exists, plus one per new subdirectory (or `--import-mode=importlib` is set and justified in the commit message).
- [ ] `tests/fixtures/sample_skill.og` is untouched and still resolves from every consumer.
- [ ] The move commit contains **only** renames — `git show --stat` shows no content churn.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change any test's behaviour.** This is the whole discipline of this task. No
  assertion edits, no fixture "improvements", no de-duplication, no parametrisation. If you
  see a bad test while moving it — and you will, across 308 files — **note it and move on**.
- **Do not fix the wall-clock timing tests.** That is
  [T-71](T-71-injected-clocks-restore-parallelism.md), it edits ten of the files you are
  moving, and doing both at once makes the diff unreviewable. **Coordinate on order: T-70
  first, or T-71 first, never concurrently.**
- **Do not add the feature-liveness smoke suite.** That is
  [T-13](T-13-feature-liveness-smoke.md).
- **Do not delete a test that looks redundant.** Two files with overlapping coverage are a
  rename candidate, not a deletion candidate ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **Do not restructure `conftest.py`.** Add the two path constants; touch nothing else. Its
  chromadb warm-up (BB-3) and dotenv guard (BB-2) are load-bearing and subtle.
- **Do not remove `"tokoboros"` from `pyproject.toml:150` `norecursedirs`.** BB-7.
- **Do not batch the renames into the move commit.** §5 part 2.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**The verification for this task is unusual and it is the whole point: the numbers must not
move.** Capture the full-suite counts *before* you start and diff them against the counts
after. A file that silently stops being collected shows up as a lower total, not as a
failure — and that is the most likely way this task goes wrong.

```bash
uv run pytest -q 2>&1 | tail -1     # run BEFORE the move; save this line verbatim
uv run pytest -q 2>&1 | tail -1     # run AFTER;  must match exactly
uv run pytest --collect-only -q 2>&1 | tail -1   # collection count, same discipline
```

Report the **actual** pass/fail counts, both runs. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Moving test files breaks `Path(__file__)` paths and collides on basenames

- **Symptom:** relocating a flat `tests/` tree into subdirectories silently breaks two
  things: tests that resolve the repo root via `Path(__file__).parent.parent` now resolve to
  `tests/`, and (with no `__init__.py`, pytest's default `prepend` import mode) two test
  files sharing a basename abort collection with `import file mismatch`.
- **Root cause:** 29 test files computed paths from their own location — 13 to reach
  `tests/fixtures/`, 16 to reach the repo root — so file depth was an undeclared part of
  their contract. And `tests/` had no `__init__.py`, so module identity was the basename.
- **Fix:** hoisted `REPO_ROOT` and `FIXTURES` into `tests/conftest.py` (which stays at the
  tests root regardless of depth) and converted all 34 call sites BEFORE moving anything;
  added `__init__.py` per test package; moved with `git mv` so rename detection survived.
- **Avoid:** never compute a repo path from `__file__` in a test — import it from
  `conftest`. Before any bulk file move, capture the full-suite pass/fail/skip counts and
  require them to be byte-identical afterward: a file that stops being collected shows up as
  a *lower total*, never as a failure.
- **Locked by:** `tests/test_test_tree_layout.py` — `test_every_test_file_mirrors_a_src_package`, `test_no_test_basename_collisions`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-7 — the directory junction.** `D:\OpenGigantic\hachi` and a sibling `tokoboros` path
  are the same files. During a 300-file move this is genuinely dangerous: a `git mv` executed
  through the junction can look like a delete on one side. Work from the canonical path only,
  and keep `norecursedirs` intact.
- **BB-3 — chromadb.** `tests/conftest.py` warms chromadb at import so the PyO3 extension
  loads exactly once. It must remain at `tests/` root and must keep running before any test
  module imports. Do not move it, do not split it into per-package conftests.
- **Windows path length.** `tests/integrations/google/test_contacts_planning_meet_hardening.py`
  under a deep repo path can approach `MAX_PATH`. If a file refuses to move, that is why —
  shorten the *name* (which you want anyway, §5 part 2) rather than flattening the directory.
- **`git mv` on Windows is case-insensitive.** Renaming `test_OGParser.py` →
  `test_og_parser.py` needs two moves via a temp name, or git records nothing.
- **`--dist=loadfile` (`pyproject.toml:153`) keys on the file.** Moving files changes worker
  assignment if anyone ever runs with `-n`. Combined with
  [T-71](T-71-injected-clocks-restore-parallelism.md) this is a real interaction — another
  reason to sequence the two tasks rather than overlap them.
- **`.claude/worktrees/` holds 15 stale full-repo copies**, each with its own `tests/`. A
  `find`/glob-based move script that starts at the repo root will walk into them. Anchor
  every path at `tests/` explicitly. (Cleanup is [T-74](T-74-repo-hygiene-sweep.md).)
- **`tests/__pycache__/` holds stale `.pyc` files keyed to the old flat layout.** Delete it
  after the move, or you will chase a phantom `import file mismatch` that no longer exists in
  source.
