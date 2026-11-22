# T-40 · Define `emit_runtime_event` once so the governance path is not pinned to the pre-bus emitter

|  |  |
|---|---|
| **Source finding** | **NEW — not in the audit.** Adjacent to CF-1 (dead wiring) and CF-11 |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | **`T-44-boot-agent-staged-builders.md` — this must land before any `boot_agent` decomposition** |
| **Effort** | ~half a day |
| **Difficulty** | Medium — the diff is small; getting the honesty of the claim right is the work |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, `tests/test_emit_runtime_event_single_definition.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

`boot_agent` defines `emit_runtime_event` **twice** — once unconditionally, then again ~145 lines
later when the EventBus funnel is enabled (which it is, by default). Rebinding a local name does
not update references already handed out by value, and **six call sites take the emitter by value
before the rebind — all six in the permission/approval subsystem**. When you are done there will be
one definition that decides at call time whether to publish through the bus, and every holder of
that reference will follow the same path.

## 2. Why this matters

The block that introduces the second definition states its own invariant twice — that the funnel
produces *"byte-identical output, zero behavior change"* — and that invariant is what makes
`bus_funnel` safe to leave on by default. The closure-capture split means the invariant is
**silently false for one subsystem, and it is the governance subsystem.** Permission requests and
decisions are the one event class that structurally cannot reach the bus.

Be careful about what that does and does not mean today (§2.1). The point of fixing it is not that
users are currently losing audit data — as far as can be verified, they are not. The point is that
`boot_agent` currently has two divergent event paths, the divergence is invisible, untested, and
lands on the events that matter most for a product whose pitch is a verifiable audit trail. Any
new `"*"` subscriber added tomorrow — a governance sink, a metrics counter, a webhook relay —
inherits the hole without anyone choosing it.

### 2.1 Be honest about certainty — this is a mechanism, not a diagnosis

Everything below was verified against source at `main` @ `bd24afe`. State it the same way:

**Verified:** two definitions; six by-value captures before the rebind; all six in the
permission/approval subsystem; `bus_funnel` defaults to `True`; `ObservabilitySink` is subscribed
only on the bus path.

**Verified NOT broken:** v1 does `read_models.append_event` + `on_event`; v2 publishes to a bus
whose first two subscribers do exactly those two things in the same order. **v1 is a strict subset
of v2**, so the read-models store and the SSE/TUI surface receive governance events either way. The
Leash screen is not starved by this defect.

**NOT verified — do not claim it:** that any specific reported governance-audit gap is caused by
this. Two independent facts bound the present-day impact to approximately zero, and you must put
both in the bug-bank entry:

1. **`ObservabilitySink` would filter these events out anyway today.** `core/obs/sink.py:37-49`
   defines `_SPAN_EVENTS` as nine names — `tool.call.started`, `tool.call.completed`,
   `llm.generate`, `session.chat.started`, `session.chat.completed`, `subagent.started`,
   `subagent.completed`, `provider.failover`, `model.routed`. No `permission.*` name is in it, and
   `_handle_safe` (`:97-104`) also returns early unless `tracing.is_active()`. So the sink is a
   no-op for governance events regardless of which path they take. **That is a second, independent
   gap — not a mitigation.**
2. **The six capture sites are currently unreachable in production.** All six live in branches
   predicated on `on_permission_request`, and grep confirms **zero call sites in `src/` pass it** —
   the only occurrences of the name are inside `boot_agent`'s own signature and body
   (`:2559`, `:2632`, `:2635`, `:2641`, `:2647`, `:2648`, `:2677`, `:2680`, `:2685`, `:2686`). The
   `elif isinstance(runtime_gate, InteractivePermissionGate)` branch is additionally a logical
   contradiction — see [CORRECTIONS.md §1](CORRECTIONS.md) and `T-01-approver-selection-dead-branch.md`.
   Every session gets `PolicyApprover`, which takes no emitter at all.

**So the defect is latent, and that is the argument for fixing it now rather than later.** The
moment T-01 makes `RegistryApprover` reachable, this capture bug goes live in the same release —
and it will look like T-01 shipped broken. It is cheap to fix, cheap to test, and it removes a trap
from the exact code T-01 and T-44 are about to edit.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.
>
> **The file is `src/hachi/gateway/orchestrator.py` (3,694 lines). There is no
> `src/hachi/core/orchestrator.py`.**

### 3.1 The block's own claim

`src/hachi/gateway/orchestrator.py:2588-2599`:

```python
    # ------------------------------------------------------------------
    # Slice 2.2 — EventBus funnel (gated behind [events] bus_funnel=true)
    #
    # When the flag is OFF (default): the two closures below are used exactly
    # as before — byte-identical output, zero behavior change.
    #
    # When the flag is ON: an EventBus is instantiated; the same two consumers
    # (read-models append + SSE/TUI surface) are registered as sync subscribers
    # in the same order, so publish() produces identical output by construction.
    # emit_runtime_event / relay_event are then re-bound to publish through the bus.
    # ------------------------------------------------------------------
    _event_bus: Any = None  # EventBus | None; exposed on ProcessSharedServices below
