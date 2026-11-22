# T-47 · Lift `fastapi_app.py`'s 19 existing routers out of the `create_gateway_app` closure

|  |  |
|---|---|
| **Source finding** | CF-6 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) |
| **Depends on** | none — **fully independent, safe to run in parallel with everything else** |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High (needs design judgement — read §3.4 and §9) |
| **Files you will touch** | `src/hachi/gateway/routers/` (new package), `src/hachi/gateway/fastapi_app.py`, `src/hachi/gateway/deps.py` (new), `tests/test_gateway_router_extraction.py` (new) |

---

## 1. Brief

⚠️ **CF-6's framing is stale. `fastapi_app.py` already has 19 `APIRouter`s.** The task is
**not** "introduce APIRouters".

The real problem: **all 19 routers and all 100 routes are declared inside a single function,
`create_gateway_app` (`:441-3059`) — 2,619 lines, 86 % of the 3,059-line module.** Every route
handler is a closure over `control_plane`, `auth_token`, and ~a dozen other locals. Lift the
routers to module scope, replacing closure capture with explicit FastAPI dependency injection.

## 2. Why this matters

A router declared inside a factory cannot be imported, tested, or reviewed on its own. The
entire REST surface — 100 routes across 19 domains — is one indivisible function, so any route
change means opening a 2,619-line body, and two people touching unrelated domains conflict in
the same hunk. It is also why the module is 3,059 lines with only **7 top-level helpers**:
there is nowhere else for anything to live.

Framing this as "split into APIRouter modules" would send an implementer looking for routers
to create — and they are already there. **The work is converting implicit closure capture into
explicit dependency injection**, which is a different (and more delicate) job. That distinction
is the whole reason this spec exists.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The closure

`src/hachi/gateway/fastapi_app.py:441` —

```python
def create_gateway_app(
    control_plane: GatewayControlPlane,
    auth_token: str | None = None,
    *,
    bind_host: str | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
```

Body runs to `:3059` — **2,619 lines**, **86 %** of the module. `control_plane` alone is
referenced **93 times** inside it (`grep -c "control_plane\." src/hachi/gateway/fastapi_app.py`).

**Only 7 functions are at module scope**, and none is a route:

| Function | Line |
|---|---|
| `_is_loopback_host` | 53 |
| `_int_env` | 58 |
| `_parse_allowlist` | 65 |
| `_last_user_text` | 320 |
| `_lifespan` | 400 |
| `_error_response` | 411 |
| `_resolve_session_store` | 420 |

```bash
grep -n "^def \|^async def " src/hachi/gateway/fastapi_app.py
```

### 3.2 The 19 routers already exist

All declared inside the closure; all mounted at `:2996-3014` via `app.include_router(...)`.

**Extract largest-first** — the top two are 39 % of the surface.

| Router | Declared | Prefix | Routes |
|---|---|---|---:|
| `config` | `:715` | `/config` | **22** |
| `runtime_ops` | `:714` | *(none)* | **17** |
| `sessions` | `:713` | `/sessions` | 11 |
| `system` | `:712` | *(none)* | 6 |
| `integrations_router` | `:2089` | — | 6 |
| `authoring_router` | `:1947` | — | 6 |
| `voice_router` | `:2834` | `/voice` | 4 |
| `runs_router` | `:2508` | `/runs` | 4 |
| `memory_router` | `:1943` | — | 4 |
| `files_router` | `:2656` | `/files` | 4 |
| `skills_router` | `:1942` | — | 3 |
| `spend_router` | `:1950` | — | 2 |
| `setup` | `:716` | `/setup` | 2 |
| `openai_compat` | `:1593` | — | 2 |
| `interactions_router` | `:2914` | — | 2 |
| `approvals_router` | `:1869` | — | 2 |
| `og_router` | `:1946` | `/og` | 1 |
| `integrations_callback_router` | `:2096` | `/integrations` | 1 |
| `channels_router` | `:1818` | — | 1 |
| | | **Total** | **100** |

Regenerate:

```bash
grep -n "APIRouter(" src/hachi/gateway/fastapi_app.py
grep -oE "@(system|sessions|runtime_ops|config|setup|openai_compat|channels_router|approvals_router|skills_router|memory_router|og_router|authoring_router|spend_router|integrations_router|integrations_callback_router|runs_router|files_router|voice_router|interactions_router)\.(get|post|put|delete|patch)" \
  src/hachi/gateway/fastapi_app.py | sed 's/@//;s/\..*//' | sort | uniq -c | sort -rn
```

### 3.3 `runtime_ops` carries no prefix and should split further

