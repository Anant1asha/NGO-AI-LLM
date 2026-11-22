# T-48 · Move the twelve flat `memory*` modules into a `core/memory/` package

|  |  |
|---|---|
| **Source finding** | CF-12 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | [T-49](T-49-memory-provider-seam-decision.md), [T-50](T-50-memory-session-provenance.md), [T-51](T-51-memory-delete-tri-store.md), [T-52](T-52-memory-compaction-persistence.md) — **land all four first**; see §2 for why |
| **Blocks** | nothing |
| **Effort** | ~3 days |
| **Difficulty** | Low (mechanical) — but wide. 197 import statements across 50 files. |
| **Files you will touch** | `src/hachi/core/memory*.py` (12 files), `src/hachi/core/graph_recall.py`, `src/hachi/core/conversation_memory.py`, ~14 other `src/` files, ~34 `tests/` files, `pyproject.toml` (only if a contract needs it — see §12) |

---

## 1. Brief

Twelve memory-related modules sit flat in `src/hachi/core/` with no package
boundary — **5,838 lines**, including the 2nd- and 3rd-largest files in `core/`.
Nothing marks them as one subsystem; nothing stops the next memory initiative from
adding a thirteenth `memory_*.py` beside them. This task moves them into
`src/hachi/core/memory/` and rewrites the imports. **Nothing else.** No behaviour
change, no signature change, no logic edit, no reformat.

When you are done, `hachi.core.memory` is a package, every import site points at the
new path, and `uv run python scripts/preflight.py` is green with the same pass count
as before you started.

## 2. Why this matters

This is the *only* task in the memory group that is pure churn, and that is exactly
why its sequencing matters more than its content. The four behavioural memory tasks
([T-49](T-49-memory-provider-seam-decision.md),
[T-50](T-50-memory-session-provenance.md),
[T-51](T-51-memory-delete-tri-store.md),
[T-52](T-52-memory-compaction-persistence.md)) are small, reviewable diffs pinned to
specific line anchors in `core/memory.py` and `core/memory_vault.py`. A 197-import
rename invalidates every one of those anchors and, if interleaved, produces a
`git diff` in which a rename and a semantic change are indistinguishable — the single
most effective way to smuggle a regression past review.

There is a second, harder reason to go last: **[T-49](T-49-memory-provider-seam-decision.md)
may delete `memory_provider.py` outright.** Moving a file you are about to delete is
wasted work and a wasted merge conflict.

So: **T-49 → T-50 → T-51 → T-52 → T-48.** If you are reading this file first, stop and
check whether those four have landed.

If the diff you are about to write contains anything other than moved files and
rewritten import lines, you are doing a different task.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The twelve modules — 5,838 lines, all flat in `src/hachi/core/`

Verified with `wc -l`:

| Module | Lines | Note |
|---|---:|---|
| `src/hachi/core/memory_vault.py` | 1801 | **2nd-largest file in `core/`** (only `mcp_client.py` at 1928 is bigger) |
| `src/hachi/core/memory.py` | 1561 | 3rd-largest. `MemoryManager` + `extract_facts`. |
| `src/hachi/core/memory_importer.py` | 352 | |
| `src/hachi/core/memory_gardener.py` | 347 | dead surface — see [T-08](T-08-memory-gardener.md) |
| `src/hachi/core/memory_graph.py` | 327 | `GraphNode`, `load_memory_dir`, `expand_graph` |
| `src/hachi/core/memory_provider.py` | 304 | **may be deleted by [T-49](T-49-memory-provider-seam-decision.md)** |
| `src/hachi/core/memory_writer.py` | 289 | `MemoryNode`, `MemoryWriter` |
| `src/hachi/core/memory_index.py` | 247 | FTS5 index |
| `src/hachi/core/memory_exporter.py` | 222 | |
| `src/hachi/core/graph_recall.py` | 206 | no `memory` prefix — easy to miss |
| `src/hachi/core/memory_guard.py` | 143 | |
| `src/hachi/core/conversation_memory.py` | 39 | no `memory_` prefix — easy to miss |
| **Total** | **5838** | |