```

The same claim appears in `src/hachi/core/settings.py:183-185`:

```python
    Back-compat: the two primary sync subscribers (read-models append + SSE
    surface) are registered in the same order as the old direct-call path, so
    output is byte-identical by construction.
```

Two things falsify "the same two consumers": the third subscriber at `:2744` (§3.4), and the six
captures at §3.5. Note also that the comment says the flag defaults OFF — it does not.

### 3.2 Definition v1 — always defined

`src/hachi/gateway/orchestrator.py:2601-2615`:

```python
    def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
        read_models.append_event(event)
        if on_event:
            on_event(event.name, event.payload)

    def relay_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
        envelopes = adapt_event(event_type, payload)
        for envelope in envelopes:
            event = envelope.primary
            read_models.append_event(event)
            if on_event:
                on_event(event.name, event.payload)
                for alias in envelope.legacy_aliases:
                    on_event(alias, event.payload)
```

### 3.3 The flag defaults to ON

`src/hachi/core/settings.py:193`:

```python
    bus_funnel: bool = True
```

So v2 is the live path on a default install.

### 3.4 Definition v2 — the rebind, and the third subscriber

`src/hachi/gateway/orchestrator.py:2727-2751`, guarded at `:2727`:

```python
    if _events_cfg.bus_funnel:
        from hachi.core.event_bus import EventBus

        _event_bus = EventBus(job_queue=job_queue)

        def _read_models_sink(event: RuntimeEvent) -> None:
            read_models.append_event(event)

        def _surface_sink(event: RuntimeEvent) -> None:
            if on_event:
                on_event(event.name, event.payload)

        _event_bus.subscribe("*", _read_models_sink, mode="sync", name="read-models")
        _event_bus.subscribe("*", _surface_sink, mode="sync", name="surface")

        from hachi.core.obs.sink import ObservabilitySink

        _event_bus.subscribe("*", ObservabilitySink().handle, mode="sync", name="observability")

        # Rebind emit_runtime_event to publish through the bus.
        def emit_runtime_event(  # type: ignore[misc]  # noqa: F811
            name: str, payload: dict[str, Any] | None = None
        ) -> None:
            event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
            _event_bus.publish(event)
```

Line `:2744` — the `ObservabilitySink` subscription — is a **third** consumer. Read it directly
against the `:2591-2596` comment quoted in §3.1: the two are not compatible. `relay_event` is
redefined the same way at `:2756-2765`, also with `# noqa: F811`.

The other two subscriptions in the file (`:3562`, `:3580`) are scoped to `FILE_UPLOADED` only, so
they are not part of this.

### 3.5 The defect — six by-value captures, all before the rebind

`emit_runtime_event` is a plain local name. A call site that *invokes* it (`emit_runtime_event(...)`)
resolves the name at call time and is fine. A call site that passes it **as an argument** captures
the function object that exists at that moment; the rebind at `:2747` never reaches it.

An exhaustive grep of `emit_runtime_event` in the file gives six such sites before `:2747`:

| Line | Receiver | Subsystem |
|---|---|---|
| `:2636` | `InteractivePermissionGate(event_emitter=…)` | permissions |
| `:2648` | `HandlerApprover(on_permission_request, …)` | approvals |
| `:2651` | `RegistryApprover(get_approval_registry(), …)` | approvals |
| `:2681` | `InteractivePermissionGate(event_emitter=…)` — tier-reconcile rebuild | permissions |
| `:2686` | `HandlerApprover(…)` — tier-reconcile rebuild | approvals |
| `:2688` | `RegistryApprover(…)` — tier-reconcile rebuild | approvals |

**All six are the permission/approval subsystem, and there are no others.** Every remaining
by-value pass in the file (`:2842`, `:3152`, `:3301`, `:3433`, `:3459`, `:3534`, `:3599`, `:3669`,
`:3679`) occurs after `:2747` and therefore captures v2 correctly.

