# T-26 · Make a routing-layer boot failure visible instead of silent

|  |  |
|---|---|
| **Source finding** | CF-7 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · **the review cites the wrong file — see [CORRECTIONS.md](CORRECTIONS.md) §11** |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing |
| **Effort** | ~1 hour |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/gateway/orchestrator.py`, one test file |
| **Batch with** | [T-05-routing-cost-warnings-arity.md](T-05-routing-cost-warnings-arity.md) and [T-27-forward-max-tokens-resilient-client.md](T-27-forward-max-tokens-resilient-client.md) — three ~1-hour fixes, one commit each, one preflight run |

---

## 1. Brief

If anything goes wrong while building the model-routing layer at boot, the failure is
swallowed by a bare `except Exception` that logs at `logger.debug` and sets
`_model_router = None`. Routing is then silently off for the whole session — the user
configured `[routing]`, Hachi ignored it, and nothing said so at any visible log level. When
you are done the failure logs at `WARNING`, emits a runtime event, and the `try` is narrow
enough that an `ImportError` or a typo cannot hide inside it.

## 2. Why this matters

`[routing]` is what makes multi-model, cost-aware operation work. When it fails to boot the
user does not get an error — they get a subtly more expensive, subtly different product,
indefinitely, with the only evidence at a log level nobody runs in production. And it is not
just genuine routing failures: the `except` spans six imports and seven constructor calls,
so an `ImportError` from a partial install, an `AttributeError` from a renamed field, or a
plain typo in this block all present identically as "routing quietly off".

The perverse detail that makes this worth an hour: **the SUCCESS path is louder than the
failure path.** A working boot logs at `INFO`; a broken one logs at `DEBUG`.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

**The file is `src/hachi/gateway/orchestrator.py`.** The review says `core/orchestrator.py` —
**there is no such file.** Do not go looking for it.

`gateway/orchestrator.py:2896-2902` — the block opens:

```python
    # 6b. Build routing infrastructure (behind [routing] flag; absent = back-compat).
    # ProviderRegistry → ModelRegistry → RoutingPolicy → ModelRouter.
    # When [routing] is absent, the policy synthesises a single-model-for-all-caps
    # mapping and default_client() returns the existing `client` unchanged.
    _model_router = None
    _provider_registry = None
    try:                                                          # :2902
```

`gateway/orchestrator.py:2903-2923` — what the `try` covers: **six imports**, then seven
construction/lookup calls, any of which can raise for reasons unrelated to routing config:

```python
        from hachi.core.providers.registry import ProviderRegistry     # :2903
        from hachi.core.resilience import RetryPolicy                  # :2904
        from hachi.core.routing.policy import RoutingPolicy            # :2905
        from hachi.core.routing.registry import ModelRegistry          # :2906
        from hachi.core.routing.router import ModelRouter              # :2907
        from hachi.core.settings import ResolvedConfig                 # :2908

        _resolved_cfg = ResolvedConfig.model_validate(config)          # :2910
        _provider_registry = ProviderRegistry.from_config(_resolved_cfg, secret_store)
        _model_registry = ModelRegistry.build(_resolved_cfg, _provider_registry)
        _routing_policy = RoutingPolicy.from_config(_resolved_cfg)
        # Apply auto-policy if requested (amendment A1).
        if _routing_policy.auto:
            _routing_policy = _routing_policy.derive_auto_policy(_model_registry)
        _retry_policy = RetryPolicy.from_config(_resolved_cfg)         # :2917
        _model_router = ModelRouter(                                   # :2918
            registry=_model_registry,
            policy=_routing_policy,
            providers=_provider_registry,
            resilience=_retry_policy,
        )
```

…and it keeps going through the `RoutingConfigStore` bootstrap at `:2925-2941`, ending at
`:2954`. **The guarded span is ~53 lines.**

`gateway/orchestrator.py:2943-2954` — the success path, at `INFO`:

```python
        logger.info(                                                   # :2943
            "Routing boot: %d models registered; default=%s; auto=%s",
            len(_model_registry.all()),
            _routing_policy.default_model,
            _routing_policy.auto,
        )
        # Cost-governance guard (BB-30): surface the silent "every chat turn routed to
        # the priciest model" trap loudly at boot instead of letting it hide in the
        # routing table. Never changes routing — an explicit choice is respected.
        for _cost_warning in _routing_policy.costly_capability_warnings(_model_registry):
            logger.warning(_cost_warning)
            emit_runtime_event("cost.routing_warning", {"message": _cost_warning})   # :2954
```

`gateway/orchestrator.py:2955-2960` — **the defect**:

```python
    except Exception:                                                  # :2955
        logger.debug(                                                  # :2956
            "Routing boot: failed to initialise routing layer; falling back to direct client",
            exc_info=True,
        )
        _model_router = None                                           # :2960
```

Note `:2952-2954`: the surrounding code **already** knows the pattern you need — a
`logger.warning` paired with an `emit_runtime_event(...)`, with the `cost.` namespace and a
`{"message": …}` payload. `emit_runtime_event` is therefore in scope at `:2955`. Copy that
shape.

## 4. Reproduce the failure

Reproducible by code reading, and by a one-command grep that shows the asymmetry directly:

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
sed -n '2943,2960p' src/hachi/gateway/orchestrator.py
```

