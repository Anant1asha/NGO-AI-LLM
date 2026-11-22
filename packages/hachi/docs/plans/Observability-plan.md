# Observability, Telemetry & Diagnostics Platform for Hachi

## Context

Hachi needs to be "one of the easiest AI platforms to debug and continuously improve" — able to answer _why did this request fail / why was it slow / which agent, tool, or prompt caused it / who's affected / how do I reproduce it / generate a bug report automatically_. This work builds a production-grade, **OpenTelemetry-first, event-driven, vendor-agnostic** observability platform spanning the Python engine, the FastAPI gateway, and the React frontend.

**Key finding from codebase inspection (verified against source):** Hachi already has a _real, well-built OTel foundation that is only partially wired_. OpenTelemetry is already an approved optional dependency (`[tracing]` / `[observability]` extras in `pyproject.toml`). The work is therefore **complete + activate + productionize the existing foundation**, then build the genuinely-missing frontend/diagnostics/consent layers — **not** build from scratch. This avoids reinventing what exists and respects the "don't add a dependency without asking" rule.

**Intended outcome:** a full end-to-end trace waterfall (browser click → gateway → agent turn → memory/tool/LLM), live metrics, structured JSON logs, an in-app DevTools diagnostics mode, one-click bug reports, and privacy-by-default consent — all exportable to Grafana/Tempo/Loki/Prometheus/Jaeger/Langfuse by collector config alone, with zero app-code change per backend.

## Review-driven corrections

- **Do not create a second observability source of truth.** Hachi already has `docs/architecture/21-observability.md` and `docs/architecture/adr/0005-observability-correlation-and-injected-exporter.md`; this plan must refresh those, not silently fork them.
- **Do not conflate Hachi turn correlation with OTel distributed trace ids.** Once W3C `traceparent` is supported, the exported OTel `trace_id` is transport-driven; `turn_id` remains Hachi's durable join key for diagnostics, bug reports, and read-model correlation.
- **Do not add a second `agent.turn` root span in `core/loop.py`.** The turn root already exists in `gateway/orchestrator.py::_chat_impl`; Phase 2 should add missing children and sink demotion, not duplicate the root.
- **Do not assume the EventBus is always active.** `ObservabilitySink` only runs when the bus funnel is enabled; the plan must define the degraded behavior or boot warning when observability is enabled but `events.bus_funnel=false`.
- **Do not add dead config knobs.** `sampling_ratio`, `mode`, or consent fields only land when their behavior is actually wired; otherwise this plan would recreate the same config drift it is trying to fix.

## Corrections from source-verified critique (2026-07-06)

A `plan-critic` pass re-read every claim against source. The "foundation exists" thesis held up (~90% accurate to the line, G1 confirmed real), but five things were wrong or unstated and are now fixed inline in the phases below. Recorded here so the executor knows they were verified, not guessed:

- **CX1 — Phase 0 insertion point was physically impossible.** `configure_from_env()` runs at `orchestrator.py:2544`, but `config = load_config()` is 83 lines later at `:2627`; `_events_cfg` is parsed at `:2679` and the EventBus/sink block runs at `:2682`–`:2699`. So "read `ObservabilitySettings` after `configure_from_env()`, before the sink" cannot work — config does not exist there. **Fixed:** Phase 0 now inserts in the `:2627`→`:2682` window (config available, still before the sink), and does **not** call `load_config()` twice.
- **CX2 — Phase 2 silently broke three existing tests.** `tests/test_obs_sink.py` asserts the marker-span behavior Phase 2 removes: `test_sink_mirrors_tool_call_started` (`:48`), `test_sink_carries_correlation_attributes` (`:61`), `test_sink_does_not_leak_secrets` (`:131`). Rewriting a test to assert _new intended_ behavior is legitimate under Rule 2 — silently breaking it is not. **Fixed:** Phase 2 now has an explicit "reconcile existing sink tests" step + a `docs/DECISIONS.md`/`docs/bug-bank.md` note + a `scope-sentinel` heads-up.
- **CX3 — the "no new dep" claim is true in `pyproject.toml` but the gate never installs it.** `[observability]` (`pyproject.toml:92-95`) does declare `opentelemetry-exporter-otlp-proto-http>=1.27.0` (D4 stands). But `scripts/preflight.py` never runs `uv sync --extra observability`, and that exporter is **not importable** in the current gate env — so every OTLP path is `importorskip`-ped and ships **untested**. **Fixed:** the gate section now requires installing the extra for this work (or explicitly scoping OTLP to manual-smoke).
- **CX4 — the doc it says to "refresh" has stale seam pointers.** `21-observability.md` and ADR-0005 cite lines that have drifted (root span is now `orchestrator.py:1474`, tool span `loop.py:517`, llm span `loop.py:1027`, thread handoff `loop.py:1194`). **Fixed:** re-deriving every `file:line` seam is now the _first_ task of Deliverable 1, and the "~82 event taxonomy" figure is corrected to the real count (**42**, `runtime_events.py`).
- **CX5 — the PII-allowlist was promised but deferred to docs.** The current sink is safe (it forwards a _fixed_ key set, not arbitrary payload), but Phase 1's envelope maps "unknown fields → metadata", which would sweep `prompt_preview` (already emitted at `orchestrator.py:1605`, `user_input[:140]`) into exported telemetry. **Fixed:** the allowlist is now concrete and **code-enforced in Phase 1**, with a test that `prompt_preview` never reaches a span/envelope attribute.