Its 17 routes span five unrelated concerns:

```
/runtime/events                        │ 1
/runtime/mcp/inventory                 │
/runtime/mcp/register                  │ 5  → mcp
/runtime/mcp/{name}/enable             │
/runtime/mcp/{name}/disable            │
/runtime/mcp/{name}            [DELETE]│
/runtime/secrets               [POST]  │
/runtime/secrets               [GET]   │ 3  → secrets
/runtime/secrets/{name}        [DELETE]│
/jobs/active                           │ 2  → jobs
/jobs/failed                           │
/permissions/audit                     │ 1  → permissions
/subagents/reports                     │ 1  → subagents
/schedules                             │
/schedules/{schedule_id}       [DELETE]│ 4  → schedules
/schedules/{schedule_id}/enabled [PUT] │
/schedules/{schedule_id}/run-now       │
```

**Split it along those lines** as part of the extraction: `runtime_events`, `mcp`, `secrets`,
`jobs`, `permissions`, `subagents`, `schedules`. ⚠️ **The route *paths* must not change** —
only which router object owns them. `runtime_ops` has no `prefix=`, so each new router must
also have no prefix, or you will silently re-path everything under it.

### 3.4 ⚠️ The two closure captures you must replace — the second is security-critical

**(a) `control_plane` — 93 references.** Mechanical: replace with a FastAPI dependency.

**(b) `_require_auth` — a nested function at `:556` that closes over `auth_token` and
`_auth_enabled`.** All protected routers are built with it, at `:710`:

```python
    protected_dependencies = [Depends(_require_auth)]
```

```python
    sessions = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=protected_dependencies)
    runtime_ops = APIRouter(tags=["runtime"], dependencies=protected_dependencies)
    config = APIRouter(prefix="/config", tags=["config"], dependencies=protected_dependencies)
```

Its docstring at `:556` documents a security contract with four distinct modes (token set /
`HACHI_GATEWAY_NO_AUTH=1` / `bind_host=None` unit-test path / non-loopback hard error), and it
is **also called directly** inside handlers for session-ownership checks — `:776`, `:795`,
`:817`, `:953`, `:977`, `:997`, and more:

```python
        _check_session_ownership(session_id, _require_auth(request))
```

**Lifting a router to module scope means its `dependencies=` list is evaluated at import
time, before any `auth_token` exists.** Get this wrong and every protected route becomes
unauthenticated — a silent, total authentication bypass that no shape test would catch.

**This is the single highest-risk element of the task.** §5 specifies the required approach
and §7 specifies the test that must fail first.

### 3.5 What else the closure captures

Before you lift anything, enumerate every free variable each router's handlers read:

```bash
# Locals bound inside create_gateway_app — each is a candidate capture.
awk 'NR>=441 && NR<=3059' src/hachi/gateway/fastapi_app.py \
  | grep -nE "^    [a-z_][a-z_0-9]* = " | awk -F'[: ]' '{print $1+440, $2}'
```

Known so far: `control_plane`, `auth_token`, `_auth_enabled`, `_require_auth`,
`protected_dependencies`, `bind_host`, `frontend_dist`. Expect more. **Every one becomes
either a `Depends` provider or an argument to a router-factory function.**

## 4. Reproduce the failure — there is none. Read the code instead.

**This is a pure refactor. All 100 routes work.** There is no crash and no wrong output. Do
not invent a repro. Here is how to see the problem:

```bash
# 1. One function holds 86% of the module.
wc -l src/hachi/gateway/fastapi_app.py                                              # 3059
awk 'NR>=441 && NR<=3059' src/hachi/gateway/fastapi_app.py | wc -l                  # 2619

# 2. The routers ALREADY exist — CF-6's "introduce routers" framing is stale.
grep -c "APIRouter(" src/hachi/gateway/fastapi_app.py                               # 19

# 3. …but every one is declared inside the closure, so none is importable.
python -c "
from hachi.gateway import fastapi_app
print([n for n in dir(fastapi_app) if 'router' in n.lower()])"                       # []

# 4. Only 7 module-level functions exist, and none is a route.
grep -c "^def \|^async def " src/hachi/gateway/fastapi_app.py                       # 8 (incl. create_gateway_app)

# 5. The capture volume.
grep -c "control_plane\." src/hachi/gateway/fastapi_app.py                          # 93
```

**You will see now:** step 3 prints `[]` — not one router can be imported or tested in
isolation.
**You should see after the fix:** step 3 lists the extracted routers;
`awk 'NR>=441 …' | wc -l` on the new `create_gateway_app` is a few hundred lines of assembly,
not 2,619.

