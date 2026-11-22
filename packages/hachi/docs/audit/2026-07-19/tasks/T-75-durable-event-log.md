# T-75 · Persist runtime events to a durable `events` table

|  |  |
|---|---|
| **Source finding** | Missed Opportunity #1 — [ARCHITECTURE-REVIEW.md](../ARCHITECTURE-REVIEW.md) |
| **Severity** | P2 |
| **Wave** | 2 (fast-follow, pre-v1.1) — **optional leverage, not gate-blocking. See §2.** |
| **Depends on** | [T-54](T-54-schema-version-tables.md) — *land it first so the new table is versioned from birth* (§2). [T-53](T-53-jobs-db-path-unification.md) transitively, since T-54 follows it. |
| **Blocks** | nothing |
| **Effort** | ~1 week |
| **Difficulty** | High — the SQLite mechanics are mechanical (§5 gives you the exact pattern to copy); the judgement is in **which** events to persist (§5.4) and in not letting scope grow into a full event-sourcing rewrite (§9) |
| **Files you will touch** | `src/hachi/core/events/store.py` *(new)*, `src/hachi/core/runtime_read_models.py`, `src/hachi/core/paths.py`, `src/hachi/gateway/orchestrator.py`, `src/hachi/gateway/control_plane.py`, `tests/test_event_store_durability.py` *(new)*, `docs/architecture/12-event-architecture.md`, `docs/architecture/adr/0006-durable-event-log.md` *(new)* |

---

## 1. Brief

Runtime events exist only in a per-session, in-memory Python list capped at 2,000 entries. They do
not survive a process restart, the sequence counter restarts at 1 on every boot, and "history" for a
non-live session is *synthesized* from the SQLite transcript at message granularity in a **separate
sequence space starting at 0**. When you are done, runtime events are written to a real SQLite
`events` table using the repo's existing store pattern; the read path serves from it; events survive a
restart; and replay returns the events that actually happened rather than a reconstruction of them.

**This is not a bug fix.** Nothing is broken in the sense of "returns the wrong answer today for a
supported use case." It is a storage change that makes four separate defects structurally impossible.
§4 shows you the evidence the gap is real; there is no failure to reproduce.

## 2. Why this matters

**Read this first: this task is optional leverage and it is not gate-blocking.** It appears in the
review's *Missed Opportunities*, not in the release gate. Wave 1 has 41 tasks that block a public v1;
this has none of them as dependencies and none of them depend on it. **Do not start this while Wave 1
is open.** A week spent here is a week not spent on the dead-feature epidemic (CF-1) or the governance
chain (CF-4), and unlike those, nothing here is user-visible on day one.

With that said, the reason it is worth a week *later* is leverage. The review calls it *"the single
highest-leverage storage change available"* because one table closes four independent problems at once:

1. **SSE loss windows** — the 2,000-entry trim silently drops events under a slow client ([T-30](T-30-sse-gap-signal.md)).
2. **Replay fidelity** — history replay today is a *reconstruction* from message rows, not a record of events (§3.3).
3. **Restart amnesia** — a gateway restart wipes every event and resets the sequence counter to zero (§3.4).
4. **The audit trail the pitch promises** — "verifiable, portable, owned audit" is currently backed by a
   Python list that a `kill -9` erases.

There is one more reason, and it is the strongest: **the project already decided to build this, and
wrote down the trigger condition.** `docs/architecture/12-event-architecture.md:101-107` defers the
durable log explicitly and names when to revisit it (§3.6). That trigger has since fired, and in its
absence two lossy substitutes were built instead. This task is not relitigating a settled decision
([CLAUDE.md](../../../../CLAUDE.md) "Don't relitigate") — it is executing the decision's own stated
follow-through. Record that reasoning in the ADR (§11), or the next reader will think you ignored the
deferral.

**T-54 must land first.** The repo has ten SQLite stores and **zero** `schema_version` tables (§3.5).
If you add an eleventh unversioned table you have made T-54's job larger and re-created the exact debt
CF-13 is about. Landing T-54 first means this table is versioned from birth, which costs you nothing
at creation time and is expensive to retrofit.

## 3. Verified current state

> Anchors were verified against `main` @ `bd24afe` on 2026-07-19.
> **Line numbers drift — re-confirm each one with Read/Grep before you edit.**
> If an anchor is wrong, the *symbol names* below are still correct: grep for those.

### 3.1 Live events are an in-memory list, trimmed to 2,000

`RuntimeReadModelStore.append_event`, `src/hachi/core/runtime_read_models.py:240-251`:

```python
    def append_event(self, event: RuntimeEvent) -> None:
        with self._lock:
            self._sequence += 1
            self._events.append(
                RuntimeEventSnapshot(
                    event.name, dict(event.payload), event.timestamp, self._sequence
                )
            )
            # This log is the single source for sequence-based polling (the gateway
            # events endpoint), so keep a generous tail for slow-polling clients.
            if len(self._events) > 2000:
                self._events = self._events[-2000:]
```