Reproduce the count:

```bash
wc -l src/hachi/core/memory*.py src/hachi/core/graph_recall.py src/hachi/core/conversation_memory.py
```

### 3.2 A thirteenth candidate the audit missed — `core/user_profile.py` (542 lines)

`UserProfileStore` (`src/hachi/core/user_profile.py:226`) is a memory store by any
reasonable definition: it is a facade over the vault's `user_collection`, it is
constructed from `tools/memory_tools.py:539`, and it reaches into `MemoryVault`
privates at **twelve** call sites (lines 422, 423, 424, 461, 463, 464, 465, 480, 494,
496, 497, 498 — enumerated in [T-49](T-49-memory-provider-seam-decision.md) §3.4).

It also carries `CorrectionLog` (`user_profile.py:105-133`), which opens its **own**
`sqlite3` connection to `sessions.db` (`:127`) for a `profile_corrections` table.

**Decision on this file is made in §5. Read it before you move anything.**

### 3.3 The blast radius — 197 import statements across 50 files

```bash
# 16 files in src/
rg -l "hachi\.core\.(memory|memory_vault|memory_writer|memory_index|memory_graph|memory_gardener|memory_guard|memory_importer|memory_exporter|memory_provider|graph_recall|conversation_memory)\b" -g '*.py' src/

# 34 files in tests/
rg -l "hachi\.core\.(memory|memory_vault|memory_writer|memory_index|memory_graph|memory_gardener|memory_guard|memory_importer|memory_exporter|memory_provider|graph_recall|conversation_memory)\b" -g '*.py' tests/
```

The complete `src/` import inventory (verified — **every line**, sorted by file):

