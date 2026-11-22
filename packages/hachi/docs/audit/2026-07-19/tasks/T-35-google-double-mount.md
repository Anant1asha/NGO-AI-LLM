# T-35 · Collapse the two Google tool mount paths into one, preserving the approver

|  |  |
|---|---|
| **Source finding** | CF-11 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **the review is wrong about both consequences — see §2.1** |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | **[T-36-tool-registry-duplicate-guard.md](T-36-tool-registry-duplicate-guard.md) — T-36 must not land before this** |
| **Effort** | ~half a day |
| **Difficulty** | Medium |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, `tests/test_google_tools_wire.py`, `tests/test_google_double_mount.py` (new), `docs/bug-bank.md` |

---

## 1. Brief

Google Workspace tools are mounted **twice** during `boot_agent` — once via `TOOL_SPECS` *with*
the session's `action_approver`, then again via the capability loop *without* it. The second
mount overwrites every handler with an approver-less one. Because a Google client with no
approver **denies** destructive actions by design, the live effect is that `send_email`,
`trash_file` and every other gated Google action is permanently blocked for exactly those users
who have Google fully configured. When you are done there will be one mount path, it will carry
the approver, and a test will fail if a second one reappears.

## 2. Why this matters

Two things, and they pull in different directions, which is why this task exists rather than a
one-line delete.

The **user-facing** reason: this breaks Google for the users who set it up correctly. Not an edge
case — the double-mount fires precisely in the fully-configured, fully-connected state. Someone
who follows the setup flow to completion gets tools that are visible to the model, callable, and
that answer every destructive request with *"No approver connected for this session."* Someone
who half-configures Google never hits it.

The **architectural** reason: the registry silently ends up in a state where a tool's schema comes
from one mount and its handler from another. Nothing detects it, nothing logs it, and the two
mounts are 80 lines apart in the same function. T-36 makes this class of mistake impossible — but
T-36 turns it into a boot crash, so this must land first.

### 2.1 ⚠️ The audit is wrong about this finding — twice. Read this before you write anything.

An implementer who trusts CF-11's wording will write the wrong fix, the wrong test, and a wrong
bug-bank entry. Both errors are corrected here, and both corrections were verified by running
code against `main` @ `bd24afe`.

**CORRECTION 1 — "schemas duplicate (Anthropic rejects duplicate names)" is REFUTED.**

`ToolRegistry.get_schemas` de-duplicates on read. `src/hachi/core/loop.py:320-321` (docstring)
states the intent, and `:330-337` implements it:

```python
        Duplicates by tool name are dropped (first registration wins) so the
        Anthropic API never receives a ``tools: Tool names must be unique`` error.
```

```python
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for schema in candidates:
            name = schema.get("name")
            if name and name not in seen:
                seen.add(name)
                result.append(schema)
        return result
```

Verified by running it:

```
len(_schemas)      = 2   <- duplicate appended, unbounded growth
len(get_schemas()) = 1   <- deduped on READ: no API error
```

There is no API failure. The residual harm is that `self._schemas` grows without bound (44 dead
dicts per boot for Google) — a memory and diagnosability wart, not an outage. **Do not write a
test asserting the Anthropic API rejects anything. It does not get the chance.**

**CORRECTION 2 — "gated handlers are replaced by ungated ones" is REFUTED *and inverted*.**

The handler replacement is real: `self._tools[tool_name] = func` (`core/loop.py:188`) is a plain
dict assignment, so the second mount's handler wins. But "no approver" does not mean "no gate" —
it means **deny**. `src/hachi/integrations/google/client.py:288-292`:

```python
        if self.approver is not None:
            return self.approver.require(action, summary, detail)
        # No approver wired → fail safe (deny). Tier policy is applied upstream when an
        # approver exists; a bare client with no approver denies destructive actions.
        return (False, "No approver connected for this session; destructive action blocked.")
```

Verified by running it:

```
approver default   = None
require_approval() = (False, 'No approver connected for this session; destructive action blocked.')
```

**So the actual impact is an availability/functional bug: every destructive Google action is
permanently blocked whenever Google is fully configured.** It is not privilege escalation, not a
security-gate bypass, and not an open door. The `src/hachi/tools/google_tools.py:97-100` docstring
already says this is the designed behaviour:

```python
        approver: Optional :class:`~hachi.core.approvals.ActionApprover` to gate...
                  ``None`` keeps backward compatibility — the client will fail-safe (deny) when
                  a destructive action is requested without an approver.
```

**Write the bug-bank entry as an availability defect.** If you describe it as a bypass, the next
person to read `docs/bug-bank.md` will go hunting for a hole that does not exist.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.
>
> **The file is `src/hachi/gateway/orchestrator.py` (3,694 lines). There is no
> `src/hachi/core/orchestrator.py` — the audit's path is wrong throughout.**

### 3.1 Path A — `TOOL_SPECS`, **with** approver

`src/hachi/gateway/orchestrator.py:3243-3250`:

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

Executed at `src/hachi/gateway/orchestrator.py:3320`:

```python
    registration_results = registrar.install(TOOL_SPECS, deps)
```

Which reaches `src/hachi/tools/google_tools.py:118-121`:

```python
    from hachi.integrations.google import GoogleIntegrationHub

    hub = GoogleIntegrationHub(approver=approver)
    hub.register_tools(registry)
```

### 3.2 Path B — the capability loop, **without** approver

The descriptor, `src/hachi/gateway/orchestrator.py:331-348` — note `factory` at `:345-347` takes
no `approver` argument:

```python
            CapabilityDescriptor(
                id="google",
                kind="native_integration",
                enabled=google_enabled,
                configured=google_configured,
                available=_is_module_available("hachi.integrations.google"),
                ...
                factory=lambda: __import__(
                    "hachi.integrations.google", fromlist=["GoogleIntegrationHub"]
                ).GoogleIntegrationHub(),
            ),
```

The loop, `src/hachi/gateway/orchestrator.py:3325-3352`:

```python
    for descriptor in capability_registry.iter_enabled():
        if descriptor.kind != "native_integration":
            continue
        if not descriptor.available or not descriptor.configured:
            _register_capability_setup_stub(tool_registry, descriptor)
            continue

        try:
            instance = capability_registry.instantiate(descriptor.id)
        except Exception as exc:
            _register_capability_setup_stub(tool_registry, descriptor)
            ...
            continue

        if isinstance(instance, tuple):
            for sub_instance in instance:
                if hasattr(sub_instance, "register_tools"):
                    sub_instance.register_tools(tool_registry)
                    native_registration_count += 1
        elif hasattr(instance, "register_tools"):
            instance.register_tools(tool_registry)
            native_registration_count += 1
```

And the approver becomes `None` at `src/hachi/integrations/google/__init__.py:37` / `:65-67`:

```python
    def __init__(self, approver: ActionApprover | None = None):
```

```python
        self.client = GoogleHTTPClient(scopes=list(all_scopes))
        # Wire the session approver so all destructive leaf tools can gate actions.
        self.client.approver = approver
```

### 3.3 The exact conditions under which both fire

**Path A** fires when `_google_client_id()` is truthy —
`src/hachi/tools/google_tools.py:105-107`:

```python
    from hachi.core.oauth import _google_client_id

    if not _google_client_id():
```

i.e. `GOOGLE_CLIENT_ID` present in the process environment **or** in a project / config-dir
`.env`. When falsy, `register_google_tools` mounts a single stub named `google_not_configured`
(`google_tools.py:75-76`, `:108-116`) and returns `False`.

**Path B** fires when the descriptor passes `:3326-3330` — `kind == "native_integration"`
**and** `descriptor.available` **and** `descriptor.configured`, having already passed
`iter_enabled()` (`:159-160`, `enabled` truthy). `enabled` / `configured` come from `cap_flags`
(`:308-323`), read from config `capabilities.google`, with `enabled` additionally satisfied by an
existing OAuth token — `:316-322`:

```python
        if not enabled:
            try:
                from hachi.integrations.oauth_flow import OAuthTokenStore

                enabled = OAuthTokenStore().is_connected(cap_id)
            except Exception:
                pass
```

**Both conditions are satisfied simultaneously in the normal working state**: a client id is
configured *and* the capability is enabled/configured *and* the module is importable. That is
what "Google is set up and connected" means. This is not a rare misconfiguration.

**Ordering:** Path A runs at `:3320`, Path B at `:3325-3352`. Path A is first.

### 3.4 The resulting split state — name it in the bug-bank entry

- `get_schemas()` de-dupes **first-wins** → the model sees **Path A's schema**.
- `_tools[name] = func` is **last-wins** → execution uses **Path B's handler**.

