# T-37 · Put the error envelope in the OpenAPI spec

> **Purely additive. No runtime behaviour changes.** Nothing about what the gateway returns at runtime
> is altered — you are declaring a response shape the code has been emitting all along. That makes this
> a good first task in the pack: small, mechanical, fully verifiable, and its root cause is already
> identified down to a single missing keyword.

|  |  |
|---|---|
| **Source finding** | CF-5 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none |
| **Blocks** | nothing (but pairs naturally with [T-38](T-38-openapi-pilot-og-domain.md)) |
| **Effort** | ~half a day |
| **Difficulty** | Low (mechanical) |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `openapi/hachi-openapi.json`, `frontend/src/lib/data/schema.d.ts`, `tests/` (one new test) |

---

## 1. Brief

The gateway has a first-class error envelope — `ErrorResponse` = `{code, message, details}` — emitted
by seven exception handlers and twenty-one in-route returns. It is **absent from the OpenAPI document
entirely**: `components.schemas` has 41 entries and none of them is `ErrorResponse`. The cause is
mechanical and exact: **not one route in the file declares a `responses=` entry**, so FastAPI never
learns the schema exists. When you are done, `ErrorResponse` appears in the spec and the error
responses of the gateway's routers are declared, so a generated client knows what an error looks like.

## 2. Why this matters

A generated client that does not know the error shape guesses — and guesses wrong. This is already
happening in-repo: `frontend/src/lib/data/client.ts:104-121` (`parseError`) reads `code` / `message` /
`details` from the body, and when it gets Starlette's `{"detail": ...}` instead it finds no `message`
and silently falls back to a generic `API GET /path → 500` string. Users see "something failed" where
the backend had a specific, actionable message. The spec is also the thing CI diff-gates on every
build; a contract that omits the single most commonly-returned shape in the API is not a contract. Note
what this task is **not**: it is not a wire-format change. Do not "unify" the error shape while you are
here — §9 explains why that is a separate, breaking decision.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The envelope exists and is fully typed — `src/hachi/gateway/fastapi_app.py:69-72`

```python
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
```

Emitted through one helper, `src/hachi/gateway/fastapi_app.py:411-417`:

```python
def _error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(code=code, message=message, details=details).model_dump(mode="json"),
    )
```

### 3.2 Seven exception handlers use it

| Line | Handler | Emits |
|---|---|---|
| `:548` | `@app.exception_handler(_AuthRequired)` | `_error_response` at `:550` |
| `:604` | `@app.exception_handler(SessionExpiredError)` | `:606` |
| `:613` | `@app.exception_handler(GatewayProtocolError)` | `:615` |
| `:621` | `@app.exception_handler(GatewayUnavailableError)` | `:625` |
| `:644` | `@app.exception_handler(_anthropic.APIStatusError)` | `:660`, `:666` |
| `:672` | `@app.exception_handler(RequestValidationError)` | `:676` |
| `:683` | `@app.exception_handler(Exception)` | `:699` |

### 3.3 …and **21 in-route returns** use it directly

Beyond the handlers, routes return the envelope inline at `:2144`, `:2149`, `:2151`, `:2229`, `:2233`,
`:2262`, `:2266`, `:2269`, `:2277`, `:2282`, `:2289`, `:2378`, `:2381`, `:2481`, `:2485`, `:2488`
(integrations/connectors), `:2853`, `:2856`, `:2883`, `:2886` (voice), and `:2908` (config write).

> **Enrichment beyond the audit brief:** the review framed this as "custom handlers vs. HTTPException".
> The verified picture is that the envelope is *also* the deliberate in-route return style in four
> subsystems. It is not a fallback — it is the house style, used 28 times, and still undeclared.

### 3.4 Meanwhile 46 sites return a different shape

```
$ grep -c "raise HTTPException" src/hachi/gateway/fastapi_app.py
46
```

Each returns Starlette's `{"detail": ...}` — a different shape from `{code, message, details}`. The
review said "~30"; the verified count is **46**. Both shapes are live in the same file today. **Do not
convert them in this task** (§9).

### 3.5 The spec has neither — `openapi/hachi-openapi.json`

```
openapi 3.1.0
paths 87
schemas 41
has ErrorResponse: False
```

The only error-ish schemas present are FastAPI's auto-generated `HTTPValidationError` / `ValidationError`.

### 3.6 The root cause, exactly — zero `responses=` declarations

```
$ grep -c "responses=" src/hachi/gateway/fastapi_app.py
0
```

