# T-36 · Make `ToolRegistry.register` raise on a duplicate tool name

|  |  |
|---|---|
| **Source finding** | CF-11 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | **[T-35-google-double-mount.md](T-35-google-double-mount.md) — do not start until it has landed** |
| **Blocks** | nothing |
| **Effort** | ~2 hours |
| **Difficulty** | Medium — the change is 4 lines; the risk is entirely in what it surfaces |
| **Files you will touch** | `src/hachi/core/loop.py`, `tests/test_tool_registry_duplicate_guard.py` (new), `docs/bug-bank.md` |

---

> ## ⚠️ ORDERING IS A HARD CONSTRAINT
>
> This change converts a silent misconfiguration into a **boot-time crash**. That is the point —
> the audit recommends it precisely because silent clobbering is undetectable today. But the
> repository currently *has* a live double-mount: Google Workspace tools are registered twice
> whenever Google is fully configured (see [T-35](T-35-google-double-mount.md)).
>
> **If you land this before T-35, every fully-configured Google user's boot raises `ValueError`
> and Hachi does not start.** Confirm T-35 is merged before you begin.

---

## 1. Brief

`ToolRegistry.register` overwrites `self._tools[name]` and appends to `self._schemas` with no
duplicate check, so two mounts of the same tool silently produce a registry whose schema came from
the first registration and whose handler came from the second. When you are done, `register`
raises on a duplicate name, and callers that legitimately need to re-mount use the `unregister`
API that already exists for that purpose.

## 2. Why this matters

The registry is the single seam between "what the model can see" and "what actually runs". Every
tool the LLM is offered, and every callable it can trigger, passes through these three lines. A
silent last-writer-wins on that seam means the security properties of a handler — whether it is
permission-gated, whether it has an approver, which credentials it closes over — can be replaced
by a later mount with no log line, no exception, and no way for any test to notice.

The evidence that this is a real hazard and not a theoretical one is that **the codebase has
already worked around it twice instead of fixing it** (§3.2, §3.3), and a third case shipped
anyway (T-35). A guard here makes the class of mistake impossible to ship rather than merely
documented.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The unguarded write

`src/hachi/core/loop.py:174-190` — the entire method. Note that the only validation is the empty
name check; nothing looks at whether `tool_name` is already present:

```python
    def register(self, schema: dict[str, Any], func: Callable[..., Any], group: str = "core"):
        """
        Register a new tool.

        Args:
            schema: The JSON Schema definition of the tool (Anthropic/OpenAI format).
            func: The actual Python callable that executes the tool.
            group: Lazy-loading group; "core" tools are always sent to the model,
                   others are sent only when their group is active for the turn.
        """
        tool_name = schema.get("name")
        if not tool_name:
            raise ValueError("Tool schema must contain a 'name' field.")

        self._tools[tool_name] = func
        self._schemas.append(schema)
        self._groups[tool_name] = group
```

`self._tools[tool_name] = func` — dict assignment, silently overwrites.
`self._schemas.append(schema)` — list append, silently duplicates.
`self._groups[tool_name] = group` — dict assignment, silently overwrites.

### 3.2 The codebase already documents this hazard — and worked around it

`src/hachi/core/loop.py:192-212` — `update_handler` exists **solely** because `register` has no
guard. Its docstring names the exact failure mode (`:195-199`):

```python
    def update_handler(self, tool_name: str, func: Callable[..., Any]) -> bool:
        """Replace the callable for an already-registered tool without touching its schema.

        Used by sub-agent builders to rebind a tool to a scoped resource (e.g. a
        role-filtered ``SkillEngine``) without duplicating the schema in
        ``_schemas``.  Calling :meth:`register` for an already-registered tool
        would append the schema a second time, causing the model to see duplicate
        tool definitions.
```

Live call sites: `src/hachi/tools/delegation_tools.py:345` (role rebinding) and
`src/hachi/gateway/orchestrator.py:437-438` (search tools).

### 3.3 A second, independent workaround

`src/hachi/gateway/orchestrator.py:395-399` — `_register_search_if_available`'s docstring, where
a caller hand-rolled idempotency for the same reason:

```python
    """Register ``web_search`` and ``extract_url`` for *provider* onto *tool_registry*.

    Idempotent: if ``web_search`` is already registered the handlers are updated
    in-place (via :meth:`~hachi.core.loop.ToolRegistry.update_handler`) so schemas
    are never duplicated.  This is safe to call on a live reload path.
    """
```

