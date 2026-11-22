# T-39 · Declare tool groups at registration; delete the hand-maintained group table

|  |  |
|---|---|
| **Source finding** | CF-11 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **one audit nuance corrected — see §3.5** |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none — but read [T-34](T-34-subagent-schedule-tool-blocklist.md) first (same drift class, security consequence) |
| **Blocks** | nothing |
| **Effort** | ~1 day |
| **Difficulty** | Medium (mechanical, but wide — 10+ registration modules and 4 test files) |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, ~8 `src/hachi/tools/*.py` registration functions, `tests/test_tool_groups_at_registration.py` (new), `tests/test_tool_lazy_loading.py`, `tests/test_notification_tools.py`, `tests/test_search_tool_visibility.py`, `tests/test_google_tools_wire.py`, `docs/bug-bank.md` |

---

## 1. Brief

Which lazy-loading group a tool belongs to is decided in three hand-maintained tables inside
`gateway/orchestrator.py`, hundreds of lines away from where the tools are registered. Both
name-keyed tables have already drifted: one entry names a tool that does not exist, and one
registered tool is missing entirely and silently falls into the wrong group. When you are done,
each tool declares its own group at its `register(...)` call, the name table is gone, and a test
fails if any surviving table entry stops matching a real tool.

## 2. Why this matters

There are ~120 tool schemas in the tree and the number grows every month. Today, adding a tool
means editing the module that defines it **and** a table in gateway code that the tool's author
has no reason to be looking at. Forgetting the second edit is not an error — it is silently
absorbed by `default="integrations"`, and the tool ends up in a group the model was never told to
unlock for that purpose. That is not a hypothetical: it has already happened to
`delegate_parallel_tasks`, so `use_tools("delegation")` currently hands the model two of the three
delegation tools and there is no way for anyone to notice.

The deeper reason is the one [T-34](T-34-subagent-schedule-tool-blocklist.md) makes urgent: a
hand-maintained list of tool-name strings, with nothing checking it against reality, **rots
silently**. In the grouping table the cost is a wrong group. In the sub-agent blocklist the same
rot is a security hole. Same mechanism, same file family, same week. Fix the pattern here so the
next table does not get written.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.
>
> **The file is `src/hachi/gateway/orchestrator.py` (3,694 lines). There is no
> `src/hachi/core/orchestrator.py`.**

### 3.1 The three tables and the single call that consumes them

`src/hachi/gateway/orchestrator.py:3357-3363` — everything below feeds this one call:

```python
    tool_registry.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name=_GROUP_BY_TOOL_NAME,
        # Google integration tools all share the "google_" prefix → lazy "google" group.
        prefix_groups={"google_": "google"},
        default="integrations",
    )
```

**Table 1 — `_CORE_TOOL_NAMES: frozenset[str]`**, `src/hachi/gateway/orchestrator.py:206-242`.
**21 names** (verified by `len(_CORE_TOOL_NAMES)`, not by counting lines). This is a deliberate,
centrally-owned per-turn token-budget decision — `tests/test_tool_lazy_loading.py:156-161`
(`test_core_tool_set_size_guard`) asserts `18 <= len(_CORE_TOOL_NAMES) <= 24` so it cannot creep.
**§5 keeps this table.**

**Table 2 — `_GROUP_BY_TOOL_NAME: dict[str, str]`**, `src/hachi/gateway/orchestrator.py:246-278`.
**71 entries: 27 written by hand, plus 44 spliced in from Google** at `:277`:

```python
    "core_suspend_workflow": "workflow",
    "send_slack_message": "messaging",
    ...
    "get_audio_info": "voice",
    **{name: "google" for name in GOOGLE_TOOL_NAMES},
}
```

**§5 deletes this table.**

**Table 3 — `prefix_groups={"google_": "google"}`**, an inline dict literal at
`src/hachi/gateway/orchestrator.py:3361`. **§5 keeps this one** — see the scope note there.