## 5. What "fixed" looks like

A `routers/` package of module-scope routers, and a `deps.py` providing what they used to
capture.

```python
# src/hachi/gateway/deps.py (new)
"""FastAPI dependency providers for the gateway.

Replaces closure capture in create_gateway_app. The app stores its
collaborators in `app.state`; these providers read them per-request,
so routers can be declared at module scope.
"""

from __future__ import annotations

from fastapi import Depends, Request

from hachi.gateway.control_plane import GatewayControlPlane


def get_control_plane(request: Request) -> GatewayControlPlane:
    return request.app.state.control_plane


def require_auth(request: Request) -> str | None:
    """Bearer-token check. Reads config from app.state, not from a closure.

    Preserves ALL FOUR modes documented at fastapi_app.py:556 — see T-47 §3.4.
    Returns the sha256 caller digest, or None in no-auth / unit-test mode.
    """
    ...


CallerHash = Annotated[str | None, Depends(require_auth)]
```

```python
# src/hachi/gateway/routers/config.py (new) — 22 routes
from fastapi import APIRouter, Depends

from hachi.gateway.deps import get_control_plane, require_auth

router = APIRouter(prefix="/config", tags=["config"], dependencies=[Depends(require_auth)])


@router.get("/providers")
def list_providers(cp=Depends(get_control_plane)):
    return cp.list_providers()
```

```python
# fastapi_app.py — after
def create_gateway_app(control_plane, auth_token=None, *, bind_host=None, frontend_dist=None):
    app = FastAPI(lifespan=_lifespan)
    app.state.control_plane = control_plane
    app.state.auth_token = auth_token
    app.state.auth_enabled = _compute_auth_enabled(auth_token, bind_host)
    ...
    for router in ALL_ROUTERS:
        app.include_router(router)
    return app
```

**Decisions already made — do not re-litigate:**

1. **`app.state` + `Depends`, not module globals.** A module-level `_CONTROL_PLANE` would make
   two apps in one process share a control plane — which the test suite creates routinely.
   `request.app.state` is per-app and is the documented FastAPI mechanism.
2. **`require_auth` moves to `deps.py` and reads from `app.state`.** It must preserve all four
   modes from the `:556` docstring **verbatim in behaviour**. Transcribe the body; do not
   re-derive the logic. Its direct call sites (`:776`, `:795`, `:817`, `:953`, `:977`, `:997`,
   …) become `Depends`-injected parameters — but only after the router they live in has moved.
3. **Route paths, methods, status codes, request models, and response models do not change.**
   **BB-4 applies if any of them do**; ideally the exported OpenAPI spec is byte-identical.
   That is the acceptance test (§7).
4. **`runtime_ops` splits into 7 prefix-less routers** (§3.3). Every other router keeps its
   identity and its `prefix=`.
5. **Extraction order is largest-first:** `config` (22) → `runtime_ops` (17, split) →
   `sessions` (11) → the rest. The first two are 39 % of the surface and prove the pattern.
6. **`create_gateway_app` keeps its signature and its name.** Same 5 parameters, same startup
   guards, same return type. Callers do not change.
7. **The startup guards stay in `create_gateway_app`.** The `bind_host` / `NO_AUTH` /
   non-loopback hard errors (documented at `:441-460`) are app-assembly concerns, not router
   concerns. Do not scatter them into `deps.py`.
8. **Zero behaviour change.**

## 6. Steps

**Six commits. The OpenAPI spec is your invariant throughout.**

### Commit 1 — pin the contract (no source change)

1. Export the current OpenAPI spec and commit it as a test fixture:
   ```bash
   uv run hachi gateway export-openapi > tests/fixtures/openapi_baseline.json   # confirm the real command
   ```
   If no such command exists, generate it in-test from `create_gateway_app(...).openapi()`.
2. Write the tests from §7. They must pass.
3. Record full-suite baseline counts.

### Commit 2 — `deps.py`, unused

4. Create `src/hachi/gateway/deps.py` with `get_control_plane` and `require_auth`.
5. In `create_gateway_app`, populate `app.state` (`control_plane`, `auth_token`,
   `auth_enabled`) **and leave the existing closure intact**. Nothing consumes `deps.py` yet.
6. Add the auth-parity test from §7 comparing `deps.require_auth` against the closure's
   `_require_auth` across all four modes. **This test is the gate on commit 3.**

### Commits 3–6 — lift routers, largest-first