```
src/hachi/cli/commands/memory.py:28       from hachi.core.memory_vault import MemoryVault
src/hachi/cli/commands/memory.py:58       from hachi.core.memory_vault import MemoryVault
src/hachi/cli/commands/memory.py:105      from hachi.core.memory_vault import MemoryVault
src/hachi/cli/commands/memory.py:156      from hachi.core.memory_vault import MemoryVault
src/hachi/cli/commands/memory.py:217      from hachi.core.memory_importer import ImportResult, ingest, parse_file
src/hachi/cli/commands/memory.py:218      from hachi.core.memory_vault import MemoryVault
src/hachi/cli/commands/memory.py:309      from hachi.core.memory_exporter import chroma_to_files
src/hachi/cli/commands/memory.py:310      from hachi.core.memory_vault import MemoryVault
src/hachi/core/graph_recall.py:28         from hachi.core.memory_graph import (GraphNode, compose_resume_pack, expand_graph, load_memory_dir)
src/hachi/core/memory.py:41               from hachi.core.conversation_memory import IterationState      (TYPE_CHECKING)
src/hachi/core/memory.py:233              from hachi.core.memory_writer import MemoryNode, _slugify
src/hachi/core/memory.py:971              from hachi.core.conversation_memory import IterationState
src/hachi/core/memory.py:1369             from hachi.core.memory_vault import _get_llm_client
src/hachi/core/memory_importer.py:33      from hachi.core.memory_vault import MemoryVault
src/hachi/core/memory_provider.py:135     from hachi.core.memory_vault import MemoryVault
src/hachi/core/memory_vault.py:52         from hachi.core.memory_guard import scan as guard_scan
src/hachi/core/memory_vault.py:1128       from hachi.core.memory_index import rrf_merge
src/hachi/core/memory_vault.py:1734       from hachi.core.memory_guard import scan as guard_scan
src/hachi/core/runtime/job_handlers.py:76    from hachi.core.memory_vault import get_memory_vault
src/hachi/core/runtime/job_handlers.py:94    from hachi.core.memory_vault import _get_llm_client
src/hachi/core/runtime/job_handlers.py:112   from hachi.core.memory_writer import MemoryWriter
src/hachi/core/runtime/job_handlers.py:195   from hachi.core.memory import extract_facts
src/hachi/core/sub_agent.py:48            from hachi.core.conversation_memory import IterationState   (TYPE_CHECKING)
src/hachi/core/sub_agent.py:220           from hachi.core.conversation_memory import IterationState
src/hachi/core/testing.py:5               from hachi.core.conversation_memory import ConversationMemory, IterationState
src/hachi/core/untrusted_content.py:16    from hachi.core.memory_guard import scan
src/hachi/core/user_profile.py:52         from hachi.core.memory_vault import MemoryVault             (TYPE_CHECKING)
src/hachi/core/user_profile.py:459        from hachi.core.memory_vault import MemoryVault
src/hachi/core/user_profile.py:475        from hachi.core.memory_vault import USER_PROFILE_MAX_ENTRIES
src/hachi/core/user_profile.py:488        from hachi.core.memory_vault import MemoryVault
src/hachi/gateway/orchestrator.py:41      from hachi.core.memory import MemoryManager
src/hachi/gateway/orchestrator.py:42      from hachi.core.memory_provider import ChromaMemoryProvider, resolve_provider
src/hachi/gateway/orchestrator.py:43      from hachi.core.memory_vault import MemoryVault
src/hachi/gateway/orchestrator.py:751     from hachi.core.memory_gardener import GardeningResult
src/hachi/gateway/orchestrator.py:1665    from hachi.core.graph_recall import build_graph_recall_section
src/hachi/gateway/orchestrator.py:1845    from hachi.core.memory import build_episode_summary
src/hachi/gateway/orchestrator.py:3043    from hachi.core.memory_provider import FTS5MemoryProvider
src/hachi/gateway/orchestrator.py:3061    from hachi.core.memory_index import MemoryIndex
src/hachi/gateway/orchestrator.py:3090    from hachi.core.memory_writer import MemoryWriter
src/hachi/gateway/shared_services.py:273  from hachi.core.memory_provider import ChromaMemoryProvider, resolve_provider
src/hachi/gateway/shared_services.py:314  from hachi.core.memory_index import MemoryIndex
src/hachi/gateway/shared_services.py:315  from hachi.core.memory_writer import MemoryWriter
src/hachi/integrations/google/meet.py:169 from hachi.core.memory_vault import MemoryVault
src/hachi/og_engine/engine.py:579         from hachi.core.memory_guard import scan as _guard_scan
src/hachi/tools/memory_tools.py:24        from hachi.core.memory_vault import MemoryVault
```

Note the two importers that are easy to forget because they are outside the obvious
neighbourhood: **`og_engine/engine.py:579`** and **`integrations/google/meet.py:169`**.

### 3.4 The name collision you must resolve — `core/memory.py` vs `core/memory/`

`hachi.core.memory` is *currently a module*. Making `core/memory/` a package means the
dotted name `hachi.core.memory` changes meaning. Three live `src/` sites import from
it as a module today:

- `gateway/orchestrator.py:41` — `from hachi.core.memory import MemoryManager`
- `gateway/orchestrator.py:1845` — `from hachi.core.memory import build_episode_summary`
- `core/runtime/job_handlers.py:195` — `from hachi.core.memory import extract_facts`

Plus test imports (e.g. `tests/test_compaction_summary_applyback.py:21`
`from hachi.core.memory import MemoryManager`).

`core/memory.py` and `core/memory/` cannot both exist. §5 resolves this.

## 4. Reproduce the failure

**There is no runtime failure to reproduce. This is a structural finding and you
should not pretend otherwise** — nothing misbehaves today because the modules are
flat. What *is* measurable is the size and shape of the problem, and those numbers
are your before/after evidence:

```bash
# 1. The 12 modules and their line counts. Expect: 5838 total.
wc -l src/hachi/core/memory*.py src/hachi/core/graph_recall.py src/hachi/core/conversation_memory.py

# 2. No package boundary exists. Expect: NO such directory.
ls src/hachi/core/memory/ 2>/dev/null || echo "no core/memory/ package"

# 3. The import blast radius. Expect: 16 files in src/, 34 in tests/.
rg -l "hachi\.core\.(memory|memory_vault|memory_writer|memory_index|memory_graph|memory_gardener|memory_guard|memory_importer|memory_exporter|memory_provider|graph_recall|conversation_memory)\b" -g '*.py' src/ | wc -l
rg -l "hachi\.core\.(memory|memory_vault|memory_writer|memory_index|memory_graph|memory_gardener|memory_guard|memory_importer|memory_exporter|memory_provider|graph_recall|conversation_memory)\b" -g '*.py' tests/ | wc -l
```

**You will see now:** 5838 lines across 12 flat modules; no `core/memory/` directory;
16 + 34 = 50 importing files.

**You should see after the fix:** `ls src/hachi/core/memory/` lists the moved modules
plus `__init__.py`; `rg -n "from hachi\.core\.memory_vault import" src/ tests/` returns
**nothing** (all rewritten); `wc -l` totals are unchanged (a pure move changes no line
counts); and the pytest pass count is identical to the pre-move run.

Record the pre-move pytest count **before** you touch anything — it is the only
evidence that a pure move stayed pure:

```bash
uv run pytest -q            # on Windows: python -m pytest -q  (BB-1)
```

## 5. What "fixed" looks like

Two decisions are made here by the task author. Do not relitigate them mid-move.

### Decision 1 — `core/memory.py` becomes `core/memory/manager.py`, and `__init__.py` re-exports

The package `__init__.py` preserves the three live public entry points so
`from hachi.core.memory import MemoryManager` keeps working:

```python
"""hachi.core.memory — the memory subsystem.

Public surface (stable): MemoryManager, extract_facts, build_episode_summary.
Everything else is internal to this package; import it from its module.
"""

from hachi.core.memory.manager import (
    MemoryManager,
    build_episode_summary,
    extract_facts,
)

__all__ = ["MemoryManager", "build_episode_summary", "extract_facts"]
```

*Why:* it makes `gateway/orchestrator.py:41`, `:1845` and
`core/runtime/job_handlers.py:195` **zero-diff**, which shrinks the reviewable surface
of an already-wide change. Keep `__init__.py` to exactly these three names — a
re-export of everything would recreate the flat namespace you are removing.

### Decision 2 — `user_profile.py` does NOT move in this task

Leave `src/hachi/core/user_profile.py` where it is.

*Why:* it is not one of the twelve the finding names; moving it widens an already-wide
diff; and its future depends on [T-49](T-49-memory-provider-seam-decision.md), which
may change how it talks to the vault entirely. Add a one-line note to the package
docstring recording that it is a memory store living outside the package, and move on.

### Target layout

```
src/hachi/core/memory/
    __init__.py            (new — the three re-exports above)
    manager.py             ← core/memory.py
    vault.py               ← core/memory_vault.py
    provider.py            ← core/memory_provider.py       (omit if T-49 deleted it)
    writer.py              ← core/memory_writer.py
    index.py               ← core/memory_index.py
    graph.py               ← core/memory_graph.py
    graph_recall.py        ← core/graph_recall.py
    gardener.py            ← core/memory_gardener.py
    guard.py               ← core/memory_guard.py
    importer.py            ← core/memory_importer.py
    exporter.py            ← core/memory_exporter.py
    conversation.py        ← core/conversation_memory.py
```

The `memory_` prefix is dropped inside the package (`memory.vault` reads better than
`memory.memory_vault`). `graph_recall.py` keeps its name — `memory.graph_recall` is
already unambiguous and it is distinct from `memory.graph`.

### Non-goals, stated as invariants

- Every moved file's **contents** are byte-identical except for its own `import` lines
  and, where a module docstring names its old path, that path string.
- No `__init__.py` re-export beyond the three names above.
- No public signature changes. No renamed classes or functions.
- `wc -l` on the moved files sums to 5838 ± only the docstring path edits.

## 6. Steps

