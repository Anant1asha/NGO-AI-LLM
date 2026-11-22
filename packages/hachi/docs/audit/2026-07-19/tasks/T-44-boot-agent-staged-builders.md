# T-44 · Decompose `boot_agent` into staged builders

|  |  |
|---|---|
| **Source finding** | CF-6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | [T-40](T-40-emit-runtime-event-closure-capture.md), [T-45](T-45-boot-agent-constructor-stashes.md), [T-35](T-35-google-double-mount.md), [T-39](T-39-tool-groups-at-registration.md) — *do not start until all four have landed* |
| **Blocks** | nothing |
| **Effort** | ~2 weeks |
| **Difficulty** | High (needs design judgement — read §9) |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, `src/hachi/gateway/boot/` (new package), `tests/test_boot_agent_stages.py` (new), several existing boot tests |

---

## 1. Brief

`boot_agent` is **1,138 lines in a single function** with **only 3 parameters** — every other
value it manipulates is closure state. It is the composition root: permissions, config, skill
engine, integrations, MCP, LLM provider, routing, memory, tools, prompt, loop, and session all
get built here, in one scope, in an order its own comments misreport. Split it into staged
builders that each take typed inputs and return a typed result.

**This is the largest task in the pack.** Four other tasks must land first, and one of them
([T-40](T-40-emit-runtime-event-closure-capture.md)) changes the closure structure you would
otherwise be decomposing.

## 2. Why this matters

3 parameters and 1,138 lines is the diagnosis, not a curiosity: **the function resists
decomposition precisely because nothing is passed — everything is captured.** Any two lines
may be coupled through a name neither of them declares, so you cannot lift a block out
without proving what it reads and what it writes. That property is what makes each new
feature O(understand-everything) and what makes this the file where every feature collides
(~85 touches since April, in a 3,694-line module).

The payoff is not aesthetic. Staged builders make the boot **dependency graph explicit and
testable in isolation** — which is what a feature-liveness boot smoke (CF-1's central
recommendation) needs to exist at all. Today you cannot assert "the vault carried the
configured settings" without booting the whole agent.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The function

`src/hachi/gateway/orchestrator.py:2557-3694` — **1,138 lines**, the tail of a 3,694-line
module. The signature, `:2557-2561`:

```python
def boot_agent(
    on_event: Callable[..., None] | None = None,
    on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None = None,
    resume_session_id: str | None = None,
) -> AgentSession:
```

**Three parameters. That is the core difficulty and you should hold it in mind throughout.**
Every other object in those 1,138 lines — `config`, `runtime_gate`, `tool_registry`,
`skill_engine`, `mcp_manager`, `memory_manager`, `credential_vault`, `read_models`,
`_event_bus`, `cost_tracker`, `scheduler`, `_provider_registry`, `secret_store`,
`sub_agent_client`, `browser_controller`, `system_prompt` — is a local bound in one place and
read in several others, often hundreds of lines apart. There is no signature anywhere that
records those relationships.

### 3.2 The 14 markers — the decomposition map

Verbatim, in **physical file order**:

| # | Line | Marker text |
|---|---|---|
| 1 | `:2627` | `# 0. Load Device Permissions (BEFORE anything else)` |
| 2 | `:2665` | `# 1. Load Local Configuration and Brain` |
| 3 | `:2787` | `# 2. Initialize the Skill Engine (the .og brain).` |
| 4 | `:2818` | `# 3. Initialize the Integration Runtime (direct SMTP/HTTP connections)` |
| 5 | `:2839` | `# 4. Initialize MCP Manager (dynamically configured from permissions)` |
| 6 | `:2865` | `# 5. Collect stable-base ingredients (prompt assembled after tool registration below)` |
| 7 | `:2881` | `# 6. Initialize the LLM Provider` |
| 8 | `:2896` | `# 6b. Build routing infrastructure (behind [routing] flag; absent = back-compat).` |
| 9 | `:2983` | `# 7. Initialize the Memory Manager (Moved up so Vault can bind to it)` |
| 10 | `:2999` | `# 8. Build infrastructure objects needed for tool registration.` |
| 11 | `:3111` | `# 8b. Declarative tool registration — ordering constraints are explicit in the` |
| 12 | **`:3379`** | **`# 5.5 Assemble the stable base system prompt via PromptComposer (single call site).`** |
| 13 | `:3399` | `# 9. Instantiate the Brain Loop (cost_tracker created earlier, shared with sub-agents)` |
| 14 | `:3450` | `# 10. Create the Session` |