### 3.2 Drift 1 — a table entry for a tool that does not exist

`src/hachi/gateway/orchestrator.py:257-261`:

```python
    "create_schedule": "schedule",
    "schedule_task": "schedule",
    "list_schedules": "schedule",
    "delete_schedule": "schedule",
    "cancel_schedule": "schedule",
```

`schedule_task` is not a registered tool. It is the *Python handler function's* identifier
(`src/hachi/tools/schedule_tools.py:19`, inside `_make_schedule_task`); the registered name is
`create_schedule` (`schedule_tools.py:86-87`), which is on the line above. Harmless here — the
line above already covers it — but it is the identical trap that produced a **security hole** in
[T-34](T-34-subagent-schedule-tool-blocklist.md), where the same wrong name was used in the
sub-agent blocklist and the two real mutators went unblocked.

### 3.3 Drift 2 — a registered tool missing from the table

`src/hachi/tools/delegation_tools.py:795-796` defines it and `:1014-1015` registers it:

```python
DELEGATE_PARALLEL_TASKS_SCHEMA: dict[str, Any] = {
    "name": "delegate_parallel_tasks",
```

```python
    registry.register(
        DELEGATE_PARALLEL_TASKS_SCHEMA,
```

But `_GROUP_BY_TOOL_NAME` has only its two siblings — `src/hachi/gateway/orchestrator.py:250-251`:

```python
    "delegate_task": "delegation",
    "list_roles": "delegation",
```

`register(...)` is called with no `group=`, so it defaults to `"core"` (`core/loop.py:174`);
`classify` then finds it in neither `core_names` nor `group_by_name`, no prefix matches, and
rule 5 drops it into `default="integrations"`.

**Consequence: `use_tools("delegation")` unlocks two of the three delegation tools.** The model is
told the group exists, asks for it, and gets an incomplete set with no error.

### 3.4 The good news — the drift is bounded, and this is the whole of it

An exhaustive cross-check of all **27** explicit `_GROUP_BY_TOOL_NAME` entries against every
tool-schema `name` literal in `src/hachi/` (120 names, AST scan) found **exactly one dead entry:
`schedule_task`.** The other 26 all resolve. There is no long tail, no archaeology, and no
open-ended discovery phase — this task is finite. Verified against `main` @ `bd24afe`:

```
group table total:  71   (27 explicit + 44 google)
dead entries:       ['schedule_task']
missing from table: delegate_parallel_tasks
```

### 3.5 ⚠️ Audit correction — the `"integrations"` group is NOT unreachable

`src/hachi/gateway/orchestrator.py:3365-3367` claims otherwise, and
`core/loop.py:288-289` repeats it:

```python
    # BB-32: MCP tools land in "integrations" (never activated) because classify()
    # doesn't know MCP server names at call time.  Reclassify them into "mcp" so
    # activating that group exposes them to the LLM.
```

**"never activated" is false.** `src/hachi/gateway/orchestrator.py:3377`:

```python
    domain_groups = sorted(tool_registry.available_groups() - {"core"} - skill_group_names)
```

`available_groups()` is `set(self._groups.values())` (`core/loop.py:309-311`), which contains
`"integrations"` the moment any tool lands there. `domain_groups` is passed to the prompt composer
at `:3386` (`tool_groups=list(domain_groups)`), so the model is *told about* the group; and
`use_tools` accepts any member of the same set — `src/hachi/tools/og_tools.py:465-469`:

```python
    def use_tools(group: str) -> str:
        groups = registry.available_groups() - {"core"}
        if group in groups:
            return f"Activated tool group '{group}'. Its tools are now available to call."
        return f"Unknown group '{group}'. Available groups: {sorted(groups)}"
```

Verified by running it (§4). **This matters for how you write the fix and the bug-bank entry:** the
defect is *wrong group*, not *unreachable tool*. `delegate_parallel_tasks` is reachable — via
`use_tools("integrations")`, a group whose name gives the model no reason to look there for
delegation. Do not describe it as hidden or dead.