The receivers really do store it by value:

- `src/hachi/core/permissions.py:808-810`:
  ```python
          self._base = base_gate
          self._approval_handler = approval_handler
          self._emit = event_emitter or (lambda *_a, **_kw: None)
  ```
- `src/hachi/core/approvals.py:314-315` (`HandlerApprover`) and `:404-405` (`RegistryApprover`):
  ```python
          self._handler = handler
          self._emit = emit
  ```

And they are exactly the three classes that emit `permission.requested` —
`core/permissions.py:858-868`, `core/approvals.py:334-344`, `core/approvals.py:421-431`.

### 3.6 The clearest single illustration

`src/hachi/gateway/orchestrator.py:3451-3462` — one call expression, two event paths:

```python
    session = AgentSession(
        loop,
        skill_engine,
        memory,
        integrations,
        mcp_manager,
        runtime_gate,
        model_name=model_name,
        event_emitter=emit_runtime_event,
        read_models=read_models,
        job_queue=job_queue,
    )
```

Line `:3457` passes `runtime_gate`, whose `._emit` was captured at `:2636` — **v1**.
Line `:3459` passes `emit_runtime_event`, resolved here at `:3459` — **v2**.
`AgentSession` stores them at `:538` (`self.permission_gate`) and `:542` (`self._event_emitter`).
Two lines apart, two different functions, no indication anywhere.

### 3.7 No test asserts any of this

`tests/test_event_bus.py`, `tests/test_eventbus_reactivity.py`, `tests/test_obs_sink.py`,
`tests/test_obs_boot_config.py` all test the bus and sink in isolation.
`tests/test_obs_boot_config.py` is explicitly written against the extracted helper
`_apply_observability_settings`, not against `boot_agent`.

**No test in the suite calls the real `boot_agent`.** Every reference is a stub —
`tests/test_cold_start_resume.py:189`, `:275` and `tests/test_gateway_runtime_validation.py:79`
all define `_fake_boot_agent`. This constrains §7; see the note there.

## 4. Reproduce the failure

**This failure is not reproducible from a shell against a running Hachi, and you should not
pretend otherwise.** Two independent reasons, both from §2.1: the six capture sites are in branches
no production caller reaches today, and `ObservabilitySink` filters `permission.*` out anyway. So
there is no user-visible symptom to trigger. The proof is a code read plus a language-semantics
demonstration.

### 4.1 The code-reading proof

Read, in this order, and the conclusion is forced:

1. `orchestrator.py:2601` — `emit_runtime_event` defined (v1).
2. `orchestrator.py:2636`, `:2648`, `:2651`, `:2681`, `:2686`, `:2688` — six sites pass the **name
   as an argument**. Each receiver stores it (`permissions.py:810`, `approvals.py:315`, `:405`).
3. `orchestrator.py:2747` — `def emit_runtime_event(...)` again, `# noqa: F811`.
4. Rebinding a name does not mutate objects already handed to other scopes. The six references
   from step 2 still point at the step-1 object.
5. `settings.py:193` — `bus_funnel: bool = True`, so step 3 executes by default.
6. `orchestrator.py:2744` — `ObservabilitySink` is subscribed **only** on the bus, so it is
   unreachable from the step-1 object.

### 4.2 The language-semantics demonstration, and the fix, in six lines

This was run against the repo's interpreter; the output is real:

```bash
uv run python -c "
def outer():
    bus = None
    def emit(): return 'BUS' if bus is not None else 'DIRECT'
    captured = emit          # captured by value, like the six call sites
    bus = object()           # assigned later, like line 2730
    return captured()
print('single-definition + late assignment ->', outer())
"
```

**You will see:** `single-definition + late assignment -> BUS`

That is the whole fix. A nested function closes over the *cell*, not the value, so **one**
definition that reads `_event_bus` at call time gives every holder — including one captured 100
lines earlier — the correct behaviour. Contrast with today's shape, where a second `def` creates a
new object and leaves earlier captures pointing at the old one.

**You should see after the fix:** `grep -c "def emit_runtime_event" src/hachi/gateway/orchestrator.py`
returns `1` (it returns `2` now), and the same for `relay_event`.

## 5. What "fixed" looks like

One definition each, branching on the closure cell at call time. `_event_bus: Any = None` at
`:2599` already establishes the cell before either function is defined, so no other restructuring
is needed.

