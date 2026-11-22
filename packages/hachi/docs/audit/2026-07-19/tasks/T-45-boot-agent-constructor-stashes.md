# T-45 · Promote `boot_agent`'s ten post-construction stashes to constructor arguments

|  |  |
|---|---|
| **Source finding** | CF-6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | [T-40](T-40-emit-runtime-event-closure-capture.md) |
| **Blocks** | [T-44](T-44-boot-agent-staged-builders.md) — *land this first; it shrinks T-44's tail* |
| **Effort** | ~2 days |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, `tests/test_agent_session_shutdown.py`, `tests/test_agent_session_construction.py` (new) |

---

## 1. Brief

`boot_agent` constructs an `AgentSession` and then writes **ten private attributes onto the
finished object** rather than passing them to the constructor. Three of those attributes are
consumed by `shutdown()` and are not declared on the class at all — so `shutdown()` reads them
through `getattr(self, "_x", None)` and silently skips cleanup when they are missing.
Promote all ten to constructor parameters.

⚠️ **CF-6 lists four stashes. There are ten, and the two it misses are the ones that leak
resources.** Read §3.2 before you plan anything.

## 2. Why this matters

The constructor signature is a contract, and right now it is fiction: an `AgentSession` built
by calling `AgentSession(...)` is **not** the object the rest of the code expects — it is
missing the sub-agent client, the browser controller, and the schedule runner, all three of
which `shutdown()` must close. The codebase already knows this, which is why those three reads
are defensive `getattr` calls with a `None` fallback.

That is precisely the idiom CF-1 names as the engine of the repo's "dead features report
success" problem, and its recommendation is explicit: *a `getattr(x, "field", None)` against
your own types is a lint error.* This task removes three instances of it from the shutdown
path — the path where a silent skip means a leaked browser process and a running scheduler
thread after the session is supposedly gone.

It is also the cheapest possible preparation for
[T-44](T-44-boot-agent-staged-builders.md): ten writes currently sit *across* the stage
boundaries T-44 needs to draw, at `:3467` and `:3656-3657`, 190 lines apart.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The ten stashes

```bash
grep -n "session\._[a-z_]* = " src/hachi/gateway/orchestrator.py
```

| # | Line | Statement |
|---|---|---|
| 1 | `:3467` | `session._max_daily_cost_usd = max_daily_cost_usd` |
| 2 | `:3485` | `session._sub_agent_client = sub_agent_client  # closed on shutdown alongside the main client` |
| 3 | `:3486` | `session._browser_controller = browser_controller  # closed on shutdown (no-op if never used)` |
| 4 | `:3488` | `session._episodic_top_k = _memory_settings.episodic_top_k` |
| 5 | `:3490` | `session._graph_recall = _memory_settings.graph_recall` |
| 6 | `:3493` | `session._durable_title = True` |
| 7 | `:3495` | `session._provider_registry = _provider_registry` |
| 8 | `:3496` | `session._secret_store = secret_store` |
| 9 | **`:3656`** | `session._schedule_runner = _schedule_runner  # stopped in shutdown()` |
| 10 | **`:3657`** | `session._scheduler = scheduler  # P4-05: exposed for companion web UI` |

**CF-6 cites the range `:3467–3496` and names only four.** That range stops 160 lines short of
stashes 9 and 10. Working from the review's list would leave `_schedule_runner` and
`_scheduler` behind — see §3.3 for why that is the dangerous outcome.

### 3.2 The split that makes this task easy — seven are already half-done

**Seven of the ten attributes are already declared in `AgentSession.__init__`** with a default
and a comment that literally says who sets them. `orchestrator.py:577-602`:

```python
        # Rolling calendar-day spend cap (P1-3).  Set by boot_agent from [limits] config /
        # HACHI_MAX_DAILY_COST_USD env.  None means unlimited (default — safe fail-open).
        self._max_daily_cost_usd: float | None = None
        ...
        # P4-05: scheduler reference — set by boot_agent after ScheduleRunner starts.
        self._scheduler: Any = None
        ...
        # Slice 2.2: when True, _enqueue_title_job uses handler_name= instead of
        # func= so the job survives a restart.  Set by boot_agent when
        # [jobs] durable_handlers=true.
        self._durable_title: bool = False

        # M1: number of past-session episodes to inject per turn (0 = disabled).
        # Set by boot_agent from memory settings (episodic_top_k).
        self._episodic_top_k: int = 3

        # Stage-C graph expansion: when True, each turn appends a concise graph-expanded
        # memory section to the recall block.  Set by boot_agent from memory.graph_recall.
        self._graph_recall: bool = True

        # BB-11: stashed by boot_agent so reload_search_provider() can rebuild the
        # ProviderRegistry with fresh credentials without a full restart.
        self._provider_registry: Any = None
        self._secret_store: Any = None
```

