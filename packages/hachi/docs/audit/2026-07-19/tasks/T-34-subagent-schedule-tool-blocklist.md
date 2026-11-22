# T-34 · Fix the sub-agent tool blocklist so it actually blocks the schedule mutators

|  |  |
|---|---|
| **Source finding** | **NEW — not in the audit.** Same drift class as CF-11 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P0** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing — but **ship it first** (see below) |
| **Effort** | ~1 hour |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/tools/delegation_tools.py`, `tests/test_delegation_blocklist_integrity.py` (new), `tests/test_security_hardening.py`, `docs/bug-bank.md` |

---

> ## ⚠️ THIS IS THE ONLY FINDING IN THE CF-11 SET THAT **FAILS OPEN**
>
> Every other task in this wave describes something that is broken *shut* — a dead branch, a
> tool that is denied, a group that never activates. This one is a hole. The declared security
> boundary for sub-agents does not cover the two tools that mutate the schedule store, and
> nothing anywhere else catches it.
>
> **Ship this before T-35, T-36, and T-39.** It is one hour of work and it is the only item in
> the set where the current behaviour is *more permissive* than the design says it is.

---

## 1. Brief

`BLOCKED_TOOL_NAMES` in `tools/delegation_tools.py` is documented as *"the security boundary"*
for sub-agents. Its scheduling section blocks `schedule_task` — **a tool that does not exist** —
while the two tools that actually mutate the schedule store, `create_schedule` and
`delete_schedule`, are absent from the list and pass straight through to every sub-agent.
When you are done, the list will name the real registered tools, and a test will fail loudly
the next time an entry drifts away from a real tool name.

## 2. Why this matters

Sub-agents are delegated work by the main agent with a deliberately narrowed tool surface. The
narrowing is the entire safety story for delegation: a sub-agent is untrusted-ish code driven by
a model that the user never sees prompt-by-prompt. The blocklist is the layer that says "no
matter what role .og you write, these things are off-limits" — recursive spawning, memory writes,
identity mutation, and privileged main-agent actions. `create_schedule` writes a durable,
recurring, autonomously-firing instruction into the user's schedule store. A sub-agent that can
call it can arrange for arbitrary future agent turns; a sub-agent that can call `delete_schedule`
can silently remove the user's existing automation. Both are exactly the class of action the
blocklist exists to prevent, and both are reachable today.

The second half of the fix matters as much as the first: the reason this survived is that
**nothing checks the strings in the blocklist against reality**. Fixing only the four strings
leaves the identical trap armed for the next tool that gets renamed. Both halves ship together.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The blocklist and its own description of itself

`src/hachi/tools/delegation_tools.py:140-147`

```python
# These tools are NEVER available to sub-agents.
# This is the security boundary that prevents:
# - Recursive spawning (delegate_task, list_roles)
# - Uncontrolled memory writes (core_save_memory, core_save_user_profile)
# - Memory reads that could leak cross-session data
# - Workflow manipulation (suspend_workflow)
# - Session state corruption (core_search_sessions)
BLOCKED_TOOL_NAMES = frozenset(
```

`src/hachi/tools/delegation_tools.py:166-173` — the tail of the set. Note line 166: the author
**already hit this exact drift class once**, fixed it, and left a comment about it — then missed
the adjacent case four lines below.

```python
        # Workflow control (registered name is core_suspend_workflow)
        "core_suspend_workflow",
        # Skill authoring + scheduling are privileged main-agent actions
        "save_skill",
        "schedule_task",
        "list_schedules",
        "cancel_schedule",
    }
)
```

### 3.2 The real registered names

`src/hachi/tools/schedule_tools.py:86-87` — the constant is named `SCHEDULE_TASK_SCHEMA`, but
the `"name"` field the registry keys on is `create_schedule`:

```python
SCHEDULE_TASK_SCHEMA = {
    "name": "create_schedule",
```

`src/hachi/tools/schedule_tools.py:137-138` — same trap:

```python
CANCEL_SCHEDULE_SCHEMA = {
    "name": "delete_schedule",
```

`src/hachi/tools/schedule_tools.py:153-157` — the alias, which *is* correctly blocked:

```python
_CANCEL_ALIAS_SCHEMA = {
    **CANCEL_SCHEDULE_SCHEMA,
    "name": "cancel_schedule",
    "description": "Alias for delete_schedule — cancel a proactive schedule by its schedule_id.",
}
```

`src/hachi/tools/schedule_tools.py:160-165` — all four are registered:

```python
def register_schedule_tools(registry: ToolRegistry, scheduler: Scheduler) -> None:
    """Mount the scheduling tools onto the provided ToolRegistry."""
    registry.register(SCHEDULE_TASK_SCHEMA, _make_schedule_task(scheduler))
    registry.register(LIST_SCHEDULES_SCHEMA, _make_list_schedules(scheduler))
    registry.register(CANCEL_SCHEDULE_SCHEMA, _make_cancel_schedule(scheduler))
    registry.register(_CANCEL_ALIAS_SCHEMA, _make_cancel_schedule(scheduler))
```

**Where the confusion comes from** — `src/hachi/tools/schedule_tools.py:18-19` defines a *Python
function* called `schedule_task`, which is the handler for the tool named `create_schedule`:

```python
def _make_schedule_task(scheduler: Scheduler) -> Callable[..., str]:
    def schedule_task(
```

So `grep schedule_task` hits a real definition. It is the handler's identifier, never a tool name.

### 3.3 Where the blocklist is applied — stage 1 of 3

`src/hachi/tools/delegation_tools.py:268-274`, inside `_build_scoped_registry`:

```python
    for schema in parent_registry.get_schemas():
        tool_name = schema.get("name", "")

        # Stage 1: Security block
        if tool_name in BLOCKED_TOOL_NAMES:
            logger.debug("Blocked tool '%s' from sub-agent registry", tool_name)
            continue
```

`src/hachi/tools/delegation_tools.py:289-291` — surviving tools are copied with the parent's
**live handler**, bound to the parent's real `Scheduler`:

```python
        handler = parent_registry._tools.get(tool_name)
        if handler:
            scoped.register(schema, handler)
```

Note that `scoped.register(schema, handler)` omits `group=`, so it defaults to `"core"`
(`core/loop.py:174`). Whatever lazy group a tool had on the parent registry is **discarded** in
the sub-agent's registry — `create_schedule` is `"schedule"` on the parent (hidden until the model
calls `use_tools("schedule")`) but plain `"core"` on the sub-agent, i.e. visible on every turn
without unlocking anything.

### 3.4 `create_schedule` is genuinely on the parent registry

`src/hachi/gateway/orchestrator.py:3256-3259` — the `TOOL_SPECS` entry that mounts it:

```python
        ToolSpec(
            name="schedule",
            register_fn=lambda d: register_schedule_tools(d.tool_registry, d.scheduler),
        ),
```

`_build_scoped_registry` filters *from* that parent registry, so the tool is reachable.

### 3.5 The exposure bound — state this precisely, do not overstate

Stage 2 of `_build_scoped_registry` is the role `.og`'s `::meta tools:` allowlist
(`src/hachi/tools/delegation_tools.py:266`, `:277-286`):

```python
    has_filter = bool(allowed_prefixes or allowed_exact)
```

- Role with **no** `tool_patterns` → `has_filter` is `False` → **every non-blocked tool passes**.
  The docstring at `:235-236` calls this the backward-compatibility default. These roles get
  `create_schedule` and `delete_schedule`.
- Role with a narrow `tool_patterns` that does not match `create_schedule` → does **not** get it.

So: **this is not "every sub-agent always". It is "every sub-agent whose role declares no tool
allowlist".** Say it that way in the bug-bank entry too.

### 3.6 Two further stale entries — you will hit these, so know about them now

An exhaustive AST scan of every tool-schema literal under `src/hachi/` (120 names) against the
17 entries in `BLOCKED_TOOL_NAMES` finds **three** names that match no registered tool:

| Stale entry | Real situation | Security impact |
|---|---|---|
| `schedule_task` | Real tools are `create_schedule` / `delete_schedule`, both unblocked | **The hole. This is the finding.** |
| `core_save_agent_profile` | No such tool is registered anywhere | None — inert |
| `core_delete_agent_profile` | No such tool is registered anywhere | None — inert |

The two agent-profile names are inert because the tools genuinely do not exist:
`src/hachi/tools/memory_tools.py:291` and `:303` define inner functions `save_agent_profile` /
`delete_agent_profile` that are **never passed to `registry.register`** — the registration block
at `:335-660` mounts `core_save_memory`, `core_search_memory`, `core_delete_memory`,
`core_save_user_profile`, `core_search_user_profile`, `core_delete_user_profile`,
`core_save_user_profile_structured`, and `core_search_sessions`, and nothing else. That is a
separate dead-code finding — **§9 says do not fix it here.**

### 3.7 There is no test that would have caught this

`tests/test_security_hardening.py:49-57` is the closest thing, and it **asserts the bug**:

```python
def test_sub_agent_blocklist_covers_privileged_tools() -> None:
    # The registered name is core_suspend_workflow (the old "suspend_workflow"
    # entry silently failed to match).
    assert "core_suspend_workflow" in BLOCKED_TOOL_NAMES
    assert "suspend_workflow" not in BLOCKED_TOOL_NAMES
    for name in ("save_skill", "schedule_task", "list_schedules", "cancel_schedule"):
        assert name in BLOCKED_TOOL_NAMES
    # Delegation itself must still be blocked (no recursive spawning).
    assert "delegate_task" in BLOCKED_TOOL_NAMES
```

Read the comment on lines 50-51, then read line 54. The author fixed the `suspend_workflow` →
`core_suspend_workflow` drift, documented it, and in the next statement asserted `schedule_task`
— a string that has never been a tool name. **The test asserts membership in a set of strings and
never asks whether those strings name anything real.** That is the whole bug in one function.

`tests/test_delegation_failclosed.py` (10 tests: `test_resolve_failure_returns_abort_message`,
`test_depth_limit_blocks_delegation`, `test_cycle_detection_blocks_delegation`, …) covers depth,
cycles, leases, and `.og` failures. It does not touch `BLOCKED_TOOL_NAMES`.
`tests/test_parallel_delegation.py:250` asserts only `"delegate_parallel_tasks" in BLOCKED_TOOL_NAMES`.

## 4. Reproduce the failure

This one **is** reproducible from a shell, and both commands below were run against
`main` @ `bd24afe` — the outputs are real, not predicted.

### 4.1 The name mismatch

```bash
uv run python -c "
from hachi.tools.delegation_tools import BLOCKED_TOOL_NAMES
from hachi.tools.schedule_tools import (SCHEDULE_TASK_SCHEMA, CANCEL_SCHEDULE_SCHEMA,
                                        LIST_SCHEDULES_SCHEMA, _CANCEL_ALIAS_SCHEMA)
real = [s['name'] for s in (SCHEDULE_TASK_SCHEMA, LIST_SCHEDULES_SCHEMA,
                            CANCEL_SCHEDULE_SCHEMA, _CANCEL_ALIAS_SCHEMA)]
print('registered schedule tools:', real)
for n in real:
    print(f'  {n:18} blocked={n in BLOCKED_TOOL_NAMES}')
print('schedule_task in BLOCKED_TOOL_NAMES =', 'schedule_task' in BLOCKED_TOOL_NAMES)
print('schedule_task is a registered name  =', 'schedule_task' in real)
"
```

**You will see now:**

```
registered schedule tools: ['create_schedule', 'list_schedules', 'delete_schedule', 'cancel_schedule']
  create_schedule    blocked=False
  list_schedules     blocked=True
  delete_schedule    blocked=False
  cancel_schedule    blocked=True
schedule_task in BLOCKED_TOOL_NAMES = True
schedule_task is a registered name  = False
```

**You should see after the fix:** all four `blocked=True`; the last two lines both `False`.

### 4.2 End-to-end through the real scoped-registry builder

```bash
uv run python -c "
import tempfile, pathlib
from hachi.jobs.scheduler import Scheduler, ScheduleStore
from hachi.core.loop import ToolRegistry
from hachi.tools.schedule_tools import register_schedule_tools
from hachi.tools.delegation_tools import _build_scoped_registry
store = ScheduleStore(pathlib.Path(tempfile.mkdtemp()) / 'schedules.json')
parent = ToolRegistry()
register_schedule_tools(parent, Scheduler(store))
scoped = _build_scoped_registry(parent)     # no tool_patterns = the backward-compat default
print('parent    tools:', sorted(parent._tools))
print('SUB-AGENT tools:', sorted(scoped._tools))
"
```

**You will see now:**

```
parent    tools: ['cancel_schedule', 'create_schedule', 'delete_schedule', 'list_schedules']
SUB-AGENT tools: ['create_schedule', 'delete_schedule']
```

Read those two lines together. The blocklist strips the read tool and the alias, and passes
through **exactly the two tools that mutate the store**. It is an inverted filter.

**You should see after the fix:** `SUB-AGENT tools: []`.

## 5. What "fixed" looks like

Two things, both required.

**(a) The list names real tools.** The scheduling section becomes:

```python
        # Skill authoring + scheduling are privileged main-agent actions.
        # NOTE: these are TOOL names (the `"name"` field of the registered schema),
        # not the Python constant or handler-function names. schedule_tools.py
        # defines SCHEDULE_TASK_SCHEMA whose tool name is "create_schedule".
        "save_skill",
        "create_schedule",     # was "schedule_task" — never a registered tool
        "list_schedules",
        "delete_schedule",     # the real mutator; was missing entirely
        "cancel_schedule",     # alias for delete_schedule
```

**(b) Drift fails loudly.** A new frozenset documents the deliberately-reserved names, and a new
test asserts every other blocklist entry resolves to a real tool schema:

```python
_RESERVED_BLOCKED_NAMES: frozenset[str] = frozenset(
    {
        # Blocked pre-emptively: the handlers exist in tools/memory_tools.py
        # (save_agent_profile / delete_agent_profile) but are not registered today.
        # Keeping them blocked means registering them later cannot silently widen
        # the sub-agent surface. Verified not-registered on 2026-07-19.
        "core_save_agent_profile",
        "core_delete_agent_profile",
    }
)
"""Names in BLOCKED_TOOL_NAMES that intentionally do not (yet) map to a registered tool.

Anything blocked but NOT registered and NOT listed here is drift — see
tests/test_delegation_blocklist_integrity.py.
"""
```

**Decisions already made for you — do not relitigate:**

- `schedule_task` is **deleted**, not moved to `_RESERVED_BLOCKED_NAMES`. It is not a reserved
  future name; it is a wrong guess at an existing tool. Keeping it preserves the illusion.
- The two agent-profile names are **kept** and moved under `_RESERVED_BLOCKED_NAMES`. Deleting
  them would mean that whoever registers those tools later gets them exposed to sub-agents by
  default. Defence in depth wins over tidiness.
- `cancel_schedule` **stays** — it is a real alias tool and blocking it is correct.
- The integrity check is a **test**, not a boot-time assert. A boot-time assert would false-fire:
  the live registry legitimately lacks tools in many configurations (Google unconfigured, sandbox
  not opted in, no search provider), so "blocked name not in registry" is not an error at runtime.

## 6. Steps

1. Write the failing tests first — §7. Run them. Watch them fail. Do not skip this.
2. In `src/hachi/tools/delegation_tools.py`, replace `"schedule_task"` with `"create_schedule"`
   and add `"delete_schedule"`. Add the comment from §5(a) explaining tool-name-vs-constant-name.
3. In the same file, add `_RESERVED_BLOCKED_NAMES` (§5(b)) directly below `BLOCKED_TOOL_NAMES`,
   with the docstring. Leave the two agent-profile names inside `BLOCKED_TOOL_NAMES` as well —
   the reserved set is a *declaration*, not a removal.
4. Update `tests/test_security_hardening.py::test_sub_agent_blocklist_covers_privileged_tools`:
   the tuple on line 54 becomes `("save_skill", "create_schedule", "list_schedules",
   "delete_schedule", "cancel_schedule")`. **This is a contract correction, not test-weakening**
   — the old assertion encoded the bug, exactly like the `test_gateway_config_mutations.py` case
   documented at the end of [CORRECTIONS.md](CORRECTIONS.md). Say so in your commit message.
5. Run the full suite. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_delegation_blocklist_integrity.py` (new)
- **Test names:** `test_schedule_mutators_are_blocked_from_sub_agents` and
  `test_every_blocked_name_is_a_real_tool_name`
- **They must assert:** (1) a registry built by the real `register_schedule_tools` and filtered by
  the real `_build_scoped_registry` yields **no** schedule tools; (2) every entry in
  `BLOCKED_TOOL_NAMES` that is not declared reserved appears as the `"name"` of a real tool schema
  in the source tree.
- **They must FAIL before your fix** with, respectively:
  `AssertionError: sub-agent can still reach: ['create_schedule', 'delete_schedule']` and
  `AssertionError: BLOCKED_TOOL_NAMES contains names that match no registered tool: ['schedule_task']`

```python
"""BB-N: the sub-agent blocklist named a tool that does not exist, so the two
tools that mutate the schedule store were never blocked."""

from __future__ import annotations

import ast
import pathlib
import tempfile

from hachi.core.loop import ToolRegistry
from hachi.jobs.scheduler import ScheduleStore, Scheduler
from hachi.tools.delegation_tools import (
    _RESERVED_BLOCKED_NAMES,
    BLOCKED_TOOL_NAMES,
    _build_scoped_registry,
)
from hachi.tools.schedule_tools import register_schedule_tools

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "hachi"


def _registered_tool_names() -> set[str]:
    """Every tool-schema `name` literal in the source tree.

    A tool schema is a dict literal with a string `"name"` and either a literal
    `"input_schema"` key or a `**` unpack (the `_CANCEL_ALIAS_SCHEMA` form).
    """
    names: set[str] = set()
    for path in _SRC.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - defensive
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            literal_keys = {
                k.value
                for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            has_unpack = any(k is None for k in node.keys)
            if "name" not in literal_keys or not ("input_schema" in literal_keys or has_unpack):
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "name"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    names.add(value.value)
    return names


def test_schedule_mutators_are_blocked_from_sub_agents(tmp_path) -> None:
    parent = ToolRegistry()
    register_schedule_tools(parent, Scheduler(ScheduleStore(tmp_path / "schedules.json")))
    assert "create_schedule" in parent._tools  # guard: the parent really mounts them

    # No tool_patterns == the backward-compatible default role (all non-blocked pass).
    scoped = _build_scoped_registry(parent)

    leaked = sorted(scoped._tools)
    assert leaked == [], f"sub-agent can still reach: {leaked}"


def test_every_blocked_name_is_a_real_tool_name() -> None:
    inventory = _registered_tool_names()
    # Sanity-check the scanner itself before trusting its verdict.
    assert "create_schedule" in inventory
    assert "cancel_schedule" in inventory  # the {**BASE, "name": ...} alias form

    stale = sorted(
        name
        for name in BLOCKED_TOOL_NAMES
        if name not in inventory and name not in _RESERVED_BLOCKED_NAMES
    )
    assert stale == [], (
        f"BLOCKED_TOOL_NAMES contains names that match no registered tool: {stale}. "
        "Either the tool was renamed (fix the entry) or it is deliberately reserved "
        "(add it to _RESERVED_BLOCKED_NAMES with a comment)."
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The scanner predicate above is not guesswork — it was run against `main` @ `bd24afe`, discovers
120 tool names, and reports exactly `['core_delete_agent_profile', 'core_save_agent_profile',
'schedule_task']`. Do not simplify the `has_unpack` clause away: without it, `cancel_schedule`
false-positives as stale because `_CANCEL_ALIAS_SCHEMA` inherits `input_schema` via `**`.

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and both failed before the fix.
- [ ] `BLOCKED_TOOL_NAMES` contains `create_schedule` and `delete_schedule`; it does **not**
      contain `schedule_task`.
- [ ] The §4.2 command prints `SUB-AGENT tools: []`.
- [ ] `_RESERVED_BLOCKED_NAMES` exists, contains only the two agent-profile names, and each has a
      comment saying why.
- [ ] `tests/test_security_hardening.py::test_sub_agent_blocklist_covers_privileged_tools` was
      **corrected** (not deleted, not skipped) and the commit message says why.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not rename `SCHEDULE_TASK_SCHEMA` / `CANCEL_SCHEDULE_SCHEMA` to match their tool names.**
  This is the single most likely drift for this task: the constants *are* confusingly named, and
  renaming them "to prevent recurrence" feels like the root-cause fix. It is not. It is a
  cross-cutting rename of public-ish module constants, it touches every import site, and it does
  not close the hole. Fix the blocklist; leave the constants alone.
- **Do not register `core_save_agent_profile` / `core_delete_agent_profile`.** You will notice
  that `tools/memory_tools.py:291` and `:303` define handlers that nobody mounts, and it will look
  like a two-line win. Registering a new agent-facing tool that writes to the agent-persona vault
  is a product decision with a permission surface, not a cleanup. Note it and move on.
- **Do not touch `_GROUP_BY_TOOL_NAME` in `gateway/orchestrator.py`.** It has the identical
  `schedule_task` dead entry at `:258`, and fixing it here is a one-line temptation. It belongs to
  [T-39-tool-groups-at-registration.md](T-39-tool-groups-at-registration.md), which deletes those
  tables wholesale. Two tasks editing the same table produces a conflict for no benefit.
- **Do not "fix" `src/hachi/packs/research-agent/research_agent.og:74`**, which instructs the
  model to *"Use schedule_task to queue the research"* — a third manifestation of the same drift,
  in a bundled pack. Real, worth a separate task, not this one.
- **Do not broaden the blocklist** with tools that merely look privileged. Every addition
  silently narrows what delegation can do, and there is no test that would tell you that you
  broke a role.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). Correcting `test_security_hardening.py` per §6
  step 4 is explicitly sanctioned; deleting it is not.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. The §7 scanner uses stdlib `ast`.

## 10. Verify

```bash
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
uv run pytest tests/test_delegation_blocklist_integrity.py tests/test_security_hardening.py \
              tests/test_delegation_failclosed.py tests/test_parallel_delegation.py -q

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-88` is the highest
today, so likely `BB-89`; confirm before appending):

```markdown
### BB-N — Sub-agent blocklist named a nonexistent tool; schedule mutators walked free

- **Symptom:** A sub-agent whose role `.og` declares no `::meta tools:` allowlist could call
  `create_schedule` and `delete_schedule`, creating or deleting the user's durable, recurring,
  autonomously-firing schedules. `BLOCKED_TOOL_NAMES` is documented as "the security boundary".
- **Root cause:** Constant-name vs tool-name mismatch. `schedule_tools.py` defines
  `SCHEDULE_TASK_SCHEMA` whose registered `"name"` is `create_schedule`, and
  `CANCEL_SCHEDULE_SCHEMA` whose name is `delete_schedule`. The blocklist was written from the
  constant names, so it blocked the string `"schedule_task"` (a no-op — no such tool) plus the two
  harmless read/alias tools, and missed both mutators. Nothing validated the strings against real
  tool names; `test_security_hardening.py` asserted `"schedule_task" in BLOCKED_TOOL_NAMES`,
  locking the bug in as the contract.
- **Fix:** Replaced `schedule_task` with `create_schedule`, added `delete_schedule`, declared the
  two genuinely-unregistered `core_*_agent_profile` entries in `_RESERVED_BLOCKED_NAMES`, and
  added an integrity test that AST-scans the source tree for tool-schema `name` literals and
  fails on any blocked name that matches none of them.
- **Avoid:** A tool name is the `"name"` field of the registered schema — never the Python
  constant, never the handler function's identifier. Any hand-maintained list of tool names needs
  a test that resolves every entry against a real schema, or it will rot silently and fail open.
- **Locked by:** `tests/test_delegation_blocklist_integrity.py` —
  `test_schedule_mutators_are_blocked_from_sub_agents`,
  `test_every_blocked_name_is_a_real_tool_name`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **The constant/handler/tool-name triangle.** `schedule_tools.py` has three different names for
  one tool: constant `SCHEDULE_TASK_SCHEMA`, handler function `schedule_task` (`:19`), tool name
  `create_schedule` (`:87`). Grepping for any one of them tells you nothing about the others. When
  in doubt, print `[s["name"] for s in registry.get_schemas()]`.
- **`_build_scoped_registry` re-registers with `group="core"`.** Do not assume the parent's lazy
  group protects a sub-agent. It does not — see §3.3.
- **`ScheduleStore` takes a `Path`, `Scheduler` takes a `ScheduleStore`.** Both positional. Use
  `tmp_path` in tests so you never touch the user's real `schedules.json`.
- **Sibling task, same drift class:** [T-39-tool-groups-at-registration.md](T-39-tool-groups-at-registration.md)
  fixes the identical `schedule_task` phantom in `_GROUP_BY_TOOL_NAME`. Read its §3 before you
  conclude you have found every instance — but do not edit its files.
</content>
</invoke>
