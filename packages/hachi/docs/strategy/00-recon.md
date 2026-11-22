# Phase 0 — Repository Reconnaissance

> **Historical document.** Written before the Hachi rename. References to
> "Hachi", the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project now called **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

**Engagement:** Hachi Principal Engineering & Product Strategy
**Date:** 2026-06-12 · **Branch:** `feat/telegram-setup-and-pypi-release` (clean) · **HEAD:** `cd77a4d`
**Voice:** This document is *observation only*. No recommendations appear here (those start in Phase 1).

## Evidence provenance

| Marker | Meaning |
|---|---|
| ✅ | Read directly by the lead auditor (file open in this session, line numbers verified) |
| Ⓐ | Reported by a recon subagent with cited paths/lines; spot-checked but not fully re-read |
| ▶ | Observed by *executing* something (test run, grep) in this session |
| ⚠️ UNVERIFIED | Claim found in repo docs that has not been independently verified |

Where a subagent's claim contradicted a direct read, the direct read wins. (Concretely: one subagent
misreported the tool names in `tools/og_tools.py` and `tools/os_tools.py`; the tool inventory below was
re-derived by grepping every `"name":` schema field in `src/hachi/tools/` ▶.)

---

## 1. Snapshot

| Metric | Value | Source |
|---|---|---|
| Tracked files | 418 | ▶ `git ls-files` |
| Python LOC | 60,782 total — 38,767 in `src/`, 22,015 in `tests/` | ▶ `wc -l` |
| Frontend LOC (ts/tsx/js) | 2,775 across 56 `.tsx` + 15 `.ts` files | ▶ |
| `.og` files tracked | 30 (29 shipped skills/brain + 1 test fixture) | ▶ |
| Markdown docs | 28 files (incl. a 76 KB format spec and 105 KB knowledge-transfer doc) | ▶ / Ⓐ |
| Test suite | **1,357 passed, 13 skipped, 0 failed in 60.8 s** (`uv run --frozen python -m pytest -q`) | ▶ |
| Languages | Python 3.11+ (engine), TypeScript/React (web UI), `.og` DSL (skills) | ✅ |
| Version | 0.1.0, MIT license, hatchling build | ✅ pyproject.toml:8 |

**One-sentence identity (as the code actually is):** a Python autonomous-agent engine whose system prompt,
skills, permissions, and MCP/integration config are all expressed in a custom `.og` graph-file format,
fronted by a Textual TUI (primary), a FastAPI gateway + React web app (secondary), and messaging channels
(Telegram real; Slack/Discord/WhatsApp present), with ChromaDB+SQLite memory.

---

## 2. Repository layout (annotated, real paths)

```
hachi/
├── pyproject.toml              # hatchling; deps: anthropic, chromadb, fastapi, textual, typer… ✅
├── uv.lock                     # 3,779 lines Ⓐ
├── Dockerfile                  # python:3.12-slim → `hachi gateway` on :8787 Ⓐ
├── docker-compose.yml          # gateway + frontend services, secret-mounted API token Ⓐ
├── install.sh / install.ps1    # clone-to-~/.hachi-src + uv bootstrap installers Ⓐ
├── README.md                   # public claims: 97.2% token savings, 40+ features Ⓐ
├── docs/reference/objectgraph-spec.md   # 76 KB .og whitepaper (12 sections) ✅(headers)
├── KNOWLEDGE_TRANSFER.md       # 105 KB internal narrative Ⓐ
├── QA_TESTING_PLAN.md          # 47 KB, 8 QA phases marked complete Ⓐ
├── god-tier-plan.md / tui-product-brief.md             # roadmap + TUI design brief (intentional docs) Ⓐ
├── abvc/ (.gitkeep only), image.png (59 KB, unreferenced)   # stray Ⓐ
├── openapi/hachi-openapi.json           # generated gateway contract (38.5 KB) Ⓐ
├── docs/
│   ├── benchmark.md            # the 97.2% methodology Ⓐ (cross-checked vs test ✅)
│   ├── configuration.md, cookbook.md, QA_BUG_REPORT.md
│   └── qa/                     # 11 manual QA reports (core-engine, telegram, google, …)
├── frontend/                   # TanStack Start + React 19 + Vite (NOT SvelteKit) Ⓐ
│   └── src/generated/hachi-api.ts       # openapi-typescript output (1,394 lines) Ⓐ
├── qa/fixtures/                # isolated-runtime setup script + .env.sample
├── src/hachi/
│   ├── cli/main.py             # Typer CLI, 4,594 LOC, ~19 commands + 5 sub-apps Ⓐ
│   ├── core/                   # 47 modules: loop, memory, llm, permissions, vault, …
│   ├── og_engine/              # parser, engine, serializer, skill_md, graph_viz ✅
│   ├── tools/                  # 16 modules, ~56 static tool schemas ▶
│   ├── gateway/                # orchestrator (boot), fastapi_app, control_plane, workspace ✅
│   ├── channels/               # telegram (+setup/commands), slack, discord, whatsapp, router
│   ├── integrations/           # google (10 modules), notion (3), slack (3)
│   ├── jobs/                   # queue.py (in-memory durable-ish), scheduler.py
│   ├── tui/                    # app.py 3,063 LOC + widgets/formatters/state_store
│   ├── default_skills/         # 29 shipped .og files + manifest.json ✅
│   └── daemon.py
└── tests/                      # ~130 test files, ~1,207 test functions Ⓐ▶
```