| Attribute | Declared at | Default |
|---|---|---|
| `_max_daily_cost_usd` | `:577` | `None` |
| `_scheduler` | `:584` | `None` |
| `_durable_title` | `:589` | `False` |
| `_episodic_top_k` | `:593` | `3` |
| `_graph_recall` | `:597` | `True` |
| `_provider_registry` | `:601` | `None` |
| `_secret_store` | `:602` | `None` |

For these seven the promotion is trivial and the default is **already chosen for you** — move
the declaration to a keyword parameter with the identical default.

### 3.3 ⚠️ The other three are undeclared, and they are the shutdown-critical ones

`_sub_agent_client`, `_browser_controller`, and `_schedule_runner` appear **nowhere** in
`AgentSession.__init__`. They exist only because `boot_agent` writes them. That is why every
read of them is defensive:

`orchestrator.py:1816-1820` — the first three lines of `shutdown()`:

```python
    def shutdown(self):
        """Gracefully close all persistent connections, MCP servers, and session store."""
        runner = getattr(self, "_schedule_runner", None)
        if runner is not None:
            runner.stop()
```

`orchestrator.py:1896-1900` — closing LLM clients:

```python
        for client in (
            getattr(self.loop, "llm_client", None),
            getattr(self, "_sub_agent_client", None),
        ):
```

`orchestrator.py:1913-1915`:

```python
        # Shut down the browser worker thread + headless browser if one was started.
        browser = getattr(self, "_browser_controller", None)
        if browser is not None:
```

And one non-shutdown reader, `orchestrator.py:1319`:

```python
        client = getattr(self, "_sub_agent_client", None) or getattr(self.loop, "llm_client", None)
```

**All three inline comments at the stash sites document a lifecycle contract the constructor
fails to express** — `# closed on shutdown alongside the main client`, `# closed on shutdown
(no-op if never used)`, `# stopped in shutdown()`. A contract that lives in a comment on an
assignment 2,300 lines from the method that depends on it is not a contract.

**This is why CF-6's four-item list is dangerous to work from: omitting `_schedule_runner`
leaves a running scheduler thread after `shutdown()`.** The `getattr` fallback means it fails
*silently* — the session reports a clean shutdown and the thread keeps ticking.

### 3.4 The current constructor

`orchestrator.py:520-532` — ten parameters, seven required:

```python
    def __init__(
        self,
        loop: ExecutionLoop,
        skill_engine: SkillEngine,
        memory: MemoryManager,
        integrations: IntegrationRuntime,
        mcp_manager: MCPManager,
        permission_gate: Any,
        model_name: str,
        event_emitter: Callable[[str, dict[str, Any]], None] | None = None,
        read_models: RuntimeReadModelStore | None = None,
        job_queue: JobQueue | None = None,
    ):
```

### 3.5 ⚠️ `:3467` is conditional

```python
    # P1-3: propagate the daily cap to the session so _daily_cap_exceeded() can enforce it.
    if max_daily_cost_usd:
        session._max_daily_cost_usd = max_daily_cost_usd
```

The attribute is set **only when the local is truthy**, so a `0.0` cap leaves it `None`.
Promoting it must preserve that: pass `max_daily_cost_usd or None`, not the raw value.

Behaviour analysis (do this rather than trusting the above): the only consumer is
`_daily_cap_exceeded`, `orchestrator.py:1577-1590`:

```python
        if not self._max_daily_cost_usd:
            return None
        ...
            if spent >= self._max_daily_cost_usd:
```

`None` and `0.0` are both falsy, so they take the same branch and `:1589-1590` is unreachable
for either. **The two are observationally identical today** — but pass `or None` anyway, so
the promotion is provably neutral rather than argued-neutral.

### 3.6 ⚠️ The existing shutdown test bypasses the constructor