Two critique points were themselves wrong on inspection and are **not** adopted: (a) the claim that `session.chat.started/completed` are absent from the sink's `_SPAN_EVENTS` — they are present (`sink.py:31-32`) and _do_ emit `agent.turn.start`/`agent.turn.end` marker spans today, which is extra reason to demote them; (b) the claim that the current sink forwards raw payload fields — it forwards only a fixed allowlist (`sink.py:94,103,107`).

## Locked decisions (from your answers)

| #   | Decision                         | Choice                                                                               | Consequence                                                                                                                                                                                           |
| --- | -------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **First execution pass**         | **Backend-complete (Phases 0–5)**                                                    | Build the backend foundation now; frontend (P6–8) is documented in the doc but built next pass.                                                                                                       |
| D2  | **Frontend telemetry SDK**       | **`@opentelemetry/*` web SDK**                                                       | When P6 lands, use OTel JS web SDK (W3C `traceparent`, auto-instrumentation). New npm deps are pre-authorized by this choice.                                                                         |
| D3  | **Session replay**               | **Lightweight timeline**                                                             | Breadcrumb + zustand-state + network + console + error timeline keyed by `turn_id` (with `otel_trace_id` as a secondary correlation field when present). No DOM capture, no new dep.                  |
| D4  | **Backend export**               | **No new backend deps**                                                              | Traces + metrics and, optionally, logs ship over OTLP using the already-approved `[observability]` extra; Tempo/Loki/Prometheus/Jaeger/Langfuse remain collector configuration, not app-code choices. |
| D5  | **Trace identity model**         | **Separate `turn_id` from the exported OTel `trace_id`**                             | `turn_id` remains the durable Hachi join key; OTel `trace_id` follows W3C parentage when a remote parent exists. Envelopes/logs must expose both where available.                                     |
| D6  | **Observability docs authority** | **Refresh the existing architecture set, do not add a parallel source-of-truth doc** | Update `docs/architecture/21-observability.md`, ADR-0005, and `docs/guides/configuration.md`; only add a new umbrella doc if `21-observability.md` is explicitly reduced to a stub/link.              |
| D7  | **EventBus dependency**          | **Observability tolerates `events.bus_funnel=false`, but warns and degrades**        | Direct spans/metrics/logging still work; sink-derived span enrichment and event-bus-driven telemetry are unavailable until the bus is re-enabled.                                                     |

## What already exists (reuse — do NOT rebuild)

All verified by reading the files:

- **`src/hachi/core/tracing.py`** — own `TracerProvider`; `setup_tracing`, `configure_from_env` (`HACHI_TRACING`→console), **`setup_from_config(kind, endpoint)`** (console/otlp/langfuse), `span()` context manager, `add_span_attributes()`. BatchSpanProcessor (non-blocking). Graceful no-op when SDK absent.
- **`src/hachi/core/obs/trace.py`** — `TraceContext(trace_id=turn_id, session_id, principal=sha256(token)[:16], surface)`; `bind()` sets contextvars + OTel baggage; `copy_otel_context`/`attach_otel_context` for thread-pool span nesting. Important constraint: this `trace_id` is Hachi's current turn-correlation id, not a future distributed-trace id once Phase 4 lands.
- **`src/hachi/core/obs/metrics.py`** — 6-instrument facade (`setup_metrics`, `record_turn/tool_call/provider_error/route_selection`, `TurnTimer`). **Dormant** (never called outside the module).
- **`src/hachi/core/obs/sink.py`** — `ObservabilitySink` subscribed to EventBus `"*"` at boot; mirrors 9 events into **empty marker spans** (`sink.py:114-118`).
- **`src/hachi/core/obs/logging_setup.py`** — `setup_logging`, `traced_logger` (injects trace_id). **Not adopted anywhere yet** — the bootstrap exists, but no entrypoint calls it.
- **`src/hachi/core/event_bus.py`** — thread-safe pub/sub, sync + async(JobQueue), pattern matching. `RuntimeEvent(name, payload, timestamp)`.
- **`src/hachi/core/runtime_events.py`** — 42-event taxonomy (verified count of event-name constants); payloads redacted upstream.
- **`src/hachi/core/cost.py`** — `CostTracker.record`, `cache_metrics`, per-model/provider/feature snapshots; `daily_spend` ledger.
- **`src/hachi/core/session_store.py`** — `interaction_log` (per-turn audit: turn_id, tokens, cost, rating) + `daily_spend`.
- **`src/hachi/core/loop.py`** — real spans `span("tool.call")` and `span("llm.generate")`; thread-pool OTel handoff via `copy_otel_context` / `attach_otel_context`.
- **`src/hachi/gateway/orchestrator.py::_chat_impl`** — already opens the `agent.turn` root span and binds the per-turn `TraceContext`; this is the existing owner of the turn root.
- **`src/hachi/gateway/orchestrator.py`** — `boot_agent`: `configure_from_env()` is called, EventBus is built, the sink is subscribed when the bus funnel is active, and `ResolvedConfig` is only materialized much later in boot.
- **`src/hachi/gateway/fastapi_app.py`** — `create_gateway_app`, CORS, route wiring, a sync `POST /sessions/{id}/messages` path, and an async SSE `GET /sessions/{id}/stream` path. That sync-route thread hop is the load-bearing Phase 4 propagation seam.
- **`frontend/src/lib/data/client.ts`** — single `request()` HTTP chokepoint and the injected-callback pattern `registerReconnectCallback` (reuse this to avoid client↔store cycles).
- **`src/hachi/jobs/queue.py`** — durable `SQLiteJobQueue` + `ResidentWorkerThread` (backpressure/batching substrate).
- **`docs/architecture/21-observability.md` + `docs/architecture/adr/0005-observability-correlation-and-injected-exporter.md`** — existing architecture/docs authority that this plan must amend, not bypass.

## Gaps this closes

