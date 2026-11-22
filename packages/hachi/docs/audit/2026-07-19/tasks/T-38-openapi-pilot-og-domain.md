# T-38 · Make the generated schema load-bearing — pilot on the `og` domain

|  |  |
|---|---|
| **Source finding** | CF-5 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 1 (gate-blocking, before public v1) |
| **Depends on** | none. Pairs naturally with [T-37](T-37-error-envelope-in-openapi.md) — do that one first if you want the easier warm-up. |
| **Blocks** | nothing — but this pilot is the input to the *decision* about migrating the other 15 domains (§9) |
| **Effort** | ~1 day |
| **Difficulty** | Medium — the TypeScript is easy; §3.3 is a real obstacle the audit did not anticipate |
| **Files you will touch** | `src/hachi/gateway/fastapi_app.py`, `openapi/hachi-openapi.json`, `frontend/src/lib/data/schema.d.ts`, `frontend/src/lib/data/domains/og.ts`, one frontend test |

---

## 1. Brief

`frontend/src/lib/data/schema.d.ts` is 6,001 generated lines that **nothing imports**, while the real
frontend↔gateway contract is 60 hand-written `interface Gateway*` blocks that "mirror Python dicts
exactly". CI regenerates and diff-gates the generated file on every build to protect something no code
reads. This task makes the schema load-bearing for **exactly one domain** — `og.ts`, the smallest —
proving the pattern end-to-end so the migration of the rest becomes an informed decision rather than a
guess.

## 2. Why this matters

This repo has already suffered the "frontend wired to nonexistent gateway routes" regression class. The
CI job that supposedly prevents it (`scripts/preflight.py:124-131`) diff-checks a file nothing consumes
— so it detects that the *generated artifact* changed, never that the *frontend* disagrees with the
gateway. Meanwhile the true contract is maintained by hand in four places (Python route → OpenAPI JSON →
hand-written TS interface → `types.ts` display model), and a fifth in the Python client. The point of
this pilot is **not** to convert one file for tidiness; it is to find out what conversion actually costs
and whether the generated types are good enough to consume — which, as §3.3 shows, is a live question
with a surprising answer. If you finish this task without being able to say what migrating the other 15
domains would take, the pilot has failed.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 The generated file is inert

`frontend/src/lib/data/schema.d.ts` is **exactly 6,001 lines** and has **zero importers**. Repo-wide,
only four mentions exist, and **none of them is an import**:

| Where | What it says |
|---|---|
| `frontend/package.json:13` | `"generate:api": "openapi-typescript ../openapi/hachi-openapi.json -o src/lib/data/schema.d.ts"` |
| `frontend/package.json:14` | `"check:api": "openapi-typescript ... && git diff --exit-code -- src/lib/data/schema.d.ts"` |
| `frontend/src/lib/data/domains/integrations.ts:127` | `* These are inline types (not touching schema.d.ts).` |
| `frontend/src/lib/data/domains/interactions.ts:13` | `// ---- Gateway shapes (mirrors InteractionRecord in schema.d.ts) ----` |

The last two are comments in which the authors **explicitly acknowledge hand-mirroring** the generated
file rather than importing it.

The CI gate, `scripts/preflight.py:124-131`:

```python
    Step(
        "openapi <-> frontend contract",
        [
            ["uv", "run", "hachi", "gateway-openapi", "--output", "openapi/hachi-openapi.json"],
            ["npm", "run", "--prefix", "frontend", "check:api"],
        ],
        needs_frontend=True,
    ),
```

regenerates and diff-gates 6,001 lines to protect a file nothing reads.

### 3.2 The real contract is hand-written

**61** `interface Gateway*` declarations (**60** excluding tests) across the domain layer. Verified
per-file counts:

| File | `Gateway*` interfaces | | File | `Gateway*` interfaces |
|---|---|---|---|---|
| `integrations.ts` | 9 | | `authoring.ts` | 4 |
| `memory.ts` | 8 | | `setup.ts` | 3 |
| `config.ts` | 7 | | `skills.ts` | 2 |
| `work.ts` | 6 | | `operator.ts` | 2 |
| `spend.ts` | 5 | | **`og.ts`** | **2** |
| `chat.ts` | 5 | | `interactions.ts` | 2 |
| `approvals.ts` | 4 | | `files.ts` | 1 |
| | | | `providers.ts`, `voice.ts` | 0 |

