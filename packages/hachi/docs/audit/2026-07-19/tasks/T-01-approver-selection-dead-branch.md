# T-01 · Fix the dead `RegistryApprover` branch so gateway sessions can actually be approved

|  |  |
|---|---|
| **Source finding** | NEW P0 — not in the review. See [CORRECTIONS.md](CORRECTIONS.md) §1. Subsumes much of CF-4 in [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | **P0** |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none — **this is the first task in the pack** |
| **Blocks** | [T-15](T-15-approvals-through-control-plane.md), [T-16](T-16-approval-real-deadline.md), [T-17](T-17-fe-resolve-approvals-by-request-id.md), [T-20](T-20-govern-channel-schedule-sessions.md) |
| **Effort** | ~1 day |
| **Difficulty** | High (needs a design decision — read §5 first) |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, `src/hachi/cli/main.py`, `tests/test_action_approval.py` (or a new `tests/test_approver_selection.py`), `docs/bug-bank.md` |

---

## 1. Brief

`boot_agent()` picks one of three `ActionApprover` implementations. The branch that
picks `RegistryApprover` — the only one that can ever produce a *pending approval a
human can resolve* — is a logical contradiction and **can never execute**. On top of
that, the parameter the whole selection keys on (`on_permission_request`) is passed by
**zero call sites in `src/`**. The result: every session in every entry path gets
`PolicyApprover`, so gated actions are either auto-approved with no audit trail
(`unrestricted` tier) or instantly denied with a message telling the user to connect a
companion that is already connected (`guided`/`sandbox`).

When you are done, the gateway boot path selects `RegistryApprover`, a gated action
parks a real request in `PendingApprovalRegistry`, `GET /approvals` returns it, and a
test asserts *which approver `boot_agent` selects* — which no test does today.

## 2. Why this matters

Every strategy document in this repo says the moat is **verifiable, owned governance**.
The pending-approval registry, the `/approvals` REST surface, the Leash screen, the
`permission.requested` SSE event, and the TUI approvals view are all built — and all
of them are downstream of a branch that cannot run. This is not a missing feature; it
is a **shipped feature reporting success while doing nothing**, which is precisely the
pattern the audit called existential. Fixing the frontend approval plumbing
([T-17](T-17-fe-resolve-approvals-by-request-id.md),
[T-18](T-18-fe-surface-decision-failures.md)) is unverifiable until this lands, because
there will never be an approval to resolve.

If the fix you are about to write does not end with "a real approval appears in
`GET /approvals` and blocks the tool until a human resolves it" — stop and re-read.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The contradiction — `gateway/orchestrator.py:2630-2653`, in `boot_agent`

```python
    permissions_file = get_workspace_dir() / "device-permissions.og"
    gate = PermissionGate(permissions_file)
    runtime_gate: Any = gate

    if on_permission_request:
        runtime_gate = InteractivePermissionGate(
            base_gate=gate,
            approval_handler=on_permission_request,
            event_emitter=emit_runtime_event,
        )

    # Build the session-scoped ActionApprover for destructive tool actions.
    # Selection priority:
    #   1. TUI path  — on_permission_request is set → HandlerApprover (reuses TUI modal).
    #   2. Gateway/API path — no handler but context exists → RegistryApprover (parks in
    #      the PendingApprovalRegistry so Agent B's /approvals endpoint can resolve it).
    #   3. No human context at all → PolicyApprover (tier-gated: allow unrestricted, deny
    #      guided/sandbox with an actionable message).
    action_approver: ActionApprover
    if on_permission_request is not None:
        action_approver = HandlerApprover(on_permission_request, emit_runtime_event)
    elif isinstance(runtime_gate, InteractivePermissionGate):
        # InteractivePermissionGate without a handler = gateway context.
        action_approver = RegistryApprover(get_approval_registry(), emit_runtime_event)
    else:
        action_approver = PolicyApprover(gate.tier)
```

Trace it: `runtime_gate` is only reassigned to an `InteractivePermissionGate` inside
`if on_permission_request:`. Reaching the `elif` requires
`on_permission_request is not None` to be **False**. Both cannot hold.
**The `RegistryApprover` branch is unreachable by construction.**

### 3.2 Duplicated verbatim in the tier-reconcile block — `gateway/orchestrator.py:2685-2690`

```python
            if on_permission_request is not None:
                action_approver = HandlerApprover(on_permission_request, emit_runtime_event)
            elif isinstance(runtime_gate, InteractivePermissionGate):
                action_approver = RegistryApprover(get_approval_registry(), emit_runtime_event)
            else:
                action_approver = PolicyApprover(gate.tier)
```

Same contradiction. Whatever you do to §3.1 must be done here too — or better, both
should call one shared helper (see §5).

### 3.3 `on_permission_request` has zero callers — `boot_agent` signature at `gateway/orchestrator.py:2557-2561`

```python
def boot_agent(
    on_event: Callable[..., None] | None = None,
    on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None = None,
    resume_session_id: str | None = None,
) -> AgentSession:
```

`rg -n "on_permission_request" src/` returns **10 hits, all inside
`gateway/orchestrator.py` itself**. No caller anywhere passes it. All five production
boot paths omit it:

| Path | Anchor | Call |
|---|---|---|
| Gateway / web (**the important one**) | `cli/main.py:276` in `_InProcessGatewayRuntime._boot_session_agent` | `agent = boot_agent(resume_session_id=resume_session_id)` |
| Legacy Rich REPL | `cli/main.py:3602` in `_run_repl` | `agent: AgentSession = boot_agent(on_event=_render_event)` |
| `hachi run --once` | `cli/main.py:3776` in `_run_once` | `agent: AgentSession = boot_agent()` |
| `hachi schedule run-due` | `cli/commands/schedule.py:169` in `schedule_run_due` | `agent = boot_agent()` |
| `hachi schedule run-now` | `cli/commands/schedule.py:205` in `schedule_run_now` | `agent = boot_agent()` |
| Channels (Telegram/WhatsApp) | `channels/runner.py:20` in `GatewaySessionRunner.__init__`, called at `:29` | `def __init__(self, boot: Callable[[], AgentSession] = boot_agent)` … `agent = self._boot()` |

The Textual cockpit TUI does **not** call `boot_agent` at all — it is REST-only over
`GatewayClient`. So `HandlerApprover` has no production path either; only
`PolicyApprover` is ever constructed.

### 3.4 What `PolicyApprover` does instead — `core/approvals.py:278-292`

```python
    def require(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        if self._tier == "unrestricted":
            return (True, "auto-approved (unrestricted tier)")
        return (
            False,
            "This action needs human approval. Connect the TUI or web companion to approve, "
            "or set tier=unrestricted in ~/.hachi/device-permissions.og.",
        )
```

- `guided` / `sandbox`: **instant deny**, telling the user to connect a companion that
  *is* connected and has no route to approve. This is a live, still-unfixed
  auto-decline mechanism, distinct from BB-77.
- `unrestricted`: **instant auto-approve** with no request, no event, no audit row.

### 3.5 Nothing populates the registry, so `permission.requested` is never emitted

The event has exactly three emitters, all inside classes that are never constructed in
production:

- `core/approvals.py:334-344` — `HandlerApprover.require`
- `core/approvals.py:421-431` — `RegistryApprover._build_and_park`
- `core/permissions.py:858-868` — `InteractivePermissionGate._request_decision`

`PendingApprovalRegistry.create` (`core/approvals.py:127-136`) therefore never runs, so
`list_pending()` (`core/approvals.py:138-157`) always returns `[]` and the
`/approvals` route (`gateway/fastapi_app.py:1873-1901`) is permanently
`{"pending": []}`.

### 3.6 Blast radius: `action_approver` is consumed at exactly ONE place

`gateway/orchestrator.py:3243-3250`:

```python
        ToolSpec(
            # Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, Contacts, Meet, Tasks).
            # Only mounted when GOOGLE_CLIENT_ID is set; degrades to a friendly stub otherwise.
            # The session-scoped action_approver gates destructive leaf tools (send_email,
            # trash_file, etc.) through the appropriate human-approval path.
            name="google",
            register_fn=lambda d: register_google_tools(d.tool_registry, approver=action_approver),
        ),
```

`rg -n "action_approver" src/` returns hits only in `orchestrator.py`, and `:3249` is
the only *use*. So today the approver chain gates **Google Workspace tools only**.

This bounds your blast radius — and it raises a second question you must **not** answer
here: why is exactly one integration gated? Flag it as a follow-up (§9).

### 3.7 Why it survived — `tests/test_action_approval.py`

Every test in that file constructs the approvers **by hand**:

```python
        approver = RegistryApprover(registry, emit=_noop_emit, timeout=5.0)   # :225
        approver = PolicyApprover("guided")                                    # :72
        approver = HandlerApprover(handler=bad_handler, emit=_noop_emit)       # :211
```

`rg -n "action_approver" tests/` returns **nothing**. **No test asserts which approver
`boot_agent` selects.** That is the exact gap your regression test must close.

## 4. Reproduce the failure

**This is not reproducible as a single shell command, and you should not pretend
otherwise.** `boot_agent()` spawns MCP subprocesses, opens SQLite stores and builds LLM
clients; and the only approver-gated surface (§3.6) requires `GOOGLE_CLIENT_ID` to be
configured before it mounts anything real. What *is* mechanically checkable is the
premise, and it is decisive.

```bash
# 1. The selection parameter has no caller. Expect: every hit is inside orchestrator.py.
rg -n "on_permission_request" src/

# 2. Enumerate every boot path. Expect: 5 call sites, NONE passing on_permission_request.
rg -n "boot_agent\(" src/

# 3. The approver is consumed once. Expect: one hit at register_google_tools(...).
rg -n "action_approver" src/

# 4. No test pins the selection. Expect: NO output.
rg -n "action_approver" tests/
```

**You will see now:** (1) ten hits, all in `gateway/orchestrator.py`; (2) five call
sites, none passing the handler; (3) a single consumer; (4) silence. Combined with the
branch trace in §3.1, that proves every session gets `PolicyApprover`.

**You should see after the fix:** grep (2) shows the gateway path at `cli/main.py:276`
passing an explicit gateway marker, and grep (4) returns your new test.

**Optional live confirmation** (only if you already have a gateway running and
`GOOGLE_CLIENT_ID` configured — do not set it up just for this):

```bash
curl -s -H "Authorization: Bearer $HACHI_GATEWAY_TOKEN" http://127.0.0.1:8787/approvals
```

Ask the agent to send an email, then re-run. Today: `{"pending":[]}` both times, and
the turn returns the "Connect the TUI or web companion" refusal. After the fix: the
second call lists a real `request_id` and the turn blocks until you POST a decision.

## 5. What "fixed" looks like

> ### DECISION REQUIRED
>
> `boot_agent` has **no signal today that distinguishes "gateway context" from "CLI
> context"**. Every path calls it with the same (empty) arguments. The fix therefore
> has to introduce one. Pick before you type:
>
> **(a) Add one explicit parameter to `boot_agent` — RECOMMENDED.**
> e.g. `approval_surface: Literal["gateway", "cli", "handler"] | None = None`, defaulting
> to `None` (= today's `PolicyApprover`). `_boot_session_agent` (`cli/main.py:276`)
> passes `"gateway"`.
> *For:* explicit, trivially testable, no layering violation, matches the existing
> `on_event` / `resume_session_id` parameter style, and leaves every other path's
> behaviour byte-identical. *Against:* one more parameter on an already-long signature.
>
> **(b) Detect gateway context implicitly** — e.g. sniff a module-global set by the
> gateway, or check whether a control plane is live.
> *For:* no signature change. *Against:* `og_engine`/`core` must not know about
> `gateway` (import-linter contract, see §12); implicit global state is exactly the
> class of bug this task is fixing; and it is far harder to test.
>
> **(c) Make `RegistryApprover` the default whenever no handler is supplied** (delete
> `PolicyApprover` from the default path).
> *For:* smallest diff. *Against:* **it changes CLI behaviour for the worse.**
> `hachi run --once` and `hachi schedule run-due` have no human attached; under (c) a
> gated action would block for the full 180 s timeout (`core/approvals.py:396`) and then
> deny, instead of failing fast. Do not choose this.
>
> **Recommendation: (a).** The rest of this spec assumes it. If you choose otherwise,
> say so in the commit message and adapt §6/§7.

Target state:

1. `boot_agent` gains one keyword-only parameter with a safe default:

   ```python
   def boot_agent(
       on_event: Callable[..., None] | None = None,
       on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None = None,
       resume_session_id: str | None = None,
       *,
       approval_surface: str | None = None,   # "gateway" | None
   ) -> AgentSession:
   ```

2. A single module-level helper owns the selection, so §3.1 and §3.2 cannot diverge
   again:

   ```python
   def select_action_approver(
       *,
       on_permission_request: Callable[[PermissionRequest], PermissionDecision] | None,
       approval_surface: str | None,
       tier: str,
       emit: Callable[[str, dict[str, Any]], None],
   ) -> ActionApprover:
       """Pick the approver for this session. Exactly one rule per surface."""
       if on_permission_request is not None:
           return HandlerApprover(on_permission_request, emit)
       if approval_surface == "gateway":
           return RegistryApprover(get_approval_registry(), emit)
       return PolicyApprover(tier)
   ```

   Both `:2646-2653` and `:2685-2690` become a call to it. The dead
   `isinstance(runtime_gate, InteractivePermissionGate)` test is deleted.

3. `cli/main.py:276` in `_boot_session_agent` passes it:

   ```python
   agent = boot_agent(resume_session_id=resume_session_id, approval_surface="gateway")
   ```

4. Every other call site is **untouched** and keeps `PolicyApprover`.

5. Observable outcome: with the gateway running at `guided` tier, a gated Google action
   emits `permission.requested`, appears in `GET /approvals` with a real `request_id`,
   and blocks the tool until `POST /approvals/{id}` resolves it or 180 s elapse.

## 6. Steps

1. Write the regression test from §7 and watch it **fail**. Do not skip this.
2. Add `select_action_approver(...)` as a module-level function in
   `gateway/orchestrator.py`, near the other boot helpers and **above** `boot_agent`.
   Keep the existing selection-priority comment — move it onto the new function's
   docstring rather than deleting it (CLAUDE.md Rule 3: don't delete comments).
3. Add the keyword-only `approval_surface: str | None = None` parameter to `boot_agent`
   and document it in the existing `Args:` block of the docstring (`:2576-2578`).
4. Replace the `if/elif/else` at `:2646-2653` with a call to
   `select_action_approver(...)`, passing `gate.tier`.
5. Replace the duplicate at `:2685-2690` with the same call — inside the reconcile
   block it must use the **rebuilt** `gate.tier`.
6. Change `cli/main.py:276` to pass `approval_surface="gateway"`.
7. Run the regression test — it must now pass.
8. Run `uv run python scripts/preflight.py` (**full**, not `--quick`) and report the
   real counts. This changes gating behaviour; a scoped run will not surface it.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_approver_selection.py` (**new**)
- **Test names:** `test_gateway_boot_path_requests_registry_approver` and
  `test_select_action_approver_maps_gateway_surface_to_registry_approver`
- **It must assert:** the real, observed selection — (1) that the gateway boot path
  actually asks `boot_agent` for the gateway surface, and (2) that the gateway surface
  actually yields a `RegistryApprover`. Together they close the §3.7 gap.
- **It must FAIL before your fix** with:
  - test 1: `AssertionError: assert None == 'gateway'` (the kwarg is not passed today)
  - test 2: `ImportError: cannot import name 'select_action_approver'` — and once the
    helper exists but before step 6, it is test 1 that holds the line. Test 1 is the
    behavioural lock; keep it even if you restructure test 2.

```python
# sketch — adapt to the repo's existing fixtures
from unittest.mock import MagicMock

import pytest


def test_gateway_boot_path_requests_registry_approver(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gateway boot path must ask boot_agent for the registry-backed approver.

    Regression: the RegistryApprover branch in boot_agent was unreachable AND no
    caller ever selected it, so every gateway session silently got PolicyApprover.
    """
    from hachi.cli import main as cli_main

    captured: dict[str, object] = {}

    def _spy(*args: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(cli_main, "boot_agent", _spy)

    runtime = cli_main._InProcessGatewayRuntime()
    runtime._boot_session_agent("sess-1")

    assert captured.get("approval_surface") == "gateway"


@pytest.mark.parametrize(
    ("surface", "expected"),
    [("gateway", "RegistryApprover"), (None, "PolicyApprover")],
)
def test_select_action_approver_maps_gateway_surface_to_registry_approver(
    surface: str | None, expected: str
) -> None:
    """Selection is total and explicit: gateway -> registry, anything else -> policy."""
    from hachi.gateway.orchestrator import select_action_approver

    approver = select_action_approver(
        on_permission_request=None,
        approval_surface=surface,
        tier="guided",
        emit=lambda _name, _payload: None,
    )
    assert type(approver).__name__ == expected


def test_handler_still_wins_over_surface() -> None:
    """A supplied handler keeps priority — the CLI/TUI contract is unchanged."""
    from hachi.core.permissions import PermissionDecision
    from hachi.gateway.orchestrator import select_action_approver

    approver = select_action_approver(
        on_permission_request=lambda _req: PermissionDecision(action="deny"),
        approval_surface="gateway",
        tier="guided",
        emit=lambda _name, _payload: None,
    )
    assert type(approver).__name__ == "HandlerApprover"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and `test_gateway_boot_path_requests_registry_approver` failed before the fix with `assert None == 'gateway'`.
- [ ] `rg -n "isinstance\(runtime_gate, InteractivePermissionGate\)" src/` returns **nothing** — both dead branches are gone.
- [ ] The selection logic exists in exactly **one** place; `:2646` and `:2685` both call it.
- [ ] `rg -n "boot_agent\(" src/` shows `cli/main.py:276` passing `approval_surface="gateway"` and the other four call sites unchanged.
- [ ] `hachi run --once` and `hachi schedule run-due` still get `PolicyApprover` (no behaviour change on unattended paths).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not widen the approver to other tools.** §3.6 shows `action_approver` gates only
  `register_google_tools`. Wiring `os_tools`, `file_tools`, MCP or the shell tool into
  the approver is a real and probably necessary follow-up — **note it and move on**.
  It multiplies the blast radius of this change and would make the regression
  unreviewable.
- **Do not fix the second Google mount path.** `gateway/orchestrator.py:3325-3352`
  registers native capability integrations via `instance.register_tools(tool_registry)`
  with **no approver**, which can replace the gated handlers. That is CF-11 and it has
  its own spec — [T-35](T-35-google-double-mount.md). Out of scope here.
- **Do not delete `HandlerApprover`** because it has no caller today. It is the TUI
  contract and is fully tested.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not start decomposing `boot_agent` (that is CF-6). Add the parameter, extract the
  one helper, stop.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Run the FULL suite, not a scoped run.** This task changes real gating behaviour:
under `unrestricted` the gateway silently auto-approved every gated action and now
parks a request instead; under `guided`/`sandbox` it denied instantly and now blocks
for up to 180 s. Any test that exercised a gated Google action through a booted gateway
session may change timing or outcome. Report the **actual** pass/fail counts.
"Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — `RegistryApprover` unreachable: every session silently got `PolicyApprover`

- **Symptom:** `GET /approvals` was permanently `{"pending": []}` and the Leash screen was structurally empty. Under `guided`/`sandbox` every gated action was denied instantly with "Connect the TUI or web companion to approve" — while the companion was connected. Under `unrestricted` every gated action was auto-approved with no request and no audit row.
- **Root cause:** Two compounding defects in `boot_agent` (`gateway/orchestrator.py`). (1) The `RegistryApprover` branch was `elif isinstance(runtime_gate, InteractivePermissionGate)`, but `runtime_gate` only becomes an `InteractivePermissionGate` when `on_permission_request` is truthy — and reaching the `elif` requires it to be `None`. Logically unreachable, and duplicated verbatim in the tier-reconcile block. (2) `on_permission_request` was passed by zero call sites in `src/`, so all five boot paths fell through to `PolicyApprover`. `permission.requested` therefore had no live emitter and `PendingApprovalRegistry` was never populated.
- **Fix:** Extracted `select_action_approver(...)` as the single selection rule and added an explicit `approval_surface` parameter to `boot_agent`; `_InProcessGatewayRuntime._boot_session_agent` (`cli/main.py`) passes `"gateway"`. Both former `if/elif/else` sites now call the helper.
- **Avoid:** never branch on a value derived from the same condition you already
  branched on — and never let a composition root choose a strategy on a signal no
  caller supplies. If a boot path needs to pick a behaviour, pass it explicitly and
  pin the choice with a test.
- **Locked by:** `tests/test_approver_selection.py` — `test_gateway_boot_path_requests_registry_approver`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — do not reach
  through it in the new helper. `select_action_approver` must depend on nothing but its
  arguments.
- **Import layering:** `pyproject.toml` `[tool.importlinter]` forbids
  `hachi.core` / `hachi.og_engine` / `hachi.tools` / `hachi.jobs` / `hachi.integrations`
  from importing `hachi.gateway`. The new helper lives in `hachi.gateway.orchestrator`,
  which may import `hachi.core.approvals` — that direction is fine. Do **not** invert it.
- **`get_approval_registry()` is a process-global singleton** (`core/approvals.py:244-255`).
  Tests that assert on registry contents must not leak between test functions; the
  existing suite works around this by constructing `PendingApprovalRegistry()` directly
  (`tests/test_action_approval.py:224`). Follow that pattern — do **not** add a
  registry-reset hook to production code just for tests.
- **No existing test needs amending for this task.** Every test in
  `tests/test_action_approval.py` constructs approvers by hand and is unaffected by the
  selection change. If one of them goes red, you have changed an approver's *behaviour*
  — which is out of scope; revert and re-read §5.
- **The 180 s blocking wait is real** (`core/approvals.py:396` default, consumed at
  `:473` → `entry.event.wait(timeout=...)` at `:200`). If a test hangs after your fix,
  you have booted a gateway session that is genuinely waiting for a human. Resolve it or
  construct the approver with a short `timeout=` as the existing tests do.