**You will see now:** `logger.info(` on the success path at `:2943` and `logger.debug(` on
the failure path at `:2956` — a working boot is louder than a broken one.

**You should see after the fix:** `logger.warning(` (or higher) on the failure path, plus an
`emit_runtime_event(...)` call beside it.

**Behavioural reproduction** (optional, but it is what the regression test automates): boot a
session with a `[routing]` section referencing a provider that does not exist, at default log
level. **You will see now:** no output at all; routing is off; `_model_router is None`.
**You should see after the fix:** a WARNING naming the exception type, and a runtime event on
the stream.

## 5. What "fixed" looks like

**Two changes. Do both.**

**(1) Promote the log and emit an event.** Replace `:2955-2960` with something shaped like
the existing `:2952-2954` pattern:

```python
    except Exception as exc:
        logger.warning(
            "Routing boot: failed to initialise routing layer (%s: %s); "
            "falling back to the direct client — [routing] configuration is NOT active",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        emit_runtime_event(
            "routing.boot_failed",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        _model_router = None
```

Keep `exc_info=True` — the traceback is the only thing that makes this diagnosable, and it
costs nothing at WARNING.

Include the **exception type name** in the message. That is what distinguishes "your
`[routing]` config names a missing provider" from "`ModelRegistry` moved and the import is
broken", and it is what the current message cannot express at all.

**(2) Narrow the `try`.** Move the six imports at `:2903-2908` **out** of the `try`, to the
top of the block (or to module scope if the import-linter contracts allow — check
`ARCHITECTURE.md`'s layering section first; `gateway` importing `core` is permitted, but
these are deliberately function-local, so keep them function-local and simply hoist them
above the `try`).

That single move means an `ImportError` — a broken install, a renamed module, a typo — now
raises loudly at boot instead of masquerading as "routing config problem, carry on". The
remaining `try` covers only the construction calls, which is what it was meant to guard.

If you want to narrow further, `except Exception` over the constructors is acceptable and
in keeping with the file's style — the imports are the important part.

## 6. Steps

1. **Write the regression test from §7 first.** Run it. Watch it fail.
2. Hoist the six imports at `orchestrator.py:2903-2908` above the `try:` at `:2902`.
3. Change `logger.debug` at `:2956` to `logger.warning`, bind the exception
   (`except Exception as exc:`) and include `type(exc).__name__` in the message.
4. Add `emit_runtime_event("routing.boot_failed", {...})` beside it, copying the shape at
   `:2954`.
5. Re-run the test.
6. Run `uv run python scripts/preflight.py --quick`, then the full gate.
7. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** a new `tests/test_routing_boot_failure.py`. (The ten existing `tests/test_routing_*.py`
  files all test the routing components themselves, not `boot_agent`'s wiring of them — no
  test anywhere mentions "Routing boot", verified by grep.)
- **Test name:** `test_routing_boot_failure_logs_at_warning`
- **It must assert:** using pytest's `caplog` fixture at `WARNING` level, that a genuine
  routing-construction failure produces a **WARNING** record. Assert on the captured record's
  `levelno`/`levelname` — the real logging output — not on a mocked logger.
- **It must FAIL before your fix** with: `AssertionError: assert [] != []` — i.e. no records
  are captured at WARNING, because the message is emitted at DEBUG.

The cheapest honest way to trigger a failure is to make one of the constructors raise:
monkeypatch `ModelRegistry.build` (or `ProviderRegistry.from_config`) to raise, then boot.
Booting a full agent in a test is heavy — check whether the existing `tests/test_routing_*.py`
files or `tests/conftest.py` already provide a lightweight `boot_agent` harness before
building one. If a full boot is impractical, assert the two properties that do not require
it:

1. `caplog` at WARNING captures a record when the guarded block raises (extract the block
   into a small helper if that is what it takes — but see §9 before refactoring).
2. **The static asymmetry is gone:** read `gateway/orchestrator.py`, locate the `except`
   arm, and assert it does not call `logger.debug`. A source-reading assertion is a weak
   test and you should prefer the behavioural one — but it is honest, it fails today, and it
   is better than no lock at all. Say which one you chose in the commit message.