> **Correction to the audit:** the review said "55+ across 14 files". Verified: **60 non-test
> interfaces**, and the domain layer has **16** non-test files, 14 of which carry at least one
> `Gateway*` interface (`providers.ts` and `voice.ts` carry none). The 61st is in
> `interactions.test.ts`.

The convention is stated verbatim at `frontend/src/lib/data/domains/approvals.ts:13`:

```typescript
// 1. Raw gateway shapes (mirror Python dicts exactly)
```

### 3.3 ⚠ THE OBSTACLE THE AUDIT MISSED — the schema has almost nothing to import

**Only 9 of ~100 gateway operations have a typed 200-response schema.** The other 91 produce an *empty*
schema, because almost every route is annotated `-> Any` with no `response_model=`.

The nine that are typed: `GET /health`, `GET /readiness`, `POST /sessions`,
`DELETE /sessions/{session_id}`, `POST /sessions/{session_id}/messages`,
`POST /sessions/{session_id}/interrupt`, `GET /sessions/{session_id}/events`, `GET /interactions`,
`PUT /interactions/{interaction_id}/rating`.

**`GET /og/graph` is not among them.** The route, `src/hachi/gateway/fastapi_app.py:2002-2005`:

```python
    @og_router.get("/graph")
    async def get_og_graph() -> Any:
        """Return the ObjectGraph node graph with per-pass token estimates."""
        return control_plane.og_graph()
```

which generates, in `frontend/src/lib/data/schema.d.ts:5159-5168`:

```typescript
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
```

**You cannot import a type that is `unknown`.** The pilot therefore has a backend half: add a
`response_model` to the route, regenerate, *then* import. This is not scope creep — it is the actual
work of making the schema load-bearing, and discovering it is a large part of this pilot's value.

### 3.4 The real payload shape — `og_graph_from_engine`, `src/hachi/gateway/orchestrator.py:2483-2495`

```python
        result_nodes.append(
            {
                "id": node.name,
                "name": node.name,
                "kind": kind,
                "index": index_tokens,
                "dense": dense_tokens,
                "full": full_tokens,
                "deps": list(node.requires),
            }
        )

    return {"nodes": result_nodes, "count": len(result_nodes)}
```

### 3.5 The hand-written mirror — `frontend/src/lib/data/domains/og.ts:11-25`

78 lines total, two interfaces, backing one route:

```typescript
// ---- Gateway shape ----

interface GatewayOgNode {
  id: string;
  name: string;
  kind?: string;
  index?: number;
  dense?: number;
  full?: number;
  deps?: string[];
}

interface GatewayOgGraph {
  nodes: GatewayOgNode[];
}
```

**Note the drift already present:** the backend returns `{nodes, count}` (§3.4); `GatewayOgGraph`
declares only `nodes`. Harmless today, and a small live demonstration of exactly what hand-mirroring
costs.

The adapter directly below, `frontend/src/lib/data/domains/og.ts:29-44`:

```typescript
function adaptOgNode(raw: GatewayOgNode): OgNode {
  const validKinds = new Set<OgNode["kind"]>(["root", "skill", "leaf"]);
  const kind: OgNode["kind"] = validKinds.has(raw.kind as OgNode["kind"])
    ? (raw.kind as OgNode["kind"])
    : "skill";

  return {
    id: raw.id ?? "",
    name: raw.name ?? "",
    kind,
    index: raw.index ?? 0,
    ...
```

**This adapter stays.** See §5.

### 3.6 The generated file's import surface

`frontend/src/lib/data/schema.d.ts` exports `paths` (`:6`), `webhooks` (`:1897`), `components`
(`:1898`), `$defs` (`:2377`), and `operations` (`:2378`). Schemas render as, e.g.,
`schema.d.ts:2029`:

```typescript
        InteractionRecord: {
            /** Id */
            id: string;
            /** Session Id */
            session_id: string;
            /** Turn Id */
            turn_id?: string | null;
```

### 3.7 A verified zero-backend-change alternative — `interactions.ts`

Because `GET /interactions` **is** one of the nine typed operations, `InteractionRecord` and
`InteractionListResponse` already exist in `schema.d.ts` — and
`frontend/src/lib/data/domains/interactions.ts` (147 lines, 2 interfaces) hand-mirrors them anyway, as
its own comment at `:13` admits.

