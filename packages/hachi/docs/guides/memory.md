# Memory Architecture

How Hachi remembers things across turns and sessions, what gets written, how recall
works, and the retrieval-quality controls. Audited and hardened under Issue 10
(see `DECISIONS.md`).

## Three layers

| Layer | Store | Lifetime | Code |
|---|---|---|---|
| **Active context** | in-process message history | current session, compacted | `core/memory.py` (`MemoryManager`) |
| **SessionStore** | SQLite transcript (`sessions.db`) | durable, per session | `core/session_store.py` |
| **MemoryVault** | ChromaDB vectors | durable, long-lived facts | `core/memory_vault.py` |

The MemoryVault is split into four collections:

- `core_memory` — workspace/task facts (the main semantically-queried store)
- `user_profile` — stable facts about the user (hard cap 25 entries)
- `agent_profile` — facts about the agent's own behaviour (hard cap 25)
- `delegation_log` — sub-agent delegation outcomes

All writes are routed through the durable jobs queue (`jobs/queue.py`) so a turn is
never blocked on embedding/IO; a resident worker drains it.

## Writing

Three write paths, each producing **atomic, structured facts** (not raw transcript
snippets):

1. **Explicit** — the `core_save_memory` tool enqueues a `_smart_upsert` job that
   semantically searches for the 3 most similar existing facts and asks an LLM to
   merge/atomise before writing. This is the highest-quality path. *(Issue 10 fix: the
   old bare-`upsert_fact` fallback that bypassed this dedup on any error was removed —
   on consolidation failure we now log and skip rather than write a likely duplicate.)*
2. **Auto-sync** — after every clean turn, `sync_turn` extracts `user_facts` /
   `workspace_facts` / `agent_facts` from the last exchange. *(Issue 10 fix: a
   `_is_substantive_fact` quality gate now drops trivial extractions — empty, very
   short, or pure acknowledgements like "ok"/"thanks" — before they reach the vault,
   in addition to the pre-existing 30-char combined-exchange gate.)*
3. **Compaction flush** — when active history exceeds `max_active_messages`, dropped
   messages are extracted and flushed into `core_memory`.

**Dedup.** Facts are content-addressed by SHA-256 (identical strings are idempotent),
plus the `_smart_upsert` LLM consolidation for near-duplicates. Pure paraphrase dedup
at write time remains a `# TODO(issue10)` (cosine-similarity skip > ~0.92).

**Bounds.** `user_profile`/`agent_profile` are hard-capped at 25 entries. `core_memory`
now has a configurable soft cap (`memory.core_memory_max_entries`, default 1000) with
oldest-first pruning so it cannot grow unbounded. `delegation_log` remains unbounded
(`# TODO(issue10)`).

## Reading / recall

Recall is **query-driven**, not bulk-injected, for the workspace store:

- **Per-turn semantic recall** — `core_memory` is queried with the actual user input
  (`top_k=5`) and the results injected into the per-turn (non-cached) system block.
  On turns after the first, this runs as a background prefetch keyed to the prior
  turn's input and is consumed at the next turn's start, hiding latency.
- **Session-start snapshot** — *(Issue 10 fix)* previously this probed the vault with a
  **fixed literal query `"important context"`**, which biased results toward whatever
  facts happened to use those words. It now calls `get_recent_facts(limit=8)` — an
  unbiased recency fetch — so the snapshot reflects what's actually recent.
- **Profiles** — `user_profile` and `agent_profile` are small (≤25) and injected into
  the session-stable, prefix-cached system block. Bulk injection here is acceptable
  because the size is bounded; it is not done for the unbounded `core_memory`.

### Retrieval-quality controls (Issue 10)

The core fix: **a similarity threshold**. Previously `_query_collection` fetched
ChromaDB distances but never used them — it returned `top_k` results regardless of
relevance, so a query with no good match still injected 5 unrelated facts every turn.

Now results whose **cosine distance** exceeds `memory.recall_distance_max` (default
**0.85**, range `[0, 2]`) are dropped. The default is deliberately conservative
(favours recall — keeps broadly-related facts, drops only clearly-unrelated ones) and
is fully tunable:

```toml
[memory]
recall_distance_max = 0.85      # lower = stricter; null = disable (legacy top-k-always)
core_memory_max_entries = 1000  # soft cap with oldest-first pruning
```

Both are wired from config into the `MemoryVault` constructor at session boot
(`gateway/orchestrator.py` → `memory_provider.ChromaMemoryProvider.initialize`), so
editing `settings.toml` actually changes runtime behaviour.

Optional **hybrid retrieval**: with `memory.graph = true` an FTS5 (BM25) keyword index
is merged with the vector results via Reciprocal Rank Fusion. Off by default.

## Benchmark-style assessment

Design-level estimate from the audit (no live corpus; reasoned from the code):

| Axis | Before | After |
|---|---|---|
| Query precision | Poor — top-k returned regardless of score | Improved — distance-thresholded |
| Session-snapshot relevance | Poor — biased fixed query | Improved — unbiased recency |
| Write precision | Medium — no quality gate on auto-sync | Improved — substantive-fact gate |
| Near-dedup | Poor — exact-hash only; fallback bypassed dedup | Improved — bare fallback removed |
| Store-size risk | High — `core_memory` unbounded | Bounded — soft cap + prune |
| Latency (first turn) | ~200–600 ms (Chroma client + embed-model load) | unchanged |
| Latency (later turns) | ~5–30 ms (embedded, prefetched) | unchanged |

Latency characteristics: the ChromaDB `PersistentClient` is lazily initialised on first
access; the embedding model (all-MiniLM-L6-v2) loads once (~200–400 ms). Concurrent vault
access is serialised by an `RLock`.

## Remaining follow-ups (`# TODO(issue10)`)

- Cosine-similarity write-time dedup for paraphrases (> ~0.92 → skip).
- Bound / TTL the `delegation_log` collection.
- LRU (not just oldest-first) eviction for `core_memory`.
