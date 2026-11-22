# T-20 · Register channel and schedule sessions through the governed runtime

|  |  |
|---|---|
| **Source finding** | CF-4(d) — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md). **Its stated consequence is wrong** — see [CORRECTIONS.md](CORRECTIONS.md) §1 and §11, and §2 below |
| **Severity** | **P1** |
| **Wave** | 1 (gate-blocking, before public v1) — but the *clean* version waits on [T-41](T-41-extract-in-process-runtime.md) (Wave 2); read §5 |
| **Depends on** | [T-01](T-01-approver-selection-dead-branch.md) — *without it the governed path is no more governed than the ungoverned one* |
| **Blocks** | nothing |
| **Effort** | ~1 day (interim) · ~3 days (clean, post-CF-2) |
| **Difficulty** | High (needs a scoping decision — read §5 first) |
| **Files you will touch** | `src/hachi/cli/commands/channel.py`, `src/hachi/cli/commands/schedule.py`, `src/hachi/cli/main.py`, `tests/` (new), `docs/bug-bank.md`. **Not** `src/hachi/channels/runner.py` — it already has the seam you need |

---

## 1. Brief

Telegram/WhatsApp channels and both `hachi schedule` run commands call `boot_agent()`
directly, outside `GatewayControlPlane`. They keep their own private agent maps that the
gateway knows nothing about. When you are done, a session created by a channel or a
schedule is registered the same way a web session is — so it appears in `/sessions`, its
runtime events reach the audit and spend read models, and it gets the same approver as
every other governed session.

## 2. Why this matters — and what the review got wrong

> **The review says these paths park "an approval in an in-process registry no surface
> can reach". That is not what happens.**
> Per [CORRECTIONS.md](CORRECTIONS.md) §1: no approval is created *at all*. Channels and
> schedules get `PolicyApprover` — but so does the gateway path today, for the separate
> reason fixed in [T-01](T-01-approver-selection-dead-branch.md). There is no
> registry-orphan bug to fix here. Do not go looking for one.

The **verified** consequence is invisibility. Every gateway read model resolves through
`_InProcessGatewayRuntime._agents` — for example `recent_sessions`
(`src/hachi/cli/main.py:455-459`), `permission_audit` (`:530-535`), `subagent_reports`
(`:537-543`) all begin with:

```python
        with self._agents_lock:
            agent = next(iter(self._agents.values()), None)
```

A channel or schedule session lives in a *different* dict (`GatewaySessionRunner._agents`,
`src/hachi/channels/runner.py:22`) or in a bare local (`agent = boot_agent()` in
`schedule.py`). So a Telegram conversation and a cron-fired task are, from the product's
own governance surfaces, **invisible**: not in the session list, not in the audit view,
not in spend. And once [T-01](T-01-approver-selection-dead-branch.md) lands and gateway
sessions become genuinely approvable, these two paths will be the only ones left that
are *not* — which is the worse end state, because the gap becomes silent rather than
uniform.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Channels — `src/hachi/channels/runner.py`

`:14` is the **import**, not the call site (the review cites it as the call site):

```python
from hachi.gateway.orchestrator import AgentSession, boot_agent
```

The real binding is `:20`, and the call is `:29`:

```python
class GatewaySessionRunner:
    """Lazily boot one AgentSession per session key and run turns on it."""

    def __init__(self, boot: Callable[[], AgentSession] = boot_agent):
        self._boot = boot
        self._agents: dict[str, AgentSession] = {}
        self._lock = threading.Lock()

    def _agent_for(self, session_key: str) -> AgentSession:
        with self._lock:
            agent = self._agents.get(session_key)
            if agent is None:
                agent = self._boot()
                self._agents[session_key] = agent
            return agent
```

**`boot` is already an injectable seam.** No signature change is needed in this file.
`self._agents` at `:22` is the private map parallel to the gateway's.

Two construction sites, both in `src/hachi/cli/commands/channel.py`:

```python
    runner = GatewaySessionRunner()      # :114  — telegram
    runner = GatewaySessionRunner()      # :162  — whatsapp
```

### 3.2 Schedules — `src/hachi/cli/commands/schedule.py`, **two** sites

`:169`, in `schedule_run_due`:

```python
    agent = boot_agent()
    try:

        def fire(schedule):
            console.print(f"[cyan]Running[/cyan] '{schedule.name}': {schedule.task}")
            reply = agent.chat(schedule.task)
            _deliver_schedule_result(schedule, reply)
```