```python
# sketch — adapt to the repo's existing fixtures
from __future__ import annotations

import logging

import pytest


def test_routing_boot_failure_logs_at_warning(caplog: pytest.LogCaptureFixture, monkeypatch) -> None:
    """A routing-layer boot failure must be visible at default log level.

    It was logged at logger.debug while the SUCCESS path logged at logger.info —
    a working boot was louder than a broken one, and a user whose [routing] config
    failed to build got a silently different (more expensive) product with no signal.
    """
    from hachi.core.routing.registry import ModelRegistry

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated routing registry failure")

    monkeypatch.setattr(ModelRegistry, "build", _boom)

    with caplog.at_level(logging.WARNING, logger="hachi.gateway.orchestrator"):
        ...  # boot a session with a [routing] section

    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "routing boot failure produced no WARNING record"
    assert any("Routing boot" in r.getMessage() for r in warnings)
    assert any("RuntimeError" in r.getMessage() for r in warnings), (
        "the exception type must be in the message — it is what distinguishes a config "
        "problem from an ImportError"
    )
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.
> The most likely cause of a false pass is `caplog.set_level(logging.DEBUG)` somewhere in a
> shared fixture — check `tests/conftest.py`.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists and failed before the fix.
- [ ] `grep -n "logger.debug" src/hachi/gateway/orchestrator.py` no longer matches inside the
      routing-boot `except` arm.
- [ ] The WARNING message contains the exception **type name**.
- [ ] A `routing.boot_failed` runtime event is emitted beside the log.
- [ ] The six imports at `:2903-2908` are **outside** the `try`, so an `ImportError` is no
      longer swallowed.
- [ ] `_model_router = None` on failure is **unchanged** — the fallback behaviour is correct;
      only its silence was wrong.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not make routing-boot failure fatal.** Falling back to the direct client is the
  correct, deliberate behaviour — `_model_router = None` is a documented back-compat path
  (see the comment at `:2896-2899`). The bug is that it happens *silently*, not that it
  happens. Raising here would turn a degraded session into no session.
- **Do not refactor `boot_agent`.** You are landing inside a 1,137-line function
  (`gateway/orchestrator.py:2557-3693`) that CF-6 already flags for decomposition. Extracting
  a `_build_routing()` helper is exactly the drift this section exists to prevent: it is a
  different task, with a different review burden, and it will collide with CF-6 work. Touch
  the `except` arm and the import placement. Nothing else.
- **Do not add new runtime-event categories or a new event-name convention.** Copy
  `emit_runtime_event("cost.routing_warning", {"message": …})` at `:2954`.
- **Do not "fix" the other bare `except Exception` blocks** you will see while reading this
  file. Note them and move on.
- Do not weaken, skip, or delete an existing test to go green — fix the code ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Targeted (Windows: `python -m pytest` per BB-1):

```bash
uv run pytest tests/test_routing_boot_failure.py tests/test_routing_compat.py \
              tests/test_routing_hot_reload.py tests/test_hot_path_routing.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — highest today is **BB-88**):

```markdown
### BB-N — A routing-layer boot failure silently disabled routing (logged at DEBUG, success logged at INFO)

- **Symptom:** a user configured `[routing]`, and Hachi ran every turn on the single default
  model as if the section were absent. No error, no warning — at default log level, nothing
  at all.
- **Root cause:** `gateway/orchestrator.py:2955-2960` caught every exception from the ~53-line
  routing-boot block at `logger.debug` and set `_model_router = None`. The success path one
  branch up logs at `logger.info` (`:2943`), so a working boot was strictly louder than a
  broken one. The `try` opened at `:2902` and wrapped six imports as well as the
  constructors, so `ImportError`/`AttributeError`/typos in that block were indistinguishable
  from a routing-config problem.
- **Fix:** promoted to `logger.warning` with the exception type in the message and
  `exc_info=True`; added a `routing.boot_failed` runtime event alongside (matching the
  existing `cost.routing_warning` pattern at `:2954`); hoisted the six imports out of the
  `try`. The `_model_router = None` fallback is unchanged — falling back is correct, being
  silent about it was not.
- **Avoid:** a failure must never be logged at a lower level than the corresponding success.
  And never wrap `import` statements in the same `try` as the logic they support — it turns
  every packaging or rename error into a false "your config is bad".
- **Locked by:** `tests/test_routing_boot_failure.py` — `test_routing_boot_failure_logs_at_warning`
```

## 12. Known traps

- **The review's path is wrong.** It says `core/orchestrator.py:2955-2960`. The file is
  `src/hachi/gateway/orchestrator.py`. There is no `core/orchestrator.py`.

- **`emit_runtime_event` is defined TWICE in this function**, at
  `gateway/orchestrator.py:2601` and again at `:2747` (the second carries
  `# type: ignore[misc]  # noqa: F811` — it is a deliberate shadow, and it is CF-6's
  "the same name does different things at different line numbers" finding). Both are above
  `:2902`, and the existing code at `:2954` already calls it from inside this very block, so
  your call is consistent with what is there. **Do not try to disambiguate or fix the
  shadowing** — that is CF-6, not this task.

- **`caplog` may be pre-configured.** If a shared fixture in `tests/conftest.py` sets the
  root level to DEBUG, your "fails before the fix" test will pass before the fix. Check, and
  scope `caplog.at_level(...)` to the `hachi.gateway.orchestrator` logger explicitly.

- **Booting an agent in a test is expensive.** Look for an existing lightweight boot harness
  before writing one. If none exists, §7 gives you a weaker but honest fallback assertion —
  use it and say so, rather than inventing a heavyweight fixture for a one-hour task.

- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend API
  types. You are not changing a route here — but you *are* adding a runtime event name, and
  if the frontend enumerates event names anywhere, grep `frontend/src` for
  `cost.routing_warning` to see whether `routing.boot_failed` needs a peer entry.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant because the
  guarded block touches `_shared.routing_store` at `:2928-2941`.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
