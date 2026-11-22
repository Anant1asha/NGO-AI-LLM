# Streaming / Frontend Performance Plan (revised)

**Branch:** `perf/streaming-optimizations` · **Date:** 2026-06-28
**Status:** PLAN ONLY — no code applied. Branch is clean, **0 commits ahead of main**.
**Provenance:** Original 13-item plan rewritten after a source-verified `plan-critic` pass
(read the actual files; 63 tool calls). Every file:line below was checked against source on
2026-06-28 but **may drift** — re-confirm at edit time before each change.

> ⚠️ **The earlier "B1/B2 already applied to the first SSE generator" status note was FALSE**
> and has been removed. `git log main..HEAD` is empty, the working tree is clean, and grep finds
> none of the B1 headers — both SSE triggers are still the original 50 ms timers. **Nothing has
> been applied.** Treat the whole list as unstarted.

---

## 0. Prerequisites & cross-cutting blockers (read first)

These gate the perf claims; the original plan ignored them.

### P0 — There is no measurement harness

No locust/k6/wrk/autocannon, no `scripts/bench*` anywhere in the repo. Every backend metric in
the original plan ("TTFT", "inter-token −25 ms", "req/s") is **unmeasurable today**, so the
"revert anything that doesn't move its metric" rule is currently impossible to honor.

**Decision required (one of):**

- **(a)** Build a minimal SSE-timing script first — opens N concurrent SSE clients against a booted
  gateway, records first-byte + inter-chunk timestamps — _before_ attempting B2/B4 (whose entire
  justification is latency). Lives at `scripts/bench_sse.py`, not shipped in the lib path.
- **(b)** Reclassify B1–B4 as **correctness-neutral best-practice** changes and **strike all the
  numbers**. Ship them because they're correct, not because we measured a win.

This plan assumes **(b)** unless the user picks (a). All fabricated latency numbers are removed below.

### P1 — Windows measurement reality

The dev OS is Windows 11. uvicorn on Windows uses the selector loop (**no uvloop**), single process,
served in a daemon background thread (`control_plane.py:_serve`). B3's only claimed benefit is
POSIX-only and **invisible on the dev box**; per-token timing on the Windows selector loop is noisy.
Any measurement must say which OS produced it. Per BB-1, run the gate with `python -m pytest` /
`python -m mypy` if the `.exe` shims hit OS error 4551.

### P2 — Regression-law compliance (CLAUDE.md Rule 2)

Behavioral changes need a **failing test FIRST**, then fix, then a `docs/bug-bank.md` entry.
Behavioral items here: **B4, B7, B10, F1, F3**. The original plan omitted tests for the two
riskiest (B7, B10) and planned no bug-bank entries. See §5 for the required test + BB matrix.

### P3 — Frontend test harness gap

The promised "F1 render-count test" is **undeliverable as written**: no `@testing-library/react`,
no jsdom/happy-dom, vitest runs in node env, and `Markdown.test.tsx` uses one-shot `renderToString`.
Either (a) add `@testing-library/react` + `jsdom` as **new dev-deps** + set `environment: 'jsdom'`
(an explicit approval ask — even dev-deps per CLAUDE.md), or (b) downgrade F1's test to a pure-function
memoization test (spy the highlighter, assert stable-prefix call counts) in node env. This plan assumes
**(b)** unless approved otherwise.

---

## 1. Verified "skip" list (confirmed still true — do NOT touch)

These prior fixes were re-verified against source and must be **preserved**:

- ✅ Anthropic prompt caching is done (`core/llm.py`). Skip.
- ✅ Client token batching exists; SSE uses `fetch`+`ReadableStream` (not `EventSource`); Router + hand-rolled SWR cache (no TanStack Query footguns). Skip.
- ✅ `@tanstack/react-virtual` already installed (no new dep needed _if_ virtualization were pursued — it isn't; see §4).
- ✅ **Keep** the `streamingText` dep in `conversation.tsx` `useMemo` — dropping it freezes streamed text.
- ✅ **Do NOT** wrap the live SSE poll (`read_session_events`) in `to_thread` — adds a per-poll thread hop on the inter-token path. Offload only the REST reads (B5).
- ✅ **Do NOT** reintroduce conversation-list virtualization — removed deliberately (a ResizeObserver on the growing streaming row froze the thread; messages hard-capped at 400). `conversation.tsx:1100-1108`.

---

## 2. Backend

Legend: **GO** (ship as-is) · **GO\*** (ship with the correction noted) · **REVISE** (scope fix) ·
**REWORK** (own commit + failing test + BB entry) · **DROP**.

### B1 — SSE response headers · **GO\***

- **Sites (all 3, all unpatched):** `fastapi_app.py:1122` (`event_stream`), `:1646` (`_openai_event_stream`), `:2680` (voice). None has a `headers=` kwarg today.
- **Change:** add `X-Accel-Buffering: no` and `Cache-Control: no-cache` to all three. **DROP `Connection: keep-alive`** — it is a hop-by-hop header (RFC 7230 §6.1), server-managed; setting it manually is ignored at best. `Cache-Control` does **not** already exist on these responses.
- **Metric:** best-practice for proxy buffering; **no measured claim** without P0(a).
- **Risk:** none. **Test:** assert the two headers are present on each StreamingResponse (no route change → no OpenAPI regen, confirm via `check:api`).

### B2 — SSE wakeup mechanism · **REWORK** (own commit; highest Tier-1 risk)

- **Reality:** the current `_poll_trigger`/`_sse_trigger` is an **unconditional 50 ms heartbeat**, not event-gated: `while True: await asyncio.sleep(0.05); _wake.set()` (`fastapi_app.py:1068-1072`, `:1568-1571`). The "poll tighter while events flow, back off when idle" mechanism **does not exist** and the original plan did not design it.
- **Problem:** `append_event` (`runtime_read_models.py:240`) runs in the worker thread and sets no asyncio.Event the loop can await. "Remove the trigger + tight loop" with no real wakeup ⇒ **busy-loop burning a core per open SSE connection.** The original "Risk: low" is wrong.
- **Correct approach:** keep an `asyncio.Event`, signal it on append via `loop.call_soon_threadsafe(event.set)` plumbed from `append_event` → control plane → each live SSE generator, and use a bounded `wait_for(timeout=…)` fallback so a missed wakeup can't hang the stream. **If that cross-thread plumbing is too invasive this pass, KEEP the 50 ms timer and DROP B2** — do not ship a naive tight loop.
- **Tests (failing-first):** (i) a produced event wakes the stream promptly; (ii) an idle stream does not spin (assert bounded iterations over a fixed wall-clock window). **BB entry** for the busy-loop trap.

### B3 — uvicorn `loop="auto"`, `http="auto"` · **DROP**

- `control_plane.py:1426` runs uvicorn (`uvicorn[standard]>=0.48` pinned), but `loop`/`http` **already default to `"auto"`**. Setting them explicitly is a **no-op**; throughput will not move. At most leave a one-line comment of intent with **zero perf claim**.

### B4 — `read_events_since` O(N)→O(1) · **REWORK** (own commit; highest correctness risk)

- **Site:** `runtime_read_models.py:426-433` — `[snap for snap in self._events if snap.sequence > after]`.
- **Invariants (verified):** append-only (`:243`), monotonic +1 from 1 (`:242`), **front-trimmed at 2000** (`:250-251` `self._events = self._events[-2000:]`).
- **Fatal gap the original plan missed:** after a trim, `self._events[0].sequence == self._sequence - 1999`, not 1. A naive `start = after - base + 1` goes **negative** when `after < base_sequence` (slow client), and `events[negative:]` **silently returns a wrong tail slice** — data corruption on the live polling path feeding both web SSE and `get_session_events`.
- **Correct approach:** `start = max(0, after - self._events[0].sequence + 1)` (guard empty list), or `bisect_right` over a parallel monotonic sequence list; return `self._events[start:start+limit]`.
- **Value caveat:** `_events` is global with one `_sequence` and bounded at 2000, so the O(N) baseline is already tiny — the win is **marginal** and only on the live path (historical sessions go through `_synthesize_history_events`, untouched). Also used by the TUI surface (`snapshot_events_since`, `orchestrator.py:1018-1022`) — any off-by-one hits both.
- **Tests (failing-first):** `after=0` on a trimmed buffer returns the oldest _surviving_ event with correct sequence; `after` far below base does not wrap; parity vs the old scan across a randomized sequence; empty buffer. **BB entry** for the underflow trap.

### B5 — offload blocking SQLite REST reads · **REVISE**

- **Sites:** `list_sessions` (`fastapi_app.py:773`), `get_session_messages` (`:976`), `get_session_events` (`:1028`). Pattern already in use (`anyio.to_thread.run_sync` at `:758`, `:1381+`, `:1557`).
- **Corrections:**
  - `get_session_events` for a **live** session is an in-memory list slice (B4's method) — threading it adds a **pointless** hop. Thread **only** the historical/`_synthesize_history_events` branch.
  - `list_sessions` (`:773`) only truly comes off the loop **together with B7** — otherwise you thread one query and still run N owner lookups inline. Land B5(list_sessions) + B7a in the same commit.
- **Test:** endpoints still return identical data.

### B6 — raise AnyIO threadpool limiter · **REVISE**

- Lifespan is currently empty (`fastapi_app.py:395-397`) → net-new code in the right place. AnyIO default is 40 tokens.
- **Correction:** do **not** derive the value from `HACHI_GATEWAY_MAX_SESSIONS` (read in `cli/main.py:2866`, default 100) — that caps **session objects**, not concurrent blocking reads, and lives in the CLI layer. Pick a defensible constant (~64–100) on **its own env knob**, comment the real rationale (concurrent blocking REST reads + in-flight per-turn `send_message` threads), set via `anyio.to_thread.current_default_thread_limiter().total_tokens = N` inside `_lifespan`.

### B7 — kill the session-list N+1 · **REWORK / SPLIT** (security-adjacent)

- **Reality:** it's up to **3N+1** — `get_recent_sessions` (`session_store.py:698`) + per-session title subquery (`:717-721`) + turn-count subquery (`:729-732`) + the gateway's `get_session_owner` per session (`fastapi_app.py:787`).
- **The trap:** `owner_token_hash` IS a column (`session_store.py:175-177`), but the live gateway reads/writes ownership only in the **in-memory `_connections` map** (`control_plane.py:364-395`); the DB column is **not populated** on the live create path. Folding the column into the SELECT and switching the filter to it **changes which sessions a caller sees** — a privacy/ownership regression.
- **Split:**
  - **B7a (GO, perf):** fold only `title` + `total_turns` into `get_recent_sessions`. Parity test. Land with B5.
  - **B7b (REWORK, decision):** owner N+1 — either persist owner to the DB column on `set_session_owner` (then read from the fold) **recorded in `docs/DECISIONS.md`**, or leave the in-memory dict lookups (they're O(1) gets — may not be worth touching). Do **not** change the filter's source of truth without a regression test covering owned / other-owner / legacy-NULL / live-vs-historical sessions. **BB entry** if the source of truth changes.

### B8 — composite index `messages(session_id, id)` · **REVISE**

- `session_store.py:103-104` **already** has `idx_msg_session ON messages(session_id)`. Stacking `(session_id, id)` creates **two overlapping indexes** → write amplification on the message-insert hot path.
- **Correct approach:** **replace** — drop `idx_msg_session`, create `idx_msg_session_id ON messages(session_id, id)`. SQLite already exposes `id` (rowid/PK) cheaply, so **measure before committing**; for a few hundred messages/session this may be noise. **Test:** the composite index exists, the old one doesn't.

### B9 — `jobs/queue.py` PRAGMAs · **REVISE**

- `jobs/queue.py` sets WAL (`:629`) but **not** `synchronous` (defaults to FULL) → `synchronous=NORMAL` is a **valid add**. But `busy_timeout` is **already effectively set** via the connection `timeout=10` (`:621`) → the busy_timeout half is **redundant**.
- **Correct approach:** add **only** `PRAGMA synchronous=NORMAL` after the WAL line. One-line `docs/DECISIONS.md` note on the NORMAL durability tradeoff (can lose the last txn on OS crash — acceptable for ephemeral jobs per the queue docstring). For contrast, `session_store.py` already sets WAL + NORMAL + busy_timeout (`:64-69`).

### B10 — recall off the inline turn path · **REWORK / SPLIT**

- **Two different things conflated:**
  - `orchestrator.py:1124,1139` are inside `_build_frozen_snapshot` (`:1108-1164`), built at **session start** — _not_ the per-turn cost the original plan implied. **First verify** whether it's already once-per-session (likely a non-issue) before touching.
  - `:1561` is **episodic recall** in `_chat_impl_inner`, run **synchronously each turn**, result needed synchronously (merged into `recall_block` → prompt, `:1567-1586`).
- **Already partly done:** a prefetch pipeline exists (`_enqueue_prefetch_job`/`_run_prefetch_job`/`_pop_prefetch`, `:1183-1340`, consumed `:1546`); **semantic** recall is already prefetched for turns 2+ (sync only on turn 1, `:1547-1549`).
- **The risk:** folding **episodic** recall into prefetch computes it against the **previous** turn's query → episodic results for the wrong query. Acceptable as a heuristic _only_ if explicitly decided.
- **Correct approach:** own commit; record the previous-query staleness tradeoff in `docs/DECISIONS.md`; recall-parity test (episodic content still present, dedup at `:1567-1570` still holds). **BB entry** if prompt contents change.

---

## 3. Frontend

### F1 — memoize Markdown highlighting · **REVISE** (right fix, oversold scope)

- **Correction:** top-level `Markdown` is **already** `React.memo` (`Markdown.tsx:893`) and `parseBlocks` is **already** `useMemo([text, isStreaming])` (`:901`). So **settled bubbles do NOT re-parse** — the "kills O(n²) per-reply re-highlight across the thread" claim is **false**.
- **The real quadratic** is the **single streaming bubble**: as `text` grows, `parseBlocks` re-runs and unmemoized `CodeBlock` (`:667`) re-calls `renderHighlighted` (`:804`) for every block on every token → O(n·k). F1's mechanism is correct **for the streaming bubble only**.
- **Change:** `React.memo` on `CodeBlock` with a **content-hash key** (NOT block index — an open ` ``` ` fence can retroactively change a block when it closes) + `useMemo` the `renderHighlighted` call. Preserves "always render Markdown (no remount/FOUC)".
- **Test:** per P3, a pure-function memoization test (spy highlighter, assert stable-prefix call counts) unless `@testing-library/react`+jsdom are approved. Cover the open-fence-then-close case. **BB entry** for the fence-memo trap.

### F2 — memoize card components · **GO** (only solid as-is item)

- `ActionCardRow` (`conversation.tsx:350`) and `RoutineCard` (`:509`) are plain functions. `React.memo` both + hoist the inline `{contain:'content'}` style to a module const. Handlers come from zustand selectors (referentially stable), so memo will actually help. Visual/eyeballed verification acceptable; render-count test only if the P3 harness exists.

### F3 — redundant on-mount loaders · **REVISE**

- `memory.tsx:301` (`useEffect(() => void loadMemory(), [])`) and `og.tsx:1118` (`void loadOg()`) double-fetch with `bootstrapLiveData` — confirmed. **But** they are also the **refresh-on-navigate** mechanism (per their own comments).
- **Correct approach:** **dedupe** (in-flight guard / short staleness window), do **NOT** remove (removal breaks refresh-on-navigate). **Test:** navigating back still triggers a refresh after the dedupe window.

---

## 4. Dropped / deferred

- **B3** — no-op (`loop`/`http` already auto). Dropped.
- **orjson / ORJSONResponse** — new C-extension **runtime dep** with **no measurement** showing JSON serialization is hot, and big payloads are already bounded. **Defer/reject** per CLAUDE.md ("don't add a dependency without asking" + "solve the stated problem"). If ever pursued: scope to specific endpoints, not a global default, and only after P0(a) shows it's the bottleneck.
- **Conversation-list virtualization** — **leave out** (see §1; deliberate prior fix). Correct call.

---

## 5. Regression-law matrix (CLAUDE.md Rule 2)

| Item | Behavioral?             | Failing-first test                    | Bug-bank entry             |
| ---- | ----------------------- | ------------------------------------- | -------------------------- |
| B1   | config                  | header-present assertion              | —                          |
| B2   | yes                     | wake-on-event + no-spin               | BB (busy-loop)             |
| B4   | yes                     | underflow / parity / empty            | BB (trim underflow)        |
| B5   | yes                     | endpoints return identical data       | —                          |
| B7a  | yes                     | session-list parity                   | —                          |
| B7b  | yes (if filter changes) | owned/other/legacy/live-vs-historical | BB (owner source-of-truth) |
| B8   | schema                  | composite exists, old gone            | —                          |
| B9   | pragma                  | `synchronous==1` assertion            | —                          |
| B10  | yes (if prompt changes) | recall parity + dedup                 | BB (episodic staleness)    |
| F1   | yes                     | stable-prefix highlight call count    | BB (fence-memo)            |
| F3   | yes                     | refresh-on-navigate after dedupe      | —                          |

> B1/B3/B8/B9 are config/index/pragma changes where "failing test first" is awkward — justify
> via assertion tests (or a benchmark), not a red→green behavioral test.

---

## 6. Revised commit order (low-risk first, each independently revertible)

1. **B1 + F2 + B9** — headers (corrected), card memos, queue `synchronous=NORMAL`.
2. **B8** — replace `idx_msg_session` with composite (measure first).
3. **B5 + B7a** — offload REST reads + title/turns fold (must land together).
4. **B6** — threadpool limiter (own knob, not session-cap-derived).
5. **F1** — streaming-bubble highlight memo (+ content-hash key).
6. **F3** — dedupe on-mount loaders.
7. **B4** — `read_events_since` clamp/bisect. _Own commit, heavy tests._
8. **B2** — SSE wakeup (real `call_soon_threadsafe` + bounded `wait_for`), or **keep timer & drop**. _Own commit, heavy tests._
9. **B10** — episodic recall off inline path. _Own commit, DECISIONS note + parity test._
10. **B7b** — owner reconciliation, only if the §2 decision says so.

**Dropped:** B3, orjson, virtualization.

---

## 7. Gate (CLAUDE.md)

- `uv run python scripts/preflight.py` (ruff, mypy-gate, skill-lint, eval, **FULL** pytest, frontend) — report **actual** counts. Windows: `python -m pytest` / `python -m mypy` if `.exe` shims hit OS err 4551 (BB-1).
- **No gateway route changes** (headers/internals only) ⇒ OpenAPI regen should be unneeded — **confirm with `check:api`** (BB-4). If any signature/route does change, run `hachi gateway-openapi` + `npm run --prefix frontend generate:api`.
- Per-change discipline: measure against the item's metric (once P0 is resolved) and **revert anything that doesn't move it**.

---

## 8. Open decisions for the user

1. **P0:** build the SSE-timing harness (a) or ship B1–B4 as correctness-neutral with no numbers (b)?
2. **P3 / F1 test:** add `@testing-library/react`+jsdom dev-deps (a) or pure-function memo test (b)?
3. **B7b:** persist owner to the DB column (reconcile the two stores) or leave the in-memory lookups?
4. **B2:** invest in the cross-thread wakeup, or keep the 50 ms timer and drop B2?