`:205`, in `schedule_run_now` — **undocumented in the review**:

```python
    console.print(f"[cyan]Running[/cyan] '{schedule.name}': {schedule.task}")
    agent = boot_agent()
    try:
        reply = agent.chat(schedule.task)
        _deliver_schedule_result(schedule, reply)
```

Neither has an injection seam. Both need redirecting.

### 3.3 The governed path — name every symbol

1. **`GatewayControlPlane.create_session`** — `src/hachi/gateway/control_plane.py:284-292`

   ```python
   def create_session(
       self,
       *,
       client_id: str,
       surface: str,
       capabilities: list[str] | tuple[str, ...] | None = None,
       protocol_version: str = PROTOCOL_VERSION,
   ) -> dict[str, Any]:
   ```

2. **Registers under lock** — `control_plane.py:314-327`

   ```python
           with self._connections_lock:
               if len(self._connections) >= self._max_active_sessions:
                   raise GatewayProtocolError(
                       f"Maximum active sessions reached ({self._max_active_sessions})."
                   )
               session_id = str(uuid.uuid4())
               self._connections[session_id] = {
                   "client_id": req.client_id,
                   "surface": req.surface,
                   "capabilities": list(req.capabilities),
                   "connected_at": _now_iso(),
                   # C1: store owner hash at creation time; None means no-auth / legacy.
                   "owner_token_hash": None,
               }
   ```

3. **Fires the connect hook** — `control_plane.py:329-337`

   ```python
           if self._on_connect is not None:
               try:
                   self._on_connect(session_id, req)
               except Exception:
                   # Boot (agent/MCP/DB init) failed — release the registered session
                   # slot so repeated failed connects don't exhaust max_active_sessions.
                   with self._connections_lock:
                       self._connections.pop(session_id, None)
                   raise
   ```

4. **`_InProcessGatewayRuntime.register_connection`** — `src/hachi/cli/main.py:292-326`;
   the registration is `:313-320`:

   ```python
           agent = self._boot_session_agent(session_id, resume_session_id=resume_session_id)
           replaced_agent: AgentSession | None = None
           with self._agents_lock:
               replaced_agent = self._agents.get(session_id)
               self._agents[session_id] = agent
               # Ensure a per-session chat lock exists (idempotent for re-registrations).
               if session_id not in self._chat_locks:
                   self._chat_locks[session_id] = threading.Lock()
   ```

5. **`_InProcessGatewayRuntime._boot_session_agent`** — `src/hachi/cli/main.py:263-283`,
   which is where `boot_agent` is finally called (`:276`).

6. **Wired together** in `_build_gateway_control_plane` — `src/hachi/cli/main.py:2965`:

   ```python
           on_connect=runtime.register_connection if runtime else None,
   ```

### 3.4 The runtime handle these paths would need — `src/hachi/cli/main.py:2710`

```python
_ACTIVE_RUNTIME: "_InProcessGatewayRuntime | None" = None
```

set at `:2931-2932` and `:3974-3975`. There is already **one precedent** for reaching it
from outside: `src/hachi/core/runtime/resume.py:124-135`

```python
        import hachi.cli.main as _main_mod

        runtime = getattr(_main_mod, "_ACTIVE_RUNTIME", None)
```

That edge is the explicitly-frozen `hachi.core.runtime.resume -> hachi.cli.main` seam in
`pyproject.toml`'s import-linter contract. Note the shape; §5 discusses whether to add a
second one.

## 4. Reproduce the failure

Reproducible without a bot token or a cron job — the invisibility is structural.

```bash
# 1. Every ungoverned boot site. Expect: channels/runner.py:20 (+29),
#    schedule.py:169, schedule.py:205 — none reaching the control plane.
rg -n "boot_agent" src/hachi/channels/ src/hachi/cli/commands/

# 2. The parallel agent map.
rg -n "_agents" src/hachi/channels/runner.py

# 3. Every gateway read model resolves through the OTHER map.
rg -n -A 2 "with self._agents_lock:" src/hachi/cli/main.py | head -40

# 4. The governed entry point nothing in (1) calls.
rg -n "create_session|register_connection" src/hachi/ --type py
```

**You will see now:** (1) four boot sites outside the control plane; (2) a private dict
in `runner.py`; (3) every read model iterating `_InProcessGatewayRuntime._agents`;
(4) `create_session` called only from `gateway/fastapi_app.py`.