Two subsystems independently discovered the hazard, documented it, and routed around it. Nobody
fixed the constructor of the problem.

### 3.4 The teardown API you will point callers at already exists

`src/hachi/core/loop.py:214-238` — `unregister` removes handlers, schemas, and groups:

```python
    def unregister(self, tool_names: Iterable[str]) -> int:
        """Remove the named tools from the registry (handlers, schemas, groups).
```

Its only production users are the MCP lifecycle paths: `src/hachi/core/mcp_client.py:1788`,
`:1799`, `:1821`. That is the pattern any legitimate re-mount should follow.

### 3.5 What the missing guard actually produces

Verified by running against `main` @ `bd24afe`:

```
len(_schemas)      = 2                  <- duplicate appended, unbounded growth
len(get_schemas()) = 1                  <- deduped on READ (loop.py:330-337)
handler result     = SECOND (ungated)   <- LAST writer wins
```

Note the middle line, because it changes what you should assert: `get_schemas` de-dupes
first-wins, so **the model never sees a duplicate and the Anthropic API never errors**. The
observable damage is (a) `_schemas` grows without bound, and (b) schema and handler can come from
different registrations. Do not write a test that expects an API-level failure — see
[T-35 §2.1](T-35-google-double-mount.md).

### 3.6 Existing tests

- `tests/test_tool_registration.py` (9 tests) — `test_registrar_installs_in_dependency_order`,
  `test_delegation_always_last`, `test_config_after_mcp`, `test_cycle_raises`, … These are about
  **`ToolRegistrar` install ordering**, not `ToolRegistry.register`. Nothing here covers duplicates.
- `tests/test_tool_lazy_loading.py` (9 tests) — `test_get_schemas_filters_by_active_groups`,
  `test_classify_assigns_groups_and_preserves_explicit_stamps`,
  `test_no_tool_is_permanently_hidden`, … Group classification and lazy visibility. Nothing here
  covers duplicates either.

No test anywhere asserts what happens when the same name is registered twice.

## 4. Reproduce the failure

Reproducible from a shell. This command was run against `main` @ `bd24afe`; the output is real.

```bash
uv run python -c "
from hachi.core.loop import ToolRegistry
r = ToolRegistry()
schema = {'name': 'demo', 'input_schema': {'type':'object','properties':{}}}
r.register(schema, lambda: 'FIRST (gated)', group='core')
r.register(schema, lambda: 'SECOND (ungated)', group='integrations')
print('len(_schemas)      =', len(r._schemas))
print('len(get_schemas()) =', len(r.get_schemas()))
print('group             =', r._groups['demo'])
print('handler result    =', r._tools['demo']())
"
```

**You will see now:**

```
len(_schemas)      = 2
len(get_schemas()) = 1
group             = integrations
handler result    = SECOND (ungated)
```

Three writes silently clobbered, one silently duplicated, zero diagnostics.

**You should see after the fix:**

```
ValueError: Tool 'demo' is already registered. Registering it again would overwrite
the existing handler and append a duplicate schema. If this is an intentional
re-mount, call unregister(['demo']) first.
```

## 5. What "fixed" looks like

```python
    def register(self, schema: dict[str, Any], func: Callable[..., Any], group: str = "core"):
        """
        Register a new tool.

        Args:
            schema: The JSON Schema definition of the tool (Anthropic/OpenAI format).
            func: The actual Python callable that executes the tool.
            group: Lazy-loading group; "core" tools are always sent to the model,
                   others are sent only when their group is active for the turn.

        Raises:
            ValueError: If the schema has no ``name``, or if a tool with that name
                is already registered.  Silent overwrites hid a class of bug where a
                tool's schema came from one mount and its handler from another (see
                docs/bug-bank.md).  To deliberately re-mount a tool, call
                :meth:`unregister` first; to swap only the callable, use
                :meth:`update_handler`.
        """
        tool_name = schema.get("name")
        if not tool_name:
            raise ValueError("Tool schema must contain a 'name' field.")
        if tool_name in self._tools:
            raise ValueError(
                f"Tool {tool_name!r} is already registered. Registering it again would "
                f"overwrite the existing handler and append a duplicate schema. If this is "
                f"an intentional re-mount, call unregister([{tool_name!r}]) first."
            )

        self._tools[tool_name] = func
        self._schemas.append(schema)
        self._groups[tool_name] = group
```

**Decisions already made for you — do not relitigate:**