1. Confirm T-49/T-50/T-51/T-52 have landed (§2). If they have not, **stop**.
2. Record the baseline: `uv run pytest -q` and write down the exact pass/fail counts.
3. `mkdir src/hachi/core/memory` and write `__init__.py` with the three re-exports
   from §5.
4. Move the files **with `git mv`**, one per commit-able chunk if you like, but land
   them as one commit (§9). `git mv` preserves rename detection, which is the only
   thing that will make this diff reviewable:
   ```bash
   git mv src/hachi/core/memory.py            src/hachi/core/memory/manager.py
   git mv src/hachi/core/memory_vault.py      src/hachi/core/memory/vault.py
   git mv src/hachi/core/memory_provider.py   src/hachi/core/memory/provider.py
   git mv src/hachi/core/memory_writer.py     src/hachi/core/memory/writer.py
   git mv src/hachi/core/memory_index.py      src/hachi/core/memory/index.py
   git mv src/hachi/core/memory_graph.py      src/hachi/core/memory/graph.py
   git mv src/hachi/core/graph_recall.py      src/hachi/core/memory/graph_recall.py
   git mv src/hachi/core/memory_gardener.py   src/hachi/core/memory/gardener.py
   git mv src/hachi/core/memory_guard.py      src/hachi/core/memory/guard.py
   git mv src/hachi/core/memory_importer.py   src/hachi/core/memory/importer.py
   git mv src/hachi/core/memory_exporter.py   src/hachi/core/memory/exporter.py
   git mv src/hachi/core/conversation_memory.py src/hachi/core/memory/conversation.py
   ```
   `git mv` of `memory.py` → `memory/manager.py` requires the directory to exist
   first (step 3).
5. Rewrite the **intra-package** imports first — the seven listed in §3.3 that live
   inside the moved files themselves (`graph_recall.py:28`, `memory.py:41/233/971/1369`,
   `memory_importer.py:33`, `memory_provider.py:135`, `memory_vault.py:52/1128/1734`).
   Use the fully-qualified new path (`from hachi.core.memory.vault import MemoryVault`),
   not a relative import — the rest of the repo uses absolute imports and consistency
   matters more than brevity here.
6. Rewrite the remaining `src/` imports — the ~36 lines in §3.3 outside the package.
   Do **not** skip `og_engine/engine.py:579` or `integrations/google/meet.py:169`.
7. Rewrite the `tests/` imports across the 34 files. These are mechanical; a
   `git grep -l` driven sed is fine here **provided** you diff the result and confirm
   only import lines changed.
8. `rg -n "hachi\.core\.memory_" src/ tests/` must return **nothing**. Same for
   `rg -n "hachi\.core\.graph_recall" src/ tests/` and
   `rg -n "hachi\.core\.conversation_memory" src/ tests/`.
9. Run `uv run python scripts/preflight.py` (**full**). Compare the pytest counts to
   step 2 — they must be **identical**.
10. Update the docs that name the old paths (§9 tells you which ones are in scope).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

This task fixes no bug, so the "regression" being locked is the *structural invariant*:
the memory subsystem lives behind a package boundary, and the public surface survived
the move. Both assertions fail today.

- **File:** `tests/test_memory_package_boundary.py` (**new**)
- **Test names:** `test_memory_package_exists_and_exports_public_surface` and
  `test_no_flat_memory_modules_remain`
- **It must assert:** the real, observed module layout — that
  `hachi.core.memory` is an importable **package** (has `__path__`), that the three
  public names are importable from it, and that no `hachi.core.memory_*` module is
  importable any more. Not a mock; these are real imports.
- **It must FAIL before your fix** with:
  - test 1: `AssertionError: hachi.core.memory is a module, not a package`
    (`hasattr(mod, "__path__")` is `False` today)
  - test 2: `AssertionError: flat module still importable: hachi.core.memory_vault`