`interactions.ts` is therefore a **pure frontend pilot**: delete two hand-written interfaces, import two
generated ones, done. See §5 for when to prefer it.

## 4. Reproduce the failure

Fully reproducible from a shell; nothing to run, only to count.

```bash
cd /d/OpenGigantic/hachi

# 1. 6,001 generated lines...
wc -l frontend/src/lib/data/schema.d.ts

# 2. ...with zero importers (only two comments and two package.json scripts mention it)
grep -rn "schema\.d\.ts\|from \"../schema\"\|from \"./schema\"" frontend/src frontend/package.json | grep -v node_modules

# 3. The real contract, hand-written:
grep -rcE "^\s*(export )?interface Gateway" frontend/src/lib/data/domains/*.ts | grep -v ":0"

# 4. And the obstacle — how many operations actually have a typed 200 response:
python - <<'PY'
import json
d = json.load(open('openapi/hachi-openapi.json'))
typed = untyped = 0
for p, ops in d['paths'].items():
    for m, op in ops.items():
        if m not in ('get', 'post', 'put', 'delete', 'patch'):
            continue
        sch = op.get('responses', {}).get('200', {}).get('content', {}).get('application/json', {}).get('schema', {})
        if '$ref' in sch or sch.get('type') or 'items' in sch or 'anyOf' in sch:
            typed += 1
        else:
            untyped += 1
print("typed 200 responses:", typed)
print("untyped/empty 200 responses:", untyped)
PY
```

**You will see now:**
```
6001 frontend/src/lib/data/schema.d.ts
frontend/package.json:  "generate:api": ...
frontend/package.json:  "check:api": ...
frontend/src/lib/data/domains/integrations.ts:127: * These are inline types (not touching schema.d.ts).
frontend/src/lib/data/domains/interactions.ts:13:// ---- Gateway shapes (mirrors InteractionRecord in schema.d.ts) ----
...
typed 200 responses: 9
untyped/empty 200 responses: 91
```

Zero import lines. Nine typed operations out of a hundred.

**You should see after the fix:** `og.ts` appears in the grep at step 2 as a genuine
`import type { components } from "../schema";`, its two hand-written `Gateway*` interfaces are gone, and
the typed-operation count is **10**.

## 5. What "fixed" looks like

One domain — `og.ts` — derives its raw gateway types from the generated schema, and the route that
backs it is typed on the Python side so there is something real to derive from.

### Step-through of the target state

**Backend** (`src/hachi/gateway/fastapi_app.py`) — declare the shape the code already returns, following
the file's existing response-model convention (`SessionEventsResponse` at `:132`,
`InteractionListResponse`):

```python
class OgNodeModel(BaseModel):
    """One ObjectGraph node with per-pass token estimates (GET /og/graph)."""

    id: str
    name: str
    kind: str
    index: int
    dense: int
    full: int
    deps: list[str] = []


class OgGraphResponse(BaseModel):
    """Response for ``GET /og/graph``."""

    nodes: list[OgNodeModel]
    count: int
```

```python
    @og_router.get("/graph", response_model=OgGraphResponse)
    async def get_og_graph() -> Any:
        """Return the ObjectGraph node graph with per-pass token estimates."""
        return control_plane.og_graph()
```

> Derive the field set from `og_graph_from_engine` (§3.4), **not** from the frontend's hand-written
> interface — the frontend's is already missing `count`. And note `control_plane.og_graph()` returns
> `{"nodes": []}` when no handler is wired (`src/hachi/gateway/control_plane.py:886-890`), so `count`
> must tolerate absence or the fallback must be updated to include it. Check this before you declare
> `count` required.

**Frontend** (`frontend/src/lib/data/domains/og.ts`) — replace the hand-written block:

```typescript
import type { components } from "../schema";

// ---- Gateway shapes: DERIVED from the generated OpenAPI schema, not hand-mirrored.
// Regenerate with `npm run generate:api` after any gateway change (BB-4).
type GatewayOgNode = components["schemas"]["OgNodeModel"];
type GatewayOgGraph = components["schemas"]["OgGraphResponse"];
```

Everything below — `adaptOgNode`, `loadOg`, `_hasEverSucceeded`, `_inFlight`, `registerLoader` — is
**unchanged**.

