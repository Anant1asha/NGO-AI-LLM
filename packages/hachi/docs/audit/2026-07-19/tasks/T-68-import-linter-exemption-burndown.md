# T-68 · Burn down the five gateway import-linter exemptions

|  |  |
|---|---|
| **Source finding** | CF-17 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). **The review's mechanism claim is refuted — read §3.1 before anything else.** |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none, but [T-42](T-42-retire-core-cli-seam.md) owns one of the six entries — **do not duplicate it here** |
| **Blocks** | nothing |
| **Effort** | ~3 days (five independent seams; each is a half-day once you pick its shape) |
| **Difficulty** | High (needs design judgement — read §9) |
| **Files you will touch** | `pyproject.toml`, `src/hachi/core/onboarding.py`, `src/hachi/core/cost.py`, `src/hachi/core/runtime/job_handlers.py`, `src/hachi/core/runtime/resume.py`, `src/hachi/tools/config_tools.py`, plus wherever you put the new protocol, plus `tests/`, `docs/bug-bank.md` |

---

## 1. Brief

The engine layer reaches up into the gateway service in five places. Each is declared as a
frozen exemption in `pyproject.toml`'s import-linter config — **not** a hole in the linter.
Your job is to burn down those five declared seams, not to close a leak.

When you are done, `[tool.importlinter]`'s gateway contract has fewer `ignore_imports`
entries than the five it has today, and `uv run lint-imports` still reports
`Contracts: 3 kept, 0 broken`.

## 2. Why this matters

The layering rail is one of the genuinely strong things in this repo — the review's own
comparative analysis says blocking import-linter with self-cleaning frozen seams *"is rarer
than it should be even at mature companies"*. Its value comes entirely from the exemption
list trending toward zero. A frozen seam that stays frozen for a year is indistinguishable
from no contract at all: the contract still passes, the coupling still exists, and every new
contributor reads the list as a menu of precedents.

The concrete cost is testability. Each of these five imports means a piece of the engine
cannot be exercised — or embedded — without a gateway process. That is the same coupling
[T-73](T-73-skill-engine-collaborators.md) fixes for `SkillEngine` and
[T-41](T-41-extract-in-process-runtime.md) fixes for the CLI monolith. This task is the
layering half of the same story.

If your fix ends with "I moved the import lower in the file" or "I wrapped it in a
try/except", stop and re-read: neither changes the graph, and §3.1 explains why.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 ⚠️ REFUTED — "it escapes import-linter because it's runtime, not import-time"

The review states that `job_handlers.py:435` *"attempts an engine→gateway import inside
try/except — escaping import-linter because it's runtime, not import-time."*

**This is false on both counts.**