Per router: create `src/hachi/gateway/routers/<name>.py`, **move the handler bodies verbatim**,
replace each captured name with a `Depends` parameter, delete the in-closure declaration, and
add the module-scope router to the `include_router` list.

| Commit | Routers | Routes |
|---|---|---:|
| 3 | `config` | 22 |
| 4 | `runtime_ops` → `runtime_events`, `mcp`, `secrets`, `jobs`, `permissions`, `subagents`, `schedules` | 17 |
| 5 | `sessions`, `system`, `setup` | 19 |
| 6 | the remaining 14 routers | 42 |

After **every** commit:

```bash
uv run python scripts/preflight.py --quick
# and the invariant that matters:
pytest tests/test_gateway_router_extraction.py::test_openapi_spec_is_unchanged -q
```

⚠️ **If the OpenAPI diff is non-empty at any point, stop and fix it before moving on.** A
drift caught three commits later is a bisect through 60 relocated routes.

### After the last router

7. Confirm `create_gateway_app` is a few hundred lines of assembly.
8. Confirm no `APIRouter(` remains inside it.

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law), applied to a
refactor.** There is no bug, so the instrument is a **characterization test**: pin the exact
HTTP contract *before* the move, so the relocation is provably behaviour-neutral.

- **File:** `tests/test_gateway_router_extraction.py` (new)
- **Test names:** `test_openapi_spec_is_unchanged`, `test_auth_parity_across_all_four_modes`,
  `test_protected_routes_reject_a_missing_token`
- **They must assert:** the real generated OpenAPI document and real HTTP responses from a
  `TestClient` — not a mock's return value.
- **`test_openapi_spec_is_unchanged` PASSES before and must still pass after** — that is what
  characterization means, and it is the single most valuable test in this task.
- **`test_protected_routes_reject_a_missing_token` must FAIL** the moment a router is lifted
  without its auth dependency — that is the bypass it exists to catch.

```python
# sketch — adapt to the repo's existing fixtures
import json
from pathlib import Path

from fastapi.testclient import TestClient

BASELINE = Path(__file__).parent / "fixtures" / "openapi_baseline.json"


def test_openapi_spec_is_unchanged(control_plane) -> None:
    """The 100-route contract must survive the move byte-for-byte.

    Any path, method, status code, or model change is out of scope for T-47
    and triggers BB-4 (spec + frontend types must be regenerated).
    """
    from hachi.gateway.fastapi_app import create_gateway_app

    spec = create_gateway_app(control_plane).openapi()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert sorted(spec["paths"]) == sorted(baseline["paths"]), "route set changed"
    for path, methods in baseline["paths"].items():
        assert sorted(spec["paths"][path]) == sorted(methods), f"methods changed on {path}"


def test_protected_routes_reject_a_missing_token(control_plane) -> None:
    """Every protected route must still 401 without a bearer token.

    THE bypass guard: a router lifted to module scope loses its
    `dependencies=[Depends(_require_auth)]` silently, and no shape test
    would notice. See T-47 §3.4.
    """
    from hachi.gateway.fastapi_app import create_gateway_app

    app = create_gateway_app(control_plane, auth_token="s3cret", bind_host="127.0.0.1")
    client = TestClient(app)

    protected = [
        p for p in app.openapi()["paths"]
        if not p.startswith(("/health", "/docs", "/openapi"))   # adapt to the real public set
    ]
    assert len(protected) > 80, "sanity: expected most of the 100 routes to be protected"

    unguarded = [p for p in protected if client.get(p).status_code not in (401, 403, 405)]
    assert unguarded == [], f"routes served without auth: {unguarded}"


def test_auth_parity_across_all_four_modes(monkeypatch) -> None:
    """deps.require_auth must behave identically to the closure's _require_auth.

    Four modes from the docstring at fastapi_app.py:556:
      (1) token configured, valid credential      → caller digest
      (2) token configured, missing/bad           → 401
      (3) HACHI_GATEWAY_NO_AUTH=1                 → None, no enforcement
      (4) auth_token=None and bind_host=None      → None, no enforcement (unit-test path)
    """
    ...
```

> Generate `openapi_baseline.json` **once, from `main`, before any edit.** A baseline captured
> after the first router moves bakes in whatever that move broke.

## 8. Acceptance criteria

- [ ] The characterization tests from §7 exist; the OpenAPI baseline was captured from
      unmodified `main`.
- [ ] `test_openapi_spec_is_unchanged` passes at **every** commit, not only the last.
- [ ] `python -c "from hachi.gateway import routers; print(len(routers.ALL_ROUTERS))"` reports
      the full set, and each router is importable without calling `create_gateway_app`.