### The boundary — state this clearly in your report

Generated types can replace the **raw gateway layer** (`interface Gateway*`). They **cannot and should
not** replace the **adapter layer** into `types.ts`. `adaptOgNode` (§3.5) narrows `kind` to a union,
supplies `?? 0` / `?? ""` defaults, and normalises absent fields — deliberate resilience against a
backend that may omit fields, and the frontend's own display contract. That layer is legitimate and
stays. **This pilot proves the raw layer only.** A reviewer who expects `types.ts` to disappear has
misread the goal.

### If the backend half is refused

If a reviewer objects to adding `response_model` to `/og/graph`, **switch the pilot to `interactions.ts`**
(§3.7) — its types are already in the schema, so it is a pure frontend change and still proves the
import pattern. Say in your report which you did and why. Do **not** silently fall back to
hand-written types.

## 6. Steps

1. Re-verify §3.3 — regenerate the spec and confirm `/og/graph` still produces
   `"application/json": unknown`. If someone has since added a `response_model`, skip to step 5.
2. Add `OgNodeModel` and `OgGraphResponse` to `src/hachi/gateway/fastapi_app.py`, beside the existing
   response models near `:132`.
3. Attach `response_model=OgGraphResponse` to the route at `:2002`.
4. Confirm the no-handler fallback (`control_plane.og_graph()`, `control_plane.py:886-890`) still
   validates against the model — if it returns `{"nodes": []}` with no `count`, either give `count` a
   default or fix the fallback. **Do not make the model lie about the real payload to accommodate the
   fallback.**
5. **BB-4:** regenerate the spec and the frontend types (§12).
6. Confirm `components["schemas"]["OgGraphResponse"]` now exists in `frontend/src/lib/data/schema.d.ts`
   and is not `unknown`.
7. Write the frontend test from §7. **Run it. Watch it fail** (it cannot compile / the type does not
   exist yet if you run it before step 5).
8. Replace the two hand-written interfaces in `frontend/src/lib/data/domains/og.ts:11-25` with the
   derived aliases from §5.
9. Run `npm run --prefix frontend typecheck`. Fix any mismatch **by correcting the hand-written
   assumption**, not by widening the generated type with `as any`.
10. Run the full gate (§10) and add the bug-bank entry (§11).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

This task has two halves, so it needs two locks.

### 7a. Backend — the route is typed (Python, `pytest`)

- **File:** `tests/test_gateway_openapi_contract.py` (new, or the file
  [T-37](T-37-error-envelope-in-openapi.md) created — check first and share it)
- **Test name:** `test_og_graph_route_declares_a_response_schema`
- **It must assert:** that the OpenAPI document generated from the live app gives `GET /og/graph` a
  `$ref`'d 200-response schema, and that the referenced schema carries the real fields from §3.4
  (including `count`).
- **It must FAIL before your fix** with: `AssertionError: GET /og/graph has an untyped 200 response`

```python
# sketch — adapt to the repo's existing gateway test fixtures
def test_og_graph_route_declares_a_response_schema() -> None:
    """T-38: /og/graph must publish a real schema so the frontend can derive its types."""
    app = create_gateway_app(GatewayControlPlane())
    spec = app.openapi()

    schema = spec["paths"]["/og/graph"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in schema, "GET /og/graph has an untyped 200 response"

    name = schema["$ref"].rsplit("/", 1)[-1]
    props = spec["components"]["schemas"][name]["properties"]
    assert set(props) >= {"nodes", "count"}
```

### 7b. Frontend — the domain consumes the generated types (`vitest`)

- **File:** `frontend/src/lib/data/domains/og.test.ts` (new — no `og.test.ts` exists today)
- **Test name:** `adaptOgNode maps a generated-schema node to the display model`
- **It must assert:** that a fixture typed as `components["schemas"]["OgNodeModel"]` flows through the
  real `adaptOgNode` to the expected `OgNode`. The type-level assertion is enforced by `tsc` at
  `npm run --prefix frontend typecheck`; the runtime assertion covers the adapter.
- **It must FAIL before your fix** with a TypeScript error —
  `Property 'OgNodeModel' does not exist on type ...` — because the schema has no such member until the
  backend half lands.

