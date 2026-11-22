# Phase 4 — Next-Gen Memory: the OG Memory Graph

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy · **Date:** 2026-06-12
**Inputs:** Phase 0 §7 (memory as implemented, all direct reads), Phase 1 TD-3/TD-5/R4/R5, Phase 2
(format affordances + retrieval v2), Phase 3 §8 (steal Hermes' recall maturity + OpenClaw's
human-readable ergonomics, expressed as `.og`).
**Voices:** §1 = What I found (recap) · §2–§9 = What I propose.

---

## 1. What exists today (recap, with the gap named)

| Layer | Today | Limitation |
|---|---|---|
| Active context | `MemoryManager`: 30-msg sliding window, skill-switch compaction, tool-result clearing, LLM checkpoint ✅ memory.py | Works; not memory in the durable sense |
| Episodic | `SessionStore` SQLite transcripts + titles ✅ session_store.py | Searchable text (`core_search_sessions`), but no structure — a transcript is not knowledge |
| Semantic | `MemoryVault` ChromaDB ×5 collections; facts = **atomic strings** with `{category, timestamp}` ✅ memory_vault.py:74–137 | No entities, no relations, no validity window, no projects, no decisions, no causality. Recall = cosine top-k of sentences ✅ orchestrator.py:824–829 |
| Write path | Post-turn LLM extraction → 3 buckets (user/workspace/agent) ✅ memory.py:166–235 | Sentence-shaped; failures silent (TD-5); queue is in-memory (TD-3) |
| Read path | Frozen snapshot (profile + agent + top-8 “important context”) + per-query top-5 recall ✅ orchestrator.py:641–680, 824–839 | Fixed-query hot-path Chroma hit (W10); no time/project filters; superseded facts compete with current ones |

**The gap, in one sentence:** the engagement brief assumed `memory.og` exists; it does not (Phase 0
D1). Memory is the one subsystem where the `.og` thesis — typed, traversable, token-efficient
knowledge — has not been applied to the data that actually distinguishes a *personal* agent. This
phase designs that application.

## 2. Design goals (proposal)