---

## 3. Entry points & runtime surfaces

### 3.1 CLI (`src/hachi/cli/main.py`, 4,594 LOC) Ⓐ

Top-level commands (line numbers per subagent audit): `onboard` (902), `quickstart` (922),
`permissions` (1012), `reauth` (1137), `run` (1296, TUI default / `--repl` fallback / `--resume`),
`gateway` (1331), `gateway-status` (1345), `gateway-openapi` (1393), `setup` (1415, tiers
lightning/recommended/enhanced/power), `config*` (1478–1605), `google-auth` (1654), `models` (1733),
`secrets` (1812), `doctor` (1857), `security-audit` (1958).
Sub-apps: `schedule` (2142), `skill` (2574 — import/list/show/search/deps/graph/viz/lint/**benchmark**/pack…),
`mcp` (3405), `memory` (3575), `session` (3863).

### 3.2 TUI (`src/hachi/tui/`, 4,349 LOC) Ⓐ

`app.py` (3,063 LOC) runs the agent **in-process** via `boot_agent()` — not through the gateway.
Multi-pane Textual layout (transcript, collapsible sidebar, slash-command palette), reading state from
`AgentSession.snapshot_*` read-models; permission approvals via modal screens.

### 3.3 Gateway (`src/hachi/gateway/fastapi_app.py`, 540 LOC) Ⓐ

~28 typed REST routes + SSE: session CRUD (`/sessions*`), event polling + `/sessions/{id}/stream` (SSE, line 315),
runtime introspection (`/runtime/events`, `/runtime/mcp/inventory`, `/jobs/*`, `/permissions/audit`),
config mutation (`PUT /config/provider|permissions|memory`), onboarding (`/setup*`),
**OpenAI-compatible** `/v1/chat/completions` + `/v1/models` (435, 459), and channel webhook
`POST /channels/{channel}/inbound` (482). Auth: bearer token (`HACHI_GATEWAY_API_TOKEN`), optional on loopback.
`control_plane.py` is a typed facade enforcing max 100 sessions / 100k-char prompts Ⓐ.

### 3.4 Channels (`src/hachi/channels/`) Ⓐ

`base.py` defines `InboundMessage`/`OutboundMessage`/`ChannelAdapter` + `SessionRunner` callable;
`router.py`/`runner.py` route channel messages into `session.chat()`. Telegram is the mature path
(long-poll `telegram.py`, guided `telegram_setup.py`, `/command` dispatch `telegram_commands.py` — tested in
`tests/test_telegram_commands.py`, `tests/test_telegram_setup.py`). Slack/Discord real but thinner; WhatsApp
minimal (flagged by subagent as possible stub — Phase 1 verifies). No channel test files for
Discord/Slack/WhatsApp Ⓐ.

### 3.5 Other entries

- `daemon.py` — background daemon mode (CLI `hachi daemon`, tests `test_cli_daemon.py`, `test_daemon.py`).
- Scheduler fires stored schedules straight into `session.chat()` ✅ orchestrator.py:1568–1578.
- OpenAI-compatible endpoint makes Hachi usable as a backend for third-party clients Ⓐ.

---

