# T-42 · Retire the `core → cli` seam behind a `SessionRuntime` protocol

|  |  |
|---|---|
| **Source finding** | CF-2 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P1 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | [T-41](T-41-extract-in-process-runtime.md) — *do not start until it has landed* |
| **Blocks** | nothing |
| **Effort** | ~2 days |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/core/runtime/resume.py`, `src/hachi/core/runtime/protocols.py` (new, or an existing `core` protocol module), `src/hachi/cli/main.py`, `pyproject.toml`, `tests/test_cold_start_resume.py` |

---

## 1. Brief

`core/runtime/resume.py` imports `hachi.cli.main`, reads the module global `_ACTIVE_RUNTIME`,
and touches the private `_agents` / `_agents_lock` attributes on it — the only `core → cli`
import in the repo, kept legal by a standing `import-linter` exemption. Replace it with a
small `SessionRuntime` protocol defined in `core`, injected from the edge, and **delete the
exemption**.

**This is trivial once [T-41](T-41-extract-in-process-runtime.md) has landed** — that task
moves the class this seam reaches for out of the CLI entirely, which is 90 % of the reason
the seam exists. Do not attempt it first; you would write the protocol twice.

## 2. Why this matters

This is the one *genuine* layering inversion in the codebase, and it is worth being precise
about that. CF-2 leans on `boot_agent` / `AgentSession` living outside `core` as evidence of
inverted layering — but they live in `src/hachi/gateway/orchestrator.py`, which is
**correct service-layer placement**, not an inversion. There is no `src/hachi/core/orchestrator.py`.
Strip that away and one real violation remains: the **engine reaching up into the CLI**.

While it stands, `hachi.core` cannot be imported without the Typer app being importable, the
`forbidden` contract that is supposed to protect the engine has a hole in it, and any future
`core → cli` import can be waved through with "there's already an exemption". Closing it
makes the rail mean what it says.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The four touch points, all inside `_do_resume`

`src/hachi/core/runtime/resume.py:108` — `def _do_resume(session_id: str, context: dict[str, Any], cursor: int) -> str:`

**`:121-126`** — the import and the global read:

```python
    # Resolve the active in-process runtime (set by _start_gateway_server / gateway command).
    # Read via the module object so monkeypatching and late writes are visible at call time.
    try:
        import hachi.cli.main as _main_mod

        runtime = getattr(_main_mod, "_ACTIVE_RUNTIME", None)
    except ImportError as exc:
```

**`:145-146`** — reaching into two private attributes:

```python
    # --- Hot path: session is already live ---
    with runtime._agents_lock:
        agent_session = runtime._agents.get(session_id)
```

**`:158`** — the one public call:

```python
    rehydrated = runtime.rehydrate_session(session_id)
```

Confirm the whole surface in one command:

```bash
grep -n "_agents_lock\|_agents\.get\|rehydrate_session\|import hachi.cli.main\|_ACTIVE_RUNTIME" \
  src/hachi/core/runtime/resume.py
