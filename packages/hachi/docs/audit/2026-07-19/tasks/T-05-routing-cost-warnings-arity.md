# T-05 · Fix the missing `registry` argument that makes routing cost warnings always empty

|  |  |
|---|---|
| **Source finding** | CF-1 #2 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) · [CORRECTIONS.md](CORRECTIONS.md) §11 |
| **Severity** | P1 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | [T-13](T-13-feature-liveness-smoke.md) |
| **Effort** | ~30 minutes — the smallest task in this pack |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/core/routing/validate.py`, `tests/test_routing_validate.py`, `docs/bug-bank.md` |

---

## 1. Brief

`validate_routing()` calls `policy.costly_capability_warnings()` with **no arguments**,
but that method requires a positional `registry` argument. Every call raises
`TypeError`, which is swallowed by a bare `except Exception: pass`, so
`RoutingValidationResult.warnings` is **always `[]`** — the BB-30 "every chat turn is
routed to the priciest model" guard has never fired on the routing validate/apply
endpoint since the function was written.

The fix is one word. When you are done, `warnings` is populated, and the swallow that
hid this for the feature's entire life is a `logger.warning`.

## 2. Why this matters

BB-30 is a real, previously-hit cost bug: a user whose `[routing.capabilities]` pins
`reasoning` to an expensive model while `default_model` is cheap pays ~16× on every
turn, silently. The guard that surfaces it exists and is correct — it just never runs on
the path where a user is *about to commit* a routing change. That is precisely the
moment a warning is worth anything.

**Bound the change with this fact:** `gateway/orchestrator.py:2952` calls the same
method **correctly**, so boot-time warnings do work today. Only the validate/apply
endpoint path is dead. You are not repairing the guard; you are repairing one call site.
(The *other* silent failure in that same `try` block — routing boot failing at DEBUG
level, `orchestrator.py:2955-2960` — is owned by
[T-26](T-26-routing-boot-failure-visible.md). Do not touch it here.)

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The broken call

`src/hachi/core/routing/validate.py:78-84`:

```python
    # Advisory: costly capability overrides (BB-30).
    try:
        warnings.extend(policy.costly_capability_warnings())
    except Exception:
        pass

    return RoutingValidationResult(ok=not issues, issues=issues, warnings=warnings)
```

### 3.2 The signature it violates

`src/hachi/core/routing/policy.py:56`:

```python
    def costly_capability_warnings(self, registry: ModelRegistry) -> list[str]:
```

`registry` is positional and required. The call in 3.1 is a **guaranteed `TypeError` on
every invocation**, caught by the `except Exception` on the next line.

### 3.3 The argument is already in scope

`src/hachi/core/routing/validate.py:32-37` — `registry` is the **first parameter** of the
enclosing function:

```python
def validate_routing(
    registry: ModelRegistry,
    policy: RoutingPolicy,
    *,
    providers: Any = None,  # ProviderRegistry | None — unused today, reserved for future
) -> RoutingValidationResult:
```

The function's own docstring at `:45-48` already promises the behaviour:

```python
    Advisory warnings (non-blocking):
      - Re-uses ``policy.costly_capability_warnings()`` (BB-30 guard) to flag
        any explicit per-capability override that prices orders-of-magnitude
        more than the default model.
```

### 3.4 The correct call site, for contrast

`src/hachi/gateway/orchestrator.py:2949-2954` — this one works:

```python
        # Cost-governance guard (BB-30): surface the silent "every chat turn routed to
        # the priciest model" trap loudly at boot instead of letting it hide in the
        # routing table. Never changes routing — an explicit choice is respected.
        for _cost_warning in _routing_policy.costly_capability_warnings(_model_registry):
            logger.warning(_cost_warning)
            emit_runtime_event("cost.routing_warning", {"message": _cost_warning})
```

### 3.5 The consumer chain (so you know what starts working)

`validate_routing` is reached from:

- `src/hachi/cli/main.py:2510` — `_InProcessGatewayRuntime.validate_routing`, which
  imports it at `:2518`.
- `src/hachi/gateway/control_plane.py:1225-1240` — `GatewayControlPlane.validate_routing`,
  which falls back to importing it directly at `:1240` when no handler is attached.
- `src/hachi/gateway/fastapi_app.py:1564` — the REST route.

### 3.6 Why it survived

`tests/test_routing_validate.py:82-85` never invokes the function:

```python
    def test_validation_result_has_both_fields(self) -> None:
        result = RoutingValidationResult(ok=True, issues=["a"], warnings=["w"])
        assert result.issues == ["a"]
        assert result.warnings == ["w"]