11 integer steps (0–10) plus three sub-steps (6b, 8b, 5.5). Regenerate:

```bash
awk 'NR>=2557 && NR<=3694' src/hachi/gateway/orchestrator.py \
  | grep -n "^    # [0-9]" | awk -F: '{print $1+2556": "$2}'
```

### 3.3 ⚠️ THE MOST IMPORTANT WARNING IN THIS SPEC: the numbering lies about execution order

**Step 5.5 is physically located at `:3379` — after step 8b at `:3111`.** It executes
*eleventh*, not sixth. Anyone who decomposes by reading the numbers will build a stage graph
that is wrong at exactly the point where it matters most: the system prompt.

Two comments are **scar tissue from prior reorderings**, and both are load-bearing warnings
the numbers contradict:

`:2865` — step 5 tells you its own output is deferred:

```python
    # 5. Collect stable-base ingredients (prompt assembled after tool registration below)
    total_tools = integration_count + mcp_tool_count
```

`:2983` — step 7 tells you it was hoisted out of numeric order:

```python
    # 7. Initialize the Memory Manager (Moved up so Vault can bind to it)
```

`:3379` — and step 5.5 is the deferred assembly, now sitting 500 lines below its number:

```python
    # 5.5 Assemble the stable base system prompt via PromptComposer (single call site).
    system_prompt = build_stable_base(
        brain_text=brain_prompt,
        skill_count=skill_count,
```

**A staged-builder decomposition must encode the REAL dependency graph, not the numbering.**
The real edge is: *prompt assembly depends on tool registration* (the tool count and group
names go into the prompt), so `BuildPrompt` is a **downstream** stage of `RegisterTools`, not
an upstream one. Likewise the memory manager must be constructed before the credential vault
binds to it — that is a real edge the number "7" hides.

**Before you write a single stage, derive the dependency graph empirically.** Do not read it
off the comments:

```bash
# For each local bound in boot_agent, find its assignment and all its reads.
# Anything read ABOVE its own number, or bound BELOW a later number, is a lie in the comments.
awk 'NR>=2557 && NR<=3694' src/hachi/gateway/orchestrator.py \
  | grep -nE "^    [a-z_][a-z_0-9]* = " | awk -F'[: ]' '{print $1+2556, $2}'
```

Cross-check every candidate stage boundary by confirming that no name assigned below it is
read above it. **Renumber the comments to physical order as part of this task** — leaving them
wrong re-arms the trap for the next reader.

### 3.4 Unnumbered blocks that are also decomposition boundaries

The numbered markers are not the whole structure. Six unnumbered banner-comment blocks carve
out further stages; a decomposition that ignores them will split mid-concern.

| Lines | What it is |
|---|---|
| `:2588-2598` | EventBus funnel setup — `# Slice 2.2 — EventBus funnel (gated behind [events] bus_funnel=true)` |
| `:2705-2710` | Rebind — `# Slice 2.2 — EventBus funnel: rebind emit/relay through the bus when [events] bus_funnel=true.` |
| `:2768-2770` | `# End EventBus funnel wiring` |
| `:3498-3511` | `# JobRegistry activation` |
| `:3659-3667` | `# Slice 2.2 — A4: scheduler timeout sweep for WAITING runs.` |
| `:3671-3675` | `# E5 — Weekly failure-report scheduler (opt-in, default off).` |