G1. **Memory is files** — human-readable, diffable, git-able `.og` under the user's data dir
    (OpenClaw's most-praised memory property Ⓢ, with types OpenClaw lacks).
G2. **Typed graph, reused machinery** — nodes + `->[:key=value]` edges parse with the *existing*
    parser (parser.py:299–310 ✅); serializer round-trips writes (serializer.py ✅). No new format.
G3. **Hybrid retrieval** — symbolic (FTS5/BM25 + filters) ⊕ semantic (embeddings) ⊕ graph expansion;
    the same Retrieval-v2 ranking core proposed in Phase 2 P0 serves skills *and* memory.
G4. **Governed evolution** — every mutation versioned via `::changelog`, superseded—not overwritten
    (the direct answer to Hermes' Curator complaint 🌐 Phase 3 §3); MemoryGuard + quarantine retained.
G5. **Token-shaped output** — recall returns a composed *resume pack* (~300–600 tok), not raw chunks.

## 3. Schema — node and edge vocabulary

New `::schema` (validated by lint; all parseable today):

**Node types** (`->[:role=…]`):
`episode` (a session/day summary) · `fact` (atomic, with validity) · `decision` (ADR-shaped: choice +
rationale + status) · `task` (status: open/blocked/done) · `project` (container + status) · `person`
(relationship memory) · `preference` (user_profile successor) · `insight` (causal/post-mortem) ·
`artifact` (file/URL/runbook pointer).

**Edge types** (`->[:key=value]`, value = node id or ISO date):

| Edge | Meaning | Memory dimension |
|---|---|---|
| `t=2026-05-14` / `valid_until=…` | event time / expiry | **temporal** |
| `about=<project>` | membership | **project** |
| `involves=<person>` | participation | **relationship** |
| `decided_in=<episode>` | provenance | **decision** |
| `supersedes=<node>` | newer truth replaces older (old node kept, marked) | decision/fact hygiene |
| `caused_by=<node>` / `led_to=<node>` | causal chain | **causal** |
| `blocks=<task>` / `blocked_by=<node>` | dependency | project |
| `next=<task>` | ordered continuation | project |
| `evidence=session:<id>#<turn>` | link into SessionStore transcript | auditability |

**File layout** (platformdirs data dir; one graph, sharded for diff ergonomics):

```
memory/
├── profile.og          # preference/person nodes about the user (succeeds user_profile, keeps 25-entry curation rule)
├── agent.og            # behavioral corrections (succeeds agent_profile)
├── projects/<slug>.og  # one file per project: project/task/decision/insight/artifact nodes
├── people/<slug>.og    # person nodes + cross-project relationship edges
└── journal/2026-06.og  # episode + loose fact nodes, monthly shard (OpenClaw daily-notes ergonomics, typed)
```

Node IDs are file-qualified (`projects/billing-db-migration:use-pgloader`) — which is why Phase 2 P0
“qualified IDs” is a **prerequisite** (the shipped collision bug ▶ would be fatal in memory).

## 4. Retrieval — symbolic ⊕ semantic ⊕ graph (the 3-stage recall)

Mirrors the skill engine's 3-pass shape so one mental model serves both:

**Stage A — candidate seeding (symbolic).** SQLite **FTS5** mirror of (name, keywords, dense) — the
component Hermes proved at 10 ms/10k entries 🌐 — plus structured filters parsed from the query
context: time window (“last month” → `t ∈ [2026-05-01, 2026-05-31]`), type hints (“decision”,
“who”), entity matches against person/project name table. BM25-scored.

**Stage B — semantic merge.** Chroma cosine over node `dense+full` (Chroma already a dependency ✅).
Merge A+B by reciprocal-rank fusion; apply recency decay `score·λ^Δdays` (λ≈0.97, decision/preference
nodes exempt) and a small use-count prior (extend the existing usage tracker ✅ engine.py:1106–1125).

**Stage C — graph expansion (the part flat RAG cannot do).** From top seeds, walk ≤2 hops along
`about/blocks/blocked_by/next/supersedes/caused_by/involves`, with rules:
- a node reached via `supersedes` **replaces** its target in results (stale truth filtered, kept on disk);
- open `task` nodes of a seeded `project` always join;
- `caused_by` chains attach to any blocked task;
- expansion budget ≈ 12 nodes, then the **resume-pack composer** renders dense lines + the single
  most load-bearing `full` block into ~300–600 tokens.

The pack replaces both today's fixed `semantic_search("important context")` snapshot (kills the
hot-path query, Phase 1 W10/R20) and the flat recall block (orchestrator.py:831–839 ✅).

## 5. The worked example — “continue the database migration from last month”

### 5.1 The memory file as it would exist (`memory/projects/billing-db-migration.og`)

```og
::meta
  title: Billing DB Migration
  version: 1.4.0
  updated: 2026-05-21
  domain: project|database

::index
  # node-id            | type     | scope | conf | keywords
  billing-db-migration | project  | all   | 1.0  | migration, postgres, billing, database
  use-pgloader         | decision | all   | 1.0  | pgloader, tooling, decision
  migrate-invoices     | task     | all   | 1.0  | invoices, table, done
  migrate-payments     | task     | all   | 1.0  | payments, table, blocked
  fk-cycle-issue       | insight  | all   | 1.0  | foreign key, cycle, refunds
  runbook              | artifact | all   | 1.0  | runbook, script, steps

::changelog
  2026-05-21 | updated | node[migrate-payments] | blocked on FK cycle
  2026-05-14 | added   | node[use-pgloader]     | supersedes use-dms after spike

::node[billing-db-migration]
->[:role=project]
->[:t=2026-05-02]
::dense
Migrate billing Postgres 12 → 16. Status: in-progress. 1/3 tables done.

::node[use-pgloader]
->[:role=decision]
->[:t=2026-05-14]
->[:supersedes=use-dms]
->[:decided_in=journal/2026-05:ep-2026-05-14]
->[:about=billing-db-migration]
::dense
Decision: pgloader, not AWS DMS. Status: accepted.
::full
DMS spike failed on enum casts (3 days lost). pgloader handles enums + identity
columns; rerun-safe with --on-error-stop. Revisit only if CDC needed.

::node[migrate-payments]
->[:role=task]
->[:t=2026-05-21]
->[:about=billing-db-migration]
->[:next=migrate-refunds]
->[:blocked_by=fk-cycle-issue]
::dense
Migrate payments table. Status: BLOCKED.

::node[fk-cycle-issue]
->[:role=insight]
->[:t=2026-05-21]
->[:caused_by=circular-fk-payments-refunds]
->[:involves=people/priya:priya]
->[:evidence=session:8f3a92#41]
::dense
payments↔refunds circular FK blocks pgloader ordering.
::full
Fix agreed with Priya (DBA): drop FK pre-load, recreate post-load via
runbook §4. Schema freeze until Jul 1 — no column changes during migration.

::node[runbook]
->[:role=artifact]
->[:about=billing-db-migration]
::dense
~/work/billing/migrate/runbook.md + scripts/migrate.sh (idempotent).
```

### 5.2 Query path, step by step

1. **Parse query context**: tokens {continue, database, migration}; temporal phrase “last month” →
   window 2026-05-01..31 (today = 2026-06-12).
2. **Stage A**: FTS5 → `billing-db-migration` (BM25 0.91), `migrate-payments`, `use-pgloader`;
   window filter boosts all (every `t` in May).
3. **Stage B**: embedding merge concurs (RRF keeps the same head); decay mild (3 weeks).
4. **Stage C**: from `billing-db-migration` pull open tasks → `migrate-payments` (status BLOCKED) →
   `blocked_by` → `fk-cycle-issue` → `caused_by` + `involves` → person constraint; decision edge
   resolves `use-pgloader`, and its `supersedes=use-dms` **suppresses** the stale DMS decision from
   the pack; `artifact` joins via `about`.
5. **Resume pack rendered into the turn's dynamic prompt tail** (≈220 tok):

```
[Memory: project billing-db-migration — in-progress, 1/3 tables done (t:2026-05-02..21)]
Decision in force: pgloader, not DMS (enum casts; rerun-safe). [use-pgloader, 2026-05-14]
Open task: migrate-payments — BLOCKED by payments↔refunds circular FK.
Fix agreed w/ Priya: drop FK pre-load, recreate post-load (runbook §4). Schema freeze until Jul 1.
Artifact: ~/work/billing/migrate/runbook.md · scripts/migrate.sh
Evidence: session 8f3a92#41 (load_memory_node for full detail)
```

6. The agent resumes by opening the runbook at §4 — no re-derivation, no stale-DMS confusion, no
   “what was blocking this again?”. Flat top-k recall over today's sentence store would return the
   *strings* “user is migrating a database” and possibly both DMS and pgloader sentences with no
   ordering between them — the `supersedes` and `blocked_by` edges are precisely what cosine cannot
   express.

## 6. Write path — how the graph gets populated (governed)

1. **Per-turn extraction upgraded**: the existing post-turn job (memory.py:166–235 ✅) switches from
   “3 buckets of sentences” to a schema-constrained tool-call emitting typed nodes+edges (validated
   against §3 before write; rejects malformed). Runs on the **durable queue** (Phase 1 R5 — hard
   prerequisite, else memory writes stay lossy per TD-3/TD-5).
2. **Episode nodes**: one per session close (title + 3-line summary + `evidence=` link), giving the
   journal layer for free from SessionStore data ✅.
3. **Explicit tools**: `core_save_memory` keeps its signature but writes a typed node;
   new `link_memory(from, edge, to)` and `load_memory_node(id, blocks=…)` mirror the skill tools.
4. **The Gardener** (nightly queue job): dedupe near-identical facts, propose `supersedes` for
   contradictions, expire `valid_until`, compact journal shards. **Governance rule:** the gardener
   *appends* (changelog + supersedes) and only auto-applies whitelisted low-risk merges; everything
   else lands as a reviewable “memory diff” surfaced in TUI — the structural answer to Hermes'
   overwrite dealbreaker Ⓢ.
5. **Safety unchanged**: every write still passes MemoryGuard scan→quarantine ✅ memory_vault.py:111–150;
   `evidence=` links keep provenance to raw transcripts.

## 7. Migration from today's implementation

| Step | Content | Effort (conf.) |
|---|---|---|
| M0 | Read-side: `MemoryIndex` (FTS5 + reuse Retrieval-v2 ranker) over a new `memory/` dir; recall = RRF(old Chroma, new index) behind `memory.graph=true` flag. No data moves. | 3–5 d (high) |
| M1 | Write-side: typed extractor + episode nodes + one-time converter Chroma→`journal/*.og` (content/category/timestamp preserved; extend the existing `memory_importer.py`, which already parses ChatGPT/Gemini/Hermes exports Ⓐ). Old collections become **derived indexes**, rebuilt from files. | 4–7 d (medium-high) |
| M2 | Graph features: edges in extractor, Stage-C expansion, resume-pack composer replacing frozen-snapshot+recall blocks (orchestrator.py:641–680, 824–839). | 4–6 d (medium) |
| M3 | Gardener + memory-diff TUI surface; profile.og/agent.og cutover (keep 25-entry curation rule ✅ memory_vault.py:28). | 3–5 d (medium) |
| M4 | Chroma demoted to optional semantic index (in-memory provider = FTS5-only path stays viable ✅ memory_provider seam, orchestrator.py:1266–1279). | 1–2 d (high) |

**Hard prerequisites from earlier phases:** durable job queue (R5), loud memory failures (R4),
qualified node IDs (Phase 2 P0), Retrieval v2 ranker (Phase 2 P0), per-session serialization (R1 —
single-writer guarantee for files).

**Compatibility:** memory tool names/signatures unchanged; SessionStore untouched (it becomes the
evidence layer); existing users' Chroma data auto-imported by M1's converter on first boot.

## 8. Risks & open questions (honest)

| Risk | Mitigation / status |
|---|---|
| Typed extraction quality < sentence extraction | Schema-constrained tool-call output + validation + quarantine on failure; fall back to `fact` nodes when structure is uncertain. Measure with a 100-exchange labeled set (extend Phase 2 benchmark harness). |
| File growth / diff noise | Monthly journal shards; gardener compaction; `::index` keeps Pass-1 cheap per file. |
| Plain-text sensitivity on disk | Same exposure as OpenClaw's praised markdown memory — but offer optional at-rest encryption via the existing secret_store/Fernet path Ⓐ secret_store.py:123–150. **Open question for the user: default off or on?** |
| Concurrent writers (channels + scheduler) | Serialized sessions (R1) + queue single-consumer; file writes atomic (write-temp-rename). |
| Token cost of resume packs | Pack budget enforced (600 tok cap); packs sit in the *dynamic* prompt tail so the cached prefix is unaffected ✅ prompt_composer.py:128–132. |
| “Is this over-engineering vs. Hermes' FTS5?” | M0/M1 alone ≈ Hermes parity (fast symbolic recall over files). M2's edges are the wedge — ship M0/M1 first, validate, then decide M2 scope with usage data. |

## 9. Why this wins (tie-back to positioning)

- Closes Phase 0 **D1** honestly: `memory.og` becomes real, making the brief's claimed architecture true.
- Extends the Phase 3 governance story to memory: *diffable, versioned, supersede-not-overwrite,
  quarantined* — three verified competitor pains answered in one design (OpenClaw: opaque dumps cost
  tokens; Hermes: ungoverned self-modification; both: no decision/causal structure).
- Gives marketing the demo that sells the moat: “continue the migration from last month” resolving
  through typed edges in ~220 tokens is a *visible* intelligence difference, not a benchmark claim.
- Total estimated effort M0–M4: **15–25 engineering-days** (medium confidence), strictly behind the
  Phase 1 P0s.