## 4. Dependencies, build, deploy

- **Runtime deps** ✅ pyproject.toml:34–48: pydantic, fastapi, uvicorn, anthropic, httpx, chromadb,
  platformdirs, keyring, cryptography, tomlkit, typer, rich, textual. Extras: google/notion/slack/browser
  (playwright)/tracing (otel)/presentations (pptx) ✅ :50–81.
- **LLM providers**: Anthropic native + OpenAI-compatible/OpenRouter/Ollama/Gemini via
  `core/llm.py` + `core/unofficial_providers.py` (default model if unconfigured: `claude-haiku-4-5`
  ✅ orchestrator.py:1112–1113).
- **CI** Ⓐ `.github/workflows/ci.yml`: 5 jobs — `test`, `security` (`security-audit --fail-on-high`;
  `continue-on-error: true` on main at line 49, strict `--fail-on-medium` on PRs at 52–53), `lint`
  (ruff+mypy both `continue-on-error`), **`benchmark`** (`hachi skill benchmark --json --threshold 0.80`,
  lines 80–98 — the token-savings claim is a hard CI gate), and `frontend-contract` — **commented out**
  (lines 100–143).
- **Release** Ⓐ `.github/workflows/release.yml`: tag-push → version-vs-tag verification → `uv build` →
  PyPI publish via OIDC trusted publishing (no token). Documented in RELEASING.md.
- **Install story** Ⓐ: curl|bash / irm|iex installers (clone to `~/.hachi-src`, uv-run launcher),
  `pipx install hachi-og`, source+uv, or docker-compose (gateway :8787 + frontend :5173).
- **User-side state** ✅ core/paths.py:73–81: platformdirs-native dirs (config/data/state/cache) with
  one-time import from legacy `~/.hachi` (paths.py:95–120). N.B. several docstrings still say
  `~/.hachi/skills/` (e.g. engine.py:4) while the real default is the platformdirs data dir.

---

## 5. Test suite & quality signals

- ▶ Full run on Windows: **1,357 passed, 13 skipped, 60.8 s** (`uv run --frozen python -m pytest -q -p no:cacheprovider`).
- Ⓐ ~130 test files / ~1,207 test functions; no root `conftest.py` — mock LLMs are defined inline per
  test file (e.g. `_SpendingLLM` in tests/test_loop_resilience.py:18–32); `core/testing.py` provides
  `InMemoryConversationMemory`.
- **Covered well** Ⓐ: og_engine (10 files incl. parser/serializer/RBAC/lint/benchmark), tools (~189 tests),
  sessions (~88), TUI (~78), CLI (~78), gateway (7 files), security/permissions (5 files).
- **Thin or absent** Ⓐ: `core/loop.py` core dispatch (only budget/resilience scenarios; no multi-turn
  multi-tool E2E), `gateway/orchestrator.py` (no direct test file), `core/memory.py` MemoryManager
  (indirect only), `core/memory_vault.py` (quarantine only), `core/session_store.py`,
  `core/credential_vault.py`, `tools/os_tools.py`, `tools/delegation_tools.py`, `tools/og_tools.py`
  (covered indirectly via CLI tests), channels other than Telegram, Notion integration.
- **QA artifacts**: 11 manual reports in docs/qa/ + docs/QA_BUG_REPORT.md (3 Medium, 21 Low open as of
  2026-06-12; 6 High fixed) Ⓐ. docs/qa/REVERIFY.md records 15/16 bugs fixed; the once-PARTIAL
  `::assertions` plural-parse bug is now fixed in code ✅ parser.py:301–310 (regex accepts optional plural `s`).

---

## 6. The `.og` pipeline — as actually implemented

This is the claimed differentiator, so it gets the deepest treatment. All ✅ unless noted.

### 6.1 What `.og` is used for (and not)