- **Raise, do not warn.** A log line would be ignored exactly as reliably as the current silence.
- **No `replace=True`/`force=` escape hatch.** `unregister()` already exists (§3.4), is public,
  is greppable, and is what the MCP lifecycle already uses. A boolean flag would become the
  default dodge within a month.
- **`ValueError`, not a custom exception.** It matches the empty-name check three lines above and
  needs no new import or taxonomy decision.
- **Do not change `update_handler` or `unregister`.** They are the sanctioned paths and they
  already behave correctly.

## 6. Steps

1. Confirm [T-35](T-35-google-double-mount.md) has landed. `git log --oneline` for it. If it has
   not, stop — you will break every configured Google user.
2. Write the failing test first — §7. Run it. Watch it fail.
3. Add the duplicate check to `ToolRegistry.register` (`src/hachi/core/loop.py`), immediately
   after the existing empty-name check, plus the `Raises:` docstring block from §5.
4. Run the **full** suite. Expect fallout: any test that registers the same name twice now raises.
   For each failure, decide honestly — is it a test that was papering over a real double-mount
   (fix the source), or a fixture that re-registers for convenience (make the fixture use a fresh
   `ToolRegistry`, or call `unregister` first)? **Do not add `pytest.raises` around a call that
   should not be duplicating in the first place.**
5. Audit the MCP re-enable path. `core/mcp_client.py:1710` `register_tools` mounts server tools
   and `:1761` calls `registry.register`. Confirm that enabling a server that was previously
   registered goes through `unregister_server_tools` (`:1792`) first. If it does not, that is a
   latent double-mount this change will expose — fix it by calling `unregister` before re-mount,
   and say so in your report.
6. Run the §10 boot check in as many configurations as you can reach.
7. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_tool_registry_duplicate_guard.py` (new)
- **Test names:** `test_duplicate_registration_raises`,
  `test_duplicate_registration_leaves_registry_unchanged`,
  `test_unregister_then_register_is_allowed`, `test_update_handler_still_works`
- **They must assert:** a second `register` of the same name raises `ValueError`; the registry is
  **not** mutated by the rejected call (handler, schema count, and group all unchanged); the
  sanctioned re-mount path (`unregister` then `register`) still works; and `update_handler` — the
  existing workaround with 3 production call sites — is unaffected.
- **`test_duplicate_registration_raises` must FAIL before your fix** with:
  `Failed: DID NOT RAISE <class 'ValueError'>`

```python
"""BB-N: ToolRegistry.register silently overwrote handlers and appended duplicate
schemas, so a tool's schema could come from one mount and its handler from another."""

from __future__ import annotations

import pytest

from hachi.core.loop import ToolRegistry

_SCHEMA = {"name": "demo", "input_schema": {"type": "object", "properties": {}}}


def test_duplicate_registration_raises() -> None:
    reg = ToolRegistry()
    reg.register(_SCHEMA, lambda: "first")
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_SCHEMA, lambda: "second")


def test_duplicate_registration_leaves_registry_unchanged() -> None:
    """A rejected registration must not half-apply."""
    reg = ToolRegistry()
    reg.register(_SCHEMA, lambda: "first", group="core")

    with pytest.raises(ValueError):
        reg.register(_SCHEMA, lambda: "second", group="integrations")

    assert reg._tools["demo"]() == "first"
    assert len(reg._schemas) == 1
    assert reg._groups["demo"] == "core"


def test_unregister_then_register_is_allowed() -> None:
    """The sanctioned re-mount path (used by the MCP lifecycle) still works."""
    reg = ToolRegistry()
    reg.register(_SCHEMA, lambda: "first")
    assert reg.unregister(["demo"]) == 1
    reg.register(_SCHEMA, lambda: "second")
    assert reg._tools["demo"]() == "second"
    assert len(reg._schemas) == 1


def test_update_handler_still_works() -> None:
    """update_handler is the sanctioned callable swap — 3 production call sites."""
    reg = ToolRegistry()
    reg.register(_SCHEMA, lambda: "first")
    assert reg.update_handler("demo", lambda: "second") is True
    assert reg._tools["demo"]() == "second"
    assert len(reg._schemas) == 1
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] T-35 landed **before** this change. Name the commit in your report.
- [ ] The regression tests from §7 exist, and `test_duplicate_registration_raises` failed before
      the fix with `DID NOT RAISE`.
- [ ] `register` raises `ValueError` on a duplicate name and leaves the registry untouched.
- [ ] `unregister` → `register` still works; `update_handler` still works.
- [ ] `tests/test_tool_registration.py` (9) and `tests/test_tool_lazy_loading.py` (9) pass
      unmodified.