The backing field is declared at `:230` — `self._events: list[RuntimeEventSnapshot] = []` — a plain
Python list. There is no persistence anywhere in this class.

### 3.2 A reconnecting stale client is silently clamped, with no gap signal

`RuntimeReadModelStore.read_events_since`, `src/hachi/core/runtime_read_models.py:426-440`:

```python
    def read_events_since(self, after: int, limit: int = 100) -> tuple[RuntimeEventSnapshot, ...]:
        """Events whose sequence is greater than ``after``, oldest→newest, capped at ``limit``.

        The single source for sequence-based polling (the gateway events endpoint).
        O(1) index into the bounded ring-tail: the event at index ``i`` has sequence
        ``base + i`` where ``base = self._events[0].sequence``.  Clamp ``start`` to
        zero for stale clients (``after < base``) to avoid the silent tail-slice wrap
        that a naive ``after - base + 1`` would produce after a trim (BB entry).
        """
        with self._lock:
            if not self._events:
                return ()
            base = self._events[0].sequence
            start = max(0, after - base + 1)
            return tuple(self._events[start : start + limit])
```

`base` is computed, used for the clamp, and discarded. The caller receives a bare tuple with nothing
in it indicating that events between its cursor and `base` are gone.

### 3.3 History replay is *synthesized*, at message granularity, in a second sequence space

`GatewayControlPlane._synthesize_history_events`, `src/hachi/gateway/control_plane.py:588-649`.
The docstring at `:591-596` states the reconstruction plainly:

```python
    def _synthesize_history_events(
        self, session_id: str, after: int, limit: int
    ) -> list[dict[str, Any]]:
        """Turn a stored transcript into the event envelopes the client replays.

        user msg  → ``session.turn.started`` {user_text}
        assistant → ``text.stream.delta`` {text} + ``session.chat.completed``
        tool msg  → ``tool.call.completed`` {name, result_preview}
        """
```

Three verified specifics:

- **`:599`** — capped at 500 messages: `messages = self._get_session_messages(session_id, 500) or []`
- **`:601`** — a fresh sequence space: `seq = 0`
- **`:649`** — pagination applied *after* building the entire list:
  `return [e for e in events if e["sequence"] > after][:limit]`

The branch that selects it is `read_session_events` at `:554` (`if is_live:` → in-memory ring) versus
`:575-586` (not live → synthesize). So the **same endpoint returns two structurally different things**
depending on whether the process still holds the session in `_connections`, and their `sequence`
values are not comparable. Sequence 7 from the live ring and sequence 7 from history are different
events.

Note what is *lost* by reconstruction even when it works: `permission.requested`, `permission.decided`,
`approval.*`, `boot.*`, `job.*`, `subagent.*`, `memory.*`, `cost.*` — none of them are messages, so
none of them survive into replay. **The governance events are exactly the ones the reconstruction
cannot represent**, which is why this matters more for this product than for a generic chat app.

### 3.4 Restart amnesia — the store takes no arguments and starts at zero

`src/hachi/core/runtime_read_models.py:220-238`:

```python
class RuntimeReadModelStore:
    """Maintains read-only state projections for TUI queries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        ...
        self._events: list[RuntimeEventSnapshot] = []
        ...
        # Monotonic per-store event counter; the sole source of event sequence
        # numbers that paging clients poll against.
        self._sequence = 0
```

No `session_id`, no db path, no writer — **no constructor arguments at all**. One store is created per
booted agent at `src/hachi/gateway/orchestrator.py:2585` (`read_models = RuntimeReadModelStore()`) and
one as a fallback at `:543` (`self._read_models = read_models or RuntimeReadModelStore()`).

Consequence: a gateway restart produces a store whose `_sequence` is `0`, so the next event is
sequence `1` — while a surviving client still holds a cursor of, say, `4000`. It will never see
another event, because nothing will ever be `> 4000` again in that process.

### 3.5 Two independent sequence counters already exist

They are unrelated, both named `_sequence`, and they diverge.

**`EventBus.publish`, `src/hachi/core/event_bus.py:139-141`:**

```python
        with self._lock:
            self._sequence += 1
            seq = self._sequence
```

**`RuntimeReadModelStore.append_event`, `src/hachi/core/runtime_read_models.py:242`:**

```python
            self._sequence += 1
```

The bus's number is returned from `publish()` and handed to async subscribers; the read model's number
is the one clients page against. Nothing reconciles them. **Do not attempt to unify them in this task**
(§9) — but be aware that the durable table introduces a *third* candidate ordering (rowid), so §5
specifies which one is authoritative.

### 3.6 The architecture doc already deferred this — and named the trigger

`docs/architecture/12-event-architecture.md:101-107`:

```markdown
## 8. Deferred (seam only, per §4a)

Durable/persistent event log, replay, dead-letter queue, cross-process/distributed delivery.
The bus interface accommodates all four later (persist in `publish`; replay by re-reading a
persisted log; DLQ as a failed-handler-job sink) — none is built now because no consumer needs
them on a single node. Trigger to build: first multi-process deployment or first "replay events
since T" requirement.
```