The registry is internally inconsistent: schema from one mount, handler from another. Nothing in
the codebase can currently detect this.

### 3.5 The group re-tagging that only Path A performs

`src/hachi/tools/google_tools.py:123-127` — reaching into registry privates because there is no
public re-tagging API:

```python
    # Re-tag every registered google_* tool with the lazy group so the
    # orchestrator's use_tools("google") activates them correctly.
    for name in GOOGLE_TOOL_NAMES:
        if name in registry._tools:
            registry._groups[name] = "google"
```

Path B does no such thing. It happens to be harmless today because `classify()` at `:3357-3363`
runs afterwards with `prefix_groups={"google_": "google"}` and re-stamps everything. Do not
remove either mechanism as part of this task — see
[T-39-tool-groups-at-registration.md](T-39-tool-groups-at-registration.md).

### 3.6 Google is the only capability with two mounts

`TOOL_SPECS` (`:3222-3316`) contains: `search`, `files`, `google`, `presentation`, `schedule`,
`rest_apis`, `memory`, `session`, `integration_tools`, `mcp_tools`, `config`, `delegation`. The
capability registry (`:329-…`) contains `google`, `slack`, `notion`. **`google` is the only id in
both.** Slack and Notion mount once, via the capability loop only. That is what makes the fix
targeted rather than a redesign of the capability mechanism.

### 3.7 No test covers the double-mount

`tests/test_google_tools_wire.py` (12 tests) exercises `register_google_tools` **in isolation**:
`test_returns_false_when_no_client_id`, `test_registers_stub_when_no_client_id`,
`test_mounts_hub_tools_when_client_id_set`, `test_tools_tagged_google_group`,
`test_hub_register_tools_called_once`, … The last one is about a single call *inside*
`register_google_tools`; nothing asserts anything about the two boot paths interacting, because
nothing in that file boots.

## 4. Reproduce the failure

**The end-to-end failure is not reproducible from a shell without live Google credentials, and
you must not create any.** Both halves of the mechanism *are* independently reproducible, and both
commands below were run against `main` @ `bd24afe` — these outputs are real.

### 4.1 The registry's behaviour under a double mount

```bash
uv run python -c "
from hachi.core.loop import ToolRegistry
r = ToolRegistry()
schema = {'name': 'demo', 'input_schema': {'type':'object','properties':{}}}
r.register(schema, lambda: 'FIRST (gated)')
r.register(schema, lambda: 'SECOND (ungated)')
print('len(_schemas)      =', len(r._schemas))
print('len(get_schemas()) =', len(r.get_schemas()))
print('handler result     =', r._tools['demo']())
"
```

**You will see now:**

```
len(_schemas)      = 2
len(get_schemas()) = 1
handler result     = SECOND (ungated)
```

Schema first-wins, handler last-wins, no error anywhere. That is CORRECTION 1 and the split state
in three lines.

### 4.2 What an approver-less Google client does

```bash
uv run python -c "
from hachi.integrations.google.client import GoogleHTTPClient
c = GoogleHTTPClient(scopes=['openid'])
print('approver default   =', c.approver)
print('require_approval() =', c.require_approval('send_email','send a mail'))
"
```

**You will see now:**

```
approver default   = None
require_approval() = (False, 'No approver connected for this session; destructive action blocked.')
```

That is CORRECTION 2: deny, not permit.

### 4.3 The code-reading proof that both paths run

There is no shell command for this one. Read, in order:

1. `orchestrator.py:3243-3250` — Path A is in `TOOL_SPECS`, unconditionally, with `approver=`.
2. `orchestrator.py:3320` — `TOOL_SPECS` is installed.
3. `google_tools.py:107` — Path A no-ops **only** when `_google_client_id()` is falsy.
4. `orchestrator.py:331-348` — the `google` descriptor's factory takes **no** approver.
5. `orchestrator.py:3325-3330` — Path B's guard: enabled ∧ native ∧ available ∧ configured.
6. `orchestrator.py:3350-3351` — Path B calls `register_tools` on the approver-less hub.

Nothing between steps 2 and 6 unregisters anything. There is no `if already_mounted` check
anywhere in either path — grep `unregister` and you will find it only in `core/mcp_client.py`
(`:1788`, `:1799`, `:1821`).

