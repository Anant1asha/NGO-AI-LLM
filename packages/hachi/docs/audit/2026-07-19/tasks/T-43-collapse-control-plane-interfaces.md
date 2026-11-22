# T-43 · Collapse `GatewayControlPlane`'s 72 constructor callables into grouped interfaces

|  |  |
|---|---|
| **Source finding** | CF-2 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | [T-41](T-41-extract-in-process-runtime.md) — *do not start until it has landed* |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §9) |
| **Files you will touch** | `src/hachi/gateway/control_plane.py`, `src/hachi/gateway/in_process_runtime.py`, `src/hachi/cli/main.py`, `tests/test_gateway_control_plane.py`, `tests/test_gateway_new_endpoints.py` |

---

## 1. Brief

`GatewayControlPlane.__init__` takes **exactly 72 parameters** — 70 optional callables and 2
tunables — wired in a single 80-line call from `cli/main.py`. Every new endpoint adds a
parameter, a delegate method, and a wiring line. Replace the callable bag with a small set
of **protocol objects grouped by domain**, so adding an endpoint touches one protocol and one
implementation.

⚠️ **This is not a pass-through class. Read §3.3 before you plan anything.**

## 2. Why this matters

The 72-callable constructor is dependency inversion taken past the point of meaning: it
inverts *everything*, so it communicates *nothing*. You cannot tell from the signature which
handlers a working gateway actually needs — all 70 default to `None`, so a control plane
missing half its wiring constructs fine and fails at the first request. The `None`-defaulting
is also why the class needs a `_require_handler` guard on ~38 methods: the type system was
given no chance to help.

The payoff is concrete: **the 15 parameter groups in §3.4 are near-isomorphic with the 13
method groups of `_InProcessGatewayRuntime`** ([T-41](T-41-extract-in-process-runtime.md) §3.7)
— the same domains, wired twice, in two files, with two naming conventions. A
protocol-per-domain refactor collapses **both** call sites at once. That is the whole reason
this task is worth a week.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The class and its constructor

- `src/hachi/gateway/control_plane.py:85` — `class GatewayControlPlane:`; body runs to `:1422`
  (**1,338 lines**) in a **1,533-line** file.
- `:88-246` — `def __init__(self, *, …)`, **159 lines**, **72 parameters**.
- All 70 handler params are `Callable[…] | None = None`. The only two non-optional-shaped
  params are tunables, at `:167-168`:
  ```python
          max_active_sessions: int = 100,
          max_prompt_chars: int = 100_000,
  ```
- **81 methods** in the class (verified: `awk 'NR>=85 && NR<=1422' … | grep -cE "^    (async )?def "` → 81).

### 3.2 The single wiring call site

`src/hachi/cli/main.py:2950` — `def _build_gateway_control_plane(runtime, support) -> GatewayControlPlane:`
The one construction is at `:2963`, running to `:3043` with **exactly 72 kwargs**:

```python
    return GatewayControlPlane(
        readiness_probe=_gateway_readiness_probe,
        on_connect=runtime.register_connection if runtime else None,
        on_disconnect=runtime.close_connection if runtime else None,
        on_chat=runtime.chat if runtime else None,
        ...
        max_active_sessions=max_active_sessions,
        max_prompt_chars=max_prompt_chars,
    )
```

Note the `runtime … if runtime else None` idiom: the builder takes **two** runtimes
(`runtime` may be `None`; `support` never is), and the split is *per parameter*. That
distinction must survive the refactor — see §5 decision 3.

`_build_gateway_control_plane` has three callers: `cli/main.py:2935`, `:3978`, `:4077`.

### 3.3 ⚠️ "contains almost no behavior" is REFUTED

CF-2 says the class "contains almost no behavior". **That is wrong, and planning a
pass-through collapse on the strength of it would delete working code.**

Of the 80 non-`__init__` methods, roughly **42 carry real logic** and **38 are thin
`_require_handler(...)` delegations**. (A body-size heuristic classifies 37/43; the boundary
cases are judgement calls. Either way: about half the class is real.) The non-`__init__`
body is ~1,079 lines.

The methods with substance — verify each with Read before touching it:

| Method | Line | ~Lines | What it actually does |
|---|---|---|---|
| `create_session` | 284 | 85 | Input validation, protocol-version check, lock-guarded connection tracking, `max_active_sessions` enforcement with slot release on failed connect |
| `mcp_inventory` | 723 | 69 | Merges live + configured server views |
| `_synthesize_history_events` | 588 | 62 | Rebuilds an event stream from SQLite messages |
| `spend` | 926 | 47 | Aggregation |
| `read_session_events` | 542 | 45 | Cursor handling |
| `send_message` | 403 | 44 | `max_prompt_chars` enforcement, dispatch |
| `set_mcp_enabled` | 1063 | 43 | Live-aware enable with tombstone semantics |
| `delete_mcp_server` | 1107 | 43 | Ditto |
| `session_state` | 672 | 41 | Live/store reconciliation |
| `get_or_create_session` | 448 | 38 | |
| `interrupt` | 1325 | 34 | |
| `close_session` | 509 | 32 | |
| `session_transcript` | 1151 | 31 | |
| `validate_routing` | 1225 | 30 | |
| `rollback_routing` | 1256 | 25 | |
| `readiness` | 261 | 22 | |
| `register_mcp_server` | 1041 | 21 | |
| `complete_chat` | 487 | 21 | |
| `_is_session_in_store` | 651 | 20 | |

**Accurate framing: a thin façade over ~38 admin operations, bolted onto a genuine
session-lifecycle service.** The façade half is the problem; the service half is the product.

**A collapse must PRESERVE the ~42 stateful methods verbatim.** They are the only place
session limits, prompt limits, protocol versioning, and connection accounting are enforced.

Regenerate the size table:

```bash
awk 'NR>=85 && NR<=1422' src/hachi/gateway/control_plane.py \
  | grep -nE "^    (async )?def " | awk -F'[:(]' '{print $1+84, $2}' \
  | sed 's/    def //;s/    async def //' \
  | awk 'NR>1{print prev_name": "prev_line" ("$1-prev_line-1"L)"} {prev_line=$1; prev_name=$2}' \
  | sort -t'(' -k2 -rn
```

### 3.4 The 15 parameter groups — the interface plan

Complete, in declaration order. This is the target decomposition.

| # | Group | N | Parameters |
|---|---|---|---|
| **I** | Session lifecycle & transport | 11 | `readiness_probe`, `on_connect`, `on_disconnect`, `on_chat`, `read_events`, `get_session_state`, `get_recent_sessions`, `get_session_messages`, `delete_session`, `get_runtime_events`, `on_interrupt` |
| **II** | Runtime observability | 5 | `get_mcp_inventory`, `get_active_jobs`, `get_failed_jobs`, `get_permission_audit`, `get_subagent_reports` |
| **III** | Scheduling | 4 | `list_schedules`, `cancel_schedule`, `toggle_schedule`, `run_schedule_now` |
| **IV** | Config & setup | 9 | `get_config`, `update_provider`, `validate_provider`, `update_permissions`, `update_memory`, `list_models`, `get_setup_state`, `apply_setup`, `update_limits` |
| **V** | Capabilities | 2 | `get_capabilities`, `set_capability_enabled` |
| **VI** | Skills / kennel | 4 | `get_skills`, `get_og_graph`, `get_kennel`, `add_skill` |
| **VII** | Memory | 4 | `get_memory`, `get_memory_recall`, `add_memory_fact`, `delete_memory_fact` |
| **VIII** | Authoring | 6 | `get_authoring_targets`, `get_authoring_target`, `authoring_generate`, `authoring_apply`, `authoring_revert`, `authoring_save_source` |
| **IX** | Spend | 2 | `get_spend`, `get_spend_daily` |
| **X** | Permission allowlists | 5 | `add_allowed_folder`, `add_allowed_command`, `remove_allowed_folder`, `remove_allowed_command`, `add_always_allow` |
| **XI** | MCP admin | 3 | `register_mcp_server`, `set_mcp_enabled`, `delete_mcp_server` |
| **XII** | Providers & routing | 11 | `list_providers`, `add_or_update_provider`, `remove_provider`, `get_routing`, `set_routing`, `validate_routing`, `rollback_routing`, `get_routing_audit`, `test_provider_connection`, `list_all_models`, `probe_provider` |
| **XIII** | Secrets | 3 | `store_secret`, `list_secret_names`, `delete_secret` |
| **XIV** | Misc | 1 | `reload_search_tools` |
| **XV** | Tunables | 2 | `max_active_sessions`, `max_prompt_chars` |