**You should see after the fix:** (1) the channel and schedule paths obtain their agent
through the runtime rather than calling `boot_agent` themselves, and (4) shows the new
call sites.

**Manual confirmation** (needs a Telegram bot token — skip if you do not have one): run
`hachi serve` in one terminal and `hachi channel telegram` in another, send the bot a
message, then `curl -H "Authorization: Bearer $HACHI_GATEWAY_TOKEN"
http://127.0.0.1:8787/sessions`. Today the channel conversation is absent.

## 5. What "fixed" looks like

> ### DECISION REQUIRED — how far to go in Wave 1
>
> The clean answer is the CF-2 extraction: pull the runtime out of `cli/main.py` (it is
> a 2,358-line class living at the CLI edge) into a real service that `channels/` and
> `cli/commands/` can depend on without a layering violation. **That is
> [T-41](T-41-extract-in-process-runtime.md), a Wave-2 task, and it is out of scope
> here.** Choose one of:
>
> **(a) Interim: add ONE public method on `_InProcessGatewayRuntime` and route both
> paths through it when a gateway is live — RECOMMENDED for Wave 1.**
>
> ```python
> # src/hachi/cli/main.py, on _InProcessGatewayRuntime
> def boot_registered_session(self, *, client_id: str, surface: str) -> AgentSession:
>     """Boot an agent registered in the gateway's session map (channels, schedules)."""
> ```
>
> Channels pass it as the existing `boot=` seam (`runner.py:20`); schedules call it
> directly. When `_ACTIVE_RUNTIME` is `None` (no gateway in this process — the common
> case for `hachi schedule run-due` under cron), fall back to today's `boot_agent()`
> **and log a WARNING naming the degradation**, rather than failing.
> *For:* small, testable, reuses the existing seam, no new import direction beyond the
> one `resume.py` already has (§3.4). *Against:* it deepens the `cli.main` god-class
> that CF-2 wants to dissolve — an explicitly accepted, documented interim.
>
> **(b) Minimal: leave the boot paths alone, but make them declare their surface** so
> they at least get the right approver from
> [T-01](T-01-approver-selection-dead-branch.md).
> *For:* two-line diff, zero layering risk. *Against:* does **not** fix the verified
> consequence (invisibility to `/sessions`/audit/spend), which is the whole point of
> this task. Only choose this if (a) is blocked.
>
> **(c) Block instead of govern:** refuse gated actions on these paths with an explicit
> error, as the review's remediation list suggests
> ([ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) line 269).
> *For:* honest and very small. *Against:* it makes Telegram strictly less capable than
> the web UI forever, and it still leaves the sessions invisible.
>
> **Recommendation: (a), with the (b) surface-declaration folded in** so the fallback
> path is at least labelled. Say in the commit message that this is a documented
> interim pending the CF-2 extraction.

Target state under (a):

1. `_InProcessGatewayRuntime.boot_registered_session(client_id, surface)` calls
   `self.register_connection(...)`-equivalent bookkeeping (or `create_session` via a
   control-plane handle if one is reachable) and returns the registered `AgentSession`.
   It must reuse the existing `_agents_lock` / `_chat_locks` bookkeeping at
   `cli/main.py:315-320` rather than duplicating it.
2. `channel.py:114` and `:162` construct the runner with the governed boot:

   ```python
   runner = GatewaySessionRunner(boot=_governed_channel_boot)
   ```

   where `_governed_channel_boot` resolves `_ACTIVE_RUNTIME`, calls
   `boot_registered_session(client_id="telegram", surface="channel")`, and falls back
   with a WARNING when no gateway is live. **`channels/runner.py` is unchanged.**
3. `schedule.py:169` and `:205` call the same helper with
   `client_id="scheduler", surface="schedule"`.
4. Sessions created this way appear in `GET /sessions` with their real `surface`, and
   their events reach `permission_audit` / spend like any web session.
5. The fallback path is **loud**: one WARNING per boot naming exactly what is degraded
   ("session not registered with the gateway — it will not appear in /sessions or the
   audit view"), not a DEBUG line. (Compare BB-71: a router fallback swallowed at DEBUG
   is on the bug-bank precisely for this.)

## 6. Steps

