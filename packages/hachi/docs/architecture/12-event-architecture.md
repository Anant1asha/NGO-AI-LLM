# 12 — Event Architecture

> Phase 2 / Gate B. Initiative **C**. Contract + one impl + seam. Seams are `file:line`.
> Related: ADR-0003.

## 1. Problem

Events are a one-way typed **log**, not a bus: the emit funnel `emit_runtime_event`/
`relay_event` (`orchestrator.py:1484-1498`) does `read_models.append_event()` + a single
`on_event(...)` callback, synchronously, in-process, memory-only (cap 2000,
`runtime_read_models.py:247`). Nothing can *subscribe and react*. The brief (C) needs
publish/subscribe with async dispatch, and reactive agents (react to `file.uploaded`,
`search.completed`, `message.received`, `tool.call.completed`).

## 2. Contract — `EventBus`

```python
# core/event_bus.py
Handler = Callable[[RuntimeEvent], None]

class EventBus:
    def publish(self, event: RuntimeEvent) -> None: ...
    def subscribe(self, pattern: str, handler: Handler, *,
                  mode: Literal["sync", "async"] = "sync",
                  name: str | None = None) -> Subscription: ...
    def unsubscribe(self, sub: Subscription) -> None: ...
```

- **`pattern`** matches the dotted taxonomy by prefix/glob: `"tool.call.*"`, `"session.*"`,
  `"*"`. Reuses the existing `<domain>.<noun>.<verb>` vocabulary (`runtime_events.py:16-56`)
  — the bus does not invent a new event language.
- **`sync` subscribers** run inline on the publishing thread (today's behavior): the
  read-model store, the SSE pump, and the new observability sink. Ordering preserved.
- **`async` subscribers** (reactive agents, durable-wait wakeups) are **dispatched via the
  job queue** as named handler jobs — *not* fire-and-forget threads (honors the
  "prefer queued background work" guardrail). This gives them durability and retry for free
  once `JobRegistry` is active ([16](16-durable-execution.md)).

## 3. One implementation, built over the existing funnel (back-compat)

The bus *wraps* the emit funnel rather than replacing the producers:

```python
# gateway/orchestrator.py — emit funnel becomes:
def emit_runtime_event(event):
    bus.publish(event)            # was: read_models.append_event(event); on_event(...)

# at boot, the legacy consumers are registered as the first sync subscribers:
bus.subscribe("*", lambda e: read_models.append_event(adapt_event(e)), mode="sync", name="read-models")
bus.subscribe("*", _sse_and_tui_on_event, mode="sync", name="surface")
bus.subscribe("*", obs_sink.handle, mode="sync", name="observability")   # H
```

Every current producer already routes through `on_event`/`relay_event`, so **publishers are
unchanged**; consumers become explicit subscribers. New reactive subscribers attach with no
edits to producers — the single-funnel property (Gate-A finding) is what makes this a
one-function change.

## 4. New event types (additive)

Add to the taxonomy (`runtime_events.py`): `file.uploaded`, `file.extracted`,
`search.completed`, `message.received`, `webhook.received`, `run.suspended`, `run.resumed`,
`provider.failover`, `model.routed`. Also **promote the leaked raw literals** (`job.retry`,
`budget_exceeded`, `llm_retry`, `session_time_limit` — emitted as strings outside the
taxonomy, Gate-A debt) into declared constants so the bus contract is complete and typed.

## 5. Reactive agents (the C payoff)

A reactive subscriber maps an event to agent work, enqueued durably:

```python
bus.subscribe("file.uploaded", on_file_uploaded, mode="async", name="auto-extract")
# on_file_uploaded(event) → enqueue a JobRegistry handler "extract_and_index"(file_id)
```

The agent reacts to events, not only direct user requests — satisfying C — while all heavy
work runs through the durable job substrate, not inline.

## 6. What it touches

| File | Change |
|---|---|
| `core/event_bus.py` (new) | `EventBus`, `Subscription`, pattern matcher |
| `gateway/orchestrator.py:1484` | funnel publishes to the bus; legacy consumers become subscribers |
| `core/runtime_events.py:16` | new event constants; promote leaked literals |
| `jobs/queue.py` | async dispatch path (handler jobs) — see [16](16-durable-execution.md) |
| `core/runtime_read_models.py` | unchanged (now a subscriber) |

## 7. What could break (and the guard)

- **Ordering / double-delivery:** sync subscribers must see events in sequence exactly once.
  *Guard:* the bus preserves publish order for sync handlers and assigns the monotonic
  `sequence` before fan-out (as the store does today); a test asserts SSE output is identical
  pre/post bus for a fixed event script.
- **A slow/throwing sync subscriber stalls the turn.** *Guard:* sync handlers are wrapped
  to log-and-continue on exception (never propagate into the loop); anything heavy must be
  `async`. Documented contract.
- **Back-compat for `on_event` consumers** (TUI handler). *Guard:* the surface callback is
  registered as a sync subscriber; behavior identical.

## 8. Deferred (seam only, per §4a)

Durable/persistent event log, replay, dead-letter queue, cross-process/distributed delivery.
The bus interface accommodates all four later (persist in `publish`; replay by re-reading a
persisted log; DLQ as a failed-handler-job sink) — none is built now because no consumer needs
them on a single node. Trigger to build: first multi-process deployment or first "replay events
since T" requirement.