**The second trigger has fired.** `GET /sessions/{session_id}/events?after=N` *is* a "replay events
since T" requirement, and it shipped — implemented twice, lossily, as the ring in §3.1 and the
synthesis in §3.3. Quote this paragraph in your ADR; it is the strongest single argument for the task
and it pre-empts "why are you reopening a deferred decision?"

Related settled decisions you should read but **not** reopen: `docs/architecture/adr/0003-event-bus-over-emit-funnel.md`
and `docs/architecture/adr/0004-durable-run-state-on-sqlite-job-substrate.md`.

### 3.7 There is no `schema_version` table anywhere, and no `events` table

Verified by grep across `src/hachi/`:

- `schema_version` appears **only** in `src/hachi/core/obs/envelope.py` (`:88`, `:113`, `:167`) as a
  field on the telemetry envelope. **No SQLite store has a `schema_version` table.** This is T-54's
  premise, and it is why T-54 is a dependency.
- No `CREATE TABLE ... events` exists anywhere.

### 3.8 The `.db` files that exist today

| File | Declared at |
|---|---|
| `sessions.db` | `src/hachi/core/paths.py:41` |
| `tui_state.db` | `src/hachi/core/paths.py:49` |
| `memory_index.db` | `src/hachi/core/paths.py:83` |
| `files.db` | `src/hachi/core/paths.py:93` |
| `runs.db` | `src/hachi/core/runtime/store.py:53` (**not** in `paths.py`) |
| `jobs.db` | `src/hachi/jobs/queue.py:582` **and** `src/hachi/cli/commands/jobs.py:26` (two sites — this is [T-53](T-53-jobs-db-path-unification.md)) |

Declare your path in `paths.py` (§5.2). Do not repeat the `runs.db`/`jobs.db` mistake of hiding a
database path inside the module that happens to use it.

## 4. See the opportunity

**There is no failure to reproduce. This is an opportunity, not a defect** — do not go looking for a
broken output, and do not manufacture one. What follows is the evidence that the gap is real and
measurable. Run it and paste the numbers into your ADR.

### 4.1 Prove there is no durable event storage (grep evidence)

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
cd D:/OpenGigantic/hachi

# 1. No events table exists.
grep -rniE "CREATE TABLE.*events" --include=*.py src/hachi/ ; echo "exit=$?  (1 = no matches = confirmed)"

# 2. No schema_version table exists in ANY store (T-54's premise).
grep -rn "schema_version" --include=*.py src/hachi/ | grep -v "obs/envelope"

# 3. The event log is a Python list.
grep -n "_events: list" src/hachi/core/runtime_read_models.py

# 4. Only TWO production call sites use the shared migration helper.
grep -rn "apply_migrations" --include=*.py src/hachi/ | grep -v "core/migrations.py"
```

**You will see now:** (1) no matches; (2) no matches outside the telemetry envelope; (3)
`230:        self._events: list[RuntimeEventSnapshot] = []`; (4) exactly two production sites —
`core/files/store.py:407` and `core/runtime/store.py:94`, both of which are the pattern you will copy.

### 4.2 Prove restart amnesia deterministically

The store takes no arguments and holds no path, so "restart" is exactly "construct a second one":

```bash
uv run python -c "
from hachi.core.runtime_read_models import RuntimeReadModelStore
from hachi.core.runtime_events import RuntimeEvent

store = RuntimeReadModelStore()
for i in range(2100):
    store.append_event(RuntimeEvent(name='tool.call.completed', payload={'i': i}, timestamp='t'))

print('events appended:            2100')
print('events retained:           ', len(store.read_events_since(after=0, limit=10_000)))
print('oldest retained sequence:  ', store.read_events_since(after=0, limit=1)[0].sequence)

