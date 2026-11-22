# 23 — API Changes

> Phase 2 / Gate B. Aggregates gateway/contract changes from docs 12–21. Additive; every new
> route ships with a `response_model` (also chipping at debt D11). Seams are `file:line`.

## 1. New REST routes

| Route | Initiative | Response model |
|---|---|---|
| `GET /runs`, `GET /runs/{id}` | D | `RunStateView` |
| `POST /runs/{id}/wake` | D | `RunStateView` (webhook/tool wake; auth-scoped) |
| `POST /files` (multipart) | E | `FileMeta` |
| `GET /files`, `GET /files/{id}` | E | `FileMeta` / list |
| `GET /files/{id}/content` | E | streaming `FileResponse` |
| `GET /models` (enhanced) | B | `list[ModelInfo]` from the registry (also resolves prior H6 lineage) |

`POST /search` is **deferred** (the agent uses the tool; a REST surface lands only if the UI needs
it). All routes carry bearer auth + session-ownership where applicable
([fastapi_app.py:498](src/hachi/gateway/fastapi_app.py:498)), via the existing two-layer
`GatewayControlPlane` seam (`control_plane.py:65`).

## 2. New SSE event types (additive)

The stream envelope is unchanged (`{id, event, data:{sequence, event_type, payload, time}}`,
`fastapi_app.py:765`). New `event_type`s: `file.uploaded`, `file.extracted`, `search.completed`,
`run.suspended`, `run.resumed`, `provider.failover`, `model.routed`. Existing consumers ignore
unknown types (forward-compatible).

## 3. Contract-currency process (unchanged, now enforced harder)

Every route change runs the existing dance: `uv run hachi gateway-openapi --output
openapi/hachi-openapi.json` → `npm run --prefix frontend generate:api` → the CI `frontend-contract`
job re-exports + `check:api` (`git diff --exit-code` on `schema.d.ts`) + `typecheck`.

**New guard (closes the Gate-A regression class + debt D11):** add a CI check that greps the
frontend's `fetch`/route calls against the exported OpenAPI `paths` and **fails on any
frontend-called path the gateway does not serve** — the single check that would have caught the
prior "FE wired to 5 nonexistent routes" class. New typed routes also bring previously-untyped
payloads into the schema opportunistically as we touch them.

## 4. Error-contract alignment (debt D10)

New routes use the uniform `ErrorResponse{code,message,details}` envelope (`fastapi_app.py:58`),
and a FastAPI handler is registered to map `HachiError.http_status` → response (today it is dead,
`errors.py:6`), so domain errors (`ToolError` 502, `OGParseError` 422) surface correctly instead
of collapsing to 500. Existing routes are unchanged (no break).

## 5. What could break (and the guard)

- **`/models` content changes** (now registry-driven). *Guard:* regression test pins the
  configured running model appears.
- **`PROTOCOL_VERSION`** stays `"1.0"` — all changes are additive, so **no lockstep break**
  (`control_plane.py:216`).
- **New binary route surface.** *Guard:* covered in [18](18-attachment-platform.md) §7.

## 6. Deferred

`/search` REST; WebSocket route for streaming voice ([19](19-voice-platform.md)); typing the ~15
legacy untyped routes wholesale (done opportunistically as touched, not as a big-bang).