Total: 11+5+4+9+2+4+4+6+2+5+3+11+3+1+2 = **72**. ✓

### 3.5 The isomorphism with T-41 — the reason to sequence after it

| T-43 param group | T-41 method group ([T-41](T-41-extract-in-process-runtime.md) §3.7) |
|---|---|
| I Session lifecycle & transport (11) | 1 Session lifecycle + locking (15) |
| II Runtime observability (5) | 2 Runtime observability read-models (6) |
| III Scheduling (4) | 3 Scheduling (4) |
| IV Config & setup (9) + V Capabilities (2) | 4 Config/provider/setup (10) |
| VI Skills/kennel (4) + VII Memory (4) | 5 Skills/memory/OG (7) + 10 Kennel (2) |
| VIII Authoring (6) | 6 Authoring (7) |
| IX Spend (2) | 7 Spend (2) |
| X Permission allowlists (5) | 8 Permissions/limits (6) |
| XI MCP admin (3) | 9 MCP admin (5) |
| XII Providers & routing (11) | 13 Providers/routing admin (11) |
| XIII Secrets (3) | 11 Secrets (3) |
| XIV Misc (1) | 12 Search (1) |

The counts differ only where the runtime keeps a private helper the control plane never sees
(`_standalone_og_engine`, `_mcp_live_server_names`, `_mcp_node_names`,
`_resolve_authoring_target_path`) or where the control plane never got a delegate. **Nine of
twelve groups are an exact or near-exact match.** Define the protocols once and both files
implement/consume the same names.

### 3.6 Tests that bind to the current shape

- `tests/test_gateway_control_plane.py` — **18 tests**, the primary contract.
- `tests/test_gateway_new_endpoints.py` — 6 `hachi.cli.main.*` patch strings.
- Any test constructing `GatewayControlPlane(...)` with a subset of kwargs relies on the
  `= None` defaults; those constructions must move to protocol stubs.

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor with no runtime symptom.** The control plane works. Do not invent
a repro. Here is how to see the problem:

```bash
# 1. Count the constructor parameters.
awk 'NR>=88 && NR<=246' src/hachi/gateway/control_plane.py | grep -cE "^        [a-z_]+:"   # 72

# 2. Count the kwargs at the single wiring site.
awk 'NR>=2963 && NR<=3043' src/hachi/cli/main.py | grep -cE "^        [a-z_]+="             # 72

# 3. Count the guard that exists only because every param defaults to None.
grep -c "_require_handler" src/hachi/gateway/control_plane.py                                # 41

# 4. See the four-place cost of one endpoint: pick any handler and follow it.
grep -rn "get_spend_daily" src/hachi/ | grep -v test
```

**You will see now:** step 4 prints four sites for one endpoint — the runtime method, the
constructor parameter, the delegate method, and the wiring line.
**You should see after the fix:** two sites — one protocol member and one implementation —
and step 1 reports a single-digit constructor arity.

## 5. What "fixed" looks like

Protocols in `gateway/`, one per domain, consumed positionally by name.

```python
# src/hachi/gateway/ports.py (new)
"""Domain ports the gateway control plane consumes.

One protocol per domain, mirroring the runtime's method groups
(see T-41 §3.7). Adding an endpoint means adding ONE member here
and ONE implementation — not four wiring sites.
"""

from __future__ import annotations

from typing import Any, Protocol


class SessionPort(Protocol):          # group I  — 11 members
    def register_connection(self, session_id: str, request: ConnectRequest) -> None: ...
    def close_connection(self, session_id: str) -> None: ...
    def chat(self, session_id: str, text: str) -> str: ...
    ...


class ObservabilityPort(Protocol):    # group II  — 5 members
    ...


class SchedulingPort(Protocol):       # group III — 4 members
    ...

# … IV–XIV …
```