**Not one route or router in the 3,000-line file declares an error response.** FastAPI builds
`components.schemas` from the models it can *see* — request bodies, `response_model=`, and `responses=`.
`ErrorResponse` is only ever constructed inside a function body and serialised into a bare
`JSONResponse`, so FastAPI has no way to know it exists. That is the entire bug, and it is why the fix
is additive: you are telling the framework about a shape the code already returns.

### 3.7 The 19 routers, where the declaration goes

`src/hachi/gateway/fastapi_app.py`: `:712` `system`, `:713` `sessions`, `:714` `runtime_ops`,
`:715` `config`, `:716` `setup`, `:1593` `openai_compat`, `:1818` `channels_router`, `:1869`
`approvals_router`, `:1942` `skills_router`, `:1943` `memory_router`, `:1946` `og_router`, `:1947`
`authoring_router`, `:1950` `spend_router`, `:2089` `integrations_router`, `:2096`
`integrations_callback_router`, `:2508` `runs_router`, `:2656` `files_router`, `:2834` `voice_router`,
`:2914` `interactions_router`. Example shape today:

```python
    sessions = APIRouter(prefix="/sessions", tags=["sessions"], dependencies=protected_dependencies)
```

`APIRouter` accepts a `responses=` mapping that applies to every route it carries — one edit per
router, not one per route.

### 3.8 The consumer that already assumes the envelope — `frontend/src/lib/data/client.ts:104-121`

```typescript
async function parseError(res: Response, method: string, path: string): Promise<ApiError> {
  let code: string | undefined;
  let message = `API ${method} ${path} → ${res.status}`;
  let details: unknown;
  try {
    const body = await res.json();
    // Gateway ErrorResponse: { code, message, details }
    if (body && typeof body === "object") {
      code = (body as Record<string, unknown>).code as string | undefined;
      const m = (body as Record<string, unknown>).message;
      if (typeof m === "string" && m) message = m;
      details = (body as Record<string, unknown>).details;
    }
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return new ApiError(message, res.status, code, details);
}
```

The frontend already hand-mirrors the envelope. Its `ApiError` class is at `client.ts:46-57`.

## 4. Reproduce the failure

Fully reproducible, no server needed — the spec is a checked-in file.

```bash
cd /d/OpenGigantic/hachi

# 1. The envelope is absent from the spec
python -c "import json;d=json.load(open('openapi/hachi-openapi.json'));print('ErrorResponse in schemas:', 'ErrorResponse' in d['components']['schemas']);print('schema count:', len(d['components']['schemas']))"

# 2. The root cause: nothing declares an error response
grep -c "responses=" src/hachi/gateway/fastapi_app.py

# 3. But the envelope is emitted 28 times
grep -c "_error_response(" src/hachi/gateway/fastapi_app.py

# 4. And a competing shape is raised 46 times
grep -c "raise HTTPException" src/hachi/gateway/fastapi_app.py
```

**You will see now:**
```
ErrorResponse in schemas: False
schema count: 41
0
29        # 28 call sites + the definition itself
46
```

**You should see after the fix:** `ErrorResponse in schemas: True`, `schema count: 42`, and a non-zero
`responses=` count. The `_error_response` and `HTTPException` counts are **unchanged** — this task adds
declarations, it does not move any code between the two shapes.

## 5. What "fixed" looks like

`ErrorResponse` is in `components.schemas`, and the gateway's routers declare the error responses they
actually return, so a generated client can type them.

Define one shared mapping next to the routers and pass it to each `APIRouter`:

```python
    # T-37: the gateway's error envelope (_error_response → ErrorResponse) is returned
    # by 7 exception handlers and 21 in-route returns, but FastAPI only puts a model in
    # components.schemas when a route DECLARES it. Declaring it once per router makes
    # the envelope part of the published contract.
    _ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Missing or invalid bearer token"},
        403: {"model": ErrorResponse, "description": "Caller does not own this session"},
        404: {"model": ErrorResponse, "description": "Resource not found"},
        500: {"model": ErrorResponse, "description": "Unhandled server error"},
        503: {"model": ErrorResponse, "description": "Runtime unavailable"},
    }

    sessions = APIRouter(
        prefix="/sessions",
        tags=["sessions"],
        dependencies=protected_dependencies,
        responses=_ERROR_RESPONSES,
    )
```

**Design decisions, made here so you do not have to make them:**