```python
# sketch — adapt to the repo's existing fixtures
import importlib
import importlib.util

import pytest

_FLAT_MODULES = [
    "hachi.core.memory_vault",
    "hachi.core.memory_provider",
    "hachi.core.memory_writer",
    "hachi.core.memory_index",
    "hachi.core.memory_graph",
    "hachi.core.memory_gardener",
    "hachi.core.memory_guard",
    "hachi.core.memory_importer",
    "hachi.core.memory_exporter",
    "hachi.core.graph_recall",
    "hachi.core.conversation_memory",
]


def test_memory_package_exists_and_exports_public_surface() -> None:
    """core/memory/ is a package and still exports the three public names.

    Locks T-48: the move must not change the public surface that
    gateway/orchestrator.py and core/runtime/job_handlers.py import.
    """
    mod = importlib.import_module("hachi.core.memory")
    assert hasattr(mod, "__path__"), "hachi.core.memory is a module, not a package"
    for name in ("MemoryManager", "extract_facts", "build_episode_summary"):
        assert hasattr(mod, name), f"public name lost in the move: {name}"


@pytest.mark.parametrize("dotted", _FLAT_MODULES)
def test_no_flat_memory_modules_remain(dotted: str) -> None:
    """No memory module may be importable from the flat core/ namespace."""
    assert importlib.util.find_spec(dotted) is None, f"flat module still importable: {dotted}"
```

> `find_spec` is used rather than a bare `import` so the test reports a clean
> assertion instead of an `ImportError` traceback, and so it never has the
> side effect of importing chromadb-backed modules. Do **not** rewrite it to
> `patch.dict(sys.modules)` — see §12 (BB-3).

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and both tests failed before the fix.
- [ ] `ls src/hachi/core/memory/` lists 12 modules + `__init__.py` (11 + `__init__.py` if T-49 deleted `provider.py`).
- [ ] `rg -n "hachi\.core\.memory_" src/ tests/` returns **nothing**.
- [ ] `rg -n "hachi\.core\.graph_recall|hachi\.core\.conversation_memory" src/ tests/` returns **nothing**.
- [ ] `git log --stat` shows the moves as **renames** (you used `git mv`), not delete+add.
- [ ] `git diff -M --stat` shows **no** moved file with substantive content change beyond its own import lines.
- [ ] The pytest pass/fail counts are **identical** to the pre-move baseline recorded in §6 step 2.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not fix anything you notice while moving.** You will read 5,838 lines of memory
  code during this task and you will find things. Every one of them belongs to a
  sibling task or a new one. Specifically: **do not** fix the missing `_session_id`
  ([T-50](T-50-memory-session-provenance.md)), **do not** touch `delete_fact`
  ([T-51](T-51-memory-delete-tri-store.md)), **do not** correct the
  `get_pending_summaries()` comment ([T-52](T-52-memory-compaction-persistence.md)),
  **do not** wire up the gardener ([T-08](T-08-memory-gardener.md)). This is the
  single most likely way this task goes wrong.
- **Do not move `core/user_profile.py`.** §5 Decision 2.
- **Do not add re-exports beyond the three public names.** A convenience
  `from .vault import *` in `__init__.py` rebuilds the flat namespace you are deleting
  and makes the boundary decorative.
- **Do not split, merge, or shrink any module.** `memory_vault.py` is 1,801 lines and
  wants decomposing. That is a separate task with its own regression risk.
- **Do not convert absolute imports to relative ones** anywhere outside the new
  package, and prefer absolute inside it too (§6 step 5).
- **Do not bundle this with any other memory task in one commit.** One commit, verbatim
  moves, honest message ([CLAUDE.md](../../../../CLAUDE.md) Rule 1).
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3). The
  auto-format hook covers the files you touch; a repo-wide run reflows ~100 files and
  makes this diff unreviewable.
- Do not add a runtime dependency without asking.
- **Docs:** update only the docs that name a moved path as a *code reference*
  (`docs/architecture/*`, `docs/guides/memory.md`, `docs/DECISIONS.md`). Do **not**
  rewrite historical audit snapshots under `docs/audit/2026-0[1-6]-*/` — they are
  records of what was true then.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** A rename that misses one lazy import inside a