# A restart is a new store. There is no path, no file, nothing to reopen.
restarted = RuntimeReadModelStore()
print('after restart, events:     ', len(restarted.read_events_since(after=0, limit=10_000)))
restarted.append_event(RuntimeEvent(name='tool.call.completed', payload={}, timestamp='t'))
print('next sequence after restart:', restarted.read_events_since(after=0, limit=1)[0].sequence)
"
```

**You will see now:** 2,100 appended, **2,000** retained (100 dropped with no signal), oldest retained
sequence **101**, and after "restart" **0** events with the sequence counter back at **1** — while any
surviving client still holds a cursor of 2,100 and will therefore never receive another event from that
process.

**You should see after the change:** all 2,100 events still readable after reopening the store over the
same database file, sequence numbering continuing from 2,101, and a stale cursor served correctly from
disk instead of being clamped.

> Confirm `RuntimeEvent`'s import path before running — it is defined in
> `src/hachi/core/runtime_events.py:93-98` (`name`, `payload`, `timestamp`) and re-exported elsewhere.
> If the constructor differs, adapt; the point is the six printed lines, not the import.

### 4.3 Prove replay fidelity ≠ live fidelity by reading

Not runnable from a shell — this one is a code-reading proof. Compare:

- **Live:** `control_plane.py:554-573` returns whatever the ring holds — every event name in the
  taxonomy at `src/hachi/core/runtime_events.py:16-60` (`boot.*`, `session.*`, `tool.*`,
  `permission.*`, `subagent.*`, `job.*`, `mcp.*`, `file.*`).
- **History:** `control_plane.py:602-647` emits **exactly four** event types, derived only from
  message rows: `session.turn.started`, `text.stream.delta`, `session.chat.completed`,
  `tool.call.completed`.

So `permission.requested` and `permission.decided` — the governance record — exist live and vanish on
replay. That is the fidelity gap, and no amount of tuning the ring size fixes it.

## 5. What "fixed" looks like

A new `EventStore` writes every persisted event to a SQLite `events` table.
`RuntimeReadModelStore` gains an **optional** durable writer; when present it writes through, and the
read path serves from disk. The in-memory ring stays as a hot cache.

### 5.1 The exact pattern to copy — `RunStateStore`

**This is the most useful part of this spec. Copy this file's shape; do not invent a new one.**

The repo has two stores that use the shared migration helper. They are not equally good models:

| | `core/files/store.py` — `FileMetaStore` | `core/runtime/store.py` — `RunStateStore` |
|---|---|---|
| Connection | new `sqlite3.connect` **per call** (`:411-414`) | one persistent connection (`:71-73`) |
| WAL | **no PRAGMA at all** | `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000` (`:75-77`) |
| Thread safety | none | `threading.RLock` (`:70`), `check_same_thread=False` |
| Transactions | implicit `with conn` | explicit `_db()` contextmanager with rollback (`:80-88`) |
| Indexes | none | `CREATE INDEX IF NOT EXISTS` in the schema script (`:36-37`) |

**Copy `RunStateStore`.** It is the only store in the repo with the full discipline, and the events
table needs every part of it: events are appended from the agent's worker thread while the gateway
reads them from a request thread.

> **Correction to the review, worth knowing:** the review credits the project with "excellent SQLite
> discipline (WAL, atomic writes, CAS job claims)". Verified: WAL is set in exactly **four** places —
> `core/runtime/store.py:75`, `core/session_store.py:64`, `core/user_profile.py:131`,
> `jobs/queue.py:630`. `FileMetaStore` has none. The discipline is real but not uniform, which is
> precisely why §5.1 names the file to copy rather than saying "follow repo convention."

The full skeleton, from `src/hachi/core/runtime/store.py:24-94`:

```python
_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    ...
);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs (session_id);
CREATE INDEX IF NOT EXISTS idx_runs_status  ON runs (status);
"""

# Migration list: (column, definition) pairs to add if missing.
# Use apply_migrations() for safe additive evolution.
_MIGRATIONS: list[tuple[str, str]] = [
    # Example future migration:
    # ("created_at", "TEXT"),
]


def _default_db_path() -> Path:
    from hachi.core.paths import get_hachi_paths

    paths = get_hachi_paths()
    data_dir: Path = paths.data_dir
    return data_dir / "runs.db"


class RunStateStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _default_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection = sqlite3.connect(
            str(self._db_path), timeout=10, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    @contextmanager
    def _db(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_INITIAL_SCHEMA)
            self._conn.commit()
            apply_migrations(self._conn, "runs", _MIGRATIONS)
```

The migration helper it calls is `src/hachi/core/migrations.py:22-56`, `apply_migrations(conn, table,
migrations)` — **additive columns only**, idempotent, safe at every boot. It does *not* manage a
version counter (that is T-54). Its contract, from the docstring at `:34-36`: *"The caller retains
ownership; this function does NOT commit or close."*

### 5.2 The table

Assuming [T-54](T-54-schema-version-tables.md) has landed, register this table's version through
whatever mechanism T-54 established — **do not hand-roll a second one**.

```python
# src/hachi/core/events/store.py
_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    name        TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events (session_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_name        ON events (name);
"""
```

Add `events_db` to `HachiPaths` in `src/hachi/core/paths.py` next to the existing accessors
(`sessions.db` at `:41`, `files.db` at `:93`) rather than hiding the filename in the store module
(§3.8).

**Sequence authority (decided here, do not re-decide):** `seq INTEGER PRIMARY KEY AUTOINCREMENT` is
the durable sequence, and it is **global, not per-session** — it monotonically increases across
restarts, which is the entire point. `RuntimeReadModelStore._sequence` becomes a cache of the last
value the store issued, seeded from `SELECT MAX(seq)` at construction, not an independent counter.
`EventBus`'s `_sequence` (§3.5) is untouched and remains a per-process fan-out ordinal.

### 5.3 Where to hook the write — `append_event`, not `publish`

The architecture doc suggests *"persist in `publish`"* (§3.6). **Do not do that.** Verified reason:
`[events] bus_funnel` is a real config toggle (`src/hachi/core/settings.py:175-193`, defaulting to
`True` at `:193`) and the legacy direct-call path still exists at
`src/hachi/gateway/orchestrator.py:2601-2615`:

```python
    def emit_runtime_event(name: str, payload: dict[str, Any] | None = None) -> None:
        event = RuntimeEvent(name=name, payload=payload or {}, timestamp=now_iso())
        read_models.append_event(event)
        if on_event:
            on_event(event.name, event.payload)