| Use | Real? | Where |
|---|---|---|
| Skills (knowledge/procedures) | ✅ Yes — core use | `default_skills/**/*.og`, user `skills/` dir, `learned/`, `imported/` |
| System persona ("brain") | ✅ Yes | `brain.og` parsed + rendered into system prompt — workspace.py:103–178 |
| Device permissions | ✅ Yes | `device-permissions.og` consumed by `PermissionGate` — orchestrator.py:1085–1094 |
| MCP server config | ✅ Yes | nodes with `role=mcp` start subprocess servers — orchestrator.py:964–1019 |
| Integrations/env config | ✅ Yes | `role=env` / `role=integration` nodes — orchestrator.py:1155–1160 |
| REST tool definitions | ✅ Yes | `::api[name]` blocks → `UniversalRestAdapter` — parser.py:599–624, orchestrator.py:1380–1385 |
| Sub-agent role personas | ✅ Yes | `default_skills/roles/{coder,researcher,emailer,analyst,devops}.og` |
| **Conversation/long-term memory** | ❌ **No** | Memory is ChromaDB (`core/memory_vault.py`) + SQLite (`core/session_store.py`). ▶ grep: `memory.og`, `workflows.og`, `projects.og` — **zero matches in the repo** |

> The engagement brief described the differentiator as "`skills.og`, `memory.og`, `workflows.og`,
> `projects.og`". Only the skills/brain/permissions/config family exists. There is **no OG-backed memory,
> workflow, or project graph today** — that is aspiration, not implementation. (Material for Phases 2 & 4.)

### 6.2 Production of `.og` files (4 paths)

1. **Shipped**: 29 files copied from `src/hachi/default_skills/` per `manifest.json` core/optional
   packs at first boot — skill_packs.py:90–109, workspace.py:54–61.
2. **Wizard-generated**: `device-permissions.og` via `generate_permissions_og(tier, paths)` — workspace.py:296–301.
3. **Agent-authored**: `save_skill` tool → `SkillEngine.upsert_skill` writes `<skills>/learned/<slug>.og`,
   hot-loads it, bumps semver+changelog on refinement, lints and returns advisories — engine.py:621–771.
   Serializer escapes content lines starting with `::`/`->[:` (structural-injection defence) — serializer.py:29–40.
4. **Imported**: `SKILL.md` (Claude Agent Skills format) → `.og` via `skill_md_to_og` into `imported/` —
   engine.py:783–821; community-pack infra exists in `core/community_packs.py` (no packs shipped Ⓐ).

### 6.3 Parsing (parser.py, 691 lines)

Regex/line-oriented, not a grammar: `NODE_PATTERN`/`EDGE_PATTERN`/`BLOCK_PATTERN` — parser.py:299–310.
File-level blocks `::meta|::index|::schema|::changelog` (315–318); ~17 node-level block types; metadata
edges `->[:key=value]` (537–550). Models are pydantic: `OGFile`, `OGNode`, `OGIndexEntry` (confidence
field per entry, 71–74), `OGChangelogEntry`. `::api` blocks get strict JSON validation (604–620).

### 6.4 Indexing & retrieval (engine.py, 1,235 lines)

- Boot: `SkillEngine(agent_role="orchestrator")` globs `**/*.og` under the skills dir and builds
  `_nodes: dict[name→OGNode]` + `_keyword_index: dict[keyword→[names]]` — engine.py:248–252, 295–346.
  **Node names are a single global namespace across all files; a duplicate name silently overwrites** —
  engine.py:323–324.