```python
    _event_bus: Any = None  # EventBus | None; assigned below when [events] bus_funnel is on.

    # NOTE: both closures read _event_bus at CALL time, not definition time. They must be
    # defined exactly ONCE. Re-defining either name later would create a new function object
    # and silently strand every reference already passed by value — the permission gate and
    # the action approvers are constructed before the bus exists and hold theirs forever.
    def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
        if _event_bus is not None:
            _event_bus.publish(event)
            return
        read_models.append_event(event)
        if on_event:
            on_event(event.name, event.payload)

    def relay_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
        envelopes = adapt_event(event_type, payload)
        for envelope in envelopes:
            event = envelope.primary
            if _event_bus is not None:
                _event_bus.publish(event)
            else:
                read_models.append_event(event)
                if on_event:
                    on_event(event.name, event.payload)
            # Aliases: on_event only, never read_models (original behavior preserved).
            if on_event and envelope.legacy_aliases:
                for alias in envelope.legacy_aliases:
                    on_event(alias, event.payload)
```

Then, in the `if _events_cfg.bus_funnel:` block, **delete both redefinitions** (`:2747-2751` and
`:2756-2765`) and both `# noqa: F811` / `# type: ignore[misc]` suppressions. Everything else in that
block — the `EventBus(...)` construction, the three `subscribe` calls, the `logger.info` — stays
exactly as it is.

**Decisions already made for you — do not relitigate:**

- **Read the cell; do not introduce a mutable holder object or a module-level singleton.** The cell
  is already there and the fix uses it. A holder is more machinery for the same result.
- **`relay_event` gets the same treatment even though no by-value capture of it precedes the
  rebind.** Leaving one of the pair split shape-wise is how the next person reintroduces the bug —
  and `# noqa: F811` on a *second definition of the same name* is exactly the smell that should
  never survive review here.
- **Do not change the `[events] bus_funnel` default.** The flag's behaviour is not the bug.
- **Fix the stale comments in the same commit.** `:2591-2592` says the flag defaults OFF (it does
  not) and `:2594-2596` says "the same two consumers" (there are three). `settings.py:183-185`
  repeats the byte-identical claim. Leaving a comment that asserts an invariant the code does not
  hold is how this happened.

## 6. Steps

1. Write the failing test first — §7. Run it. Watch it fail with `expected 1 definition, found 2`.
2. Replace the v1 definitions at `orchestrator.py:2601-2615` with the §5 versions, including the
   `NOTE:` comment. The comment is load-bearing: it is the only thing that will stop T-44's author
   from re-splitting them.
3. Delete the v2 redefinition of `emit_runtime_event` (`:2747-2751`) and of `relay_event`
   (`:2756-2765`), including `# noqa: F811` and `# type: ignore[misc]`.
4. Correct the comment block at `:2588-2598`: the flag defaults **on**, and there are **three**
   sync subscribers (read-models, surface, observability). Correct the same claim in
   `core/settings.py:183-185`.
5. Run `ruff` on the touched file — removing `# noqa: F811` should now be clean rather than an
   unused-suppression error. If ruff complains about the suppression, you missed a redefinition.
6. Run the full suite, then the §10 checks. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_emit_runtime_event_single_definition.py` (new)
- **Test names:** `test_boot_agent_defines_each_event_closure_once` and
  `test_late_bound_bus_reaches_a_reference_captured_before_assignment`
- **They must assert:** (1) `boot_agent` contains exactly one `def emit_runtime_event` and one
  `def relay_event` — parsed from the real source with `ast`, not from a mock; (2) the closure-cell
  pattern the fix relies on actually delivers bus publication to a reference captured *before* the
  bus was assigned, exercised against the real `EventBus` and real `RuntimeEvent`.
- **Test 1 must FAIL before your fix** with:
  `AssertionError: boot_agent defines 'emit_runtime_event' 2 times (lines [2601, 2747]) — expected exactly 1`

```python
"""BB-N: boot_agent defined emit_runtime_event twice. The six call sites that pass
it BY VALUE (all in the permission/approval subsystem) captured the first
definition and never followed the EventBus rebind."""

from __future__ import annotations

import ast
import inspect

import hachi.gateway.orchestrator as orch
from hachi.core.event_bus import EventBus
from hachi.core.runtime_events import RuntimeEvent