```

and the bus path at `:2727-2744` funnels into the *same* call:

```python
    if _events_cfg.bus_funnel:
        from hachi.core.event_bus import EventBus

        _event_bus = EventBus(job_queue=job_queue)

        def _read_models_sink(event: RuntimeEvent) -> None:
            read_models.append_event(event)
        ...
        _event_bus.subscribe("*", _read_models_sink, mode="sync", name="read-models")
```

So `read_models.append_event` is the **one choke point both configurations pass through**. Persisting
in `publish` would silently stop persisting when someone sets `bus_funnel = false` — a dead feature
that reports success, which is the exact CF-1 pattern this audit exists to stop.

`RuntimeReadModelStore.__init__` currently takes **no arguments** (§3.4) and is constructed bare in
**19 places across 6 test files**. Your new parameter must therefore be optional:

```python
    def __init__(self, event_store: EventStore | None = None, session_id: str = "") -> None:
```

When `event_store is None`, behaviour is byte-identical to today. Wire the real one at
`src/hachi/gateway/orchestrator.py:2585`.

> `RuntimeEvent` carries **no `session_id`** (`src/hachi/core/runtime_events.py:93-98`: just `name`,
> `payload`, `timestamp`). The session id must come from the store instance, which is per-session.
> Do not try to add it to `RuntimeEvent` — that ripples through every emit site.

### 5.4 Which categories to persist — the recommendation

The review names the tradeoff: durable events add write volume, so gate by category if needed. **Here
is the concrete call. Persist everything except the streaming firehose.**

Verified event taxonomy from `src/hachi/core/runtime_events.py:16-60` plus emit-site counts:

| Category | Volume | Persist? |
|---|---|---|
| `permission.*`, `approval.*` | ~2 per gated action | **Yes** — this is the audit trail |
| `tool.call.started` / `.completed` | ~2 per tool call | **Yes** — what the agent did |
| `session.*` (`chat.started/completed`, `turn.*`, `resumed`, `shutdown`, limits) | ~4 per turn | **Yes** |
| `subagent.*`, `job.*`, `run.*`, `mcp.*`, `file.*`, `memory.*`, `cost.*`, `llm.retry` | low | **Yes** |
| `boot.progress` | 11 per boot (`total: 11` at `orchestrator.py:2622`) | **Yes** — bounded, and boot diagnostics are the thing you most want after a crash |
| **`text.stream.delta`** | **one per streamed chunk** | **No** |
| `thinking.step`, `usage.updated` | per chunk / per turn | `thinking.step` **no**, `usage.updated` **yes** |

`text.stream.delta` is the only real volume problem, and it is verified per-chunk — see the comment at
`src/hachi/core/loop.py:1115-1121`, which explains that delta listeners *"accumulate `text.stream.delta`
events"*. It is also the **least** valuable to persist: the assistant's final text is already durably
stored as a message row by `SessionStore`, which is what §3.3's synthesis reads back.

Implement the filter as a module-level `frozenset` of **excluded** names — deny-list, not allow-list —
mirroring `_SPAN_EVENTS` at `src/hachi/core/obs/sink.py:37-49`. A deny-list fails *safe*: a newly added
event name is persisted by default. An allow-list fails *silent*, which is CF-1 again.

```python
# Names deliberately NOT persisted: per-chunk streaming noise whose content is
# already durable as a message row in SessionStore.
_EPHEMERAL_EVENTS: frozenset[str] = frozenset({"text.stream.delta", "thinking.step"})
```

### 5.5 The read path

`read_events_since` serves from the durable table when a store is attached, falling back to the
in-memory ring otherwise. Keep the ring as a hot cache for the common "tail of a live session" query —
do not delete it.

Then, in `GatewayControlPlane.read_session_events` (`control_plane.py:542-586`), the history branch
(`:575-586`) reads real persisted events for the session instead of calling
`_synthesize_history_events`. **Leave `_synthesize_history_events` in the file** as the fallback for
sessions recorded before this table existed — deleting it loses replay for every existing session
(§9).

## 6. Steps

1. **Confirm [T-54](T-54-schema-version-tables.md) has landed.** If it has not, stop and schedule it
   first (§2). Do not proceed and "add versioning later."
2. Write the failing durability test from §7 first. Watch it fail.
3. Add `events_db` to `HachiPaths` (`src/hachi/core/paths.py`, next to `files.db` at `:93`).
4. Create `src/hachi/core/events/store.py` with `EventStore`, copying `RunStateStore`'s skeleton
   verbatim (§5.1): `_EVENTS_SCHEMA`, `_MIGRATIONS`, `_default_db_path()`, persistent connection +
   `RLock` + the three PRAGMAs, `_db()` contextmanager, `_init_schema()` calling `apply_migrations`.
5. Give it three methods: `append(session_id, name, payload, timestamp) -> int` (returns the assigned
   `seq`), `read_since(session_id, after, limit) -> list[...]`, and `max_seq() -> int`.
6. Register the table's schema version via T-54's mechanism.
7. Add `_EPHEMERAL_EVENTS` (§5.4) and apply it in `append`, not at the call site — one choke point.
8. Add the optional `event_store` / `session_id` parameters to `RuntimeReadModelStore.__init__`
   (`core/runtime_read_models.py:223`), defaulting to `None` / `""`. Seed `self._sequence` from
   `event_store.max_seq()` when attached.
9. Write through in `append_event` (`:240`) — inside the existing `with self._lock:` block, after the
   ring append, so ring and table cannot disagree about ordering.
10. Read through in `read_events_since` (`:426`) when a store is attached.
11. Wire the real `EventStore` at `src/hachi/gateway/orchestrator.py:2585` where
    `RuntimeReadModelStore()` is constructed, passing the session id.
12. Point the history branch of `GatewayControlPlane.read_session_events`
    (`control_plane.py:575-586`) at the durable store, keeping `_synthesize_history_events` as the
    pre-migration fallback.
13. Update `docs/architecture/12-event-architecture.md:101-107` — move the durable log out of
    "Deferred" and record that the "replay events since T" trigger fired.
14. Write ADR `docs/architecture/adr/0006-durable-event-log.md` (§11).
15. Run the gate (§10).

## 7. Regression test — WRITE THIS FIRST

**This is [CLAUDE.md](../../../../CLAUDE.md) Rule 2 (the regression law) and it is not optional.**
Write the test, watch it FAIL, then write the fix, then watch it PASS.

A real characterization test applies here even though this is not a bug fix: "events survive a
restart" is a claim about observed behaviour that is **false today and must be true after**, and it is
cheap to assert honestly. There is no mock in it.

- **File:** `tests/test_event_store_durability.py` (new)
- **Test name:** `test_events_survive_store_restart`
- **It must assert:** events appended through one `RuntimeReadModelStore` over a `tmp_path` database
  are readable through a **second, independently constructed** store over the *same* path, with
  sequence numbering continuing rather than restarting.
- **It must FAIL before your fix** with `TypeError: RuntimeReadModelStore.__init__() takes 1 positional
  argument but 2 were given` (or the keyword-argument equivalent) — because `__init__` currently takes
  no arguments at all (§3.4).

> **No existing test does this.** Verified: `tests/test_durable_store.py` has 16 tests and every one
> uses a single live `RunStateStore` from the fixture at `:26`; `tests/test_cold_start_resume.py:126-128`
> likewise constructs one store per test. **Reopening a store over the same path is a pattern this repo
> does not yet have.** You are writing the first one, so do not go looking for an example to copy.

```python
# sketch — adapt to the repo's existing fixtures
def test_events_survive_store_restart(tmp_path: Path) -> None:
    """T-75: a durable event log must outlive the process that wrote it."""
    db = tmp_path / "events.db"

    first = RuntimeReadModelStore(event_store=EventStore(db_path=db), session_id="s1")
    for i in range(3):
        first.append_event(
            RuntimeEvent(name="tool.call.completed", payload={"i": i}, timestamp="t")
        )
    before = first.read_events_since(after=0, limit=100)
    assert len(before) == 3

    # "Restart": a brand-new store object over the same file. No shared state.
    second = RuntimeReadModelStore(event_store=EventStore(db_path=db), session_id="s1")
    after = second.read_events_since(after=0, limit=100)

    assert len(after) == 3, "events did not survive the restart"
    assert [e.name for e in after] == [e.name for e in before]

    # Sequence continues; it does not restart at 1.
    second.append_event(RuntimeEvent(name="session.shutdown", payload={}, timestamp="t"))
    assert second.read_events_since(after=3, limit=10)[0].sequence == 4