- **G0 (design drift):** the current plan would create a second observability source of truth alongside `docs/architecture/21-observability.md` and ADR-0005.
- **G1 (bug):** `[observability]` config is dead — `setup_from_config`/`setup_metrics` are never called at boot; only `HACHI_TRACING` env works. `settings.py:199` docstring _falsely_ claims the gateway calls `setup_from_config` (behavior drift).
- **G2:** ObservabilitySink emits zero-duration marker spans → no real trace waterfall.
- **G2b:** sink-based enrichment disappears when `events.bus_funnel=false`; the degraded mode is currently undocumented.
- **G3:** Metrics are fully dormant — no `record_*` call sites, no config-driven metric exporter.
- **G4:** No gateway request-tracing middleware, no W3C `traceparent`, no request metrics, and the current `trace_id == turn_id` language becomes wrong as soon as a remote parent trace exists.
- **G5:** Logging bootstrap is dead code; adding a JSON formatter alone will not affect runtime until real entrypoints call `setup_logging()`.
- **G6:** No canonical event envelope unifying backend + frontend, and no explicit separation between Hachi correlation ids (`turn_id`, `session_id`) and distributed-trace ids (`otel_trace_id`, `span_id`).
- **G7–G10 (next pass):** frontend telemetry is greenfield; no `/telemetry` ingest or `/diagnostics` API; no in-app DevTools; no bug-report bundle; no central consent UI.

---

## Deliverable 1 — Refresh the existing observability architecture set

Author the docs slice **first** (it is the contract the phases implement):

- **Primary architecture contract:** `docs/architecture/21-observability.md`
- **Decision record to amend:** `docs/architecture/adr/0005-observability-correlation-and-injected-exporter.md`
- **Operator-facing config truth:** `docs/guides/configuration.md`

**First task — re-derive every `file:line` seam (CX4).** Both existing docs cite lines that have drifted (they reference `loop.py:355/737/856`, `orchestrator.py:1138/1141/1190`, `control_plane.py:418`, `fastapi_app.py:480`; the real current seams are root span `orchestrator.py:1474`, tool span `loop.py:517`, llm span `loop.py:1027`, thread handoff `loop.py:1194`, sync `post_message` `fastapi_app.py:946`, idempotency early-return `:955`, SSE `:1104`). A "refresh" that copies stale pointers _is_ the drift this plan (G0) exists to kill — so grep each seam fresh and, where practical, anchor prose on the named statement rather than a bare line number.

If a new `docs/architecture/observability.md` is still desired later, `21-observability.md` must first be demoted to a stub that points at it. Do **not** leave two authoritative observability documents in the tree.

Sections + key content:

1. **Overview & goals** — "Hachi emits structured events; telemetry observes them." Goals + non-goals (v1 excludes rrweb full-DOM replay).
2. **Current architecture** — Mermaid: CLI/TUI/Gateway → `boot_agent` → ExecutionLoop → tools(thread pool)/LLM/memory/router/cost/session_store; EventBus spine; principal boundary (bearer→sha256); existing `agent.turn` root in the orchestrator.
3. **Existing telemetry** — credit + document the foundation above (tracing/trace/metrics/sink/logging_setup/event_bus/cost/session_store, real spans in the loop and orchestrator).
4. **Gaps** — G0–G10 (the "why").
5. **Proposed architecture** — Mermaid: direct instrumentation seams → {spans, metrics, structured logs}; EventBus → `ObservabilitySink` (attrs/span-events only); structured logger → JSON output and optional OTLP logs bridge; OTLP → collector fan-out → Tempo/Loki/Prometheus/Jaeger/Langfuse. Frontend SDK → `/telemetry` (next pass) → same collector path. `/diagnostics` → DevTools. **Waterfall comes from `with span()` wrappers, not the sink. Logs are not modeled as an EventBus subscriber in this pass.**
6. **Design decisions (ADR-style)** — DD0 no second source of truth; DD1 separate `turn_id` from OTel `trace_id`; DD2 waterfall via wrappers + sink demotion; DD3 additive `TelemetryEnvelope` with exporter adapters outside the core dataclass; DD4 OTLP-everywhere (vendor = collector config); DD5 frontend = OTel JS web SDK (D2); DD6 backpressure/offline via SQLiteJobQueue + IndexedDB; DD7 privacy via attribute allowlist + emit-time redaction; DD8 lightweight replay keyed by `turn_id`; DD9 degraded mode warning when EventBus observability enrichment is unavailable.
7. **Tradeoffs** — sampling vs completeness; dep-free JSON logs vs structlog; sink-as-span vs sink-as-attributes; OTLP→collector vs native Prometheus (chose collector, D4).
8. **Rollout plan** — the phase table (all phases; each independently deployable, default-off).
9. **Folder structure** — target tree (below).
10. **Event schema** — envelope field table + `RuntimeEvent`→envelope mapping + `schemaVersion` + explicit backward-compat note that today's runtime-event `payload.trace_id` maps to `turn_id`, not exported OTel `trace_id`.
11. **Trace model** — span tree, attribute conventions, `traceparent` propagation, and the split between `turn_id` (Hachi correlation) and `otel_trace_id`/`otel_span_id` (distributed tracing). For web, `http.request ⊃ agent.turn`; for CLI/TUI, `agent.turn` remains the root.
12. **Metrics** — full instrument catalog + recording seams + cardinality budget.
13. **Logging strategy** — JSON formatter + `TraceContextFilter` + actual bootstrap wiring in gateway/CLI/TUI entrypoints; optional OTel logs bridge only after JSON logging is verified stable.
14. **Privacy model** — per-category consent, emit-time redaction, principal hashing where actually plumbed, self-hosted = local-only, and an explicit allowlist of safe span/log fields (no prompt bodies, no retrieved memory bodies, no raw bearer, no secret-looking tool args by default).
15. **Configuration** — only add fields that have working behavior in this pass; document future mode/sampling matrices here, but do **not** add dead `ObservabilitySettings` knobs until the sampler/behavior exists.
16. **Extensibility** — adapter points; "add a backend" = collector config only; "new sink" = subscribe the bus; "new frontend exporter" = implement the interface.
17. **Developer guide + troubleshooting** — how to enable, read a trace, add a span/metric, extend.