### 3.6 Related — the registry-privates poke

`src/hachi/tools/google_tools.py:123-127`, because there is no public re-tagging API:

```python
    # Re-tag every registered google_* tool with the lazy group so the
    # orchestrator's use_tools("google") activates them correctly.
    for name in GOOGLE_TOOL_NAMES:
        if name in registry._tools:
            registry._groups[name] = "google"
```

Grouping-at-registration is what removes the need for this. **§5 explicitly defers it** — read the
scope note before you delete anything here.

### 3.7 `classify` already supports the fix

`src/hachi/core/loop.py:249-254` and `:267-268` — rule 4 is the hinge:

```python
        Resolution order (first match wins):
        1. ``core_names`` → ``"core"``
        2. ``group_by_name`` exact match → mapped group
        3. ``prefix_groups`` prefix match → mapped group (longest prefix wins)
        4. Tools already tagged with an explicit non-core group are left intact
        5. Everything else (or tools still at the ``register`` default of "core") → ``default``
```

```python
            elif self._groups.get(name, "core") == "core":
                # Only reclassify tools that haven't been given an explicit group.
```

A tool registered with `group="voice"` is left alone by `classify`. Per-skill REST tools already
rely on this (`orchestrator.py:3354-3356`), and `use_tools` itself is already registered with an
explicit `group="core"` at `:3177-3179`. **You are extending an existing pattern, not inventing one.**

### 3.8 Who else reads these tables

Four test files import them — you will be updating these:

| File | Line | Imports |
|---|---|---|
| `tests/test_tool_lazy_loading.py` | `:157`, `:167` | `_CORE_TOOL_NAMES`, `_GROUP_BY_TOOL_NAME` |
| `tests/test_notification_tools.py` | `:27`, `:456-457` | both, passed to a real `classify()` |
| `tests/test_search_tool_visibility.py` | `:23-24`, `:42-43` | both, passed to a real `classify()` |
| `tests/test_google_tools_wire.py` | `:188`, `:192-193` | `_GROUP_BY_TOOL_NAME` only |

## 4. Reproduce the failure

Reproducible from a shell. This was run against `main` @ `bd24afe`; the output is real.

```bash
uv run python - <<'PY'
from hachi.core.loop import ToolRegistry
from hachi.gateway.orchestrator import _CORE_TOOL_NAMES, _GROUP_BY_TOOL_NAME
from hachi.tools.delegation_tools import (
    DELEGATE_TASK_SCHEMA, DELEGATE_PARALLEL_TASKS_SCHEMA, LIST_ROLES_SCHEMA)
from hachi.tools.og_tools import USE_TOOLS_SCHEMA, _make_use_tools

r = ToolRegistry()
for s in (DELEGATE_TASK_SCHEMA, DELEGATE_PARALLEL_TASKS_SCHEMA, LIST_ROLES_SCHEMA):
    r.register(s, lambda: "")
r.register(USE_TOOLS_SCHEMA, _make_use_tools(r), group="core")
r.classify(core_names=set(_CORE_TOOL_NAMES), group_by_name=_GROUP_BY_TOOL_NAME,
           prefix_groups={"google_": "google"}, default="integrations")
for n in ("delegate_task", "list_roles", "delegate_parallel_tasks"):
    print(f"  {n:24} -> {r._groups[n]}")
print("available_groups() =", sorted(r.available_groups()))
print("use_tools('integrations') ->", _make_use_tools(r)("integrations"))
PY
```

**You will see now:**

```
  delegate_task            -> delegation
  list_roles               -> delegation
  delegate_parallel_tasks  -> integrations
available_groups() = ['core', 'delegation', 'integrations']
use_tools('integrations') -> Activated tool group 'integrations'. Its tools are now available to call.
```