```typescript
// sketch — follow the existing patterns in frontend/src/lib/data/domains/*.test.ts
import { describe, expect, it } from "vitest";
import type { components } from "../schema";

describe("og domain", () => {
  it("adapts a generated-schema node to the display model", () => {
    // If this type does not exist, the build fails — that IS the contract check.
    const raw: components["schemas"]["OgNodeModel"] = {
      id: "brain",
      name: "brain",
      kind: "root",
      index: 12,
      dense: 40,
      full: 900,
      deps: [],
    };

    expect(raw.kind).toBe("root");
    expect(raw.deps).toEqual([]);
  });
});
```

> **`adaptOgNode` is not exported today** (`frontend/src/lib/data/domains/og.ts:29`). Export it so the
> test can call it directly, and assert on its real output — a test that only declares a typed literal
> checks the types but not the adapter. Exporting one pure function is the minimum change; do not
> restructure the module.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] Both regression tests from §7 exist, and failed before the fix with the stated errors.
- [ ] `GET /og/graph` has `response_model=OgGraphResponse`; the typed-operation count is **10** (was 9).
- [ ] `frontend/src/lib/data/domains/og.ts` contains `import type { components } from "../schema";` and
      **no** hand-written `interface Gateway*`.
- [ ] `grep -rn "from \"../schema\"" frontend/src` returns at least one hit — the file is no longer
      inert.
- [ ] `npm run --prefix frontend typecheck` passes with **no** `as any` / `@ts-expect-error` added.
- [ ] `openapi/hachi-openapi.json` and `frontend/src/lib/data/schema.d.ts` were regenerated (BB-4, §12);
      `npm run --prefix frontend check:api` exits clean.
- [ ] The adapter layer (`adaptOgNode` → `types.ts`) is **unchanged** except for being exported.
- [ ] **The report states the per-file sizing for the remaining 15 domains** (§9's table) and a
      recommendation on whether to continue. This is the pilot's actual deliverable.
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **DO NOT migrate the other 15 domains.** This is the adjacent thing you will be tempted by — once the
  pattern works it is mechanical, and doing `files.ts` "while you are here" feels free. It is not: 91
  of 100 operations are untyped (§3.3), so every additional domain drags in its own backend
  `response_model` work, its own payload-shape verification, and its own risk. **Whether to continue is
  a judgement call to be made AFTER this pilot, with its cost in hand.** Sizing input, so the decision
  is informed: `integrations.ts` 9 interfaces, `memory.ts` 8, `config.ts` 7, `work.ts` 6, `spend.ts` 5,
  `chat.ts` 5, `approvals.ts` 4, `authoring.ts` 4, `setup.ts` 3, then `skills.ts` / `operator.ts` /
  `interactions.ts` at 2 and `files.ts` at 1.
- **Do not pick a different pilot domain without saying so.** Runner-up is `files.ts` (156 lines, 1
  interface, 4 routes: `POST /files`, `GET /files`, `GET /files/{id}`, `GET /files/{id}/content`).
  **Avoid `providers.ts` and `voice.ts`** — they declare **zero** `Gateway*` interfaces, so converting
  them demonstrates nothing. **Avoid `chat.ts`** — 1,593 lines, 5 interfaces, and it carries the SSE
  path; it is the worst possible candidate. §3.7's `interactions.ts` is the sanctioned alternative if
  the backend half is refused.
- **Do not delete or replace the adapter layer.** `adaptOgNode` and `types.ts` stay (§5).
- **Do not touch `types.ts`.** It is the display contract, not the gateway contract.
- **Do not migrate the Python client.** `src/hachi/client/models.py:1-8` states it mirrors
  `frontend/src/lib/data/types.ts` — the *display* models, not the gateway — and
  `src/hachi/client/gateway.py` uses **37 distinct hardcoded path literals** with no schema check. So
  the real chain is **four** hand-maintained layers (Python route → OpenAPI → hand-written TS → display
  models) with the Python client mirroring the fourth. Whether the client joins the contract is a
  separate decision; name it in your report and stop.
- **Do not add a preflight check that walks `GatewayClient` paths against the spec.** Same CF-5 finding,
  separate task.
- **Do not hand-edit `schema.d.ts` or `openapi/hachi-openapi.json`.** Both are generated.
- **Do not fix the error envelope's absence from the spec** — that is
  [T-37](T-37-error-envelope-in-openapi.md).
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not add a runtime dependency without asking. (`openapi-typescript` is already a frontend
  dev-dependency — you need nothing new.)
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_gateway_openapi_contract.py

# BB-4 — MANDATORY, a route's response shape is now declared
uv run hachi gateway-openapi --output openapi/hachi-openapi.json
npm run --prefix frontend generate:api

npm run --prefix frontend typecheck
npm run --prefix frontend test

# The schema is no longer inert:
grep -rn "from \"../schema\"" frontend/src

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — `BB-89` at the time of writing;
re-check the file, the highest entry was `BB-88`, and coordinate with any sibling task landing first):