`tests/test_agent_session_shutdown.py:26` builds its fixture with
`AgentSession.__new__(AgentSession)` and hand-assigns attributes — including, at `:36`, `:41`,
`:42`, exactly the three undeclared stashes:

```python
    agent._schedule_runner = None
    ...
    agent._sub_agent_client = None
    agent._browser_controller = None
```

**Because it never calls `__init__`, this test cannot catch a dropped constructor argument.**
It will stay green no matter what you do to the signature. Your new test (§7) must actually
construct the object.

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor with no user-visible symptom today**, because `boot_agent` always
performs all ten writes. The latent failure is real but unreachable through the shipped boot
path. Do not fabricate a repro; demonstrate it directly instead:

```bash
# 1. The ten stashes, and how far apart they are.
grep -n "session\._[a-z_]* = " src/hachi/gateway/orchestrator.py

# 2. Seven are pre-declared; three are not.
sed -n '573,604p' src/hachi/gateway/orchestrator.py
grep -n "_sub_agent_client\|_browser_controller\|_schedule_runner" src/hachi/gateway/orchestrator.py \
  | awk -F: '$1>520 && $1<610'          # → nothing: absent from __init__

# 3. Which is why shutdown reads them defensively.
sed -n '1816,1820p;1896,1900p;1913,1915p' src/hachi/gateway/orchestrator.py

# 4. Prove the latent leak: a constructed-not-booted session skips cleanup silently.
python - <<'PY'
import inspect
from hachi.gateway.orchestrator import AgentSession
src = inspect.getsource(AgentSession.__init__)
for name in ("_sub_agent_client", "_browser_controller", "_schedule_runner"):
    print(f"{name:22} declared in __init__: {name in src}")
PY
```

**You will see now:** step 4 prints `False` three times — the constructor does not establish
three attributes that `shutdown()` depends on.
**You should see after the fix:** `True` three times, and `grep -c 'getattr(self, "_schedule_runner"'`
→ 0.

## 5. What "fixed" looks like

Ten new keyword-only parameters, defaults identical to today's declared defaults, and three
`getattr` calls replaced with plain attribute access.

```python
    def __init__(
        self,
        loop: ExecutionLoop,
        skill_engine: SkillEngine,
        memory: MemoryManager,
        integrations: IntegrationRuntime,
        mcp_manager: MCPManager,
        permission_gate: Any,
        model_name: str,
        event_emitter: Callable[[str, dict[str, Any]], None] | None = None,
        read_models: RuntimeReadModelStore | None = None,
        job_queue: JobQueue | None = None,
        *,
        # --- promoted from boot_agent post-construction stashes (T-45) ---
        max_daily_cost_usd: float | None = None,
        sub_agent_client: Any = None,        # closed on shutdown alongside the main client
        browser_controller: Any = None,      # closed on shutdown (no-op if never used)
        schedule_runner: Any = None,         # stopped in shutdown()
        scheduler: Any = None,
        episodic_top_k: int = 3,
        graph_recall: bool = True,
        durable_title: bool = False,
        provider_registry: Any = None,
        secret_store: Any = None,
    ):
```

and in `shutdown()`:

```python
        runner = self._schedule_runner          # was: getattr(self, "_schedule_runner", None)
        if runner is not None:
            runner.stop()
```

**Decisions already made — do not re-litigate:**

1. **Keyword-only (`*`) for all ten.** Ten more positional parameters on a 10-parameter
   constructor is worse than what we started with, and keyword-only makes every call site
   self-documenting.
2. **Defaults are copied exactly from the `:577-602` declarations** (§3.2). The three
   undeclared ones get `None` — the value the `getattr` fallback already produces, so the
   defensive readers become plain reads with identical behaviour.
3. **Keep the private `self._x` attribute names.** They have readers across the class and in
   `_InProcessGatewayRuntime`. Renaming is out of scope and would churn unrelated files.
4. **`max_daily_cost_usd` is passed as `max_daily_cost_usd or None`** (§3.5), preserving the
   conditional-write semantics exactly.
5. **Replace the three `getattr(self, "_x", None)` reads with direct attribute access** — at
   `:1319`, `:1818`, `:1899`, `:1914`. This is the *point* of the task, not a bonus; leaving
   them keeps the defensive idiom alive and CF-1's lint rule unenforceable here.
6. **`_durable_title` stays a `bool` parameter**, not an inversion of the `if
   _jobs_cfg.durable_handlers:` guard at the call site — pass
   `durable_title=_jobs_cfg.durable_handlers`.