The doc documents **all** phases 0–8 + C; this execution pass implements **0–5**.

---

## Deliverable 2 — Execution: Phases 0–5 (this pass, backend-complete)

Every phase is **default-off** (gated by `ObservabilitySettings`), independently deployable, and leaves runtime behavior unchanged until opted in, so the preflight gate stays green. Sequencing: **0 → 1 → (2 ∥ 3) → 4 → 5**.

**Land one commit (ideally one PR) per phase, gate green between each — not a single mega-diff (D-G6).** "Backend-complete this pass" describes the _scope_ of the pass, not a single commit: these phases touch three of the largest files in the repo (`orchestrator.py`, `loop.py` ~64KB, `fastapi_app.py` ~132KB) plus two new modules, existing test rewrites, and two docs. The phases are already independently deployable, so commit them that way and run `preflight.py` between each. **Phase 4 (middleware + thread-hop) is its own PR** — its blast radius and the Step-A discriminating check should not be co-mingled with Phase 5 logging.

### Phase 0 — Fix dead wiring + config drift (BUG FIX; regression law applies)

- **Goal:** make `[observability]` config actually drive boot (G1) and define the degraded behavior when the EventBus sink is unavailable (G2b).
- **Files:** `gateway/orchestrator.py::boot_agent` — insert the observability-setup block **immediately after `_events_cfg = EventsSettings.model_validate(...)` (currently `~:2679`) and before the `if _events_cfg.bus_funnel:` gate (`~:2682`)**: `config` is already loaded (at `~:2627`) and `_events_cfg` already parsed, so `ObservabilitySettings.model_validate(config.get("observability", {}))` reads real config, `tracing.setup_from_config(...)`/`setup_metrics` run before the sink subscribes (`~:2699`), and the degraded warning can read `_events_cfg.bus_funnel` directly. `core/settings.py` (fix the false `ObservabilitySettings` docstring at `:199`); `docs/guides/configuration.md` (keep the config surface truthful); `docs/bug-bank.md` (BB entries: dead wiring + docstring drift). _(Seam line numbers are as-of 2026-07-06 — re-confirm against source before editing; anchor on the named statements, not the numbers.)_
- **Design/reuse:** call the existing `setup_from_config` verbatim — do **not** invent a config helper or call `load_config()` a second time (the earlier draft's "read observability config early, after `configure_from_env()`" was impossible: config does not exist at `:2544`, it loads 83 lines later — see CX1). Reuse the already-loaded `config` dict and already-parsed `_events_cfg`. If observability is enabled while `events.bus_funnel=false`, boot logs a warning: direct spans/metrics/logging still work, but sink-derived enrichment is disabled. Strictly flag-gated (defaults remain `False`).
- **Tests (failing-first):** `enabled=True, exporter="console"` → `tracing.is_active()` True after boot; default off → False; SDK-absent → False, no raise; unknown kind → warn + boot continues; `enabled=True` plus `bus_funnel=false` → warning emitted, boot continues.
- **Rollback:** revert (additive behind flags; no data migration).

### Phase 1 — Canonical envelope + span-name constants (schema foundation)

- **Goal:** one additive schema unifying backend + frontend (G6); lock the vocabulary before instrumenting.
- **Files (NEW):** `core/obs/envelope.py` — `TelemetryEnvelope` (timestamp, schema_version, turn_id, otel_trace_id, otel_span_id, session_id, workspace_id, agent_id, principal, severity, component, event_type, duration_ms, model, tool, cost_usd, tokens{...}, retry, stacktrace, metadata) + `from_runtime_event(event, ctx, current_span=None)` + `to_dict()`. `core/obs/spans.py` — span-name + attr-key constants (`SPAN_HTTP_REQUEST/AGENT_TURN/PROMPT_BUILD/MEMORY_RECALL/TOOL_CALL/LLM_GENERATE/PERMISSION_CHECK/SUBAGENT/RESPONSE_VALIDATE`), single source of truth for loop/sink/middleware, **plus a code-enforced attribute allowlist** (see below).
- **PII allowlist (code-enforced here, not deferred to docs — CX5):** `spans.py` exports an explicit `ALLOWED_SPAN_ATTRS: frozenset[str]` (correlation ids + `role/model/status/duration/iterations/tool_name` + the metric label keys) and a `DENY_METADATA_KEYS` set (`prompt_preview`, `prompt`, `messages`, `input`, `user_input`, retrieved-memory bodies, raw `authorization`/bearer, anything matching a `*_body`/`*_content` shape). `from_runtime_event`'s "unknown fields → metadata" catch-all **filters through these**, so a payload key like `prompt_preview` (already emitted at `orchestrator.py:1605` as `user_input[:140]`) can never reach an exported envelope field or span attribute. The Phase 2 sink and Phase 4 middleware import the _same_ `ALLOWED_SPAN_ATTRS` — one allowlist, not three. Rationale: the current sink is already safe because it forwards a fixed key set (`sink.py:94,103,107`), but the envelope's generic `metadata` sweep is a new, wider surface and needs the guard from day one.
- **Design:** envelope is a _pure view produced at export boundaries_; `RuntimeEvent` stays the bus wire format. Do **not** put exporter-specific methods like `to_otlp_log_record()` on the core dataclass. Back-compat rule: the current runtime-event `payload.trace_id` maps to `turn_id` until the field name is cleaned up later; `otel_trace_id`/`otel_span_id` come from the active span context when present.
- **Tests:** maps the 9 span-events + a generic event; legacy payload `trace_id` maps to `turn_id`; unknown _safe_ fields → metadata; **denied fields never appear — a payload carrying `prompt_preview`/`user_input` yields an envelope + `to_dict()` with neither the key nor the value anywhere**; round-trip; property test never raises on arbitrary payload.
- **Rollback:** delete the new modules (nothing but tests import them yet).

### Phase 2 — Real backend trace waterfall (span wrappers + sink demotion)

- **Goal:** marker spans → nested, timed waterfall (G2).
- **Files:** `gateway/orchestrator.py` — keep the existing `agent.turn` root span, move its name/attr keys onto `spans.py` constants if useful, and do **not** create a second root in `core/loop.py`. `core/loop.py` — keep `span("tool.call")` + `span("llm.generate")`; add missing child spans such as `PROMPT_BUILD`, `MEMORY_RECALL`, `PERMISSION_CHECK`, `SUBAGENT`, `RESPONSE_VALIDATE` where time is actually spent. `core/tracing.py` — add a small helper for current-span events (for example `add_span_event(name, **attrs)`) so the sink stays behind the tracing abstraction. `core/obs/sink.py` — **demote** the open-and-close marker spans (`sink.py:114-118`) to `tracing.add_span_attributes(**attrs)` + span-events on the _current_ span; keep `is_active()` fast-path + the fixed-key allowlist (now sourced from `spans.py::ALLOWED_SPAN_ATTRS`, Phase 1).
- **What the sink emits today (verified — informs the demotion):** all **9** entries in `_SPAN_EVENTS` (`sink.py:26-38`) open a marker span, **including** `session.chat.started`/`session.chat.completed`, which `_SPAN_NAMES` (`:40-43`) maps to `agent.turn.start`/`agent.turn.end`. So the sink currently emits `agent.turn.start`/`agent.turn.end` marker spans that are _distinct from_ the real `agent.turn` root in the orchestrator (`:1474`) — a concrete source of double-accounting this phase removes. (Note: the earlier assumption that `session.chat.*` were unmapped/dead was wrong; they are live and must be demoted too.)
- **Test reconciliation (CX2 — do this explicitly, do not let it read as cheating):** demoting the sink makes `exp.get_finished_spans()` empty for a bare event, which **breaks three existing tests that assert the old marker-span behavior** — `test_obs_sink.py::test_sink_mirrors_tool_call_started` (`:48`, asserts `"tool.call.started" in names`), `::test_sink_carries_correlation_attributes` (`:61`, `s.name == "tool.call.started"`), `::test_sink_does_not_leak_secrets` (`:131`, `spans[0].attributes`). Rewrite these to assert the **new** contract (attributes/span-events land on the _current_ span; secrets still absent), keeping the same intent. Record the behavior change in `docs/DECISIONS.md` ("sink demoted from span-emitter to attribute-stamper; the waterfall is now owned by `with span()` wrappers") and a `docs/bug-bank.md` line, and call it out in the commit/diff summary so `scope-sentinel` and reviewers see it is an intended contract change, not a weakened test. (The sink already has precedent for stamp-onto-current-span behavior: `test_event_stamped_with_trace_id_when_context_active` at `:142`.)
- **Design (the reconciliation):** **spans are created where work happens** (existing `agent.turn` in the orchestrator, child spans in the loop, request span in Phase 4); **events stamp attributes/events onto the active span** (sink). This removes double-accounting — `tool.call.completed` no longer opens a throwaway span; the wrapper owns duration, the event stamps status/tokens onto it. When `events.bus_funnel=false`, direct spans still give the waterfall; only sink-based enrichment is missing.
- **Tests (in-memory exporter, `batch=False`, `force=True`):** rewrite the three tests above; then stubbed turn → assert tree `agent.turn ⊃ {tool.call, llm.generate, memory.recall}`, correct parent links, non-zero durations, completed-event attrs land on the existing `tool.call` span (not a separate span); tool raises → span records exception; pooled tool nests under turn; no duplicate `agent.turn` root appears **and no stray `agent.turn.start`/`agent.turn.end` marker spans remain**; SDK absent → no spans, turn identical.
- **Rollback:** revert wrappers + sink demotion **and** the three test rewrites together (same PR — reverting one without the others leaves red tests or transient double spans).

### Phase 3 — Metrics activation + full instrument catalog

- **Goal:** wire the dormant metrics (G3). **No new dep** — OTLP metric exporter (`opentelemetry.exporter.otlp.proto.http.metric_exporter`) ships in the already-approved `[observability]` extra (D4).
- **Files:** `core/obs/metrics.py` — add `setup_from_config(kind, endpoint)` mirroring tracing (lazy OTLP import + graceful `ImportError`→warn); add only instruments with a real recording seam in this pass: `hachi.turn.latency_ms`, `hachi.tool.latency_ms`, `hachi.llm.latency_ms`, `hachi.memory.latency_ms`, `hachi.tokens.total`(model,kind), `hachi.cost.usd.total`(model,provider,feature), `hachi.provider_errors.total`, `hachi.route_selections.total`, `hachi.cache.hits.total` + `hachi.cache.calls.total`, `hachi.jobs.queue_depth`(observable gauge). `core/loop.py` — `record_turn` at turn exit, `record_tool_call` at the `tool.call` wrapper, `record_route_selection` at the actual routing seam (`_resolve_turn_client`), and latency histograms where the work occurs. `core/cost.py` — token/cost counters in `CostTracker.record` (lazy import; no-op unconfigured), and increment the two cache counters where `cache_metrics()` already runs. `gateway/orchestrator.py::boot_agent` — call `metrics.register_gauge_source("hachi.jobs.queue_depth", <callable returning depth>)` with the live `SQLiteJobQueue` after it is created; `jobs/queue.py` — expose a cheap `depth()` accessor for that callable.
- **Gauge wiring (S1/S2 — resolve the statefulness/layering gap, don't hand-wave it):** an observable gauge callback must close over a _live_ instance, but `metrics.py` must not import `gateway`/`jobs` (import-linter). So `metrics.py` exposes a **`register_gauge_source(name, callback)`** seam; **boot** (which legitimately imports both layers) hands it the live queue's `depth()` callable — dependency flows core←gateway, no new cross-layer import from core. **`cache.hit_ratio` is demoted from an observable gauge to a counter pair** (`cache.hits.total`/`cache.calls.total`) computed at query time, because `cost.py::cache_metrics` is a _per-call pure function_ with no running accumulator for a pull-based gauge to read — a hit-ratio gauge would need new mutable state this pass shouldn't add. If no gauge source is registered (e.g. CLI/TUI with no queue), the instrument simply reports nothing.
- **Design:** cheap counters/histograms live at the _same seams as the spans_; this slice does **not** invent an EventBus metrics sink. Cost/token metrics in `cost.py` fire for every provider path; the one observable gauge uses an OTel async callback (no hot-path cost) fed by the registered source. `metrics.py` is imported _by_ loop/cost/boot, imports none of them (no cycle, no layer break).
- **Cardinality budget:** never id/free-text labels — only surface/tool/model/provider/capability/kind/error.
- **Tests (in-memory reader):** turn → counters/histograms + attrs + values; cost/token counters match known usage; `cache.hits.total`/`cache.calls.total` increment on a cached vs uncached path; `queue_depth` reads a registered source callable (and is silent when none is registered); OTLP exporter missing → warn, no raise; unconfigured → every `record_*` short-circuits; zero-token/zero-cost turn records nothing spurious.
- **Rollback:** revert call sites (behind `metrics_enabled`).

### Phase 4 — Gateway request-tracing middleware + async→session handoff

- **Goal:** add a root span per HTTP request, W3C `traceparent`, request metrics, and a proven parent/child handoff into the existing `agent.turn` span (G4).
- **Task order (do the risk first):** **Step A — prove the thread hop before writing the full middleware.** The confirmed dispatch chain is single-threaded except for one hop: FastAPI runs the **sync** `post_message` (`fastapi_app.py:946`) on a worker thread, which calls `control_plane.send_message` → `_on_chat` (= `runtime.chat`) → `_chat_impl` (`orchestrator.py:1452`) → `agent.turn` (`:1474`) inline. So the _only_ boundary between an ASGI middleware span and `agent.turn` is the sync-route→threadpool hop. Write a minimal spike (a trivial middleware span + a probe in `post_message` reading the current OTel context) and assert whether the context survives. **Everything else in this phase branches on that result** — do not write the auto-nesting prose or tests until it is known.
- **Files (NEW):** `gateway/middleware/trace.py` — implemented as **pure ASGI** (a Starlette `@app.middleware("http")` function or a raw ASGI class), **not `BaseHTTPMiddleware`** (decided, not "preferred": `BaseHTTPMiddleware` is known to buffer/break `StreamingResponse`, and the SSE path at `fastapi_app.py:1104` is exactly that). Extract `traceparent`/`tracestate` (`TraceContextTextMapPropagator`) → start `span(SPAN_HTTP_REQUEST)` as the HTTP root (child of the remote span when a traceparent is present) → record request attrs/metrics → inject `traceparent` into the **response** headers. **Do not bind a turn-scoped `TraceContext` here**: the middleware does not reliably know `turn_id` or `session_id`, and forcing placeholders would create fake correlation data. **Special-case SSE** `GET /sessions/{id}/stream`: handshake span only — NOT the infinite generator. `gateway/fastapi_app.py` — register the middleware right after CORS (order CORS → trace → auth). `gateway/orchestrator.py` — keep `TraceContext` turn-scoped at `_chat_impl`.
- **Handoff (conditional on Step A — do not assert the happy path):** _If_ the OTel context survives the hop, `agent.turn` nests under `http.request` automatically and no extra code is needed. _If it does not_ (the likely case for a sync route on a threadpool), fix propagation explicitly at the `post_message` dispatch seam by capturing the middleware's OTel context and re-attaching it around the `send_message` call (reuse the loop's existing `copy_otel_context`/`attach_otel_context` pattern, `loop.py:1194`/`:510`). **Do not** invent a fake root in `control_plane.py`.
- **Idempotency-replay branch (D-G7):** `post_message` returns early on an idempotency-key hit (`fastapi_app.py:955`) _before_ `send_message`, so a replayed request produces an `http.request` span but **no `agent.turn`** (the turn never ran). This is correct, but it means "every `POST /messages` has `http.request ⊃ agent.turn`" is **false for replays** — the trace model and the Phase 4 tests must state and assert this branch explicitly rather than assuming a turn always follows.
- **Design:** two correlation layers — W3C `traceparent` / exported OTel `trace_id` (cross-process) + Hachi `turn_id` (turn-local diagnostics join key). `TraceContext` stays turn-scoped. Principal hashing on the HTTP span is allowed; do not claim turn-level `TraceContext.principal` fidelity until that value is explicitly plumbed into the chat path.
- **No OpenAPI change — prove it, don't assert it (S3, BB-4):** no routes added; the middleware adds a response header only. Run the repo's generator (`uv run hachi gateway-openapi --output openapi/hachi-openapi.json`) and confirm a **zero diff**; note the header in the doc. If the diff is non-empty, treat it as a Phase 4 finding, not noise.
- **Tests (TestClient + in-memory exporter):** first commit Step A's hop-survival test; then `POST .../messages` (fresh key) → `http.request` root ⊃ `agent.turn`; **idempotent replay → `http.request` present, no `agent.turn`**; response carries `traceparent`; inbound `traceparent` → the HTTP root is parented to the remote id and `agent.turn` sits under the HTTP span; SSE handshake span closes (no eternal span); malformed traceparent → new root, no raise; unauthenticated → span present + 401.
- **Rollback:** remove the middleware registration (early-returns to no-op when tracing inactive).

### Phase 5 — Structured logging (JSON formatter + incremental traced_logger; no new dep)

- **Goal:** JSON logs correlated by `turn_id` / `session_id` and, when available, `otel_trace_id`, without touching ~100 call sites (G5).
- **Files:** `core/obs/logging_setup.py` — add a stdlib JSON `Formatter` (ts, level, logger, message, turn_id/session_id, otel_trace_id/otel_span_id when a span is active, exc_info) + a **`TraceContextFilter(logging.Filter)`** that reads the active `TraceContext` and current OTel span context; install both on the root in `setup_logging()` when `log_format=="json"`. `core/settings.py` — add `log_format: str = "text"` (text|json). `cli/main.py` plus the gateway/TUI bootstraps that currently own logging setup — call `setup_logging()` so this slice actually affects runtime; preserve existing rotating-file handler precedence instead of clobbering daemon logging. Optional OTel logs bridge (`LoggingHandler`→OTLP logs) is a follow-on inside this phase only after JSON logging is stable.
- **Design (the trick):** the central formatter + filter make all existing `getLogger(__name__)` calls emit correlated JSON with **zero call-site churn**, but this only matters if real entrypoints opt in. `traced_logger` stays incremental polish, not the primary adoption path. No structlog — JSON is dep-free.
- **Tests (caplog):** JSON formatter → valid JSON; `turn_id` present when bound, empty otherwise; `otel_trace_id` appears when a span is active; filter injects on a vanilla `getLogger(__name__)` record; existing handlers are preserved; logs bridge absent → text/JSON still works.
- **Rollback:** default `log_format="text"` = current behavior; revert the formatter install.

**Cross-cutting (starts here, completes next pass): Phase C — privacy + config discipline.** In this pass, only add config that has real behavior (`log_format`, and any other field actually wired in code). Document future `sampling_ratio`, `mode`, and consent matrices in the architecture doc, but do **not** add them to `ObservabilitySettings` until the sampler / redaction behavior exists. Backend privacy in P0–5 is enforced by the existing runtime-event redaction plus explicit span/log attribute allowlists. Frontend consent UI + Settings toggles land with P6–8.

---

## Deferred to the next pass — Phases 6–8 (documented in the doc, not built now)

Per D1 (backend-complete now). Summarized so the plan is complete:

- **Phase 6 — Frontend telemetry SDK** using **`@opentelemetry/*` web SDK** (D2): instrument `client.ts::request()` via a `registerTelemetryCallback` seam (mirroring `registerReconnectCallback`), `sse.ts`, a React `ErrorBoundary` + `window.onerror`/`unhandledrejection`, `PerformanceObserver` web-vitals, zustand breadcrumbs; W3C `traceparent` propagation to the gateway; batched + IndexedDB-buffered + consent-gated OTLP export. New npm deps authorized by D2.
- **Phase 7 — Gateway `POST /telemetry` ingest + read-only `GET /diagnostics/*` API** — auth + dev-flag gated (404 when off); ingest re-emits onto the EventBus so sink/metrics process uniformly; heavy work offloaded to `SQLiteJobQueue`. **New routes ⇒ OpenAPI regen** (`hachi gateway-openapi` + `npm run generate:api`, BB-4).
- **Phase 8 — In-app DevTools `/diagnostics` route** (gated, code-split): live logs, trace explorer/timeline, agent graph, tool exec, model calls, errors, metrics, network, config, search — read-only from the P7 API + live SSE. **Lightweight replay** (D3) from breadcrumbs keyed by `turn_id` (with `otel_trace_id` as a secondary pivot). **One-click bug report** bundle joined to backend `interaction_log`/traces/logs by `turn_id`, shaped to seed a `docs/bug-bank.md` entry + failing test.

---

## Layering, dependencies & gate compliance

- **import-linter (frozen):** core telemetry API + sinks + adapters live in `core/obs/`; exporter wiring at boot, ASGI middleware, and (next pass) `/telemetry`+`/diagnostics` routes live in `gateway/` only; CLI/TUI call the same core `setup_*`. `og_engine` untouched. All P0–5 edits are core→core or gateway→core — **no new cross-layer imports**.
- **Dependencies:** **zero new backend deps** for P0–5 — `[observability]` (`pyproject.toml:92-95`) already declares `opentelemetry-exporter-otlp-proto-http>=1.27.0`, which covers traces _and_ metrics _and_ logs (D4 verified). Frontend OTel deps arrive in P6 (authorized by D2).
- **Gate must actually install the extra (CX3) — this is a real gap, not a formality:** the exporter is _declared_ but **not importable in the current gate env** (only `[tracing]` = api+sdk is installed), and `scripts/preflight.py` does **not** run `uv sync --extra observability`. As-is, every OTLP path is `pytest.importorskip`-ped and **ships untested** (see the existing skips in `tests/test_obs_tracing_config.py:44-45,59-60`). Resolve one of two ways, explicitly, before claiming coverage: **(a)** add `uv sync --extra observability` (or `--all-extras`) to the preflight/CI setup for this work so the OTLP tests actually run; or **(b)** state plainly that automated coverage is console + in-memory only and OTLP export is **manual-smoke** (Verification step 2). Do not imply full traces+metrics+logs export coverage while the gate can't import the exporter. **(a) is the recommended resolution.**
- **OpenAPI contract (BB-4):** **not triggered** by P0–5 — no routes added (Phase 4 adds a response header only, and _proves_ zero diff by running the generator — see Phase 4). Regeneration is required in P7 when routes land.
- **Regression law:** Phase 0 fixes real bugs (dead `setup_from_config` wiring + false docstring) → failing tests first + `docs/bug-bank.md` entries.
- **Windows (BB-1):** run tests via `python -m pytest` if the `.exe` shim errors (OS 4551).
- **Guardrails:** no `subprocess shell=True`; no `.env` autoload in core; creds resolved lazily; no shared-loop-state mutation (use `TurnContext`); background work via `jobs/queue.py`. All telemetry is opt-in and degrades to a zero-cost no-op when unconfigured. Do not widen scope by renaming every legacy `trace_id` field in one pass; normalize at the new envelope boundary first.

## Folder structure (target)

```
src/hachi/core/obs/
  trace.py          (exists)
  metrics.py        (+ setup_from_config, + new instruments)   [P3]
  sink.py           (demoted to attribute/event stamping)      [P2]
  logging_setup.py  (+ JSON formatter, + TraceContextFilter)   [P5]
  envelope.py       (NEW — TelemetryEnvelope)                  [P1]
  spans.py          (NEW — span-name/attr constants)           [P1]
src/hachi/gateway/
  middleware/trace.py   (NEW — request root span + traceparent) [P4]
  routes/telemetry.py   (NEW — ingest)                          [P7, next]
  routes/diagnostics.py (NEW — read-only DevTools API)          [P7, next]
frontend/src/lib/telemetry/  (NEW — bus/envelope/breadcrumbs/consent/config/
  instrument/{http,sse,errors,perf,store}, export/{otlp,buffer}, index)   [P6, next]
frontend/src/routes/diagnostics.tsx      (NEW — gated DevTools)  [P8, next]
frontend/src/lib/store/diagnostics.ts    (NEW — zustand slice)   [P8, next]
docs/architecture/21-observability.md    (refresh existing source of truth) [Deliverable 1]
docs/architecture/adr/0005-observability-correlation-and-injected-exporter.md (amend) [Deliverable 1]
docs/guides/configuration.md             (keep config truth aligned) [Deliverable 1 / P0 / P5]
```

## Verification (end-to-end)

1. **Unit/integration tests** per phase, using the existing conventions: in-memory span exporter with `setup_tracing(exporter=InMemorySpanExporter(), batch=False, force=True)` and `tracing._reset_for_tests()` / `metrics._reset_for_tests()` in autouse fixtures (pattern already in `tests/test_tracing.py`); in-memory metric reader for P3; `caplog` for P5; FastAPI `TestClient` for P4. Guard OTel-dependent tests with `pytest.importorskip`.
   - **Flakiness discipline (D-G1):** `setup_from_config` forces `BatchSpanProcessor` (`tracing.py:131,141`), which exports asynchronously on a timer — reading `get_finished_spans()` right after a real boot is a flake. **Rule:** boot-path tests (Phase 0) assert only activation/config (`is_active()`, exporter kind), never span _contents_; every span-content assertion (Phases 2/4) goes through the in-memory `batch=False`/`SimpleSpanProcessor` seam so export is synchronous. Never mix the two in one test.
2. **Manual smoke:** `HACHI_TRACING=true uv run hachi run` → confirm the console span waterfall (`agent.turn ⊃ memory.recall/llm.generate/tool.call`) for a real turn; then enable the gateway path and confirm `http.request ⊃ agent.turn ⊃ ...` on `POST /sessions/{id}/messages`; then set `[observability] enabled=true, exporter="otlp", endpoint=...` and confirm spans/metrics reach an OTLP collector (e.g. local Tempo/Prometheus via docker-compose) with **no app-code change**.
3. **The gate (must be GREEN before proposing a push):**
   ```
   uv run python scripts/preflight.py            # full: ruff, mypy-gate, skill-lint, import-linter, eval, FULL pytest, frontend
   ```
   Report the **actual** pass/fail + exact pytest counts. On Windows use the `python -m` fallback if a shim errors. Delegate to `gate-keeper` for an honest run and `scope-sentinel` to review the diff before commit.
4. **Layering check:** `uv run lint-imports` stays green (no new cross-layer imports).
5. **No-op proof (D-G5 — assert overhead, not just `is_active()`):** with observability disabled (default), confirm `tracing.is_active()` is `False` and metrics are dormant **and** that a turn produces a byte-identical `RuntimeEvent` stream vs. baseline (the added `record_*`/`span()` call sites all short-circuit on their `None` guard — `tracing.py:170`, `metrics.py:100`). Add one coarse timing assertion (disabled-path turn within noise of baseline) so ADR-0005's "measured in a perf test" promise is actually met, rather than asserting zero-cost by inspection.
6. **Phase 4 discriminating check:** explicitly prove whether the HTTP middleware span survives FastAPI's sync-route thread hop into `post_message`. If that check fails, fix propagation at the dispatch seam before adding any more instrumentation.