Line 3 is the bug. Line 5 is the audit correction (§3.5) — the group is activatable, just wrong.

**You should see after the fix:** all three delegation tools report `-> delegation`.

For the dead table entry, no runtime symptom exists — it is provable only by reading, or by the
inventory scan in §7:

```bash
uv run python -c "
from hachi.gateway.orchestrator import _GROUP_BY_TOOL_NAME
print('schedule_task in table:', 'schedule_task' in _GROUP_BY_TOOL_NAME)
print('delegate_parallel_tasks in table:', 'delegate_parallel_tasks' in _GROUP_BY_TOOL_NAME)
"
```

**You will see now:** `True` then `False`. Both should be `False` and `True` respectively —
or, after the fix, the table is gone and the question no longer exists.

## 5. What "fixed" looks like

Every non-core tool declares its group where it is registered:

```python
# src/hachi/tools/schedule_tools.py
def register_schedule_tools(registry: ToolRegistry, scheduler: Scheduler) -> None:
    """Mount the scheduling tools onto the provided ToolRegistry."""
    registry.register(SCHEDULE_TASK_SCHEMA, _make_schedule_task(scheduler), group="schedule")
    registry.register(LIST_SCHEDULES_SCHEMA, _make_list_schedules(scheduler), group="schedule")
    registry.register(CANCEL_SCHEDULE_SCHEMA, _make_cancel_schedule(scheduler), group="schedule")
    registry.register(_CANCEL_ALIAS_SCHEMA, _make_cancel_schedule(scheduler), group="schedule")
```

`_GROUP_BY_TOOL_NAME` is deleted, and the `classify` call becomes:

```python
    tool_registry.classify(
        core_names=set(_CORE_TOOL_NAMES),
        group_by_name={},
        # Google integration tools all share the "google_" prefix → lazy "google" group.
        prefix_groups={"google_": "google"},
        default="integrations",
    )
```

**Decisions already made for you — do not relitigate:**

- **`_CORE_TOOL_NAMES` stays.** It is not a per-tool fact; it is a central per-turn token-budget
  decision spanning eight modules, guarded by a size test. Scattering it into the modules destroys
  the ability to see and cap the budget in one place. Groups move; core-ness does not.
- **The `"google_"` prefix rule stays** (table 3). It is a *convention* rule, not a name list, so
  it cannot drift the way a name table can — and the convention is already enforced by
  `tests/test_google_tools_wire.py:175` (`test_google_tool_names_all_prefixed_google`). Threading
  `group="google"` through nine `GoogleService.register_tools` implementations
  (`integrations/google/__init__.py:82-87`) is a separate, larger change.
- **Consequently `google_tools.py:123-127`'s privates poke stays too.** Its removal is unlocked by
  the change above, not by this task. Leave a comment there pointing at this task; do not delete.
- **`classify` keeps its signature.** `group_by_name={}` at the one production call site is
  clearer than a signature change that ripples into the three test files that call it directly,
  and it leaves the mechanism available for a future dynamic table.
- **The integrity check is a test, not a boot assert.** A boot assert would false-fire: the live
  registry legitimately lacks tools in many configurations (no search provider, sandbox not opted
  in, Google unconfigured). Same reasoning as [T-34 §5](T-34-subagent-schedule-tool-blocklist.md).

### The groups to assign, derived from the current table

`delegation` · `authoring` · `browser` · `sandbox` · `schedule` · `workflow` · `messaging` ·
`notifications` · `vision` · `voice`. Take each group's members from
`_GROUP_BY_TOOL_NAME:250-276` verbatim — with the two corrections: drop `schedule_task`, and add
`delegate_parallel_tasks` to `delegation`.

## 6. Steps