7. **Zero behaviour change.**

## 6. Steps

**Three commits.**

### Commit 1 — the constructor test (no source change)

1. Write `tests/test_agent_session_construction.py` from §7. It **must fail** on the three
   undeclared attributes.
2. Record full-suite baseline counts.

### Commit 2 — promote the ten

3. Add the ten keyword-only parameters to `AgentSession.__init__` (`:520`) with the defaults
   from §3.2 / §5.
4. In the `__init__` body, replace the seven bare declarations at `:577-602` with assignments
   from the new parameters. **Keep the explanatory comments** — update "Set by boot_agent" to
   name the parameter instead.
5. Add the three previously-undeclared assignments (`self._sub_agent_client = sub_agent_client`,
   etc.) alongside them.
6. In `boot_agent`, move all ten values into the `AgentSession(...)` call and **delete** the
   ten stash statements at `:3467`, `:3485-3486`, `:3488`, `:3490`, `:3493`, `:3495-3496`,
   `:3656-3657`.
   ⚠️ **`:3656-3657` are 190 lines below the construction site and sit after the
   `_schedule_runner.start()` block at `:3652-3654`.** Confirm the runner is fully started
   before construction, or move the construction — do not reorder the `start()` silently.
   If the ordering cannot be preserved, **stop and report it**; do not paper over it.
7. Replace the four defensive reads (`:1319`, `:1818`, `:1899`, `:1914`) with direct attribute
   access.
8. Full suite; counts must match the baseline.

### Commit 3 — fix the fixture that bypasses the constructor

9. Rewrite `tests/test_agent_session_shutdown.py`'s `_minimal_agent_session` to call the real
   constructor with mocks instead of `AgentSession.__new__` (§3.6), so it starts catching
   dropped arguments. **This is a test *strengthening*, not a weakening** — call it out in
   the commit message.
10. Full suite.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law).** Unusually for a
Wave-2 refactor, this one has a test that **genuinely fails today**, because the constructor
really does leave three attributes unestablished.

- **File:** `tests/test_agent_session_construction.py` (new)
- **Test names:** `test_constructor_establishes_every_shutdown_dependency`,
  `test_shutdown_stops_a_constructor_supplied_schedule_runner`
- **It must assert:** the real attribute state of a constructor-built session and the real
  side effects of `shutdown()` — not a mock's return value.
- **It must FAIL before your fix** with:
  `AssertionError: constructor did not establish: ['_sub_agent_client', '_browser_controller', '_schedule_runner']`

```python
# sketch — adapt to the repo's existing fixtures
from unittest.mock import MagicMock


def _constructed_session(**kwargs):
    from hachi.gateway.orchestrator import AgentSession

    return AgentSession(
        loop=MagicMock(),
        skill_engine=MagicMock(),
        memory=MagicMock(),
        integrations=MagicMock(),
        mcp_manager=MagicMock(),
        permission_gate=MagicMock(),
        model_name="test-model",
        **kwargs,
    )


SHUTDOWN_DEPENDENCIES = ("_sub_agent_client", "_browser_controller", "_schedule_runner")


def test_constructor_establishes_every_shutdown_dependency() -> None:
    """shutdown() depends on three attributes the constructor never sets.

    FAILS before T-45: they exist only because boot_agent writes them
    afterwards, so shutdown() reads them via getattr(..., None) and
    silently skips cleanup on any constructor-built session.
    """
    session = _constructed_session()
    missing = [a for a in SHUTDOWN_DEPENDENCIES if not hasattr(session, a)]
    assert missing == [], f"constructor did not establish: {missing}"


def test_shutdown_stops_a_constructor_supplied_schedule_runner() -> None:
    """The leak CF-6's four-item list would have left behind (T-45 §3.3).

    FAILS before T-45 with TypeError: unexpected keyword 'schedule_runner'.
    """
    runner = MagicMock()
    session = _constructed_session(schedule_runner=runner)
    session.shutdown()
    runner.stop.assert_called_once()


def test_daily_cap_promotion_preserves_falsy_collapse() -> None:
    """A 0.0 cap must remain 'unlimited', as the `if` at :3467 made it (T-45 §3.5)."""
    assert _constructed_session(max_daily_cost_usd=None)._max_daily_cost_usd is None
    assert _constructed_session(max_daily_cost_usd=0.0)._max_daily_cost_usd in (None, 0.0)
    assert _constructed_session(max_daily_cost_usd=5.0)._max_daily_cost_usd == 5.0
```