# 113 (docstring), 124, 126, 135 (message), 145, 146, 158
```

That is the **entire** dependency: two private attributes and one method. Nothing else in
`core` names the CLI.

### 3.2 The exemption — `pyproject.toml:206-211`

The contract it punches a hole in is declared at `pyproject.toml:195-211`, named at `:196`:

```toml
[[tool.importlinter.contracts]]
name = "the engine must not import the UI/entry edges (cli, tui)"
type = "forbidden"
source_modules = [
    "hachi.core",
    "hachi.og_engine",
    "hachi.tools",
    "hachi.jobs",
    "hachi.integrations",
]
forbidden_modules = ["hachi.cli", "hachi.tui"]
ignore_imports = [
    # SEAM: cold-start resume needs the CLI's Typer app to rebuild a session's
    # command context. Lazy import inside resume(); should move behind a control-plane
    # protocol so core no longer names the CLI. Tracked as an honest seam in memory.
    "hachi.core.runtime.resume -> hachi.cli.main",
]
```

### 3.3 ⚠️ The exemption's own comment is factually wrong

> *"cold-start resume needs the CLI's **Typer app** to rebuild a session's **command context**."*

**It does not.** `_do_resume` never touches the Typer app, any Typer command, or anything
resembling a "command context". It reaches for `_ACTIVE_RUNTIME` — a plain module global
holding an `_InProcessGatewayRuntime` instance (`cli/main.py:2710`):

```python
#: Module-level slot for the most-recently-created in-process gateway runtime.
#: Set by :func:`_start_gateway_server` and the ``gateway`` command so that
#: :func:`~hachi.core.runtime.resume._do_resume` can call
#: :meth:`_InProcessGatewayRuntime.rehydrate_session` on cold-start resume
#: without importing the CLI or threading a runtime reference through every layer.
_ACTIVE_RUNTIME: "_InProcessGatewayRuntime | None" = None
```

(Note the slot's own docstring says "without importing the CLI" — while the mechanism it
describes is *exactly* how the CLI gets imported. Both comments are wrong in the same
direction.)

**This matters operationally, not just cosmetically: the stated justification would survive
[T-41](T-41-extract-in-process-runtime.md) while the real dependency would not.** A reader
who trusts the comment concludes the seam is load-bearing forever. It is not — after T-41
the runtime class lives in `hachi.gateway.in_process_runtime`, and `core` importing
`hachi.gateway` is governed by a *different* contract (`pyproject.toml:213+`, "the engine
must not import the gateway service"). So T-41 does not fix this seam by itself; it just
removes the last excuse for it.

**Correcting this comment is part of this task** — and the correction is to delete the
whole block.

### 3.4 The linter self-cleans — deleting the entry IS the completion signal

Verified against the installed `import-linter` 2.12
(`.venv/Lib/site-packages/importlinter/contracts/forbidden.py:73`):

```python
    unmatched_ignore_imports_alerting = fields.EnumField(AlertLevel, default=AlertLevel.ERROR)
```

and `.venv/Lib/site-packages/importlinter/application/contract_utils.py:88-91`:

```python
    else:  # AlertLevel.ERROR
        messages = [_build_missing_import_message(expr) for expr in expressions]
        raise MissingImport("\n".join(messages))
```

So an exemption that no longer matches a real import **raises** `No matches for ignored
import hachi.core.runtime.resume -> hachi.cli.main.` This gives you a free, unambiguous
completion check: **remove the import and leave the exemption in place — the linter will
fail. Then delete the exemption and it passes.** If you delete the exemption and the linter
fails with a *contract violation* instead, you have missed an import.

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor with no runtime symptom.** Cold-start resume works today. Do not
invent a repro. Here is how to see the problem:

```bash
# 1. The engine names the CLI — the only such import in the repo.
grep -rn "hachi\.cli" src/hachi/core/ src/hachi/og_engine/ src/hachi/tools/ src/hachi/jobs/ src/hachi/integrations/

# 2. The rail that forbids it has a hole cut for exactly that line.
sed -n '195,211p' pyproject.toml