```python
# control_plane.py — after
    def __init__(
        self,
        *,
        sessions: SessionPort | None = None,
        observability: ObservabilityPort | None = None,
        scheduling: SchedulingPort | None = None,
        config: ConfigPort | None = None,
        capabilities: CapabilityPort | None = None,
        skills: SkillsPort | None = None,
        memory: MemoryPort | None = None,
        authoring: AuthoringPort | None = None,
        spend: SpendPort | None = None,
        allowlists: AllowlistPort | None = None,
        mcp: MCPAdminPort | None = None,
        providers: ProviderRoutingPort | None = None,
        secrets: SecretsPort | None = None,
        search: SearchPort | None = None,
        max_active_sessions: int = 100,
        max_prompt_chars: int = 100_000,
    ) -> None:
```

**16 parameters instead of 72.** `_InProcessGatewayRuntime` satisfies all fourteen ports
structurally — its method groups already *are* these ports (§3.5) — so
`_build_gateway_control_plane` collapses to roughly:

```python
    return GatewayControlPlane(
        sessions=runtime,
        observability=runtime,
        scheduling=support,
        ...
        max_active_sessions=max_active_sessions,
        max_prompt_chars=max_prompt_chars,
    )
```

**Decisions already made — do not re-litigate:**

1. **`typing.Protocol`, structural, not ABCs.** No inheritance changes to the runtime class.
   No new dependency.
2. **Fourteen ports + two tunables. Do not merge to "3–4 grouped interfaces"** as CF-2
   suggests — that produces four 18-member god-protocols and loses the isomorphism with
   T-41's groups, which is the entire leverage. Fourteen is the number the code already has.
3. **The `runtime` vs `support` split survives at the PORT level, not the method level.**
   Today, session-ish params get `runtime … if runtime else None` while admin params get
   `support.…` unconditionally. Map that to: `sessions=runtime` (nullable),
   everything else `=support`. Read `cli/main.py:2963-3043` line by line and record which
   side each of the 72 kwargs is on **before** you write the builder — this is the one place
   a silent behaviour change can hide.
4. **Ports stay `| None = None` for now.** Making them required is a second, separable
   change; doing it here would force every test that builds a partial control plane to
   supply fourteen stubs in the same diff.
5. **`_require_handler` stays.** With ports still nullable, the guard is still load-bearing.
   Its *argument* changes from a callable to `port.method`.
6. **The ~42 stateful methods do not change at all** (§3.3). Only the lines where they
   reach for a handler change: `self._on_chat(...)` → `self._sessions.chat(...)`.

## 6. Steps

**Six commits: one per wave of ports, smallest-blast-radius first. Each is independently
green. Do NOT do this in one diff.**

### Commit 1 — characterization tests (no source change)

1. Write the tests from §7. They must pass against today's code.
2. Record the full-suite baseline counts.

### Commit 2 — introduce the ports, change nothing

3. Create `src/hachi/gateway/ports.py` with all 14 `Protocol` classes and their 70 members,
   transcribed from §3.4 with signatures copied from the `Callable[…]` annotations at
   `control_plane.py:88-246`. Nothing imports it yet.