1. Write the regression test from §7 and watch it **fail**.
2. Add `boot_registered_session` to `_InProcessGatewayRuntime` (`cli/main.py`, next to
   `_boot_session_agent` at `:263` and `register_connection` at `:292`). Reuse the
   existing lock/bookkeeping; do not copy-paste it.
3. Add a small module-level helper that resolves `_ACTIVE_RUNTIME` and falls back with a
   WARNING. Follow the `resume.py:124-135` shape exactly.
4. Point `channel.py:114` and `:162` at it via `GatewaySessionRunner(boot=…)`.
5. Point `schedule.py:169` and `:205` at it. **Both** — the second one is easy to miss.
6. Verify `channels/runner.py` is untouched in your diff.
7. Run the full gate.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_governed_session_entry_points.py` (**new**)
- **Test names:**
  `test_channel_runner_boots_through_the_gateway_runtime`,
  `test_schedule_run_due_boots_through_the_gateway_runtime`,
  `test_schedule_run_now_boots_through_the_gateway_runtime`
- **It must assert:** the real, observed registration — that after the channel/schedule
  path boots a session, the agent is **present in `_InProcessGatewayRuntime._agents`**
  (i.e. reachable by the read models), not merely that some function was called. A
  call-spy alone would pass against a stub that registers nothing.
- **It must FAIL before your fix** with:
  `AssertionError: assert 0 == 1` — `runtime._agents` is empty because the path called
  `boot_agent` directly.

```python
# sketch — adapt to the repo's existing fixtures
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def live_runtime(monkeypatch: pytest.MonkeyPatch):
    """An _InProcessGatewayRuntime installed as the process-active runtime."""
    from hachi.cli import main as cli_main

    monkeypatch.setattr(cli_main, "boot_agent", lambda *a, **kw: MagicMock())
    runtime = cli_main._InProcessGatewayRuntime()
    monkeypatch.setattr(cli_main, "_ACTIVE_RUNTIME", runtime)
    return runtime


def test_channel_runner_boots_through_the_gateway_runtime(live_runtime, monkeypatch) -> None:
    """A Telegram/WhatsApp session must be visible to /sessions and the audit view.

    Regression: GatewaySessionRunner booted into its OWN private _agents dict, so
    channel conversations were invisible to every gateway read model.
    """
    from hachi.cli.commands import channel as channel_cmd

    runner = channel_cmd._build_channel_runner()   # the helper introduced by this task
    runner("tg:12345", "hello")                    # drives _agent_for -> boot

    assert len(live_runtime._agents) == 1


def test_schedule_run_now_boots_through_the_gateway_runtime(live_runtime, monkeypatch) -> None:
    """The SECOND schedule boot site (schedule_run_now) is easy to miss — pin it."""
    ...
    assert len(live_runtime._agents) == 1


def test_falls_back_loudly_when_no_gateway_is_active(monkeypatch, caplog) -> None:
    """Cron-invoked `hachi schedule run-due` still works, but says what it lost."""
    from hachi.cli import main as cli_main

    monkeypatch.setattr(cli_main, "_ACTIVE_RUNTIME", None)
    ...
    assert any(r.levelname == "WARNING" for r in caplog.records)
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> Likely cause: you asserted on a mock call rather than on `runtime._agents`.

## 8. Acceptance criteria

- [ ] The regression tests from §7 exist and failed before the fix with an empty `runtime._agents`.
- [ ] `rg -n "boot_agent" src/hachi/cli/commands/schedule.py` shows **both** former sites (`:169`, `:205`) now routed through the governed helper.
- [ ] `git diff --stat src/hachi/channels/runner.py` is **empty** — the seam was used, not modified.
- [ ] With a gateway live, a channel session and a schedule session appear in `GET /sessions` with `surface` set to `"channel"` / `"schedule"`.
- [ ] With no gateway live, both paths still work and emit exactly one **WARNING** naming the degradation.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts), **including `lint-imports`** — see §12.
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not start the CF-2 runtime extraction.** Moving `_InProcessGatewayRuntime` out of
  `cli/main.py` is the correct fix and it has its own spec —
  [T-41](T-41-extract-in-process-runtime.md), Wave 2, ~1 week. The gravitational pull
  here is strong — you will be adding a method to a 2,358-line class and thinking
  "I should just move it". **Do not.** Note it, add the interim, move on.
- **Do not change `channels/runner.py`.** The `boot=` parameter at `:20` exists exactly
  for this. If your diff touches that file you have taken a longer route than needed.