```

Three more tests, each independently checkable:

- **`test_replay_fidelity_matches_live_fidelity`** — append a `permission.decided` event, then read it
  back through the durable path. Asserts the event type that §4.3 proves is *unrepresentable* in
  today's synthesis survives replay. **Fails before** because the event never reaches storage.
- **`test_stale_cursor_is_served_not_clamped`** — append 2,100 events, read with `after=5`, assert the
  first returned sequence is `6` and **not** `101`. This is the claim that the gap becomes impossible
  rather than merely detectable — the difference between this task and [T-30](T-30-sse-gap-signal.md).
- **`test_streaming_deltas_are_not_persisted`** — append one `text.stream.delta` and one
  `tool.call.completed`; assert the table holds exactly one row. Locks §5.4's deny-list so a later
  edit cannot quietly start persisting the firehose.

> If your test passes before you write the fix, the test is wrong. Do not proceed.

## 8. Acceptance criteria

- [ ] The regression test from §7 exists, and failed before the change with `TypeError` on the
      `RuntimeReadModelStore` constructor.
- [ ] **Events survive a restart:** a second store over the same path returns everything the first
      wrote, and sequence numbering continues instead of resetting to 1.
- [ ] **Replay fidelity equals live fidelity:** an event type that is not a message row —
      `permission.decided` is the canonical case — is returned by the replay path. Verified by test,
      not by inspection.
- [ ] **A gap is impossible, not merely detectable:** a cursor older than the 2,000-entry ring is
      served from disk with no clamp. If you cannot assert this, you have built a cache, not a log.
- [ ] `text.stream.delta` and `thinking.step` are **not** in the table; every other emitted event name
      is (deny-list, per §5.4).
- [ ] `T-54`'s schema-version mechanism covers the new table. No second versioning scheme was invented.
- [ ] `_synthesize_history_events` still exists and still serves sessions recorded before the table.
- [ ] `docs/architecture/12-event-architecture.md`'s "Deferred" section no longer lists the durable
      event log, and says why.
- [ ] ADR `0006-durable-event-log.md` exists, is linked from `docs/architecture/adr/README.md`, has a
      `Status:` line and `## Context` / `## Decision` / `## Consequences`
      (enforced by `scripts/check_adrs.py:26-28`).