The first three bracket the closure hazard that [T-40](T-40-emit-runtime-event-closure-capture.md)
addresses: `emit_runtime_event` is defined at `:2601` and **redefined at `:2747`** with
`# noqa: F811`, alongside a `relay_event` redefinition at `:2756`. The same name means
different things at different line numbers — hostile to humans and to tooling, and fatal to a
naive lift-and-shift.

### 3.5 Why the four dependencies must land first

| Task | Why it blocks T-44 |
|---|---|
| [T-40](T-40-emit-runtime-event-closure-capture.md) | **Changes the closure structure itself.** It resolves the `:2601` / `:2747` redefinition. Decomposing first means decomposing a shape that is about to change, then redoing it. |
| [T-45](T-45-boot-agent-constructor-stashes.md) | Mechanical, ~2 days, and it removes ten post-construction attribute writes (`:3467`–`:3657`) that otherwise sit *across* your stage boundaries. Landing it first shrinks T-44's tail. |
| [T-35](T-35-google-double-mount.md) | Edits the tool-registration block `:3111-3377`, **inside** `boot_agent`. |
| [T-39](T-39-tool-groups-at-registration.md) | Same block. |

T-35 and T-39 rewrite lines you are about to relocate. Land them first or force a painful
rebase on someone.

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor. `boot_agent` works.** There is no crash, no wrong output, no
user-visible symptom. Do not invent one. Here is how to see the problem:

```bash
# 1. One function, 1,138 lines.
awk 'NR>=2557 && NR<=3694' src/hachi/gateway/orchestrator.py | wc -l

# 2. Three parameters. Everything else is closure state.
sed -n '2557,2561p' src/hachi/gateway/orchestrator.py

# 3. The numbering lies: 5.5 sits AFTER 8b.
awk 'NR>=2557 && NR<=3694' src/hachi/gateway/orchestrator.py \
  | grep -n "^    # [0-9]" | awk -F: '{print $1+2556": "$2}'

# 4. The same name is two different functions.
grep -n "def emit_runtime_event\|noqa: F811" src/hachi/gateway/orchestrator.py
```

**You will see now:** step 3 prints `# 5.5 …` at line 3379, between `# 8b …` (3111) and
`# 9. …` (3399); step 4 prints two definitions of `emit_runtime_event` (`:2601`, `:2747`).
**You should see after the fix:** `boot_agent` is a short orchestration function calling
named stages; step 3 prints nothing (the numbered comments are gone, replaced by stage names);
each stage is independently constructible in a test.

## 5. What "fixed" looks like

A `boot` package of stage functions, each with a typed input and a typed result, and a
`boot_agent` that reads as a sequence.

```python
# src/hachi/gateway/boot/__init__.py (new package)
```

```python
# src/hachi/gateway/boot/stages.py
"""Staged builders for agent boot.

Each stage takes an explicit input and returns a frozen result. The stage
ORDER below is the REAL dependency order, which is NOT the order the old
numbered comments implied — see T-44 §3.3. In particular, prompt assembly
is DOWNSTREAM of tool registration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionsStage:
    gate: PermissionGate
    runtime_gate: InteractivePermissionGate | None
    action_approver: ActionApprover


@dataclass(frozen=True, slots=True)
class ConfigStage:
    config: ResolvedConfig
    brain_prompt: str
    paths: HachiPaths


@dataclass(frozen=True, slots=True)
class ToolsStage:
    tool_registry: ToolRegistry
    total_tools: int
    skill_group_names: frozenset[str]
    domain_groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptStage:
    system_prompt: str          # depends on ToolsStage — NOT on step "5"
```

and the target `boot_agent`:

```python
def boot_agent(
    on_event: Callable[..., None] | None = None,
    on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None = None,
    resume_session_id: str | None = None,
) -> AgentSession:
    events = build_event_plumbing(on_event)
    perms = build_permissions(on_permission_request, events)
    cfg = build_config_and_brain()
    skills = build_skill_engine(cfg)
    integrations = build_integrations(cfg, perms)
    mcp = build_mcp(cfg, perms)
    llm = build_llm_provider(cfg)
    routing = build_routing(cfg, llm, events)
    memory = build_memory(cfg, llm)
    infra = build_tool_infrastructure(cfg, memory, perms)
    tools = register_tools(cfg, skills, integrations, mcp, infra, perms)
    prompt = build_prompt(cfg, skills, tools, perms)      # ← downstream of tools
    loop = build_brain_loop(cfg, llm, routing, tools, prompt, memory, events)
    return build_session(loop, ...)
```

**Decisions already made — do not re-litigate:**

1. **Stages return frozen dataclasses**, matching the repo's existing idiom
   (`core/runtime_read_models.py` uses `@dataclass(frozen=True, slots=True)` for all 14 of
   its snapshots). Not dicts, not tuples, not `NamedTuple`.
2. **Stage order follows the REAL graph** you derived in §3.3, not the comment numbering.
   `build_prompt` comes after `register_tools`. **This is non-negotiable and is the point of
   the task.**
3. **New package `src/hachi/gateway/boot/`**, not more top-level functions in
   `orchestrator.py`. The module is already 3,694 lines.
4. **Stages take explicit inputs.** A stage that reaches for a module global, or that takes
   `**kwargs`, has reproduced the closure problem in a new file. If a stage needs 9 inputs,
   pass 9 inputs — the arity is information, and it is exactly the information the current
   code destroys.
5. **`boot_agent` keeps its 3-parameter signature and its name.** It has 13+ call sites and a
   documented contract. This task changes its body, not its interface.
6. **Renumber or delete the step comments** as you go. A stage named `build_memory` does not
   also need `# 7.`; leaving a stale number behind re-arms §3.3.
7. **Zero behaviour change.** Same objects, same order, same side effects, same events
   emitted in the same sequence.

## 6. Steps

**This cannot be one commit. Nine, minimum — one per stage wave, verbatim-move-first
throughout.**

### Commit 1 — the dependency graph (documentation + characterization tests)

1. Derive the real read/write graph for every local in `boot_agent` (§3.3). Write it down —
   a table of `name → assigned at → read at` — and put it in the PR description. **This
   artifact is the deliverable of commit 1**; everything after depends on its correctness.
2. Write the characterization tests from §7. They must pass against today's code.
3. Record full-suite baseline counts.

### Commit 2 — the package and the boundary types

4. Create `src/hachi/gateway/boot/` with `stages.py` holding only the frozen result
   dataclasses. Nothing imports it yet. This commit adds no behaviour.

### Commits 3–9 — extract stages, leaves first

Extract in this order. Each stage: **cut the block verbatim into a function, add the
parameters it actually reads, return the frozen result, call it from `boot_agent`.** Run the
full suite after every single one.

| Commit | Stage | Source block |
|---|---|---|
| 3 | `build_permissions` | `:2627-2664` (step 0) |
| 4 | `build_config_and_brain` | `:2665-2786` (step 1) |
| 5 | `build_skill_engine`, `build_integrations`, `build_mcp` | `:2787-2864` (steps 2–4) |
| 6 | `build_llm_provider`, `build_routing` | `:2881-2982` (steps 6, 6b) |
| 7 | `build_memory`, `build_tool_infrastructure` | `:2983-3110` (steps 7, 8) |
| 8 | `register_tools` | `:3111-3377` (step 8b) — **rebase target for T-35/T-39** |
| 9 | `build_prompt`, `build_brain_loop`, `build_session` | `:3379-3694` (steps 5.5, 9, 10) |

⚠️ **Commit 9 is where §3.3 bites.** `build_prompt` must take `ToolsStage` as an input. If
you find yourself needing to call it *before* `register_tools` to satisfy a "5.5 comes after
5" intuition, stop — you are following the numbering, not the graph.