```

It constructs the **result dataclass** by hand. `tests/test_routing_hot_reload.py:241-283`
*does* call `validate_routing()` (five times), but every case uses a single-model
registry and never asserts anything about `warnings` — with one model there is no
costlier override to flag, so the empty list looks correct.

## 4. Reproduce the failure

Directly reproducible:

```bash
uv run python -c "from hachi.core.routing.policy import RoutingPolicy; RoutingPolicy(default_model='m').costly_capability_warnings()"
```

**You will see now:**

```
TypeError: RoutingPolicy.costly_capability_warnings() missing 1 required positional argument: 'registry'
```

**You should see after the fix:** the same `TypeError` from this command (the *method*
signature is unchanged and correct — do not "fix" it by defaulting `registry`). What
changes is that `validate_routing()` now passes it. The end-to-end proof is the §7 test:
a costly override must produce a non-empty `warnings` list.

## 5. What "fixed" looks like

```python
    # Advisory: costly capability overrides (BB-30).
    try:
        warnings.extend(policy.costly_capability_warnings(registry))
    except Exception:
        logger.warning(
            "validate_routing: cost-governance warnings could not be computed; "
            "the BB-30 costly-override guard is not covering this validation",
            exc_info=True,
        )
```

`validate.py` has no logger today — add the two standard lines at the top of the module,
matching the convention used across `src/hachi/core/`:

```python
import logging

logger = logging.getLogger(__name__)
```

Keep the `try`/`except`: the routing validate endpoint must not 500 because a pricing
lookup blew up. But the swallow becomes loud. **Both halves are required by this task's
Definition of Done.**

## 6. Steps

1. Write the regression test from §7 first. Run it. Watch it fail with
   `assert [] != []`.
2. Add `import logging` + `logger = logging.getLogger(__name__)` to
   `src/hachi/core/routing/validate.py`.
3. Change `policy.costly_capability_warnings()` →
   `policy.costly_capability_warnings(registry)` at `:80`.
4. Replace `except Exception: pass` at `:81-82` with the `logger.warning` in §5.
5. Run the test. Watch it pass.
6. Run `uv run python scripts/preflight.py`. Report real counts.
7. Add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_routing_validate.py` (existing)
- **Test name:** `test_costly_capability_override_produces_a_warning`
- **It must assert:** `result.warnings` is non-empty and names the pinned model — i.e.
  the *observed output of `validate_routing()`*, not a hand-built
  `RoutingValidationResult`.
- **It must FAIL before your fix** with:
  `AssertionError: assert [] != []` (or `assert 0 > 0` if you assert on `len`).

The existing `_reg()` helper at `tests/test_routing_validate.py:12-24` builds descriptors
**without pricing**, and `costly_capability_warnings` returns early when
`_input_price(default_model)` is `None` (`policy.py:80-82`). Your test needs a registry
with real `Pricing` on both models, and both must advertise `Capability.REASONING`
(the guard skips unless `default_model in registry.by_capability(cap)` — `policy.py:93-98`).
The threshold is `ratio >= 3.0` (`policy.py:100`).

```python
# sketch — adapt to the repo's existing fixtures
from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing
from hachi.core.routing.policy import RoutingPolicy
from hachi.core.routing.registry import ModelRegistry
from hachi.core.routing.validate import validate_routing


def _priced_reg() -> ModelRegistry:
    reg = ModelRegistry()
    for mid, price in (("cheap-model", 0.15), ("pricey-model", 2.50)):  # ~16x
        reg.register(
            ModelDescriptor(
                id=mid,
                provider="anthropic",
                capabilities=frozenset({Capability.REASONING}),
                context_window=200_000,
                max_output=8_192,
                pricing=Pricing(input_per_mtok=price, output_per_mtok=price * 4),
            )
        )
    return reg


def test_costly_capability_override_produces_a_warning() -> None:
    policy = RoutingPolicy(
        default_model="cheap-model",
        capabilities={"reasoning": ["pricey-model"]},
    )
    result = validate_routing(_priced_reg(), policy, providers=None)

    assert result.ok, "a costly override is advisory, never blocking"
    assert result.warnings, (
        "BB-30 cost guard produced no warning — costly_capability_warnings() was "
        "never actually invoked by validate_routing()"
    )
    assert any("pricey-model" in w for w in result.warnings)
```

