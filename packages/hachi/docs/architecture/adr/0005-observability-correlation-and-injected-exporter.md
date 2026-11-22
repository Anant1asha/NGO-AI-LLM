# ADR-0005 — Observability via correlation-id stamping + injected exporter

- **Status:** Active (Phases 0–5 implemented 2026-07-06)
- **Date:** 2026-06-21 (amended 2026-07-06)
- **Related:** [21](../21-observability.md); composes with ADR-0003

## Context

At inception (2026-06-21): tracing was dormant with 2 leaf spans, no per-turn root, and
thread-pool context loss; events carried no `turn_id`/`session_id`; no metrics or default
logging. End-to-end traces could not be assembled.

At amendment (2026-07-06): the partial foundation exists (`tracing.py`, `core/obs/*`), but
`[observability]` config was dead (never called `setup_from_config` / `setup_metrics` at boot),
the sink emitted zero-duration marker spans (no real waterfall), and `logging_setup.py` was never
called from entrypoints.  Five additional gaps were discovered and corrected (CX1–CX5 in the
plan).

## Decision

1. **`turn_id` is the Hachi correlation key** (`TraceContext.trace_id == turn_id`); it is the
   stable join key for diagnostics, bug reports, and read-model correlation.  The exported OTel
   `trace_id` is transport-driven (W3C `traceparent` when a remote parent exists) and may differ.
   Both are exposed in span attributes and `TelemetryEnvelope`.

2. **Injection pattern:** spans are created *where work happens* (`with span(...)` wrappers at
   choke points); the `ObservabilitySink` stamps attributes and span-events onto the *active* span
   (attribute stamper, not span emitter).  This removes double-accounting.

3. **Exporter:** `setup_from_config(kind, endpoint)` in `core/tracing.py` selects the exporter
   (`console` / `otlp` / `langfuse`).  All non-test exporters go through `BatchSpanProcessor`
   (async, non-blocking — Gate-C amendment A5).  Vendor choice = collector config, no app code.

4. **Metrics:** thin facade in `core/obs/metrics.py` with `setup_from_config` mirroring tracing.
   Instruments: 10 counters/histograms + one observable gauge (queue depth, registered at boot).
   `[observability] metrics_enabled=true` to activate.

5. **Logging:** `setup_logging(log_format=)` in `core/obs/logging_setup.py`.  A
   `TraceContextFilter` injects `turn_id`/`session_id`/`otel_trace_id` into every log record
   without touching call sites.  `log_format="json"` enables the JSON formatter.

6. **Privacy:** `spans.py::ALLOWED_SPAN_ATTRS` and `DENY_METADATA_KEYS` enforce the attribute
   allowlist at the envelope boundary.  No prompt bodies, no raw bearer, no retrieved memory
   bodies reach the exporter.

7. **Degraded mode:** `enabled=true` + `bus_funnel=false` → boot warning; direct spans/metrics/
   logging still work; sink-based enrichment unavailable.

## Seam reference (verified 2026-07-06)

| Seam | Location |
|------|----------|
| `agent.turn` root span | `orchestrator.py::_chat_impl` line ~1474 |
| `tool.call` child span | `loop.py` line 517 |
| `llm.generate` child span | `loop.py` line 1027 |
| Thread-pool OTel context capture | `loop.py` line 1194 |
| Thread-pool OTel context re-attach | `loop.py` line 510 |
| `http.request` root span (middleware) | `gateway/middleware/trace.py` |
| Sync `post_message` route | `fastapi_app.py` line ~946 |
| Idempotency early-return | `fastapi_app.py` line ~955 |
| SSE route | `fastapi_app.py` line ~1104 |
| Observability boot block | `orchestrator.py::boot_agent` after `_events_cfg` parse (~line 2680) |

## Alternatives considered

1. **Scatter `span()` calls through business logic.** Rejected — littering; choke points
   (turn root, `registry.execute`, `BaseLLMClient`, event sink) give coverage without scattering.
2. **Adopt the Langfuse SDK directly in the loop.** Rejected — couples business logic to a
   vendor; the OTel exporter seam keeps Hachi provider-agnostic.
3. **New correlation id instead of reusing `turn_id`.** Rejected — `turn_id` already exists;
   reusing it avoids a second id.
4. **Sink as span emitter (original design).** Amended — the sink's zero-duration marker spans
   created double-accounting with the real `agent.turn` root.  Demoted to attribute stamper.
5. **`structlog` for JSON logging.** Rejected — stdlib JSON formatter is dep-free and sufficient;
   `structlog` would be a new dependency.

## Consequences

**Positive:** one trace spine across all layers; Langfuse/Tempo/Prometheus is one config value;
redaction inherited from the event taxonomy; the default-silent logging gap closes; metrics
activate with a config flag.

**Negative:** id-stamping touches many emit sites (additive, low-risk); thread-context propagation
is subtle (covered by nesting test); minor enabled-overhead (no-op when off); sink demotion
breaks three existing tests that must be intentionally rewritten (CX2).

**Reversibility:** high — all changes are additive; disabling (`enabled=false`) reverts to
today's behavior.

## Constraint: OTLP exporter in gate env

The `[observability]` extra (`pyproject.toml`) declares
`opentelemetry-exporter-otlp-proto-http>=1.27.0`, but `scripts/preflight.py` must install it
(`uv sync --extra observability`) for OTLP tests to run.  Console + in-memory paths run with
`[tracing]` only.  OTLP export without the extra is manual-smoke only (see CX3 in the plan).