1. Write the failing tests first — §7. Run them. Watch them fail.
2. Working group by group (not module by module — it keeps the diff reviewable), add `group="…"`
   to each `registry.register(...)` call for the 26 live names in `_GROUP_BY_TOOL_NAME`. The
   registration functions are in `src/hachi/tools/`: `delegation_tools.py`, `og_tools.py`,
   `browser_tools.py`, `sandbox_tools.py`, `schedule_tools.py`, `workflow_tools.py`,
   `messaging_tools.py`, `notification_tools.py`, `vision_tools.py`, `voice_tools.py`.
3. Add `group="delegation"` to the `delegate_parallel_tasks` registration
   (`delegation_tools.py:1014-1015`) — this is Drift 2, the actual behaviour change.
4. Do **not** add anything for `schedule_task` — it does not exist. Drift 1 dies with the table.
5. Delete `_GROUP_BY_TOOL_NAME` (`orchestrator.py:244-278`) and set `group_by_name={}` at the
   `classify` call (`:3357-3363`). Keep the `# Non-core, statically-known tools…` comment's intent
   by leaving a one-line note that groups are now declared at registration.
6. Update the four test files in §3.8. `test_google_tools_wire.py:186-193`
   (`test_orchestrator_group_dict_includes_google_tools`) asserts the Google splat that no longer
   exists — rewrite it to assert the surviving prefix rule instead, i.e. that after `classify`
   every `GOOGLE_TOOL_NAMES` entry is in group `"google"`. That is a **contract correction**, not
   test-weakening; say so in the commit message.
7. Run the full suite, then the §10 boot check. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_tool_groups_at_registration.py` (new)
- **Test names:** `test_all_delegation_tools_share_the_delegation_group` and
  `test_core_tool_names_all_reference_real_tools`
- **They must assert:** (1) after the real `register_delegation_tools` + the real `classify` call
  wiring, all three delegation tools report group `"delegation"`; (2) every surviving hand-written
  table entry resolves to a real tool-schema name in the source tree.
- **Test 1 must FAIL before your fix** with:
  `AssertionError: delegate_parallel_tasks is in group 'integrations', expected 'delegation'`

```python
"""BB-N: tool groups lived in a hand-maintained orchestrator table that drifted —
delegate_parallel_tasks fell into 'integrations', so use_tools('delegation')
unlocked two of three delegation tools."""

from __future__ import annotations

from hachi.core.loop import ToolRegistry
from hachi.gateway.orchestrator import _CORE_TOOL_NAMES
from hachi.tools.delegation_tools import (
    DELEGATE_PARALLEL_TASKS_SCHEMA,
    DELEGATE_TASK_SCHEMA,
    LIST_ROLES_SCHEMA,
)

# Mirrors the production call at gateway/orchestrator.py:3357-3363.
_CLASSIFY_KWARGS = dict(
    core_names=set(_CORE_TOOL_NAMES),
    group_by_name={},
    prefix_groups={"google_": "google"},
    default="integrations",
)


def test_all_delegation_tools_share_the_delegation_group() -> None:
    reg = ToolRegistry()
    # NOTE: register with group= exactly as production does after the fix. Before the
    # fix these calls carry no group and classify() drops the parallel one into
    # "integrations" via default=.
    reg.register(DELEGATE_TASK_SCHEMA, lambda: "", group="delegation")
    reg.register(LIST_ROLES_SCHEMA, lambda: "", group="delegation")
    reg.register(DELEGATE_PARALLEL_TASKS_SCHEMA, lambda: "")  # <- production omits group= today

    reg.classify(**_CLASSIFY_KWARGS)

    for name in ("delegate_task", "list_roles", "delegate_parallel_tasks"):
        actual = reg._groups[name]
        assert actual == "delegation", f"{name} is in group {actual!r}, expected 'delegation'"