> If your test passes before you write the fix, the test is wrong. Do not proceed.

Sanity-check your registry first: run
`RoutingPolicy(...).costly_capability_warnings(reg)` **directly** in a scratch REPL and
confirm it returns a non-empty list. If it does not, your fixture is failing one of the
guard's preconditions (pricing present, default model capable, ratio ≥ 3) and your test
would pass-after-fix for the wrong reason.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix.
- [ ] `grep -n "costly_capability_warnings()" src/` returns **no** hits (i.e. no
      zero-arg call remains anywhere).
- [ ] `validate_routing()` on a costly-override policy returns non-empty `warnings`.
- [ ] The `except Exception: pass` in `validate.py` is now `logger.warning(..., exc_info=True)`.
- [ ] `gateway/orchestrator.py:2952` is untouched (it was already correct).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not give `registry` a default value** on `costly_capability_warnings`. That would
  make the broken zero-arg call legal and re-hide the bug forever. The method signature
  is correct; the call site was wrong.
- **Do not surface warnings in the UI.** `RoutingValidationResult.warnings` already flows
  out through `fastapi_app.py:1564`; whether the routing settings screen *renders* them
  is a frontend task and is not this change. Note it, do not build it.
- **Do not touch `providers: Any = None`.** It is documented as reserved
  (`validate.py:36`) and deleting an unused-but-declared parameter is a contract change
  (CLAUDE.md Rule 3).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2). In particular leave
  `test_validation_result_has_both_fields` alone; it is a weak test, not a wrong one.
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
# Windows: if the pytest .exe shim fails with OS error 4551, use `python -m pytest` (BB-1)
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) at the next free `BB-N`.
*(Highest at time of writing: **BB-88**. Sibling Wave-1 tasks also append — re-check with
`grep -n '^### BB-' docs/bug-bank.md | tail -1` and do NOT hardcode a number.)*

```markdown
### BB-N — Routing validation never returned a cost warning (arity error swallowed since inception)

- **Symptom:** `POST` to the routing validate/apply endpoint always returned
  `warnings: []`, even for a config that pins `reasoning` to a model ~16× the price of
  `default_model` — exactly the BB-30 trap the guard was written to catch.
- **Root cause:** `core/routing/validate.py` called
  `policy.costly_capability_warnings()` with no arguments, but the method requires a
  positional `registry` (`core/routing/policy.py:56`). Every call raised `TypeError`
  into a bare `except Exception: pass`, so the warnings list was unconditionally empty.
  `registry` was already in scope — it is `validate_routing`'s first parameter.
  `gateway/orchestrator.py` called the same method correctly, so boot-time warnings
  worked and masked the gap.
- **Fix:** passed `registry` at the call site and replaced the bare swallow with
  `logger.warning(..., exc_info=True)`.
- **Avoid:** never wrap a *single* call in `except Exception: pass` — an arity error is
  indistinguishable from "no warnings" and survives forever. A test that constructs the
  result dataclass by hand does not test the function that builds it.
- **Locked by:** `tests/test_routing_validate.py` —
  `test_costly_capability_override_produces_a_warning`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-30** is the bug this guard exists for — read it before writing the test so your
  fixture reproduces the real shape (cheap default + expensive capability pin).
- `costly_capability_warnings` has **three** early-return guards
  (`policy.py:80-98`): no/zero default price, resolved model equals default, and
  `default_model` not in `registry.by_capability(cap)`. A fixture that trips any of them
  returns `[]` and your test will look like it "passes" the wrong way.
- Only `Capability.REASONING` and `Capability.CODING` are scanned (`policy.py:84`).
- `ModelRegistry.pricing_for_model` does longest-prefix matching
  (`registry.py:72-89`) — do not name your fixture models so one is a prefix of the
  other (e.g. `"model"` and `"model-pro"`) or the price lookup will surprise you.