- **Declare per router, not per route.** 19 edits instead of ~100, and it cannot drift route-by-route.
- **Use concrete status codes, not the `"4XX"` wildcard.** OpenAPI 3.1 permits ranges, but tooling
  support is uneven and `openapi-typescript` output is cleaner with explicit codes. The set above
  covers what the seven handlers and 21 in-route returns actually emit — verify against §3.2/§3.3
  rather than copying blindly.
- **Do not add `422`.** FastAPI already auto-generates it as `HTTPValidationError`; overriding it would
  contradict the `RequestValidationError` handler at `:672` and produce a confusing diff.
- **`system` (`:712`) is the one router without `dependencies=protected_dependencies`.** Its `/health`
  and `/readiness` routes are unauthenticated, so `401` does not apply to it — give it a reduced
  mapping rather than the shared one.

The measurable outcome: `openapi/hachi-openapi.json` gains an `ErrorResponse` schema (41 → 42), and
`frontend/src/lib/data/schema.d.ts` regenerates with it available under `components["schemas"]["ErrorResponse"]`.

## 6. Steps

1. Write the regression test from §7. **Run it. Watch it fail.**
2. Add `_ERROR_RESPONSES` next to the router definitions in `src/hachi/gateway/fastapi_app.py`
   (just above `:712`), with the comment from §5 explaining why it exists.
3. Add `responses=_ERROR_RESPONSES` to each of the 18 protected routers listed in §3.7.
4. Give `system` (`:712`) a reduced mapping without `401`.
5. **BB-4:** regenerate the spec and the frontend types (§12).
6. Re-run the test. Watch it pass.
7. Confirm the diff is additive only: `git diff openapi/hachi-openapi.json` should show a new schema and
   new `responses` entries, and **no change to any existing 200 response**.
8. Add the bug-bank entry (§11) and run the full gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

- **File:** `tests/test_gateway_openapi_contract.py` (new — grep first; if a spec-shape test file
  already exists, add to it rather than creating a second one)
- **Test name:** `test_openapi_declares_the_error_envelope`
- **It must assert:** that the OpenAPI document **generated from the live app object** contains an
  `ErrorResponse` schema with the three real fields, and that at least one protected route declares it
  for `401`. Generating from the app (not reading the checked-in JSON) means the test fails for the
  real reason — a missing declaration — rather than because someone forgot to run the generator.
- **It must FAIL before your fix** with: `AssertionError: ErrorResponse missing from components.schemas`

```python
# sketch — adapt to the repo's existing gateway test fixtures
def test_openapi_declares_the_error_envelope() -> None:
    """T-37: the {code, message, details} envelope the gateway returns must be in the spec."""
    cp = GatewayControlPlane()
    app = create_gateway_app(cp)
    spec = app.openapi()

    schemas = spec["components"]["schemas"]
    assert "ErrorResponse" in schemas, "ErrorResponse missing from components.schemas"
    assert set(schemas["ErrorResponse"]["properties"]) >= {"code", "message", "details"}

    # And at least one protected route must actually reference it.
    responses = spec["paths"]["/sessions/{session_id}/interrupt"]["post"]["responses"]
    ref = responses["401"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ErrorResponse")
```

> **Pin the second assertion to a route you have confirmed exists in the spec** — `grep '"/sessions/{session_id}/interrupt"' openapi/hachi-openapi.json`
> before relying on it. If that path moves, the test fails for an unrelated reason and the next
> person will "fix" it by deleting the assertion.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the fix with `ErrorResponse missing from components.schemas`.
- [ ] `openapi/hachi-openapi.json` contains an `ErrorResponse` schema; schema count 41 → 42.
- [ ] `frontend/src/lib/data/schema.d.ts` was regenerated and contains `ErrorResponse` (BB-4, §12).
- [ ] `npm run --prefix frontend check:api` exits clean.
- [ ] **No runtime behaviour changed:** `grep -c "raise HTTPException"` is still **46** and
      `grep -c "_error_response("` is still **29**. If either moved, you converted call sites — that is
      §9's out-of-scope work; revert it.
- [ ] The `path` count in the spec is still **87** — no route was added or removed.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **DO NOT convert the 46 `raise HTTPException` sites to the envelope.** This is the adjacent thing you
  will be tempted by — the two shapes coexisting looks like the "real" bug, and a global exception
  handler for `HTTPException` would "fix" it in one edit. It is a **breaking wire-format change**: it
  alters what every one of those 46 endpoints returns on error, and the frontend's `parseError`
  (`frontend/src/lib/data/client.ts:104-121`) and `ApiError` (`:46`) decode the body today. Flag it as a
  follow-up decision with a written migration note. **Do not bundle it here** — this task's entire value
  is that it is additive and risk-free, and bundling destroys that.