1. **grimp (import-linter's graph builder) reads the AST, not the runtime.** A `from ...
   import ...` inside a function body, inside a `try:`, is an edge in the graph exactly like
   a module-level one. Deferring an import hides it from the *interpreter*, never from the
   *linter*.
2. **It does not escape. It is explicitly whitelisted** at `pyproject.toml:234`:

   ```toml
   "hachi.core.runtime.job_handlers -> hachi.gateway.orchestrator",
   ```

**Proof, and you can re-run it.** import-linter fails a contract when an `ignore_imports`
entry matches nothing. Add a bogus entry alongside the four real ones and only the bogus one
is reported:

```
No matches for ignored import hachi.core.nonexistent_module -> hachi.gateway.workspace.
```

The `job_handlers -> gateway.orchestrator` entry produced no such complaint — therefore
grimp **found** that function-local import. See §4 for the copy-pasteable probe.

**Consequence for you: there is no linter bug to fix.** This is a burn-down of declared debt.

### 3.2 ⚠️ Path correction — the file is under `core/runtime/`, not `jobs/`

The review says `jobs/job_handlers.py:435`. `src/hachi/jobs/` contains exactly three
modules — `__init__.py`, `queue.py`, `scheduler.py` — and **no `job_handlers.py`**. The
real path is:

```
src/hachi/core/runtime/job_handlers.py:435
```

The line number `435` coincidentally matches, which makes the wrong path easy to
copy without noticing.

### 3.3 The three contracts — `pyproject.toml:174-237`

Intent, quoted from the config header at `:164-172`:

```toml
# Intended layers (high -> low; higher may import lower, never the reverse):
#   edges    : cli, tui, channels        (entry adapters / transports)
#   service  : gateway, client, sdk      (the REST surface + its consumers)
#   engine   : core, og_engine, tools, jobs, integrations   (the foundation)
#
# Each `ignore_imports` line is a FROZEN, pre-existing inversion seam — visible
# debt to burn down, not a license to add more.
```

**Contract 1 — `pyproject.toml:179-193`. Good news: ZERO exemptions.**

```toml
[[tool.importlinter.contracts]]
name = "og_engine is pure (the .og moat depends on nothing but core)"
type = "forbidden"
source_modules = ["hachi.og_engine"]
forbidden_modules = [
    "hachi.gateway", "hachi.client", "hachi.sdk", "hachi.cli",
    "hachi.tui", "hachi.channels", "hachi.tools", "hachi.jobs", "hachi.integrations",
]
```

No `ignore_imports` key at all. **The `.og` moat is genuinely clean** — nine forbidden
packages, zero declared inversions. Do not disturb it.
(`og_engine` still has a *constructor*-level coupling to a Hachi home directory —
that is [T-73](T-73-skill-engine-collaborators.md), and it is not a layering violation.)

**Contract 2 — `pyproject.toml:195-211`. One exemption, and it is NOT yours.**

```toml
ignore_imports = [
    # SEAM: cold-start resume needs the CLI's Typer app to rebuild a session's
    # command context. Lazy import inside resume(); should move behind a control-plane
    # protocol so core no longer names the CLI. Tracked as an honest seam in memory.
    "hachi.core.runtime.resume -> hachi.cli.main",
]
```

Anchor `pyproject.toml:209`. Real import at `core/runtime/resume.py:124`:

```python
        import hachi.cli.main as _main_mod
```

**Owned by [T-42](T-42-retire-core-cli-seam.md). Do not touch it here.** If T-42 has already
landed, this entry is gone and contract 2 has zero exemptions — confirm, don't assume.

**Contract 3 — `pyproject.toml:213-237`. Five exemptions. This is the task.**

```toml
[[tool.importlinter.contracts]]
name = "the engine must not import the gateway service (freeze known seams)"
type = "forbidden"
source_modules = [
    "hachi.core", "hachi.og_engine", "hachi.tools", "hachi.jobs", "hachi.integrations",
]
forbidden_modules = ["hachi.gateway"]
# Check DIRECT engine->gateway edges only. The one indirect path (core -> cli.main ->
# gateway.workspace) is the cli seam already frozen by the contract above; cli importing
# the gateway is correct edge->service layering, not a new domain coupling.
allow_indirect_imports = "true"
ignore_imports = [
    # SEAMS: these reach up into the gateway for shared-session/workspace services
    # that have no engine-level home yet. All lazy except onboarding. Burn down by
    # introducing a GatewayControlPlane protocol owned by core.
    "hachi.core.onboarding -> hachi.gateway.workspace",
    "hachi.core.cost -> hachi.gateway.shared_services",
    "hachi.core.runtime.job_handlers -> hachi.gateway.orchestrator",
    "hachi.core.runtime.resume -> hachi.gateway.shared_services",
    "hachi.tools.config_tools -> hachi.gateway.workspace",
]
```

### 3.4 The five real import sites

| # | Exemption (`pyproject.toml`) | Real import site(s) | Shape |
|---|---|---|---|
| 1 | `:232` `core.onboarding -> gateway.workspace` | `core/onboarding.py:18` — `from hachi.gateway.workspace import install_optional_skill_pack` | **Module-level.** The only eager one. |
| 2 | `:233` `core.cost -> gateway.shared_services` | `core/cost.py:102` — `from hachi.gateway.shared_services import ProcessSharedServices` | Function-local |
| 3 | `:234` `core.runtime.job_handlers -> gateway.orchestrator` | `core/runtime/job_handlers.py:435` — `from hachi.gateway.orchestrator import _shared  # type: ignore[attr-defined]` | Function-local, inside `try:` |
| 4 | `:235` `core.runtime.resume -> gateway.shared_services` | `core/runtime/resume.py:189` — `from hachi.gateway.shared_services import ProcessSharedServices` | Function-local |
| 5 | `:236` `tools.config_tools -> gateway.workspace` | `tools/config_tools.py:290`, `:347`, `:385` — `from hachi.gateway.workspace import get_skills_dir` | Function-local · **three sites, one exemption** |

Exemption 1 is the odd one out and the highest value: a module-level import means
`import hachi.core.onboarding` drags in the whole gateway package.

Exemption 3 is also broken *behaviourally*, independent of layering — it reaches for a
module global `_shared` that does not exist, so `file.extracted` publishes to a fresh bus
with no subscribers. That is [T-09](T-09-file-extracted-shared-bus.md)'s subject:

```python
        bus: Any = None
        try:
            from hachi.gateway.orchestrator import _shared  # type: ignore[attr-defined]

            bus = getattr(_shared, "event_bus", None)
        except Exception:
            pass

        if bus is None:
            bus = EventBus()
```

Note also that `python -m mypy src/hachi` reports **`Unused "type: ignore" comment`** at
both `job_handlers.py:400` and `:435` — the suppression on that very line is itself dead.

### 3.5 The contracts are self-cleaning — deleting the entry IS the completion signal

Verified today: an `ignore_imports` entry that matches nothing **fails** the run with
`No matches for ignored import <edge>.` So the loop is:

1. Remove the coupling in code.
2. Delete the exemption line.
3. `uv run lint-imports` → still `Contracts: 3 kept, 0 broken`.

And if you remove the coupling but *forget* step 2, the gate fails and tells you exactly
which line to delete. You cannot get this wrong silently.

### 3.6 Baseline — all three contracts pass today

```
Analyzed 237 files, 687 dependencies.

og_engine is pure (the .og moat depends on nothing but core) KEPT
the engine must not import the UI/entry edges (cli, tui) KEPT
the engine must not import the gateway service (freeze known seams) KEPT

Contracts: 3 kept, 0 broken.
```

## 4. Reproduce the failure

There is no runtime failure to reproduce — this is declared debt. What you *can* do is
prove every claim in §3 from a shell.

```bash
# Baseline: green today, with six exemptions in force.
uv run lint-imports

# The five real gateway import sites (matches §3.4 exactly).
rg -n "from hachi\.gateway|import hachi\.gateway" \
   src/hachi/core src/hachi/tools src/hachi/jobs src/hachi/integrations src/hachi/og_engine

# The review's path is wrong — no job_handlers.py here.
ls src/hachi/jobs/

# The exemptions themselves.
sed -n '206,237p' pyproject.toml
```

**Proof that grimp sees function-local imports** (refutes §3.1). Write a probe config to a
scratch path — **do not edit `pyproject.toml` for this** — containing the four `core->gateway`
exemptions **plus one bogus entry**, then run it:

```bash
cat > /tmp/il_probe.ini <<'EOF'
[importlinter]
root_package = hachi
include_external_packages = False

[importlinter:contract:probe]
name = probe: engine must not import gateway
type = forbidden
source_modules =
    hachi.core
forbidden_modules =
    hachi.gateway
allow_indirect_imports = true
ignore_imports =
    hachi.core.onboarding -> hachi.gateway.workspace
    hachi.core.cost -> hachi.gateway.shared_services
    hachi.core.runtime.job_handlers -> hachi.gateway.orchestrator
    hachi.core.runtime.resume -> hachi.gateway.shared_services
    hachi.core.nonexistent_module -> hachi.gateway.workspace
EOF
uv run lint-imports --config /tmp/il_probe.ini
```

**You will see now:**

```
No matches for ignored import hachi.core.nonexistent_module ->
hachi.gateway.workspace.
```

**and nothing about `job_handlers`** — which is the point. The function-local, try-wrapped
import at `job_handlers.py:435` **matched**. If grimp only saw import-time edges, that entry
would have been reported as unmatched too.

**You should see after the fix:** `uv run lint-imports` reports `Contracts: 3 kept, 0 broken`
with strictly fewer `ignore_imports` lines under the gateway contract than the five it has
today.

## 5. What "fixed" looks like

The config's own header already prescribes the shape (`pyproject.toml:229-231`):

> *"Burn down by introducing a GatewayControlPlane protocol owned by core."*

Follow it. Each seam becomes: a `Protocol` **declared in `core/`**, implemented in
`gateway/`, and handed to the engine at composition time. The engine names the protocol; it
never names `hachi.gateway`.

Sequence them cheapest-first — **each is independently landable and independently
verifiable**, so treat this as five small PRs, not one:

**(a) `tools.config_tools -> gateway.workspace` (`:236`) — start here.**
Three call sites all want one thing: `get_skills_dir()`. Core already owns a paths module
(`core/paths.py`, on the mypy strict gate). Either move/mirror the resolution there, or
inject the directory into the tool's construction. One value, three sites, no protocol
needed.

**(b) `core.cost -> gateway.shared_services` (`:233`) and (c) `core.runtime.resume ->
gateway.shared_services` (`:235`).**
Both want `ProcessSharedServices`. This is the natural first `Protocol`: declare the
narrow slice each caller actually uses in `core/`, have `ProcessSharedServices` satisfy it
structurally, and pass it in. Do them together — same target, same protocol, and doing one
alone means designing the protocol twice.

**(d) `core.runtime.job_handlers -> gateway.orchestrator` (`:234`).**
Do **not** design this in isolation. [T-09](T-09-file-extracted-shared-bus.md) is already
fixing the same line for correctness (the `_shared` global does not exist). Coordinate:
whoever lands first should inject the `EventBus` rather than reach for it, which closes both
the correctness bug and the layering seam in one move. **Read T-09 before you touch this
line.** While you are there, drop the dead `# type: ignore[attr-defined]` mypy flags at
`:400` and `:435`.

**(e) `core.onboarding -> gateway.workspace` (`:232`) — hardest, highest value, do last.**
The only module-level import of the five, so it is the only one with an import-time cost,
and `install_optional_skill_pack` is a fatter dependency than a path lookup.
[CORRECTIONS.md](CORRECTIONS.md) §6 flags a related constraint: `core/onboarding.py:526` is
a first-run bootstrap with deliberately merged config semantics — read that note before
restructuring anything in this module.

**Partial completion is a real, good outcome.** Landing (a) alone is a win: one fewer line,
gate still green, nothing else disturbed. Do not hold three seams hostage to the fourth.

## 6. Steps

Per seam — repeat, do not batch:

1. Write the §7 test for **that seam** and watch it fail.
2. Declare the `Protocol` (or move the value) in `core/`.
3. Rewire the engine-side call to depend on the protocol/argument.
4. Wire the concrete gateway implementation in at the composition root.
5. **Delete the `ignore_imports` line from `pyproject.toml`.**
6. `uv run lint-imports` → `Contracts: 3 kept, 0 broken`. If it says
   `No matches for ignored import ...`, you did step 3 but forgot step 5.
7. Run the FULL `uv run python scripts/preflight.py` and report the real counts.
8. Commit. One seam, one commit. Then start the next.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

The layering itself is already locked by `uv run lint-imports` in preflight and CI — **do
not write a pytest test that shells out to import-linter.** That duplicates the gate and
tests the tool, not your change.

The test that matters asserts the thing the seam prevented: **that the engine module works
with no gateway present.** That is the actual regression risk — a "fix" that swaps a direct
import for an indirect one, or a lazy one, and keeps the runtime dependency.

- **File:** `tests/test_engine_gateway_decoupling.py` (**new**)
- **Test name** (one per seam): e.g. `test_config_tools_resolves_skills_dir_without_gateway`
- **It must assert:** the engine-side function returns a real, correct result when
  constructed with the injected collaborator and **no gateway module is imported by it**.
  Assert observed behaviour plus the absence of the module in `sys.modules` after a clean
  import — not that a mock was called.
- **It must FAIL before your fix** with `ImportError` (once the gateway is genuinely
  unavailable) or, on the `sys.modules` assertion,
  `AssertionError: hachi.gateway.workspace was imported`.

```python
# sketch — adapt to the repo's existing fixtures
import subprocess
import sys


def test_config_tools_resolves_skills_dir_without_gateway() -> None:
    """The engine must not need the gateway package to resolve its own paths.

    Regression: tools/config_tools.py reached into hachi.gateway.workspace at three
    call sites, frozen as an import-linter exemption. A lazy import still couples
    the runtime — this asserts the coupling is gone, not merely deferred.
    """
    # Run in a fresh interpreter: sys.modules in the test process is already polluted
    # by the rest of the suite, so an in-process assertion would pass vacuously.
    code = (
        "import sys; import hachi.tools.config_tools as m; "
        "m.<the function you rewired>(); "
        "assert 'hachi.gateway.workspace' not in sys.modules, "
        "'gateway.workspace was imported'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The subprocess is load-bearing: `hachi.gateway.*` is already in `sys.modules` by the time
> most tests run, so the same assertion in-process passes for the wrong reason.

## 8. Acceptance criteria

- [ ] A regression test from §7 exists per seam you closed, and each failed before its fix.
- [ ] `uv run lint-imports` reports `Contracts: 3 kept, 0 broken`.
- [ ] The gateway contract's `ignore_imports` list is **strictly shorter** than the five entries at `pyproject.toml:232-236`.
- [ ] `rg -n "from hachi\.gateway|import hachi\.gateway" src/hachi/core src/hachi/tools src/hachi/jobs src/hachi/integrations src/hachi/og_engine` no longer lists the site(s) you closed.
- [ ] The `og_engine is pure` contract still has **zero** `ignore_imports`.
- [ ] `hachi.core.runtime.resume -> hachi.cli.main` is **untouched** unless [T-42](T-42-retire-core-cli-seam.md) landed it.
- [ ] For each closed seam, the engine-side module imports cleanly in a subprocess with no `hachi.gateway.*` in `sys.modules`.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not touch `hachi.core.runtime.resume -> hachi.cli.main`** (`pyproject.toml:209`,
  `resume.py:124`). It belongs to [T-42](T-42-retire-core-cli-seam.md). Two agents editing
  `resume.py` — which is *also* seam (c) here — is the most likely collision in this task.
  Do (c) only after checking T-42's status.
- **Do not add a new `ignore_imports` entry for anything.** If a fix seems to require one,
  the fix is wrong. The list only shrinks.
- **Do not "fix" a seam by making the import lazier, or by wrapping it in try/except.**
  §3.1: grimp sees it either way, and the runtime coupling is unchanged. The only real fix
  is inverting the dependency.
- **Do not relax the contract to make a seam legal** — do not add to `forbidden_modules`
  exclusions, do not split `source_modules`, do not flip `allow_indirect_imports`.
- **Do not start decomposing `gateway/orchestrator.py` or `cli/main.py`.** Those are
  [T-41](T-41-extract-in-process-runtime.md) / [T-44](T-44-boot-agent-staged-builders.md).
  This task moves *declarations*, not implementations.
- **Do not fix `job_handlers.py`'s `file.extracted` bug** unless you have read and
  coordinated with [T-09](T-09-file-extracted-shared-bus.md). Two independent fixes to the
  same eight lines will conflict.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run lint-imports                          # the specific gate for this task
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite.** Inverting a dependency changes construction order at every
composition root that builds these objects, and Hachi's cross-module regressions do not
surface in scoped runs. Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the highest
today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — A deferred import does NOT escape import-linter

- **Symptom:** an engine→gateway import inside a function body, wrapped in try/except, was
  believed to "escape" the layering gate — leading to the conclusion that the gate had a
  hole and that moving an import into a function was a way to satisfy it.
- **Root cause:** grimp (import-linter's graph builder) reads the AST. A function-local or
  try-wrapped import is an edge in the graph exactly like a module-level one. The import at
  `core/runtime/job_handlers.py:435` was not escaping anything — it was explicitly
  whitelisted in `pyproject.toml` `[tool.importlinter]` `ignore_imports`.
- **Fix:** none needed in the linter. The five engine→gateway edges are declared debt;
  burn them down by inverting the dependency behind a `Protocol` owned by `core/`.
- **Avoid:** never "fix" a layering violation by deferring the import — it changes nothing
  the linter sees and nothing about the runtime coupling. To prove an edge is really gone,
  assert in a FRESH subprocess that the module is absent from `sys.modules`. And remember
  the contracts are self-cleaning: an `ignore_imports` entry that matches nothing FAILS the
  run with `No matches for ignored import <edge>`, so deleting the entry is the completion
  signal for each seam.
- **Locked by:** `uv run lint-imports` (blocking in `scripts/preflight.py` and CI);
  `tests/test_engine_gateway_decoupling.py`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Seams (b) and (c) both
  target it — your protocol must tolerate the not-yet-booted state, and your test must cover
  it. Do not paper over it with a `getattr` default (that idiom is
  [T-14](T-14-ban-getattr-own-types.md)'s subject and it masked at least three shipped bugs).
- **`.import_linter_cache/` exists at the repo root.** If a result looks stale after a
  restructure, delete it and re-run before you start debugging your change.
- **The exemption strings must match grimp's module names exactly**, not file paths.
  `hachi.core.runtime.job_handlers`, never `src/hachi/core/runtime/job_handlers.py`.
- **`tools/config_tools.py` has THREE import sites behind ONE exemption** (`:290`, `:347`,
  `:385`). Missing one leaves the edge in the graph, the exemption still matching, and no
  signal that you are half-done. Grep before you delete the line.
- **`allow_indirect_imports = "true"`** (`pyproject.toml:227`) is a **string**, not a bool,
  and the surrounding comment explains why the indirect `core -> cli.main -> gateway.workspace`
  path is deliberately not checked. Do not "tidy" it to a bool or flip it while burning down
  seams — you will turn on a whole class of findings that are out of scope here.
- **`core/onboarding.py` is a first-run bootstrap.** [CORRECTIONS.md](CORRECTIONS.md) §6
  records that `:526` must keep *merged* config-write semantics; a blanket refactor of this
  module breaks onboarding. Read it before seam (e).