- [ ] `grep -c "APIRouter(" src/hachi/gateway/fastapi_app.py` → **0** (all moved).
- [ ] `runtime_ops` is split into 7 prefix-less routers and **no route path changed**
      (proven by the OpenAPI test).
- [ ] `deps.require_auth` passes the four-mode parity test; no protected route is reachable
      without a token.
- [ ] `create_gateway_app` keeps its 5-parameter signature and its startup guards.
- [ ] No module-level mutable app state — collaborators live on `app.state` (§5 decision 1).
      Verify: two apps constructed in one process with different control planes do not
      interfere.
- [ ] Six commits, each green on its own.
- [ ] Full-suite counts identical to the commit-1 baseline. Report both.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not change behaviour while moving code.** Primary boundary. No route path, method,
  status code, request model, response model, or error envelope changes. **This is a pure
  move.**
- Do not "introduce APIRouters" — they already exist (§3.2). If your plan starts there, re-read
  §1.
- Do not fix the route-grammar inconsistencies CF-5 identifies
  (`POST /runtime/mcp/{name}/enable` vs `PUT /schedules/{id}/enabled`,
  `/config/provider` vs `/config/providers`). They are real, they are ugly, and they are a
  **breaking API change** tracked separately. Moving a badly-named route is in scope;
  renaming it is not.
- Do not add versioning, do not touch the `/v1/*` OpenAI facade's shape.
- Do not use module-level globals for the control plane (§5 decision 1).
- Do not move the startup guards out of `create_gateway_app` (§5 decision 7).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- **Do not run a repo-wide `ruff format`** ([CLAUDE.md](../../../../CLAUDE.md) Rule 3). With
  ~2,600 lines relocating, formatter noise would make the diff unreviewable.
- Do not add a runtime dependency without asking. FastAPI's `Depends` is already in use.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
uv run python scripts/preflight.py --quick   # inner loop, after EVERY router
uv run python scripts/preflight.py           # before you call it done
uv run lint-imports                          # the new routers/ package must not break layering
```

Plus the invariant, after every commit:

```bash
pytest tests/test_gateway_router_extraction.py -q
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N`):

```markdown
### BB-N — lifting a FastAPI router out of a factory closure silently drops its auth dependency

- **Symptom:** `create_gateway_app` (`fastapi_app.py:441-3059`) declared all 19 routers and
  100 routes inside its body, with `dependencies=[Depends(_require_auth)]` where
  `_require_auth` was a nested function closing over `auth_token`. Moving a router to module
  scope evaluates that `dependencies=` list at import time, before any token exists —
  producing an unauthenticated route with no error and no failing shape test.
- **Root cause:** Closure capture used as dependency injection. The auth config was only
  reachable from inside the factory, so the guard could not be expressed at module scope.
- **Fix:** Moved collaborators to `app.state` and re-expressed `require_auth` as a
  request-scoped `Depends` provider in `gateway/deps.py`, preserving all four documented
  auth modes.
- **Avoid:** When lifting a router out of a factory, assert that every protected path still
  returns 401 without a token — an OpenAPI-shape test will not catch a missing dependency.
- **Locked by:** `tests/test_gateway_router_extraction.py` —
  `test_protected_routes_reject_a_missing_token`
```

## 12. Known traps

- **The auth-bypass trap (§3.4).** The highest-severity risk in this task. A lifted router
  with a stale or missing `dependencies=` list serves protected data to anyone, and every
  route-shape test still passes.
- **The stale-framing trap.** CF-6 says "split into APIRouter modules"; they exist. Wasted
  effort otherwise.
- **The prefix trap (§3.3).** `runtime_ops` has **no** `prefix=`. Giving its successor routers
  a prefix silently re-paths 17 routes. The OpenAPI test catches this — which is why it runs
  on every commit.
- **Direct `_require_auth(request)` calls.** At least six handlers call it inline for
  session-ownership checks (`:776`, `:795`, `:817`, `:953`, `:977`, `:997`). Those must be
  converted alongside their router, not before it.
- **BB-4:** any gateway route change ⇒ regenerate the OpenAPI spec **and** the frontend API
  types, or CI fails. **This task should change none.** If `test_openapi_spec_is_unchanged`
  fails, you have exceeded scope — do not regenerate the spec to make it pass.
- **Two apps, one process.** The test suite constructs multiple apps. Module-level state
  shared between them produces order-dependent failures that reproduce only in a full run.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — `_resolve_session_store`
  (`:420`) already handles this. Do not "simplify" it on the way past.