**You should see after the fix:** with Google fully configured, exactly one mount runs;
`len(registry._schemas)` contains each `google_*` name once; and the handler in `_tools` belongs
to a hub whose `client.approver is action_approver`.

## 5. What "fixed" looks like

**Keep Path A. Stop Path B from mounting Google's tools.** The decision is made here — do not
re-litigate it. Reasons, in order of weight:

1. **Path A carries the approver and Path B structurally cannot.** The capability factory is a
   zero-argument lambda constructed inside `_build_capability_registry(config)`, a module-level
   function whose only input is config. Wiring a session-scoped `ActionApprover` into it means
   coupling the capability registry to per-session state — a much larger change than this task,
   and one that would then apply to Slack and Notion too.
2. **Path A handles the not-configured case better for this integration.** It checks
   `_google_client_id()` and mounts a purpose-written `google_not_configured` stub explaining
   exactly which env var to set.
3. **Path A owns the group re-tagging** (§3.5).

### The mechanism

Add a declarative field to `CapabilityDescriptor` (`orchestrator.py:141-149`) rather than
special-casing the string `"google"` in the loop:

```python
@dataclass
class CapabilityDescriptor:
    id: str
    kind: str
    enabled: bool
    configured: bool
    available: bool
    requires_scopes: tuple[str, ...]
    setup_hint: str
    factory: Callable[[], Any] | None = None
    mounts_tools: bool = True
    """False when this capability's tools are mounted elsewhere (e.g. via TOOL_SPECS).

    The descriptor is still used for status reporting, `iter_enabled()`, and optional
    skill-pack installation — only the `register_tools` call in boot_agent is skipped.
    """
```

Set `mounts_tools=False` on the `google` descriptor, with a comment pointing at the `TOOL_SPECS`
entry. Then guard **both** branches of the loop body — the stub branch as well as the mount
branch — so a configured-but-not-connected Google does not get a redundant
`setup_google_capability` stub competing with Google's own `google_not_configured` stub:

```python
    for descriptor in capability_registry.iter_enabled():
        if descriptor.kind != "native_integration":
            continue
        if not descriptor.mounts_tools:
            # Tools are mounted by TOOL_SPECS (with the session approver). The descriptor
            # still drives status_snapshot() and install_optional_skill_pack().
            continue
        if not descriptor.available or not descriptor.configured:
            _register_capability_setup_stub(tool_registry, descriptor)
            continue
        ...
```

**What must NOT change:** `iter_enabled()` must still yield the google descriptor, because
`orchestrator.py:2772-2775` uses enabled capability ids to install optional skill packs, and
`status_snapshot()` (`:165-176`) reports capability state to the UI. The `continue` goes **inside**
the loop body, after the `kind` check — not into `iter_enabled()`.

## 6. Steps

1. Write the failing test first — §7. Run it. Watch it fail.
2. Add `mounts_tools: bool = True` to `CapabilityDescriptor` (`orchestrator.py:141-149`) with the
   docstring from §5. It is defaulted, so Slack and Notion are unaffected.
3. Add `mounts_tools=False` to the `google` `CapabilityDescriptor` (`orchestrator.py:331-348`),
   with a comment naming the `TOOL_SPECS` entry at `:3243-3250` as the single mount point.
4. In the capability loop (`orchestrator.py:3325-3352`), add the `if not descriptor.mounts_tools:
   continue` guard immediately after the `kind` check and **before** the
   `available`/`configured` stub branch.
5. Re-read the loop and confirm `native_registration_count` no longer counts Google. If any log
   line or return value reports that number, make sure the new number is still honest.
6. Run the full suite, then §10's boot check. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_google_double_mount.py` (new)
- **Test names:** `test_google_capability_does_not_mount_tools` and
  `test_google_tools_keep_their_approver_after_capability_loop`
- **They must assert:** (1) the `google` descriptor built by the real `_build_capability_registry`
  declares `mounts_tools=False` while `slack`/`notion` do not, and is still yielded by
  `iter_enabled()`; (2) simulating the two mounts in order against a real `ToolRegistry` leaves
  the surviving handler bound to a hub whose `client.approver` is the approver object, not `None`.
- **They must FAIL before your fix** with: `AttributeError: 'CapabilityDescriptor' object has no
  attribute 'mounts_tools'` (test 1) and `AssertionError: surviving handler's approver is None —
  the approver-less capability mount overwrote the gated one` (test 2).