- `search(query)`: exact term match against the keyword index **plus a fuzzy substring scan over every
  keyword** — engine.py:360–372. The fuzzy pass is O(#keywords × #query-terms); docstrings/spec
  call routing "O(1)" (engine.py:17, parser.py:410), which holds only for the exact-match dict path.
  No semantic/embedding search; no ranking by `confidence`; results ordered only by `::traverse`
  priority — engine.py:374–396.
- 3-pass read model exposed to the LLM via 9 tools + 1 meta-tool ✅ og_tools.py:185–495:
  `search_skills` (Pass 1) → `peek_skill` (Pass 2: dense ≤30-token summary + per-block token-cost
  manifest, engine.py:445–497) → `load_skill` (Pass 3: selectable blocks, default execution set,
  engine.py:499–580) — plus `skill_dependencies` (transitive `requires` closure w/ cycle detection,
  engine.py:954–1007), `check_skill_assertions` (deterministic precondition eval via
  `core/assertion_eval.py`), `skill_changelog` (delta-load check), `skill_traverse_hints`, `save_skill`,
  `list_skills`, and `use_tools` (lazy tool-group unlock).
- `resolve_node` deliberately does **not** auto-expand `requires` edges; dependencies are listed by name
  in a footer for on-demand loading — engine.py:505–509, 567–579.
- Usage tracking: every `load_skill` writes `~/.hachi/brain/skill_usage.json` (note: hardcoded
  `Path.home()/".hachi"`, bypassing platformdirs — engine.py:255); stale-skill + analytics reports —
  engine.py:1106–1234.
- Lint: dense-token budget (30 tok est.), dangling index, missing keywords/dense/content — engine.py:104–208.
- RBAC: node `scope` filtered at query time by engine role; `with_role()` makes shared read-only views for
  sub-agents — engine.py:258–293; tests `test_og_rbac.py`, `test_og_scope_rbac.py`.

### 6.5 Injection into context

- `brain.og` → layered prompt (identity → warnings → rules → steps) — workspace.py:135–178; shipped brain
  is 7 nodes / ~202 lines ✅ default_skills/brain.og.
- Skill *count* and the 3-pass protocol instructions go into the stable system prompt; skill *content*
  enters only через tool results (per-turn, model-driven) — prompt_composer.py:53–64.
- The execution loop intercepts `load_skill` to (a) auto-unlock that skill's REST tool group,
  (b) record usage, (c) signal skill-switch compaction — loop.py:519–530.

### 6.6 Shipped-content reality check

`brain.og` is fully spec-compliant (::meta/::index/scoped nodes) ✅. But e.g. `weather.og` has **no
::index, no ::meta** — a single node with inline keywords ✅ default_skills/general/weather.og:1–23.
Pass-1 routing for such files rides on node keywords only. Spec-vs-shipped-content drift is measurable
(REVERIFY.md found 17/22 skills affected by the plural-blocks bug before the parser fix Ⓐ).

### 6.7 Spec-vs-code deltas already verified (Phase 2 fodder)

| Spec claim (docs/reference/objectgraph-spec.md) | Code reality |
|---|---|
| §5.1 engine auto-traverses `->[:requires]` during resolve | Explicitly removed; footer-only — engine.py:505–509 ✅ |
| §5.3 confidence <0.3 auto-excluded from results | `confidence` parsed but never filters/ranks search — engine.py:348–396 ✅ |
| §5.4 session `visited` skip ("skip-if-known") | No visited-set anywhere in engine.py ✅ |
| "O(1) routing" | Exact-match path only; fuzzy scan is linear — engine.py:369–372 ✅ |

---

## 7. Memory & context selection — as actually implemented

Three layers plus composition, all ✅ read directly:

1. **Active context** — `MemoryManager` (core/memory.py): sliding window at 30 messages
   (orchestrator.py:1243) with tool-pair-safe boundary search (memory.py:690–751); skill-switch
   compaction deferred to turn boundaries (memory.py:270–339); lossless clearing of >600-char tool
   results once history exceeds ~12k est. tokens (memory.py:39–45, 415–453); LLM-generated structured
   checkpoint replaces dropped middle segments (memory.py:801–876). Narrow `ConversationMemory`
   Protocol + frozen `IterationState` seam to the loop (core/conversation_memory.py:9–39).
2. **SessionStore** — SQLite transcripts, titles, cost per session (core/session_store.py; bound at
   orchestrator.py:1264, logged at 863–897); resume replays last ≤40 user/assistant turns
   (orchestrator.py:444–474).
3. **MemoryVault** — ChromaDB persistent client with **5 collections**: `core_memory`, `user_profile`
   (bounded, max 25 entries — memory_vault.py:28), `agent_profile`, `delegation_log`,
   `memory_quarantine`; every write passes a prompt-injection `MemoryGuard` scan, blocked content is
   quarantined with threat metadata — memory_vault.py:74–150. Backend seam `memory_provider.py` allows
   `in_memory` fallback without ChromaDB (orchestrator.py:1266–1279).

**Per-turn composition** (orchestrator.py:794–908 ✅): refresh frozen vault snapshot (user profile +
agent persona + top-8 "important context" facts — :641–680) → consume async-prefetched recall keyed by
turn_id, else sync top-5 semantic search (:824–829) → build immutable `TurnContext` whose
`PromptComposer.compose()` splits prompt into a **cacheable stable prefix** (brain+skills+permissions+
profiles, carries the Anthropic cache breakpoint) and a **dynamic tail** (time header + recall) —
prompt_composer.py:98–134, turn_context.py:106–115, consumed at loop.py:289–300, 444–456.

**Post-turn sync**: `complete_task` → `sync_turn` enqueues LLM fact-extraction (3 buckets:
user/workspace/agent-behavioral facts, haiku-class model) — memory.py:105–235. Jobs run on an
`InMemoryJobQueue` (orchestrator.py:1056) **drained synchronously at the start of the next `chat()`**
(orchestrator.py:686–691, 819) — i.e. "background" work actually executes inline before the next turn;
a daemon-thread fallback exists when no queue is wired (memory.py:150–164).

**Sub-agents**: `delegate_task` spawns an isolated loop (haiku-class default, 10-iteration/120 s caps Ⓐ
core/sub_agent.py), role-scoped `SkillEngine` view, reports persisted to `delegation_log`
(orchestrator.py:1411–1427 ✅).

---

## 8. The benchmark behind the headline number ✅▶

`tests/test_og_benchmark.py` (the same engine code drives `hachi skill benchmark`, CI-gated ≥0.80):

- **Observed this session** ▶: `nodes=42 | baseline=8991 tok | 3-pass=253 tok (p1=39, p2=86, p3=128) | savings=97.2%`.
- **What it measures**: baseline = `resolve_node(blocks=["all"])` of *all 42 shipped nodes* concatenated;
  3-pass = search-results JSON + peek of top-5 + **full load of exactly one node** — test_og_benchmark.py:43–60.
- **Measurement caveats (observed, not judged — Phase 2 will weigh them)**: token figure is `len(chars)/4`
  (engine.py:73–87), not a real tokenizer; the query is the engine's *first indexed keyword*, not a
  realistic query distribution (test_og_benchmark.py:48–51); retrieval *quality* is unmeasured (the
  benchmark assumes candidate #1 is the right node); per-turn tool-call message overhead and the
  3 extra LLM round-trips are not counted; no comparison arm vs. markdown-with-index, embeddings/RAG,
  or hybrid.
- docs/reference/benchmark.md cites external arXiv research on selective loading — ⚠️ UNVERIFIED; citations will be
  checked in Phase 2/3 (one known-circulating "95.3%" OG paper claim was previously found refuted and must
  not be relied on).

---

## 9. Verified discrepancies: documentation vs. code

| # | Claim | Reality | Evidence |
|---|---|---|---|
| D1 | Brief/positioning: OG memory = `memory.og`, `workflows.og`, `projects.og` | None exist; memory is Chroma+SQLite | ▶ grep zero matches |
| D2 | CLAUDE.md: "frontend/ SvelteKit app" | TanStack Start + React 19 + Vite (`tanstack_start_ts`) | Ⓐ frontend/package.json |
| D3 | CLAUDE.md: "CI enforces frontend-contract job" | Job commented out in ci.yml:100–143 | Ⓐ |
| D4 | "O(1) retrieval" (engine.py:17, spec) | Linear fuzzy substring scan in same function | ✅ engine.py:369–372 |
| D5 | Spec §5.1/5.3/5.4 features (auto-traversal, confidence filtering, visited-skip) | Not implemented | ✅ §6.7 above |
| D6 | Docstrings: skills at `~/.hachi/skills/` | platformdirs data dir (legacy import shim) | ✅ paths.py:73–81 |
| D7 | engine.py:14–17 markets vs "OpenClaw" inside source docstring | Competitive claim embedded in code, unbenchmarked vs. that product | ✅ |
| D8 | CLAUDE.md memory description ("compacted per turn") | Compaction is *deferred/conditional*, plus inline-drained queue | ✅ §7 |

---

## 10. Open questions carried into Phase 1+

1. Quality of `core/loop.py` behavior under real multi-tool turns — no E2E test exercises it Ⓐ (§5).
2. Whether the in-memory job queue's synchronous drain-at-turn-start creates latency/durability issues (✅ §7).
3. WhatsApp channel & community-packs maturity (Ⓐ flagged as thin).
4. Global node-name collision behavior with user-authored skills (✅ engine.py:323–324).
5. Verification of benchmark.md's external citations and construction of a fair OG-vs-markdown-vs-RAG
   benchmark (⚠️ UNVERIFIED → Phase 2 design).
6. Frontend ↔ gateway contract drift risk while the CI job is disabled (Ⓐ D3).