- [ ] `uv run python scripts/preflight.py` is GREEN (report the real pytest counts).
- [ ] A `docs/bug-bank.md` entry was added (§11).

## 9. Out of scope — do NOT

- **Do not start this while Wave 1 is open.** This is optional leverage from the review's *Missed
  Opportunities*, not a release-gate item. If Wave 1 is unfinished, close this file and go pick up a
  Wave 1 task. This is the primary boundary on the task.
- **Do not do this before [T-54](T-54-schema-version-tables.md).** An eleventh unversioned table makes
  CF-13 worse, not better (§2).
- **Do not unify the two `_sequence` counters** (§3.5). `EventBus._sequence` and
  `RuntimeReadModelStore._sequence` are independent by construction and reconciling them touches the
  async-dispatch path. Note it; leave it.
- **Do not delete `_synthesize_history_events`.** Every session recorded before this table exists can
  only be replayed through it. Deleting it is silent data loss for existing users.
- **Do not turn this into event sourcing.** You are adding a durable *log* that the read path can
  serve. You are not making the table the system of record for session state, not rebuilding
  `AgentSession` from events, and not touching `SessionStore`. If you find yourself editing
  `core/session_store.py`, stop.
- **Do not implement the gap signal from [T-30](T-30-sse-gap-signal.md) here.** T-30 is the cheap
  interim fix — return `base_sequence` so clients can *detect* a gap. This task makes the gap
  *impossible*. If T-30 has already landed, its `base_sequence` field stays and simply stops ever
  indicating a gap; leave the field and its tests alone. If T-30 has not landed, do not do it as a
  warm-up — they are separately reviewable.
- **Do not add a retention/pruning policy in this task.** An unbounded table is a real follow-up
  concern, but a retention window is a product decision (how long is the audit trail?), not an
  implementation detail. File it. `RetentionSettings` already exists (imported at
  `gateway/orchestrator.py:2715`) — do not wire it in on your own initiative.
- **Do not fix the history/live sequence-space collision** beyond what pointing the history branch at
  the durable store gives you for free.
- **Do not add a runtime dependency.** `sqlite3` is stdlib; you need nothing else.
- Do not weaken, skip, or delete an existing test to go green — fix the code
  ([CLAUDE.md](../../../../CLAUDE.md) Rule 2).
- Do not run a repo-wide `ruff format` ([CLAUDE.md](../../../../CLAUDE.md) Rule 3).
- Do not fix other findings you notice in passing — note them and move on.

## 10. Verify

```bash
# on Windows use `python -m pytest` if the .exe shim fails — see BB-1
uv run pytest -q tests/test_event_store_durability.py tests/test_runtime_read_models.py \
                 tests/test_gateway_runtime_validation.py tests/test_migrations.py

# ADR lint — this task adds an ADR
uv run python scripts/check_adrs.py

uv run python scripts/preflight.py --quick   # inner loop
uv run python scripts/preflight.py           # before you call it done
```

Report the **actual** pass/fail counts. "Looks done" is not done.

## 11. Bug bank entry

This task is an opportunity, not a defect — but it **closes a real data-loss class**, so an entry is
warranted. Append to [docs/bug-bank.md](../../../bug-bank.md) (next free `BB-N` — the highest entry is
`BB-88` at the time of writing, and several Wave 1 tasks also claim `BB-89`; re-check the file).