```python
"""BB-N: Google tools were mounted twice — once with the session approver
(TOOL_SPECS) and once without it (capability loop). The approver-less mount
won, so every destructive Google action was permanently denied."""

from __future__ import annotations

from hachi.core.loop import ToolRegistry
from hachi.gateway.orchestrator import _build_capability_registry


def test_google_capability_does_not_mount_tools() -> None:
    registry = _build_capability_registry(
        {"capabilities": {"google": {"enabled": True, "configured": True},
                          "slack": {"enabled": True, "configured": True}}}
    )
    google = registry.get("google")
    assert google is not None
    # Still enabled: install_optional_skill_pack() and status_snapshot() depend on it.
    assert google.id in {d.id for d in registry.iter_enabled()}
    # But it must not mount tools — TOOL_SPECS does that, with the approver.
    assert google.mounts_tools is False

    slack = registry.get("slack")
    assert slack is not None and slack.mounts_tools is True, (
        "the opt-out must be per-descriptor, not a change to the default"
    )


def test_google_tools_keep_their_approver_after_capability_loop() -> None:
    """The last handler to win must be one that has an approver wired."""

    class _Approver:
        def require(self, action, summary, detail=""):  # noqa: D102
            return (True, "approved by test")

    approver = _Approver()
    seen: dict[str, object] = {}

    def _mount(reg: ToolRegistry, appr: object | None) -> None:
        """Stand-in for GoogleIntegrationHub.register_tools with a given approver."""
        schema = {"name": "google_send_email",
                  "input_schema": {"type": "object", "properties": {}}}

        def _handler() -> str:
            seen["approver"] = appr
            return "sent" if appr is not None else "blocked"

        reg.register(schema, _handler)

    reg = ToolRegistry()
    _mount(reg, approver)   # Path A — TOOL_SPECS, with approver
    _mount(reg, None)       # Path B — capability loop, no approver  (must not happen after fix)

    reg._tools["google_send_email"]()
    assert seen["approver"] is not None, (
        "surviving handler's approver is None — the approver-less capability "
        "mount overwrote the gated one"
    )
    assert len(reg._schemas) == 1, f"schema list grew to {len(reg._schemas)} entries"
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

The second test is deliberately a *mechanism* test against the real `ToolRegistry`, not a mocked
`GoogleIntegrationHub`: constructing a real hub instantiates nine services and an HTTP client, and
booting a real agent to reach the capability loop needs Google credentials you must not create.
The first test is the one that actually locks the fix; the second locks the invariant it protects.

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and both failed before the fix.
- [ ] `CapabilityDescriptor.mounts_tools` exists, defaults to `True`, and is `False` only on the
      `google` descriptor.
- [ ] The capability loop skips `register_tools` **and** `_register_capability_setup_stub` for any
      descriptor with `mounts_tools=False`.
- [ ] `capability_registry.iter_enabled()` still yields `google` — optional skill-pack install
      (`orchestrator.py:2772-2775`) and `status_snapshot()` are unchanged.
- [ ] `tests/test_google_tools_wire.py` (12 tests) still passes unmodified.
- [ ] **A real boot with Google configured was performed** and `google_*` names appear exactly
      once in `registry._schemas` — see §10.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11), describing this as an **availability** defect.

## 9. Out of scope — do NOT

- **Do not set the google descriptor's `factory=None` to disable Path B.** This is the obvious
  one-character fix and it is wrong. `CapabilityRegistry.instantiate` raises on a null factory
  (`orchestrator.py:191-192`: `raise RuntimeError(f"Capability '{capability_id}' has no runtime
  factory")`), the loop catches it at `:3334`, and you get a spurious `MCP_SERVER_FAILED` event
  plus a `setup_google_capability` stub registered for a working integration. Strictly worse than
  the bug.
- **Do not "fix" it by adding the approver to the capability factory instead.** It looks more
  general and it is the other plausible direction. It requires threading session-scoped state into
  a config-time registry, changes behaviour for Slack and Notion, and loses the
  `_google_client_id()` guard and the purpose-written stub. §5 already made this call.
- **Do not add the duplicate guard to `ToolRegistry.register` while you are in here.** That is
  [T-36-tool-registry-duplicate-guard.md](T-36-tool-registry-duplicate-guard.md), and the ordering
  is load-bearing: **if T-36 lands first, this misconfiguration becomes a hard boot crash for
  every fully-configured Google user.** One task, one change.
- **Do not clean up `google_tools.py:125-127`'s reach into `registry._tools` / `registry._groups`.**
  It is real (there is no public re-tagging API) and it belongs to
  [T-39-tool-groups-at-registration.md](T-39-tool-groups-at-registration.md).
- **Do not create, request, or hard-code Google OAuth credentials** to reproduce this. The §4
  proofs are sufficient and the §10 boot check is the operator's job, not the test suite's.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
uv run pytest tests/test_google_double_mount.py tests/test_google_tools_wire.py -q

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

**Then the check the test suite cannot do for you.** On a machine that already has Google
configured and connected (do not set one up for this — ask the maintainer to run it if you do not
have one), boot and count:

```bash
uv run python -c "
from hachi.gateway.orchestrator import boot_agent
s = boot_agent()
names = [x.get('name','') for x in s.loop.tool_registry._schemas]
g = [n for n in names if n.startswith('google_')]
import collections
dupes = {n: c for n, c in collections.Counter(g).items() if c > 1}
print('google tools:', len(g), '| duplicated:', dupes)
"
```

Expect `duplicated: {}`. Before the fix this reports 44 duplicated names. Report the **actual**
pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-88` is the highest
today; confirm before appending):

```markdown
### BB-N — Google tools mounted twice; the approver-less mount won, denying every destructive action

- **Symptom:** With Google fully configured AND connected, every destructive Google action
  (`send_email`, `trash_file`, …) returned *"No approver connected for this session; destructive
  action blocked."* — permanently, for exactly the users who completed setup. This is an
  **availability** defect, not a security bypass.
- **Root cause:** Two live mount paths in `boot_agent`. `TOOL_SPECS`
  (`gateway/orchestrator.py:3243-3250`) mounted the hub with the session `action_approver`; the
  capability loop (`:3325-3352`) then mounted it again from a `CapabilityDescriptor` factory
  (`:345-347`) that takes no approver, so `GoogleIntegrationHub.__init__` set
  `client.approver = None`. `ToolRegistry.register` overwrites handlers last-wins
  (`core/loop.py:188`), so the approver-less handler survived; `get_schemas` de-dupes first-wins
  (`:330-337`), so the schema came from the *other* mount. `client.require_approval` fails safe
  and denies when `approver is None` (`integrations/google/client.py:288-292`).
- **Fix:** Added `CapabilityDescriptor.mounts_tools` (default `True`), set `False` on the `google`
  descriptor, and made the capability loop skip both `register_tools` and the setup stub for such
  descriptors. `TOOL_SPECS` is now the single mount path and keeps the approver. The descriptor is
  still enabled, so skill-pack install and status reporting are unchanged.
- **Avoid:** One integration, one mount path. When adding an integration, check both `TOOL_SPECS`
  and the capability registry before adding a second. Two audit claims about this were wrong and
  were verified false: the Anthropic API never sees duplicates (`get_schemas` de-dupes), and a
  missing approver denies rather than permits.
- **Locked by:** `tests/test_google_double_mount.py` —
  `test_google_capability_does_not_mount_tools`,
  `test_google_tools_keep_their_approver_after_capability_loop`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **Sequencing is a hard constraint, not a preference.** T-36 makes a duplicate `register` raise.
  Land this first, or every fully-configured Google user's boot crashes. Both specs say so.
- **`register_google_tools` reads `.env`, not just the process environment.**
  `_google_client_id()` (`core/oauth.py`) checks a project or config-dir `.env` too
  (`google_tools.py:102-107`), so "I did not export `GOOGLE_CLIENT_ID`" does not mean Path A
  no-ops on your machine. `tests/test_google_tools_wire.py:111`
  (`test_mounts_hub_when_client_id_only_in_dotenv`) exists precisely because of this.
- **BB-2:** no `.env` autoload in the core/library import path; credentials resolve lazily at call
  time. Do not "simplify" the lazy `_google_client_id()` import at `google_tools.py:105` to a
  module-level one.
- **`ProcessSharedServices` is `None` before a session boots** (BB-6) — relevant if you try to
  reach the registry from outside `boot_agent`.
- **The two stubs have different names and do not collide:** `google_not_configured`
  (`google_tools.py:76`) vs `setup_google_capability` (`orchestrator.py:484`). Both would be
  registered today in the configured-but-unavailable state. The §5 fix removes the second.
</content>
</invoke>