⚠️ **The event plumbing (`:2588-2598`, `:2705-2710`, `:2768-2770`) is extracted FIRST or
LAST, never in the middle.** It brackets almost the entire function. Prefer first, as
`build_event_plumbing`, so every later stage receives an already-resolved emitter rather than
capturing one that gets rebound behind its back. [T-40](T-40-emit-runtime-event-closure-capture.md)
should have already made this tractable — if it has not, stop and re-read T-40's outcome.

### After the last stage

5. Delete the numbered comments (§5 decision 6).
6. `wc -l` on the new `boot_agent` body: it should be under ~80 lines.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug, so the instrument is a **characterization test**: pin the
observable output of boot — the ordering, the wiring, the emitted events — *before* you move
anything, so the decomposition is provably behaviour-neutral.

- **File:** `tests/test_boot_agent_stages.py` (new)
- **Test names:** `test_boot_emits_events_in_a_stable_order`,
  `test_prompt_reflects_registered_tool_count`,
  `test_booted_session_has_the_expected_wiring`
- **They must assert:** the real observed boot output — the event sequence, the tool count
  embedded in the prompt, the identity of objects hung off the session — not a mock's return
  value.
- **They PASS before the refactor and must still pass after.** That is what characterization
  means, and it is the correct application of Rule 2 here.

```python
# sketch — adapt to the repo's existing fixtures
def test_boot_emits_events_in_a_stable_order(tmp_path, monkeypatch) -> None:
    """Pin the boot event sequence so a stage reordering cannot pass silently.

    This is the single highest-value guard in the task: stage extraction that
    changes WHEN an event fires is exactly the failure mode.
    """
    seen: list[str] = []
    session = boot_agent(on_event=lambda name, payload: seen.append(name))
    try:
        # Compare against the recorded baseline, not a hand-written guess.
        assert seen == EXPECTED_BOOT_EVENTS
    finally:
        session.shutdown()


def test_prompt_reflects_registered_tool_count(tmp_path) -> None:
    """The system prompt is built FROM the tool registry — T-44 §3.3.

    If a decomposition moves prompt assembly upstream of tool registration
    (following the misleading "5.5" numbering), the count goes stale and
    this test catches it.
    """
    session = boot_agent()
    try:
        prompt = session._loop.system_prompt          # adapt to the real attribute
        registered = len(session._tool_registry.list_tools())
        assert str(registered) in prompt
        assert registered > 0
    finally:
        session.shutdown()


def test_booted_session_has_the_expected_wiring(tmp_path) -> None:
    """Every collaborator boot is supposed to attach is actually attached."""
    session = boot_agent()
    try:
        for attr in (
            "_sub_agent_client", "_browser_controller", "_provider_registry",
            "_secret_store", "_schedule_runner", "_scheduler",
        ):
            assert hasattr(session, attr), f"boot dropped {attr}"
    finally:
        session.shutdown()
```

> Generate `EXPECTED_BOOT_EVENTS` **once, from a real run against `main`**, and paste the
> literal list. A test that captures the sequence from the code under test asserts nothing.
> If the list is environment-dependent, assert on the *relative order* of a stable subset
> rather than dropping the test.

The third test overlaps [T-45](T-45-boot-agent-constructor-stashes.md)'s coverage
deliberately — after T-45 those become constructor args, and the assertion should be updated
to check the constructor, not `hasattr`. Coordinate rather than duplicating.

## 8. Acceptance criteria

- [ ] The characterization tests from §7 exist and passed before the refactor.
- [ ] **The dependency-graph table from §6 step 1 is attached to the PR.** A reviewer must be
      able to check your stage order against it without re-deriving it.
- [ ] The `boot_agent` body is under ~80 lines and reads as a sequence of named stage calls.
- [ ] `src/hachi/gateway/boot/` exists; every stage takes explicit parameters and returns a
      frozen dataclass. **No stage reads a module global; no stage takes `**kwargs`.**
- [ ] `build_prompt` takes the tool-registration result as an input, and this is visible in
      its signature.