```markdown
### BB-N — The generated OpenAPI types were CI-gated but imported by nothing

- **Symptom:** `frontend/src/lib/data/schema.d.ts` (6,001 generated lines) had zero importers, while
  the real frontend↔gateway contract lived in 60 hand-written `interface Gateway*` blocks across 14
  domain files. The `preflight`/CI "openapi <-> frontend contract" step regenerated and diff-gated a
  file no code read, so it could never catch a frontend/gateway disagreement — the exact regression
  class the repo had already suffered ("FE wired to nonexistent gateway routes").
- **Root cause:** two layers. (1) Codegen was bolted on after adapter-first development and never
  threaded into the type graph. (2) More fundamentally, there was almost nothing to import: only
  **9 of ~100** gateway operations declared a `response_model`, so 91 operations generated
  `"application/json": unknown` and could not be consumed even by a willing developer.
- **Fix:** piloted on the smallest domain. Added `OgGraphResponse`/`OgNodeModel` and
  `response_model=` to `GET /og/graph`, regenerated, and rewrote
  `frontend/src/lib/data/domains/og.ts` to derive its raw types from
  `components["schemas"][...]`. The adapter layer into `types.ts` deliberately stays.
- **Avoid:** a route annotated `-> Any` with no `response_model=` publishes an EMPTY schema. Before
  claiming an OpenAPI document is a contract, count how many of its operations actually declare a
  response — and before adding a CI gate on a generated artifact, confirm something imports it.
- **Locked by:** `tests/test_gateway_openapi_contract.py` —
  `test_og_graph_route_declares_a_response_schema`; `frontend/src/lib/data/domains/og.test.ts`
```

## 12. Known traps

- **BB-4 — THIS TASK CHANGES A GATEWAY RESPONSE DECLARATION.** Run both:
  ```bash
  uv run hachi gateway-openapi --output openapi/hachi-openapi.json
  npm run --prefix frontend generate:api
  ```
  or `scripts/preflight.py`'s "openapi <-> frontend contract" step (`scripts/preflight.py:124-131`)
  fails, and so does CI. This task is *about* that pipeline — running it is not optional housekeeping,
  it is step 5.
- **`response_model=` is a runtime filter, not just documentation.** FastAPI validates and **prunes** the
  returned dict to the declared model. If `og_graph_from_engine` ever emits an extra key, it will now be
  **dropped from the response**. Confirm §3.4 is the complete shape before declaring the model, and
  confirm the OG Explorer screen still renders.
- **The no-handler fallback returns a different shape.** `control_plane.og_graph()`
  (`src/hachi/gateway/control_plane.py:886-890`) returns `{"nodes": []}` — **no `count`** — when
  `_get_og_graph` is unwired. With a strict `count: int` this raises a validation error at runtime.
  Handle it deliberately (default the field, or fix the fallback); do not discover it in production.
- **Do not silence a type mismatch with `as any` or `@ts-expect-error`.** If the generated type
  disagrees with the hand-written one, the generated type is describing what the backend actually
  declares — the hand-written assumption was wrong, and finding that is the point of the pilot. Fix the
  assumption (or the backend model), and report the discrepancy.
- **The generated types are uglier to consume.** `components["schemas"]["OgNodeModel"]` is less readable
  than `GatewayOgNode`. A local `type` alias (as in §5) keeps the call sites clean — that is expected
  and fine, and is not the same thing as hand-mirroring.
- **`schema.d.ts` regenerates wholesale.** Expect a large diff even for a small model addition,
  especially if [T-37](T-37-error-envelope-in-openapi.md) landed first. That is normal for a generated
  file.
- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
