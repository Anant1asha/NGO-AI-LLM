# DECISIONS.md

Engineering decision log for the 12-issue hardening pass on `feat/phase4-platform-impl`.
Each entry: **Found** (root cause / current behaviour) → **Decided/Changed** (approach + files) →
**Why** (rationale). Significant architectural decisions are flagged **[ADR]**.

Methodology: 8 parallel read-only audits (one per issue cluster) established root causes, then 8
file-disjoint implementation lanes applied fixes with explicit cross-file contracts. Audits and
fixes were delegated to Sonnet 4.6 subagents; orchestration, decisions, and verification by Opus.
"Minimal-safe" means: smallest correct fix now, with deeper refactors captured as `# TODO(issueN)`.

---

## ⚠️ Operational findings (require human action — NOT code-fixable)

1. **Live secrets in `.env`.** `D:\OpenGigantic\hachi\.env` holds real, plaintext production
   credentials (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `GOOGLE_CLIENT_SECRET`, `NOTION_API_KEY`, Discord/Slack tokens, STT/TTS keys). The file is
   gitignored (verified) so it is not in git history, but these keys should be **rotated** because
   they have been stored in cleartext. We did not modify `.env` (it is the user's live secret store).

2. **Stale `.env` comment.** The header comment in `.env` claims "the app does NOT auto-load this
   file." That is now false — `cli/main.py::_load_dotenv_into_environ()` loads it at import time.
   Documented in `docs/guides/configuration.md`; the user should update/remove the misleading comment.

---

## Issue 1 — "Unknown session id" on page refresh

**Found.** The session id lives in two unbridged stores. `POST /sessions` registers a UUID in the
in-memory `GatewayControlPlane._connections` dict; `SessionStore.start_session()` separately writes
a (different-format) id to SQLite. On gateway restart `_connections` is wiped. Client-side,
`_liveSessionId` is a **module-level variable** (`frontend/.../chat.ts:27`) with no persistence — it
resets to `null` on browser refresh, and the zustand store does not persist `sessions`. The visible
error originates in `control_plane.py`: `session_state()` (~547) and `send_message()` (~341) gate on
`_connections` only and raise `GatewayProtocolError("Unknown session_id")` for a session from a prior
process. The events endpoint already tolerates dead sessions (falls back to SQLite history); only
`session_state`/`send_message` do not.

**Decided/Changed.**
- Backend (`control_plane.py`): `session_state()` falls back to SQLite-backed metadata instead of
  raising for a known-but-dead session. `send_message()` raises a **typed, recoverable** signal
  (`session_expired`) instead of a generic "Unknown session_id". `# TODO(issue1)` left for full
  server-side session re-boot-on-resume.
- Frontend (`chat.ts`): persist `_liveSessionId` to `sessionStorage` (tab-scoped) and rehydrate on
  load so a same-tab refresh reconnects. On `session_expired` → silently create a new session + show
  a friendly inline notice. On unrecognized/corrupted id → silently reset and create new, **no
  error surfaced**.

**Why.** [ADR] We **distinguish expired (expected) from corrupted (bug)** as the spec requires:
expired is a normal lifecycle event → friendly, non-alarming UX; a missing/garbled id is our bug →
recover silently rather than blame the user. Making `session_state` SQLite-tolerant mirrors the
already-correct events endpoint, so the fix is consistent with existing patterns and low-risk. Full
transparent server resume is deferred because it needs careful re-wiring of the orchestrator boot
path — the minimal fix already removes the user-visible failure.

---

## Issue 2 — Slow/delayed markdown & code-block rendering (FOUC)

**Found.** Not a parser or highlighter problem (the markdown component is a zero-dep synchronous
regex tokenizer; no lazy `import()`, no shiki/prism). Root cause is **(c) streaming buffering + (d)
remount**: `conversation.tsx` (~929) renders `<StreamingText>` (raw `white-space:pre-wrap`, zero
markdown) during the stream, then switches to `<Markdown>` only when streaming completes. That
switch **unmounts/remounts** the whole message subtree, so code blocks go from plain text to fully
styled in one repaint — the flash — plus a layout shift (inline spans → block `<pre>`/`<div>`).

**Decided/Changed.** Render `<Markdown text={msg.text} isStreaming={showCursor}/>` **always** (drop the
StreamingText branch for hachi messages). New `isStreaming` prop: keep synchronous per-flush parsing
(cheap; the existing `FLUSH_MIN_INTERVAL_MS=48` throttle bounds cadence and `useMemo(parseBlocks,
[text])` bounds re-parse), but for an **unclosed** fenced code block render the styled `<pre>`
container with un-highlighted text so chrome appears the instant ``` arrives. Stable block keys
across streaming→done = prop change, not remount. `min-height` on the message body prevents the
start/end collapse-expand shift.

**Why.** The original `StreamingText` optimization avoided O(size²) re-renders, but `React.memo` on
`MessageItem` already ensures only the last message re-renders per flush — so the perf win no longer
justifies the FOUC. Parsing during streaming is the correct trade now. Keeping the same component
across the transition is what actually kills the flash (no remount) and the layout shift.

---

## Issue 3 — Voice: speed, accuracy, reliability

**Found.** Latency is dominated by code-fixable issues, not the providers:
- **TTS waits for the full blob** before playback (`speakText` does `await res.blob()`); server
  returns `StreamingResponse(io.BytesIO(full_bytes))` — buffered, not streamed. ~1–2.5 s of silence.
- **STT batches** the full utterance (Whisper has no token streaming) — provider-limited.
- **VAD hangover** `SILENCE_HANGOVER_FRAMES=40` ≈ 667 ms tail on every utterance.
- **`httpx.Client` rebuilt per call** → TLS handshake each time (~100–300 ms).
- **ElevenLabs model hardcoded** `eleven_monolingual_v1` (not the low-latency turbo/flash model).
- **Mic stream + AudioContext rebuilt every utterance** (~150–200 ms + permission churn).

**Decided/Changed.** P1 stream TTS playback via `MediaSource`/`ReadableStream` (blob fallback) + server
streams httpx body where supported. P2 reuse MediaStream/AudioContext across utterances (rebuild only
the MediaRecorder). P3 hangover 40→25 + pre-speech gate (don't upload leading silence). P4 shared
lazy `httpx.Client` + 60 s timeout. P6 `config.voice.elevenlabs_model` (default `eleven_turbo_v2_5`)
+ configurable stt/tts model & base_url. Plus voice cost tracking (see Issue 9).

**Why.** [ADR] **Fix what's in our control; document what isn't.** Streaming TTS playback is the single
biggest perceived-latency win and is fully ours. STT streaming is genuinely provider-limited (Whisper
is batch-only) — documented in `docs/` with a mitigation path (Groq `whisper-large-v3-turbo` via
`stt_base_url`) rather than faked. VAD stays an energy detector (a WASM VAD like Silero is noted as a
follow-up) because retuning the threshold/hangover is low-risk and recovers most of the latency now.

---

## Issue 4 — MCP servers not appearing after registration

**Found.** Two compounding gaps. (1) Boot (`orchestrator._configure_mcp_servers`, ~1475) reads MCP
servers **only from `.og` `role=mcp` nodes**, never from the `[mcp_servers]` TOML that the
registration API writes — so an API-registered server is lost on restart and absent if no session is
live to hot-load it. (2) `MCPManager.get_inventory()` never populates an error field, so the UI has
no per-server `error`/`loading` state (only binary ready/stopped).

**Decided/Changed.** `_configure_mcp_servers` also loads `[mcp_servers]` TOML entries
(`MCPServerConfig.from_toml_entry`) at boot, de-duped against `.og`-defined servers. `get_inventory`
gains `err` (from a new `_last_error` on the connection) and a transient `loading`/`starting` status.
Frontend renders connected/loading/error chips and shows the error text.

**Why.** Registration already persisted to TOML correctly; the bug was purely that the boot path never
read it back — so the smallest correct fix is to make boot authoritative over both sources. Surfacing
`err` closes the "registered but silently dead" UX hole the spec calls out.

---

## Issue 5 — Tavily ignored; everything routes to Playwright

**Found.** `ProviderRegistry.from_config()` only instantiates `TavilySearchProvider` when
`config.search.provider == "tavily"` (default `None`). Storing the Tavily API key via the
integrations UI writes the key to the vault but **never sets `search.provider`** — so the provider is
never registered, `web_search`/`extract_url` tools are never added, and the LLM only ever has
`browse_web` (Playwright). There is no "routing" between them; the LLM simply uses the only web tool
present.

**Decided/Changed.** (1) `registry.from_config()` registers Tavily when `provider=="tavily"` **OR** a
Tavily key is resolvable (vault `tavily_api_key` or env `TAVILY_API_KEY`) — **key-presence is
sufficient**. (2) The credential-submit route also persists `[search] provider="tavily"` so it
survives restarts. (3) `_register_search_if_available` logs a clear warning when no provider is found
and `browse_web`/Playwright becomes the fallback; a `fallback_active` status field drives a UI notice.

**Why.** [ADR] **Configured-credential implies intent.** A user who pastes a Tavily key obviously wants
Tavily; requiring a separate hidden `provider` toggle was the trap. We make the key the activation
signal and make the Playwright fallback **explicit and visible** (log + UI) rather than silent, as the
spec demands.

---

## Issue 6 — `.env` credentials ignored; "Needs setup" shown wrongly

**Found (6a).** OAuth2 connectors compute "configured" via `is_configured()` which reads **only** the
canonical `HACHI_OAUTH_<NAME>_CLIENT_ID` env name. A user's `.env` with the bare `GOOGLE_CLIENT_ID`
(what the legacy Google path uses) therefore reads as unconfigured. apikey connectors (Telegram/
WhatsApp/Tavily) already check vault-or-env and work. `.env` *is* loaded (via
`cli/main.py::_load_dotenv_into_environ`), contradicting the stale `.env` comment.

**Decided/Changed.**
- **6a:** connector resolution checks the canonical name **and** documented legacy aliases (e.g.
  `GOOGLE_CLIENT_ID`/`_SECRET`); `connector_status()` now reports `source: "vault"|"env"|null` so the
  UI can show "(from environment)". Explicit env→connector→state mapping documented in
  `connector_registry.py`.
- **6b:** the existing generic `CredentialDialog` (masked fields) gains a per-integration **Test
  connection** button (`POST /integrations/{id}/credentials/test`), a "currently configured" masked
  hint, and an env-sourced tag. Secrets are never put in localStorage (verified: only UI-dismissal
  flags are).
- **6c:** CLI commands `hachi set K=v [K2=v2 ...]`, `hachi get K` (masked), `hachi list-keys`
  (status: vault/env/not-set), `hachi unset K`, validated against a `KNOWN_CREDENTIAL_KEYS` schema
  (warn on unknown). Backed by the existing `CredentialVault`. *(wave 2 — in `cli/main.py`)*
- **6d:** repo-wide scan found **zero `TOKOBOROS_` in tracked code/docs/CI/Docker**; the only
  occurrences are in the user's local `.env` (`STT_API_KEY`, `TTS_API_KEY`, 5× `SMTP_*`). So the
  rename is a no-op in code; we add a **startup back-compat shim** that copies any set `TOKOBOROS_*`
  to its `HACHI_*` equivalent (if unset) and logs a deprecation warning. *(wave 2)*

**Why.** [ADR] **6d shim despite the "no migration shims" memory.** A prior decision ripped out
back-compat shims and resolved never to reintroduce them. The current explicit instruction overrides
that, and this shim is narrow (env-var only, deprecation-warned, no persistent state) and directly
serves the user's own working `.env`. Tension noted here for reversibility. The alias approach for 6a
is preferred over forcing users to rename env vars because it makes the *common* `.env` (bare provider
names) "just work" while keeping the canonical `HACHI_OAUTH_*` names authoritative.

---

## Issue 7 — `settings.toml` validation & authority

**Found.** `settings.toml` **is** loaded and respected (4-layer merge in `config_loader.py`;
`permissions.tier` is a clean behaviour-controlling key for a test). But every model uses
`extra="ignore"`, so **unknown keys are silently dropped**; malformed TOML logs a warning and falls
back to defaults with **no abort**; there is **no file-permission check**; `settings.toml` is **not in
`.gitignore`** and there is **no `settings.example.toml`**; the `provider.headers` dict could harbor a
literal `Authorization` secret.

**Decided/Changed.** `config_loader` gains load-time validation: warn on unknown top-level/section keys
(diffed against `ResolvedConfig`), surface malformed primary-config clearly, and a **strict mode**
(`HACHI_CONFIG_STRICT=1`) that raises. A **world-writable check** (`mode & 0o002`) warns (aborts under
strict) on POSIX, best-effort on Windows. `settings.toml` + `**/.hachi/settings.toml` added to
`.gitignore`; new `settings.example.toml` documents every key (type/default/effect). Full key
reference in `docs/guides/configuration.md`.

**Why.** [ADR] **Validate loudly, fail safe by default.** Hard-aborting every existing install on an
unknown key would be hostile to current users, so the default is warn-and-continue with an opt-in
strict gate for CI/production. The agent already cannot write `permissions.tier` or credential keys
(blocked in `set_agent_config`), so "read-only authority" is enforced at the tool layer; the
world-writable check defends the remaining OS-level vector the spec names.

---

## Issue 8 — `.og` security model, governance, versioning

**Found (8a/8b).** `.og` files are parsed by `og_engine` with a 3-pass (index→dense→full) model;
malformed/missing files are handled gracefully (skipped + logged, sandbox fallback). The agent can
write `.og` via `save_skill`/`add_mcp_server` but only into the skills dir, never `~/.hachi/`
(blocked). **Crucially: permissions are engine-enforced** — `PermissionGate.check_command/check_path`
block actions *before* execution; only an advisory tier/folder **summary** is injected into the
prompt, **not** the full blocked-paths/commands policy. So the agent cannot read and "reason around"
the real policy. **No secrets found in any `.og` file.** Gaps: `upsert_skill`'s write is **non-atomic**,
and there is **no content version history** (only an in-file `::changelog` + semver).

**Decided/Changed.**
- **8b model:** documented tiered trust in `docs/reference/og-security.md` — **Tier 1** engine-enforced,
  never-agent-writable (`device-permissions.og`, `brain.og`); **Tier 2** advisory bundled skills;
  **Tier 3** agent-writable (`learned/*.og`, `mcp-*.og`, guard-scanned + linted on write).
  Recommendation: engine should refuse `upsert_skill` targeting core/system names.
- **8a/8b fix:** `upsert_skill` write made **atomic** (temp + `os.replace`).
- **8c versioning:** new `core/og_history.py` — **append-only** `<skills_dir>/.og-history/<name>.jsonl`
  (`{version, utc-timestamp, author: human|agent, summary, sha256, content}`), wired into
  `upsert_skill` (author=`agent`). CLI `hachi og rollback <name> --version N` (wave 2, records
  author=`human`). UI history view (wave 2 / tracked TODO).

**Why.** [ADR] **Permissions stay out of the prompt; history stays append-only and out of agent reach.**
The audit confirmed the engine-enforcement design is sound, so the work is to *formalize and document*
it rather than re-architect. Versioning is a sidecar JSONL (not git, not a rewrite of the `.og`) so it
is trivially append-only and cannot be edited through the agent's tool surface — satisfying "the
versioning system itself cannot be modified by the agent." Atomic write closes a real
corruption-on-crash risk found in the audit.

---

## Issue 9 — Cost tracking accuracy & completeness

**Found.** Only **5 of 16** model/API call sites track cost — the main LLM path is covered, but
**STT, TTS, the session titler, and Tavily are untracked**. The cost model correctly prices
input/output/cache-read/cache-write Anthropic tokens, but has **no voice pricing**. `get_spend`
collapses a multi-model session into a **single** entry (ignores `per_model_snapshot()`), reports
`inT=0` always, and there is **no per-modality** breakdown and **no "last used model"** in the
conversation UI.

**Decided/Changed.** `cost.py` gains `VOICE_PRICING` + `record_voice_usage(modality, model, units)`
feeding the **same daily ledger** (so `/spend/daily` includes voice). `session_titler.generate_title`
accepts a `cost_tracker` and records its usage. `runtime_events` turn/usage event gains `model` (+
token split); the orchestrator populates it. UI: per-model + per-modality + per-session + cumulative
breakdown in the Spend panel; a "via <model>" badge under the latest assistant message. `get_spend`
wired to `per_model_snapshot()` (wave 2 in `cli/main.py`).

**Why.** Voice (especially ElevenLabs) is materially expensive, so untracked voice was the biggest
correctness gap. Routing one capability to Opus and another to Haiku in the same session made the
single-entry breakdown actively misleading — surfacing `per_model_snapshot()` fixes that. The
"last used model" badge is the cheapest way to give users the confidence the spec asks for.

---

## Issue 10 — Memory audit & quality

**Found.** **Write:** every clean turn triggers LLM fact-extraction with only a 30-char gate (noise
risk); dedup is SHA-256-exact only (paraphrases proliferate), and a bare-fallback in
`memory_tools.py:137` bypasses the smart-consolidation dedup entirely. **Read:** hybrid — user/agent
profiles are **bulk-injected** every session (bounded at 25 entries each, acceptable), workspace
memory is **semantically queried per turn against real user input (good)**, but session-start uses a
**biased fixed query `"important context"`**. **Quality:** `_query_collection` fetches distances but
**never applies a similarity threshold** — top-k is returned regardless of relevance; `core_memory`
and `delegation_log` are **unbounded**.

**Decided/Changed.** Add a configurable **similarity threshold** in `_query_collection` (read distances,
drop low-similarity hits; conservative default). Add **`get_recent_facts()`** and replace the biased
`"important context"` probe with it (orchestrator lane). **Remove the dedup-bypass fallback**
(`memory_tools.py:137`) — log+skip on consolidation failure. Add a **write-quality filter** for trivial
extracted facts. Add a **soft cap + prune** for `core_memory`. Architecture written up in
`docs/guides/memory.md`.

**Why.** [ADR] **A relevance threshold is the highest-leverage fix** — injecting 5 unrelated facts every
turn both wastes context and degrades answers; returning *fewer, relevant* memories beats *k, always*.
The default threshold is deliberately conservative (favor recall) so we don't silently starve good
recalls; it's tunable. Replacing the fixed probe removes a systematic bias that surfaced whatever
happened to match the literal words "important context."

---

## Issue 11 — Model routing options all work

**Found.** Concrete model descriptors (opus-4/-4-8, sonnet-4, haiku-4/-4-5, gpt-4o/-mini) and the
real capability slots (reasoning, coding, summarization, title_generation, compaction, long_context,
vision) all resolve correctly. But **5 capability slots are stubs with no router impl** —
`embeddings`, `speech_to_text`, `text_to_speech`, `web_search`, `realtime` — and there is **no
"last used model" indicator** in the conversation UI.

**Decided/Changed.** Hide/disable the 5 stub capability slots in the routing UI (label "not
configurable yet") so users can't select a no-op route. Add the "last used model" badge (shared with
Issue 9 via the new `model` SSE field).

**Why.** Showing routing controls that silently fall through to the default model is a trust bug —
better to disable them honestly than to imply configurability that doesn't exist. The badge gives the
positive confirmation (which model actually answered) the spec wants.

---

## Issue 12 — Ghost / unnamed sessions

**Found.** `on_connect` calls `SessionStore.start_session()` **eagerly**, persisting an empty SQLite
row before any message exists — so failed boots, OpenAI-compat facade sessions, and
created-but-never-used sessions all leave "Unnamed" rows. `get_recent_sessions()` returns those
0-message rows. Deletion is actually **correct** (it removes from SQLite); sessions "reappear" only
because a new empty row is created on the next send before the first message commits.

**Decided/Changed.** First implemented as **lazy** row creation (defer the INSERT to the first
`log_message`). The full regression suite then showed lazy persistence broke real guarantees other
code/tests rely on: foreign-key rejection of unknown sessions, synchronous-commit visibility, and
per-session cost recording. **Revised to keep `start_session` eager** (row inserted + committed
immediately, FK integrity intact) and prevent ghosts at the *visibility* and *cleanup* layers instead:
`get_recent_sessions` hides sessions with no real signal (no messages AND no cost AND no title AND no
turns); `delete_empty_sessions()` (same predicate) + `POST /sessions/cleanup-empty` route + a "Clean up
empty sessions" UI action remove them on demand; the frontend also guards against rendering obviously
empty unnamed sessions and no longer shows the "no message history found" placeholder. The automatic
startup ghost-purge was **removed** — silently deleting message-less rows on every DB open is dangerous
(it deleted a legacy row a migration test still expected).

**Why.** [ADR] **Don't trade an integrity guarantee for a cosmetic one.** Lazy persistence removed FK
rejection (a safety property) and synchronous commit (relied on by cost recording and same-connection
reads). Hiding + explicit cleanup achieves the user-visible goal (no ghost sessions in the UI; one-click
cleanup) without weakening the store. The visibility predicate keys on "real signal" so a cost-bearing
or titled session is never mistaken for a ghost.

---

## Cross-cutting architectural decisions [ADR]

- **File-disjoint parallelism with contracts.** The backend hotspots (`orchestrator.py`,
  `fastapi_app.py`, `control_plane.py`) are touched by many issues, so they were assigned to a single
  owning lane; other lanes call newly-added functions by agreed signature (`delete_empty_sessions`,
  `record_voice_usage`, `get_recent_facts`, the `model` event field, `generate_title(cost_tracker=)`).
  This guarantees zero edit conflicts while preserving parallelism.
- **Cost discipline.** Audits and implementation ran on Sonnet 4.6 (not Opus) per the cost mandate;
  Opus was reserved for orchestration, decisions, and verification.
- **Verification gate.** No issue is "done" until: `ruff check`, `mypy src`, `pytest -q`, the frontend
  `vitest` + `vite build`, and OpenAPI `check:api` pass (any backend route change requires
  `gateway-openapi` re-export + `npm run generate:api`). Status tracked in the wave-2 reconciliation
  section below.

---

## Implementation reconciliation (what actually landed)

Delegated to 8 parallel Sonnet lanes (wave 1) + 1 CLI lane (wave 2), with cross-cutting glue and
verification by Opus. Per-lane landed changes and their own test counts:

| Lane | Key files | Tests |
|---|---|---|
| Conversation UI | `Markdown.tsx`, `conversation.tsx`, `chat.ts`, `store.ts` | 24 (Markdown) |
| Integrations/Spend UI | `integrations.tsx/.ts`, `SpendSection.tsx`, `ProviderSettings.tsx`, `types.ts` | 24 |
| Voice | `voice.py`, `speech.py`, `voice_endpoints.py`, `ContinuousVoice.tsx`, `voice.ts` | 9 + 4 |
| Memory | `memory_vault.py`, `memory.py`, `memory_tools.py` | 20 |
| Governance | `config_loader.py`, `og_engine/engine.py`, `og_history.py` (new), docs, `settings.example.toml`, `.gitignore` | 16 |
| Creds/env | `connector_registry.py`, `oauth_flow.py` | 17 |
| Gateway core | `orchestrator.py`, `fastapi_app.py`, `control_plane.py` | 16 |
| Supporting backend | `session_store.py`, `registry.py`, `mcp_client.py`, `settings.py`, `cost.py`, `session_titler.py`, `runtime_events.py` | 36 |
| CLI (wave 2) | `cli/main.py` | 32 |

**Cross-cutting glue done by Opus:**
- Memory config keys wired end-to-end: `MemorySettings.recall_distance_max` / `core_memory_max_entries`
  (`settings.py`) → `ChromaMemoryProvider.initialize(...)` (`memory_provider.py`) → vault construction
  (`orchestrator.py`). Without this the keys would be "read by nothing" (the anti-pattern the
  `LimitsSettings` docstring explicitly warns about).
- **Seam GAP-1** (Issue 5): `fallback_active` added to the `GET /integrations` Tavily entry (the UI reads
  it there; the lane had only put it on the POST-credentials response). `fastapi_app.py::get_integrations`.
- **Seam GAP-4** (Issue 6b): new `POST /integrations/{id}/credentials/test` route — bounded live probe
  (real ping for Tavily/Telegram, "stored; no live test" for others), never echoes secrets, never raises.
- **Seam GAP-3** (Issue 9): `get_spend` (`cli/main.py`) now emits the real per-model breakdown from
  `CostTracker.per_model_snapshot()` plus `modalities`/`session`/`cumulative_usd` (C-SPEND), keeping the
  legacy keys for the work tab. *Known limit:* per-session **voice** modality isn't split out — voice cost
  is recorded into the daily ledger total, not a per-session modality bucket. `TODO(issue9)`: modality-tagged ledger.
- **Seam GAP-2** (Issue 1): verified end-to-end — the gateway's `SessionExpiredError` → HTTP 410 with
  `code="session_expired"`, and `client.ts::parseError` lifts `body.code` into `ApiError.code`, which
  `chat.ts` matches. No change needed.
- `docs/guides/memory.md` authored; `settings.example.toml` extended with the new memory + `elevenlabs_model` keys.

**Cross-lane contract alignment (verified):** `session_expired` code (gateway↔chat.ts) ✓; `payload.model`
on `usage.updated` + `session.chat.completed` (A8 emits field, A7 populates, A1 consumes) ✓;
`POST /sessions/cleanup-empty` (A7 route ↔ A1 caller) ✓; `get_recent_facts` (A4 ↔ A7) ✓;
`record_voice_usage` (A8 ↔ A3) ✓; `delete_empty_sessions` (A8 ↔ A7) ✓; `source` field (A6 ↔ UI) ✓.

## Verification results

> **Bottom line:** `pytest -q` = **3359 passed / 0 failed / 17 skipped**; frontend `tsc` + 56 vitest +
> `vite build` green; `ruff check src tests` clean; the `mypy` strict-gate test passes; OpenAPI contract
> regenerated and re-typechecked clean.

- **Frontend:** `tsc --noEmit` clean; **56 vitest tests pass**; `vite build` succeeds (199 modules).
- **OpenAPI contract:** schema re-exported (`hachi gateway-openapi`), `schema.d.ts` regenerated
  (`generate:api`, +128 lines for the new routes/shapes), frontend **re-typechecks clean against the new
  schema**. (The regenerated `schema.d.ts` is an intentional, committable change — `check:api` "diff" is expected.)
- **Backend lint:** `ruff check src tests` — **all checks pass**.
- **Backend types:** `mypy src` baseline is a large pre-existing style-debt set (≈450, `no-untyped-def` /
  `type-arg` / `no-any-return`; mypy is `continue-on-error` on main for this reason). This session
  introduced **7 new errors** (in `og_history.py`, `fastapi_app.py`, `config_loader.py`, `cost.py`,
  `voice_endpoints.py`) — **all 7 fixed**, so the session is net-zero (slightly negative) on the mypy count.
- **Backend tests:** all **144** new-suite tests across the 8+1 lanes pass together (2 POSIX-only skips).
  Fixed one test-isolation bug in `test_memory_fixes.py` (the consolidation-failure tests patched
  `AnthropicClient` during job *capture* but executed the captured job *outside* the patch, so a
  shared client from an earlier test leaked in — now they execute under an active patch).
- **Full-suite regression triage (the important part):** the first full `pytest -q` run surfaced
  **17 failures** — and triage showed these were **real regressions**, not pre-existing env noise. The
  parallel lanes each passed their own isolated tests but broke pre-existing tests they couldn't see,
  in four clusters: (1) the `session_store` **lazy-row** change broke FK-integrity / synchronous-commit /
  session-cost / title-migration tests; (2) a speculative `claude-haiku-4-5` price override shadowed the
  family prefix the cost tests encode; (3) the OAuth **alias** + the local `.env` made three
  "not configured" tests non-hermetic (they cleared only the canonical env var, not the legacy alias);
  (4) a new unused `type: ignore` (`fastapi_app.py:840`) failed the strict **mypy-gate** test. **All four
  root-caused and fixed** — session_store reverted to eager + visibility/cleanup (see Issue 12);
  haiku-4-5 override removed (prefix-match to `claude-haiku-4` → `(1.0, 5.0)`); the three OAuth tests made
  hermetic by also clearing `GOOGLE_CLIENT_ID`; the gated `type: ignore` removed; and one new
  test rewritten to assert the eager design. Re-run of the 9 affected files + the 9 lane suites is
  **green (150 + 144 pass)**; a final full `pytest -q` was run to confirm the whole suite (~3359 tests)
  is clean.
- **Lesson:** parallel lanes must be regression-tested against the *whole* suite, not just their own new
  tests — isolated green is necessary but not sufficient. The first full run is what caught all 17.
- **Live integration proof:** exporting the OpenAPI schema imports the entire gateway cleanly (all lanes
  integrate), and the run shows the **`TOKOBOROS_*`→`HACHI_*` shim firing** on the real `.env` with the
  expected deprecation warnings (Issue 6d verified live).

## Tracked follow-ups (`TODO`)

- `TODO(issue1)`: full server-side session re-boot-on-resume (current fix makes `session_state` SQLite-tolerant + returns a typed `session_expired`; the frontend then resumes/creates cleanly).
- `TODO(issue9)`: modality-tagged daily ledger for a true per-session voice/text/image cost split.
- `TODO(issue10)`: cosine write-time dedup for paraphrases; bound/TTL `delegation_log`; LRU (not just oldest-first) eviction for `core_memory`.
- `TODO(issue8c)`: gateway route + UI view for `.og` version history (CLI `hachi og history`/`rollback` shipped; the append-only store + engine wiring shipped).
- Voice provider/hardware limits (documented, not code-fixable): Whisper is batch-only (mitigate via Groq `whisper-large-v3-turbo` through `stt_base_url`); OpenAI/ElevenLabs TTS buffer server-side until they expose `synthesize_stream`; energy-RMS VAD is noise-sensitive (a WASM VAD like Silero is the upgrade path).

---

## Live bug-fix round (2026-06-23, post-deploy) — user-reported in the running app

Diagnosed against the live gateway; root causes were deeper than the first pass and several
were **pre-existing latent bugs** the first round's fixes merely exposed. All verified live
(gateway booted, real session turns).

**Process gotcha (the meta-cause of "still not working"):** the running gateway is a long-lived
process — uncommitted on-disk fixes and `settings.toml` edits do **not** reach it until restart.
Confirmed via process start-time vs edit-time. Restarted the gateway after each backend change.
The Vite dev server (HMR) does pick up frontend edits live, but it was talking to a stale gateway.

### MCP "internet-search not reachable" (web search) — THREE stacked bugs
- **`[mcp_servers]` silently dropped by the config loader.** `workspace.load_config()` returns
  `ResolvedConfig.model_dump()`, and `ResolvedConfig` had **no `mcp_servers` field** (`extra="ignore"`),
  so every TOML-defined MCP server was stripped before boot ever saw it — TOML MCP servers could
  *never* have worked. Fix: added `mcp_servers: dict[str, dict[str, Any]]` to `ResolvedConfig`
  (`settings.py`). (Also removed A5's false "unknown key: mcp_servers" validator warning.)
- **HTTP transport sent the wrong `Accept` header → `406 Not Acceptable`.** MCP streamable-HTTP
  requires `Accept: application/json, text/event-stream`; `HttpTransport.start()` sent only
  `Content-Type`. The response also comes back as SSE (`data: {…}`) which the parser couldn't read,
  and the spec needs the `Mcp-Session-Id` echoed. Fixed all three in `mcp_client.py::HttpTransport`.
- **Permission gate blocked user-registered TOML servers.** The gate reads its tier from
  `device-permissions.og` (which was `guided`), *not* `settings.toml` (`unrestricted`) — a known
  split. Under `guided`, `is_mcp_server_allowed(name, trusted=False)` denied all of them. Fix:
  TOML `[mcp_servers]` are user-authored config → call the gate with `trusted=True` (unlike
  community-pack `.og` servers). `orchestrator._configure_mcp_servers`.
- **Result (verified):** all 4 servers boot `ready` — `internet-search` exposes `tavily_search`
  + 4 more (17 tools total). `err` now surfaced to the UI (`MCPServerSnapshot.err`).
- *Note:* the user has 3 identical Tavily MCP entries (`tavily`, `tavily-mcp`, `internet-search`) →
  15 duplicate tools; recommend keeping one. The native `[search] provider="tavily"` path also had a
  vault-key-name mismatch (`apikey.tavily.tavily_api_key` vs `tavily_api_key`) — fixed in `registry.py`.

### Model selection (gpt-4o-mini → spend showed haiku) — FOUR stacked bugs
- **The chat baked its model from `provider.model` (haiku), ignoring `routing.default_model`.**
  Fixed: when the router is active, `model_name = routing.default_model` so the session metadata +
  `/spend` reflect what actually runs (`orchestrator.py`). Plus a loud warning on fallback instead of
  silent haiku.
- **`set_routing` didn't reload live agents** → routing UI changes did nothing until restart. Added
  `self._reload_agents()` (`cli/main.py`).
- **Factory rejected provider kind `openai`** (`Unsupported provider kind: openai`) — the bundled
  gpt-4o/gpt-4o-mini descriptors use kind `openai`; the factory only knew `openai-compatible`. Added
  `openai` (maps to the OpenAI base URL) in `llm.py::create_llm_client`.
- **The configured provider's key never reached gpt-4o-mini.** `OpenAICompatProvider.models()`
  advertised descriptors with `provider="openai"`, but the provider's registry name is
  `"openai-compatible"`, so the router couldn't match them to *this* provider (which holds the key)
  and built a keyless generic client. Fixed: re-home advertised descriptors to `self.name`
  (`openai_compat_provider.py`). Also fixed a `gpt-4o-min` typo in the user's `settings.toml`.
- **Result (verified):** a live turn now runs on `gpt-4o-mini` (was haiku).

### Frontend: retry / cross-section leak / title / session list
- **Retry returned the *previous/unrelated* response + duplicated the user message.** `handleRetry`
  called `startTask` (which appends a fresh you/hachi pair), and — the real correctness bug — SSE
  events were applied to the global store with **no session scoping**, so a stale stream (or a
  query from another screen) rendered into the current chat (the "Aditya Dhanraj" leak). Fixes:
  new `store.retryLastMessage()` that resets the failed bubble in place (no duplicate); and a
  `_streamSessionId`/`session_id` guard at the top of `handleSseMessage` + `_cursor` reset on session
  change + single-stream abort (`chat.ts`). This is the highest-impact correctness fix of the round.
- **Title not instant** — there is no backend title event at all; the title only refreshed via
  `loadSessions` on mount. Added `loadSessions()` (immediate + delayed) on `session.chat.completed`.
- **Session list flickered between visible and empty** — `loadSessions` wiped the list to `[]` on any
  transient error, filtered out the active 0-message session, and never marked the live session
  active. Fixed all three (`chat.ts` + `conversation.tsx`).

### Verification (this round)
- Live gateway: 4 MCP servers `ready` (17 tools); turn runs on `gpt-4o-mini`; auth preserved across
  restart (persisted token).
- `ruff` clean on all changed files; OpenAPI re-exported + `schema.d.ts` regenerated + frontend
  `tsc` clean + 56 vitest pass; targeted backend suite **462 passed / 0 failed**; full `pytest -q`
  re-run for cross-cutting regressions.

---

## Reassessment P0 sweep (2026-06-24) — closing the idempotency deficit (AUDIT Theme A / P0-3)

The 2026-06-23 `AUDIT.md` was independently re-verified against HEAD `4063e41` (all 4 P0s + key
P1s still open by direct grep; HEAD's "live bug-fix round" was orthogonal to the architectural
backlog). Began executing the 30-day roadmap **trust-first**, starting with the audit's named
"single most corrosive gap": duplicate side effects on retry. One tested change at a time.

**Why this first.** North star is trust; an assistant that *acts on your behalf* must never do so
twice. Three independent auditors flagged the same hole — no idempotency anywhere a side effect
happens. Closed in three layers.

### P0-3a — outbound messaging dedup (`core/idempotency.py` + `tools/messaging_tools.py`)
- **Found:** the 4 `send_*` tools (Slack/Discord/WhatsApp/Telegram) had zero dedup — an LLM retry,
  the 4-worker tool pool, or a turn resume re-sends the identical message.
- **Changed:** new `IdempotencyGuard` (thread-safe, TTL, `begin`/`finish`/`abort`; mirrors the
  `lease_manager` house style but caches+replays the prior **success** result). Wired into all four
  tools. **Scope = one guard per session** (per `register_messaging_tools` call): covers every
  in-session retry path, but never suppresses a genuinely distinct send from another concurrent
  session. Only **successful** sends are deduped — a failed attempt `abort()`s its reservation so a
  real retry still goes through.
- **Gotcha caught by a test:** `IdempotencyGuard.__len__` makes an empty guard *falsy*, so the
  `guard or IdempotencyGuard()` idiom silently discarded an injected guard → fixed to an explicit
  `is None` check (commented so it isn't reintroduced).
- **Tests:** `test_idempotency.py` (11, incl. fake-clock TTL expiry + a 50-thread race proving
  exactly one `begin` wins) + 8 tool-layer dedup tests. Fixed a pre-existing `_telegram_send` mypy
  `no-any-return` while in the file.

### P0-3b — scheduler dedup (`jobs/scheduler.py`)
- **Found:** `Scheduler.add()` minted a fresh `uuid4` every call → a retried `create_schedule`
  produced a duplicate **recurring** job (fires forever).
- **Changed:** a windowed fingerprint scan (`_find_recent_duplicate`, default 60 s) — a retry with
  the same logical identity (name/task/kind/timing/delivery) inside the window returns the existing
  schedule instead of a duplicate. Scans the **live store** (the schedules dict *is* the dedup
  record — no parallel bookkeeping that can drift). Keys on persisted `created_at`, so dedup also
  holds across a restart between the two creates.
- **Tests:** 5 in `test_scheduler.py` (within-window, past-window, distinct-identity, window=0
  disable, and an across-restart case).

### P0-3c — ingress idempotency (`core/session_store.py` + `gateway/fastapi_app.py` + `frontend/chat.ts`)
- **Found:** `POST /sessions/{id}/messages` had no `Idempotency-Key` — a client retry / reconnect /
  double-click re-runs the **whole turn** (double spend + every side effect again).
- **Changed:** durable `idempotency_keys` table in SessionStore (`PRIMARY KEY (session_id, idem_key)`,
  `INSERT OR IGNORE` = first-write-wins, survives restart) + `get/save_idempotent_response`. The
  route reads `Idempotency-Key` (header preferred, `idempotency_key` body field fallback), replays
  the stored response on a hit, and persists **only on success** (`send_message` raises on failure →
  left retryable). Frontend keys each turn on the stable assistant-bubble id (`turn-${hachiMsgId}`);
  `retryLastMessage` already reuses that id, so a retry/double-submit replays server-side with zero
  extra state. `control_plane` untouched (uses injected callbacks, no store handle) — store resolved
  in the route via the existing `ProcessSharedServices` pattern (`_resolve_session_store`, patchable).
- **Tests:** `test_ingress_idempotency.py` (9: 5 durable-store incl. restart + first-write-wins +
  per-session scoping; 4 route incl. same-key-replays-without-rerunning via an `on_chat` call
  counter, distinct-keys, no-key, body-field fallback). OpenAPI re-exported + `schema.d.ts`
  regenerated; frontend `tsc` clean + 56 vitest pass.
- **Honest scope:** outbound + scheduler dedup are in-process/short-window (the realistic automatic
  retry paths); ingress is durable. Concurrent *in-flight* duplicates (same key, truly simultaneous)
  are suppressed for outbound (the guard's pending reservation) but for ingress two simultaneous
  first-time posts could both run before either stores — `INSERT OR IGNORE` still keeps the replay
  consistent. Provider-native idempotency keys (where a provider supports them) remain a future
  upgrade over content-hash dedup.

**Verification:** consolidated workstream run **155 passed / 0 failed**; `ruff` + `mypy` clean on all
changed modules; OpenAPI + frontend contract regenerated and consistent.

### P0-2 — `interaction_log`, the keystone of the eval loop (`session_store.py` + `loop.py` + `orchestrator.py`)
- **Found:** no durable per-interaction record existed — SessionStore persisted only flat `messages`
  rows, and per-turn cost was reconstructed by scanning the last 500 in-memory events (lost on
  restart). No row-level ground truth → no rating, no failure mining, no per-turn audit, no
  output-regression net. The audit's biggest world-class gap (eval maturity) was *unbuildable*
  without this.
- **Changed (three small pieces):**
  1. **Storage** — `interaction_log` table `{id, session_id, turn_id, ts, user_input, agent_output,
     tool_calls(JSON), memory_hits(JSON), model_used, token_cost, tokens, rating, notes}` +
     `log_interaction` / `get_interactions` / `set_interaction_rating`. `session_store.py` is in the
     **strict mypy gate** and stays clean. `rating`/`notes` are NULL until a future `/review`
     surface fills them (the write side, `set_interaction_rating`, already exists).
  2. **Per-turn tool capture** — `ExecutionLoop` now records `last_tool_calls` (names, in call order),
     reset at the top of each `run()` and appended in the sequential pre-pass (thread-safe, before the
     pool dispatch). Exposed as a copy via a property.
  3. **Write site** — extracted `AgentSession._write_interaction_log` (a testable seam) called once
     per turn from `_chat_impl_inner`, mapping in-scope values: recalled facts → `memory_hits`,
     `loop.last_tool_calls`, `self.model_name`, and **per-turn** cost/token deltas (added
     `_last_recorded_tokens` to mirror the existing `_last_recorded_cost_usd`). Best-effort — a
     logging failure never breaks a turn.
- **Tests (14):** 8 store (round-trip, JSON decode, per-session scoping, ordering+limit, rating
  set/preserve/unknown, restart-durability) + 3 loop (batch order, empty-before-run, reset-per-run via
  the `ScriptedLLMClient` harness) + 3 write-site (field mapping, no-op without store, swallows store
  errors). No real `boot_agent` turn harness exists in the suite, so the write site is covered via the
  extracted seam rather than a full boot.
- **Verification:** 57-test P0-2 regression green; `ruff` clean; **zero new mypy errors** (loop.py
  10→10, orchestrator.py 34→34, both pre-existing-advisory and not in the strict gate; session_store
  strict-gated and clean). Deferred to a later increment: the `/review` UI + thumbs endpoint + a
  trajectory-eval suite that *consume* this table (now unblocked).

### P0-1 — wiring the suspend producer (`loop.py` + `orchestrator.py`)
- **Found:** a dead marquee feature. `loop.py` caught `SuspendWorkflow`, ran
  `return "[WORKFLOW SUSPENDED] {reason}"`, and **discarded the structured wait condition**. No
  `RunState(WAITING)` was ever created, so the *entire* consumer subsystem — wake (`POST /runs/{id}/wake`),
  boot-recover (`_boot_recover_runs`), the 30 s timeout sweep, and `GET /runs` — had **zero inputs**
  and was permanently empty. The suspend tool's own docstring *claimed* "the gateway layer persists
  RunState(WAITING) + arms the registry" — that wiring did not exist. Tests asserted only the
  exception contract, so CI stayed green over a feature that did nothing.
- **Changed (the missing connection, both halves now meet):**
  1. `ExecutionLoop` now surfaces the structured suspend via `last_suspend` (the `SuspendWorkflow`
     itself), reset each `run()` and set in the suspend branch — mirroring the `last_tool_calls`
     pattern. The return string is unchanged (no contract break for existing callers).
  2. `AgentSession._persist_suspended_run_if_any(turn_id)` runs right after `loop.run()`: maps
     `wait_kind`→`WaitKind` (unknown → `USER`, the safe default), builds a `WaitCondition`, and
     `RunStateStore().upsert(RunState(status=WAITING, …))` + `get_wait_registry().arm(run_id, wait)`,
     then emits the existing `run.suspended` event. Best-effort (never breaks a turn); no-op on a
     normal turn. `resume_cursor=0` for now — a warm wake resumes the live in-memory session; precise
     cursor + cold-start replay remain the separately-tracked deferred resume work.
- **Tests (5):** 2 loop (`last_suspend` set with the right wait_kind/key on suspend via the
  `ScriptedLLMClient`; None on a normal turn) + 3 producer (`test_suspend_workflow.py`: creates a
  durable WAITING run **and** arms the registry so `resolve(key)` returns the run_id; unknown
  wait_kind → USER; no-op when not suspended). These assert the **durable side effect** the prior
  tests never did. 108-test producer+consumer regression green (`test_durable_store/waits/runtime_*`).
- **Verification:** `ruff` clean; **zero new mypy errors** (loop 10→10, orchestrator 34→34).

### P0-4 — making the Docker self-host recipe actually run (`frontend/` + `Dockerfile` + compose + CI)
- **Found:** `docker compose up` failed on first invocation. (1) `frontend` service built `./frontend`
  with `dockerfile: Dockerfile` — which **did not exist** → immediate build failure. (2) The backend
  runs non-root `USER hachi` (uid 10001) but volumes mounted to `/root/.config/hachi` etc. — paths the
  non-root user **cannot write**. (3) `test_docker_assets.py` only asserted the string `"8787"` was
  present, so CI was falsely green over all of it.
- **Changed:**
  - **frontend image (new):** `frontend/Dockerfile` (multi-stage — `node:22` build → `nginx:1.27`
    serve), `frontend/nginx.conf.template`, `frontend/docker-entrypoint.sh`, `frontend/.dockerignore`.
    nginx serves the built SPA on 5173 and reverse-proxies `/api/` → the gateway, **mirroring the dev
    Vite proxy**: trailing-slash `proxy_pass` strips the `/api` prefix, the bearer token is injected
    server-side (read from the mounted secret by the entrypoint → `envsubst` into the config, so the
    browser never holds it), and `proxy_buffering off` keeps SSE streaming. SPA `try_files` fallback
    for client-side routing.
  - **writable volumes:** switched the four backend volumes from `/root/...` bind mounts to **named
    volumes** targeting `/home/hachi/...` (the platformdirs paths for that user). The Dockerfile now
    pre-creates those XDG dirs `chown`ed to `hachi`, so each named volume **inherits hachi ownership**
    on first init and the non-root user can write. (A host bind mount would be created root-owned and
    re-break writes — hence named volumes, the standard non-root pattern.)
  - **honest tests + CI:** replaced the string-only `test_docker_assets.py` with 10 structural guards
    (frontend Dockerfile exists/builds/serves; volumes target `/home/hachi` not `/root`; named volumes
    declared; Dockerfile pre-creates+chowns the dirs; nginx proxies `/api` with prefix-strip + token +
    SSE; entrypoint reads the secret). Added a `docker-smoke` CI job (`docker compose config` +
    `docker compose build` of **both** images) so a missing/broken Dockerfile can't pass green again.
  - `.gitignore`: ignore `.hachi/` (holds the local gateway-token secret).
- **Verification:** `docker compose config` **valid** (volumes resolve to `/home/hachi`, both contexts
  build); compose + ci YAML parse-validated; 10 structural tests green. A live `docker compose build`
  could **not** be run locally — Docker Desktop's Linux engine went down mid-session — so the live
  build is verified by the new `docker-smoke` CI job (stable Linux Docker), exactly the audit's
  prescribed verification path. Honest gap: the running container has not been hit with a real browser
  request locally; the proxy/token/SSE wiring is asserted structurally + mirrors the proven dev proxy.

### Google Workspace config resolution (2026-06-24, user-reported: "configured in .env but does it work?")
- **Found (proven by reproduction):** `core/oauth.py` captured the OAuth client id/secret as
  **module-level globals at import time** — `GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")`.
  So a value present in `.env` but merged into the environment *after* this module was first imported
  (a different import order, a non-CLI entrypoint, or a `.env` in a directory the loader didn't read)
  was **never seen**: every Google tool failed "Missing GOOGLE_CLIENT_ID" despite being configured.
  Two compounding gaps: (a) `register_google_tools` gated the real-vs-stub decision on bare
  `os.environ`, and (b) `hachi setup` persists keys to `config_dir/.env`, but the startup loader only
  read `cwd/.env` — so a wizard-configured credential was written to disk and never loaded next run.
- **Changed (three layers, so "configure → it works" is reliably true):**
  1. **Lazy resolution** (`oauth.py`): replaced the import-time globals with `_resolve_env()` (read at
     call time: process env first, then `cwd/.env`, then `config_dir/.env`) behind `_google_client_id()`
     / `_google_client_secret()`; updated `_require_google_client_id` + the browser/refresh flows.
  2. **Consistent gate** (`google_tools.py`): `register_google_tools` now uses `_google_client_id()`
     (same resolver), so a credential configured in *any* `.env` location mounts the real hub, not the
     "not configured" stub.
  3. **Root cause** (`cli/main.py`): the startup loader now also merges `config_dir/.env` (where the
     setup wizard writes) into `os.environ` — `cwd/.env` still wins on conflicts. Fixes Google **and**
     every other wizard-configured credential (SMTP/Telegram/…) being silently ignored on the next run.
- **Not changed (by design):** the first-time consent still uses the local-server browser flow
  (`webbrowser.open` + loopback redirect). On a headless gateway the intended path is to run
  `hachi auth google` once (browser, consent, token persisted); the gateway then uses the saved token
  and refreshes silently. A first Google call in a headless context with no saved token still blocks
  ~120 s on the browser flow — noted as a follow-up (a non-interactive guard that returns
  "run `hachi auth google`" instead of hanging).
- **Tests (9):** 4 oauth regression (value set after import is resolved; env beats .env; .env
  fallback; dotenv parsing) + updated 4 patch sites to the resolver + 4 "no-credentials" stub tests
  now force the resolver to None (clearing only `os.environ` no longer suffices in a repo that ships a
  `.env`) + 1 new "mounts the real hub when the id is only in `.env`". 213-test Google/OAuth/credential/
  deployment regression green; `ruff` clean; **zero new mypy errors** (oauth 19→19, cli/main 121→121).

### Connector hardening (2026-06-24, "check if something is left") — Google write-tool idempotency + headless auth
Completeness sweep after the P0/Google commit (`4fc85b2`) surfaced two real residual items (the rest
of the backlog is the roadmapped P1 tier). Both closed:
- **In-turn idempotency for Google writes (Theme A completion).** Ingress idempotency covers full-turn
  *client* retries, and the messaging tools got per-call guards — but an LLM-retry / tool-pool
  re-dispatch *within* a turn could double-send an email or double-create an event. Added an **opt-in**
  guard to `GoogleHTTPClient.post` (`idempotency_key` param; refactored the body into `_post_raw`): a
  duplicate POST with the same key replays the prior JSON response. Per-client (= per-session) guard.
  **Only side-effecting leaf tools pass a key** — `gmail.send_email`, `gmail.reply_thread`,
  `calendar.create_event`, `calendar.create_recurring_event` — keyed on the **logical** identity
  (to/subject/body, thread/body, title/start/end[/RRULE]), NOT the serialized body (MIME boundaries +
  Meet `requestId` are random). Reads / batch / freeBusy pass no key and are never deduped. Failures
  `abort()` (stay retryable). The 4 test `FakeGoogleClient.post` stand-ins were updated to accept (and
  ignore) the kwarg. *Deliberately scoped to outbound/notifying ops; in-account creates (draft, task,
  contact, file upload) are reversible and can adopt the same one-line pattern later.*
- **Headless first-auth fail-fast.** A first Google call in the gateway with no saved token used to
  open a browser + block ~120 s on a dead loopback redirect. The `gateway`/`serve` server now
  `setdefault`s `HACHI_OAUTH_NONINTERACTIVE=1`; `_run_google_browser_flow` checks it and raises a clear
  "run `hachi auth google`" error immediately. `hachi auth google` runs in its own interactive process
  (flag unset) so the real consent still works. Gotcha caught: `test_cli_gateway_command` invokes the
  `gateway` command → sets the flag **process-wide** for the suite, so the existing browser-flow tests
  were made hermetic (`delenv`).
- **Tests (8):** `test_google_idempotency.py` (6: keyed-post replays/sends-once, no-key never dedups,
  failure retryable, distinct keys, + 2 `send_email` leaf-level dedup/distinct) + 1 headless-guard +
  hermetic fixes. Full Google/OAuth/gateway regression green; `ruff` clean; **zero new mypy errors**
  (oauth 19→19, cli/main 121→121; client.py actually 5→4).

### P1-2 — hot-path model tiering (`core/routing/classifier.py` + `core/loop.py`)

- **Found:** `ExecutionLoop.__init__` stores `self.router` (optional `ModelRouter`) but `self.router`
  is **never used** in the generate path. Both `_generate_with_retry` and `_stream_generate` always
  call `self.llm_client` — the fixed default client. Net effect: 100% of user turns use the default
  model with no complexity-based tiering and no cross-provider failover chain, even when a
  `ModelRouter` is wired in by `boot_agent`.

- **Changed:**

  1. **`src/hachi/core/routing/classifier.py` (new):** Pure `classify_turn_capability(user_input: str)
     -> Capability` function. No LLM calls. Rules (top-to-bottom, first match wins):
     - **LONG\_CONTEXT** — prompt ≥ 16 000 chars (~4 000 tokens) OR long-doc phrase detected
       ("entire file", "whole codebase", "all pages", "full document", etc.).
     - **CODING** — code fence (`` ``` ``) found OR ≥ 2 coding keywords present
       (`def `, `class `, `import `, `function`, `implement`, `refactor`, `debug`, `bug`, `error`,
       `exception`, `syntax`, `compile`, `build`, `test`, `unittest`, `pytest`, `lint`,
       `type hint`, `type annotation`).
     - **SUMMARIZATION** — `summarize`/`summarise`, `tl;dr`, `tldr`, `key points`, `main points`,
       or `abstract` detected.
     - **REASONING** — analytical phrase detected (`step by step`, `explain`, `analyse`/`analyze`,
       `compare`, `evaluate`, `pros and cons`, `trade-off`, `why`, `reasoning`, `cause`,
       `because`, `therefore`, `conclusion`) **and** prompt is ≥ 200 chars (short "why?" stays default).
     - **REASONING (default)** — all other turns (REASONING is the widest capability net:
       all Anthropic models support it so the router always has candidates).

  2. **`src/hachi/core/loop.py`:**
     - Added `self._turn_client: BaseLLMClient = llm_client` instance attribute (set in `__init__`,
       default = `llm_client` so router=None path is byte-for-byte unchanged).
     - Added `_resolve_turn_client(user_input)` method: calls `router.new_turn()` (clears the A12
       sticky cache), calls `classify_turn_capability(user_input)`, then `router.select(capability)`.
       On `NoRouteError` or any routing exception: logs at DEBUG and falls back to `llm_client`.
       Sets `self._turn_client` to the resolved/fallback client.
     - In `run()`, after `user_input_for_turn` is resolved: resets `self._turn_client = self.llm_client`
       then calls `self._resolve_turn_client(user_input_for_turn)` when `self.router is not None`.
     - Replaced `self.llm_client.generate` → `self._turn_client.generate` in `_generate_with_retry`.
     - Replaced `self.llm_client.generate_stream` → `self._turn_client.generate_stream` in
       `_stream_generate`.
     - Updated the model-name lookups (`_llm_model` for span + `model_name` for cost tracking) from
       `self.llm_client` → `self._turn_client` (accurate telemetry for the actual generating model).

- **Why:** ModelRouter already builds a `ResilientClient` fallback chain per `(capability,
  constraints)`. By routing the main turn through it we get: (a) cheaper models for simple turns,
  (b) reasoning-class models for multi-step/complex turns, (c) automatic cross-provider failover if
  the primary is down — all with zero additional LLM calls. The heuristic mis-routes are safely
  degraded (wrong tier, not wrong answer) and the back-compat guarantee means existing sessions with
  no router see zero behavior change.

- **Sticky-per-turn:** `router.new_turn()` is called once at the top of each `run()` call so the A12
  sticky-route cache is cleared and the turn re-selects independently. Within a single run() the
  `_resolve_turn_client` selection is stable; the router's own sticky cache handles repeated `select()`
  calls (e.g. from sub-tool routing within the same turn).

- **Verify (2026-06-24):**
  - `uv run pytest tests/test_hot_path_routing.py tests/test_e2e_loop.py tests/test_routing_compat.py
    tests/test_routing_router.py tests/test_routing_capability.py tests/test_routing_policy.py
    tests/test_provider_registry.py tests/test_routing_registry.py -q` → **119 passed / 0 failed**.
  - `uv run ruff check src/hachi/core/loop.py src/hachi/core/routing/classifier.py
    tests/test_hot_path_routing.py` → **All checks passed**.
  - `uv run ruff format --check` (same three files) → **already formatted / clean**.
  - `uv run mypy src/hachi/core/loop.py --ignore-missing-imports` → **10 errors (baseline = 10,
    no new errors introduced)**.
  - `uv run mypy src/hachi/gateway/orchestrator.py --ignore-missing-imports` → **34 errors (baseline =
    34, untouched)**.

---

### P1-3 — enforce daily spend cap

**Found.** `max_daily_cost_usd` was declared in `LimitSettings` (`core/settings.py:117`),
displayed in the CLI `/spend/daily` route (`cli/main.py:1441`), and stored in the daily
ledger via `SessionStore.record_daily_cost` — but never read back to block a turn.
`get_daily_spend` had exactly one caller (the display path). The per-session and per-turn
caps in `core/loop.py` were enforced (`_budget_exceeded` / `_turn_budget_exceeded`) but
the calendar-day cap was silently ignored.

**Changed.**
- `src/hachi/gateway/orchestrator.py` — three minimal edits:
  1. Added `_max_daily_cost_usd: float | None = None` instance attribute to
     `AgentSession.__init__` with a comment noting the P1-3 source.
  2. Added `AgentSession._daily_cap_exceeded() -> str | None` helper (before
     `_chat_impl_inner`): reads `_session_store.get_daily_spend(date.today().isoformat())`,
     compares against `_max_daily_cost_usd`, returns a reason string on breach or `None`.
     Wraps the read in `try/except` — a store failure returns `None` (safe fail-open).
  3. In `_chat_impl_inner` (after `_drain_job_queue`, before `_memory_snapshot` build):
     calls `_daily_cap_exceeded()`; if truthy, emits `BUDGET_EXCEEDED` event and returns
     `[BUDGET LIMIT REACHED] daily cost cap reached (~$X.XXXX >= $Y.YY)` — same format
     as `loop.py`'s per-session/per-turn refusals.
  4. In `boot_agent`: reads `max_daily_cost_usd` from `limits_cfg` /
     `HACHI_MAX_DAILY_COST_USD` env (same pattern as session/turn caps), assigns to
     `session._max_daily_cost_usd` after `set_session_store`.
  5. Added `BUDGET_EXCEEDED` import from `hachi.core.runtime_events`.
- `tests/test_daily_cap_enforcement.py` — new file; 12 focused tests covering all cases:
  cap not set / zero / store None (all return None), under cap, at cap, over cap, store
  read error (fail-open), date key alignment, and `_chat_impl_inner` refusal message +
  event emission.

**Why.** Minimum-correct fix: the check lives in the orchestrator (not the loop) because
that is where `_session_store` and the config-derived cap are both visible at turn start.
No loop state is mutated. Abort-only (no model-downgrade) per the P1-3 scope; downgrade
is a separate P1-2 finding. `BUDGET_EXCEEDED = "budget.exceeded"` was already in the
runtime event taxonomy — no new event invented.

**Verify.**
```
uv run pytest tests/test_daily_cap_enforcement.py tests/test_daily_spend_ledger.py -q
uv run ruff check src/hachi/gateway/orchestrator.py
uv run mypy src/hachi/gateway/orchestrator.py --ignore-missing-imports
```

---

### P1-4 — web Stop cancels the server-side turn

**Found.** `ExecutionLoop.cancel()` (a `threading.Event`) is correctly implemented and
tested. But it was unreachable from the gateway. The gateway only called
`turn_task.cancel()` (asyncio `CancelledError`) on client disconnect — which cancels the
*coroutine* waiting for the result but not the *worker thread* running the turn via
`anyio.to_thread.run_sync(...)`. The worker thread continued to completion, incurring
full LLM and tool costs after the user hit Stop. There was also no HTTP route to trigger
a mid-turn cancellation explicitly.

**Decided/Changed.**
1. **`GatewayControlPlane.__init__`** (`src/hachi/gateway/control_plane.py`) — added
   `on_interrupt: Callable[[str], dict[str, Any]] | None = None` parameter (stored as
   `self._on_interrupt`), mirroring the existing `on_chat`/`on_connect` callback pattern.
2. **`GatewayControlPlane.interrupt(session_id)`** — new public method: checks that the
   session is live (returns `{"interrupted": False}` if not), then calls `_on_interrupt`
   if wired (swallows handler exceptions so it never leaks a 5xx). Always returns
   `dict[str, Any]` with a single `"interrupted"` bool key.
3. **`_InProcessGatewayRuntime.interrupt_session(session_id)`** (`src/hachi/cli/main.py`)
   — new method: looks up the `AgentSession` by session_id under `_agents_lock`, calls
   `agent.loop.cancel()` (thread-safe), returns `{"interrupted": True/False}`.
4. **`_build_gateway_control_plane`** (`src/hachi/cli/main.py`) — wires
   `on_interrupt=runtime.interrupt_session if runtime else None` (one new line, matching
   the pattern of the 30+ other callbacks in that function).
5. **`POST /sessions/{session_id}/interrupt`** (`src/hachi/gateway/fastapi_app.py`) —
   new route; uses the same `_check_session_ownership` + `_require_auth` as every other
   `/sessions/{id}` route; returns `SessionInterruptResponse` (new `BaseModel`). Returns
   200 with `{"interrupted": false}` for non-live sessions (safe, never 404/500).
6. **SSE disconnect wiring** (`fastapi_app.py`) — both the primary SSE stream
   (`/sessions/{id}/stream`) and the OpenAI-compatible stream (`/v1/chat/completions`)
   now also call `control_plane.interrupt(session_id)` on `await request.is_disconnected()`
   in addition to the existing `turn_task.cancel()`.
7. **Frontend** (`frontend/src/lib/data/domains/chat.ts`) — `stopStreamingLive()` now
   fires `POST /sessions/{id}/interrupt` as a fire-and-forget (`catch(() => void 0)`)
   before calling `abortSse()`, so the Stop button explicitly stops the server-side
   worker thread even when SSE disconnect detection lags.
8. **OpenAPI** — `openapi/hachi-openapi.json` and `frontend/src/lib/data/schema.d.ts`
   regenerated to include the new route and `SessionInterruptResponse` schema.
9. **Tests** — `tests/test_gateway_interrupt.py` (new, 13 tests): control-plane unit
   tests (handler called, unknown-session safe, no-runtime safe, handler-exception safe),
   HTTP integration tests (200/403/401), ownership enforcement, and a real-loop smoke test
   verifying `_cancel_event` is set by `loop.cancel()`.

**Why.** The minimal correct path: `loop.cancel()` already existed and was fully tested;
the gap was purely a wiring gap. No cancellation logic was reimplemented. The callback
pattern matches the existing 30+ callbacks in `control_plane.py` exactly, keeping the
surface consistent. The SSE and frontend wiring are belt-and-suspenders: the browser
disconnect alone should trigger `is_disconnected()` → `interrupt`, but the explicit Stop
button call guarantees the signal arrives even on HTTP/1.1 where disconnect detection may
lag by one poll interval.

**Verify.**
```
uv run pytest tests/test_gateway_interrupt.py tests/test_gateway_control_plane.py tests/test_loop_backstop_cancel.py tests/test_session_ownership.py -q
uv run ruff check src/hachi/gateway/control_plane.py src/hachi/gateway/fastapi_app.py src/hachi/cli/main.py tests/test_gateway_interrupt.py
uv run ruff format --check src/hachi/gateway/control_plane.py src/hachi/gateway/fastapi_app.py src/hachi/cli/main.py tests/test_gateway_interrupt.py
uv run mypy src/hachi/gateway/fastapi_app.py --ignore-missing-imports   # must be 0
uv run mypy src/hachi/gateway/control_plane.py --ignore-missing-imports  # must be 0
npm run --prefix frontend typecheck   # must be 0
```

---

### P1-8 — MCP retry / circuit-breaker / reconnect

**Found.**  `MCPServerConnection.call_tool(...)` was single-shot: one transport call, no
retry, no circuit-breaker, no reconnect.  A flapping or mid-session-dead MCP server was
re-hit every turn at full blocking cost.  The `resilient_call` / `HealthRecorder` /
`RetryPolicy` machinery in `core/resilience.py` was already wired to LLM, Speech, and
Search providers — but never to MCP.  `errors.py` already defined `MCPError` and
`ToolError` (both unused: `grep "raise ToolError\|raise MCPError" src` → 0).  When an
MCP transport error occurred, `call_tool` returned an English string (`"Error: No response
from MCP server '...'"`) that the loop treated as a successful tool result
(`is_error=False`), hiding failures from the LLM and the operator view.

**Decided/Changed.**
1. **`src/hachi/core/mcp_client.py`** — Added:
   - Three new imports at top: `MCPError`, `HealthRecorder + RetryPolicy + resilient_call`.
   - `_MCPTimeoutError(TimeoutError)` — private exception for transport-dead/no-response
     cases; `TimeoutError` base ensures `resilience._is_transient` recognises it as
     retryable without coupling `MCPError` (which can be non-retryable protocol errors) into
     the transient-detection path.
   - Three new attributes in `MCPServerConnection.__init__`: `_retry_policy`, `_health_recorder`,
     `_reconnect_lock` — all scoped **per connection** so one dead server's breaker is invisible
     to peers.  Policy defaults: `max_attempts=3`, `backoff_base_s=0.25`, `breaker_threshold=5`,
     `breaker_cooldown_s=30.0`.
   - `call_tool(...)` replaced: fast-fails (raises `MCPError`) when the breaker is open;
     attempts one `_try_reconnect()` when the transport is dead before entering the retry loop;
     delegates to `resilient_call(_attempt, ...)` with `on_failover` logging; wraps non-MCPError
     exceptions in `MCPError`.
   - `_try_reconnect()` — serialised via `_reconnect_lock`; calls `transport.close()`,
     re-creates transport via `_make_transport()`, re-runs `_start_inner()` (the same sequence as
     `MCPServerConnection.start()`, minus the outer timed thread).
   - `_call_tool_once(...)` — extracted from the old `call_tool` body; raises
     `_MCPTimeoutError` on no-response (transient/retryable) and `MCPError` on JSON-RPC error
     responses (non-transient, not retried).
2. **`tests/test_mcp_resilience.py`** (new) — 16 tests covering all five required scenarios:
   transient retry + success, max-attempts exhaustion, breaker opens + fast-fails without
   touching transport, dead transport → exactly one reconnect, reconnect failure → MCPError,
   no reconnect when transport healthy, happy-path result unchanged, per-server isolation.
   Uses `FakeTransport` (no subprocess/network) and monkey-patched `_call_tool_once`.

**Secondary error-surfacing (DONE — partial).** Before this change, a tool failure
returned a success-looking string (`is_error=False`).  After this change, `call_tool`
raises `MCPError` on all failure paths.  The execution loop (`core/loop.py:401-402`)
already catches any `Exception` from `registry.execute(tool_call)` and returns
`(error_string, is_error=True, None)`, which the loop encodes as `{"is_error": True}` on
the `tool_result` block — visible to the LLM and the operator.  The full structured
`{ok, code, message, retryable}` envelope refactor (cross-cutting, all tool types) is
deferred as a follow-up.

**Why.**  Minimal-safe: reused the existing `resilient_call` + `HealthRecorder` +
`RetryPolicy` with zero changes to `resilience.py`.  Per-server isolation is automatic
because each `MCPServerConnection` owns its own recorder; no global state.  The
`_MCPTimeoutError(TimeoutError)` trick avoids modifying `resilience._is_transient`
(which is also used by LLM/Speech/Search providers) to avoid unintended side-effects.
The reconnect path reuses the existing `_make_transport()` + `_start_inner()` pair that
was already the established boot sequence.  The successful path is byte-for-byte identical
to the old `call_tool` (same return value, same truncation logic).

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_mcp_resilience.py tests/test_mcp_transport_and_config.py tests/test_mcp_client_timeout.py tests/test_mcp_injection_guard.py -q
uv run ruff check src/hachi/core/mcp_client.py tests/test_mcp_resilience.py
uv run ruff format --check src/hachi/core/mcp_client.py tests/test_mcp_resilience.py
uv run mypy src/hachi/core/mcp_client.py src/hachi/core/resilience.py src/hachi/core/errors.py --ignore-missing-imports   # 0 errors across all three
```

---

### P1-6 — apply compaction summary back into history

**Found.** `MemoryManager._run_and_clear_summary_job` generated a real structured
summary via `_generate_structured_summary(messages)` but discarded it — only returning
it as a job audit value. The placeholder string inserted by `_sliding_window_compact`
(`"[Context compacted asynchronously. Permanent facts are being flushed…]"`) stayed in
`_history` permanently. On provider failover or resume the model received the useless
placeholder instead of the real compacted context (Active Task / Completed Actions /
Key Decisions / Active State / Blocked).

**Changed.**

- `src/hachi/core/memory.py` — 3 logical edits:
  1. Added `import threading` to the import block.
  2. Added `self._history_lock: threading.Lock = threading.Lock()` in `__init__` with a
     comment explaining the concurrency contract.
  3. Wrapped `self._history = anchor + [checkpoint] + recent` in `_sliding_window_compact`
     with `with self._history_lock:` (tiny critical section — single list assignment).
  4. Rewrote `_run_and_clear_summary_job`: after generating the real summary it now calls
     `self._apply_summary_to_history(summary)` before returning.
  5. Added new method `_apply_summary_to_history(summary)`: acquires `_history_lock`,
     scans `_history` for the placeholder checkpoint by `_COMPACTION_PLACEHOLDER_SENTINEL`,
     replaces its `.content` **in place** with the real checkpoint text (same framing
     header), then releases the lock. If no placeholder is found (re-compacted in the
     meantime), logs at DEBUG and returns without side-effects.
  6. Added class-level constant `_COMPACTION_PLACEHOLDER_SENTINEL = "[Context compacted
     asynchronously."` so tests and the scanner share one canonical string.

- `tests/test_compaction_summary_applyback.py` — new file, 4 focused tests.

**Concurrency approach — why it is safe.**

`_history` is mutated by the main turn thread (in `_sliding_window_compact`,
`add_message`, etc.) and read-modified by the background worker thread (in
`_apply_summary_to_history`). A plain `threading.Lock` (non-reentrant) is sufficient:

- No caller holds `_history_lock` while calling back into `MemoryManager`, so
  there is no re-entrancy and therefore no deadlock risk.
- The lock is held for the duration of a single list assignment (`_sliding_window_compact`)
  or a short linear scan + one attribute set (`_apply_summary_to_history`) — never across
  the LLM network call (which takes seconds and runs outside the lock).
- Replacing `msg.content` on a `Message` object that is still referenced by `_history`
  is safe: Pydantic `BaseModel` fields are mutable; no list reordering occurs.
- If `_history` was rebuilt by a second compaction before `_apply_summary_to_history`
  runs, the scan finds no sentinel (because the new list was constructed with a fresh
  placeholder Message object that also contains the sentinel if an in-flight job is still
  pending — but `_compaction_in_flight` guard prevents a second job, so only one
  placeholder + one job exist at a time). In the rare case that the history was reset/
  cleared entirely between enqueue and execution, the sentinel scan returns no match
  and the method is a no-op.

**Why.**  The real structured summary (Active Task / Completed Actions / Key Decisions /
Active State / Blocked) is critical for model continuity across context compactions.
Without it, every resumed session or provider failover sees only the opaque placeholder
rather than the dense checkpoint the background job worked to produce.

**Verify.**
```
uv run pytest tests/test_compaction_summary_applyback.py tests/test_conversation_memory.py tests/test_memory_tools_queue.py tests/test_p2_02_job_queue.py tests/test_g3_compaction.py tests/test_memory_fixes.py -q
uv run ruff check src/hachi/core/memory.py tests/test_compaction_summary_applyback.py
uv run ruff format --check src/hachi/core/memory.py tests/test_compaction_summary_applyback.py
uv run mypy src/hachi/core/memory.py --ignore-missing-imports  # 16 errors before, 16 errors after
```

Results (2026-06-24): 4/4 new tests pass; 231/231 memory+compact+job tests pass;
ruff check + format clean; mypy 16→16 (no regression).

---

### P1-5 — durable fact-extraction

**Found.**
`MemoryManager.sync_turn()` (memory.py ~line 236) enqueued fact-extraction jobs with
`func=extraction_func, args=(combined,)` — a closure over the live `self` (vault, LLM client,
memory_writer). The SQLiteJobQueue `_recover_running()` logic (queue.py ~line 624) explicitly
discards orphaned func-only jobs on restart: any extraction job in-flight at process death is
silently dropped. `handle_extract_fact` in `job_handlers.py` existed as a stub seam and performed
no actual extraction. `JobContext.llm_client` and `JobContext.memory_writer` fields were absent.

**Changed.**
1. **`src/hachi/core/memory.py`** — Added module-level `extract_facts(text, *, vault, llm_client,
   memory_writer=None, session_id="") -> str` containing the shared extraction core (flat JSON-bucket
   path and M1 typed tool-call path). Both `_run_fact_extraction` and `_run_typed_extraction` now
   delegate to it. `sync_turn` with a queue now enqueues `Job(handler_name="extract_fact",
   payload={"session_id": str, "text": str, "typed": bool})` — no `func=`, no closures.

2. **`src/hachi/core/runtime/job_handlers.py`** — `JobContext` gains `llm_client` and
   `memory_writer` fields. `build_job_context` resolves: (a) vault via `get_memory_vault()`,
   (b) LLM client via `memory_vault._get_llm_client()` (the module-level singleton used by the
   vault itself), (c) MemoryWriter via `MemoryWriter(get_hachi_paths().memory_dir)` only when
   `typed=True`. All three accept injected factory callables for test isolation.
   `handle_extract_fact` is now real: resolves context, guards against None vault/client (returns
   `"skipped:..."` — never raises), calls `extract_facts`, catches LLM exceptions (returns
   `"error:..."` — never raises).

3. **`tests/test_durable_fact_extraction.py`** — 11 new tests: real extraction via injected fakes,
   durable enqueue assertion (handler_name not func=), JSON-serializable payload, graceful
   degradation on missing services (5 cases), end-to-end worker dispatch through registry.

4. **`tests/test_memory_tools_queue.py`** — Updated `test_sync_turn_rapid_enqueues_are_processed_once_each`
   to use a `JobRegistry` with an injected fake handler (previously monkey-patched `_run_fact_extraction`
   which the durable path no longer calls).

**How LLM client is resolved in the handler.**
`build_job_context` calls `memory_vault._get_llm_client()` — the same module-level shared
`AnthropicClient` singleton that vault LLM calls already use (MED-022). It is stateless and safe
to call from any worker process with `ANTHROPIC_API_KEY` set. If absent, returns `None` and the
handler returns `"skipped:no_llm_client"` without raising.

**Flush job (`_flush_facts_to_vault`) — deferred.**
`_flush_facts_to_vault` takes `messages: list[Message]` — live Pydantic objects. Serializing these
would require a full transcript schema with tool-use/tool-result block handling. The flush job runs
only from sliding-window compaction (rarely triggered), making the risk/reward unfavorable in this
sprint. It remains on `func=` (ephemeral in-process only) and is a follow-up item. A proper
conversion would introduce a `flush_facts` handler with a serialized transcript payload.

**No double-extraction guarantee.**
`sync_turn` with a queue enqueues exactly one job per turn (the `typed` bool selects the path,
not two separate jobs). Without a queue, extraction is skipped entirely. `_run_fact_extraction`
and `_run_typed_extraction` are only reachable via direct call (never from the queue path). The
handler calls `extract_facts` once inside a single try/except.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_durable_fact_extraction.py tests/test_memory_tools_queue.py tests/test_p2_02_job_queue.py tests/test_conversation_memory.py tests/test_durable_store.py tests/test_durable_waits.py tests/test_job_queue.py tests/test_memory_fixes.py tests/test_memory_loud_failures.py tests/test_memory_reliability.py -q
uv run ruff check src/hachi/core/memory.py src/hachi/core/runtime/job_handlers.py tests/test_durable_fact_extraction.py tests/test_memory_tools_queue.py
uv run ruff format --check src/hachi/core/memory.py src/hachi/core/runtime/job_handlers.py tests/test_durable_fact_extraction.py tests/test_memory_tools_queue.py
uv run mypy src/hachi/core/memory.py src/hachi/core/runtime/job_handlers.py --ignore-missing-imports
```

Results (2026-06-24): 120/120 tests pass; ruff check + format clean; mypy before=18 errors (16+2),
after=15 (13+2) — net improvement of 3 (refactored methods removed some pre-existing errors). No regression.

---

### P1-9 — backup/restore CLI + Windows CI + GitHub connector

#### Part A — `hachi backup` / `hachi restore` CLI

**Found.** `SessionStore.backup(dest)` existed (core/session_store.py:862) with no callers and no
CLI entry point. The memory vault (ChromaDB at `paths.chroma_dir`) had no backup path at all. Users
had no supported way to protect or recover their session history or memory vault.

**Changed.**
- `src/hachi/cli/main.py`: Added `@app.command("backup")` and `@app.command("restore")`.
  - `hachi backup [--dest <dir>]`: creates `<dest>/hachi-backup-<YYYYMMDD-HHMMSS>/` containing
    (1) `sessions.db` via `SessionStore.backup()` (online hot-backup, safe with a running gateway),
    (2) `chroma_vault/` via `shutil.copytree`, (3) `settings.toml` + `device-permissions.og`.
    `.env` files are **explicitly excluded** (contain secrets) — the output states this clearly.
    Default dest: `<state_dir>/backups/`.
  - `hachi restore <src> [--yes]`: copies `sessions.db` back via `shutil.copy2` and replaces the
    live `chroma_vault/` via `shutil.rmtree` + `copytree`. Requires `--yes` or interactive
    confirmation; refuses cleanly on cancel. Exits 1 with a clear message if src is missing.
- `tests/test_backup_restore.py`: 11 tests covering backup creates files (sessions.db round-trip via
  real SQLite, chroma_vault dir copy, config files, secrets excluded, output mentions exclusion,
  default dest), and restore round-trips both artefacts and refuses without confirmation.

**Why.** The backup command gives users a point-in-time snapshot of session history + memory vault
with zero dependencies (no archive format, no external tools). Secrets are intentionally excluded
because `.env` contains plaintext credentials that belong in a secret manager, not a backup dir.
The restore guard (`--yes`) prevents accidental overwrite of live data.

#### Part B — Windows in CI

**Found.** `.github/workflows/ci.yml` `test` job matrix was `[ubuntu-latest, macos-latest]`.
The primary dev platform (Windows 11) was not covered, so Windows-specific regressions in path
handling, file encoding, or subprocess behaviour would not be caught in CI.

**Changed.**
- `.github/workflows/ci.yml`: Added `windows-latest` to the `test` job matrix. `fail-fast: false`
  was already set so a Windows failure does not mask Linux/macOS results. The `uv sync` and
  `uv run pytest -q` steps are cross-platform and require no shell changes.

**Why.** The Windows encoding fix at main.py boot (`sys.stdout.reconfigure`) and several
Windows-specific path guards already exist; CI should verify they stay working.

#### Part C — phantom GitHub connector removed

**Found.** `connector_registry.py` registered a full GitHub OAuth2 `ConnectorSpec` (id="github")
with authorize/token URLs and env-var mappings, but there is no `src/hachi/integrations/github/`
backend and no GitHub tool. A user who clicked "Connect GitHub" in the UI would complete the OAuth
flow and then have nothing to use it with — a dead UI affordance.

**Decision: REMOVED the registration** (clean removal was straightforward — no deep entanglement).

**Changed.**
- `src/hachi/integrations/connector_registry.py`: Removed the `github` `ConnectorDef` from
  `CONNECTORS` and the `"github"` entry from `OAUTH2_CLIENT_ID_ALIASES`. Updated the module
  docstring table to remove the github rows and added a NOTE explaining the intentional absence
  (add back once `src/hachi/integrations/github/` exists).
- `tests/test_oauth_integrations.py`: Updated `test_all_connectors_have_ids` to assert
  `"github" not in ids` (with explanatory comment) and lowered the minimum connector count from 5
  to 4. Replaced the github-specific `test_status_configured_when_creds_present_but_no_token` test
  with the same logic targeting `notion` (same OAuth2 pattern, actually backed by tools).

**Why.** Clean removal is better than a documented dead affordance: users don't see a "Connect
GitHub" button that leads nowhere, and the code surface is smaller. The secret-scanner tests
(`test_secret_scanner.py`, `test_secret_patterns_extended.py`) that detect GitHub PAT patterns
(`ghp_*`, `github_pat_*`) are unaffected — they test secret detection, not connector registration.

**Frontend note.** `grep -rn "github" frontend/` may reveal a hardcoded GitHub connector tile.
That is a follow-up (frontend change not tackled here — the backend registry is the source of
truth for the integrations list endpoint, so the tile will simply return 404 on connect attempts
until the frontend is updated or GitHub tools are implemented).

**Verify.**
```
uv run pytest tests/test_backup_restore.py tests/test_oauth_integrations.py -q
uv run ruff check src/hachi/cli/main.py src/hachi/integrations/connector_registry.py tests/test_backup_restore.py tests/test_oauth_integrations.py
uv run ruff format --check src/hachi/cli/main.py src/hachi/integrations/connector_registry.py tests/test_backup_restore.py tests/test_oauth_integrations.py
uv run mypy src/hachi/cli/main.py src/hachi/integrations/connector_registry.py --ignore-missing-imports
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml OK')"
```

Results (2026-06-24): 59/59 tests pass; ruff check + format clean; mypy main.py 122 errors
(baseline was already 122 — no regression); connector_registry.py 0 errors; ci.yml YAML valid.

---

### P1-7 — personalization substrate (UserProfileStore + CorrectionLog + save tool)

**Found.**
The `user_profile` ChromaDB collection (bounded to 25 entries via `MemoryVault.upsert_user_fact /
search_user_profile`) provided raw fact storage, but there was NO structured facade exposing
grouped read/write/correct/export semantics. Corrections were handled destructively (delete +
re-write) with no audit trail — a wrong fact silently vanished. The existing `core_save_user_profile`
tool accepted the old flat `{content, category}` list and the old vault category set
(name/role/preference/habit/…) without grouping into the four P1-7 schema buckets
(identity/preferences/routines/knowledge). No onboarding-wizard changes were in scope.

**Changed.**

- **`src/hachi/core/user_profile.py`** — new module; zero additions to existing files:
  - `PROFILE_CATEGORIES = frozenset({"identity","preferences","routines","knowledge"})` — the
    four P1-7 schema buckets.
  - `_resolve_read_category(vault_category)` — maps old vault categories (name→identity,
    preference→preferences, habit→routines, relationship→knowledge, …) so existing entries
    surface correctly under the new schema without a migration.
  - `CorrectionLog` — durable, append-only SQLite store backed by a `profile_corrections` table
    in the existing `sessions.db` file. Schema: `{id, ts, category, old_value, new_value, reason}`.
    There is NO UPDATE or DELETE path on rows — only INSERT. The table survives process restarts
    because it lives in the same WAL-mode SQLite file as the rest of the durable store. Thread
    safety via a reentrant lock.
  - `UserProfileStore` — structured facade over `MemoryVault`'s user_profile collection:
    - `get() -> dict[str, list]` — reads all user_collection entries and groups by P1-7 category.
    - `set(category, value) -> str` — validates category, writes via `_vault._guarded_write` to
      stamp the P1-7 category in metadata (bypassing `upsert_user_fact`'s legacy normalisation
      that would remap unknown categories to "preference").
    - `correct(old_value_or_id, new_value, *, reason="") -> dict` — non-destructive: (1) appends
      a CorrectionLog entry preserving old_value, (2) deletes the superseded fact from the vault,
      (3) writes the replacement. The old value is NEVER silently lost.
    - `export() -> dict` — returns `{profile: grouped, corrections: all log entries, stats: vault
      capacity}`.

- **`src/hachi/tools/memory_tools.py`** — minimal additions only:
  - `register_memory_tools` signature extended with optional `profile_store=None`; auto-builds a
    `UserProfileStore` from the live vault when omitted (backward-compat — existing callers pass
    zero new args).
  - `save_user_profile_structured(category, value) -> str` — new tool handler that calls
    `UserProfileStore.set` and returns a human-readable result string.
  - `core_save_user_profile_structured` registered with the LLM tool schema (category enum:
    identity|preferences|routines|knowledge, value string).

- **`tests/test_user_profile_store.py`** — new test file, 18 tests.

**CorrectionLog backing choice — SQLite table in sessions.db.**
Rationale: (1) SQLite is the existing house pattern for append-heavy audit data
(`interaction_log`, `idempotency_keys` — same file, same approach). (2) Corrections are a
structured log, not a semantic search target — a relational table is a better fit than ChromaDB.
(3) The file already exists on every install; no new dependency or DB file is introduced.
(4) Append-only is enforced by having no UPDATE/DELETE code path — only INSERT.

**Backward compatibility with existing user_profile writes.**
The `category` metadata field written by old code (name/role/preference/habit/…) is preserved
verbatim in ChromaDB; `UserProfileStore.get()` runs every entry through `_resolve_read_category`
at read time — no migration required, no re-write, no risk of data loss. New writes via
`UserProfileStore.set` stamp P1-7 category strings directly (identity/preferences/routines/knowledge).
The vault's existing `upsert_user_fact` and `memory_tools.py:save_user_profile` are untouched
and continue to write the old category strings; they and the new tool coexist without conflict.

**Deferred (out-of-scope follow-ups).**
- Onboarding wizard step / `SetupStep` flow change capturing the four P1-7 buckets during setup.
- Frontend / web UI for displaying and editing the structured profile.
- Implicit learning / PII-minimisation (P2-4 scope).
- Wrapping `memory_exporter.chroma_to_files` to include corrections in the `.og` export
  (profile.og currently exports raw Chroma entries, not the CorrectionLog).

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_user_profile_store.py tests/test_memory_tools_queue.py tests/test_conversation_memory.py -q
uv run ruff check src/hachi/core/user_profile.py src/hachi/tools/memory_tools.py tests/test_user_profile_store.py
uv run ruff format --check src/hachi/core/user_profile.py src/hachi/tools/memory_tools.py tests/test_user_profile_store.py
uv run mypy src/hachi/core/user_profile.py src/hachi/tools/memory_tools.py --ignore-missing-imports
```

---

### P1-1 — document the single-tenant constraint

**Found.**
`MemoryVault` accepts an `account_id` parameter that namespaces ChromaDB collections per account
(ADV-023 — all five collections get a `<account_id>_` prefix and a per-account subdirectory under
`chroma_vault/`). However, `account_id` is **never plumbed** from the authentication layer:
`boot_agent` constructs the vault with no `account_id` argument; the `TraceContext` `principal`
field in `orchestrator.py` is hardcoded to `"session"` (a placeholder). The result is that every
session on the same install shares the same `core_memory`, `user_profile`, `agent_profile`, and
`delegation_log` collections. Under the stated single-operator model this is safe — there is only
one trusted human behind all sessions. But the moment a second user/token/tenant is added, the two
principals would share one memory store → cross-user PII recall and profile contamination.

**Changed (action a only — documentation + comment seams; NO behavioral change).**

- **`README.md`**: Added a prominent "Security model / single-tenant" subsection (before the
  Configuration section) stating that Hachi is a single-operator product, that ChromaDB collections
  are shared per-install, that `account_id` namespacing exists but is unplumbed, and explicitly
  warning against adding a second principal without wiring `account_id` first.
- **`SECURITY.md`**: Added a "Trust model" section (before "Security Architecture Notes") with the
  same constraint, the explicit do-not-add-second-user warning, the two required wiring steps
  (`MemoryVault` constructor + `ProcessSharedServices` fingerprint), and a reference to the vault
  `account_id` seam (ADV-023).
- **`src/hachi/gateway/orchestrator.py`** (line ~1263): Extended the `principal="session"` comment
  with a SINGLE-TENANT block explaining the unplumbed state and what must be done before a second
  principal is added — so a future developer wiring multi-tenant sees the warning at the code.
- **`src/hachi/core/memory_vault.py`** (`__init__`, line ~302): Added a SINGLE-TENANT comment
  block before the `resolved_account` assignment — the exact construction site where `account_id`
  would be wired — with the same warning and cross-references.

**Why.**
The guard rails for the account_id seam exist in the vault but are invisible to a developer who
only reads the boot path. Documentation at the two seams (vault construction + TraceContext) makes
the constraint impossible to miss and prevents an accidental multi-user deployment.

**Action (b) — account_id plumbing — is intentionally DEFERRED** to the 12-month multi-tenant
roadmap track. Wiring requires: (1) authenticating the principal in the gateway request context,
(2) passing it through `boot_agent` → `MemoryVault.__init__`, and (3) updating
`ProcessSharedServices` to fingerprint per-account so each account gets an independent shared-vault
singleton. This is non-trivial and out of scope for the current hardening pass.

**Verify.**
```
uv run ruff check src/hachi/gateway/orchestrator.py src/hachi/core/memory_vault.py
uv run mypy src/hachi/gateway/orchestrator.py src/hachi/core/memory_vault.py --ignore-missing-imports
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_memory_vault.py -q
```

---

### P2-1 — token-based window management

**Found.**
`MemoryManager.prepare_for_turn` and `add_message` triggered sliding-window compaction only when
`len(self._history) > self._max_active_messages` (a message-COUNT check). A handful of very large
messages — e.g. a single 50 000-character tool output — could push estimated token usage well past
the provider context window BEFORE the count limit (30 messages) was reached. This produced a hard
"prompt too long" 400 from Anthropic instead of graceful compaction.

**Changed.**

*Files changed:*
- `src/hachi/core/memory.py` — token-budget implementation
- `tests/test_token_window_management.py` — 12 new tests (all green)

*Changes:*
1. **Module constant** `_MAX_ACTIVE_TOKENS = 24_000` added (line ~383). Rationale: Anthropic
   claude-3-* has a 200 000-token window; system prompt + tool schemas consume ~8 000 tokens;
   24 000 leaves ~168 000 for the in-flight turn — well under the hard limit with generous headroom.

2. **Constructor param** `max_active_tokens: int | None = None` added to `MemoryManager.__init__`.
   Resolution order (highest to lowest priority):
   - Explicit constructor arg
   - `HACHI_MAX_ACTIVE_TOKENS` environment variable
   - Module constant `_MAX_ACTIVE_TOKENS`

3. **Token trigger in `add_message`** (fires BEFORE the count trigger so large messages compact
   early): `if self.estimate_token_count() > self._max_active_tokens: self._sliding_window_compact(); return`

4. **Token trigger in `prepare_for_turn`** — catches histories loaded via `seed_history()` or
   direct `_history` manipulation that bypassed `add_message`. Fires AFTER `apply_pending_compaction`
   and sets `compacted=True` in the returned `IterationState`.

5. **`_sliding_window_compact` updated**:
   - Guard changed from `if len(self._history) <= self._max_active_messages` to
     `if not over_count and not over_tokens: return` (both triggers are checked).
   - Token-triggered runs use `keep_count = max(4, len(self._history) // 2 - 2)` (drop half)
     instead of the standard `max_active_messages - 2` to make a larger dent in one pass.
   - **Bounded post-compaction loop**: after each pass, if tokens are still over budget, `keep_count`
     is halved and the loop retries. The loop is capped at `_MAX_COMPACT_PASSES = 3` iterations;
     after the third pass it logs a WARNING and returns (the caller retries on the next turn). This
     prevents infinite compaction for pathological cases (e.g. a single retained message that is
     itself larger than the budget).
   - Added `-> None` return type annotation (fixes 2 pre-existing mypy `no-untyped-call` errors).

**Why.**
`estimate_token_count()` already existed and was already used for the lossless tool-result-clearing
path (`_TOOL_RESULT_CLEAR_TOKENS`). Reusing it costs a single O(N) pass per `add_message` call —
cheap given N is bounded by `_max_active_messages`. The change is additive and backwards-compatible:
the message-count trigger is kept as secondary defense-in-depth, all existing tool-pair-safety
logic (`_find_safe_sliding_boundary`), the async summary placeholder/apply-back (P1-6), and the
lossless tool-result clearing are fully preserved.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_token_window_management.py \
    tests/test_conversation_memory.py \
    tests/test_compaction_summary_applyback.py \
    tests/test_memory_tools_queue.py \
    tests/test_g3_compaction.py -q
# → 37 passed

uv run ruff check src/hachi/core/memory.py tests/test_token_window_management.py
uv run ruff format --check src/hachi/core/memory.py tests/test_token_window_management.py
# → All checks passed / 2 files already formatted

uv run mypy src/hachi/core/memory.py --ignore-missing-imports
# → 11 errors (baseline was 13 — net improvement of 2)
```


---

### P2-7 — job-queue dead-letter + re-drive

**Found.**
`JobStatus` had no dead-letter state. When a job's retry count was exhausted (the `else` branch in
`JobWorker.execute_one` at ~line 473 of `queue.py`), it was set to `FAILED`. The
`cleanup_completed` method deleted jobs in `(COMPLETED, FAILED, CANCELLED)` after the retention
window, so a retry-exhausted durable job — e.g. a memory fact-extraction during an extended
provider outage — would be silently and permanently lost. Additionally the retry path called
`update_status(PENDING)` which for SQLiteJobQueue only updated the `status` column, NOT `attempt`
or `scheduled_for`, so the attempt counter in the DB never incremented and the job looped
forever in "attempt 1 < max_retries" without ever reaching the exhausted branch.

**Changed.**

*`src/hachi/jobs/queue.py`*
- Added `DEAD_LETTER = "dead_letter"` to `JobStatus` — semantically: retry-exhausted but handler
  exists; re-driveable.
- Retry path (`execute_one`): changed `update_status(PENDING)` call to `update_attempt()` for
  SQLiteJobQueue (falls back to `update_status` for InMemoryJobQueue). This persists `attempt` and
  `scheduled_for` to the DB so the counter actually increments between reads.
- Dead-letter routing: the retry-exhausted `else` branch (line ~473, `job.attempt >= max_retries`,
  handler exists) now sets `result.status = DEAD_LETTER` and emits `"job.dead_letter"` event
  instead of `FAILED`. Structurally-unexecutable path (line ~369, no callable and no handler in
  registry) stays terminal `FAILED` — retrying would just hit the same wall.
- `cleanup_completed` (both `InMemoryJobQueue` and `SQLiteJobQueue`): now only deletes
  `COMPLETED`, `FAILED`, and `CANCELLED`. `DEAD_LETTER` is explicitly preserved.
- `redrive_dead_letter() -> int`: added to both implementations and the abstract base `JobQueue`.
  Resets every `DEAD_LETTER` job to `PENDING` with `attempt=0`, clears `completed_at` and result
  columns, returns the count. SQLite implementation does a single `UPDATE … WHERE status =
  'dead_letter'` so it's atomic and durable.
- `update_status` in `SQLiteJobQueue`: clears `_func_table` entry on `DEAD_LETTER` (same as
  `FAILED`/`COMPLETED`/`CANCELLED`).

*`src/hachi/core/runtime_read_models.py`*
- `RuntimeReadModelStore.consume_event`: added `"job.dead_letter"` alongside `"job.failed"` in
  the failure-projection branch so dead-lettered jobs appear in `failed_jobs()` / the web UI
  "Needs attention" panel.

*`src/hachi/cli/commands/jobs.py`* (new file)
- `hachi jobs dead-letter`: lists current dead-letter jobs (table or JSON).
- `hachi jobs redrive`: calls `queue.redrive_dead_letter()`, prints count.
- Opens the production `SQLiteJobQueue` via `PlatformDirs("hachi", "opengigantic")` / `jobs.db`.

*`src/hachi/cli/main.py`*
- Imports and registers `jobs_app` under `"jobs"`.

*`tests/test_job_queue.py`*
- Updated `test_failed_job_reaches_read_model_projection`: event name is now `"job.dead_letter"`
  (max_retries=1, handler exists → dead-letter, not terminal FAILED).

**Why.**
A retry-exhausted job represents a transient/resolvable failure (e.g. provider outage, ChromaDB
unavailable). Silently deleting it after cleanup discards durable work with no recovery path.
Dead-lettering preserves the job + its payload/error until an operator explicitly re-drives it
(`hachi jobs redrive`) or until the underlying problem is fixed. Structurally-unexecutable jobs
(no handler registered) remain terminal FAILED because re-driving them would just fail again.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_job_dead_letter.py tests/test_p2_02_job_queue.py tests/test_job_queue.py -q
# → 41 passed

uv run ruff check src/hachi/jobs/queue.py src/hachi/cli/main.py \
    src/hachi/cli/commands/jobs.py src/hachi/core/runtime_read_models.py \
    tests/test_job_dead_letter.py tests/test_job_queue.py
# → All checks passed

uv run mypy src/hachi/jobs/queue.py --ignore-missing-imports
# → 3 errors (unchanged from baseline)

uv run mypy src/hachi/cli/main.py --ignore-missing-imports
# → 122 errors (unchanged from baseline)
```

---

### P2-5 — Behavioral tests for brain.og hard constraints

**Found.**
`tests/test_prompt_composer.py` only asserted structural shape (ordering, section headers,
which fragments appear in cacheable vs dynamic split) — it used a hardcoded `_BRAIN =
"STABLE_BRAIN_CONTENT"` fixture and never touched the shipped `brain.og`.  Deleting any
constraint line from `src/hachi/default_skills/brain.og` would not fail any test.

**Changed.**
Added `tests/test_brain_constraints.py` (11 new tests; 0 source file changes).

Two test layers:

*Source-level (7 tests)* — read the raw shipped brain.og and assert each guardrail is
present as text.  These fail the moment the line is deleted from the source.

*Composition-level (4 tests)* — render brain.og through the full production pipeline
(`parse_og_file` → `_render_brain_prompt` → `build_stable_base`) and assert each
constraint survives into the composed prompt string.  A composer bug that silently drops
a node type (e.g. skipping all `::warning` blocks) would be caught here even if the
source is intact.

Invariants guarded:

| Test | brain.og guardrail | Why it matters |
|---|---|---|
| `test_brain_og_no_hallucination_rule_present` + `test_no_hallucination_rule_survives_composition` | `::warning` in `execution-principles`: "NEVER hallucinate tool outputs" | Core honesty constraint — without it the agent may fabricate tool results |
| `test_brain_og_no_claim_without_tool_use_rule_present` | `::warning`: "NEVER claim you completed a task without actually using tools" | Grounding rule — prevents false success confirmations |
| `test_brain_og_destructive_command_confirmation_rule_present` + `test_destructive_command_rule_survives_composition` | `tool-philosophy::full`: "Never run destructive commands without explicit user confirmation" | Irreversible-action safeguard — rm -rf / format protection |
| `test_brain_og_execution_engine_identity_present` + `test_execution_engine_identity_survives_composition` | `identity::full`: "You are NOT a chatbot. You are an execution engine" | Identity anchor — prevents the agent drifting to passive advice-giving |
| `test_brain_og_skill_search_first_rule_present` | `tool-philosophy` + `skill-routing::full`: "ALWAYS check for relevant skills before improvising" | Core .og moat — agent must load skill blueprints before improvising |
| `test_brain_og_warning_blocks_are_hard_constraints_rule_present` | `skill-routing::full`: "::warning blocks, treat them as hard constraints — never violate them" | Meta-rule — makes all other warnings mandatory rather than advisory |
| `test_hard_constraints_section_present_in_composed_prompt` | `--- HARD CONSTRAINTS ---` header emitted by `_render_brain_prompt` Layer 2 | Guards the renderer's warning-aggregation loop specifically |

Matching strategy: case-insensitive substring search on a few distinctive keywords per
constraint (e.g. `"hallucinate" + "tool"`), not exact full-line matches, so trivial
rewording does not produce false failures while deletion still causes failure.

**Why.**
The audit (P2-5) identified that CI had no behavioral coverage of safety guardrails.  A
refactor or brand-rename PR that accidentally truncated a node, or a composer change that
dropped the warning-block rendering layer, would ship silently.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_brain_constraints.py tests/test_prompt_composer.py -q
# → 26 passed

uv run ruff check tests/test_brain_constraints.py
# → All checks passed

uv run ruff format --check tests/test_brain_constraints.py
# → 1 file already formatted
```

---

### P2-11 — deep readiness probe + compose healthcheck

**Found.**
`_gateway_readiness_probe()` in `src/hachi/cli/main.py` (line ~2028) only checked that
two files exist (`global_config_toml`, `permissions_file`).  A gateway with no provider
API key, an unwritable session-store directory, or a dead job-worker thread still
reported `"ready": true`.  `docker-compose.yml` had no `healthcheck` for the `hachi`
service — Docker could not distinguish a broken gateway from a healthy one.

**Changed.**

| File | Change |
|------|--------|
| `src/hachi/cli/main.py` | `_gateway_readiness_probe` now returns `(bool, list[str], dict[str, str])` with five checks. Added `_GATEWAY_RESIDENT_WORKER` module-level slot; `_InProcessGatewayRuntime._boot_session_agent` populates it after agent boot so the probe can inspect worker liveness without coupling to the runtime instance. Added `ResidentWorkerThread` import. |
| `src/hachi/gateway/control_plane.py` | `readiness()` unpacks both 2-tuple (legacy) and 3-tuple probes; adds `checks` key to the returned dict. Constructor type annotation updated. |
| `src/hachi/gateway/fastapi_app.py` | `ReadinessResponse` Pydantic model gains `checks: dict[str, str]` field (default `{}`). |
| `docker-compose.yml` | Added `healthcheck` to the `hachi` service (30 s interval, 10 s timeout, 3 retries, 20 s start_period, `curl --fail http://localhost:8787/readiness`). `frontend.depends_on` now waits for `service_healthy`. |
| `tests/test_readiness_probe.py` | 12 new tests covering all five checks and the HTTP route. |

**Readiness checks performed** (all fast + side-effect-free; no live API calls):

1. `config_file` — global `settings.toml` exists.
2. `permissions_file` — `device-permissions.og` exists.
3. `provider_configured` — API key resolvable from env / keyring for the configured
   provider (skipped for keyless providers such as Ollama).
4. `session_store_writable` — `mkstemp` + immediate unlink in the sessions-DB parent
   dir confirms the directory is writable without persisting anything.
5. `job_worker` — if a `ResidentWorkerThread` has been registered, it must be alive
   (`.is_running` ↔ `thread.is_alive()`).  Pre-session (not yet registered) is
   reported as `"not started"` and is **not** a blocker.

**Structured result shape** (`GET /readiness`):

```json
{
  "status": "ready | not_ready",
  "ready": true,
  "blockers": [],
  "checks": {
    "config_file": "ok",
    "permissions_file": "ok",
    "provider_configured": "ok (ANTHROPIC_API_KEY)",
    "session_store_writable": "ok",
    "job_worker": "not started"
  },
  "active_connections": 0,
  "time": "2026-06-24T…"
}
```

HTTP 200 when ready; HTTP 503 when `ready` is false.  The endpoint is **unauthenticated**
so Docker / load-balancer probes do not need a bearer token.  No secrets are returned —
values are booleans or short human-readable reasons (no key material).

**Docker-compose healthcheck config:**

```yaml
healthcheck:
  test: ["CMD", "python", "-c",
         "import urllib.request; urllib.request.urlopen('http://localhost:8787/readiness', timeout=5)"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 20s
```

**Why.**
AUDIT P2-11 identified that the readiness probe was cosmetic (file-exists only).  A
broken provider key or a crashed job-worker would silently report "ready", causing
clients and the Docker scheduler to route traffic to a non-functional gateway.  The
compose healthcheck ensures Docker marks the container `unhealthy` and prevents
`frontend` from starting before the gateway is genuinely ready.

The healthcheck originally used `curl`, but `python:3.12-slim` does not include `curl`
(the Dockerfile runs only `pip install` — no `apt-get install curl`).  Using `curl`
would cause the healthcheck to always exit with "curl: not found", permanently marking
the container unhealthy and preventing the `frontend` service (which has
`depends_on: hachi: condition: service_healthy`) from ever starting.  The replacement
uses `urllib.request.urlopen` from Python's stdlib: it raises on non-2xx responses
(including the 503 the readiness route returns when not ready) and on
connection-refused during startup, so the exit code semantics are identical to
`curl --fail`.

**Verify.**
```
cd /d/OpenGigantic/hachi
PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_readiness_probe.py tests/test_gateway_control_plane.py \
    tests/test_cli_gateway_command.py -q

uv run ruff check src/hachi/cli/main.py src/hachi/gateway/fastapi_app.py \
    src/hachi/gateway/control_plane.py tests/test_readiness_probe.py
uv run ruff format --check src/hachi/cli/main.py src/hachi/gateway/fastapi_app.py \
    src/hachi/gateway/control_plane.py tests/test_readiness_probe.py
uv run mypy src/hachi/gateway/fastapi_app.py src/hachi/cli/main.py \
    --ignore-missing-imports  # fastapi_app MUST be 0; cli/main stays at 122
python -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('compose valid')"
```

### P2-10 — cold-start resume

**Found.**
`resume.py` `_do_resume()` tried `GatewayControlPlane.instance().get_session(session_id)`
— but `GatewayControlPlane` has no `instance()` singleton method and no `get_session()`
method, so the code NEVER reached the live-session path and always fell through to
`HonestResumeError("Replay not implemented for cold-start resume (slice 2.4 scope)")`.
A WAITING run woken after a gateway restart therefore always raised, even though all
the rehydration machinery (`resume_from_session`, `boot_agent(resume_session_id=…)`,
`_boot_session_agent`) was already present and functional.

**Changed.**

| File | Change |
|------|--------|
| `src/hachi/cli/main.py` | Added `_ACTIVE_RUNTIME: _InProcessGatewayRuntime \| None = None` module-level slot (alongside `_GATEWAY_RESIDENT_WORKER`). `_start_gateway_server` and the `gateway` command set it when a runtime is created. Added `rehydrate_session(session_id) → AgentSession \| None` method to `_InProcessGatewayRuntime`: boots a fresh agent via the REAL `_boot_session_agent(session_id, resume_session_id=session_id)` path and registers it in `_agents`. |
| `src/hachi/core/runtime/resume.py` | Rewrote `_do_resume`. Now reads `_ACTIVE_RUNTIME` from `hachi.cli.main` via `getattr()` at call time (so monkeypatching works). Hot path: session is in `_agents` → `agent.chat(inject_text)` directly. Cold path: session absent → `runtime.rehydrate_session(session_id)` → chat on the rehydrated agent. No-runtime path: `_ACTIVE_RUNTIME is None` → `HonestResumeError` (honest fail preserved). |
| `tests/test_cold_start_resume.py` | 5 new tests (see below). |

**Rehydration wire (how it connects to existing machinery).**
`resume.py._do_resume` calls `runtime.rehydrate_session(session_id)` in
`src/hachi/cli/main.py` (line ~329), which calls
`self._boot_session_agent(session_id, resume_session_id=session_id)` (line ~266),
which calls `boot_agent(resume_session_id=session_id)` in
`src/hachi/gateway/orchestrator.py` (~line 2128).  `boot_agent` creates an
`AgentSession`, then `AgentSession.resume_from_session(source_session_id, max_messages=40)`
(~line 571) loads the SQLite transcript via `SessionStore.get_session_messages` and
seeds it into the `MemoryManager`.  This is the SAME path used by
`_start_gateway_server(resume_session_id=…)` → `_pending_resume_session_id` →
`register_connection(resume_session_id=…)` for normal session-resume-on-connect.

**How the tests prove rehydration is REAL (not faked).**
The key assertion in `TestColdStartResume.test_cold_start_rehydrates_and_resumes_turn` is:
```python
assert agent.seen_resume_session_id == prior_sid
```
The `_fake_boot_agent` captures the `resume_session_id` argument that `boot_agent` was
called with.  `_ScriptedAgent.replayed_messages` is populated by calling
`session_store.get_session_messages(resume_session_id, …)` on the REAL store — so the
test also verifies that two transcript messages written before the run was created are
returned in order.  A fake session that bypassed `boot_agent` would have
`seen_resume_session_id=None` and `replayed_messages=[]`, failing both assertions.

**What still HonestResumeError-s.**
When `_ACTIVE_RUNTIME is None` (standalone `hachi run` CLI, `uv run hachi` without
`--runtime`, or any context where the gateway was never started), `_do_resume` raises
`HonestResumeError("_ACTIVE_RUNTIME is None …")`. Tested by
`TestNoRuntimeHonestFail.test_raises_honest_resume_error_when_no_runtime`. The run is
rolled back to WAITING (not FAILED) so the operator can wake it again after starting
the gateway.

**Idempotency preservation.**
`resume_run` guards `WAITING→RUNNING` at the top; all other statuses (RUNNING,
COMPLETED, CANCELLED, FAILED) return `"no-op: status is …"` immediately without
calling `_do_resume`. Tested by `TestIdempotency.test_double_wake_is_noop_for_completed`
and `test_double_wake_is_noop_for_running`.

**Verify.**
```
cd /d/OpenGigantic/hachi
PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_cold_start_resume.py tests/test_durable_store.py \
    tests/test_durable_waits.py tests/test_suspend_workflow.py \
    tests/test_gateway_runtime_validation.py -q

uv run ruff check src/hachi/core/runtime/resume.py src/hachi/cli/main.py \
    tests/test_cold_start_resume.py
uv run ruff format --check src/hachi/core/runtime/resume.py \
    src/hachi/cli/main.py tests/test_cold_start_resume.py
uv run mypy src/hachi/core/runtime/resume.py src/hachi/gateway/orchestrator.py \
    src/hachi/cli/main.py src/hachi/gateway/control_plane.py \
    --ignore-missing-imports
# resume.py/control_plane.py MUST be 0 errors; orchestrator stays at 34; cli/main stays at 122
```

---

### P2-10b — direct test for resume_from_session (real replay proof)

**Found:** `AgentSession.resume_from_session` (orchestrator.py ~571) had zero test coverage.
Searching `tests/` for `resume_from_session` returned no matches.  The method is the
substance of cold-start resume — it reads a prior session's transcript from SQLite,
filters to user/assistant rows, seeds them into `MemoryManager`, and caches the pairs
in `_resumed_transcript` for the UI.  Despite its criticality, no test ever called it
directly; the only adjacent coverage was `test_cold_start_resume.py` which stubs out
`boot_agent` entirely and never exercises the replay internals.

**Changed:** Added `tests/test_resume_from_session.py` — 18 tests across 6 classes,
no mocks on the memory or store path.

**Why / design choices:**

- Construction pattern copied verbatim from `tests/test_interaction_log.py` (line 121):
  `sess = AgentSession.__new__(AgentSession)` then set only `_session_store`, `memory`,
  and `_resumed_transcript`.  This avoids boot_agent and its 30+ required dependencies
  while still exercising the production code path.

- `MemoryManager()` is constructed with no arguments (bare defaults) — sufficient for
  `seed_history`, which only appends to `_history` and sets `_last_user_query`.

- Real `SessionStore(db_path=str(tmp_path / "…"))` with `start_session()` + `flush_sync()`
  before every read — matches the pattern already established in the session_store tests.

- History inspection via `mm.history` (the public `@property` at memory.py ~629) which
  returns `self._history` — the exact list extended by `seed_history`.

- `seed_history` nuances accommodated:
  1. It uses `extend()`, not prepend — so pre-existing history comes BEFORE resumed
     messages (locked in by `TestSeedHistoryNuances::test_seed_history_appends_not_prepends`).
  2. It scans reversed to set `_last_user_query` to the most-recent user content
     (locked in by `test_last_user_query_updated_after_resume`).
  3. Returns `len(messages)` so the count == number of user+assistant rows passed.

- `get_session_messages` returns oldest-first within its `limit=` cap, and the cap
  selects the N most-recent rows from the DB — so `max_messages=2` on a 4-row session
  yields the final pair (locked in by `TestMaxMessagesCap::test_max_messages_pulls_most_recent`).

**Verify:**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_resume_from_session.py -q
# 18 passed in 4.43s

uv run ruff check tests/test_resume_from_session.py
# All checks passed!

uv run ruff format --check tests/test_resume_from_session.py
# 1 file already formatted
```

**Bug found:** None.  The implementation matches its documented contract exactly.
The empty-content guard (`content = row.get("content") or ""` + `not content` check)
correctly drops both None and `""` content; the tool-row filter is exact-set membership.

---

### P2-13 — perf/latency regression guard (recall + compaction)

**Found.** No CI guard existed to catch unbounded/excessive work in the two hot paths:
(1) `MemoryManager._sliding_window_compact` — the post-compaction tightening loop was
bounded at `_MAX_COMPACT_PASSES=3` in code but never covered by a regression test asserting
on the call-count bound; (2) `MemoryVault._query_collection` — always called with a bounded
`n_results=top_k` but no test verified the argument reached the ChromaDB collection; (3) lazy
ChromaDB init (`_chroma_client=None` after `__init__`) was covered in `test_g3_vault_lazy.py`
but not expressed as an explicit perf-regression assertion in a dedicated file.

**Changed.** New file `tests/test_perf_regression.py` — 13 deterministic structural tests, zero
wall-clock assertions (no flaky CI thresholds). Four test classes:

- **`TestCompactionPassBound`** (2 tests): spies on `_generate_structured_summary` via a call-
  through wrapper and asserts `call_count <= 3` even when `max_active_tokens=1` (every pass still
  over budget). Seam: `_MAX_COMPACT_PASSES = 3` local constant at `memory.py:1013`,
  `for _pass in range(_MAX_COMPACT_PASSES):` at `memory.py:1029`.

- **`TestCompactionPerTurnWorkBounded`** (2 tests): spies on `_sliding_window_compact` itself
  and asserts (a) adding one overflow message triggers at most one compaction call, and (b) 20
  sequential `add_message` calls trigger at most 20 compaction calls total (linear, not O(N²)).
  Seam: `add_message()` at `memory.py:638`, compaction trigger at `memory.py:659-665`.

- **`TestHistoryBoundedAfterManyAdds`** (2 tests): after 100 `add_message` calls, token
  estimate stays under `2 × budget` (generous tolerance for the post-append measurement window)
  and message count stays within `max_active_messages + 4`. Locks in the "cliff removed"
  behavior. No spy needed — asserts directly on `estimate_token_count()` and `len(_history)`.

- **`TestRecallBoundedTopK`** (4 tests): uses `_FakeCollection.query_calls` (recording spy
  baked into the fake) to assert `n_results == top_k` for `semantic_search(top_k=5)`,
  `search_user_profile(top_k=10)`, and a custom `top_k=3` call. Seam:
  `collection.query(n_results=top_k, ...)` at `memory_vault.py:774`. A fourth test asserts
  `n_results` is never `None` for any recorded call.

- **`TestVaultLazyInit`** (3 tests): asserts `_chroma_client is None` after `__init__`,
  all `_collections` slots are `None` after `__init__`, and `PersistentClient` is never called
  during `__init__`. Uses `patch.dict(sys.modules, {"chromadb": mock_chroma, ...})` — same
  pattern as `test_g3_vault_lazy.py`. Seam: `self._chroma_client: Any = None` at
  `memory_vault.py:335` and `_collections` dict at `memory_vault.py:339`.

**Why structural, not wall-clock.**
Wall-clock threshold tests are muted or skipped in CI within weeks (flaky on runner variance).
Structural assertions catch the same regressions: if someone removes the `_MAX_COMPACT_PASSES`
bound, `call_count <= 3` fails; if `query` is called without `n_results`, the recording spy
catches it; if `__init__` starts eagerly opening ChromaDB, `_chroma_client is None` fails.

**Spy technique.** Compaction tests wrap the REAL method via a nonlocal counter closure and
reassign `mm._generate_structured_summary = _counting_generate`, then call through
to `original_generate(messages)` so behavior is unchanged and the assertion reflects real
execution — not a reimplementation. Recall tests use a `_FakeCollection` that accumulates
`query_calls` on every `.query()` invocation, which pre-populates the stubbed vault's
`_collections` dict (same technique as `test_memory_fixes.py`).

**ChromaDB dependency.** Zero tests in this file require a real ChromaDB installation.
All vault tests use `MemoryVault.__new__` + pre-populated `_collections` dict. The lazy-init
tests use `patch.dict(sys.modules)` to inject a `MagicMock` chromadb module.

**Real perf bug found.** None. All three guards validated as already correct in source.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_perf_regression.py -q
# 13 passed in 3.67s

PYTHONPATH=src uv run --with pytest --no-project pytest \
    tests/test_token_window_management.py tests/test_compaction_summary_applyback.py -q
# 16 passed — no shared-state collision

uv run ruff check tests/test_perf_regression.py   # All checks passed!
uv run ruff format --check tests/test_perf_regression.py  # 1 file already formatted
```

---

### Eval loop E1 — interaction read/rating API

**Found.** `SessionStore` already had `get_interactions()` and `set_interaction_rating()` (written as the P0-2 eval plumbing), but no gateway routes exposed them to the frontend or eval tooling. The `/review` UI and any trajectory-eval harness had no way to read rows or post ratings without going directly to SQLite.

**Changed.**
- `src/hachi/gateway/fastapi_app.py` — four new Pydantic models (`InteractionRecord`, `InteractionListResponse`, `RatingRequest`, `RatingResponse`) added above the `_lifespan` function (line ~340 area). New `interactions_router` (prefix `/interactions`, `protected_dependencies`) with two routes:
  - `GET /interactions` — query params `session_id` (optional) and `limit` (1–500, default 100). If `session_id` supplied: `_check_session_ownership` then `store.get_interactions(session_id=..., limit=...)`. Otherwise: fetch all rows then filter to sessions owned by the caller (mirrors `list_sessions`' `_owned` helper); no-auth returns everything. 503 if the store is unavailable.
  - `PUT /interactions/{interaction_id}/rating` — body `{rating: "up"|"down", notes?: str}`. Looks up the row's `session_id` first (via `get_interactions` scan), ownership-checks that session, then calls `store.set_interaction_rating`. Returns 404 if no row matched; 422 if `rating` is not `"up"` or `"down"` (Pydantic `Literal`).
  - `app.include_router(interactions_router)` appended to the existing `include_router` block (~line 2507).
- `tests/test_interactions_api.py` — 23 new tests across 5 classes; all use real `SessionStore(db_path=tmp_path)` seeded via `log_interaction`, with `patch("hachi.gateway.fastapi_app._resolve_session_store", ...)` to inject the isolated DB.
- `openapi/hachi-openapi.json` — regenerated; now contains `/interactions` and `/interactions/{interaction_id}/rating`.

**Why.** The write side (`log_interaction`) was complete but dark. This adds the read surface needed for the `/review` UI and eval tooling without any write-side coupling. Ownership gating mirrors the existing `list_sessions` / `get_session` pattern so no new security surface is introduced. `Literal["up","down"]` at the API layer constrains the free-text store column to a meaningful vocabulary without changing the store schema.

**Verify.**
```
uv run pytest tests/test_interactions_api.py -q
# 23 passed

uv run ruff check src/hachi/gateway/fastapi_app.py tests/test_interactions_api.py
# All checks passed!

uv run python -m mypy --config-file mypy-strict-gate.ini
# Success: no issues found in 36 source files

uv run hachi gateway-openapi --output openapi/hachi-openapi.json
# then: python -c "import json; data=json.load(open('openapi/hachi-openapi.json')); ..."
# ['/interactions', '/interactions/{interaction_id}/rating']
```

---

### Eval loop E2 — eval report + regression runner

**Found.** The interaction_log was populated (P0-2) and exposed via the HTTP API (E1), but there was no in-process analytics layer and no structural regression harness. Failure patterns (down-rated turns, tool names, per-model costs) had to be queried manually; there was no way to run a named regression case through the real agent loop and assert structural properties of the trajectory.

**Changed.**

- `src/hachi/core/eval/__init__.py` — package init, re-exports public API.
- `src/hachi/core/eval/report.py` — **REAL analytics; pure function, no I/O.** `build_failure_report(interactions, *, since) -> EvalReport` aggregates over `interaction_log` rows. `EvalReport` fields: `total_turns`, `rated_up`, `rated_down`, `unrated`, `failure_rate` (`down / (up+down)`, 0.0 when no rated turns), `avg_cost_per_turn` (excludes None-cost rows from denominator), `total_cost`, `errored_turns` (output empty/whitespace OR starts with `[error]`/`error:`/`exception:`/`traceback`/`[incomplete]`), `top_failing_tools` (tool→count from down-rated turns only, sorted desc), `per_model` (model→`PerModelStats{count,avg_cost,down_count}`), `recent_failures` (last 10 down-rated turns). Optional `since` ISO filter applied before all aggregation.
- `src/hachi/core/eval/runner.py` — **REAL execution; dependency-injected turn_fn.** Four assertion kinds: `ToolCalledAssertion`, `OutputContainsAssertion`, `NoErrorAssertion`, `MaxCostAssertion`. `run_case(case, turn_fn=...)` calls the injected `turn_fn` (real `ExecutionLoop` in tests, real `AgentSession` in production), evaluates all assertions against the real `TurnTrajectory`, and sets `passed=True` only when the failures list is empty — never hardcoded. `DEFAULT_SUITE` has 2 seed cases; docstring is explicit this is a starting scaffold.
- `src/hachi/cli/commands/eval.py` — `eval_app` Typer sub-app with two commands:
  - `hachi eval report [--json] [--since ISO] [--session SID] [--limit N]` — opens the real SessionStore (same path as `hachi session`), calls `get_interactions`, calls `build_failure_report`, renders a Rich table or JSON. Fully functional.
  - `hachi eval run [--suite PATH]` — honestly reports "not wired" rather than faking a pass (see "Why" below). Suite loading (`.py` files) is scaffolded; JSON format stub present.
- `src/hachi/cli/main.py` — one line added: `app.add_typer(eval_app, name="eval")`.
- `tests/test_eval_report.py` — 26 tests; pin exact aggregation math: rating counts, failure_rate fractions, cost sum/avg, errored_turns rule (empty + prefix), top_failing_tools counts and sort order, per_model stats, since filter inclusion/exclusion, recent_failures cap at 10.
- `tests/test_eval_runner.py` — 12 tests including the **anti-fake proof**: `test_unsatisfiable_assertion_fails_with_reason` passes `output_contains("NEVER_IN_OUTPUT")` against a scripted ExecutionLoop that returns "pong" — asserts `passed=False` with the needle in the failure reason. Any runner that hardcodes pass would break this test.

**Why.**

*Report*: analytics must be a pure function so it is testable without a live database; seeding 38 tests against known rows pins the real math.

*Runner*: dependency-injecting `turn_fn` keeps the runner framework-agnostic and makes the anti-fake guarantee testable without a live API key. The scripted `ExecutionLoop` in the test is the same class that runs in production — not a mock — so the test covers real assertion logic against real loop output.

*`eval run` not wired*: wiring `boot_agent` in the CLI command would require workspace init, LLM credentials, and skills loading — too fragile for a first-pass CLI and not guaranteed in CI. The runner itself is fully exercised in tests. When a real turn_fn is available, wire it in `eval.py` with `from hachi.gateway.orchestrator import boot_agent`.

*`errored_turns` rule*: conservative prefix list catches the three real failure modes (empty reply, crash traces, iteration-limit `[INCOMPLETE]`) without over-flagging short valid responses like "No." The rule is documented in the module docstring and tested.

**Verify.**
```
PYTHONPATH=src uv run --with pytest --no-project pytest tests/test_eval_report.py tests/test_eval_runner.py -q
# 38 passed in 4.68s

uv run ruff check src/hachi/core/eval/__init__.py src/hachi/core/eval/report.py \
    src/hachi/core/eval/runner.py src/hachi/cli/commands/eval.py \
    tests/test_eval_report.py tests/test_eval_runner.py
# All checks passed!

uv run mypy src/hachi/core/eval src/hachi/cli/commands/eval.py --ignore-missing-imports
# Success: no issues found in 4 source files

PYTHONPATH=src uv run --no-project python -c "from hachi.cli.main import app; app()" eval report --json
# {"total_turns": 25, "rated_up": 0, "rated_down": 0, "unrated": 25, "failure_rate": 0.0,
#  "avg_cost_per_turn": 0.0, "total_cost": 0.0, "errored_turns": 0,
#  "top_failing_tools": [], "per_model": {"gpt-4o-mini": {"count": 25, ...}},
#  "recent_failures": [], "since": null}
```

---

### Eval loop E3 — /review frontend screen

**Found.** The gateway already exposes `GET /interactions` and `PUT /interactions/{id}/rating` (committed in the P0 sweep on `reassess`), but the frontend had no screen to display or rate turns. The committed `schema.d.ts` was also stale — it predated these endpoints being added to `openapi/hachi-openapi.json`, so CI `frontend-contract` would have failed on next push.

**Changed.**

| File | Action |
|------|--------|
| `frontend/src/lib/data/schema.d.ts` | Re-generated via `npm run generate:api` — now includes `InteractionListResponse`, `InteractionRecord`, `RatingRequest`, `RatingResponse` |
| `frontend/src/lib/data/types.ts` | Added `AgentInteraction` UI type (`tool_calls`/`memory_hits` as `string[]`, not objects) |
| `frontend/src/lib/store/store.ts` | Added `interactions: AgentInteraction[]` to `State` interface, import, and `domainDefaults()` (defaults to `[]` in live mode) |
| `frontend/src/lib/data/domains/interactions.ts` | NEW — 3-layer domain loader: gateway shapes → `adapt()` → store `hydrate`. `loadInteractions()` GETs `/interactions`, `rateInteraction()` PUTs `/interactions/{id}/rating` then re-fetches. `_hasEverSucceeded` honesty pattern: first live failure clears to `[]` so fixture data is never shown as real. |
| `frontend/src/lib/data/domains/interactions.test.ts` | NEW — 27 vitest tests covering adapter mapping, rating normalization, timestamp humanization, null/undefined defensive coalescing, and RatingRequest body shape |
| `frontend/src/lib/data/useRouteLoaders.ts` | Added `/review` branch lazy-importing `loadInteractions()` |
| `frontend/src/routes/review.tsx` | NEW — `/review` route component: header bar + scrollable card list; each card shows user_input, agent_output, tool_calls/memory_hits as string chips, model/cost metadata, thumbs-up/down buttons, and a collapsible notes textarea. Calls `rateInteraction()` which round-trips to the gateway and re-fetches. |
| `frontend/src/components/shell/Sidebar.tsx` | Added `{ key:'review', route:'/review', label:'Review', icon:'eye' }` to `NAV_ITEMS` |
| `frontend/src/routeTree.gen.ts` | Updated to register `/review` route (normally auto-generated by Vite plugin on `npm run dev`; done manually here to unblock `tsc`) |

**Why.** The 3-layer pattern (gateway shapes → adapter → UI types → `hydrate`) is the established contract for all domain loaders. Following it exactly ensures the screen uses only authoritative gateway data in live mode and degrades gracefully to empty on failure. `rateInteraction` re-fetches after PUT so the rating shown always reflects server truth, not local optimism.

**Verify.**
```
cd frontend
npm run generate:api   # ✓ schema.d.ts updated (was stale — interactions endpoints missing)
npm run typecheck      # ✓ 0 errors
npm run test           # ✓ 82 tests pass (6 test files; +27 new from interactions.test.ts)
npm run check:api      # ✓ clean after schema.d.ts committed (diff is the previously-stale schema)
```

**Note on `check:api`:** The diff shown by `check:api` is the interactions endpoints being added to `schema.d.ts` — these were missing from the committed file because the prior P0 sweep added the gateway endpoints but didn't regenerate the schema. Committing the updated `schema.d.ts` makes `check:api` clean.

---

### E4 — Wire `hachi eval run` via record/replay corpus (2026-06-24)

**Gap.** `hachi eval run` previously printed "not wired in this release" and exited 0 unconditionally. The gap was honest but meant the command could never serve as a CI gate.

**What was built.**

| File | Role |
|------|------|
| `src/hachi/core/eval/replay.py` (NEW) | Production replay harness: `ScriptedLLMClient`, `ToolSpec`, `ReplayCase`, `make_replay_turn_fn`, `run_replay_suite` |
| `src/hachi/core/eval/corpus.py` (NEW) | Curated seed corpus: `DEFAULT_REPLAY_SUITE` with 5 cases (plain text, single-tool, two-tool trajectory, multi-turn smoke, output_contains smoke) |
| `src/hachi/cli/commands/eval.py` (EDITED) | `eval run` command rewired: loads `DEFAULT_REPLAY_SUITE`, calls `run_replay_suite`, prints a Rich scorecard, exits 1 on any failure |
| `tests/test_eval_replay.py` (NEW) | 20 tests covering `ScriptedLLMClient`, `make_replay_turn_fn`, `run_replay_suite`, the full corpus, the anti-fake property, and CLI exit codes |

**Anti-fake guarantee.**
1. `make_replay_turn_fn` builds a REAL `ExecutionLoop` (production class). The only stubbed component is `ScriptedLLMClient`, which replays recorded `LLMResponse` objects instead of calling the Anthropic API.
2. `run_replay_suite` delegates every case to the existing `run_case()` from `runner.py` — the audited anti-fake core. Pass/fail logic is NOT reimplemented.
3. CLI exits non-zero (`typer.Exit(code=1)`) when any case fails. This is proven by `test_eval_run_cli_exits_nonzero_on_failing_case`, which injects a suite with an unsatisfiable `output_contains("NEVER_PRESENT")` assertion and asserts `exit_code != 0`.

**Honest cost limitation.** `ScriptedLLMClient` has no real cost meter; `TurnTrajectory.cost_usd` is always `0.0` for replay runs. `max_cost_usd` assertions are intentionally absent from `DEFAULT_REPLAY_SUITE` — a threshold check against a synthetic `0.0` is meaningless. Document this in both `replay.py` and `corpus.py`.

**Verification output.**

```
uv run pytest tests/test_eval_replay.py tests/test_eval_runner.py -v
# 33 passed in 4.54s (17 new in test_eval_replay.py + 16 pre-existing in test_eval_runner.py)

uv run ruff check src/hachi/core/eval src/hachi/cli/commands/eval.py tests/test_eval_replay.py
# All checks passed!

uv run mypy src/hachi/core/eval src/hachi/cli/commands/eval.py --ignore-missing-imports
# Success: no issues found in 6 source files

uv run hachi eval run
# ───────────────────── hachi eval run — 5 case(s) ──────────────────────
#   PASS  plain_text_reply
#   PASS  single_tool_call
#   PASS  two_tool_trajectory
#   PASS  multi_turn_smoke
#   PASS  output_contains_smoke
# ───────────────────────────────────────────────────────────────────────
# 5 passed / 0 failed  out of 5 total
# Exit code: 0

# Failure path (suite with output_contains("NEVER_PRESENT") assertion):
# ───────────────────── hachi eval run — 1 case(s) ──────────────────────
#   FAIL  will_fail
#          ↳ output_contains('NEVER_PRESENT'): not found; output starts with 'pong'
# ───────────────────────────────────────────────────────────────────────
# 0 passed / 1 failed  out of 1 total
# Exit code: 1
```

---

### E5 — Weekly failure-report automation (2026-06-24)

**Gap.** The `interaction_log` + `build_failure_report()` already existed, but nothing
triggered a periodic report.  A user could only get a report by running `hachi eval report`
manually.  The audit named "weekly-failure-report automation" as the natural next increment
so Hachi self-reports failure-rate degradation over time without human prompting.

**Design: why NOT the agent-turn scheduler.**  `src/hachi/jobs/scheduler.py` fires agent
turns (`Schedule.task` → `session.chat()`).  A failure report is internal computation, not
an LLM turn — it needs no Anthropic API key, no tool loop, and must never contribute to
session cost.  Using the scheduler would model it as a user request, add noise to the
interaction_log, and block on the session lock during a live turn.

**Chosen pattern: mirror `_start_timeout_sweep`.**  `orchestrator._start_timeout_sweep` is
the established pattern for resident internal computation: a module-level function that
starts a daemon thread with a `while True: sleep(); try: work(); except: log_debug` loop.
`_start_eval_report_scheduler` follows exactly this shape:
- Thread named `hachi-eval-report`, daemon=True
- Sleeps `min(interval_seconds, 3600)` per tick (caps at 1 h so the process stays
  responsive even with a 1-week interval)
- Calls `maybe_generate_report(...)` inside try/except, logs at debug on failure, never
  raises

**Decoupled core (`src/hachi/core/eval/scheduled_report.py`).**  All logic is extracted
into a pure module with no orchestrator imports:
- `render_report_markdown(report)` — pure EvalReport → markdown
- `ReportArtifact` — typed result (md_path, json_path, report, generated_at)
- `generate_failure_report_artifact(store, *, out_dir, …)` — reads rows, builds report,
  writes both `eval-report-<stamp>.md` and `eval-report-<stamp>.json`
- `due_for_report(last_run_at, now, interval_seconds)` — pure predicate
- `read_last_report_at` / `write_last_report_at` — atomic marker (temp + os.replace)
- `maybe_generate_report(store, *, out_dir, marker_path, interval_seconds, limit, emit, now)`
  — the single testable unit the thread calls each wake

**Opt-in, default off.**  `EvalReportSettings(BaseModel)` in `src/hachi/core/settings.py`
with `enabled: bool = False`, `interval_seconds: int = 604800`, `limit: int = 1000`.
Boot wiring in `orchestrator.boot_agent` reads `config.get("eval_reports", {})` and calls
`_start_eval_report_scheduler` only when `enabled=True`.  Nothing runs unless the operator
adds `[eval_reports] enabled = true` to `settings.toml`.

**Event.**  `EVAL_REPORT_GENERATED = "eval.report.generated"` added to
`src/hachi/core/runtime_events.py`.  Payload carries `markdown_path`, `json_path`,
`total_turns`, `failure_rate`, `generated_at`.

**Output location.**  `get_hachi_paths().state_dir / "eval-reports"` — confirmed
`state_dir` is where `sessions.db`, `schedules.json`, and `checkpoints/` already live.
`workspace_dir` does not exist; `data_dir` is for persistent data not ephemeral reports.

**Manual entry point: `hachi eval snapshot`.**  New `@eval_app.command("snapshot")` in
`src/hachi/cli/commands/eval.py`.  Generates the artifact immediately, updates the weekly
marker (so the scheduler clock resets), and prints the written paths + totals.  Does not
touch `eval report` or `eval run`.

**Verification output.**

```
uv run pytest tests/test_eval_scheduled_report.py -q
# 37 passed in 1.45s

uv run pytest tests/test_eval_report.py tests/test_eval_runner.py tests/test_eval_replay.py -q
# 55 passed in 5.71s (no regression)

uv run ruff check src/hachi/core/eval src/hachi/core/runtime_events.py \
    src/hachi/gateway/orchestrator.py src/hachi/cli/commands/eval.py \
    tests/test_eval_scheduled_report.py
# All checks passed!

uv run mypy src/hachi/core/eval src/hachi/core/runtime_events.py \
    src/hachi/cli/commands/eval.py --ignore-missing-imports
# Success: no issues found in 8 source files

uv run mypy src/hachi/gateway/orchestrator.py --ignore-missing-imports
# Found 34 errors (all pre-existing; zero new errors from E5 symbols)

uv run hachi eval snapshot --out $TEMP/hachi-eval-test
# Snapshot written  turns=27  failure_rate=0.0%
#   md  → C:\Users\opsin\AppData\Local\Temp\hachi-eval-test\eval-report-20260624-172538.md
#   json→ C:\Users\opsin\AppData\Local\Temp\hachi-eval-test\eval-report-20260624-172538.json
```

**Honest residual limitation.**  The resident scheduler is intentionally dormant until
opted in.  Because `hachi gateway` boot_agent is the entry point, the scheduler is NOT
active in `hachi run` (TUI mode) — it fires only when the gateway is running.  A user who
never runs the gateway can still generate reports on demand via `hachi eval snapshot`.
The first automatic run fires at the first `min(interval, 3600)` tick after `enabled=True`
boot — not immediately on boot.  Both behaviours are intentional: the first-tick-delay
avoids a report storm on restart; gateway-only scope keeps the clean process model intact.

---

### COST-1 — OpenAI-compatible streaming usage (eval-flywheel finding) (2026-06-24)

**Symptom.**  Every `gpt-4o-mini` (and all other OpenAI-compat provider) turn appeared in
the `interaction_log` with `tokens=0` and `token_cost=0.0`.  The eval report showed 100%
of OpenAI-compat interactions with zero cost and zero tokens.

**Root cause.**  `OpenAICompatibleClient.generate_stream` set `payload["stream"] = True`
but never sent `stream_options: {"include_usage": true}`.  Per the OpenAI streaming spec,
usage is omitted from streamed responses unless that option is requested explicitly.  The
final-chunk usage-parse block (`if "usage" in data`) in the SSE loop therefore never fired,
`final_usage` stayed `TokenUsage()` (all zeros), and `cost_tracker.record(model, response.usage)`
recorded nothing.  The non-streaming `generate` path already parsed `usage` correctly — this
was streaming-only.

**Impact.**  Beyond cosmetic eval metrics:
1. Eval report cost/token metrics were always zero for all OpenAI-compat providers.
2. **The daily spend cap (P1-3) was silently inert for streaming OpenAI-compat turns** —
   cost never accrued so the cap never tripped.  This is a trust/safety regression for any
   non-Anthropic user relying on spend limits.
3. The frontend per-turn token/cost badge showed nothing for these providers.

**Fix.**  Added a `stream_usage: bool = True` parameter to `OpenAICompatibleClient.__init__`
stored as `self._stream_usage`.  In `generate_stream`, immediately after `payload["stream"] = True`,
added `if self._stream_usage: payload["stream_options"] = {"include_usage": True}`.
`create_llm_client` reads `provider_config.get("stream_usage", True)` and threads the value
through all four `OpenAICompatibleClient(...)` construction sites (ollama, gemini, named
presets, openai/openai-compatible).  The existing final-chunk parse path
(`if "usage" in data and data["usage"]`) already handled empty-choices + usage-field chunks
correctly — no change needed there.

**Opt-out rationale.**  Default `True` because every major hosted provider (OpenAI, Groq,
Together, DeepSeek, OpenRouter, Gemini-compat, recent Ollama/vLLM) supports `stream_options`.
The opt-out flag (`stream_usage: false` in provider config) exists only for the rare strict
local server that returns HTTP 400 on unknown request fields.  The cost of opting out is
losing usage metrics for that provider.

**Honest limitations.**
- Historical rows in the `interaction_log` already written with `tokens=0`/`cost=0.0` will
  NOT backfill — this is a forward-only fix.
- The `chatgpt-web` (unofficial) provider is inherently usage-less; its `generate_stream`
  is in `unofficial_providers.py` and is unaffected / not addressable.
- Cache-token fields (`cache_read_tokens`, `cache_creation_tokens`) are NOT parsed from the
  OpenAI streaming usage chunk (OpenAI does not return them in the same way Anthropic does);
  this is symmetric with the non-streaming `generate` path and left as a potential follow-up.

**Files changed.**
- `src/hachi/core/llm.py` — `__init__` (new `stream_usage` param + `_stream_usage` attr),
  `generate_stream` (two lines: opt-in block after `payload["stream"] = True`),
  `create_llm_client` (read `stream_usage` from config + thread to all 4 construction sites).
- `tests/test_streaming.py` — updated `_make_openai_client()` to set `_stream_usage = True`
  (mirrors `__init__` default; required because the helper uses `__new__`), added 4 new
  tests: `test_openai_stream_default_sends_stream_options`,
  `test_openai_stream_opt_out_omits_stream_options`,
  `test_openai_stream_usage_captured_from_final_chunk`,
  `test_openai_stream_no_usage_chunk_returns_zeros`.

**Verification output.**

```
uv run pytest tests/test_streaming.py -q
# 18 passed in 3.76s

uv run pytest tests/ -q -k "llm or openai or stream or usage or cost"
# 195 passed, 3584 deselected in 43.44s

uv run ruff check src/hachi/core/llm.py tests/test_streaming.py
# All checks passed!

uv run mypy src/hachi/core/llm.py --ignore-missing-imports
# Success: no issues found in 1 source file
```

### E6 — Eval regression corpus + precise assertions (2026-06-24)

**Loop invariants now protected by the corpus (14 cases):**
- Plain text reply passes through verbatim (output_contains)
- Single tool call fires + final reply appears (tool_called, output_contains)
- Two-tool trajectory across separate iterations (tool_called × 2)
- Multi-turn smoke — 3 LLM turns finishes without error
- output_contains baseline smoke (no tools)
- **Tool error recovery**: `_execute_single_tool` catches tool raises, feeds the error
  string back to the LLM as `is_error=True`; the TURN itself does not raise — `no_error()` passes.
- **Unregistered tool**: `ToolRegistry.execute()` returns the string
  `"Error: Tool '…' is not registered."` (no exception) — turn continues gracefully.
- **Max-iterations cap**: scripted LLM always calls a tool, never emits text — loop
  terminates at `max_iterations=10` returning `[INCOMPLETE]`; `tool_call_count(10)` confirms
  exactly 10 dispatches.
- **Empty/degraded response**: `LLMResponse(content="")` + no tool_calls → loop exits cleanly
  (`not assistant_content` branch at loop.py line 947); `no_error()` + `tool_call_count(0)` pass.
- **Tool with arguments**: `ToolCall.input` is unpacked as `**kwargs` into the callable — verified.
- **Parallel tool calls**: all `ToolCall`s in one `LLMResponse` are submitted to the thread
  pool concurrently (loop.py lines 1013-1017); both tools appear in `tool_calls`; order
  reflects the pre-pass iteration order.
- **Three-tool ordered trajectory**: `tool_called_in_order(["plan","execute","verify"])` +
  `tool_call_count(3)`.
- **Clean reply zero tools**: `tool_call_count(0)` + `output_not_contains("[error]")`.
- **No internal loop sentinel markers in clean output**: checks `[CANCELLED]`, `[TIME LIMIT
  REACHED]`, `[BUDGET LIMIT REACHED]`, `[WORKFLOW SUSPENDED]`, `[INCOMPLETE]` are absent.

**Three new assertion kinds added to `runner.py`:**
1. `ToolCallCountAssertion(count: int)` / `tool_call_count(n)` — `len(trajectory.tool_calls) == count`.
2. `OutputNotContainsAssertion(substr: str)` / `output_not_contains(s)` — `substr not in trajectory.output`.
3. `ToolOrderAssertion(names: tuple[str,...])` / `tool_called_in_order([...])` — `names` is
   an ordered subsequence of `trajectory.tool_calls` (not necessarily contiguous).

**Honest framing:**
- This is a loop-mechanics regression suite, not a model-quality suite.
- `ScriptedLLMClient` replaces only the LLM transport boundary; all ReAct loop, tool dispatch,
  and memory code is production `ExecutionLoop`.
- `cost_usd` is always `0.0` (no real cost meter); `max_cost_usd` assertions are absent.

**Surprising loop behaviors confirmed by reading source:**
- Parallel tool calls are supported in a single `LLMResponse` (the loop iterates all
  `response.tool_calls` twice — pre-pass for side-effects, then pool submit — so order
  in `last_tool_calls` is the pre-pass iteration order, which matches `ToolCall` list order).
- Tool errors are silently absorbed: `_execute_single_tool` returns a tuple, never re-raises
  tool exceptions as loop-level exceptions (only `SuspendWorkflow` propagates).
- An empty `LLMResponse` (no content, no tool_calls) is a CLEAN FINISH, not an error.
- `ToolRegistry.execute()` returns a string for unregistered tools — no exception path.
- No candidate loop bugs were found. All expected-pass cases passed on first run.

**Verification:**
```
uv run pytest tests/test_eval_replay.py tests/test_eval_runner.py tests/test_eval_assertions.py -q
# 64 passed in 5.19s

uv run ruff check src/hachi/core/eval tests/test_eval_replay.py tests/test_eval_runner.py tests/test_eval_assertions.py
# All checks passed!

uv run mypy src/hachi/core/eval --ignore-missing-imports
# Success: no issues found in 6 source files

uv run hachi eval run
# 14 passed / 0 failed  out of 14 total  (exit code 0)
```

---

### M1 — Episodic memory store (2026-06-25)

**Gap.**
Episode nodes were written to `memory/journal/<session>.og` at session close with a
near-useless 3×80-char summary derived from the last 3 history messages. The
`interaction_log` data — which captures actual `user_input`, `agent_output`, and
`tool_calls` per turn — was never used for recall. There was no ChromaDB episodic
collection, so past-session content was invisible to semantic recall; each session
started blind to everything that happened in previous sessions.

Additionally, `search_delegations` did not apply `_redact_results()` to its output,
breaking the invariant that all recall paths redact secrets (MED-009).

**Design (implemented exactly).**

1. **New ChromaDB collection** `episodic_memory` added to `_COLLECTION_SPECS` with lazy
   init (same pattern as `delegation_log`, `user_profile`, etc.). Existing `_FakeCollection`
   tests that bypass `__init__` are unaffected because they only touch collections they
   explicitly declare.

2. **Capture** — `build_episode_summary(interactions, *, max_chars=1500)` in `memory.py`:
   a pure, deterministic, zero-cost function (no LLM call). Produces a header line + a
   bulleted list of per-turn `user_input` (truncated to 120 chars) → `agent_output` head
   → tool names. Length-capped at `max_chars` with a graceful truncation note. Returns `""`
   for empty lists (caller skips the vault write). The vault upsert is done in the
   orchestrator `shutdown()` block alongside the existing `.og` episode write, NOT inside
   `MemoryManager.write_episode`, so `write_episode`'s existing tests stay green without
   modification.

3. **Recall** — `search_episodic(query, top_k)` on `MemoryVault`: delegates to
   `_query_collection("episodic_collection", ...)` and applies `_redact_results()`.
   Returns the same dict shape as `semantic_search` so the orchestrator can merge uniformly.
   Guarded: `top_k <= 0` returns `[]` immediately.

4. **Orchestrator wiring:**
   - *Turn start*: after existing semantic recall, calls `vault.search_episodic(user_input,
     top_k=self._episodic_top_k)` and merges into `recalled` (deduped by ID). Wrapped in
     try/except — never raises.
   - *Shutdown*: fetches `session_store.get_interactions(session_id, limit=50)`, reverses
     to chronological order, calls `build_episode_summary`, calls `vault.upsert_episode`
     with deterministic `session_id`-derived ID (upsert semantics, no duplicates). Wrapped
     in try/except — never breaks shutdown.
   - `_episodic_top_k` default 3, set in `__init__`, overridden by `boot_agent` from
     `_memory_settings.episodic_top_k`.

5. **Part D fix** — `search_delegations` now calls `_redact_results()` on its return path,
   matching `semantic_search` and `search_user_profile`.

**Settings** (`src/hachi/core/settings.py` — strict-gated):
`episodic_top_k: int = 3` added to `MemorySettings`. Set to 0 to disable episodic recall.

**Invariants preserved.**
- `_redact_results` applied on ALL recall outputs: episodic + delegations (Part D fix).
- `_assert_open()` + `_vault_lock` on every new collection-access method.
- Lazy collection init — `episodic_collection` is None until first access; `_FakeCollection`
  tests that set `_collections` manually to 5 keys are unaffected (they never touch
  `episodic_collection`).
- Episodic capture and recall both wrapped in try/except — never break a turn or shutdown.
- `get_recent_facts` and existing session_store.py unchanged.

**Files changed.**
| File | Change |
|------|--------|
| `src/hachi/core/memory_vault.py` | Add `episodic_memory` to `_COLLECTION_SPECS`; add `episodic_collection` lazy property; add `upsert_episode()` + `search_episodic()`; fix `search_delegations` to call `_redact_results()` |
| `src/hachi/core/memory.py` | Add `build_episode_summary()` pure function (module level) |
| `src/hachi/core/settings.py` | Add `episodic_top_k: int = 3` to `MemorySettings` |
| `src/hachi/gateway/orchestrator.py` | Add `self._episodic_top_k = 3` in `__init__`; wire episodic recall in turn start; wire episodic capture in `shutdown()`; set `session._episodic_top_k = _memory_settings.episodic_top_k` in `boot_agent` |
| `tests/test_episodic_memory.py` | New: 19 tests covering `build_episode_summary`, round-trip upsert/search, redaction, top_k=0 guard, idempotency, search_delegations redaction (Part D) |

**Capture-cadence limitation.** Episodes are captured exactly once per session, at shutdown.
For long-lived sessions (multi-hour conversations), the episode reflects the full
interaction_log at close time (up to 50 rows), which is correct. However, if a session
crashes without a clean shutdown, no episode is captured for that session — the `.og`
journal write has the same gap. A periodic in-session summarizer (triggered after every N
turns or on a time interval) is a documented follow-up.

**Verification.**
```
uv run pytest tests/test_episodic_memory.py tests/test_memory_fixes.py tests/test_memory_vault_close.py tests/test_memory_provider.py -q
# 61 passed in 8.92s

uv run ruff check src/hachi/core/memory_vault.py src/hachi/core/memory.py src/hachi/core/settings.py src/hachi/gateway/orchestrator.py tests/test_episodic_memory.py
# All checks passed!

uv run mypy src/hachi/core/memory_vault.py src/hachi/core/settings.py --ignore-missing-imports
# Success: no issues found in 2 source files

uv run python -m mypy --config-file mypy-strict-gate.ini
# Success: no issues found in 36 source files

uv run mypy src/hachi/gateway/orchestrator.py --ignore-missing-imports
# Found 34 errors (all pre-existing; zero new errors from M1)
```

---

## Memory decay (M2) — 2026-06-25

**Branch:** `reassess`

### Found / motivation

Semantic recall returns facts ranked purely by cosine distance (relevance). For a personal
agent vault that accumulates facts over months, this means a stale fact stored 6 months ago
can outrank a fresh fact stored yesterday if their embedding similarity differs by even a
small amount. This misranks recall whenever the user's context has evolved (new project,
new preference, new role). The fix must never break recall — it must only *re-order* an
already-quality-gated candidate set.

### Decided / changed

**Formula (multiplicative recency decay):** `score = distance / recency_decay` where
`recency_decay = 0.5 ** (age_days / half_life_days)`. Score is in the same direction as
distance (lower = better). At age 0 → score == distance (no penalty). At exactly
`half_life_days` → score == 2 × distance (the fact competes as if twice as far away).
The formula is parameter-free beyond the half-life value; it has no intercept, no
training data, and no risk of divergence.

**Off by default:** `decay_half_life_days: float | None = None` in `MemorySettings`.
When `None` or `<= 0`, `_query_collection` is byte-for-byte identical to pre-M2.

**Never resurrects filtered facts:** the `distance > effective_threshold` gate runs on
the RAW cosine distance and is completely unchanged. Decay only re-orders the survivors;
it cannot make a beyond-threshold candidate pass the gate.

**Over-fetch for larger reordering pool:** when decay is active, ChromaDB is queried for
`min(top_k × 4, 50)` candidates (constants `_DECAY_OVERFETCH=4`, `_DECAY_OVERFETCH_CAP=50`).
After the distance gate and decay sort, the result is sliced to `top_k`. This ensures
the freshest *relevant* fact can bubble up even if it wasn't in the top-k by raw distance.

**Never on user_profile:** `search_user_profile` passes `apply_decay=False`. Identity and
preference facts (name, role, timezone, habits) are timeless — a user's name stored two
years ago is not "stale". Only `semantic_search` (core_memory) and `search_episodic`
(episode summaries) get decay.

**`get_recent_facts` unaffected:** it uses `collection.get()` not `collection.query()`,
so it is a completely separate code path. Decay is not applied and contract C-RECENT
(unbiased recency access) is unchanged.

**`search_delegations` unaffected:** it has its own custom query path with where-clause
filtering and is not routed through `_query_collection`.

**Safety wrapping:** the decay sort is wrapped in `try/except Exception`; any bug in
`_decay_score` or the sort falls back to the undecayed relevance order and logs at DEBUG.
`_decay_score` itself is a total, exception-free pure function — unparseable/missing/empty
timestamps return `distance` unchanged; naive timestamps are assumed UTC (no tz-error);
extreme ages (underflow of `0.5**N`) are guarded by `max(recency_decay, 1e-9)`.

**Strict mypy gate:** `memory_provider.py` and `settings.py` are in `mypy-strict-gate.ini`.
Both remain 0 errors after M2. `memory_vault.py` is advisory — also clean.

### Files changed

| File | Change |
|------|--------|
| `src/hachi/core/memory_vault.py` | Add `_DECAY_OVERFETCH`, `_DECAY_OVERFETCH_CAP` constants; add `_decay_score()` module-level pure function; add `decay_half_life_days` param to `__init__`; add `apply_decay` param to `_query_collection` with over-fetch and try/except-wrapped re-rank; add `apply_decay=False` to `search_user_profile` call |
| `src/hachi/core/settings.py` | Add `decay_half_life_days: float | None = None` to `MemorySettings` |
| `src/hachi/core/memory_provider.py` | Add `decay_half_life_days: float | None = None` kwarg to `ChromaMemoryProvider.initialize()`; thread it into `_kwargs` |
| `src/hachi/gateway/orchestrator.py` | Pass `decay_half_life_days=_memory_settings.decay_half_life_days` in the `ChromaMemoryProvider.initialize()` call in `boot_agent` |
| `tests/test_memory_decay.py` | New: 20 tests covering `_decay_score` unit (age-0, half-life, unparseable, empty, Unknown-Date, distance-0, extreme-age, monotonicity, naive-ts, future-ts, half-life-0-guard), re-rank order flip via `_query_collection` and `semantic_search`, over-fetch+truncate, user_profile not-decayed, distance-gate-precedes-decay, default-off parity, C-RECENT contract |

**Config key to enable:** `memory.decay_half_life_days = 30.0` in `settings.toml`.
A value of 30 days means a one-month-old fact competes as if 2× more distant; a
three-month-old fact competes as if 8× more distant. Leave unset (the default) for
pure relevance order.

**Verification.**
```
python -m pytest tests/test_memory_decay.py tests/test_episodic_memory.py tests/test_memory_fixes.py tests/test_memory_vault_close.py tests/test_memory_reliability.py tests/test_memory_provider.py -q
# 100 passed

python -m mypy --config-file mypy-strict-gate.ini
# Success: no issues found in 36 source files

python -m ruff check src/hachi/core/memory_vault.py src/hachi/core/memory_provider.py src/hachi/core/settings.py src/hachi/gateway/orchestrator.py tests/test_memory_decay.py
# All checks passed!
```

---

## Container sandbox backend — S1 (2026-06-25)

**Found.**
`src/hachi/core/sandbox.py` contained a single concrete class (`SandboxExecutor`) with no
abstraction layer, making it impossible to slot in a hardened execution backend without
rewriting callers. `security-audit` emitted an unconditional `medium` finding
`sandbox.process_backend` regardless of the runtime configuration — even if an operator had
already deployed a hardened alternative. The module docstring marked container isolation as
"TODO".

**Decided/Changed.**

### `SandboxBackend` ABC  
Added `SandboxBackend(ABC)` with abstract `execute()`. Both concrete implementations
subclass it, exposing typed `name: str` and `is_hardened: bool` class attributes so
callers can branch without isinstance checks.

### Process backend (back-compat)
`SandboxExecutor` now subclasses `SandboxBackend`; it sets `name = "process"`,
`is_hardened = False`. **All existing methods and their signatures are byte-for-byte
preserved** (`__init__`, `_resolve_uv`, `_validate_dependencies`, `_generate_env_hash`,
`execute`). The body of `_validate_dependencies` delegates to the new module-level
`validate_dependencies()` function (so the container backend reuses the same logic);
the method itself is kept so `test_phase7_integrations_mcp_sandbox_deployment.py` can
still call `SandboxExecutor._validate_dependencies(executor)` directly.

### Container backend (`ContainerSandboxExecutor`)  
`name = "container"`, `is_hardened = True`. All config read from environment variables
with safe defaults:

| Env var | Default | Meaning |
|---|---|---|
| `HACHI_SANDBOX_IMAGE` | `python:3.12-slim` | Docker image |
| `HACHI_SANDBOX_MEMORY` | `512m` | `--memory` + `--memory-swap` (no swap) |
| `HACHI_SANDBOX_PIDS` | `256` | `--pids-limit` |
| `HACHI_SANDBOX_CPUS` | `1.0` | `--cpus` |
| `HACHI_SANDBOX_NETWORK` | `none` | `--network` |
| `HACHI_SANDBOX_USER` | `65534:65534` | `--user` (nobody:nogroup) |

Every `docker run` invocation is built as a list (never `shell=True`) and includes:
`--rm`, `--network none`, `--read-only`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--user 65534:65534`,
`--memory 512m`, `--memory-swap 512m`, `--pids-limit 256`, `--cpus 1.0`,
`--tmpfs /tmp:rw,size=64m`, `-v <exec_dir>:/work:ro`, `-w /work`.

Deps + `--network none` → immediate `SandboxResult(success=False, exit_code=-1)` with
an explanatory message (suggest `HACHI_SANDBOX_NETWORK=bridge` or baking deps into the
image). Timeout → best-effort `docker kill` then `exit_code=124`.

### Fail-fast factory  
`create_sandbox_backend(backend=None, *, sandbox_root=None)` resolves the backend from
the `HACHI_SANDBOX_BACKEND` env var (default `"process"`). When `"container"` is
selected but Docker is absent: raises `OSError` immediately — **never silently downgrades
to the process backend**, as that would be a security surprise.

### Audit-honesty helper  
`sandbox_audit_finding(backend, docker_available) -> tuple | None`:
- `("container", True)` → `None` (hardened backend active, no finding emitted)  
- `("container", False)` → `("high", "sandbox.container_unavailable", …)`  
- Any other value → `("medium", "sandbox.process_backend", …)` (existing wording)  

`cli/main.py::security_audit` replaced the unconditional `add_finding(medium, sandbox.process_backend, …)`
with a call to this helper — the finding disappears when a working container backend is
configured, and escalates to HIGH when container is selected but Docker is missing.

### `sandbox_tools.py` update  
Lazy `_executor` list now typed as `list[SandboxBackend]`; initialises via
`create_sandbox_backend()`. Registration-time CRITICAL log is now conditional:
process backend → CRITICAL; container backend → WARNING. Per-invocation log matches the
active backend's `is_hardened` attribute.

### Tests  
`tests/test_sandbox_backend.py` — 37 new unit tests, no live Docker required:
factory routing (default/process/container/missing-docker/unknown/env-var), container
command flag assertions (`--rm`, `--network`, `--read-only`, `--cap-drop ALL`,
`--security-opt no-new-privileges`, `--user`, `--memory`, `--pids-limit`, `--cpus`,
`--tmpfs`, image, `python`), stdout/exit-code flow, timeout → 124,
deps+network=none short-circuits without calling docker-run,
`validate_dependencies` cases, `sandbox_audit_finding` matrix (8 cases),
`container_backend_available`, backward-compat `_validate_dependencies` method.

**Strict mypy gate:** `sandbox.py` is in `mypy-strict-gate.ini`; 0 errors after S1.
**Ruff:** all checks passed on all four changed files.

**Why.**  
Operators who deploy into Docker-capable environments now have a production-grade,
kernel-enforced isolation path without changing any call sites. The process backend
remains the default (zero behaviour change for existing deployments). The audit finding
is now an honest reflection of the runtime posture rather than a standing false-alarm.
The fail-fast factory prevents silent security regressions where a misconfigured
container backend would transparently fall back to the weaker process backend.

**Note on live container execution.** Unit tests mock `subprocess.run` and `shutil.which`.
A live end-to-end run requires Docker and should be exercised via an operator opt-in job
similar to the existing `docker-smoke` CI job (a follow-up, not part of S1 unit scope).

### Files changed

| File | Change |
|---|---|
| `src/hachi/core/sandbox.py` | `SandboxBackend` ABC; module-level `validate_dependencies()`; `SandboxExecutor` subclasses `SandboxBackend` (back-compat preserved); new `ContainerSandboxExecutor`; `container_backend_available()`; `create_sandbox_backend()` factory; `sandbox_audit_finding()` helper; updated module docstring |
| `src/hachi/tools/sandbox_tools.py` | `_executor` typed as `list[SandboxBackend]`; lazy init via `create_sandbox_backend()`; registration-time log conditional on backend; per-invocation log conditional on `is_hardened` |
| `src/hachi/cli/main.py` | Replace unconditional `add_finding(medium, sandbox.process_backend)` with `sandbox_audit_finding()` + conditional `add_finding(*_sb_finding)` |
| `tests/test_sandbox_backend.py` | New: 37 unit tests (factory, container command flags, timeout, deps+network, audit helper, availability probe, backward-compat method) |
| `DECISIONS.md` | This entry |

**Verification.**
```
python -m pytest tests/test_sandbox_backend.py tests/test_g4_security_depth.py tests/test_phase7_integrations_mcp_sandbox_deployment.py -p no:randomly -q
# 60 passed

python -m mypy --config-file mypy-strict-gate.ini
# Success: no issues found in 36 source files

python -m ruff check src/hachi/core/sandbox.py src/hachi/tools/sandbox_tools.py src/hachi/cli/main.py tests/test_sandbox_backend.py
# All checks passed!
```

---

## FLAKE — full-suite hermeticity + determinism (2026-06-25, commit `afe8138`)

Re-diagnosed from scratch on `reassess`; the `flake-wip` branch's fixes were superseded (it never
cracked layer 3 and its layer-4 fix was wrong). Full suite: **3867 passed / 21 skipped / 0 failed**,
deterministic, 4:40 (was a ~40-min crawl while leaked keys drove real LLM calls).

### Layer 1 — import-time `.env` autoload (secret leak + nondeterminism)
**Found.** `cli/main.py::_load_dotenv_into_environ()` runs at import time, merging `<cwd>/.env` +
config-dir `.env` into `os.environ`. During pytest collection this pulls the dev's real
`ANTHROPIC_API_KEY` etc. into the process, which (a) flips import-time `@skipif(not getenv(...))`
guards so live-gateway tests RUN — and `test_cockpit_chat_live` then makes **billed** LLM calls every
suite run — and (b) leaks secrets into the test process.
**Changed.** Guard the merge behind `HACHI_DISABLE_DOTENV_AUTOLOAD`; `tests/conftest.py` sets it
(`setdefault`, before any hachi import). Production default unchanged (autoload on). New
`tests/test_dotenv_hermeticity.py` regression-guards the flag + the conftest default.

### Layer 2 — `os.environ` leak past monkeypatch
**Found.** `_apply_tokoboros_shim()` writes `HACHI_*` straight into `os.environ`; a test that triggers
it (`test_shim_covers_all_renames`) leaks those keys because monkeypatch only undoes vars it set.
Order-dependent failures in later email/SMTP tests.
**Changed.** Autouse diff-based `_restore_os_environ` fixture in conftest — snapshot `dict(os.environ)`
before, restore after (remove added keys, restore changed/deleted). Diff-based (not `clear()`) so
concurrent in-process-gateway threads never observe an empty env mid-test.

### Layer 3 — chromadb native-extension "poison" (the real unsolved layer) **[ADR]**
**Found.** `patch.dict(sys.modules, {...})` snapshots sys.modules on enter and restores on exit,
**dropping any module first-imported inside the block**. `test_file_platform`'s
`test_pdf_without_pypdf_returns_none_from_find_extractor` runs `_build_extractor_chain()` inside a
`patch.dict(sys.modules, {"pypdf": None})` block; that chain lazily first-imports `chromadb`. On exit,
patch.dict wipes all `chromadb.*` entries it added — including the **PyO3 native submodule**. A native
extension *cannot be re-initialized once unloaded*: CPython raises `ImportError: cannot load module more
than once per process`. Every later `import chromadb` in the process then fails, and the guarded
`except ImportError` in `memory_vault` / `enable_embedding_rank` swallows it as "chromadb not installed"
→ vault/embedding tests silently fail. `flake-wip`'s `_restore_chromadb_modules` fixture *deleted real
chromadb submodules on teardown*, so it **caused** this failure rather than fixing it.
**Decided.** (a) Warm `import chromadb` + `import chromadb.config` once at `conftest.py` import, so
chromadb is present in *every* `patch.dict` enter-snapshot and survives the restore. (b) Fix the
offending `test_search_without_chromadb_returns_error` to use a `None`-sentinel restore — never install
a `MagicMock` stub (the original installed one when chromadb was absent, which poisoned
`from chromadb.config import Settings` with "chromadb is not a package"). (c) Do NOT add a
chromadb-restoring fixture — removing chromadb from sys.modules is the hazard, not the cure.
**Why.** Warming is a one-line, order-independent neutralizer for the whole class of
patch.dict-wipes-native-import bugs; it costs one import already paid by most runs.

### Layer 4 — "cockpit flakiness" is a boot timeout, not a key issue
**Found.** `test_cockpit_gaps::TestMemoryCRUD` (the S1 gate's 1 failure) fails at `_create_session` →
`POST /sessions transport error: timed out`, NOT at any memory assertion. 12/13 tests in the class pass
with **no** API key — memory CRUD needs no LLM. `POST /sessions` does heavy synchronous skill-engine +
ChromaDB vault init that exceeds `GatewayClient.DEFAULT_TIMEOUT = 15s` on a cold Windows process
(uncached imports) or under full-suite load (Nth PersistentClient).
**Changed.** `GatewayClient.__init__` gains a `timeout` arg; absent that, it reads
`HACHI_GATEWAY_CLIENT_TIMEOUT` (else the 15s default). conftest grants 90s for the test process.
Production default unchanged. Rejected `flake-wip`'s `@skipif(not ANTHROPIC_API_KEY)` on the whole
class — empirically wrong (would skip 12 passing keyless tests) and would hide real regressions.

### Files changed
`src/hachi/cli/main.py` (dotenv guard) · `src/hachi/client/gateway.py` (configurable timeout) ·
`tests/conftest.py` (flags + chromadb warm + env-restore fixture; removed harmful chromadb fixture) ·
`tests/test_file_platform.py` (sentinel restore) · `tests/test_dotenv_hermeticity.py` (new).

---

## Feature tier — EventBus / knowledge-graph / query-cache (2026-06-25)

Three user-greenlit features, each "activate dormant scaffolding" not greenfield.
Orchestrate-verify-gate via Sonnet 4.6 subagents; Opus designed, verified, committed.

### EventBus reactivity (`73199b7`) **[ADR]**
**Found.** A complete `EventBus` + a byte-identical funnel existed behind default-off
`[events] bus_funnel`; the reactive architecture (Initiative C) was dormant. Reactive
`file.uploaded→auto_extract` was double-gated (needed BOTH `bus_funnel` AND
`[jobs] durable_handlers`).
**Decided.** Default `bus_funnel` True (byte-identical proven by `test_slice22_wiring`).
DECOUPLE the reactive subscription from `durable_handlers`: subscribe whenever the bus
is on — async/durable when the JobRegistry is on, else sync-inline (file.uploaded is
emitted only by FilePipeline.ingest / POST /files, never the turn hot path, so inline is
safe and cannot orphan a job). Wire ObservabilitySink (no-op when tracing off). Promote
leaked literals to the existing typed constants (unifies the budget event name with the
daily-cap path). Did NOT default `durable_handlers` on (bigger subsystem; out of scope).
**Why.** Completes the migration to the bus as the event path with the full suite as the
byte-identical safety net, without forcing durable execution semantics on every user.

### Knowledge-graph memory (`0518255`)
**Found.** `memory_graph.py` (≤2-hop typed-edge expansion + supersession) was complete but
had NO caller. Crucially, the edge data already exists and is fresh: MemoryManager's typed
extraction writes nodes WITH `->[:key=value]` edges to `.og` files via MemoryWriter on the
normal write path — so graph recall reads them with ZERO new billed calls. (The vault→.og
*exporter* writes no edges, a red herring; the *typed writer* does.)
**Decided.** New `core/graph_recall.py::build_graph_recall_section` (pure helper), wired in
`orchestrator._chat_impl_inner` step 3b to APPEND a `[Related memory (graph)]` section to
the semantic recall block — additive (never replaces the floor), `[memory] graph_recall`
flag (default True), broad try/except (a recall enhancement must never break a turn),
degrades to "" without edges. Perf: process-LRU keyed `(memory_dir, max .og mtime_ns)` so
the rglob+parse runs only on actual file change — not every turn (stat-only probe).
**Why.** Structured graph traversal (project→tasks, causal chains, supersession) on top of
flat semantic recall, free and safe, gated by the full suite.

### Frontend query-cache (`1475a52`)
**Found.** Route loaders fired once per path per session (binary `_loaded` Set in
`useRouteLoaders`) and never refetched — data went stale until a full reload.
**Decided.** New `lib/data/cache.ts`: `loadCached(key, loader, {ttlMs, force})` with
stale-while-revalidate (fresh→no-op; stale→deduped loader via existing `dedupe.ts`; stamp
only on success so failures retry) + `invalidate`/`invalidateAll` + `DEFAULT_TTL_MS=30s` +
a `_setNow` test seam. Rewired `useRouteLoaders` to domain-keyed `loadCached` (approvals
10s, spend 60s); invalidate after memory/approval mutations. Frozen foundation
(client/sse/live/store) untouched; no gateway routes → OpenAPI contract unchanged.
**Why.** Revisits now refresh on a TTL while the store keeps showing prior data (SWR),
without adopting a heavy query lib inconsistent with the custom data layer.

### Gate results
EventBus 3887 pass / KG 3907 pass / query-cache vitest 94 pass — each 0 fail, ruff +
strict-mypy (36) clean, frontend typecheck + build green. All pushed to `reassess`.

---

## Regression guardrails — Phase 1 + Memory (2026-06-27) **[ADR]**

Adopted the "guardrails" plan's mechanical floor + memory layer to stop AI-introduced
regressions/drift. Phase 1 (the Gate + the Locks) + Memory; the Rails (Phase 2) and
role-agents (Phase 4) are deliberately deferred. Single session, no subagents.

**Found.** Hachi's checks existed only as 8 separate CI jobs — no single local gate, and nothing
*mechanically* stopped a bad diff landing. ruff + strict-mypy-gate were already green; full-tree
mypy and `ruff format` were NOT (113 files would reformat).

**Decided / built.**
- **The Gate — `scripts/preflight.py`** (`uv run python scripts/preflight.py [--quick]`): one
  command mirroring CI — ruff, strict-mypy-gate, skill-lint, eval, full pytest, frontend
  (typecheck/vitest/build/openapi-contract). Cross-platform Python runner (no Makefile).
  - **No global `ruff format --check` step** — the repo is deliberately not fully formatted (113
    files; a repo-wide reflow is forbidden, Rule 3). The auto-format hook keeps *touched* files clean.
  - **pytest runs sequentially, NOT `-n auto`** — parallel workers starve wall-clock timing tests
    (`test_two_sessions_run_concurrently`, notifier non-blocking) → flaky gate. Matches CI and the
    plan's "run tests sequentially to kill time-based flakiness."
  - **security-audit is advisory** (mirrors CI continue-on-error on main; 2 pre-existing HIGH
    config-posture findings remain — not regressions).
- **The Locks — `.claude/settings.json` + `.claude/hooks/*.py`** (stdlib Python, exec-form
  invocation → portable across PowerShell / Git Bash / Linux):
  - `bash_guard.py` (PreToolUse `Bash|PowerShell`): push-lock on main/master via a one-shot
    `.claude/.push-approved` sentinel; secret-scan on commits (high-confidence patterns + staged
    `.env`); anti-forge. **Matcher includes PowerShell** — `Bash`-only would let the agent bypass
    the push-lock on Windows (the primary shell).
  - `stop_guard.py` (Stop): blocks finishing while `ruff check` is red (fast); the *full* suite is
    preflight's job, not every Stop. Guards `stop_hook_active`.
  - `auto_format.py` (PostToolUse Write|Edit|MultiEdit): `ruff format`s the touched `.py`.
  - `session_start.py` (SessionStart): injects the gate command, branch, and the top
    `docs/bug-bank.md` **Avoid:** rules so a fresh agent starts warm.
- **Memory — `docs/bug-bank.md`** (per-bug autopsy + locking test), seeded BB-1..BB-9 from the old
  CLAUDE.md gotchas + history. The SessionStart hook injects the **Avoid:** lines each session.
- **Lean CLAUDE.md** — slimmed from 257 lines to the inviolable rules + pointers; detail
  *relocated* (gotchas→bug-bank, entry-points/frontend-contract→ARCHITECTURE.md, conventions→
  CONTRIBUTING.md). Nothing dropped.

**Verified.** All 5 hooks unit-checked live this session (15/15 driver checks: push-lock blocks
main + consumes the sentinel; secret-scan blocks AWS keys / staged `.env` and does NOT self-trip
on the guardrail files; stop-guard, auto-format, session-start). preflight green on every blocking
step (ruff / mypy-gate / skill-lint / eval; full pytest 3941 pass, and the 2 timing tests pass
once sequential). Caught + fixed en route: the PowerShell matcher hole; preflight's cp1252 console
crash; and **BB-2 was a stale absolute** — `.env` IS autoloaded at the CLI edge, gated by
`HACHI_DISABLE_DOTENV_AUTOLOAD` and locked by `test_dotenv_hermeticity.py` — corrected in the bug bank.

**Deferred (the plan's phasing).** Phase 2 Rails (vulture dead-code, deptry unused-deps, jscpd
duplication, ruff `PLR0913` max-params, import-linter boundaries — add to preflight advisory→
blocking once baselines are clean); Phase 3 formal `docs/adr/` + Mermaid/C4 diagrams; Phase 4
role-separated subagents + adversarial verification. Uncommitted on `main` at time of writing.

## Regression guardrails — Phase 2: the Rails (2026-06-27) **[ADR]**

Added the mechanical guards against the *architectural-drift* and *code-rot* pains, the layer
Phase 1 deferred. Three new dev-only tools (`import-linter`, `deptry`, `vulture`) in the `dev`
extra — never imported by the product — plus ruff complexity rules. Wired into both
`scripts/preflight.py` and CI's `lint` job so the gate and CI stay in lockstep. No `src` changes.

**Found (the real import graph, measured — not assumed).** The engine layers are *not* pure: `core`
and `tools` reach up into `gateway`/`cli` in 6 concrete seams (`core.onboarding→gateway.workspace`
top-level; `core.cost`/`core.runtime.job_handlers`/`core.runtime.resume`/`tools.config_tools`→
gateway lazily; `core.runtime.resume→cli.main`). `og_engine` *is* already pure. A naïve "domain must
not import gateway" rule would therefore be red on day one — the wrong move. Baselines: deptry 34
raw findings (all extras/dev/first-party noise + a few intentional), ruff complexity 178 at strict
defaults, vulture 8 at confidence ≥80.

**Decided / built.**
- **Architecture rail — `import-linter` (BLOCKING, green).** Three `forbidden` contracts in
  `pyproject [tool.importlinter]`: (1) `og_engine` is pure — depends on nothing but `core`; (2) the
  engine must not import the UI edges (`cli`, `tui`); (3) the engine must not import `gateway`. The 6
  pre-existing seams are frozen as commented `ignore_imports` — *documented debt to burn down, not a
  licence to add more*. The gateway contract sets `allow_indirect_imports = true` because the one
  indirect path (`core→cli.main→gateway.workspace`) is the cli seam already frozen by contract (2),
  and cli importing the gateway is correct edge→service layering. **Proven to bite:** a temporary
  direct `core.approvals→gateway.workspace` import flipped the contract to BROKEN; reverted.
  `unmatched_ignore_imports_alerting` stays at its ERROR default, so a stale ignore (a seam later
  removed) fails until deleted — the ratchet self-cleans.
- **Dependency rail — `deptry` (ADVISORY).** `[tool.deptry]` models Hachi's extras truthfully:
  `known_first_party=["benchmarks"]`, `optional_dependencies_dev_groups=["dev","security"]`, a
  `package_module_name_map` for distributions whose import name differs (docx/pptx/googleapiclient…),
  and `per_rule_ignores` freezing only **confirmed** false-positives (tzdata data-pkg; tavily-python
  via `importlib.import_module`; python-multipart via Starlette). This cut 34→**4 genuine findings**:
  `slack-sdk`, `notion-client`, `google-auth`, `google-api-python-client` are declared extras whose
  SDKs are imported **nowhere** in the repo (the integrations use httpx). Left UNfrozen on purpose —
  surfacing a real signal, not suppressing it; pending a call to drop the extras or keep them as
  intentional optional installs (then freeze + make deptry blocking).
- **Dead-code rail — `vulture` (ADVISORY).** `[tool.vulture]` at `min_confidence=80` (skips the noisy
  60% method/attribute guesses that false-positive on framework entry points) + decorator/name
  ignores. `exc_type/exc_val/exc_tb` ignored (protocol-required `__exit__` params). 6 findings remain
  for a human look — incl. an **"unsatisfiable ternary" at `og_engine/engine.py:638`** (possible
  latent bug; flagged, not silently "fixed" — a real fix needs a failing test first, per the
  regression law).
- **Complexity rail — ruff `PLR0911/0912/0913/0915` (ADVISORY).** Thresholds in
  `[tool.ruff.lint.pylint]` set *above* ruff's strict defaults (max-args 8, branches 15, returns 8,
  statements 60) so only egregious outliers count: 84 vs 178. Deliberately **NOT** added to the
  global `select` — the blocking `ruff check` stays green; preflight runs them as a separate
  `--statistics` step.

**Why advisory-first.** import-linter is green so it blocks today. The other three have non-zero
pre-existing baselines; making them blocking now would turn the gate red forever — the exact failure
mode the plan warns against. They are surfaced every run (like security-audit) and ratchet to
blocking once each baseline reaches zero.

**Verified.** `preflight --quick --no-frontend` green: 5 blocking pass (ruff, mypy-gate, skill-lint,
**import-linter**, eval), 4 advisory warn (security, deptry, vulture, complexity), 0 blocking fail.
Negative test confirmed import-linter detects a fresh cross-layer import. Full `pytest` re-run to
confirm no regression from the pyproject/tooling changes (no `src` touched).

**Deferred.** `jscpd` duplication (Node dep — the one cross-stack add; flagged as optional, not
built). Ratchet deptry/vulture/complexity advisory→blocking as baselines clear. Decide the 4 unused
SDK extras. Investigate the `og_engine/engine.py:638` ternary. Phase 3 (docs/adr + diagrams) /
Phase 4 (role subagents) still deferred. Uncommitted on `main` at time of writing.

## Regression guardrails — Phases 3 & 4: legibility + role subagents (2026-06-27) **[ADR]**

Closed out the guardrails plan's last two phases. No `src` changes — docs, a stdlib docs-lint, and
Claude Code subagent definitions. Phase 3 makes the architecture and its decisions *legible and
self-checking*; Phase 4 encodes the three disciplines a hook can't run as reusable subagents.

**Phase 3 — ADR convention + diagrams + a tiny enforcement.**
- **Two-tier ADR convention, reconciled.** Decisions already lived in two places: the flat
  `DECISIONS.md` log (this file) and numbered MADR ADRs under `docs/architecture/adr/`
  (`0001..0005`, from the architecture engagement). Rather than add a third home, `adr/README.md`
  now states the rule: **`DECISIONS.md` is the default log; a numbered ADR is for a major decision
  that needs alternatives analysis + a long-lived reference, linked from `DECISIONS.md`.** Added
  `adr/0000-template.md` (MADR shape matching the existing five) and an **Index** table.
- **The diagram is the contract.** Converted the Phase-2 ASCII layer block in `ARCHITECTURE.md` to
  a GitHub-rendered **Mermaid** diagram: the three layers (edges → service → engine), the *allowed*
  downward deps, and the **forbidden** upward edges (styled red) that `import-linter` blocks. The
  picture now matches the enforced contract instead of being a stale convention beside it.
- **adr-lint (`scripts/check_adrs.py`, ADVISORY).** A small stdlib check: every `NNNN-*.md` ADR is
  indexed in `adr/README.md` (no orphans), filenames are `NNNN-kebab.md` with unique numbers, and
  each ADR has a `Status:` line + Context/Decision/Consequences. Baseline is **clean** (5/5 pass),
  so it can ratchet to blocking — kept advisory for one cycle, consistent with the Phase-2 rails.
  Wired into `preflight` and CI's `lint` job. A docs convention with no check rots; this is the
  check. The ADR `Status:` lines are left as the engagement wrote them ("Proposed"); the index
  carries a "statuses may lag — `DECISIONS.md` is the outcome of record" caveat, because rewriting
  them is a deliberate edit, not a drive-by.

**Phase 4 — role subagents (`.claude/agents/`).** Three committed Claude Code subagents encoding
the rules a one-shot hook can't (the hooks *block*; these *do the work* the right way):
- **`regression-guard`** (sonnet, can edit) — the regression law as a ritual: failing test FIRST →
  minimal code fix → `docs/bug-bank.md` entry; full *sequential* pytest; the BB-1 Windows fallback.
- **`scope-sentinel`** (inherit, read-only) — reviews a working diff against the contract: scope
  creep, weakened/missing tests, new deps, layering violations, the security guardrails, tokoboros.
- **`gate-keeper`** (sonnet, read-only) — runs `scripts/preflight.py` and reports the REAL result
  (exact pytest counts; never an assumed green; never pushes; never forges the push sentinel).
- **Self-containment is the load-bearing constraint:** a subagent's body is its *entire* system
  prompt — it does NOT inherit CLAUDE.md, conversation history, or the main prompt. So each file
  **restates** its rules; that redundancy with CLAUDE.md is deliberate and must be maintained when a
  rule changes (`.claude/agents/README.md` documents this).

**Why this completes the plan.** Phase 1 = the gate + the locks + memory; Phase 2 = the static
rails; Phase 3 = the map/decisions made legible and self-checking; Phase 4 = the workflow roles.
Every pain (regressions / drift / bugs-returning / same-bug-thrice) now has a *mechanical* counter,
not just advice in a doc the model can rationalise away.

**Verified.** `preflight --quick` green: blocking checks pass (incl. import-linter), advisory rails
warn (now incl. adr-lint reporting OK). `check_adrs.py` exits 0 over the 5 existing ADRs + new
index. No `src` touched, so the full pytest suite (last full run: 3943 passed / 21 skipped / 0
failed) is unaffected.

**Deferred (unchanged).** `jscpd` duplication rail (the one Node-dep add — still flagged optional;
the user is weighing it). Ratchet deptry/vulture/complexity/adr-lint advisory→blocking as baselines
hold. Decide the 4 unused SDK extras. Investigate the `og_engine/engine.py:638` ternary. Uncommitted
on `main` at time of writing.

## B10 — Episodic recall offloaded from inline turn path (`perf/streaming-optimizations`, 2026-06-28)

**Context.** Prior to this change `_chat_impl_inner` ran two synchronous vault calls on every turn:
`semantic_search` (already in the background prefetch) **and** `search_episodic` (always inline,
never prefetched). The episodic call added measurable latency to the turn-start hot path, especially
on slower machines where ChromaDB I/O isn't cached.

**Decision.** Move `search_episodic` into `_run_prefetch_job` alongside `semantic_search`.
Both calls now run in the background job queue between turns (turns 2+). Turn 1 keeps both calls
inline because no prefetch result exists yet — this is the correct fallback and is tested.

**Tradeoff — previous-query staleness.** On turns 2+, episodic recall uses the *previous* turn's
query (enqueued at the end of turn N, consumed at the start of turn N+1). This means the episodic
context in turn N+1 is semantically matched to turn N's question, not turn N+1's. In practice
this is acceptable because:
- Episodic results are long-term memory (prior sessions), not turn-sensitive context.
- The 1-turn lag is almost always invisible; topics rarely pivot between consecutive turns.
- Turn 1 is always exact (inline fallback).

**What to watch for.** If users report that recalled episode summaries feel irrelevant on the first
message of a new topic (turn 2+), the root cause is this lag. Fix: run a second inline episodic call
when the semantic similarity between consecutive queries drops below a threshold — but that adds
complexity; defer until a real complaint surfaces.

**Implementation.** `src/hachi/gateway/orchestrator.py`:
- `_run_prefetch_job` (~line 1203): episodic block added after semantic block; id-keyed dedup.
- `_chat_impl_inner` (~line 1582): turn-1 inline fallback now handles both semantic + episodic with
  the same id-keyed dedup. The old always-synchronous standalone episodic block was removed.

**Locked by.** `tests/test_b10_episodic_recall_offload.py` (10 tests).


---

## Observability sink demoted from span-emitter to attribute-stamper (Phase 2, 2026-07-06)

**Context.** `ObservabilitySink` previously opened zero-duration marker spans for each of 9 bus
events (e.g. `tool.call.started` → a span named `"tool.call.started"`; `session.chat.started` →
`"agent.turn.start"`). This caused double-accounting with the real `agent.turn` root span opened in
`orchestrator._chat_impl` and created empty spans with no timing or child content.

**Decision.** The sink is now an **attribute stamper**: it calls `tracing.add_span_attributes()`
and `tracing.add_span_event()` to stamp correlation ids and well-known payload fields onto the
*currently active* span — never opening a new span. The waterfall is owned by `with span(...)`
wrappers at the work seams; the sink enriches them.

**Consequences.**
- `test_obs_sink.py::test_sink_mirrors_tool_call_started`, `::test_sink_carries_correlation_attributes`,
  `::test_sink_does_not_leak_secrets` were rewritten to assert the new attribute-stamping contract.
  This is an intended contract change, not a weakened test.
- When `events.bus_funnel=false`, direct spans still give the full waterfall; only sink-based
  attribute enrichment is unavailable (Phase 0 degraded-mode warning covers this).

**Locked by.** `tests/test_obs_sink.py` (10 tests, post-Phase-2 contract).