> If `test_constructor_establishes_every_shutdown_dependency` passes before your fix, you are
> testing a booted session rather than a constructed one. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists and **failed before the fix** with the three-name
      `AssertionError`.
- [ ] `AgentSession.__init__` accepts all **ten** promoted values as keyword-only parameters
      with the defaults from §3.2.
- [ ] `grep -c "session\._[a-z_]* = " src/hachi/gateway/orchestrator.py` → **0**.
- [ ] All four defensive reads are gone:
      `grep -n 'getattr(self, "_sub_agent_client"\|getattr(self, "_browser_controller"\|getattr(self, "_schedule_runner"' src/hachi/gateway/orchestrator.py` → nothing.
- [ ] `boot_agent` passes `max_daily_cost_usd or None`, preserving §3.5.
- [ ] `_schedule_runner.start()` still runs before the session is constructed, and you
      verified the ordering rather than assuming it (§6 step 6).
- [ ] `tests/test_agent_session_shutdown.py` builds its fixture through the real constructor.
- [ ] Full-suite counts identical to the commit-1 baseline (plus the new tests). Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving the values.** Primary boundary. Same defaults, same
  falsy handling, same construction order, same shutdown sequence.
- Do not work from CF-6's four-item list (§3.1). Ten, or you leave a resource leak.
- Do not rename the private attributes (§5 decision 3).
- Do not make any of the ten required. Every one has a default today; requiring one breaks
  every hand-built `AgentSession` in the test tree.
- Do not decompose `boot_agent` — that is [T-44](T-44-boot-agent-staged-builders.md), and this
  task lands **before** it.
- Do not sweep the other `getattr(self, …)` calls elsewhere in the class. Only the four that
  read the three promoted attributes are in scope; the general rule is CF-1's, tracked
  separately.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). The `__new__`-based fixture in
  `test_agent_session_shutdown.py` is being *strengthened*, not relaxed.
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — `shutdown()` silently skipped cleanup for three attributes the constructor never set

- **Symptom:** `AgentSession.shutdown()` stops the schedule runner, closes the sub-agent LLM
  client, and closes the browser controller — but read all three via
  `getattr(self, "_x", None)`. `boot_agent` wrote them onto the finished object
  (`orchestrator.py:3485-3486`, `:3656`), so any session not built by `boot_agent` skipped
  all three cleanups and reported a clean shutdown.
- **Root cause:** Post-construction attribute stashing. The lifecycle contract lived in inline
  comments at the assignment sites, ~2,300 lines away from `shutdown()`, and the constructor
  signature did not express it. An audit list that named only four of the ten stashes would
  have left the schedule-runner leak in place.
- **Fix:** Promoted all ten stashes to keyword-only constructor parameters and replaced the
  defensive `getattr` reads with direct attribute access.
- **Avoid:** If `shutdown()` (or any lifecycle method) depends on an attribute, that attribute
  is a constructor argument. `getattr(self, "_own_field", None)` against your own type is a
  smell — it means construction is incomplete by design.
- **Locked by:** `tests/test_agent_session_construction.py` —
  `test_constructor_establishes_every_shutdown_dependency`
```

## 12. Known traps

- **The four-item list (§3.1).** CF-6's range stops 160 lines short. Grep; do not trust it.
- **The `__new__` fixture (§3.6).** `tests/test_agent_session_shutdown.py` bypasses `__init__`
  entirely, so it stays green through any constructor mistake. Fix it in commit 3 or you have
  no coverage where you most need it.
- **Ordering at `:3656`.** `_schedule_runner.start()` happens ~190 lines after the session is
  constructed. Moving the value into the constructor moves *when it is read*, not when it is
  started — confirm the runner object exists and is started in the same relative order.
- **`_durable_title` is set inside `if _jobs_cfg.durable_handlers:`** (`:3492-3493`). Pass the
  flag, not `True`.
- **Same-file concurrency.** `gateway/orchestrator.py` is touched by eleven tasks. Land this
  in a day or two, not over a week.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — `:3652`'s
  `getattr(_shared, "scheduler_runner_started", False)` guard depends on it. Do not touch it.