- **Do not change any existing `response_model=`** or add response models to routes that lack one. Only
  9 of ~100 operations have a typed 200 response today; fixing that is
  [T-38](T-38-openapi-pilot-og-domain.md)'s territory, one domain at a time.
- **Do not hand-edit `openapi/hachi-openapi.json`.** It is generated. Hand edits are overwritten by the
  next `gateway-openapi` run and will fail `check:api`.
- **Do not hand-edit `frontend/src/lib/data/schema.d.ts`.** Same reason — it is generated by
  `openapi-typescript`.
- **Do not start importing the generated types in the frontend.** That is
  [T-38](T-38-openapi-pilot-og-domain.md).
- **Do not "normalise" route grammar** (`/config/provider` vs `/config/providers`,
  `POST /runtime/mcp/{name}/enable` vs `PUT /schedules/{id}/enabled`). Same CF-5 finding, entirely
  different and breaking work.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking.
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_gateway_openapi_contract.py

# BB-4 — MANDATORY, the spec changed
uv run hachi gateway-openapi --output openapi/hachi-openapi.json
npm run --prefix frontend generate:api

# Confirm the change is purely additive
python -c "import json;d=json.load(open('openapi/hachi-openapi.json'));print('paths',len(d['paths']),'schemas',len(d['components']['schemas']),'ErrorResponse',('ErrorResponse' in d['components']['schemas']))"

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`, and coordinate with any sibling task landing first):

```markdown
### BB-N — The gateway's error envelope was absent from its own OpenAPI spec

- **Symptom:** `openapi/hachi-openapi.json` (87 paths, 41 schemas) had no `ErrorResponse`, so
  generated clients had no typed error shape — while the gateway returned `{code, message, details}`
  from 7 exception handlers and 21 in-route returns. The frontend hand-mirrors the envelope in
  `parseError` (`frontend/src/lib/data/client.ts`) instead of importing it.
- **Root cause:** FastAPI only emits a model into `components.schemas` when a route DECLARES it
  (`response_model=` or `responses=`). `grep -c "responses=" src/hachi/gateway/fastapi_app.py`
  returned **0** — not one route or router declared any error response, and `ErrorResponse` was only
  ever constructed inside function bodies and serialised into a bare `JSONResponse`.
- **Fix:** added a shared `_ERROR_RESPONSES` mapping and passed it as `responses=` on each of the
  gateway's 19 `APIRouter`s. Purely additive — no runtime behaviour changed.
- **Avoid:** returning a `JSONResponse` built from a Pydantic model does NOT put that model in the
  spec. If a shape is part of your contract, some route has to declare it.
- **Known and NOT fixed (separate decision):** 46 `raise HTTPException` sites still return Starlette's
  `{"detail": ...}`, a different shape from the envelope. Unifying them is a breaking wire-format
  change affecting the frontend's `ApiError` decoding.
- **Locked by:** `tests/test_gateway_openapi_contract.py` — `test_openapi_declares_the_error_envelope`
```

## 12. Known traps

- **BB-4 — THIS TASK CHANGES THE OPENAPI SPEC.** That is the entire point of it. Run both:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  npm run --prefix frontend generate:api
  ```
  or `scripts/preflight.py`'s "openapi <-> frontend contract" step (`scripts/preflight.py:124-131`)
  fails, and so does CI. The step runs `gateway-openapi` and then `check:api`, which regenerates
  `schema.d.ts` and `git diff --exit-code`s it — so an un-regenerated frontend type file fails the gate
  even though nothing is wrong with your Python.
- **`schema.d.ts` will grow by more than you expect.** Declaring 6 error responses across 18 routers
  adds a `responses` block to every operation in the generated TypeScript. A multi-thousand-line diff in
  a generated file is expected here; do not try to minimise it, and do not hand-edit it.
- **`system` (`:712`) has no `dependencies=protected_dependencies`.** Declaring `401` on it would claim
  `/health` can return an auth error, which it cannot. Give it a reduced mapping.
- **Do not use `_error_response`'s status codes as the whole story.** Some of the 21 in-route returns use
  `422` (`:2277`) and `500` (`:2908`). Read §3.2/§3.3 and derive the set from the actual emissions
  rather than assuming the six in §5's sketch are exhaustive.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