def test_core_tool_names_all_reference_real_tools() -> None:
    """Every surviving hand-written name table must resolve to a registered tool."""
    # Reuse the single AST inventory scanner rather than writing a second one.
    from tests.test_delegation_blocklist_integrity import _registered_tool_names

    inventory = _registered_tool_names()
    assert "create_schedule" in inventory  # sanity-check the scanner before trusting it

    stale = sorted(n for n in _CORE_TOOL_NAMES if n not in inventory)
    assert stale == [], (
        f"_CORE_TOOL_NAMES references names that match no registered tool: {stale}"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

Two notes on the sketch. First, the third `register` in test 1 deliberately omits `group=` — that
is the production state today, and it is what makes the test red before you edit
`delegation_tools.py:1014-1015`. Once you add `group="delegation"` there, update the test to match
production (all three with `group=`); it stays green and now guards the invariant.

Second, `_registered_tool_names` is the AST scanner introduced by
[T-34 §7](T-34-subagent-schedule-tool-blocklist.md). If T-34 has landed, import it as shown — one
scanner, one place to fix. If it has not, copy the function in and leave a `TODO` to de-duplicate,
rather than writing a second, subtly different scanner.

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and test 1 failed before the fix with
      `delegate_parallel_tasks is in group 'integrations'`.
- [ ] `_GROUP_BY_TOOL_NAME` no longer exists in `src/hachi/gateway/orchestrator.py`.
- [ ] Every one of the 26 live names it used to carry is now declared via `group=` at its
      `register(...)` call, in the same group as before.
- [ ] `delegate_parallel_tasks` is in group `"delegation"`.
- [ ] `_CORE_TOOL_NAMES` is unchanged, and
      `tests/test_tool_lazy_loading.py::test_core_tool_set_size_guard` still passes untouched.
- [ ] The four test files in §3.8 were updated; each change is listed in your report with a
      one-line justification.
- [ ] A real boot completed and `use_tools` reports the same domain groups as before, minus
      nothing — record the before/after list (§10).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not move `_CORE_TOOL_NAMES` into the modules.** This is the drift for this task: once you
  are deleting one table it feels obviously right to delete the other, and the two look identical.
  They are not — §5 explains why, and there is a size-guard test whose whole purpose is to keep
  that decision visible in one place. If you scatter it, nobody can ever answer "what is in the
  per-turn budget?" again.
- **Do not thread `group="google"` through the nine `GoogleService.register_tools`
  implementations.** It is the natural next step and it is a day of its own. The prefix rule
  covers Google correctly today.
- **Do not delete the privates poke at `google_tools.py:123-127`** while the Google services still
  do not pass `group=`. `tests/test_google_tools_wire.py:139` (`test_tools_tagged_google_group`)
  depends on `register_google_tools` being self-contained.
- **Do not touch `BLOCKED_TOOL_NAMES` in `tools/delegation_tools.py`.** It has the identical
  `schedule_task` phantom, and there it is a P0 security hole — but it belongs to
  [T-34](T-34-subagent-schedule-tool-blocklist.md), which is one hour of work and should already
  have landed. Two tasks editing that constant produces a conflict for no benefit.
- **Do not "fix" the BB-32 comment's MCP reclassification** (`orchestrator.py:3365-3371`). Its
  *"never activated"* parenthetical is wrong (§3.5), and correcting that one word is fine; the
  `reclassify_by_prefix` mechanism it describes is correct and load-bearing. Do not remove it.
- **Do not build the `ToolDef` pydantic model or add jsonschema validation.** Same CF-11 finding,
  separate task, much larger blast radius.
- **Do not fix `src/hachi/packs/research-agent/research_agent.og:74`**, which tells the model to
  *"Use schedule_task"* — a third instance of this drift, in a bundled pack. Real, not yours.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). The §6 step 6 rewrite is a sanctioned contract
  correction; deletion is not.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3) — this task
  touches ~10 files and the temptation is real. The auto-format hook handles what you touch.
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
uv run pytest tests/test_tool_groups_at_registration.py tests/test_tool_lazy_loading.py \
              tests/test_notification_tools.py tests/test_search_tool_visibility.py \
              tests/test_google_tools_wire.py -q

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Capture the group map before and after** — this is the only check that proves you did not
silently move a tool while retyping 26 entries:

```bash
uv run python -c "
from hachi.gateway.orchestrator import boot_agent
import collections, json
s = boot_agent()
g = s.loop.tool_registry._groups
print(json.dumps({k: v for k, v in sorted(g.items())}, indent=0))
print('--- counts ---')
print(collections.Counter(g.values()))
" > /tmp/groups_after.txt
```

Run it on `main` first (`groups_before.txt`), then on your branch, then `diff` them. The **only**
expected difference is `delegate_parallel_tasks: integrations → delegation`. Any other line in
that diff is a regression you introduced. Report the diff.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-88` is the highest
today; confirm before appending):

```markdown
### BB-N — Tool groups lived in a hand-maintained orchestrator table, and it drifted

- **Symptom:** `use_tools("delegation")` unlocked `delegate_task` and `list_roles` but not
  `delegate_parallel_tasks`, which had silently landed in the `"integrations"` group instead. The
  same table also mapped `schedule_task`, a name no registered tool has ever used.
- **Root cause:** Group membership was declared in `_GROUP_BY_TOOL_NAME` in
  `gateway/orchestrator.py`, hundreds of lines from every `register(...)` call, and consumed by a
  single `classify()` call with `default="integrations"`. A tool omitted from the table is not an
  error — it is silently absorbed by the default. Nothing validated the table's 27 hand-written
  names against real tool schemas. NOTE: `"integrations"` is a normal, activatable group
  (`available_groups()` includes it and `use_tools` accepts it) — the defect was *wrong group*,
  not *unreachable tool*; a nearby BB-32 comment saying "never activated" is inaccurate.
- **Fix:** Each tool now declares `group=` at its `register(...)` call (`classify` rule 4 already
  leaves explicitly-tagged tools intact), `_GROUP_BY_TOOL_NAME` was deleted, and a test asserts
  every surviving hand-written name table resolves to a real tool-schema name.
  `_CORE_TOOL_NAMES` was deliberately kept — it is a central per-turn token-budget decision, not a
  per-tool fact, and has its own size-guard test.
- **Avoid:** Metadata about a tool belongs at the tool's registration, not in a central table
  keyed by tool-name strings. If a table keyed by tool names is unavoidable, it needs a test that
  resolves every entry against a real schema — see the T-34 entry for what this same rot costs
  when the table is a security boundary.
- **Locked by:** `tests/test_tool_groups_at_registration.py` —
  `test_all_delegation_tools_share_the_delegation_group`,
  `test_core_tool_names_all_reference_real_tools`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **The constant/handler/tool-name triangle.** `schedule_tools.py` has three names for one tool:
  constant `SCHEDULE_TASK_SCHEMA`, handler function `schedule_task` (`:19`), tool name
  `create_schedule` (`:87`). When assigning groups, read the schema's `"name"` field — never the
  constant, never the function.
- **`classify` runs AFTER all registration** (`orchestrator.py:3357`, after `install` at `:3320`
  and the capability loop at `:3325-3352`). If you add `group=` but a tool still ends up
  reclassified, check rule order in `core/loop.py:262-279` — `core_names` and `group_by_name` both
  beat an explicit registration group.
- **`reclassify_by_prefix` runs after `classify`** (`orchestrator.py:3368-3371`) for MCP tools. It
  overwrites unconditionally (`core/loop.py:300-307`), so an MCP-prefixed tool's registration group
  will not survive. That is intended; do not "fix" it.
- **Sibling task, same drift class:** [T-34](T-34-subagent-schedule-tool-blocklist.md) — same
  phantom `schedule_task`, but in the sub-agent security boundary, where it fails open. If T-34
  has not landed yet, say so in your report; do not fix it here.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant to the §10 boot
  capture.
</content>
</invoke>