`try/except ImportError` will not fail at import time — it will silently disable a
feature and only a full run catches it. Two of the imports in §3.3 are inside broad
exception handlers (`gateway/orchestrator.py:1665` and `:3061`), which is exactly that
shape.

Report the **actual** pass/fail counts, and state explicitly that they match the
baseline. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Memory subsystem had no package boundary; 12 flat modules in core/

- **Symptom:** No runtime symptom. 5,838 lines of memory code (12 modules incl. the
  2nd-largest file in `core/`) sat flat in `src/hachi/core/` with nothing marking them
  as one subsystem, so each successive memory initiative added another
  `core/memory_*.py` beside the last.
- **Root cause:** Successive memory initiatives (vault → index → graph → gardener →
  provider) each added a module without consolidating; no package existed to add to.
- **Fix:** Moved all twelve into `src/hachi/core/memory/` with `git mv`, dropping the
  `memory_` prefix inside the package. `__init__.py` re-exports exactly the three
  public names (`MemoryManager`, `extract_facts`, `build_episode_summary`) so the
  three production import sites are zero-diff. Pure move — no behaviour change.
- **Avoid:** when a third module appears with the same domain prefix, create the
  package then, not at the twelfth. And never interleave a wide rename with a
  behavioural fix in one commit — the diff becomes unreviewable and a regression
  rides in for free.
- **Locked by:** `tests/test_memory_package_boundary.py` — `test_no_flat_memory_modules_remain`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3 — highly relevant here:** never `patch.dict(sys.modules)` over `chromadb`.
  `memory_vault.py` constructs the ChromaDB `PersistentClient` (`:537`) and `conftest.py`
  deliberately **warms chromadb at import** so the PyO3 native module loads exactly
  once per process. Leave that warm-up alone. If you are tempted to write a test that
  simulates "memory module missing" by patching `sys.modules`, don't — use
  `importlib.util.find_spec` as §7 does.
- **`core/memory.py` → `core/memory/` is a name collision, not a rename.** The
  directory must exist before `git mv src/hachi/core/memory.py
  src/hachi/core/memory/manager.py` will work, and `__pycache__/memory.cpython-*.pyc`
  can shadow the new package in a dirty tree. If you get a bizarre `ImportError` after
  the move, delete `src/hachi/core/__pycache__/` and retry before debugging anything else.
- **Two lazy imports live inside broad `try/except` blocks** — `gateway/orchestrator.py:1665`
  (`build_graph_recall_section`, wrapped in `except Exception` at `:1676`) and `:3061`
  (`MemoryIndex`, wrapped at `:3060`). A missed rewrite there **fails silently at
  runtime** and no import error surfaces. Grep, don't trust the type checker.
- **Import-linter needs no change.** `pyproject.toml` `[tool.importlinter]` contracts
  name `hachi.core` as a whole (`pyproject.toml:198-205`, `:216-222`);
  `hachi.core.memory` is still inside `hachi.core`. But **re-run the gate anyway** —
  `og_engine/engine.py:579` imports `hachi.core.memory_guard`, and `og_engine` is
  covered by the "og_engine is pure" contract (`pyproject.toml:179-193`). That contract
  forbids gateway/cli/tui/tools/jobs/integrations, not `core`, so the move is legal —
  but verify rather than assume.
- **`_slugify` is imported across module boundaries** — `core/memory.py:233` does
  `from hachi.core.memory_writer import MemoryNode, _slugify`. A private name crossing
  a module boundary is ugly, and it will now cross a *package-internal* boundary. Leave
  it exactly as it is; promoting it to public API is a behaviour-adjacent change and
  belongs to a different task.
- **`memory_vault.py:315` mentions its own import path inside a comment**
  (`# Before this function existed, \`from hachi.core.memory_vault import ...\``). Update
  the path in that comment — but do not delete or reword the comment
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- **34 test files is where the sed goes wrong.** After any bulk rewrite, run
  `git diff -- tests/ | rg -v "^[+-].*import"` and confirm it prints only diff headers.