- **Do not widen `boot_agent`'s signature further.** [T-01](T-01-approver-selection-dead-branch.md)
  adds `approval_surface`; adding a second orthogonal parameter here is how the
  1,137-line boot function got that way.
- **Do not add session *persistence* for channels.** Making a Telegram conversation
  resumable across restarts is a real feature and a much bigger one.
- **Do not touch `hachi run --once`** (`cli/main.py:3776`) or the Rich REPL
  (`:3602`). They are genuinely unattended/local and outside this finding.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done. State explicitly
whether you verified the `/sessions` visibility manually or only by unit test.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`; `BB-88` is the
highest today, and sibling tasks in this pack also append — re-check before you write):

```markdown
### BB-N — Channel and schedule sessions were invisible to /sessions, audit and spend

- **Symptom:** A Telegram/WhatsApp conversation, or a task fired by `hachi schedule run-due` / `run-now`, never appeared in `GET /sessions`, contributed nothing to the permission-audit view, and was absent from spend reporting — even with the gateway running in the same process.
- **Root cause:** Four boot sites called `boot_agent()` directly instead of going through `GatewayControlPlane.create_session` → `_InProcessGatewayRuntime.register_connection`: `GatewaySessionRunner` (kept its own private `_agents` dict) constructed at `cli/commands/channel.py` twice, and `cli/commands/schedule.py` at both `schedule_run_due` and `schedule_run_now`. Every gateway read model resolves through `_InProcessGatewayRuntime._agents`, so agents in any other map are structurally unreachable. (NOT an orphaned-approval bug — no approval was created on these paths at all; see the separate approver-selection defect.)
- **Fix:** Added `_InProcessGatewayRuntime.boot_registered_session(client_id, surface)`; channels pass it through the existing `GatewaySessionRunner(boot=…)` seam and both schedule sites call it. When no gateway runtime is active the paths fall back to a direct boot and log a WARNING naming exactly what is degraded. Interim pending the CF-2 runtime extraction.
- **Avoid:** every entry point that creates an agent session must register it in the one session map the read models query — a second private map makes the sessions invisible rather than merely unmanaged.
- **Locked by:** `tests/test_governed_session_entry_points.py` — `test_channel_runner_boots_through_the_gateway_runtime`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **`lint-imports` is BLOCKING in the gate.** `pyproject.toml`'s import-linter contracts
  forbid `hachi.core`/`hachi.og_engine`/`hachi.tools`/`hachi.jobs`/`hachi.integrations`
  from importing `hachi.cli` or `hachi.gateway`. `hachi.channels` and `hachi.cli.commands`
  are **not** in those source lists, so the edges you are adding are legal today — but
  **run `uv run lint-imports` explicitly** and do not add an `ignore_imports` entry to
  make a violation go away. If you hit one, you have chosen the wrong option in §5.
- **`_ACTIVE_RUNTIME` is `None` in most tests and in cron invocations.** The fallback is
  not an edge case, it is the common case for `hachi schedule run-due`. Test it
  explicitly (§7's third test).
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — do not reach
  through it in the new helper.
- **Existing channel tests patch the class, not the boot.**
  `tests/test_channel_whatsapp_cmd.py:376`, `:408`, `:435` and
  `tests/test_telegram_setup.py:182` all do
  `patch("hachi.channels.runner.GatewaySessionRunner")`. Because you are changing the
  *construction* in `cli/commands/channel.py` and not the class, those patches keep
  working — **but verify it**, because if you move the construction they will silently
  patch nothing. If one legitimately needs its patch target updated, that is a **test
  target correction, not a weakening** ([CLAUDE.md](../../../../CLAUDE.md) Rule 2); say
  so in the commit message.
- **`create_session` enforces a session cap** (`control_plane.py:315-318`,
  `HACHI_GATEWAY_MAX_SESSIONS`, default 100). A long-running Telegram bot with many
  distinct senders now consumes those slots. Channels currently never release them
  (`GatewaySessionRunner` only clears on `shutdown()`, `runner.py:36-44`). Note this as
  a follow-up; do not build eviction here.
- **`hachi schedule run-due` boots ONE agent for ALL due schedules** (`schedule.py:169`,
  then `scheduler.tick(fire)` at `:177`). Preserve that — do not accidentally convert it
  into one session per schedule; that would multiply boot cost and session-cap pressure.