4. Add a test asserting `_InProcessGatewayRuntime` satisfies every port
   (`isinstance(runtime, SessionPort)` with `@runtime_checkable`, or a `mypy`-only
   assertion — prefer the runtime check, it survives the mypy gate's current exclusions).
   ⚠️ **If a port member does not exist on the runtime, you have transcribed a name wrong or
   found a delegate with no backing method. Investigate; do not "fix" it by adding a method.**

### Commits 3–6 — migrate ports in four waves

Order chosen so the risky group is last and each wave is reviewable.

- **Commit 3 — the leaf admin ports (26 params):** XIII Secrets (3), XIV Misc (1),
  IX Spend (2), III Scheduling (4), X Allowlists (5), XI MCP admin (3), V Capabilities (2),
  VI Skills/kennel (4), II Observability (5)… wait — recount before you split; keep each
  commit under ~30 params and finish the wave you started.
- **Commit 4 — Providers & routing (11) + Authoring (6) + Memory (4).**
- **Commit 5 — Config & setup (9).**
- **Commit 6 — Session lifecycle & transport (11) + tunables.** ← the ~42 stateful methods
  live here; this commit deserves its own review pass.

For each wave:

  a. Add the port parameter to `__init__`; keep the old individual params **in place** and
     make the port take precedence if supplied. The class temporarily accepts both.
  b. Switch that group's delegate methods to read from the port.
  c. Switch `_build_gateway_control_plane` to pass the port instead of that group's kwargs;
     delete those kwargs from the call.
  d. Delete the now-unused individual params from `__init__`.
  e. Update the affected tests in `tests/test_gateway_control_plane.py`.
  f. Full suite. Counts must match the commit-1 baseline.

The both-accepted intermediate in (a) is what keeps every commit green. **Do not skip it and
do not leave it in** — (d) removes it in the same commit.

### After the last wave

7. Confirm `awk 'NR>=88 && NR<=110' src/hachi/gateway/control_plane.py | grep -cE "^        [a-z_]+:"` reports 16.
8. Confirm the ~42 stateful methods are byte-identical apart from handler-access lines:
   ```bash
   git diff main -- src/hachi/gateway/control_plane.py | grep "^[-+]" | grep -v "_require_handler\|self\._" | head -50
   ```
   Anything else in that output is scope creep.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug, so the instrument is a **characterization test**: pin the
behaviour of the ~42 stateful methods *before* you touch the constructor, so the collapse is
provably behaviour-neutral.

- **File:** `tests/test_control_plane_characterization.py` (new)
- **Test names:** `test_session_limit_is_enforced_at_the_control_plane`,
  `test_prompt_length_limit_is_enforced`, `test_failed_connect_releases_the_session_slot`,
  `test_runtime_satisfies_every_port`
- **They must assert:** real observed behaviour of the stateful methods — the limits, the
  slot accounting, the protocol-version rejection — not a mock's return value.
- **The first three PASS before the refactor** (that is what characterization means) **and
  must still pass after.** `test_runtime_satisfies_every_port` **MUST FAIL before** with
  `ModuleNotFoundError: No module named 'hachi.gateway.ports'`.

```python
# sketch — adapt to the repo's existing fixtures
import pytest


def test_session_limit_is_enforced_at_the_control_plane() -> None:
    """create_session must reject beyond max_active_sessions (control_plane.py:315).

    Characterization: this behaviour lives ONLY here. If the port collapse
    drops it, no other layer catches it.
    """
    from hachi.gateway.control_plane import GatewayControlPlane, GatewayProtocolError

    plane = GatewayControlPlane(max_active_sessions=2, on_connect=lambda sid, req: None)
    plane.create_session(_connect_request("a"))
    plane.create_session(_connect_request("b"))
    with pytest.raises(GatewayProtocolError, match="Maximum active sessions reached"):
        plane.create_session(_connect_request("c"))


def test_failed_connect_releases_the_session_slot() -> None:
    """A raising on_connect must NOT consume a slot (control_plane.py:334).

    Guards the subtlest behaviour in the class — trivially lost in a rewrite.
    """
    from hachi.gateway.control_plane import GatewayControlPlane

    calls = {"n": 0}

    def _flaky(sid: str, req) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")

    plane = GatewayControlPlane(max_active_sessions=1, on_connect=_flaky)
    with pytest.raises(RuntimeError):
        plane.create_session(_connect_request("a"))
    plane.create_session(_connect_request("b"))   # slot was released


def test_prompt_length_limit_is_enforced() -> None:
    """send_message must reject over max_prompt_chars (control_plane.py:431)."""
    ...


def test_runtime_satisfies_every_port() -> None:
    """_InProcessGatewayRuntime must structurally satisfy all 14 ports.

    FAILS before T-43 with ModuleNotFoundError (hachi.gateway.ports).
    """
    from hachi.gateway import ports
    from hachi.gateway.in_process_runtime import _InProcessGatewayRuntime

    runtime = _InProcessGatewayRuntime()
    missing: dict[str, list[str]] = {}
    for name in [n for n in dir(ports) if n.endswith("Port")]:
        proto = getattr(ports, name)
        absent = [m for m in proto.__protocol_attrs__ if not hasattr(runtime, m)]
        if absent:
            missing[name] = absent
    assert missing == {}, f"runtime does not satisfy: {missing}"
```

> If `test_runtime_satisfies_every_port` passes before you write `ports.py`, you are
> importing the wrong module. Do not proceed.

## 8. Acceptance criteria

- [ ] The characterization tests from §7 exist; `test_runtime_satisfies_every_port` failed
      before the fix with `ModuleNotFoundError`.
- [ ] `GatewayControlPlane.__init__` has **16** parameters (14 ports + 2 tunables).
- [ ] `src/hachi/gateway/ports.py` defines 14 protocols covering all **70** former handler
      params — none dropped. Cross-check against the §3.4 table, name by name.
- [ ] The `_build_gateway_control_plane` call at `cli/main.py:2963` passes 16 kwargs, and
      the `runtime` vs `support` assignment matches the pre-refactor mapping you recorded in
      §5 decision 3. **Attach that mapping to the PR.**
- [ ] `git diff` on the ~42 stateful methods shows changes *only* on handler-access lines.
      `create_session`, `send_message`, `session_state`, `mcp_inventory`,
      `_synthesize_history_events`, `set_mcp_enabled`, `delete_mcp_server` retain their
      logic in full.
- [ ] All 18 tests in `tests/test_gateway_control_plane.py` pass without assertion changes
      (constructor calls may change; assertions may not).
- [ ] Six commits, each green on its own.
- [ ] Full-suite counts identical to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving code.** Primary boundary. In particular: do not
  "simplify" `create_session`, do not change what `max_active_sessions` counts, do not alter
  the failed-connect slot release, do not touch the protocol-version check.
- **Do not treat the class as a pass-through** (§3.3). If your plan starts with "since it has
  no logic…", stop and re-read §3.3.
- Do not merge the 14 ports down to 3–4 (§5 decision 2).
- Do not make ports required in this task (§5 decision 4).
- Do not delete `_require_handler` (§5 decision 5).
- Do not change any HTTP route, request shape, or response shape. If a response body changes,
  **BB-4 applies** and you have exceeded scope.
- Do not rename handler methods on `_InProcessGatewayRuntime` to match port names — define
  the port members to match the *existing* method names. A rename here churns T-41's freshly
  re-pointed test patch strings a second time.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. `typing.Protocol` is stdlib.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop, after EVERY wave
uv run python scripts/preflight.py           # before you call it done
uv run lint-imports                          # new gateway/ports.py must not break layering
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — a 72-callable constructor hid which handlers a working gateway requires

- **Symptom:** `GatewayControlPlane.__init__` took 72 params, 70 of them
  `Callable | None = None`. A control plane missing half its wiring constructed successfully
  and failed at the first request; ~38 methods needed a `_require_handler` guard purely to
  compensate.
- **Root cause:** Per-endpoint dependency inversion. Each new endpoint added a parameter, a
  delegate, and a wiring line, so the constructor grew monotonically and the type system was
  never given a chance to express the requirement.
- **Fix:** Collapsed the 70 callables into 14 domain `Protocol` ports mirroring the runtime's
  own method groups; the runtime satisfies them structurally.
- **Avoid:** When a constructor's optional-callable count passes ~10, the parameters are a
  missing interface. Group by domain and pass objects.
- **Locked by:** `tests/test_control_plane_characterization.py` — `test_runtime_satisfies_every_port`
```

## 12. Known traps

- **Doing this before [T-41](T-41-extract-in-process-runtime.md).** You would define ports
  against a class inside `cli/main.py`, then move it. Wait.
- **The `runtime` vs `support` split (§5 decision 3).** The single most likely silent
  behaviour change. Some kwargs are `runtime.X if runtime else None`; others are
  `support.X` unconditionally. Collapsing both to one port object flattens that distinction.
  Record the mapping before you start.
- **`__protocol_attrs__` is a CPython implementation detail.** The §7 sketch uses it for a
  compact check; if it is unavailable on the target interpreter, enumerate the members
  explicitly instead of dropping the assertion.
- **`@runtime_checkable` only checks method *presence*, not signatures.** A port satisfied at
  runtime can still be wired to a method with the wrong arity. The mypy gate is your second
  net — run it (`uv run python scripts/preflight.py --quick` includes it).
- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend API
  types, or CI fails. This task should change no routes; if it does, you have overshot.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — several control-plane
  methods `getattr` around this. Preserve those calls verbatim.