def _defs_named(func_name: str, target: str) -> list[int]:
    """Line numbers of every `def <target>` nested directly in `<func_name>`."""
    tree = ast.parse(inspect.getsource(orch))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return [
                child.lineno
                for child in ast.walk(node)
                if isinstance(child, ast.FunctionDef) and child.name == target
            ]
    raise AssertionError(f"{func_name} not found in {orch.__name__}")


def test_boot_agent_defines_each_event_closure_once() -> None:
    for target in ("emit_runtime_event", "relay_event"):
        lines = _defs_named("boot_agent", target)
        assert len(lines) == 1, (
            f"boot_agent defines {target!r} {len(lines)} times (lines {lines}) — "
            "expected exactly 1. A second definition creates a new function object and "
            "strands every reference already passed by value."
        )


def test_late_bound_bus_reaches_a_reference_captured_before_assignment() -> None:
    """The closure-cell contract the fix depends on, against the real EventBus."""
    seen: list[str] = []

    def build():
        bus = None

        def emit(name: str) -> None:
            event = RuntimeEvent(name=name, payload={}, timestamp="2026-07-19T00:00:00Z")
            if bus is not None:
                bus.publish(event)
            else:
                seen.append(f"direct:{name}")

        captured = emit                     # mirrors orchestrator.py:2636/2648/2651
        bus = EventBus()                    # mirrors orchestrator.py:2730
        bus.subscribe("*", lambda e: seen.append(f"bus:{e.name}"), mode="sync", name="probe")
        return captured

    build()("permission.requested")
    assert seen == ["bus:permission.requested"], (
        f"reference captured before the bus existed did not publish through it: {seen}"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

**Why test 1 is structural, and why that is the right call here.** The ideal test would boot a real
agent with `bus_funnel=True` and assert `session.permission_gate._emit is session._event_emitter`
(both are real attributes — `orchestrator.py:538`, `:542`, `permissions.py:810`). It is not written
because **no test in the suite boots a real `boot_agent`** — every existing reference is a
`_fake_boot_agent` stub (§3.7) — and introducing the suite's first real boot inside a half-day fix
buys a large, slow, chromadb-touching test whose failure modes would swamp the signal. The AST test
observes the real source, is deterministic, and fails for exactly one reason. The manual boot check
in §10 covers the rest. **Say all of this in your report; do not imply the stronger test exists.**

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and test 1 failed before the fix with
      `defines 'emit_runtime_event' 2 times (lines [2601, 2747])`.
- [ ] `grep -c "def emit_runtime_event" src/hachi/gateway/orchestrator.py` returns `1`; same for
      `relay_event`.
- [ ] No `# noqa: F811` or `# type: ignore[misc]` remains on either closure, and `ruff` is clean.
- [ ] The `EventBus` construction and all three `subscribe` calls at `:2730-2744` are unchanged.
- [ ] The comment block at `:2588-2598` and `core/settings.py:183-185` no longer claim the flag
      defaults off or that there are two consumers.
- [ ] A real boot completed and emitted `boot.progress` events end to end (§10).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11) that states the impact as **latent**, with both
      bounding facts from §2.1.

## 9. Out of scope — do NOT

- **Do not fix the approver-selection dead branch while you are in here.** This is the drift for
  this task, and it is a strong pull: you will be staring at `:2647-2653`, you will see that the
  `elif` cannot execute, and it is four lines away from your edit. It is
  `T-01-approver-selection-dead-branch.md` — a P0 with its own regression test and its own
  bug-bank entry, and conflating them makes both unreviewable. Leave the branch exactly as it is,
  including its indentation.
- **Do not add `permission.*` to `_SPAN_EVENTS`** in `core/obs/sink.py:37-49`. You will notice it
  is missing (§2.1) and that adding two strings would "complete" the fix. Deciding which events
  belong on a trace span is an observability design call with a token/attribute cost, and it is a
  separate finding. Note it; move on.
- **Do not start decomposing `boot_agent`.** That is `T-44-boot-agent-staged-builders.md`, and this
  task exists partly to make that one safe. Keep this diff to the two closures and the comments.
- **Do not change the `bus_funnel` default, and do not delete the non-bus path.** The direct path
  is the documented opt-out and the `else` branch in §5 preserves it exactly.
- **Do not "simplify" `relay_event`'s alias handling.** The nesting differs subtly between v1
  (`:2612-2615`, aliases inside `if on_event:` after the primary call) and v2 (`:2763-2765`,
  aliases guarded by `if on_event and envelope.legacy_aliases`). §5 preserves both behaviours; do
  not collapse them.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. The §7 test uses stdlib `ast` and `inspect`.