- [ ] **A real boot completed** in at least the default configuration, and — per §10 — with Google
      configured if you have access to such a machine.
- [ ] Every test that had to change is listed in your report with a one-line justification.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not soften the raise into a `logger.warning` when the full suite goes red.** This is the
  drift for this task, and it will feel justified at 4pm with six failures on screen. A warning
  restores exactly the silence the change exists to remove. If the fallout is genuinely too large
  to absorb, stop and report it — do not ship a half-guard.
- **Do not add a `replace=`/`force=` parameter** for the same reason. §5 already decided this.
- **Do not fix the double-mount you are about to surface.** If the guard fires on Google, T-35 has
  not landed — go land it. If it fires somewhere new, report it as its own finding rather than
  absorbing an unrelated fix into this diff ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- **Do not introduce the `ToolDef` pydantic model or jsonschema validation** that CF-11 also
  recommends. Same finding, different task, much larger blast radius. This task is the duplicate
  guard only.
- **Do not touch `get_schemas`'s de-dupe** (`loop.py:330-337`). It looks redundant once `register`
  guards, and removing it is a two-line "cleanup" that would break sub-agent registries built by
  `_build_scoped_registry` and any future path that composes registries. Leave it.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
uv run pytest tests/test_tool_registry_duplicate_guard.py tests/test_tool_registration.py \
              tests/test_tool_lazy_loading.py -q

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Then boot for real.** The suite cannot exercise every registration combination, and this change
turns a latent one into a crash:

```bash
uv run python -c "
from hachi.gateway.orchestrator import boot_agent
s = boot_agent()
print('boot OK — tools:', len(s.loop.tool_registry._tools))
"
```

Do this at minimum in the default configuration. **If you have access to a machine with Google
fully configured and connected, boot there too** — that is the configuration T-35 fixed and the
one this change would crash if T-35 had not landed. If you do not have such a machine, say so in
your report rather than implying you checked.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-88` is the highest
today; confirm before appending):

```markdown
### BB-N — ToolRegistry.register silently clobbered duplicate tool names

- **Symptom:** Registering a tool name twice silently replaced the handler (last-wins) while the
  model kept seeing the first registration's schema (`get_schemas` de-dupes first-wins), so a
  tool's schema and its handler could come from two different mounts. `_schemas` also grew by one
  dead dict per duplicate, per boot. No exception, no log line, no test could detect it. The
  Google double-mount (see the T-35 entry) shipped through this gap.
- **Root cause:** `core/loop.py` `register()` did `self._tools[name] = func` /
  `self._schemas.append(schema)` with no membership check — the only validation was that the
  schema had a non-empty `name`. Two subsystems independently worked around it instead of fixing
  it: `ToolRegistry.update_handler` exists solely for this (its docstring says so), and
  `_register_search_if_available` hand-rolled idempotency for the same reason.
- **Fix:** `register()` now raises `ValueError` when the name is already present, and the message
  points at `unregister()` — the pre-existing public teardown API the MCP lifecycle already uses.
- **Avoid:** A registry keyed by name must reject duplicates at write time. Anything that needs to
  re-mount calls `unregister()` first; anything that needs to swap only the callable calls
  `update_handler()`. Never re-`register()` to overwrite.
- **Locked by:** `tests/test_tool_registry_duplicate_guard.py` — `test_duplicate_registration_raises`,
  `test_duplicate_registration_leaves_registry_unchanged`, `test_unregister_then_register_is_allowed`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **T-35 first. Not negotiable.** Restated here because it is the one way this task causes an
  outage.
- **A red full suite after this change is information, not an obstacle.** Every new failure is
  either a real latent double-mount (a win) or a fixture that reuses a registry (a one-line fix).
  Triage each one; report the list.
- **Run the FULL suite, not a scoped one** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). This change
  can only fail in cross-module registration paths, which is exactly what scoped runs miss.
- **`_build_scoped_registry` (`tools/delegation_tools.py:251-299`) builds a fresh `ToolRegistry`
  per sub-agent** and copies handlers in via `scoped.register(schema, handler)` at `:291`. Since
  it iterates `parent_registry.get_schemas()` — already de-duped — it cannot trip the new guard.
  Verify this rather than assuming it, because it is the highest-volume `register` caller.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb` when writing boot-path tests.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots.
</content>
</invoke>