- [ ] `grep -n "^    # [0-9]" src/hachi/gateway/orchestrator.py` returns nothing inside the
      former `boot_agent` range — the misleading numbering is gone, not just moved.
- [ ] `grep -n "noqa: F811" src/hachi/gateway/orchestrator.py` returns nothing in the boot
      path (T-40 should have removed it; confirm it did not come back).
- [ ] Nine or more commits, each green on its own.
- [ ] Boot event sequence is byte-identical to the recorded baseline.
- [ ] Full-suite counts identical to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving code.** Primary boundary. Same objects, same
  construction order, same side effects, same events, same sequence. If boot ends up faster,
  slower, or quieter, you changed something.
- **Do not trust the step numbers** (§3.3). This is the specific way this task goes wrong.
- Do not change `boot_agent`'s signature or name (§5 decision 5).
- Do not fold [T-45](T-45-boot-agent-constructor-stashes.md)'s stash promotion into this diff
  — it is a separate task with a separate test file, and it must land *before* you start.
- Do not fix the tool-registration block's contents — that is
  [T-35](T-35-google-double-mount.md) and [T-39](T-39-tool-groups-at-registration.md),
  both of which land first. Move the block; do not edit it.
- Do not "improve" the `except Exception` handlers you pass on the way. CF-1 tracks those
  separately, and changing failure behaviour inside a 1,138-line move is unreviewable.
- Do not move `AgentSession` read models — that is
  [T-46](T-46-session-read-models-facade.md), which touches a disjoint line range.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3). On a
  diff this size it would make the review impossible.
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on. You will notice
  many.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop, after EVERY stage extraction
uv run python scripts/preflight.py           # before you call it done
uv run lint-imports                          # the new boot/ package must not break layering
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — `boot_agent`'s numbered step comments misreported execution order

- **Symptom:** `boot_agent` carried steps numbered 0–10 plus 6b, 8b, and 5.5. Step 5.5
  (system-prompt assembly) was physically located at `orchestrator.py:3379` — *after* step 8b
  at `:3111`. Two further comments ("prompt assembled after tool registration below",
  "Moved up so Vault can bind to it") were scar tissue from earlier reorderings.
- **Root cause:** Blocks were reordered to satisfy real dependencies; the numbers were never
  renumbered, so the comments recorded the *original* intent while the code recorded the
  *actual* graph.
- **Fix:** Decomposed boot into named stages whose parameters encode the real dependency
  graph (prompt assembly is downstream of tool registration); deleted the numbering.
- **Avoid:** Never encode execution order in a comment that a later edit can silently
  invalidate. If ordering is load-bearing, express it as a data dependency in a signature.
- **Locked by:** `tests/test_boot_agent_stages.py` — `test_prompt_reflects_registered_tool_count`
```

## 12. Known traps

- **The numbering trap (§3.3).** The single most likely way this task ships wrong. Re-read it
  before commit 9.
- **The closure trap.** A stage that still reads a name it does not take as a parameter has
  reproduced the problem in a new file and will pass every test. Grep each new stage function
  for free variables before you commit it.
- **Rebinding.** `emit_runtime_event` exists twice (`:2601`, `:2747`). If a stage captures the
  first and is called after the rebind, events silently bypass the bus.
  [T-40](T-40-emit-runtime-event-closure-capture.md) must have landed.
- **Same-file concurrency.** `gateway/orchestrator.py` is touched by eleven tasks (T-01, T-06,
  T-07, T-08, T-26, T-35, T-39, T-40, T-44, T-45, T-46). Serialize or accept the merge cost;
  over two weeks, this file will move under you.
- **BB-4:** if a boot change alters any gateway response shape, regenerate the OpenAPI spec
  **and** the frontend API types. This task should change none.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`. Boot touches the memory stack;
  this is a live hazard here.
- **BB-5:** `paths.workspace_dir` does not exist — use `paths.skills_dir`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots. Boot is precisely where
  it transitions; do not "simplify" a `getattr` guard on the way past.