```markdown
### BB-N — Runtime events lived only in memory; a restart erased the audit trail

- **Symptom:** every runtime event — including `permission.requested`/`permission.decided`, the
  governance record — was held in a per-session Python list capped at 2,000 entries. A gateway
  restart erased all of them and reset the sequence counter to 0, so a surviving client holding
  cursor N never received another event from the new process. Replay for a non-live session was
  RECONSTRUCTED from message rows and could only ever emit 4 of the ~30 event types.
- **Root cause:** `RuntimeReadModelStore._events` (`core/runtime_read_models.py:230`) was a plain
  `list`, trimmed at `:250-251`, with `self._sequence = 0` re-initialised per construction (`:237`).
  `GatewayControlPlane._synthesize_history_events` (`gateway/control_plane.py:588-649`) synthesized a
  substitute from the transcript in a separate sequence space starting at `seq = 0` (`:601`).
  `docs/architecture/12-event-architecture.md:101-107` had deferred the durable log with the trigger
  "first 'replay events since T' requirement" — that requirement shipped as
  `GET /sessions/{id}/events?after=N` without the deferral being revisited.
- **Fix:** added `EventStore` (`core/events/store.py`) on the `RunStateStore` pattern — persistent
  connection, WAL, `apply_migrations` — and threaded it as an OPTIONAL collaborator into
  `RuntimeReadModelStore`, writing through at the `append_event` choke point that BOTH the bus path
  and the legacy direct-call path traverse. Per-chunk `text.stream.delta`/`thinking.step` are
  excluded by a deny-list.
- **Avoid:** when a "deferred, seam only" architecture decision names a TRIGGER condition, the
  trigger firing is a scheduling event. Shipping the triggering feature without revisiting the
  deferral is how a documented non-goal becomes two lossy substitute implementations.
- **Also avoid:** hook durable side-effects at the choke point that every configuration traverses,
  not at the one the default configuration happens to use. Persisting in `EventBus.publish` would
  have silently stopped persisting under `[events] bus_funnel = false`.
- **Locked by:** `tests/test_event_store_durability.py` — `test_events_survive_store_restart`
```

## 12. Known traps

- **BB-1 (Windows):** if `pytest`/`mypy` `.exe` shims fail with OS error 4551, use
  `python -m pytest` / `python -m mypy`.
- **BB-42 — do not open a connection per event.** That bug was a store constructed per call and never
  closed; on Windows it holds `*.db-wal`/`*.db-shm` handles open indefinitely. An events table is the
  highest-frequency writer in the process, so this failure mode is far worse here. Use the single
  persistent connection + `RLock` from §5.1. **One `EventStore` per process, not per event and not
  per request.**
- **`RuntimeReadModelStore()` is constructed bare in 19 places across 6 test files** (plus
  `orchestrator.py:543` and `:2585`). Your new parameters **must** be optional with today's behaviour
  as the default, or you break a large number of unrelated tests and will be tempted to "fix" them —
  which is scope creep and reads as test-weakening.
- **Secret redaction is NOT applied on the `emit_runtime_event` path.** Verified: `redact_structure`
  and `redact_secrets` are called only inside `adapt_event`, at
  `src/hachi/core/runtime_events.py:251` and `:270`, and only for the `tool_call` / `tool_result`
  event types. The comment at `:246-250` says redaction protects *"the event stream, TUI transcript,
  gateway SSE, or persisted SQLite"* — but events emitted directly through `emit_runtime_event`
  (rather than `relay_event` → `adapt_event`) never pass through it. **Persisting raw payloads turns a
  transient in-memory exposure into a durable one on disk.** Audit which of the event names you are
  persisting can carry credentials in their payload before you ship, and say what you found.
- **BB-51 (torn writes):** the atomicity you need comes from SQLite's WAL transaction, not from a
  hand-rolled write. Use the `_db()` contextmanager pattern (rollback on exception) — do not add a
  `Path.write_text` anywhere near this.
- **`apply_migrations` is additive-columns-only.** `src/hachi/core/migrations.py:44-56` only issues
  `ALTER TABLE ... ADD COLUMN`. It cannot rename, drop, or re-type. Get the column set right at
  creation; you do not get a cheap second chance.
- **`apply_migrations` does not commit or close** — the caller owns the connection
  (`core/migrations.py:34-36`). Follow `RunStateStore._init_schema` (`core/runtime/store.py:90-94`)
  exactly: `executescript`, `commit`, *then* `apply_migrations`.
- **BB-6:** `ProcessSharedServices` is `None` before a session boots — relevant if you try to resolve
  the store through shared services rather than constructing it in `boot_agent`.
- **BB-4 does NOT apply unless you change a response shape.** Serving the same
  `SessionEventsResponse` from a different backing store is not an OpenAPI change. If you *do* alter
  the response, regenerate the spec and the frontend types or CI fails.
- **The eval harness will not protect you here.** `scripts/preflight.py` runs the eval corpus, but it
  exercises loop mechanics, not storage durability. Your §7 test is the only thing standing between
  this table and a silent regression.