## 10. Verify

```bash
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
uv run pytest tests/test_emit_runtime_event_single_definition.py tests/test_event_bus.py \
              tests/test_eventbus_reactivity.py tests/test_obs_sink.py \
              tests/test_runtime_events.py tests/test_obs_boot_config.py -q

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Then boot for real, with the funnel on (the default), and confirm events still flow.** The unit
tests cannot prove that the unified closure still reaches the read-models store, because they do
not boot:

```bash
uv run python -c "
from hachi.gateway.orchestrator import boot_agent
seen = []
s = boot_agent(on_event=lambda n, p: seen.append(n))
print('events observed during boot:', len(seen))
print('sample:', seen[:5])
"
```

Expect a non-empty list including `boot.progress` entries. An empty list means the unified closure
is not reaching `on_event` — that is a regression, not a flake. Run it once on `main` and once on
your branch and compare the counts.

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-88` is the highest
today; confirm before appending):

```markdown
### BB-N — boot_agent defined emit_runtime_event twice; the governance path kept the pre-bus copy

- **Symptom:** LATENT — no confirmed user-visible symptom. With `[events] bus_funnel=true` (the
  default), every subsystem published runtime events through the `EventBus` **except** the
  permission/approval subsystem, whose emitter bypassed the bus entirely and therefore could never
  reach `ObservabilitySink` or any other bus subscriber. Two facts bound the present-day impact to
  ~zero and both are worth remembering: (a) `ObservabilitySink._SPAN_EVENTS` contains no
  `permission.*` name, so the sink ignored these events anyway — a second, independent gap; and
  (b) all six affected call sites sit in branches predicated on `on_permission_request`, which no
  production caller passes (see the T-01 entry). The defect would have gone live the moment T-01
  made `RegistryApprover` reachable.
- **Root cause:** `gateway/orchestrator.py` `boot_agent` defined `emit_runtime_event` (and
  `relay_event`) once unconditionally, then **again** ~145 lines later inside
  `if _events_cfg.bus_funnel:` with `# noqa: F811`. Rebinding a local name creates a new function
  object; it does not update references already passed by value. Six sites passed the emitter by
  value **before** the rebind — `InteractivePermissionGate(event_emitter=…)` ×2, `HandlerApprover`
  ×2, `RegistryApprover` ×2 — and each stores it as `self._emit`. `AgentSession(...)` showed the
  split in one call expression: the positional `runtime_gate` held the old emitter while the
  `event_emitter=` keyword on the next line held the new one. The block's own comment claimed the
  funnel was "byte-identical by construction" while registering a third subscriber the direct path
  never had.
- **Fix:** One definition each, reading the `_event_bus` closure cell at call time (`if
  _event_bus is not None: publish(...) else: <direct path>`), and both redefinitions deleted along
  with their `# noqa: F811`. The cell is declared before the closures, so a reference captured 100
  lines earlier follows the bus once it is assigned. Stale comments corrected.
- **Avoid:** Never re-`def` a name that has already been passed as an argument — branch inside the
  single definition on a closure cell instead. Treat `# noqa: F811` on a second definition of the
  same callable as a defect, not a style waiver.
- **Locked by:** `tests/test_emit_runtime_event_single_definition.py` —
  `test_boot_agent_defines_each_event_closure_once`,
  `test_late_bound_bus_reaches_a_reference_captured_before_assignment`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **Sequencing.** Land this **before** `T-44-boot-agent-staged-builders.md`. A staged builder has to
  thread the emitter through stage boundaries, and the correct threading is impossible to get right
  while the name is defined twice — the decomposition would bake the split in permanently. It also
  pairs with `T-01-approver-selection-dead-branch.md`: T-01 makes the six sites reachable, so this
  should land in the same release or earlier.
- **`# noqa: F811` is the tell.** Ruff flagged the redefinition and it was suppressed rather than
  fixed. If you find another `F811` suppression on a `def` in this codebase, look for the same bug.
- **Closures capture cells, not values** — §4.2 proves it in six lines. If you are tempted to
  "make it explicit" with a `nonlocal` declaration: `nonlocal` is only needed to *assign*, not to
  read. The read-only closure is correct as written.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — and `_event_bus` is attached
  to it at `orchestrator.py:2795-2796`, so do not reach for `ProcessSharedServices.instance()` to
  find the bus in a test.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb` — relevant if you attempt the real-boot
  test §7 declines to write.
</content>
</invoke>