# 3. Prove the hole is the ONLY thing keeping it green: comment out the
#    ignore_imports entry and re-run the linter.
uv run lint-imports
```

**You will see now:** step 1 prints `src/hachi/core/runtime/resume.py:113`, `:124`; step 3
(with the exemption commented out) reports the forbidden contract BROKEN with
`hachi.core.runtime.resume -> hachi.cli.main`.
**You should see after the fix:** step 1 prints nothing; step 3 is green *with no exemption
present*; `grep -c "ignore_imports" pyproject.toml` has dropped by one occurrence in that
contract.

## 5. What "fixed" looks like

A protocol in `core`, an injected instance, and no exemption.

**New (or added to an existing `core` protocol module):** `src/hachi/core/runtime/protocols.py`

```python
"""Structural contracts the engine depends on, implemented at the service edge."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SessionRuntime(Protocol):
    """The minimum surface cold-start resume needs from a live gateway runtime.

    Implemented by ``hachi.gateway.in_process_runtime._InProcessGatewayRuntime``.
    ``core`` must never name that class.
    """

    def get_live_session(self, session_id: str) -> Any | None:
        """Return the live in-memory session, or None if it is not resident.

        Implementations own their own locking; callers must not.
        """

    def rehydrate(self, session_id: str) -> Any | None:
        """Rebuild a session from the durable transcript, or None on failure."""
```

**Registration seam in `core`** — one module-level slot plus a setter, so the edge injects
downward instead of `core` importing upward:

```python
# src/hachi/core/runtime/protocols.py (continued)

_ACTIVE_SESSION_RUNTIME: SessionRuntime | None = None


def set_active_session_runtime(runtime: SessionRuntime | None) -> None:
    """Register the process-wide session runtime. Called by the gateway edge only."""
    global _ACTIVE_SESSION_RUNTIME  # noqa: PLW0603
    _ACTIVE_SESSION_RUNTIME = runtime


def get_active_session_runtime() -> SessionRuntime | None:
    """Read the registered runtime through the module object (late writes visible)."""
    return _ACTIVE_SESSION_RUNTIME
```

**`resume.py` after** — no import of `hachi.cli`, no private attribute access:

```python
    from hachi.core.runtime.protocols import get_active_session_runtime

    runtime = get_active_session_runtime()
    if runtime is None:
        raise HonestResumeError(
            "resume_run: no active in-process runtime "
            f"for session_id={session_id!r}. "
            "Cold-start resume requires a running gateway (--runtime flag). "
            "Trigger via POST /runs/{run_id}/wake after starting the gateway."
        )
    ...
    agent_session = runtime.get_live_session(session_id)
    ...
    rehydrated = runtime.rehydrate(session_id)
```

**Decisions already made — do not re-litigate:**

1. **Two methods, not more.** `get_live_session` and `rehydrate`. Do not add `chat`,
   `interrupt`, or anything else "while you're there" — the protocol must stay the size of
   the actual dependency or it becomes a second handler bag
   ([T-43](T-43-collapse-control-plane-interfaces.md) is about *undoing* one of those).
2. **`get_live_session` takes the lock internally.** The caller must not see `_agents_lock`.
   The adapter method on the runtime is:
   ```python
   def get_live_session(self, session_id: str) -> AgentSession | None:
       with self._agents_lock:
           return self._agents.get(session_id)
   ```
   Add it to the runtime class; **`rehydrate` is an alias for the existing
   `rehydrate_session`** — keep `rehydrate_session` too, it has other callers.
3. **`_ACTIVE_RUNTIME` in `cli/main.py` is deleted**, and its two writers
   (`cli/main.py:2931-2932` in `_start_gateway_server`, `:3974-3975` in the `gateway`
   command) call `set_active_session_runtime(runtime)` instead. **Do not keep both** — a
   parallel slot is how this seam grows back.
4. **The error message keeps its shape.** It is user-facing and tests assert on it; drop
   only the now-meaningless `(_ACTIVE_RUNTIME is None)` fragment.
5. **The exemption block is deleted, not commented out.**

## 6. Steps

**Three commits.**

### Commit 1 — characterization test (no source change)

1. Write the test from §7 against today's behaviour. Confirm it passes.
2. Record the full-suite baseline counts.

### Commit 2 — introduce the protocol and switch the call site

3. Create `src/hachi/core/runtime/protocols.py` with `SessionRuntime`,
   `set_active_session_runtime`, `get_active_session_runtime`.
4. Add `get_live_session` and `rehydrate` to `_InProcessGatewayRuntime` (in
   `src/hachi/gateway/in_process_runtime.py` after T-41). Both are 2–3 lines wrapping code
   that already exists. **Do not delete `rehydrate_session`.**
5. Rewrite `resume.py:121-126` to call `get_active_session_runtime()`; delete the
   `try/except ImportError` block — with no import there is nothing to catch. Keep the
   `runtime is None` branch and its `HonestResumeError`.
6. Rewrite `resume.py:145-146` to `agent_session = runtime.get_live_session(session_id)`.
7. Rewrite `resume.py:158` to `rehydrated = runtime.rehydrate(session_id)`.
8. Fix the stale docstring at `resume.py:113` (it names
   `hachi.cli.main._InProcessGatewayRuntime.rehydrate_session`).
9. In `cli/main.py`: replace both `_ACTIVE_RUNTIME` assignments with
   `set_active_session_runtime(runtime)`; delete the `_ACTIVE_RUNTIME` slot at `:2710` and
   its comment block.
10. Update `tests/test_cold_start_resume.py` — it patches
    `"hachi.cli.main._ACTIVE_RUNTIME"` (3 patch strings in that file). Point them at
    `set_active_session_runtime`, or at
    `"hachi.core.runtime.protocols._ACTIVE_SESSION_RUNTIME"`. Prefer the **setter** — it is
    the supported entry point and survives a future rename of the slot.
11. **Leave `pyproject.toml` untouched.** Run `uv run lint-imports`. It must now FAIL with
    `No matches for ignored import hachi.core.runtime.resume -> hachi.cli.main.` That
    failure is your proof the import is gone (§3.4).

### Commit 3 — delete the exemption

12. Delete `pyproject.toml:206-211` — the whole `ignore_imports = [ … ]` block including
    the three wrong comment lines (§3.3).
13. `uv run lint-imports` → green.
14. Full suite; counts must match the commit-1 baseline.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug, so the instrument is a **characterization test** plus one
**architectural assertion** that genuinely fails today.

- **File:** `tests/test_core_cli_seam.py` (new); plus edits to `tests/test_cold_start_resume.py` (existing)
- **Test names:** `test_core_does_not_import_the_cli`, `test_resume_uses_the_injected_runtime`
- **They must assert:** the real import graph of the shipped package, and real resume
  behaviour through the protocol — not a mock's return value.
- **`test_core_does_not_import_the_cli` MUST FAIL before the fix** with
  `AssertionError: core still names the CLI: ['src/hachi/core/runtime/resume.py']`.

```python
# sketch — adapt to the repo's existing fixtures
from pathlib import Path

ENGINE_PACKAGES = ("core", "og_engine", "tools", "jobs", "integrations")


def test_core_does_not_import_the_cli() -> None:
    """The engine must not name hachi.cli. FAILS before T-42 (resume.py:124).

    Source-text assertion, not an import-graph one: it is the same check the
    import-linter contract makes, expressed so a developer sees it in `pytest`
    output rather than only in the gate.
    """
    root = Path(__file__).resolve().parents[1] / "src" / "hachi"
    offenders = [
        str(p.relative_to(root.parents[1]))
        for pkg in ENGINE_PACKAGES
        for p in (root / pkg).rglob("*.py")
        if "import hachi.cli" in p.read_text(encoding="utf-8")
        or "from hachi.cli" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"core still names the CLI: {offenders}"


def test_resume_uses_the_injected_runtime() -> None:
    """Cold-start resume must resolve the runtime through the protocol seam.

    Characterization: asserts the SAME observable outcome as today (hot path
    returns the live session's reply), through the new injection point.
    """
    from hachi.core.runtime.protocols import set_active_session_runtime

    class _FakeRuntime:
        def __init__(self) -> None:
            self.rehydrate_calls: list[str] = []

        def get_live_session(self, session_id: str):
            return _LiveSession() if session_id == "live-1" else None

        def rehydrate(self, session_id: str):
            self.rehydrate_calls.append(session_id)
            return _LiveSession()

    class _LiveSession:
        def chat(self, text: str) -> str:
            return f"replied:{text}"

    fake = _FakeRuntime()
    set_active_session_runtime(fake)
    try:
        from hachi.core.runtime.resume import _do_resume

        out = _do_resume("live-1", {"wait_result": {"ok": True}}, 0)
        assert out.startswith("replied:[RESUME]")
        assert fake.rehydrate_calls == []          # hot path: no rehydration

        out_cold = _do_resume("cold-1", {"wait_result": {"ok": True}}, 0)
        assert out_cold.startswith("replied:[RESUME]")
        assert fake.rehydrate_calls == ["cold-1"]  # cold path: rehydrated once
    finally:
        set_active_session_runtime(None)
```

> If `test_core_does_not_import_the_cli` passes before you write the fix, you are pointed at
> the wrong tree. Do not proceed.

Also keep the existing no-runtime test: with `set_active_session_runtime(None)`, `_do_resume`
must still raise `HonestResumeError`. That branch is the honest-failure contract and must not
regress into a silent `None`.

## 8. Acceptance criteria

- [ ] `test_core_does_not_import_the_cli` exists and **failed before the fix**.
- [ ] `grep -rn "hachi\.cli" src/hachi/core/ src/hachi/og_engine/ src/hachi/tools/ src/hachi/jobs/ src/hachi/integrations/` returns **nothing** — including docstrings.
- [ ] `resume.py` contains no `_agents`, `_agents_lock`, or `_ACTIVE_RUNTIME` reference.
- [ ] `pyproject.toml` has **no** `ignore_imports` entry in the contract named
      *"the engine must not import the UI/entry edges (cli, tui)"*, and the three incorrect
      comment lines (§3.3) are gone with it.
- [ ] You observed the intermediate state from §6 step 11: import removed + exemption still
      present ⇒ `lint-imports` fails with `No matches for ignored import …`.
- [ ] `uv run lint-imports` is green.
- [ ] `_ACTIVE_RUNTIME` no longer exists in `cli/main.py`; both former writers call
      `set_active_session_runtime`.
- [ ] `SessionRuntime` has exactly two methods.
- [ ] Full-suite counts are identical to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change resume behaviour while moving the dependency.** Hot path, cold path, and
  the no-runtime `HonestResumeError` must behave exactly as they do today. This is the
  primary boundary of this task.
- Do not grow `SessionRuntime` past two methods (§5 decision 1).
- Do not "fix" the other frozen seam contract at `pyproject.toml:213+` (*"the engine must not
  import the gateway service"*) or any of its exemptions. Different contract, different task.
- Do not keep `_ACTIVE_RUNTIME` as a deprecated alias.
- Do not touch `_InProcessGatewayRuntime`'s other 79 methods — only *add* the two adapter
  methods.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). `tests/test_cold_start_resume.py` needs its
  patch targets re-pointed, not its assertions relaxed.
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. `typing.Protocol` is stdlib.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run lint-imports                          # the completion signal (§3.4)
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — an import-linter exemption whose comment documents a dependency that never existed

- **Symptom:** `pyproject.toml` exempted `hachi.core.runtime.resume -> hachi.cli.main`,
  justified as "cold-start resume needs the CLI's Typer app to rebuild a session's command
  context". No Typer app was involved; the real dependency was the `_ACTIVE_RUNTIME` module
  global. The wrong justification made the seam look permanent.
- **Root cause:** The exemption comment was written from intent, not from the code, and was
  never re-checked as the code moved.
- **Fix:** Replaced the import with a two-method `SessionRuntime` protocol in `core`,
  injected by the gateway edge; deleted the exemption.
- **Avoid:** An `ignore_imports` comment must name the *symbol* being reached for, not the
  module's reputation — and re-verify it whenever the target moves. `import-linter`'s
  default `unmatched_ignore_imports_alerting = ERROR` means a stale exemption fails the
  gate, so deleting the import IS the signal to delete the entry.
- **Locked by:** `tests/test_core_cli_seam.py` — `test_core_does_not_import_the_cli`
```

## 12. Known traps

- **Doing this before [T-41](T-41-extract-in-process-runtime.md).** You would write the
  protocol against `hachi.cli.main._InProcessGatewayRuntime`, then rewrite it a week later.
  Wait.
- **T-41 does not fix this by itself.** After T-41 the class is in `hachi.gateway`, and
  `core → gateway` is forbidden by a *different* contract (`pyproject.toml:213+`). The
  protocol is still required.
- **Snapshot binding.** `get_active_session_runtime()` must read the module-level variable
  *inside the function*. A `from … import _ACTIVE_SESSION_RUNTIME` at any call site captures
  `None` at import time and cold-start resume silently stops working. The current code
  already documents this hazard at `resume.py:122` — preserve the intent.
- **Test isolation.** `set_active_session_runtime` is process-global. Always reset it to
  `None` in a `finally:` or an autouse fixture, or you will leak a fake runtime into the
  next test and produce order-dependent failures.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-3:** never `patch.dict(sys.modules)` over `chromadb`.
