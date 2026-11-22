# Bug Bank — Hachi's regression memory

This file is the **memory layer that survives across sessions**. It is the direct
cure for _"a bug I already fixed came back"_ and _"I fixed the same bug three times."_

Every non-trivial bug or hard-won, non-obvious constraint gets a short **autopsy**
here: the symptom, the root cause, the fix, and what now _locks_ it (a regression
test or a mechanical guard). When an agent starts a session, the `SessionStart`
hook (`.claude/hooks/session_start.py`) injects the entries below into context, so
the warnings are loaded _before_ planning — never relearned the hard way.

> **The regression law (CLAUDE.md):** for every bug you fix, first write a test
> that _fails_ because of the bug, then fix the code, then confirm it goes green.
> That test is permanent. Add the autopsy here and link the test under **Locked by**.

## How to add an entry

Copy the template, give it the next `BB-N` number, keep it tight:

```markdown
### BB-N — Short title

- **Symptom:** what you observe (the failure, not the cause).
- **Root cause:** the actual mechanism.
- **Avoid:** the one-line rule a future agent must follow. ← the SessionStart hook surfaces this.
- **Locked by:** the regression test path, or the mechanical guard. "None yet — add when next touched" is an honest answer.
```

Keep **Avoid:** to a single imperative line: it is what gets injected at session start.

---

## Entries

### BB-1 — Windows pytest/mypy `.exe` shim fails with OS error 4551

- **Symptom:** `uv run pytest` or `uv run mypy` aborts on Windows with `OSError 4551`
  (editable-install lock) before collecting anything.
- **Root cause:** the generated `.exe` console-script shim contends with the
  editable-install lock on Windows.
- **Avoid:** on Windows, fall back to `python -m pytest` / `python -m mypy`, or
  `PYTHONPATH=src uv run --with pytest --no-project pytest -q`. `scripts/preflight.py`
  invokes tools through `uv run`, which usually sidesteps the shim.
- **Locked by:** mechanical — documented fallback; no test (environment-specific).

### BB-2 — `.env` autoload belongs at the CLI edge, never in the core import path

- **Symptom:** adding a top-level `.env` autoload to core/library modules turned the suite
  red across unrelated tests; credentials "sometimes" resolve depending on import/test order.
- **Root cause:** loading `.env` during a _library_ import leaks ambient env into hermetic
  tests and couples units to global state. A real attempt to do this caused a cascade and was
  reverted.
- **Avoid:** keep `.env` loading at the **CLI entry edge only** —
  `cli/main.py::_load_dotenv_into_environ()` runs at CLI import but is gated by
  `HACHI_DISABLE_DOTENV_AUTOLOAD=1` (conftest sets it). Core code (`core/oauth.py`,
  `core/llm.py`, `tools/google_tools.py`) resolves credentials **lazily at call time** — never
  add a library/core import-time autoload.
- **Locked by:** `tests/test_dotenv_hermeticity.py` (the guard works + conftest defaults the
  flag to `"1"`); lazy call-time readers in core. Related: BB-8.

### BB-3 — `patch.dict(sys.modules)` over `chromadb` poisons later tests

- **Symptom:** a test that patches `sys.modules["chromadb"]` passes, then a _later_
  test dies with `cannot load module more than once` (PyO3 native extension).
- **Root cause:** `patch.dict(sys.modules)` wipes chromadb's compiled PyO3 extension;
  it cannot be re-imported in the same process. A "restore" fixture made it worse by
  forcing re-import.
- **Avoid:** never `patch.dict(sys.modules)` over `chromadb`. `conftest` **warms
  chromadb at import** so the native module loads exactly once — leave that warm-up in.
- **Locked by:** `tests/conftest.py` chromadb warm-up (deterministic suite, ~8× faster).

### BB-4 — OpenAPI ↔ frontend contract drift fails CI

- **Symptom:** the `frontend-contract` CI job fails on a `schema.d.ts` diff after a
  gateway route change.
- **Root cause:** the generated TypeScript transport contract
  (`frontend/src/lib/data/schema.d.ts`) is derived from `openapi/hachi-openapi.json`;
  changing a route without regenerating both leaves them out of sync.
- **Avoid:** after **any** gateway route change run
  `uv run hachi gateway-openapi --output openapi/hachi-openapi.json` **and**
  `npm run --prefix frontend generate:api`. `scripts/preflight.py` checks this.
- **Locked by:** CI `frontend-contract` job; `npm run --prefix frontend check:api`.

### BB-5 — `paths.workspace_dir` does not exist

- **Symptom:** `AttributeError` reaching for `paths.workspace_dir`.
- **Root cause:** the path accessor was never named that.
- **Avoid:** use `paths.skills_dir` (and the other `get_hachi_paths()` accessors:
  `config_dir`, `data_dir`, `state_dir`, `cache_dir`).
- **Locked by:** `src/hachi/core/paths.py` (covered by the strict mypy gate).

### BB-6 — `ProcessSharedServices` is `None` before a session boots

- **Symptom:** `AttributeError`/`NoneType` when touching shared services outside a
  live session (e.g. in a CLI path or a test that didn't boot one).
- **Root cause:** `ProcessSharedServices` is lazy — it does not exist until a session
  boots.
- **Avoid:** never assume shared services exist outside a live session; guard for
  `None` or boot a session first.
- **Locked by:** None yet — add a regression test when next touched.

### BB-7 — `hachi` ↔ `tokoboros` directory junction (double collection)

- **Symptom:** the suite appears to collect twice / a sibling `tokoboros` path shows
  the same files; `git core.hooksPath` may point into the junction.
- **Root cause:** `D:\OpenGigantic\hachi` and a sibling `tokoboros` path are the same
  files via a Windows directory junction.
- **Avoid:** rely on pytest `norecursedirs` (skips `tokoboros`) so the suite isn't
  collected twice. Don't "fix" paths by chasing the junction.
- **Locked by:** `pyproject.toml` `[tool.pytest.ini_options] norecursedirs`.

### BB-8 — OAuth client id read as an import-time global never saw `.env`

- **Symptom:** Google Workspace config looked correct but auth never picked up
  `GOOGLE_CLIENT_ID`; spend/integration silently inert.
- **Root cause:** the id was read into a module-level global at import, before any
  `.env` was loaded (and there is no global autoload — see BB-2).
- **Avoid:** read integration credentials **lazily at call time**, loading
  `config_dir/.env` inside the call — not as a top-level constant.
- **Locked by:** regression test for lazy OAuth credential resolution (added with the fix).

### BB-9 — OpenAI-compatible streaming reported `$0` cost → daily spend cap inert

- **Symptom:** per-turn cost/tokens were `$0` across many real turns on OpenAI-compatible
  providers; the daily spend cap never triggered.
- **Root cause:** `OpenAICompatibleClient.generate_stream` omitted
  `stream_options.include_usage`, so the provider streamed no usage and cost tracking
  saw nothing — the spend cap had no data to act on.
- **Avoid:** keep the default-on `stream_usage` flag; OpenAI-compatible streaming must
  request `include_usage` or the cost/limit machinery goes silently dark.
- **Locked by:** regression test asserting usage is requested + cost > 0 on a streamed
  OpenAI-compat turn (added with the fix).

### BB-10 — Web-UI OAuth token invisible to agent (key prefix mismatch + wrong CLI command)

- **Symptom:** agent always treats the user as unauthenticated with Google even after they
  authenticated through the web UI; every Google tool call raises "Google needs a one-time
  browser sign-in… Run `hachi auth google` once" — but `hachi auth google` does not exist.
- **Root cause:** two separate code paths share the same `SecretStore` but use different key
  prefixes: the web UI (`integrations/oauth_flow.py`) writes under `"oauth2.<provider>"`;
  `OAuthManager.get_token()` only checked `"oauth.<provider>"` (via `_key()`), so it always
  returned `None`. The error message then named the non-existent `hachi auth google` command
  instead of the real `hachi google-auth` command.
- **Avoid:** when two writers share a `SecretStore`, always read both key prefixes or unify
  the write path; always verify CLI command names exist in `cli/main.py` before embedding
  them in user-facing error strings.
- **Locked by:** `tests/test_oauth.py::test_get_token_finds_web_ui_oauth2_prefix` and
  `tests/test_oauth.py::test_noninteractive_error_mentions_correct_cli_command`.

### BB-11 — Connecting Google via web UI never enables the agent capability

- **Symptom:** Integrations page shows Google as "connected" (green dot), but every Gmail
  query reports "Gmail is currently disabled." Re-connecting doesn't help; restarting the
  gateway doesn't help.
- **Root cause:** Two disconnected systems: `oauth_flow.py` stores the OAuth token
  (`oauth2.google`) but never touches `capabilities.google.enabled` in config, which
  defaults to `False`. `_build_capability_registry` reads that flag at startup — if it's
  `False`, Google tools are not registered and the agent has no Gmail capability regardless
  of the stored token.
- **Avoid:** after any OAuth connect/disconnect, always flip `capabilities.<id>.enabled`
  accordingly via `control_plane.set_capability_enabled`. At startup, fall back to the
  token store: if a token exists and the config flag is `False`, treat it as enabled.
- **Locked by:** `tests/test_oauth_integrations.py::TestOAuthAutoEnablesCapability`
  (`test_callback_success_calls_set_capability_enabled`,
  `test_callback_failure_does_not_enable_capability`).

### BB-12 — Idempotency key reuse across page reloads returns stale response instantly

- **Symptom:** a new query instantly returns the previous turn's exact response verbatim;
  the response appears before the LLM has had time to process the new prompt.
- **Root cause:** `store.ts`'s module-level `_id` counter resets to 100 on every page
  load. Since the gateway session UUID is preserved across refreshes via `sessionStorage`,
  the idempotency key `turn-102` from a prior page load collides with the new turn's key
  and the backend replays the cached old response.
- **Avoid:** include a per-page-load nonce (`_PAGE_NONCE` in `chat.ts`, generated once at
  module load via `crypto.randomUUID()`) in every turn's idempotency key. Never use a
  predictable counter alone as the idempotency key when the session may outlive the page.
- **Locked by:** `frontend/src/lib/data/domains/chat.test.ts` — _buildTurnKey produces
  different keys for the same hachiMsgId with different page-load nonces_.

### BB-9 — Secret keys blocked with no escape hatch; `secret:` refs not resolved at MCP connect time

- **Symptom:** POST `/runtime/mcp/register` with an env var like `API_KEY` always 422s
  even when the value is a `secret:mykey` reference. Conversely, servers whose TOML env
  contains raw `secret:` strings boot with the literal string instead of the resolved value.
- **Root cause:** the secret-pattern guard checked key names unconditionally; `setup_from_config`
  passed `env`/`headers` straight to the transport without resolving `secret:` refs.
- **Avoid:** env/header keys that look like secrets may carry a `secret:<name>` reference value —
  the guard must allow these and verify `cred:<name>` exists. `setup_from_config` must call
  `_resolve_secret_refs` before building the transport. System keys (non-`cred:` namespace) are
  never listed or deleted via the credential manager API.
- **Locked by:** `tests/test_mcp_registration.py` (`TestResolveSecretRefs`,
  `TestMcpSetupFromConfigSecretRefs`); `tests/test_secret_store.py::TestSecretStoreGatewayAPI`.

### BB-10 — TOML-only MCP servers invisible until a live session exists

- **Symptom:** after `POST /runtime/mcp/register`, GET `/runtime/mcp/inventory` returns an
  empty list if no conversation has been started yet. Users think registration failed.
- **Root cause:** `mcp_inventory()` in `GatewayControlPlane` only enriched servers reported by
  the live agent; TOML-persisted servers that haven't been connected in this session were dropped.
- **Avoid:** after enriching live-agent servers, merge TOML `[mcp_servers]` entries that aren't
  in the live set, reporting them as `status: "pending_restart"`.
- **Locked by:** `tests/test_mcp_registration.py::TestMcpInventoryTomlOnly`.

### BB-11 — Search provider is a boot-time registry decision; Tavily key stored live has no effect

- **Symptom:** user saves their Tavily API key via the Integrations UI; the current conversation
  still reports "web search unavailable" and no `web_search` tool appears.
- **Root cause:** `ProviderRegistry` is built once at `boot_agent`; storing a credential later
  doesn't rebuild it, so the Tavily provider is never discovered.
- **Avoid:** after storing Tavily credentials, call `reload_search_provider()` on the live
  `AgentSession` — it rebuilds the registry, re-resolves the provider, and hot-patches the
  tool registry (idempotent: updates handlers without duplicating schemas).
- **Locked by:** `tests/test_search_platform.py::TestTavilyLiveReload`.

> ⚠️ Numbering note: the three entries above (secret refs / TOML-only MCP / search reload)
> were added in a prior session that restarted the count at BB-9, colliding with the
> pre-existing BB-9/10/11. They should eventually be renumbered to BB-9b/10b/11b (or
> 13/14/15) — left as-is here to avoid touching that session's many code comments. The
> entries below continue the sequence from the real BB-12.

### BB-13 — Conversation dropdown empty on boot — `recent_sessions` short-circuited with no live agent

- **Symptom:** at server start the "New conversation" dropdown shows "No recent sessions"
  even though `sessions.db` holds prior conversations; they only appear after the first turn.
- **Root cause:** `_InProcessGatewayRuntime.recent_sessions` returned `[]` whenever `_agents`
  was empty (no agent had booted yet), so it never read the persisted `SessionStore`. The same
  `agent is None: return []` shape exists in `get_skills`/`get_memory`/etc.
- **Avoid:** gateway read-only history endpoints must fall back to the durable store when no
  agent is live — don't gate persisted data behind an in-memory agent. Open a `SessionStore`
  on `get_hachi_paths().sessions_db` and `shutdown()` it after the read.
- **Locked by:** `tests/test_web_gui_diag.py::TestRecentSessionsNoAgent`.

### BB-14 — Tavily key saved via UI invisible to provider + Test Connection (key-name mismatch)

- **Symptom:** after saving a Tavily API key in Integrations, "Test Connection" reports
  "No Tavily API key stored" and web search stays unavailable.
- **Root cause:** the credential dialog writes the namespaced key
  `apikey.tavily.tavily_api_key` (`oauth_flow.store_apikey_credential`), but
  `TavilySearchProvider._resolve_api_key` and the Test Connection `_resolve_secret` only read
  the bare `tavily_api_key`. `ProviderRegistry.from_config` already checked BOTH keys for
  _detection_, so the provider registered but then failed to find the key at call time.
- **Avoid:** readers of a connector credential must resolve the SAME key the writer used —
  check both `apikey.<connector>.<field>` and the bare name (mirror the registry's list).
- **Locked by:** `tests/test_web_gui_diag.py::TestTavilyKeyResolution`,
  `::TestTavilyTestConnectionEndpoint`.

### BB-15 — Permission tier silently reverts to Standard when the external `/models` call fails

- **Symptom:** setting the safety tier to "Open" reverts to "Standard" (on reload / intermittently),
  even though `settings.toml` correctly persists `tier = "unrestricted"`.
- **Root cause:** `loadConfig` fetched `/config` (12 ms, the safety source of truth) and
  `/models` (a LIVE external provider round-trip, ~1.6 s, flaky) in one `Promise.all`. Any
  `/models` rejection dropped into the catch, which reset `safety: "standard"`.
- **Avoid:** never couple a local source-of-truth read to a flaky external call in one
  all-or-nothing fetch. Fetch `/config` on its own; treat `/models` as a non-critical dropdown
  list whose failure can only degrade the picker, never config-derived state.
- **Locked by:** `frontend/src/lib/data/domains/config.test.ts`
  ("keeps the /config tier when /models REJECTS").

### BB-16 — MCP server stuck showing "starting" — unmapped `pending_restart` status

- **Symptom:** a TOML-persisted MCP server (e.g. a legacy "demo") shows "starting" forever
  even when no session is live and it is not actually booting.
- **Root cause:** the backend reports `pending_restart` (registered, not connected this session),
  but `adaptMcpServer.statusMap` and `mcpMeta` had no entry for it and fell back to `starting`.
- **Avoid:** keep the frontend status vocabulary in sync with the backend — `pending_restart`
  and `stopped` map to a distinct `pending` ("needs restart") state, not the `starting` fallback.
- **Locked by:** `frontend/src/lib/data/domains/integrations.test.ts`
  ("adaptMcpServer — real mapping (BB-16)").

### BB-17 — MCP servers table columns misaligned with their headers

- **Symptom:** in the MCP servers table, cell values (status/tools/transport/uptime/toggle)
  don't line up under their column headers.
- **Root cause:** the header reserved fixed widths (Enabled 40, spacer 32) but the row's toggle
  cell had no width (`flexShrink:0` only) and the delete button was content-sized, so every
  cell after Uptime drifted by the cumulative `gap`.
- **Avoid:** flex "table" rows must give every cell the SAME fixed width as its header column;
  a width-less cell collapses to content width and shifts everything after it.
- **Locked by:** visual verification (no clean unit seam for CSS layout) — toggle cell pinned to
  `width:40` (= Switch width = header), delete button to a `width:32` slot (= header spacer).

### BB-18 — Registering an MCP server with an API key was impossible from the UI

- **Symptom:** registering e.g. context7 with `CONTEXT7_API_KEY` returned HTTP 422
  ("looks like a secret; store the value via POST /runtime/secrets …"); the dialog also
  hard-blocked secret-looking stdio env keys client-side.
- **Root cause:** the backend (correctly) refuses raw secret-looking env/header values and wants
  them stored via `/runtime/secrets` then referenced as `secret:<name>`, but the dialog had no
  support for that two-step flow.
- **Avoid:** when a backend requires store-then-reference for secrets, drive it transparently —
  detect secret-looking env/header keys, `POST /runtime/secrets` first, then send `secret:<name>`
  in the register payload. The raw value never reaches `settings.toml`.
- **Locked by:** `frontend/src/lib/data/domains/integrations.test.ts`
  ("extractMcpSecrets — transparent secret handling").

### BB-19 — Re-registering an MCP server clobbered its persisted `enabled` flag

- **Symptom:** an `[mcp_servers.NAME]` entry that had `transport`, `url`, **and**
  `enabled = true` came back with only `transport` + `url` after the server was
  registered again (e.g. the user edited its URL in the UI). The lifecycle flag was
  silently dropped — looked like data loss on the entry.
- **Root cause:** `_InProcessGatewayRuntime.register_mcp_server` persisted with
  `mcp_section[name] = cfg.to_toml_entry()`, which **replaces the whole sub-table**
  from the in-memory `MCPServerConfig`. That dataclass has no `enabled` field (it's
  written separately by `set_mcp_enabled`), so `to_toml_entry()` never emits it and
  the re-register wiped it. (Siblings were already safe — register/delete only ever
  touched the targeted key — but the _targeted_ entry lost any field the config
  doesn't model.)
- **Avoid:** when persisting a server, edit ONLY the keys the config owns
  (`MCPServerConfig.TOML_MANAGED_KEYS`) — overwrite those, prune managed keys that no
  longer apply (e.g. a stdio `command` after switching to http), and leave every other
  key (notably `enabled`) untouched. Never rebuild a `[mcp_servers.NAME]` table from an
  in-memory config that doesn't carry the full key set.
- **Locked by:** `tests/test_mcp_registration.py::TestMcpRegisterPreservesEntryFields`
  (`test_reregister_preserves_enabled`,
  `test_reregister_transport_switch_prunes_stale_keys_keeps_enabled`,
  `test_register_then_delete_leaves_sibling_byte_for_byte`,
  `test_toml_managed_keys_cover_to_toml_entry`).

### BB-20 — Default OpenAI model was `gpt-4.1-mini` (not in catalog)

- **Symptom:** cost tracking returned `$0` for sessions using the default model; model-picker UI showed no entry highlighted.
- **Root cause:** `config_loader.py:217` and `cli/main.py:3798` (tier-plan builder) both hardcoded `"gpt-4.1-mini"` as the fallback, but that id was absent from `BUNDLED_MODEL_DEFAULTS`. `ModelRegistry.get("gpt-4.1-mini")` returned `None`.
- **Avoid:** whenever changing the default model, verify `ModelRegistry.build(...).get(model_id) is not None`. The locking test asserts this.
- **Locked by:** `tests/test_config_loader.py::test_openai_default_model_is_catalog_member`.

### BB-21 — Messages table had no `model` column; replayed sessions showed wrong model label

- **Symptom:** reloading a past session showed the current provider model on all past messages instead of the model used when the message was generated.
- **Root cause:** `messages` table had no `model` column; `log_message()` never accepted one; the synthesised `session.chat.completed` event from `control_plane._synthesize_history_events` emitted `payload: {}`, not `payload: {"model": ...}`. Frontend reads `payload.model` on this event to update `lastUsedModel`.
- **Avoid:** when adding a new per-turn metadata field, touch all four layers: DB schema + migration, `log_message()` signature, `get_session_messages()` SELECT, and the history-replay event synthesis.
- **Locked by:** `tests/test_session_store_model_column.py` (4 tests).

### BB-22 — New OpenAI models (gpt-4.1, o3-mini, o4-mini) missing from catalog; o3/o3-mini prefix collision risk

- **Symptom:** configuring `gpt-4.1-mini`, `o3-mini`, or `o4-mini` as the provider model gave `$0` cost tracking and no entry in the model picker.
- **Root cause:** `BUNDLED_MODEL_DEFAULTS` only had `gpt-4o` and `gpt-4o-mini`; `MODEL_PRICING` had no entries for the GPT-4.1 family or o-series. Without an explicit `"o3-mini"` entry, `pricing_for` would prefix-match `"o3"` and use o3's (10× higher) price.
- **Avoid:** when adding an o-series model, always add BOTH the base id AND any cheaper variants (e.g. `o3` AND `o3-mini`) as explicit keys in `MODEL_PRICING` so longer-prefix-wins resolves them independently. Extend `TestCurrentOpenAIModels` when adding future models.
- **Locked by:** `tests/test_routing_registry.py::TestCurrentOpenAIModels` (5 tests).

### BB-24 — Episodic recall on turns 2+ uses the previous turn's query (B10 staleness)

- **Symptom:** on turn N+1, recalled episode summaries are matched to turn N's question instead of
  the current one. In most conversations this is invisible, but a sharp topic pivot can surface
  an episodic hit that feels irrelevant to the new question.
- **Root cause:** `_run_prefetch_job` is enqueued at the end of turn N with turn N's query; the
  result is consumed at the start of turn N+1. Episodic recall was moved into this prefetch job
  (B10, `perf/streaming-optimizations`) to avoid blocking the inline turn path on turns 2+.
  Turn 1 is always exact (inline fallback runs both semantic and episodic synchronously).
- **Avoid:** do NOT add a second inline episodic call on every turn to "fix" the lag —
  that defeats the entire purpose of B10 and re-introduces the latency regression.
  Only add an inline fallback if the turn N vs N+1 query similarity drops below a threshold
  (defer until a real complaint surfaces). Document the tradeoff in docs/DECISIONS.md §B10.
- **Locked by:** `tests/test_b10_episodic_recall_offload.py` (parity tests confirm turn-1 inline
  path still calls `search_episodic` and that dedup works identically in both paths).

### BB-23 — MCP servers that failed before transport setup were invisible in the operator inventory

- **Symptom:** an MCP server with an invalid TOML config or gate-denied by the permission tier emitted `MCP_SERVER_FAILED` at boot but never appeared in `GET /runtime/mcp/inventory`, making it impossible to diagnose why a server wasn't available.
- **Root cause:** `MCPManager.get_inventory()` only iterated `_servers`, which is populated only after a successful transport setup. Servers that failed in `MCPServerConfig.from_toml_entry()` or were denied by `gate.is_mcp_server_allowed()` never entered `_servers`.
- **Avoid:** call `mcp_manager.register_boot_failure(name, reason)` at every early-exit failure path in `_configure_mcp_servers` before the `mcp_manager.setup_from_config()` call. `get_inventory()` merges `_boot_failures` into the result.
- **Locked by:** `tests/test_mcp_registration.py::TestMcpBootFailureInventory` (3 tests).

### BB-24 — Tavily connector showed "disconnected" when package not installed (no actionable UI path)

- **Symptom:** users without `tavily-python` installed saw a dead-end API-key form ("Enter your Tavily API key") when the package wasn't installed — entering a key silently failed because the import guard prevented the provider from loading.
- **Root cause:** `connector_status("tavily")` returned `"disconnected"` regardless of whether the Python package was installed, conflating two distinct states.
- **Avoid:** for connectors backed by optional Python packages, check `importlib.util.find_spec(package_name)` first. If `None`, return `status="unavailable"` and `package_installed=False` so the UI can show install guidance instead of a key-entry form.
- **Locked by:** `tests/test_tavily_status_tristate.py::TestTavilyStatusTristate` (4 tests).

### BB-25 — `update_permissions(tier)` wrote settings.toml but never regenerated device-permissions.og

- **Symptom:** changing the permission tier via the Settings UI appeared to save, but `PermissionGate` (which reads `device-permissions.og`) remained at the old tier on the next boot and for any new session started after the change.
- **Root cause:** `_InProcessGatewayRuntime.update_permissions()` called `write_global_config(config)` which persists to `settings.toml`, but `PermissionGate` reads `device-permissions.og` — a separate file that was never regenerated. The gap was invisible until a fresh boot, because the in-process gate object (already built) wasn't rebuilt either.
- **Avoid:** after any tier change, atomically regenerate `device-permissions.og` using `generate_permissions_og(tier, custom_paths)`, preserving existing `allowed_paths`. Also add a boot-reconcile step in `boot_agent` after `load_config()`: if `config.permissions.tier != gate.tier`, rebuild gate + approver.
- **Locked by:** `tests/test_permissions_update.py::TestUpdatePermissionsRegeneratesOg` (3 tests).

### BB-26 — `SessionExpiredError` (HTTP 410) left user to re-type their message

- **Symptom:** after a gateway restart, the next `POST /sessions/{id}/messages` returned 410 with `"session_expired"` and the UI showed a toast asking the user to resend manually — the in-flight prompt was lost.
- **Root cause:** the frontend `sendMessage` catch handler recognised `session_expired` but only cleared the stale session ID and showed a toast. It did not mint a new session or replay the prompt.
- **Avoid:** on `session_expired` (410), immediately call `ensureSession()` to mint a fresh session and replay the original `POST` with a new idempotency key. Use a distinct `_r`-suffixed nonce so the server does not de-duplicate it against the dead-session key. The daily spend cap is enforced server-side (durable ledger) and still applies on retry — do not add client-side spend bypass.
- **Locked by:** `frontend/src/lib/data/domains/chat.ts` auto-retry in `.catch(async …)` block. No dedicated vitest yet (SSE stream integration is hard to mock end-to-end).

### BB-27 — Opus-4 family mispriced 3× (legacy Claude-3-Opus rate)

- **Symptom:** the web UI / `/spend` showed ~3× the true cost for any turn that ran
  on an Opus-4 model; spend felt inexplicably high.
- **Root cause:** `core/cost.py` `MODEL_PRICING` **and** `core/routing/descriptor.py`
  `BUNDLED_MODEL_DEFAULTS` both priced `claude-opus-4` and `claude-opus-4-8` at
  `(15.0, 75.0)` — the legacy Claude-3-Opus rate. Current Opus (4.5+) is `$5/$25` per
  MTok, so every Opus turn's estimated cost was inflated 3×.
- **Avoid:** price current Opus at `(5.0, 25.0)`; keep the two pricing tables in sync
  (the parity guard in `tests/test_routing_registry.py::TestPricingParity` enforces it).
  When adding a model variant, verify against Anthropic's published per-MTok pricing —
  never copy an older entry's numbers.
- **Locked by:** `tests/test_cost_tracking.py::test_opus_4_family_priced_at_current_rate_not_legacy`
  and `::test_pricing_longest_prefix_match`; `tests/test_routing_registry.py::TestPricingParity`.

### BB-28 — OpenAI cached input billed at full price + Anthropic discount assumed for all

- **Symptom:** OpenAI/openai-compatible cache savings were invisible, and displayed
  cost *overstated* OpenAI spend — cached input tokens were billed at the full input
  rate, then (where any cache tokens existed) discounted with Anthropic's 0.1× rate.
- **Root cause:** two gaps. (1) `OpenAICompatibleClient` parsed only `prompt_tokens` /
  `completion_tokens` and ignored `prompt_tokens_details.cached_tokens`. (2)
  `CostTracker.record` hard-coded `_CACHE_READ_MULTIPLIER = 0.1` instead of the
  per-model `Pricing.cache_read_mult` — so even captured cache reads were priced with
  Anthropic economics for every provider.
- **Avoid:** parse `cached_tokens` into `cache_read_tokens` (split it out of
  `prompt_tokens`, both streaming and non-streaming); price cache reads with the
  resolved model's `cache_read_mult` (OpenAI 0.5×, Anthropic 0.1×). Registry-less
  trackers fall back to the module constants unchanged.
- **Locked by:** `tests/test_cost_tracking.py::test_cost_tracker_uses_per_model_cache_multiplier_from_registry`;
  `tests/test_streaming.py::test_openai_stream_splits_cached_prompt_tokens`,
  `::test_openai_generate_splits_cached_prompt_tokens`.

### BB-29 — OpenAI auto-cache defeated by the time header inside the system message

- **Symptom:** OpenAI's automatic prompt caching never engaged across turns; every
  turn re-billed the full ~6K system+tools prefix at fresh-input price.
- **Root cause:** `OpenAICompatibleClient._build_request` appended the volatile dynamic
  block (time header / recall) to the END of the system message, so the cached prefix
  changed every turn. Prompt caching is a prefix match — one byte change invalidates it.
- **Avoid:** keep the system message byte-stable across turns; place the dynamic block as
  its own trailing message AFTER the conversation so the stable system+tools prefix stays
  cacheable. (Mirrors the Anthropic split, where the dynamic tail sits after the cache
  breakpoint.)
- **Locked by:** `tests/test_streaming.py::test_openai_request_keeps_time_header_out_of_system_message`.

### BB-30 — Every chat turn silently routed to the priciest model

- **Symptom:** cost per trivial turn was inexplicably high; the model that actually
  answered was far pricier than the configured `provider.model` / `default_model`.
- **Root cause:** `routing.capabilities` pinned high-volume capabilities
  (`reasoning`/`coding`/…) to an expensive model (e.g. `gpt-4o` at $2.50/Mtok in) —
  often via a legacy import or wizard — while `default_model` was cheap
  (`gpt-4o-mini` at $0.15). The router honoured it **silently**, so every chat turn
  paid ~16× without any signal.
- **Avoid:** a fresh/imported config or tier setup must not map the general chat
  capability to a model far pricier than `default_model`. `derive_auto_policy`
  already routes `reasoning → default_model` and `title/compaction → cheapest`;
  `RoutingPolicy.costly_capability_warnings()` flags an explicit costly override
  loudly at boot. Never auto-pin chat to the priciest model.
- **Locked by:** `tests/test_routing_cost_guard.py`; boot wiring in
  `gateway/orchestrator.py` logs + emits `cost.routing_warning`.

### BB-31 — Background LLM spend (fact extraction / titling) was invisible

- **Symptom:** real spend from background fact extraction (and durable session
  titling) never showed in `/spend` and never counted against the daily cap.
- **Root cause:** `extract_facts` / `handle_extract_fact` run an LLM call with no
  per-session `CostTracker` and never wrote to the durable daily ledger — the spend
  simply vanished from accounting.
- **Avoid:** record every background (non-session) LLM call's usage into the durable
  daily ledger via `cost.record_background_usage(model, usage)` — the daily spend cap
  reads the same ledger, so untracked background calls both hide cost and weaken the cap.
- **Locked by:** `tests/test_cost_tracking.py::test_record_background_usage_writes_to_daily_ledger`,
  `::test_extract_facts_records_background_spend`.

### BB-32 — MCP tools invisible to LLM — classified as "integrations" group, never activated

- **Symptom:** LLM says "no skill found" or ignores a connected MCP server entirely; the user
  says "use the demo MCP" and the agent treats it as an `.og` skill lookup and fails.
- **Root cause:** Three-part chain. (1) `tool_registry.classify(…, default="integrations")` in
  `orchestrator.py` stamps all MCP tools (e.g. `demo_list_files`) as group `"integrations"`.
  (2) `ExecutionLoop._active_groups` starts as `set()` on every `run()` call (only `"core"` is
  always-on). (3) `get_schemas(active_groups=set())` only returns `"core"` tools, so the LLM
  never sees MCP tools and cannot call them.
- **Avoid:** after `classify()`, call `tool_registry.reclassify_by_prefix({f"{name}_": "mcp" …})`
  for every live MCP server, then set `loop._persistent_groups.add("mcp")`. Do the same in the
  `add_mcp_server_live()` hot-reload path. Never rely on the user's `use_tools` call to activate
  "mcp" — MCP tools must be always-on when servers are connected.
- **Locked by:** `tests/test_mcp_tool_visibility.py::TestMcpToolVisibility` (6 tests).

### BB-33 — `web_search` / `extract_url` invisible to LLM — demoted to "integrations" group by `classify()`

- **Symptom:** agent says "I don't have Tavily or direct internet search capabilities" even when
  `TAVILY_API_KEY` is set and a `SearchProvider` is registered at boot.
- **Root cause:** `register_search_tools()` registers both tools with the default `group="core"`.
  After all TOOL_SPECS are registered, `classify()` runs: for any tool whose current group is
  `"core"` but that is NOT in `core_names`, it reclassifies to `default="integrations"`.
  `web_search` and `extract_url` were absent from `_CORE_TOOL_NAMES`, so they got demoted.
  `"integrations"` is never in `_active_groups`, so `get_schemas()` hides them every turn.
- **Avoid:** `web_search` and `extract_url` must be in `_CORE_TOOL_NAMES`. They are safe there —
  they only enter the registry when a SearchProvider exists (no key → no registration → no schema).
- **Locked by:** `tests/test_search_tool_visibility.py::TestSearchToolVisibility` (4 tests).

### BB-34 — Duplicate skill names → React "same key" warning on the Skills screen

- **Symptom:** browser console: `Warning: Encountered two children with the same key, 'identity'`
  on the `/skills` route; in edge cases, skill cards may be duplicated or dropped.
- **Root cause:** `get_skill_inventory()` iterates `_nodes` keyed by `qid`; two `.og` files can
  define nodes with the same display `name` but different `qid`s. Both rows reach the frontend
  adapter, which sets `id = raw.name`, producing colliding React keys.
- **Avoid:** `get_skill_inventory()` must deduplicate by name after sorting (first/highest
  `use_count` wins). The frontend `loadSkills()` must also call `deduplicateSkillsByName()`
  as a defensive guard before mapping — never map a raw gateway list where uniqueness is not
  guaranteed by the schema.
- **Locked by:** `tests/test_skill_inventory_dedup.py::TestSkillInventoryDedup` (3 tests);
  `frontend/src/lib/data/domains/skills.test.ts` — deduplicateSkillsByName (4 tests).

### BB-35 — `session_messages()` returns `[]` on cold boot — past-session history empty

- **Symptom:** switching to a previous session in the web UI shows an empty conversation;
  messages never appear even though the session has a full persisted transcript.
- **Root cause:** `_InProcessGatewayRuntime.session_messages()` returned `[]` when
  `_agents` was empty (server just started, no turn has run yet). `recent_sessions()`
  had the BB-13 SessionStore fallback; `session_messages()` did not. The `/sessions/{id}/events`
  endpoint synthesises events via `_get_session_messages`, so cold-boot = empty events = empty UI.
- **Avoid:** whenever you touch `_InProcessGatewayRuntime`, mirror the BB-13 pattern in
  every method that reads from `_agents`/`_session_store` — fall back to a direct
  `SessionStore(db_path=get_hachi_paths().sessions_db)` read when `_agents` is empty.
- **Locked by:** `tests/test_session_messages_cold_boot.py::TestSessionMessagesColdBoot` (2 tests).

### BB-36 — Scheduled task executions invisible in the work section

- **Symptom:** a scheduled job fires and the agent runs the task, but nothing appears in
  the web UI work section's active-jobs or failed-jobs lists; users have no observability
  on whether their schedule is running or has errors.
- **Root cause:** `_fire_schedule` in `orchestrator.boot_agent` called `session.chat()`
  inline with no surrounding `emit_runtime_event` calls, so no `job.started` /
  `job.completed` / `job.failed` events were produced. `RuntimeReadModelStore` only tracks
  jobs when those events arrive; the work section polls `/jobs/active` and `/jobs/failed`
  which are fed entirely by those events.
- **Avoid:** whenever you add a new execution path that runs agent work outside the
  `JobWorker` pipeline, bracket it with `emit_runtime_event("job.started", ...)` and a
  matching `job.completed` / `job.failed` so the runtime read-model stays consistent.
- **Locked by:** `tests/test_schedule_job_events.py::TestScheduleJobEvents` (5 tests).

### BB-37 — `GET /schedules` returns `[]` when no agent session is active (Routines tab empty)

- **Symptom:** the Routines tab in the work section shows "Nothing here yet" even though
  schedules were created in a prior chat session. Happens after a gateway restart or when
  the user navigates to `/work` before opening a chat (no `POST /sessions` has been called).
- **Root cause:** `_InProcessGatewayRuntime.list_schedules()` routed through
  `next(iter(self._agents.values()), None)` — the same `agent is None → return []` pattern
  as BB-13. `_agents` is empty until the user sends a chat message. The schedules exist in
  `~/.hachi/state/schedules.json` but were unreachable without a live agent.
- **Avoid:** `list_schedules()` must never gate on `_agents` being non-empty. Fall back to
  `ScheduleStore(get_hachi_paths().schedules_file).load()` when no agent is active.
- **Locked by:** `tests/test_schedule_job_events.py::TestListSchedulesColdBoot` (3 tests).

### BB-39 — Home approval card title wrapped one word per line on mobile

- **Symptom:** on narrow viewports (~375px) the Home "What needs you" approval card's
  title wrapped one word per line ("Hachi / wants / to / send…"), unlike the `/approvals`
  screen's equivalent card.
- **Root cause:** `ApprovalCard` (Home, `routes/index.tsx`) put the Decline/Allow-once
  buttons as a `flexShrink:0` sibling of the title in the SAME horizontal flex row as the
  icon badge. The title's `flex:1; minWidth:0` column absorbed all the squeeze, shrinking
  to near-zero width once the fixed-size icon + action buttons claimed their space.
  `/approvals`' `ApprovalCard` never had this bug because its actions already live in a
  separate full-width row below the header (`.hachi-approval-actions`, with a
  `flex-wrap`/`min-height:44px` mobile rule in `responsive.css`).
- **Avoid:** any card with fixed-size trailing controls (buttons, badges) next to a
  variable-width title must NOT put those controls in the same flex row as a
  `flex:1; minWidth:0` title column — give the controls their own full-width row instead,
  regardless of how much width looks available at desktop breakpoints.
- **Locked by:** `frontend/src/routes/-index.ApprovalCard.test.tsx` (asserts the actions
  block is a DOM sibling of the header row, not nested inside it).

### BB-38 — `KennelConsent` Rules-of-Hooks violation — browse↔consent transition could crash the overlay tree

- **Symptom:** switching between the kennel browse panel (`kennelBrowseOpen=true`) and
  a single-item consent dialog (`kennelConsent` set) throws `Error: Rendered more/fewer
  hooks than during the previous render`, crashing the overlay tree.
- **Root cause:** `KennelConsent()` early-returned `<KennelBrowsePanel/>` when
  `kennelBrowseOpen` was true, BEFORE its Escape-key `useEffect` — so the number of hooks
  the component called differed between a browse-mode render and a consent-mode render of
  the same instance (suppressed by a `// eslint-disable-next-line react-hooks/rules-of-hooks`).
- **Avoid:** every hook a component calls must run unconditionally on every render of that
  instance — never place a hook after a conditional `return`. Guard the hook's *body*
  (e.g. `if (!isOpen) return` inside the effect) instead of skipping the hook call itself.
  `KennelBrowsePanel` already got this right by being a separate sibling component.
- **Locked by:** `frontend/src/components/overlays/KennelConsent.test.tsx` (mounts
  `<KennelConsent/>` and rerenders across both transition directions via
  `@testing-library/react`).

### BB-41 — File-attachment tools crashed on every call — wrong `PermissionGate` API

- **Symptom:** every call to `attach_file`, `read_attachment`, `list_attachments`, or
  `search_attachments` raised a `TypeError` immediately, invisible to the end user because
  the execution loop swallowed it as a generic "Tool Execution Error". The whole file
  attachment tool group was silently non-functional.
- **Root cause:** `register_file_tools`'s internal `_gated` wrapper
  (`src/hachi/tools/file_tools.py`) constructed
  `PermissionRequest(tool_name=..., action=..., resource=...)` — kwargs that don't exist
  on the real dataclass (`request_id`/`operation`/`tool`/`target`/`reason`/
  `policy_summary`) — and called `gate.check(req)`, a method `PermissionGate` doesn't
  have. `PermissionGate` only exposes `check_path(path, operation)` /
  `check_command(command)`, each returning a `PermissionResult` with `.allowed`/`.reason`.
  `os_tools.py`'s gated wrappers already used the correct pattern; `file_tools.py` never
  matched it.
- **Avoid:** any new permission-gated tool wrapper must call `gate.check_path(path,
  operation)` or `gate.check_command(command)` and branch on `.allowed`/`.reason` — never
  invent a `.check()` method or a `PermissionRequest` convenience constructor. Verify
  against `src/hachi/core/permissions.py`'s actual public surface (or copy the pattern
  from `os_tools.py`) before wiring a new tool group to the gate.
- **Locked by:** `tests/test_file_platform.py::TestRegisteredFileToolsPermissionGate` (4
  tests) — registers the file tools with a REAL `PermissionGate` (not a mock) and invokes
  the wrapped, registered callables exactly as `ToolRegistry`/the execution loop would,
  asserting real JSON results instead of a `TypeError`.

### BB-42 — Background spend recording leaked a SQLite connection on every call

- **Symptom:** every call to `record_background_usage`/`record_voice_usage` (fact
  extraction, durable session titling, voice STT/TTS spend) opened a brand-new
  `SessionStore()` — running full schema init/migrations — and never closed it. On
  Windows this holds `sessions.db-wal`/`-shm` file handles open indefinitely,
  compounding over the life of a long-running gateway process.
- **Root cause:** both functions in `src/hachi/core/cost.py` tried
  `from hachi.gateway.orchestrator import _get_session_store` inside a
  `try/except Exception` — but `_get_session_store` has never existed in
  `hachi.gateway.orchestrator` (the real process-wide accessor pattern lives in
  `hachi.gateway.fastapi_app._resolve_session_store`, which goes through
  `ProcessSharedServices.instance()`). The import always raised `ImportError`,
  which the broad `except` swallowed, so the code silently fell through to the
  fallback branch on *every single call* and the fallback `SessionStore()` was
  never shut down.
- **Fix:** added `_get_shared_session_store()` in `cost.py` — mirrors
  `hachi.core.runtime.resume._get_process_bus()`'s established pattern of lazily
  importing `ProcessSharedServices` from `hachi.gateway.shared_services` (not
  `orchestrator`) and reading `.session_store` off the singleton via `getattr`.
  Both call sites now wrap the fallback `SessionStore()` in `try/finally:
  fallback_store.shutdown()` so the connection is always closed when no shared
  store exists. Updated the frozen import-linter seam in `pyproject.toml` from
  `"hachi.core.cost -> hachi.gateway.orchestrator"` to
  `"hachi.core.cost -> hachi.gateway.shared_services"` to match.
- **Avoid:** any core-adjacent code that opens a short-lived, non-shared
  `SessionStore()` (or any other object owning a raw `sqlite3` connection) as a
  fallback MUST wrap the call in `try/finally: store.shutdown()`. Never
  reference a gateway symbol by name without grepping to confirm it actually
  exists there first — a broad `except Exception` around the lookup will hide
  an `ImportError` forever and silently downgrade every call to the "no shared
  store" path.
- **Locked by:** `tests/test_cost_tracking.py::test_record_background_usage_closes_fallback_store_connection`
  and `::test_record_voice_usage_closes_fallback_store_connection` — assert that after the
  call, the fallback store's underlying `sqlite3` connection raises
  `sqlite3.ProgrammingError` on further use (i.e. it was actually closed).

### BB-40 — Automatic background fact-extraction ("auto-memory") was a complete, silent no-op

- **Symptom:** Hachi's advertised feature — background fact extraction after every
  turn so the user never has to say "remember this" — never wrote a single fact to
  the vault, for any user, in production. No error surfaced anywhere; the job queue
  reported every `extract_fact` job as COMPLETED.
- **Root cause:** two independent, compounding bugs.
  1. `build_job_context()`'s no-factory branch (the path every real production job
     takes — `orchestrator.boot_agent` registers `handle_extract_fact` with NO
     `_vault_factory` injected) did `from hachi.core.memory_vault import
     get_memory_vault` — a function that **did not exist** in `memory_vault.py`
     (only the `MemoryVault` class + module helpers were defined). The resulting
     `ImportError` was swallowed by a bare `except Exception: logger.debug(...)`,
     so `ctx.vault` silently stayed `None` and `handle_extract_fact` returned
     `"skipped:no_vault"` — logged with a misleading "ChromaDB not configured?"
     message that pointed nowhere near the real cause.
  2. `core/memory.py`'s `extract_facts()` additionally hardcoded a check for
     `os.environ["ANTHROPIC_API_KEY"]` even though it already receives a resolved,
     working `llm_client` argument from both callers (`handle_extract_fact` and
     `MemoryManager._run_fact_extraction`), each of which already gates on
     `client is None` before calling `extract_facts`. This doubly killed
     auto-memory for any user on a non-Anthropic backend (Ollama/Groq/OpenRouter)
     even after fixing bug 1.
  3. The pre-existing test suite (`tests/test_durable_fact_extraction.py`) always
     injected `_vault_factory=lambda: vault`, so it never exercised the real,
     no-factory production code path — which is exactly why this shipped silently.
- **Fix:** added `get_memory_vault()` to `src/hachi/core/memory_vault.py` — a
  pure, paths-only constructor (`MemoryVault(brain_dir=str(get_hachi_paths().data_dir))`)
  with NO import of `hachi.gateway` (the import-linter "engine must not import the
  gateway service" contract has no ignore entry for this module). Moved the
  process-shared-vault *preference* (reuse the live session's ChromaDB client
  instead of opening a second `PersistentClient`) into
  `build_job_context()`/`job_handlers.py` itself, which already has a frozen,
  allowed seam to `hachi.gateway.orchestrator` — it now tries
  `orchestrator._shared.vault` first and falls back to `get_memory_vault()`.
  Upgraded the swallowed-import log line from `logger.debug` to
  `logger.warning(..., exc_info=True)` so a future regression here is visible.
  Changed `extract_facts()`'s gate from `if not os.environ.get("ANTHROPIC_API_KEY")`
  to `if llm_client is None` — the client itself, not an Anthropic-specific env var,
  is the correct signal that extraction can run.
- **Avoid:** whenever a durable job handler's `build_job_context()`-style no-factory
  branch imports a "get the real service" function, grep to confirm that function
  actually exists before trusting a bare `except Exception: logger.debug(...)` to
  hide the truth — that pattern is exactly how BB-40 (and BB-42, found the same
  session) shipped silently. Any test that only ever exercises an injected
  `_factory=` path is NOT testing the real production code path — always add at
  least one test with no factory injected for the handler's actual no-argument
  resolution branch. Feature gates for "is an LLM client available" must check the
  resolved client object, never a single provider's env var.
- **Locked by:** `tests/test_durable_fact_extraction.py::test_build_job_context_resolves_real_vault_with_no_factory`,
  `::test_handle_extract_fact_no_vault_factory_writes_real_fact`, and
  `::test_extract_facts_does_not_require_anthropic_api_key_when_client_present`.

### BB-43 — Benchmark headline measured a failed query; the FPR gate was never run against the shipped corpus

- **Symptom:** the marquee "97.6% token savings" headline (README badge, `benchmark.md`,
  the frozen `s_real_results_v1.json`) actually measured Pass 2/3 costs of a **failed**
  skill load, not a real one. Separately, the benchmark's own CI gate
  (`skill benchmark --suite fast --json --threshold 0.80`) failed with exit 1 — FPR
  0.40 — the moment it was run against the actual bundled `default_skills` directory
  instead of a stale, previously-installed local copy.
- **Root cause:** three independent, compounding issues.
  1. Both the CLI (`skill.py::skill_benchmark`) and the pytest benchmark
     (`test_og_benchmark.py`) picked their "representative query" as either
     `list(engine._keyword_index.keys())[0]` or the first keyword on the first
     node — with no check that the result actually resolves. On the shipped corpus
     this picks the keyword `"persona"`, whose top search hit is the bare node name
     `identity` — defined once in `brain.og` **and once per `roles/*.og` file** (6
     nodes total). `resolve_node("identity")` refuses to pick one of 6 ambiguous
     matches and returns the sentinel string `"Error: Skill 'identity' not found in
     the loaded skills."` — 13 characters, estimated as 13 tokens. The benchmark
     then reported "97.6% savings" for measuring the length of an error message.
  2. `_prefix_matched_qids()` in `src/hachi/og_engine/engine.py` let indexed tokens
     as short as 2 characters act as *prefix sources* (its own docstring claimed a
     "3-char rule" while the actual constant, `_MIN_TOKEN_LEN`, was 2). The keyword
     "market cap" tokenizes to `["market", "cap"]`; the 3-char token `"cap"` then
     prefix-matched any query token starting with those letters, e.g. `"capacitor"`
     → `core_finance` — an unrelated false positive on a negative probe.
  3. The frozen `benchmarks/og_bench/data/s_real_results_v1.json` (`nodes: 53`,
     `run_date: 2026-06-13`) was never regenerated as `default_skills` grew to 31
     files / 60 total nodes (53 non-`brain.og` "skill" nodes). Nobody caught the
     drift because (a) the pytest threshold only asserts `savings >= 0.80`, not the
     specific headline number, and (b) a developer's own machine already had an
     older, 53-node copy bootstrapped into `~/.hachi/skills`, so `skill benchmark`
     (no `--dir`) silently passed there — `get_skills_dir()` only bootstraps fresh
     from the bundled `default_skills` package when no local copy exists yet (i.e.
     on a genuinely clean checkout, which is what CI actually runs).
- **Fix:**
  - Added `pick_representative_query(engine)` to `benchmarks/og_bench/metrics.py` —
    walks indexed keywords in stable order and returns the first one whose top
    search hit's `resolve_node()` does **not** start with `"Error:"`. Wired into
    both `skill.py::skill_benchmark` (exits 2 with a clear message if none resolve,
    instead of silently measuring a failure) and `test_og_benchmark.py` (skips with
    a clear reason).
  - Added a distinct `_MIN_PREFIX_SOURCE_LEN = 4` constant in `engine.py`, used only
    by `_prefix_matched_qids`'s length check — `_MIN_TOKEN_LEN` (2) is untouched so
    short *exact*-match keywords (e.g. `"qr"`) still index normally; only their
    eligibility as a *prefix source* for other query tokens is raised.
  - Reworded probe `n001` in `s_real_probes.json` (`"supercalifragilistic skill not
    in library"` → `"...gizmo not in repertoire"`) — the old wording's incidental
    use of the real word "skill" collided with the shipped `learning_plan` node's
    "skill development" keyword via an **exact** token match (not a prefix issue,
    so unaffected by the matcher fix); this is a probe-content fix, not an engine fix.
  - Regenerated `s_real_results_v1.json` from a live run against
    `src/hachi/default_skills` (`git d293c82`, 2026-07-04): 60 nodes, 97.8% savings
    (248 vs 11,183 tokens), P@5 = 1.00, FPR = 0.00 — all gates green. Updated
    `README.md` and `docs/reference/benchmark.md` to match (including the
    "53 default skills" wording, which conflated a node count with the actual
    31-file count).
- **Avoid:** never pick a "representative"/example query for a demo or benchmark by
  index-order alone — always assert the resolution actually succeeds, or average
  over a full probe set. When a skill library allows same-named nodes across files
  (an intentional feature — see `_bare_name_index`/qualified IDs), any code that
  surfaces a bare `name` from `search()` results and later calls `resolve_node(name)`
  must handle the ambiguous case, not assume success. Re-run gates that depend on
  "the skills directory" against the actual bundled/shipped path in a test, not just
  interactively on a developer machine that may have a stale local cache from a
  previous version.
- **Locked by:** `tests/test_og_benchmark.py::test_three_pass_beats_dump_baseline`
  (now asserts the resolved text doesn't start with `"Error:"`) and the new
  `::test_retrieval_quality_gate_on_shipped_corpus` (runs the real M1 gate against
  `default_skills`, not a mock); `tests/test_og_engine.py::test_prefix_match_does_not_over_match_short_tokens`.

### BB-44 — `_history` mutated/read without consistently holding `_history_lock` — background compaction races a live turn

- **Symptom:** audit finding H1 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md` §4 H1).
  `MemoryManager._history` is protected by a `_history_lock`, but that lock was only
  ever taken inside `_sliding_window_compact()`'s reassignment and
  `_apply_summary_to_history()`'s placeholder scan. `add_message()` (the append on
  every live turn), `apply_pending_compaction()` (the deferred skill-switch
  compaction meant to run "between turns"), and the `history` property (handed by
  reference to the LLM provider at `core/loop.py:979`) all read or mutated
  `self._history` with **no lock at all**. If a background compaction
  (`_sliding_window_compact`, lock-holding) and the deferred
  `apply_pending_compaction` (lock-free) ever ran concurrently — e.g. a live turn's
  `add_message()` trips the token/count-based sliding-window compaction on one path
  while `prepare_for_turn()` calls `apply_pending_compaction()` for a still-pending
  skill switch on another — both replace `self._history` wholesale
  (`self._history = <new list>`), so whichever reassignment lands second silently
  discards the other's result (last-writer-wins on the list reference, not a merge).
  This can drop an entire tool_use/tool_result pair the other thread had already
  retained, which the Anthropic API rejects with a 400 (or worse, silently corrupts
  context if only one side of the pair survives).
- **Root cause:** locking discipline was inconsistent, not absent — one compaction
  path (`_sliding_window_compact`) was correctly guarded, but a second, differently
  shaped read-modify-reassign of the same list (`apply_pending_compaction`) and the
  primary writer (`add_message`) were not, so the lock provided no real mutual
  exclusion for the actual race the audit describes. The `history` property also
  returned the live list object by reference rather than a point-in-time snapshot,
  so a caller (e.g. `core/loop.py` building `gen_kwargs["messages"]` before a
  streaming LLM call) could be handed a reference that a background thread later
  reassigns or whose retained Message objects a background thread mutates in place.
- **Fix:** `src/hachi/core/memory.py`:
  - `add_message()` (~L734) now appends under `with self._history_lock:`.
  - `apply_pending_compaction()` (~L785) now performs the boundary lookup, the
    old-messages read, and the final reassignment as one atomic critical section
    under `with self._history_lock:` — matching `_sliding_window_compact`'s existing
    shape. The task-ledger append (which has its own append-only semantics and isn't
    part of the `_history` invariant) stays outside the lock to keep the held time
    minimal.
  - The `history` property (~L709) now returns `list(self._history)` — a shallow
    snapshot copy taken under `_history_lock` — instead of the live list reference,
    so `core/loop.py` (and any other reader) always gets a consistent, point-in-time
    view that a concurrent compaction cannot reassign out from under it.
- **Avoid:** every read *and* every write of `MemoryManager._history` must hold
  `_history_lock` for the entire read-modify-write — a lock that only some of the
  mutators respect provides no real protection. Any public accessor that hands
  `_history` to a caller outside the class (especially one that survives past the
  call, like a provider request body) must return a locked snapshot copy, never the
  live list reference.
- **Locked by:** `tests/test_history_lock_race.py::test_concurrent_apply_pending_compaction_and_sliding_window_compact_dont_clobber`.

### BB-46 — Resilience/routing subsystem was decorative: breaker never re-opened, router health never updated, stream failover could double-bill, provider inference was hardcoded

- **Symptom:** audit finding H7 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md` §4 H7;
  DETAILED_FINDINGS.md core-agent M1/L2). Four related but distinct correctness gaps in
  `core/resilience.py` / `core/routing/router.py`:
  1. A circuit breaker that transitioned `open` → `half_open` after cooldown and then
     failed its recovery probe stayed stuck in `half_open` forever instead of reopening
     — `HealthRecorder.record_failure()`'s only breaker-opening guard was
     `self._breaker == "closed"` (`resilience.py:184`, old code), so a still-broken
     provider kept receiving probe traffic indefinitely.
  2. `AIProvider.update_health()` (defined on both `AnthropicProvider` and
     `OpenAICompatProvider`) had **zero real callers repo-wide** — grep confirmed only
     the two method definitions, no invocations. Real call outcomes never fed back into
     `provider.health()`, so `ModelRouter._resolve()`'s breaker filter
     (`_provider_usable()`, router.py ~L233/346) always read a permanently-default
     `ProviderHealth(breaker="closed")` regardless of actual failures.
  3. `ResilientClient.generate_stream`'s failover path called `self._call_with_chain(...)`
     on a mid-stream primary failure, but `_call_with_chain` unconditionally prepended
     `(self._inner, self._recorder)` — the very primary that just failed — as
     fallback[0]. A primary that fails after emitting partial output would be
     re-invoked and re-charged, risking double-printed text and double-billed cost.
  4. `_synthetic_descriptor()` (router.py ~L315, amendment A11 fallback for
     undeclared model ids) hardcoded `provider="anthropic"` unconditionally, so an
     unregistered OpenAI/Gemini/xAI model id would synthesize a descriptor pointing at
     the wrong provider adapter.
- **Root cause:** each sub-part was a narrow, independent gap in an otherwise-correct
  state machine/function — not a systemic design flaw: (1) a missing state transition,
  (2) a callback hook (`update_health`) that was defined speculatively but never wired
  to a real caller, (3) a fallback-chain builder reused verbatim for a code path where
  its "always include primary" assumption no longer holds, (4) a one-line hardcoded
  default that was never revisited once real non-Anthropic bundled models existed.
- **Fix:**
  1. `HealthRecorder.record_failure()` (`src/hachi/core/resilience.py:192-218`) now
     checks `self._breaker == "half_open"` first and reopens immediately on any failed
     probe (bypassing the consecutive-failure threshold, since one failed probe during
     recovery testing is decisive), falling through to the original `closed` → `open`
     threshold check otherwise.
  2. `HealthRecorder.__init__` (`resilience.py:162-176`) gained an optional
     `on_update: Callable[[ProviderHealth], None] | None` sink, invoked via a new
     `_notify()` helper (`resilience.py:221-230`, called outside the lock) at the end of
     both `record_success` and `record_failure`. `ModelRouter._get_recorder`
     (`src/hachi/core/routing/router.py:304-322`) now resolves the owning provider via
     `self._providers.get_by_name(provider_name)` and wires its `update_health` method
     (if present) as that sink — real outcomes now flow
     `resilient_call` → `HealthRecorder` → `provider.update_health()` → next
     `_resolve()`'s `provider.health()` read.
  3. `ResilientClient._call_with_chain` (`resilience.py:327-345`) gained an
     `include_primary: bool = True` keyword; `generate_stream`'s failover call site
     (`resilience.py:430-441`) now passes `include_primary=False` so the rebuilt chain
     starts at the fallbacks only, never re-invoking the primary that just failed
     mid-stream. Also fixed the failover-log `idx > 0` gate to account for the
     no-primary case.
  4. Added `_infer_provider()` (`router.py`, new helper) that pattern-matches the model
     id against the same naming families already used in `model-registry.json`
     (`claude-*` → anthropic, `gpt-*`/`o<N>*` → openai, `gemini-*` → google, `grok-*` →
     xai), falling back to `"anthropic"` only for genuinely unrecognised ids.
     `_synthetic_descriptor()` now calls it instead of hardcoding the provider.
- **Avoid:** a circuit breaker's `half_open` state must have its own failure-handling
  branch — never gate breaker-opening solely on `self._breaker == "closed"`, or
  recovery probes can never fail back to `open`. A `*_call_with_chain`-style fallback
  builder that unconditionally includes "the current client" must not be reused
  as-is for a failure path where that client has *already just failed* — add an
  explicit flag rather than assuming every caller wants the primary retried. A
  callback/hook method defined on a Protocol implementation but never actually wired
  to a real caller (`grep -rn update_health` before this fix showed 2 defs, 0 calls) is
  effectively dead code — grep for zero-caller methods when auditing a "wired-looking"
  subsystem. Hardcoded fallback defaults (`provider="anthropic"`) for anything
  multi-provider should be revisited whenever new provider families are added.
- **Locked by:** `tests/test_resilience.py::TestHealthRecorder::test_half_open_probe_failure_reopens_breaker`,
  `tests/test_resilience.py::TestStreamFailoverExcludesPrimary::test_stream_failover_does_not_reinvoke_primary`,
  `tests/test_routing_router.py::TestHealthFeedback::test_call_outcomes_update_provider_health`,
  `tests/test_routing_router.py::TestSyntheticDescriptorProviderInference` (6 cases).

### BB-47 — "Delete session" didn't cascade-delete the transcript; no periodic retention sweep exists

- **Symptom:** audit finding H8. Calling `SessionStore.delete_session(sid)` (and the
  bulk `delete_sessions_before(cutoff)` used by `hachi session clean`) removed the
  `sessions` row and `messages` rows, but left that session's `interaction_log` rows
  (full user_input/agent_output transcript, AUDIT P0-2) and `idempotency_keys` rows
  (cached full turn responses, AUDIT P0-3) behind in `sessions.db` — a "deleted"
  session's content was still fully recoverable via `get_interactions(session_id=...)`
  or a replayed idempotency key. Separately, `JobQueue.cleanup_completed()` (defined
  3x: abstract/`InMemoryJobQueue`/`SQLiteJobQueue` in `src/hachi/jobs/queue.py`) prunes
  only the `jobs` table and has **zero callers** anywhere in `src/` — no periodic sweep
  wires it in, and no equivalent retention logic exists at all for `daily_spend` or
  `CheckpointManager`'s edit-undo snapshots (`src/hachi/core/checkpoints.py` has no
  age/expiry concept whatsoever).
- **Root cause:** `delete_session`/`delete_sessions_before` were written when
  `messages` was the only child table of `sessions`; `interaction_log` and
  `idempotency_keys` were added later (AUDIT P0-2/P0-3) without updating the delete
  paths to cascade to them. There is no `FOREIGN KEY ... ON DELETE CASCADE` on either
  table (SQLite requires `PRAGMA foreign_keys=ON` *and* an explicit `ON DELETE CASCADE`
  clause — neither table declares one), so nothing enforces this at the schema level;
  it's a manual multi-DELETE responsibility that silently drifted out of sync.
- **Fix:** `SessionStore.delete_session` (`src/hachi/core/session_store.py:814`) and
  `SessionStore.delete_sessions_before` (`src/hachi/core/session_store.py:842`) now
  also `DELETE FROM interaction_log WHERE session_id = ...` and
  `DELETE FROM idempotency_keys WHERE session_id = ...` inside the same transaction,
  before the `sessions` row(s) are removed.
  Retention-sweep follow-up: investigated wiring `cleanup_completed()` into the
  worker idle loop (`_start_timeout_sweep`/`_start_eval_report_scheduler` in
  `src/hachi/gateway/orchestrator.py`, both daemon-thread sweep patterns already
  called from `boot_agent`) but did **not** wire it in this pass — `orchestrator.py`
  had substantial unrelated uncommitted WIP (a concurrent BB-45 scheduler-sharing fix)
  in the exact function body the new call would land in, and forcing an edit into
  actively-changing shared code risked a bad merge for that other in-flight task. Left
  un-wired; tracked as follow-up, not silently dropped.
- **Avoid:** whenever a new table is added that references `sessions.id` (or any
  other "owning" entity with a delete path), grep every existing `DELETE FROM
  <owner> WHERE id = ?` call site and add the matching child-table `DELETE` in the
  same transaction — don't rely on `PRAGMA foreign_keys=ON` alone; SQLite only
  cascades if the child table's `FOREIGN KEY` clause explicitly says
  `ON DELETE CASCADE`, which none of `session_store.py`'s tables declare. Before
  wiring a "just add the caller" fix into a shared orchestration file, check
  `git status`/`git diff` on that file first — if another task already has an
  uncommitted, non-trivial diff in the same function, stop and report rather than
  editing on top of it.
- **Locked by:** `tests/test_session_store_delete.py::test_delete_removes_interaction_log_rows`,
  `::test_delete_removes_idempotency_key_rows`,
  `::test_delete_cascade_leaves_other_sessions_interaction_log_intact`;
  `tests/test_session_clean.py::test_delete_sessions_before_removes_interaction_log_and_idempotency_keys`.
  Retention-sweep wiring: **not locked yet** — `cleanup_completed()` remains
  uncalled in `src/`; a future task should add a `_start_job_cleanup_sweep` (mirroring
  `_start_timeout_sweep`) once `orchestrator.py`'s WIP has landed, and separately
  design retention for `daily_spend` and checkpoint snapshots (no existing function to
  wire — new code, not a wire-in).

### BB-45 — Per-session `Scheduler` over one shared file: double-fires and clobbers writes

- **Symptom:** audit finding H3 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md` §4
  H3). `orchestrator.boot_agent` built a brand-new `Scheduler(ScheduleStore(...))` on
  **every** call (`src/hachi/gateway/orchestrator.py:2871`, old code) and a brand-new
  `ScheduleRunner` (`~L3487`) to tick it — one of each per gateway session — but all of
  them pointed at the exact same on-disk `get_hachi_paths().schedules_file`. Two
  sessions open at once (companion web UI + TUI, or two browser tabs) each held a
  private in-memory snapshot of the one shared file: a due cron/interval entry fired
  once per session's own `ScheduleRunner` (double-fire, double-billed/duplicated
  side effects), and any mutation made through one session's `Scheduler`
  (`set_enabled`/`cancel`/`mark_fired`) was invisible to a sibling session's stale
  copy — whichever session next persisted its own full snapshot silently clobbered
  the other's write (e.g. a user-disabled schedule could revert back to enabled).
- **Root cause:** `jobs/scheduler.py`'s `Scheduler.__init__` loads `ScheduleStore.load()`
  into an in-memory `dict[str, Schedule]` **exactly once** and never reloads before
  `due()`/`tick()`/`mark_fired()`/`set_enabled()` — by design, so it can be driven by
  an injected `now` for deterministic unit tests (see the class docstring's "Tick
  serialization guarantee", which only promises no double-fire *within one Scheduler
  instance*, never across two independent instances over the same file).
  `boot_agent` is called once per gateway session, and each call built a fresh
  `Scheduler`/`ScheduleRunner` pair — the exact same anti-pattern H2/BB-42 found for
  `SessionStore`, but for the schedule file instead of the session DB.
- **Fix:** added `_get_or_create_shared_scheduler(shared, schedules_file)` in
  `src/hachi/gateway/orchestrator.py` (~L2428) — mirrors the existing
  `ProcessSharedServices` pattern already used for `routing_store`/`event_bus`
  (`getattr(shared, "X", None) is None` → lazily attach once, `shared.X` thereafter).
  `boot_agent`'s scheduler construction (`~L2903`) now calls this helper against the
  `ProcessSharedServices` singleton (`_shared`) instead of constructing a private
  `Scheduler`, so every session in the process shares the one in-memory `Scheduler`
  object — there is only one copy of schedule state in memory, period, so nothing
  can diverge or get clobbered. Additionally, only the **first** session to boot in
  the process now starts the `ScheduleRunner` thread (`~L3541`, guarded by
  `getattr(_shared, "_schedule_runner", None) is None`); sibling sessions reuse the
  same running runner instead of starting a second thread that would call
  `tick()` concurrently on the shared `Scheduler` (which has no internal lock — two
  concurrent `tick()` calls could still race to fire the same due entry twice even
  with a single shared `Scheduler` object). The shared runner is intentionally never
  stopped by an individual session's `shutdown()` — only the owning session's
  `AgentSession._schedule_runner` is non-`None`, so only its `shutdown()` can stop
  it, matching how the shared vault/skill_engine/mcp_manager already outlive any one
  session. Declared `self._schedule_runner: Any = None` in `AgentSession.__init__`
  (was previously set only dynamically, with no declared field, unlike `_scheduler`).
- **Avoid:** any state that is backed by **one shared file/DB on disk** (schedules,
  sessions, routing config, cost ledgers) must have exactly **one** in-memory owner
  per process — never let `boot_agent` (or any other per-session boot path) construct
  a private in-memory wrapper object over shared on-disk state. Route it through
  `ProcessSharedServices` (`getattr(shared, "X", None) is None` → construct-once →
  `shared.X` reuse) the same way `routing_store`/`event_bus`/BB-42's
  `_get_shared_session_store()` already do. When the shared object also needs a
  background thread ticking it (a `*Runner`/sweep loop), guard the thread start the
  same way — only the first session starts it, and no individual session's
  `shutdown()` should stop a thread other live sessions depend on.
- **Locked by:** `tests/test_scheduler.py::TestSharedScheduleFileAcrossSessions` —
  `test_naive_per_session_scheduler_double_fires` /
  `test_naive_per_session_scheduler_clobbers_writes` reproduce the bug mechanism
  directly against the `Scheduler`/`ScheduleStore` primitives (two independently
  constructed `Scheduler`s over one file); `test_boot_agent_reuses_one_shared_scheduler_instance`,
  `test_boot_agent_shared_scheduler_does_not_double_fire`, and
  `test_boot_agent_shared_scheduler_mutation_is_visible_to_other_session` exercise
  the real fix — `orchestrator._get_or_create_shared_scheduler`, the exact helper
  `boot_agent` now calls — and were confirmed to fail (double-fire / clobbered
  write) when the fix was reverted to its naive per-call `Scheduler(...)` form.

### BB-48 — Facade sessions (OpenAI-compat / channel-inbound) and `/runs/*` skipped ownership

- **Symptom:** audit finding H6 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 H6). Sessions auto-created via `POST /v1/chat/completions` and
  `POST /channels/{channel}/inbound` were readable/postable by ANY bearer holder
  (not just whoever triggered their creation) — unlike sessions created through
  the normal `POST /sessions` flow, which stamps an owner immediately. Separately,
  `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/wake`, and `DELETE /runs/{id}`
  applied no owner filter at all, unlike `GET /sessions`/`_check_session_ownership`
  which already gate every other session-scoped route.
- **Root cause:** `GatewayControlPlane.get_or_create_session()`/`complete_chat()`
  (the facade helpers that power the OpenAI-compat and channel-webhook routes)
  call `self.create_session(...)` directly and never followed it with
  `set_session_owner(...)` — that stamping only happened in the `POST /sessions`
  FastAPI route handler itself (`fastapi_app.py`, right after `create_session`
  returns), so any code path that reached `create_session` through a different
  entry point silently produced an ownerless (NULL-owner) session, which the
  existing `_check_session_ownership`/`list_sessions` policy always treats as
  "accessible by any authenticated caller" (the documented backward-compat rule
  for legacy sessions — but facade sessions aren't legacy, they're brand new).
  The `/runs/*` routes were a separate, unrelated gap: they were added later
  (Initiative D, durable runs) without anyone porting the `_check_session_ownership`
  pattern over, even though `RunState.session_id` makes it trivial to do so.
- **Fix:**
  - `GatewayControlPlane.get_or_create_session()`/`complete_chat()`
    (`src/hachi/gateway/control_plane.py`) gained an `owner_token_hash: str | None
    = None` kwarg; when a NEW facade session is created, `set_session_owner()` is
    called on it immediately, mirroring the `POST /sessions` route.
  - `fastapi_app.py`'s `openai_chat_completions` (`/v1/chat/completions`, both the
    non-streaming `complete_chat` call and the streaming `get_or_create_session`
    call) and `channel_inbound` (`/channels/{channel}/inbound`) now resolve
    `caller_hash = _require_auth(request)` and forward it as `owner_token_hash`.
    For channel-inbound, ownership is stamped from the webhook caller's bearer
    token, NOT the attacker-controlled `sender_id` field embedded in
    `session_key = f"{channel}:{sender}"`.
  - Added `_check_run_ownership(run_session_id, caller_hash)` in `fastapi_app.py`
    (thin wrapper delegating to the existing `_check_session_ownership`) and wired
    it into `get_run`, `post_run_wake`, and `delete_run` (each already looks up the
    `RunState` and has `run.session_id` on hand); `get_runs` (the list route)
    applies the same in-memory owner filter `list_sessions` already uses,
    filtering out runs whose owning session belongs to a different caller.
- **Avoid:** any code path that calls `GatewayControlPlane.create_session()`
  outside the `POST /sessions` route handler MUST also call
  `set_session_owner()` (or forward `owner_token_hash` through, as
  `get_or_create_session`/`complete_chat` now do) — never assume a facade/helper
  session is "legacy" just because it wasn't created through the primary route.
  Whenever a new session-scoped resource collection is added (durable runs,
  future entities keyed by `session_id`), port the existing
  `_check_session_ownership` pattern to it in the same PR — don't let ownership
  enforcement be something only the original `/sessions` routes remember to do.
- **Locked by:** `tests/test_session_ownership.py::TestFacadeSessionOwnership`
  (`test_channel_inbound_session_is_owned_by_caller`,
  `test_openai_compat_session_is_owned_by_caller`) and
  `::TestRunsOwnershipFilter` (`test_list_runs_excludes_runs_owned_by_other_caller`,
  `test_get_run_forbidden_for_non_owner`, `test_wake_run_forbidden_for_non_owner`,
  `test_delete_run_forbidden_for_non_owner`).

### BB-49 — "Notion/Slack via OAuth" was a facade; the real mechanism is pasted API tokens

- **Symptom:** audit finding H5 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 H5). README claimed "Google Workspace, Notion, Slack — all via OAuth", and the
  `connector_registry.py` / integrations UI present Notion and Slack with a
  "Connect with OAuth" button (full authorize/token/callback flow, tokens stored
  in `OAuthTokenStore` under `oauth2.<connector>`). Connecting either through
  that flow produces a stored OAuth token that **nothing ever reads** — every
  Notion/Slack tool call still errors asking the user to paste a raw API token.
- **Root cause (confirmed by reading the actual call chain, not assumed):**
  `src/hachi/integrations/notion/service.py` (`NotionService.__init__`/
  `_ensure_api_key`) and `src/hachi/integrations/slack/service.py`
  (`SlackService.__init__`/`_ensure_token`/`_ensure_user_token`) authenticate
  every HTTP call using `CredentialVault.get_token("notion_api_key")` /
  `"slack_bot_token"` / `"slack_user_token"` — a completely separate credential
  namespace from `OAuthTokenStore` (`integrations/oauth_flow.py`, `oauth2.*`
  vault keys). `connector_registry.py` nonetheless declares both connectors
  `auth_type="oauth2"` with **no `credential_fields` fallback**, so the OAuth
  flow is the *only* UI path offered — the two systems (OAuth token storage vs.
  API-token consumption) simply never intersect. This is intentional-by-omission,
  not a regression: `tests/test_slack_notion_fixes.py` already exercises and
  locks the real API-token mechanism (`slack_bot_token`/`slack_user_token`/
  `notion_api_key` via `CredentialVault`), confirming the API-token path is the
  one actually wired end-to-end.
  `GatewayControlPlane`/`orchestrator.py`'s `_build_capability_registry`'s
  `cap_flags()` helper calls `OAuthTokenStore().is_connected(cap_id)` as a
  fallback to auto-enable the `slack`/`notion` capability flag when a token was
  stored via the OAuth UI (BB-11's pattern) — this method does exactly what its
  name and docstring say ("Return True iff a token is stored (does not validate
  expiry)") and is not itself buggy; it just means a user can end up with the
  capability "enabled" (tools registered) while the tools still fail at call
  time for lack of the real credential, which is the crux of the UI-facing
  facade this bug describes.
- **Scope decision (per audit + task instructions):** implement the HONESTY fix
  only — reword the false claim — not the full OAuth bridge (making
  `NotionService`/`SlackService` consume `OAuthTokenStore` tokens, or changing
  `connector_registry.py`'s `auth_type` for these two connectors to `apikey`).
  Either of those is a real behavior change to the OAuth start/callback routes
  and the integrations UI's button/dialog logic — bigger than a docs pass and
  explicitly out of scope for this fix.
- **Fix:** `README.md`'s "Native Integrations" bullet now reads "Google
  Workspace (Gmail, Drive, Calendar) via OAuth; Notion and Slack via pasted API
  tokens (`hachi secrets --set notion_api_key` / `slack_bot_token`/
  `slack_user_token`)" instead of "all via OAuth". No code change was needed in
  `orchestrator.py`/`is_connected` (verified not misleading — see root cause) or
  the frontend integrations page (`integrations.tsx`'s "Connect with OAuth"
  label is correctly data-driven off the connector's real `auth_type` field;
  the falseness lives in that field's value for these two connectors, which is
  the deliberately-deferred bridge, not a copy bug).
- **Avoid:** before reflexively "fixing" `is_connected`/similar predicate
  methods flagged by an audit, read their docstring and actual return value —
  a method can be completely honest about what it checks (token presence) while
  still being *used* in a way that produces a misleading end-to-end UX (BB-11's
  auto-enable fallback + a UI button offering the only-OAuth path for a
  connector whose service layer never reads OAuth tokens). Don't conflate "this
  method's semantics are wrong" with "this subsystem's design creates a UX
  facade" — the former is a code bug, the latter is a scoped product decision.
  If Notion/Slack OAuth consumption is ever built for real, wire
  `NotionService`/`SlackService` to call `OAuthTokenStore().load(connector_id)`
  as a fallback before/after `CredentialVault`, and only then flip
  `connector_registry.py`'s `auth_type` — don't advertise OAuth again until the
  services actually consume it.
- **Locked by:** docs-only correction — no regression test (per the task's own
  scope decision: "docs/copy-honesty fix, not a behavior fix"). The underlying
  API-token mechanism this entry documents as the *real* path is already locked
  by the pre-existing `tests/test_slack_notion_fixes.py`
  (`TestSlackUserTokenConsistency`, `TestNotionSearchWorkspacePagination`).

### BB-50 — ~85% of advertised slash commands didn't exist; truth-pass implemented 2, deleted the rest

- **Symptom:** audit finding H4 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 H4). README advertised 13 slash commands (`/clear /compact /new /sessions
  /model /memory /remember /forget /plan /deep-research /settings /setup
  /quit`); `fastapi_app.py`'s `_handle_slash_command` (the ONLY in-chat
  slash-command parser in the codebase — grepped, confirmed the TUI has no
  separate one and goes through the same gateway route) implemented only
  `/model` (display-only) and `/help`. Every other command returned `"Unknown
  command"`. The web composer additionally advertised a THIRD, mostly
  non-overlapping vocabulary (`/routine /dry-run /budget /plan /memory
  /sessions /model /delegate`) with the same problem — only `/sessions` had any
  real behavior (client-side: opens the session picker, never reaches the
  backend at all).
- **Root cause:** `_handle_slash_command` was built in one pass ("Step 7 —
  Minimal slash-command handler") implementing exactly two commands as a
  proof of concept, then the README/composer vocabularies were written
  aspirationally (or copied from an early design doc) without anyone auditing
  which commands actually had a registered `elif word == "..."` branch.
  `_handle_slash_command`'s reply shape (`{"response": str, session_id:
  str|None}` — see `SessionMessageResponse`) has no mechanism for triggering
  client-side navigation/state changes (opening a session picker, a settings
  panel, starting a new session), so commands like `/clear`, `/new`,
  `/settings`, `/setup`, `/quit` could never be implemented as slash commands
  in this handler's shape at all — they are inherently client-side UI actions,
  not "send text, get text back" round-trips.
- **Fix — per-command implement/delete decision** (implement only clear 1:1
  wins backed by an existing endpoint; delete the rest rather than
  half-implement, per CLAUDE.md):
  - **Implemented** (`src/hachi/gateway/fastapi_app.py`'s `_handle_slash_command`,
    ~L869-928): `/memory <query>` now calls the same `control_plane.memory_recall()`
    backing `GET /memory/recall` and renders the hits as text; `/remember <fact>`
    now calls the same `control_plane.add_memory_fact(group="user_profile", ...)`
    backing `POST /memory/facts`. Both return a usage hint when called with no
    argument instead of silently no-op'ing. `_SLASH_HELP_TEXT` updated to list
    them.
  - **Deleted** from `README.md`'s slash-command line and (where present) the
    frontend composer's `SLASH_ITEMS` (`frontend/src/components/conversation/ConversationComposer.tsx`):
    `/clear`, `/compact`, `/new`, `/plan`, `/deep-research`, `/settings`,
    `/setup`, `/quit` — no backing endpoint reachable from a text-reply-only
    slash handler, and building the client-side plumbing for each is
    non-trivial new work, not a wire-in. Also deleted the frontend-only fakes
    `/routine`, `/dry-run`, `/budget`, `/delegate` (zero backing anywhere).
  - **Deliberately NOT implemented** (flagged, not silently dropped):
    `/forget <query>` — `memory_recall()` does return a `fact_id` per hit, so
    wiring it to `delete_memory_fact()` is *technically* possible, but deleting
    a memory based on the single top semantic match to a natural-language
    query risks silently deleting the wrong fact — that's new confidence/
    disambiguation logic, not a 1:1 endpoint wire-in, so it was left out
    rather than shipped as a foot-gun.
  - **Kept** (already real, verified not fake): `/model` (display-only, real),
    `/help` (real), `/sessions` in the frontend list (real — client-side
    `handleSlashPick` special-case that opens the session picker without
    hitting the backend at all).
- **Avoid:** when a slash-command / chat-meta-command handler returns a fixed
  `{"response": str}` shape with no side-channel for UI navigation, any
  "command" that needs to open a panel, switch screens, or start a new session
  cannot be implemented server-side in that handler at all — it must be a
  client-side interception (like `/sessions`) or it doesn't belong in that
  vocabulary. Before advertising a slash command anywhere (README, help text,
  frontend composer list), grep the actual handler for a matching `elif word
  ==` branch — three independent vocabularies (README, `_SLASH_HELP_TEXT`,
  frontend `SLASH_ITEMS`) drifting out of sync with the real implementation
  and with each other is exactly how this shipped unnoticed for 11 of 13
  commands.
- **Locked by:** `tests/test_gateway_new_endpoints.py`
  (`test_slash_memory_returns_recall_results`,
  `test_slash_memory_without_query_returns_usage_hint`,
  `test_slash_remember_adds_a_fact`,
  `test_slash_remember_without_fact_returns_usage_hint`) — each was confirmed
  to fail against the pre-fix code (returned `"Unknown command"` instead of
  calling `memory_recall`/`add_memory_fact`). The README/composer deletions are
  docs/UI-copy corrections with no dedicated regression test (nothing to
  regress once the fake references are removed); the frontend's existing
  119-test vitest suite + `tsc --noEmit` confirm no other code depended on the
  removed `SLASH_ITEMS` entries.

### BB-52 — `move`/`copy` terminal builtins bypassed the write/delete permission tier; `ren`/`rename` were missing from `_EXFIL_STEMS`

- **Symptom:** audit finding M3 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M3, with a correction in `DETAILED_FINDINGS.md` downgrading it from the
  original agent's HIGH). The `mv`/`move` and `cp`/`copy` builtins inside
  `_raw_run_terminal_command` (`src/hachi/tools/os_tools.py`) resolved their
  own `src`/`dst` paths and called `shutil.move`/`shutil.copy2` directly,
  without ever calling `gate.check_path(dst, "write")` or
  `gate.check_path(src, "delete")`. `PermissionGate.check_command`'s
  `_EXFIL_STEMS` scan (`src/hachi/core/permissions.py`) only enforces
  `blocked_paths` for these stems — it does **not** consult the full
  read/write/delete permission tier (`allow_write`, `allow_delete`,
  `allowed_paths`). Concretely: a source path outside `allowed_paths` but not
  inside `blocked_paths` could still be `move`d (deleted from its original
  location) with no gate check at all, and a `copy` succeeded even when
  `allow_write=false`. Separately, `ren`/`rename` (both real Windows/Unix
  rename commands, and both already in `_SAFE_COMMANDS`) were entirely absent
  from `_EXFIL_STEMS`, so even the blocked_paths-only check never ran for
  them.
- **Root cause:** `check_command`'s `_EXFIL_STEMS`/`_check_path_args` path
  only ever checked `blocked_paths` (a deny-list), not the full
  `PermissionGate.check_path` decision tree (allowed_paths membership +
  allow_write/allow_delete). The `mv`/`cp` builtins never called
  `check_path` at all — unlike `cat`/`type`, which `_make_guarded_run_terminal`
  (UC-PERM-003, BB-era fix) already re-checks per-argument via `check_path`.
  `move`/`copy` were simply never given the same treatment when that pattern
  was introduced, and `ren`/`rename` were never added to `_EXFIL_STEMS` at
  all despite being listed in `_SAFE_COMMANDS`.
- **Fix:** `src/hachi/tools/os_tools.py`'s `_make_guarded_run_terminal`
  (~L477-556) now mirrors the existing `_CAT_STEMS` pattern for
  `mv`/`move`/`cp`/`copy`: after `check_command` passes, it resolves the last
  two non-flag argv tokens as `src`/`dst` (matching how
  `_raw_run_terminal_command` itself resolves them), then calls
  `gate.check_path(dst, "write")` and `gate.check_path(src, "delete")` (move)
  or `gate.check_path(src, "read")` (copy) before falling through to the raw
  executor — denying with `"Permission Denied: ..."` if either check fails.
  New `_COPY_STEMS`/`_MOVE_STEMS` frozensets (~L474-481) name the executables.
  `src/hachi/core/permissions.py`'s `_EXFIL_STEMS` (~L156-171) now also
  includes `"ren"` and `"rename"`.
- **Avoid:** any terminal builtin in `_raw_run_terminal_command` that resolves
  its own filesystem paths and performs a write/delete side effect (not just a
  read) must be paired with an explicit `gate.check_path(path, operation)`
  call in `_make_guarded_run_terminal` for **every** path it touches, using
  the operation that matches the actual side effect (`"write"` for the
  destination of a copy/move, `"delete"` for the source of a move that
  removes the original, `"read"` for a copy's source). `check_command`'s
  `_EXFIL_STEMS`/blocked_paths scan is a deny-list safety net, not a
  substitute for the full allow/deny permission-tier decision — don't assume
  "it's in `_EXFIL_STEMS`" means the full gate ran.
- **Locked by:** `tests/test_os_tools_hardening.py`
  (`test_ren_and_rename_are_recognized_as_exfil_stems`,
  `test_move_denied_when_source_outside_allowed_paths`,
  `test_copy_denied_when_write_disabled`,
  `test_copy_allowed_within_allowed_paths`,
  `test_move_allowed_within_allowed_paths_when_delete_enabled`) — the first
  three were confirmed to fail against the pre-fix code (`ren`/`rename`
  missing from `_EXFIL_STEMS`; a `move` from outside `allowed_paths` silently
  succeeded; a `copy` silently succeeded with `allow_write=false`), then the
  minimal gate wiring was added and all five pass, alongside the full
  `test_os_tools_hardening.py` module (18/18) and the broader
  `-k "os_tools or permission or exfil"` sweep (71 passed, 3 skipped).

### BB-53 — REST tool allowlist failed OPEN by default; resident scheduler's webhook delivery had no SSRF guard at all

- **Symptom:** audit finding M4 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M4). (1) With `HACHI_REST_ALLOWLIST` unset — the out-of-the-box state on
  every fresh install — `UniversalRestAdapter` let an `.og` skill's
  `::api`-defined REST tool call **any** public host; an unset allowlist was
  silently treated as "no restriction" rather than "nothing permitted". (2)
  `hachi.jobs.scheduler.deliver_result` (the resident/gateway path a recurring
  schedule's `deliver_to="webhook"` actually runs through) POSTed straight to
  `schedule.webhook_url` with zero SSRF checking — a `webhook_url` pointing at
  `169.254.169.254` (cloud metadata) or `127.0.0.1` (loopback) was requested
  without complaint, even though the separate CLI-only path
  (`cli/commands/schedule.py::_deliver_schedule_result`, used only by
  `hachi schedule run-due`) already called
  `net_guard.validate_outbound_url` first.
- **Root cause:** (1) `UniversalRestAdapter._validate_outbound_url` guarded the
  allowlist with `if self.allowed_hosts and not self._host_in_allowlist(...)`
  — an empty/unset `allowed_hosts` list made the whole `if` false, so the
  check was skipped entirely instead of denying. (2) `deliver_result` is the
  shared delivery function the resident scheduler/orchestrator was documented
  to call (see its own module docstring), but it was never wired to
  `hachi.core.net_guard.validate_outbound_url` — only the separate, CLI-only
  `_deliver_schedule_result` had that guard, so any deployment relying on the
  resident scheduler (not the CLI) had no SSRF protection on webhook delivery
  at all.
- **Fix:** `src/hachi/core/rest_adapter.py` (`_validate_outbound_url`,
  ~L131-142) — an empty/unset `allowed_hosts` now unconditionally denies with
  a "HACHI_REST_ALLOWLIST is not configured (fails closed …)" message before
  any host-specific or net_guard check runs; the allowlist membership check
  only executes once an allowlist actually exists. `src/hachi/jobs/scheduler.py`
  (`deliver_result`, webhook branch ~L448-469) now calls
  `hachi.core.net_guard.validate_outbound_url(url)` before POSTing and returns
  early (with a `logger.warning`) if it's not `.ok` — mirroring the CLI path's
  existing guard so both delivery routes share the same SSRF posture.
- **Avoid:** an allowlist gate must fail CLOSED on empty/unset config — never
  write `if allowlist and host not in allowlist: deny` as the *only* check;
  that pattern silently no-ops (allows everything) when the allowlist is
  empty. Always check "is the allowlist itself configured at all?" as a
  separate, unconditional first branch. When two code paths perform the same
  outbound network action (here: CLI `schedule run-due` vs. the resident
  scheduler's `deliver_result`), grep for the other path's existing safety
  guard and reuse it — don't assume "the CLI already checks this" also covers
  the gateway/resident path.
- **Locked by:** `tests/test_ssrf_security.py::TestRestAdapterSsrfDelegation::test_unset_allowlist_env_fails_closed`
  (confirmed pre-fix that an unset `HACHI_REST_ALLOWLIST` let a request to an
  arbitrary public host proceed to net_guard instead of being denied);
  `tests/test_scheduler_hardening.py::TestDeliverResult::test_ssrf_unsafe_webhook_url_is_not_posted`,
  `::test_loopback_webhook_url_is_not_posted`, `::test_ssrf_unsafe_webhook_url_logs_warning`
  (confirmed pre-fix that `deliver_result` POSTed to a cloud-metadata and a
  loopback `webhook_url` with no guard at all). Six pre-existing tests
  (`test_ssrf_security.py`, `test_phase0_security_hardening.py`,
  `test_rest_injection_guard.py`, `test_rest_outbound_secret_guard.py`,
  `test_rest_response_trimming.py`) that constructed `UniversalRestAdapter`
  with no/empty `allowed_hosts` to reach net_guard/injection/redaction/trimming
  behavior unrelated to the allowlist itself were updated to pass an explicit
  matching-host allowlist entry, since a fail-closed default means "no
  allowlist" can no longer stand in for "no restriction" in those setups.

### BB-55 — Snapshot/recent-facts read paths injected stored memory into the system prompt without MemoryGuard redaction

- **Symptom:** audit finding M8 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M8). `MemoryVault.get_user_snapshot()`, `get_agent_snapshot()`, and
  `get_recent_facts()` read raw documents straight out of ChromaDB and inject
  them verbatim into the system prompt (user profile snapshot, agent persona
  directives, and the session-start recency probe respectively) — none of the
  three ran the content through `memory_guard.scan()` before injection. Every
  *search* path (`semantic_search`, `search_user_profile`,
  `search_delegations`, `search_episodic`) already redacts via
  `_redact_results()`, so the guard was applied inconsistently: content that
  reached storage by any route other than `_guarded_write` (e.g. written
  before the guard existed, restored from a backup/import, or written via a
  path that bypassed `_guarded_write`) would be served unredacted whenever it
  was read back through one of these three accessors, even though the exact
  same content would have been screened had it come back through search.
- **Root cause:** `get_user_snapshot`/`get_agent_snapshot`/`get_recent_facts`
  were written purely as ChromaDB `.get()` formatters (FIX 2's unbiased
  recency accessor and the two persona/profile snapshot builders) with no
  awareness that `memory_guard.scan()` exists as a read-time safety net
  elsewhere in the file — the guard was treated as a write-time-only concern.
- **Fix:** `src/hachi/core/memory_vault.py` — added `_guard_filter_docs()`
  (~L220), a small helper that runs `guard_scan()` over a list of raw
  documents and drops any that fail, logging a `WARNING` per drop (mirrors
  the existing `_guarded_write` log format). Wired into all three read paths:
  `get_recent_facts` (~L1213-1216, filters before the `[:limit]` slice so a
  dropped entry doesn't shrink the returned count below what was actually
  available), `get_user_snapshot` (~L1399-1410, inline per-doc check inside
  the `category` zip loop so doc/category pairing stays aligned, returns `""`
  if every doc was filtered), and `get_agent_snapshot` (~L1488-1500, same
  inline pattern inside its `zip(documents, metadatas, ids)` loop). Also
  toned down `src/hachi/core/memory_guard.py`'s module docstring, which
  previously read as if the scanner were a comprehensive/obfuscation-resistant
  classifier — now explicitly states it is a small English-language regex
  heuristic, not resistant to non-English phrasing/homoglyphs beyond NFKC/
  base64, and one signal among several (per M8's explicit note not to expand
  or rewrite the blocklist itself).
- **Avoid:** when a security scan/redaction step exists, audit **every** read
  path that surfaces the same underlying stored content into a prompt or
  response — not just the "obvious" one (here: `search_*`). A guard applied
  only at write time is not equivalent to a guard applied at read time: data
  written before the guard existed, imported, or written through any path
  that skips the guarded writer will sit in storage unredacted forever unless
  reads also re-check it. When formatting doc+metadata pairs from a
  `zip()`/`enumerate()` loop, filter inline inside the loop (not by
  post-filtering just the doc list) so paired fields never drift out of
  alignment.
- **Locked by:** `tests/test_memory_fixes.py::TestSnapshotAndRecentFactsRedaction`
  (`test_get_user_snapshot_redacts_guard_flagged_content`,
  `test_get_agent_snapshot_redacts_guard_flagged_content`,
  `test_get_recent_facts_redacts_guard_flagged_content` — each plants a
  `guard_scan`-flagged document directly into a fake collection and confirms
  it is now excluded from the returned snapshot/list;
  `test_get_user_snapshot_still_returns_safe_content` locks that ordinary safe
  facts are unaffected).

### BB-51 — JSON state stores self-wiped on a torn write; corrupt reads could cascade into an overwrite of good data

- **Symptom:** audit finding M1 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M1). None of `secret_store.py`'s `_MetadataStore`/`EncryptedFileSecretStore`,
  `onboarding.py`'s `OnboardingService.save_state`, or the OG engine's
  `skill_usage.json` writer (`SkillEngine._save_usage`) wrote atomically — each
  called `Path.write_text(...)` directly on the live file. A crash/kill/full-disk
  mid-write leaves a truncated or empty file on disk (a "torn write"). Worse,
  every one of these stores' *read* paths caught any `json.JSONDecodeError`/
  generic parse exception and silently returned an empty dict / default model —
  with no record that the file had ever been corrupt. Combined, this is a
  self-wipe cascade: a corrupt read silently resets in-memory state to empty,
  and the very next legitimate write (`upsert`/`set`/`save_state`/`record_use`)
  persists that empty state, permanently destroying whatever was on disk before
  the crash — with zero trace that data loss occurred.
- **Root cause:** each store independently hand-rolled its own "write the
  file" logic with a plain `write_text`, and its own "read the file" logic
  with a bare `except Exception: return {}` — there was no shared atomic-write
  helper anywhere these JSON state files are written, unlike
  `hachi.jobs.scheduler.ScheduleStore.save` and
  `hachi.core.checkpoints.CheckpointManager._save_index`, which already did
  this correctly (temp file in the same directory + `os.replace`, atomic on
  both POSIX and Windows). The corrupt-read handlers never flagged/quarantined
  the bad file before returning the default, so there was nothing to prevent
  the following write from clobbering it.
- **Fix:** new shared helper module `src/hachi/core/atomic_io.py` —
  `atomic_write_json(path, payload)` (temp file via `tempfile.mkstemp` in the
  same parent directory + `os.replace`, copying the exact pattern already used
  by `ScheduleStore.save`/`CheckpointManager._save_index`) and
  `quarantine_corrupt_file(path)` (renames an unparseable file to
  `<path>.corrupt-<unix-ts>` and logs a `WARNING`, returning the quarantine
  path). Wired into every JSON-state write/read site found by grep:
  `src/hachi/core/secret_store.py` — `_MetadataStore._load`/`_save` (~L44-57),
  `EncryptedFileSecretStore._read_blob` (~L302-311) and `_encrypt_all`'s write
  (~L342-353, the exact lines flagged by the audit); `src/hachi/core/onboarding.py`
  — `OnboardingService.resume_state`/`save_state` (~L172-187); and
  `src/hachi/og_engine/engine.py` — `SkillEngine._load_usage`/`_save_usage`
  (~L1681-1699, the `skill_usage.json` writer). Every corrupt-read branch now
  calls `quarantine_corrupt_file()` **before** returning the empty/default
  value, so the bad file is preserved on disk (inspectable, recoverable) and
  can never be silently overwritten by whatever write happens next.
- **Avoid:** any JSON-backed state file must be written via
  `hachi.core.atomic_io.atomic_write_json` — never a bare `Path.write_text`ing
  of a live path — and any read path that swallows a parse error must call
  `quarantine_corrupt_file()` on that path *before* returning a default/empty
  value, so a corrupt read can never cascade into a write that permanently
  destroys the pre-crash data. Copy this pattern (already correct in
  `ScheduleStore`/`CheckpointManager`) rather than hand-rolling a new one.
- **Locked by:** `tests/test_atomic_state_writes.py` — `TestAtomicWriteJson`
  and `TestQuarantineCorruptFile` unit-test the shared helpers directly
  (including simulating a crash via `patch("os.replace", side_effect=OSError)`
  and confirming the original file survives untouched with no leftover temp
  file); `TestMetadataStoreSelfWipe`, `TestEncryptedFileSecretStoreSelfWipe`,
  `TestOnboardingStateSelfWipe`, and `TestSkillUsageSelfWipe` each reproduce
  the exact self-wipe cascade end-to-end against the real store classes
  (corrupt file → read → confirm quarantined-not-clobbered; simulated crash
  during a second write → confirm the first write's data survives).

### BB-54 — Malformed/truncated tool-arg JSON silently executed with `input={}`; streamed tool_use_ids could collide

- **Symptom:** audit finding M7 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M7; `DETAILED_FINDINGS.md` core-agent M3/M4). When an OpenAI-compatible
  provider's tool-call `arguments` JSON arrived malformed or was cut off
  mid-object (e.g. a `max_tokens` stop landing inside a tool call), both
  `OpenAICompatibleClient._parse_tool_calls` (non-streaming) and
  `generate_stream`'s SSE tool-call-fragment reconstruction caught the
  `json.loads` failure and silently fell back to `input={}` — the `ToolCall`
  looked exactly like a normal, successfully-parsed call with no arguments, so
  `ToolRegistry.execute` ran the real tool with the wrong (empty) arguments
  instead of failing. Separately, some providers stream an empty (`""`) or
  constant `tool_use_id`; `_parse_tool_calls`'s old fallback
  (`raw_call.get("id", "tool_call")`) also returned `""` unchanged for that
  case (`.get(key, default)` only applies `default` when the key is *missing*,
  not when it's falsy), and the streaming accumulator's `tc_acc[idx]["id"]`
  stayed `""` whenever the provider never sent a non-empty id fragment. Two
  tool calls in the same response sharing that `""`/constant id would then
  collide when `ExecutionLoop.run` pairs them up via `_futures: dict[str, ...]`
  keyed on `tool_call.id` (`src/hachi/core/loop.py` ~L1167-1223) — the second
  call's future/result silently overwrites the first's. There was also no way
  for a caller to distinguish a clean completion from a `max_tokens` cutoff
  mid-tool-call, since neither client surfaced the provider's stop/finish
  reason on `LLMResponse` at all.
- **Root cause:** both JSON-parse call sites treated `except: args = {}` as a
  safe default instead of a visible failure, conflating "the model deliberately
  called this tool with no arguments" with "the argument payload never
  finished arriving." The id-fallback used `dict.get(key, default)`, which
  does not substitute the default for an empty-but-present string. Neither
  client read/forwarded the provider's `stop_reason`/`finish_reason`.
- **Fix:** `src/hachi/core/llm.py` — `ToolCall` gained a `parse_error: str |
  None` field (~L93-101) and `LLMResponse` gained `stop_reason: str | None`
  (~L104-111). `OpenAICompatibleClient._parse_tool_calls` (~L579-613) now logs
  a `logger.warning` with the tool name and raw argument string on a JSON
  decode failure and sets `parse_error` instead of silently keeping `input={}`
  as if it were valid; the id fallback is now `str(raw_call.get("id") or "")
  or _synthesize_tool_call_id()` so an empty/missing id is replaced with a
  fresh `uuid4`-based id (new module helper `_synthesize_tool_call_id()`,
  ~L26-35) rather than passing through unchanged. `generate_stream`'s
  reconstruction loop (~L744-777) applies the identical parse_error/logging/
  id-synthesis treatment to the accumulated SSE fragments, and now also
  captures each chunk's `choices[0].finish_reason` into `final_stop_reason`,
  returned as `LLMResponse.stop_reason`. `OpenAICompatibleClient.generate`
  (non-streaming, ~L657-666) and `AnthropicClient._parse_message` (~L349-372,
  reading the SDK message's `stop_reason`, guarded to only accept a real `str`
  so an unconfigured test double doesn't fail Pydantic validation) both now
  populate `stop_reason` too. `src/hachi/core/loop.py`'s
  `ToolRegistry.execute` (~L330-355) gained a guard clause: a `ToolCall` with
  `parse_error` set raises a `ValueError` *before* the tool function is ever
  invoked, which routes through the existing `except Exception` →
  `is_error=True` tool_result path in `_execute_single_tool`/`run()` — no
  other change to the loop's control flow was needed. (Note: the task's
  originally-cited `src/hachi/core/routing/registry.py` — `ModelRegistry`, the
  bundled/provider/config model-descriptor registry — has no tool-call
  parsing or pairing logic at all; the actual pairing-by-id code lives in
  `core/loop.py`, confirmed by reading both files before making any change.)
- **Avoid:** never let a parse/decode failure produce a value that is
  indistinguishable from a legitimate empty result (`args = {}` on exception
  looks identical to a real no-argument tool call) — carry the failure forward
  as an explicit, checkable field and fail that specific unit of work loudly
  instead of continuing as if it succeeded. When falling back to a
  placeholder id/value from an optional provider field, use `x or default`
  (or an explicit emptiness check), not `dict.get(key, default)` — `.get`'s
  default only fires on a *missing* key, not a present-but-falsy one. Anything
  paired up later by an id supplied by an external provider must treat a
  missing/empty id as "needs a locally-synthesized unique id," never as "use
  the empty string as-is."
- **Locked by:** `tests/test_streaming.py::test_openai_generate_malformed_tool_json_sets_parse_error`,
  `::test_openai_stream_truncated_tool_json_sets_parse_error`,
  `::test_openai_stream_empty_tool_use_id_gets_synthesized_unique_ids`,
  `::test_anthropic_generate_surfaces_stop_reason`,
  `::test_openai_generate_surfaces_finish_reason`,
  `::test_openai_stream_surfaces_finish_reason`;
  `tests/test_e2e_loop.py::test_tool_call_with_parse_error_fails_instead_of_running_with_empty_input`
  (confirmed pre-fix that a `ToolCall` carrying a `parse_error` still reached
  and executed the real tool function with empty arguments; confirmed
  post-fix it now raises before the tool runs and surfaces as
  `is_error=True` in history, exactly like a real tool exception).

### BB-59 — `save_skill` wrote lint-invalid skills to disk (M2)

- **Symptom:** `SkillEngine.upsert_skill` could write and hot-load a skill with an
  empty `::dense` block — `validate_dense("")` passes (0 tokens ≤ the 30-token
  budget), so the only pre-write check available never fired. The write-path's
  own post-write `lint_og_file()` call *did* detect this as a `missing-dense`
  lint **error**, but the code only ever surfaced `warning`/`info` issues as
  advisory feedback — errors were silently discarded, so a lint-invalid skill
  still landed on disk and stayed hot-loaded. This directly undermined the
  "lint bounds what the agent may write" governance claim in README.md.
- **Root cause:** lint ran *after* the atomic write instead of gating it, and
  its result was filtered to advisory-only levels with no error branch.
- **Fix:** `upsert_skill` now lints the *temp* file before `os.replace()`
  promotes it into place; any `error`-level lint issue aborts the write
  (`{"status": "rejected", "lint_errors": [...]}`), deleting the temp file and
  never hot-loading it. Also added a small load-time nudge: `resolve_node`'s
  Pass-3 assertions block now names `check_skill_assertions(name=..., params=...)`
  directly in the render (previously that instruction only lived in
  `brain.og`'s system prompt, one layer removed from the actual skill load).
  Deliberately did **not** build a runtime enforcement engine that blocks tool
  execution on assertion failure — out of scope per the audit's own minimal-fix
  recommendation; `evaluate_assertions`/`check_skill_assertions` already exist
  as a real, tested, deterministic (non-`eval`) checker the agent can call.
- **Avoid:** any new skill-write path must lint the content and reject on
  `error`-level issues *before* the file is promoted/hot-loaded — never lint
  only after the fact and only surface non-error levels.
- **Locked by:** `tests/test_og_skill_authoring.py::test_lint_errors_reject_the_write`,
  `tests/test_og_engine.py::test_load_time_nudges_to_check_skill_assertions`.

### BB-56 — Cost-accounting edges: fictional pricing for unrecognised/local models, local-vs-UTC date skew, silently dropped negative deltas

- **Symptom:** audit finding M14 (`docs/audit/2026-07-03/PRODUCTION_READINESS.md`
  §4 M14). Three independent, compounding correctness gaps in
  `src/hachi/core/cost.py` (and its one call site in
  `src/hachi/gateway/orchestrator.py`):
  1. Any model id with no entry in `MODEL_PRICING` and no matching registry
     descriptor — most notably an Ollama-served local model
     (`OpenAICompatProvider.models()` returns `[]` for `kind="ollama"`, so no
     descriptor is ever registered for it) — priced at `_DEFAULT_PRICING =
     (1.0, 5.0)` USD/Mtok. A genuinely free local model could therefore
     accumulate a fabricated non-zero "cost" and trip a user's daily spend cap
     on usage that cost nothing.
  2. `record_voice_usage`/`record_background_usage` keyed the daily-spend
     ledger with `datetime.date.today().isoformat()` (host **local** time),
     while `AgentSession._daily_cap_exceeded`/the per-turn recording block in
     `orchestrator.py` independently did the same with their own
     `date.today()` call. Every one of those calls resolves in the host's
     local timezone, not UTC — a user running the gateway outside UTC (e.g.
     IST, UTC+5:30) has spend near local midnight land on the wrong ledger
     date relative to a UTC-anchored day boundary, silently splitting or
     merging a day's total incorrectly depending on which side of the actual
     UTC-day boundary a given call's local wall-clock landed on. **This bug
     reproduced live during this session's own test run**: the pre-existing
     `tests/test_daily_cap_enforcement.py` fixtures wrote spend via
     `datetime.date.today().isoformat()` (local); once the code was fixed to
     read via UTC, those fixtures' writes landed on a different day than the
     UTC-based read the instant local and UTC dates diverged (crossing local
     midnight IST while still on the prior UTC day) — 5 tests failed for
     exactly the reason this bug describes, not because of a mistake in the
     fix.
  3. `orchestrator.py`'s per-turn cost-recording block computed
     `turn_delta = snap.estimated_cost_usd - self._last_recorded_cost_usd` and
     silently clamped/skipped a negative delta (`_turn_cost_usd = max(0.0,
     turn_delta)` for the per-turn log, `if turn_delta > 0:` guarding the
     ledger write) — technically safe (never records negative spend), but a
     negative delta is not supposed to happen (cost is monotonic within a
     tracker's lifetime); it only occurs after some kind of cost-tracker
     regression (e.g. a mid-session reset). Dropping it with **no trace at
     all** hid a real anomaly instead of surfacing it.
- **Root cause:** (1) `_DEFAULT_PRICING` was a leftover "better than crashing"
  guess from before any provider could report per-token cost as genuinely
  unknown — but the module already has a convention for "unknown pricing"
  (`ModelDescriptor.pricing: Pricing | None`, where `None` means "cost
  unknown," honoured correctly by `ModelRegistry.pricing_for_model`); the
  fallback constant contradicted that convention by inventing a non-zero
  number instead of treating "no pricing found anywhere" as "$0 known cost."
  (2) the daily-spend ledger's write side (`cost.py`) and read side
  (`orchestrator.py`'s cap check) each independently called
  `datetime.date.today()`/`date.today()` — nothing enforced that both sides
  resolve the same instant to the same date string, and neither used an
  explicit timezone. (3) the `max(0.0, ...)` / `if turn_delta > 0:` guards
  were written purely to keep the ledger non-negative; nobody added a log
  line for the "this shouldn't happen" branch, so the previous behaviour was
  indistinguishable from "everything is fine."
- **Fix:**
  - `src/hachi/core/cost.py`: `_DEFAULT_PRICING` (~L47) changed from
    `(1.0, 5.0)` to `(0.0, 0.0)` — an unrecognised model id now prices at $0,
    consistent with the existing "pricing unknown → 0 known cost" convention
    elsewhere in this module.
  - Added `today_utc_str()` (~L112) — `datetime.datetime.now(datetime.UTC).date().isoformat()`
    — and rewired `record_voice_usage`/`record_background_usage` (~L222, ~L300)
    to call it instead of local `datetime.date.today().isoformat()`.
    `src/hachi/gateway/orchestrator.py`'s `_daily_cap_exceeded` (~L1535) and the
    per-turn recording block (~L1707) now import and call the same
    `today_utc_str()` helper, so every reader and writer of the daily-spend
    ledger resolves the same UTC day boundary — removed the now-unused
    `from datetime import date as _date` import.
  - Added `clamp_nonnegative_cost_delta(delta_usd, *, context)` (~L132) —
    clamps a negative delta to `0.0` **and** logs a `warning` (previously
    nothing was logged). `orchestrator.py`'s per-turn recording block (~L1699)
    now calls this instead of the bare `max(0.0, turn_delta)`, so a
    tracker-reset-mid-session anomaly is visible in logs instead of invisible.
  - `tests/test_daily_cap_enforcement.py`'s fixtures (`today = datetime.date.today().isoformat()`,
    6 call sites) were updated to `today = today_utc_str()` — they must write
    to the same UTC-keyed bucket the fixed code now reads from.
- **Avoid:** an "unknown/unpriced" fallback must default to the same
  semantics the rest of the pricing system already uses for "cost unknown" —
  never invent a nonzero guessed price for a model nobody actually priced;
  a fabricated bill on a genuinely free/local model can trip a real spend cap.
  Any code that reads AND writes the same daily/periodic ledger must derive
  its date key from one shared, timezone-explicit helper (UTC) — never let
  two independent call sites each call bare `date.today()` and assume they
  agree; this includes TEST FIXTURES that seed a ledger for a test to read
  back — a fixture using local `date.today()` against UTC-keyed production
  code is itself a latent, time-of-day-dependent flake. A cumulative metric
  that "should" be monotonic (cost, tokens) going negative is a signal worth
  logging, not just clamping — silently dropping an impossible value with no
  trace makes a real regression undebuggable later.
- **Locked by:** `tests/test_cost_tracking.py::test_unknown_model_prices_at_zero_not_a_fictional_default`,
  `::test_cost_tracker_records_zero_cost_for_unknown_local_model`,
  `::test_today_utc_str_uses_utc_not_local_date`,
  `::test_record_background_usage_keys_daily_ledger_by_utc_date`,
  `::test_clamp_nonnegative_cost_delta_clamps_and_logs`,
  `::test_clamp_nonnegative_cost_delta_passes_through_positive`; the
  pre-existing `::test_pricing_longest_prefix_match` was updated in place
  (its "unknown model" assertion encoded the exact bug being fixed — the
  fallback value itself, not the lookup mechanism, was under test).
  `tests/test_daily_cap_enforcement.py` (all 13 tests) re-verified green after
  switching its fixtures to `today_utc_str()`.

### BB-57 — `GET /config` echoed unmasked secret refs / raw header values

- **Symptom:** `GET /config` returned the raw `ResolvedConfig.model_dump()` verbatim —
  `provider.api_key_ref` / `api_key_env` (env-var and vault-ref names), `providers.*`
  (same), and raw `headers` values (e.g. a live `Authorization: Bearer ...` token) were
  all echoed back to any caller, and `capabilities.*.secret_ref` leaked vault-key names.
  Inconsistent with the already-masked `GET /config/providers`.
- **Root cause:** `_InProcessGatewayRuntime.get_config()` (`cli/main.py`) dumped
  `ResolvedConfig` straight to JSON with no redaction step, while the sibling
  `GET /config/providers` route went through `provider_admin._mask_provider()`
  (drops `api_key_ref`/`api_key_env` down to a `configured` boolean, replaces header
  *values* with `"***"`). Two endpoints serializing the same underlying secrets with
  two different (one masked, one not) code paths.
- **Avoid:** never add a second serializer for a config/settings object that contains
  secret-shaped fields (`*_ref`, `*_env`, `headers`, `secret_ref`) — route ALL such
  serialization through the one existing masking helper (`provider_admin._mask_provider`
  for providers; extend it, don't bypass it, for new secret-shaped fields).
- **Locked by:** `tests/test_gateway_new_endpoints.py::test_get_config_masks_provider_secrets`,
  `::test_get_config_endpoint_masks_secrets_via_http`.

### BB-58 — OpenAI-compat endpoint ignored the requested `model`; one global rate-limit bucket

- **Symptom:** (a) `POST /v1/chat/completions` accepted any `model` string, never
  validated it, and only echoed it back in the response's `model` field — the actual
  agent turn always ran on the session's already-booted model regardless of what was
  requested, with no error if the model was nonsense. (b) `openai_limiter.allow("openai")`
  used the hardcoded literal `"openai"` as its rate-limit key for every caller, so one
  caller exhausting the sliding-window limit locked out every other caller sharing the
  same gateway instance.
- **Root cause:** (a) `model_name = payload.model or "hachi"` was computed only for
  display, never checked against anything. (b) the rate limiter key was a constant
  instead of a per-caller identity.
- **Avoid:** (a) when a request carries a caller-selectable `model`, validate it against
  the real allowlist (`control_plane.list_all_models()`) before running the turn — reject
  unrecognized models with 400 instead of silently substituting a default; fail open only
  when there is genuinely no allowlist data to check against (handler not wired). (b) any
  shared `RateLimiter` on an externally-reachable route must be keyed by the resolved
  caller identity (the same `caller_hash` from `_require_auth` that H6 uses for session
  ownership), never by a route-name constant — a constant key always degrades to one
  global bucket no matter how many distinct principals call it.
- **Locked by:** `tests/test_gateway_openai_channels.py::test_openai_chat_rejects_unknown_model`,
  `::test_openai_chat_accepts_known_model`, `::test_openai_chat_no_allowlist_data_does_not_reject`,
  `::test_openai_chat_rate_limit_is_keyed_per_caller`.

### BB-60 — TUI Cockpit chat right-rail rendered hardcoded demo plan/approval data (L4)

- **Symptom:** the Textual Cockpit's Chat view right rail always showed a fixed 5-step "plan"
  (search sources / read top 5 articles / …), a fake `skill research-protocol` line, and
  "⚠ 1 approval waiting / browse_web (researcher)" — even in live mode with a real gateway
  session that had zero pending approvals or a completely different tool pending.
- **Root cause:** `ChatView._render_rail()` in `src/hachi/tui/cockpit/views/chat.py` built the
  rail purely from module-level literals (`_PLAN_STEPS`, the skill string, the approval card
  text) and never called `CockpitData.approvals()` — even though that method already existed
  and was already used correctly by `ApprovalsView` (`views/approvals.py`). No gateway data
  model exists for a live per-turn "plan" at all (confirmed: no such field on `ConfigSnapshot`/
  `SessionInfo`; frontend `run.tsx` hides its own Plan section for the identical reason — "live
  mode emits no plan events").
- **Avoid:** any view field that claims to reflect session state must be sourced from a
  `CockpitData` method (which itself falls back to `placeholder_*()` offline) — never a bare
  module-level literal. When no live data model exists for a demo field (e.g. a "plan"), gate
  it behind `CockpitData.is_live` and omit it live rather than fabricating steps; don't invent a
  new backend model to fill the gap without discussing scope first.
- **Locked by:** `tests/test_cockpit_chat_live.py::TestChatViewOffline::test_rail_reflects_real_pending_approval`,
  `::test_rail_shows_no_approvals_when_none_pending`.

### BB-61 — Icon registry silently renders blank `<svg>` for unregistered names (L2)

- **Symptom:** `SpendSection.tsx`'s "Breakdown" heading and `memory.tsx`'s recall button showed
  no icon at all — an empty space where the icon should be, no console warning, no crash.
- **Root cause:** `components/icons/Icon.tsx`'s `registry[name] ?? ''` silently falls back to an
  empty string for any unrecognized `name`, so a typo'd/never-added icon name renders a valid but
  visually blank `<svg>`. Two call sites referenced names that were never added to the registry:
  `'bar-chart'` (SpendSection.tsx:486) and `'loader'` (memory.tsx recall button, was line 546).
- **Fix:** added `'bar-chart'` to the registry (no existing substitute — a real gap). For
  `'loader'`, changed the call site to the existing `'refresh'` icon, matching the loading-state
  convention already used elsewhere (e.g. `conversation.tsx`'s upload button swaps
  `paperclip`→`refresh` while uploading) rather than growing the icon set for a near-duplicate.
- **Avoid:** when adding an `<Icon name="...">` call, verify the name exists in
  `components/icons/Icon.tsx`'s `registry` (or add it) — the component gives no runtime signal
  when it doesn't.
- **Locked by:** `frontend/src/components/icons/Icon.test.tsx` (3 tests: bar-chart renders real
  markup, an unregistered name documents the blank-fallback failure mode, and a sweep over the
  in-use icon names asserts none render blank).

### BB-62 — Work screen "Run now" had zero gateway call (audit L1/gap 1)

- **Symptom:** clicking "Run now" on a routine in the `/work` detail panel only closed the
  panel and showed a toast — unlike Retry/Cancel-run (already wired to durable runs) and
  Approve/Decline (already wired to `/approvals`), `runRoutineNow` in `store.ts` never touched
  the gateway; a scheduled task force-triggered from the UI never actually ran.
- **Root cause:** no gateway route existed to force-fire one schedule outside its own
  `next_run` tick — `Scheduler` only had `tick()` (due-schedules only) and the CLI's
  `hachi schedule run-now` booted a brand-new, throwaway agent session rather than reusing
  the resident session already running the proactive `ScheduleRunner`.
- **Fix:** added `Scheduler.run_now(schedule_id, fire, now=None)` (mirrors `tick()`'s
  fire+`mark_fired` sequencing but bypasses the `due()` gate — an explicit user action always
  fires); `AgentSession.run_schedule_now(schedule_id)` reuses the *live* `ScheduleRunner`'s
  `_fire` callback (same `session.chat(...)` + `deliver_result` as a real tick) and dispatches
  it through the existing background job queue (`func=` closure, mirrors `_enqueue_title_job`)
  so the HTTP request returns immediately; new route `POST /schedules/{id}/run-now` wired
  through `GatewayControlPlane.run_schedule_now`; frontend `runRoutineNowLive()` in
  `work.ts` calls it and `work.tsx`'s `onRunNow` now dispatches on the routine's real id.
- **Investigated, no fix needed (false positive):** audit gap 2 — the scripted demo
  `_runQueue`/`runTick()`/`finishRun()` path in `store.ts` (source of the hardcoded
  `"Summarised 6 PRs…"` result) is unreachable whenever `dataMode === 'live'`; every entry
  point (`openRun`, `runAllowLeash`, `runAlwaysAllow`, `runDenyLeash`, `stopRun`) has an
  explicit live-mode early return before the mock queue is ever seeded, and `dataMode` is a
  fixed constant set once from the build-time `USE_MOCKS` flag (never toggled at runtime).
  Locked with a regression test rather than a code change.
- **Avoid:** when a "force this scheduled/recurring thing to run now" feature is needed,
  reuse the *live* session's existing fire callback/job queue (via `AgentSession`) instead of
  booting a second, throwaway agent inline in the request handler — a synchronous LLM call in
  an HTTP handler blocks the response and double-boots session state. When auditing a mock vs.
  live data path for a "have we shipped fake data to a real user" concern, check the *entry
  points* into the mock branch, not just the code that produces the fake string — one guard at
  the top of the shared trigger function is enough to make every downstream fake-data path
  provably unreachable in live mode.
- **Locked by:** `tests/test_scheduler.py` (4 new `run_now` tests);
  `tests/test_schedule_run_now_gateway.py` (8 tests: `AgentSession.run_schedule_now` +
  `POST /schedules/{id}/run-now`); `frontend/src/lib/data/domains/work.test.ts` (3 tests);
  `frontend/src/lib/store/store.test.ts` (4 tests, gap-2 false-positive lock).

### BB-63 — `HealthRecorder.snapshot()` p50 latency off-by-one on even-length windows (L3)

- **Symptom:** `ProviderHealth.p50_latency_ms` reports a value one rank too high whenever the
  recorder has collected an even number of latency samples (e.g. 4 samples `[100, 200, 300, 400]`
  reported 300.0 instead of the correct 200.0).
- **Root cause:** `p50 = lats[len(lats) // 2]` picks the *upper*-middle element for even `n`
  (e.g. `n=4` -> index 2, the 3rd-smallest value), which is one rank higher than the standard
  nearest-rank percentile (`rank = ceil(p * n)`, 1-indexed -> index 1 for `n=4, p=0.5`). It
  happened to match for odd `n` (median), masking the bug in the one existing test.
- **Avoid:** compute percentiles with the nearest-rank formula
  `lats[max(0, math.ceil(p * n) - 1)]`, not `len // 2` — verify against both an odd- and an
  even-length fixed dataset, never just one parity.
- **Locked by:** `tests/test_resilience.py::TestHealthRecorder::test_p50_latency_even_count_uses_nearest_rank`.

### BB-64 — Tool execution exceptions swallowed with no traceback ever logged

- **Symptom:** when a tool raises an unexpected exception, the LLM receives a compact
  `"Tool Execution Error: <str(exc)>"` message (correct/intended), but there is zero log
  record anywhere with the exception or its traceback — operators have no way to debug the
  real failure beyond the one-line message.
- **Root cause:** `ExecutionLoop._execute_single_tool()`'s `except Exception as exc:` branch
  only stringified `exc` into the tool-result text; it never called `logger.error(...,
  exc_info=exc)` or otherwise preserved the traceback/chain.
- **Avoid:** whenever an except-branch converts an exception into a user/model-facing string,
  also log it with `exc_info=exc` (or re-raise `from exc`) so the traceback isn't silently
  discarded — stringifying for a consumer and logging for debugging are two separate needs.
- **Locked by:** `tests/test_p4_03_parallel_tools.py::test_execute_single_tool_error_preserves_traceback_in_log`.

### BB-65 — `ExecutionLoop._generate_with_retry` dead code left in `loop.py`

- **Symptom:** none at runtime — purely a maintainability/audit finding. A full non-streaming
  retry-wrapper method (`_generate_with_retry`) sat unreferenced in `loop.py`, confusing future
  readers about which retry path `run()` actually uses.
- **Root cause:** P1-2 (`docs/DECISIONS.md`) moved turn generation to streaming
  (`_stream_generate`, its own independent retry loop) but never deleted the older
  non-streaming `_generate_with_retry` it superseded. Grep confirmed zero call sites anywhere
  in the repo (only a stale docstring cross-reference in `_stream_generate` and a comment in
  `tests/test_iteration_limit.py`).
- **Avoid:** when a code path is superseded (new retry/generation strategy, etc.), delete the
  old implementation in the same change — don't leave it "just in case"; grep the whole repo
  for call sites before trusting a function is dead, then remove it and any stale
  cross-reference comments pointing at it.
- **Locked by:** `tests/test_p4_03_parallel_tools.py::test_generate_with_retry_removed_as_dead_code`.

### BB-66 — `AgentSession.shutdown()` never shuts down the per-session tool thread pool

- **Symptom:** every session leaked its `ExecutionLoop._tool_pool` (a 4-worker
  `ThreadPoolExecutor` created per `ExecutionLoop`) for the remaining life of the process —
  no observable crash, just accumulating idle threads across session churn (CLI restarts,
  gateway session ends, `_reload_agents`).
- **Root cause:** `AgentSession.shutdown()` closes the session store, LLM HTTP clients,
  browser controller, memory vault, integrations, and MCP manager, but never called
  `self.loop.shutdown()` — the one method that calls `self._tool_pool.shutdown()`.
- **Avoid:** whenever a component owns a `ThreadPoolExecutor` (or similar resource) with its
  own `shutdown()`, the *owner's* shutdown/teardown method must explicitly delegate to it —
  a resource is never freed "by association" just because it's an attribute of something
  that got cleaned up.
- **Locked by:** `tests/test_agent_session_shutdown.py::TestAgentSessionShutdown::test_shutdown_shuts_down_tool_pool`.

### BB-67 — Budget/token safety ceiling checked only post-hoc; a single call can overshoot it

- **Symptom:** with a hard `_TOKEN_SAFETY_CEILING` (or an opt-in `max_tokens`) close to the
  current cumulative usage, the loop still let ONE MORE full LLM call complete before
  stopping — cumulative usage could land arbitrarily far past the ceiling (bounded only by
  that one call's actual token cost) instead of being refused before it started.
- **Root cause:** `ExecutionLoop._safety_ceiling_exceeded()` compared only the
  already-recorded `cost_tracker.snapshot().total_tokens` against the ceiling. That snapshot
  reflects calls that already completed; there was no estimate of the *upcoming* call's
  worst-case token cost, so a call that would clearly blow the budget was allowed to run
  anyway and only caught one iteration later, after the overrun already happened.
- **Avoid:** when a resource cap is checked in a loop with expensive steps between checks,
  the check must account for the worst-case cost of the *next* step, not just the
  already-recorded total — "check after every step" is not equivalent to "never exceed the
  cap by more than one step's cost" unless the next step's cost is bounded and added in.
- **Locked by:** `tests/test_loop_backstop_cancel.py::test_token_safety_ceiling_is_preflight_not_post_hoc`.

### BB-68 — Streaming LLM calls with unknown/zero usage silently under-count spend

- **Symptom:** when a provider stream never sends a usage chunk (e.g. `stream_usage=False`
  for a strict local server, or a provider that omits `stream_options`), `generate_stream()`
  returns an all-zero `TokenUsage()` with zero visibility — cost/token budget caps
  (`_budget_exceeded`, `_safety_ceiling_exceeded`) silently under-count these calls' real
  spend since there is nothing distinguishing "really used 0 tokens" from "usage unknown."
- **Root cause:** `OpenAICompatibleClient.generate_stream()` initializes
  `final_usage = TokenUsage()` and only overwrites it if a usage chunk arrives; when none
  does, the zero default is returned with no log signal at all.
- **Avoid:** the zero-usage fallback return value must stay (breaking it would ripple into
  every caller that already treats it as a valid `TokenUsage`), but any code path that
  returns a placeholder/unknown value silently must at minimum log a WARNING so the gap is
  operationally visible — never let "unknown" and "verified zero" be indistinguishable in
  both the return value AND the logs.
- **Locked by:** `tests/test_streaming.py::test_openai_stream_no_usage_chunk_logs_warning`
  (companion to the pre-existing `test_openai_stream_no_usage_chunk_returns_zeros`, which
  pins the unchanged zero-usage return value).

### BB-69 — Sub-agents ran with no inherited budget cap, invisibly draining shared spend

- **Symptom:** a delegated sub-agent (`delegate_task`/`delegate_parallel_tasks`) could run
  its full `max_iterations` budget completely unchecked by any cost/token cap even when the
  parent session had `max_session_cost_usd`/`max_session_tokens`/`max_turn_cost_usd`/
  `max_turn_tokens` configured — the parent's `CostTracker` recorded the spend correctly
  (it's shared), but nothing stopped the sub-agent's own loop from continuing to spend
  against it. The parent's own budget checks wouldn't fire until its NEXT turn, by which
  time the sub-agent had already run unchecked.
- **Root cause:** `SubAgentRuntime.run()` constructed its own `ExecutionLoop` passing only
  `llm_client`/`registry`/`memory`/`base_system_prompt`/`on_event`/`cost_tracker` — never
  `max_cost_usd`/`max_tokens`/`max_cost_per_turn`/`max_tokens_per_turn`, so those defaulted
  to `0` (unlimited) regardless of what the parent session had configured.
- **Avoid:** when a child execution unit shares a parent's tracked resource (cost tracker,
  rate limiter, etc.), it must also inherit the parent's ENFORCEMENT of that resource's caps
  by default — sharing the accounting without sharing the limit lets the child spend past
  what the parent would ever allow itself.
- **Locked by:** `tests/test_sub_agent_budget_caps.py` (2 tests: cap propagation stops the
  loop early; `SubAgentRuntime` accepts all 4 cap kwargs). Threaded end-to-end via
  `register_delegation_tools()`/`_make_delegate_task()`/`_make_delegate_parallel_tasks()` in
  `src/hachi/tools/delegation_tools.py`, wired from `boot_agent()`'s existing
  `max_session_cost_usd`/`max_session_tokens`/`max_turn_cost_usd`/`max_turn_tokens` in
  `src/hachi/gateway/orchestrator.py`.

### BB-70 — Sub-agent iteration-limit exhaustion reported as SUCCESS, not TIMEOUT

- **Symptom:** when a delegated sub-agent never finished its task and was cut off by
  `max_iterations`, the orchestrator received `Status: success` in the delegation report —
  indistinguishable from a task that genuinely completed — even though the summary text
  said `"[INCOMPLETE] The task reached the N-iteration limit..."`. The incomplete result was
  also persisted to the memory vault as a confirmed `delegation_result` fact (BB-42's
  sibling: `_enqueue_delegation_persistence` only skips the fact-upsert for non-SUCCESS).
- **Root cause:** `ExecutionLoop.run()` never raises `AgentException` on iteration-limit
  exhaustion (P1-04 made it a graceful `"[INCOMPLETE] ..."` string return, not a raised
  exception — see `tests/test_iteration_limit.py`). `SubAgentRuntime.run()`'s
  `except AgentException as exc:` branch, written to map this case to
  `SubAgentStatus.TIMEOUT`, was therefore unreachable: the `[INCOMPLETE]` string flowed
  straight into the `try` block's normal return path, reported as `SUCCESS`.
- **Avoid:** when a callee changes from "raises on incomplete" to "returns a sentinel string
  on incomplete" (or vice versa), every caller's exception handler for the old contract
  becomes silently dead code — grep for the exception type across the codebase whenever you
  change how a loop signals a non-exceptional-but-not-fully-successful outcome, and update
  callers to check the new signal instead of leaving a now-unreachable except clause.
- **Locked by:**
  `tests/test_sub_agent_iteration_limit_status.py::test_sub_agent_iteration_limit_exhaustion_is_not_success`.

### BB-71 — Router fallback (`_resolve_turn_client`) silently swallowed at DEBUG level

- **Symptom:** when the `ModelRouter` failed to resolve a route (misconfiguration, all
  candidates unavailable, or any unexpected error) and the loop silently fell back to the
  default `llm_client`, the ONLY trace of this was a DEBUG log line — invisible in normal
  operation (INFO/WARNING is the typical default level), so a misrouted/degraded session
  looked identical to a healthy one in the logs.
- **Root cause:** `ExecutionLoop._resolve_turn_client()`'s `except NoRouteError` and
  `except Exception` branches both called `logger.debug(...)` instead of `logger.warning(...)`
  before falling back — an operationally significant event (the model actually serving this
  turn silently changed) was logged at a level nobody watches by default.
- **Avoid:** a fallback path that silently changes user-visible behavior (which model
  answers, which provider is used, etc.) must log at WARNING or above — DEBUG is for
  developer tracing, not for "something degraded and the user should be able to find out."
- **Locked by:** `tests/test_hot_path_routing.py::TestNoRouteErrorFallback` — new
  `test_no_route_error_logs_at_warning_not_debug` and
  `test_arbitrary_router_exception_logs_at_warning_not_debug`.

### BB-72 — `cleanup_completed()` defined 3×, called by zero production code; session data stores grew without bound

- **Symptom:** `jobs.db` accumulated completed/failed/cancelled rows forever;
  `interaction_log`, `idempotency_keys`, and `daily_spend` tables in `sessions.db` had
  no prune path; `CheckpointManager` snapshot files piled up on disk.  A "governed"
  product that never prunes its own audit trail leaks data and disk indefinitely.
- **Root cause:** `SQLiteJobQueue.cleanup_completed()` and `InMemoryJobQueue.cleanup_completed()`
  were defined (and tested) but never wired into any background call path.  The
  `ResidentWorkerThread._run()` loop only called `execute_one()` on idle and had no
  periodic maintenance step.  Session-store tables had no cleanup methods at all;
  `CheckpointManager` had no prune method.
- **Fix:**
  - Added `SessionStore.cleanup_idempotency_keys()`, `cleanup_interaction_log()`,
    and `cleanup_daily_spend()` (`core/session_store.py`).
  - Added `CheckpointManager.prune_old_snapshots()` (`core/checkpoints.py`).
  - Added `RetentionSettings` to `core/settings.py` (maps to `[retention]` in
    `settings.toml`; conservative defaults: jobs 24 h, interaction_log 90 d,
    idempotency keys 48 h, daily_spend 365 d, checkpoints 30 d, sweep every 3600 s).
  - Extended `ResidentWorkerThread.__init__` with optional `session_store`,
    `checkpoint_manager`, and retention-TTL params; added `_maybe_sweep()` / `_do_sweep()`
    called on every idle poll cycle.
  - `boot_agent` in `gateway/orchestrator.py` now passes `session_store`,
    `checkpoint_manager`, and `RetentionSettings` values to `ResidentWorkerThread`.
- **Avoid:** defining a cleanup method without also hooking it into the background
  maintenance loop — the method is effectively dead code and stores grow unbounded.
  When adding a new durable store, add its cleanup method AND wire it into
  `ResidentWorkerThread._do_sweep()` in the same PR.
- **Locked by:**
  `tests/test_retention_sweep.py` — 6 tests covering:
  `test_worker_idle_prunes_old_completed_jobs`,
  `test_inmemory_queue_also_swept`,
  `test_session_store_cleanup_idempotency_keys`,
  `test_session_store_cleanup_interaction_log`,
  `test_session_store_cleanup_daily_spend`,
  `test_checkpoint_manager_prune_old_snapshots`.

### BB-73 — `[observability]` config was dead; `setup_from_config`/`setup_metrics` never called at boot

- **Symptom:** Setting `[observability] enabled=true` in `settings.toml` had no effect —
  tracing and metrics stayed dormant regardless of config. `HACHI_TRACING=true` (env-var path)
  was the only way to activate tracing. `ObservabilitySettings.metrics_enabled=true` was also
  inert. The degraded mode (`enabled=true` + `bus_funnel=false`) had no warning.
- **Root cause:** `boot_agent` called `configure_from_env()` (env-var path only) at line ~2544
  but never read `ObservabilitySettings` from the loaded config dict or called
  `tracing.setup_from_config` / `metrics.setup_metrics`. The config objects existed and the
  functions existed; they were simply never wired together.
- **Fix:** Added `_apply_observability_settings(obs_cfg, events_cfg)` in
  `gateway/orchestrator.py` (called from `boot_agent` immediately after `_events_cfg` is
  parsed — config is already loaded, no double `load_config()` call). The helper calls
  `tracing.setup_from_config` and (conditionally) `metrics.setup_metrics`, and logs a
  `WARNING` when `enabled=true` + `bus_funnel=false` (degraded mode).
- **Avoid:** adding a new config section to `ObservabilitySettings` without also adding its
  activation call in `_apply_observability_settings`. The docstring in `settings.py` now
  correctly references `_apply_observability_settings` so the connection is documented.
- **Locked by:** `tests/test_obs_boot_config.py` — 8 tests covering enabled/disabled/
  metrics/sdk-absent/unknown-exporter/degraded-mode paths.

### BB-74 — `ObservabilitySettings` docstring falsely claimed the gateway called `setup_from_config`

- **Symptom:** `core/settings.py` docstring for `ObservabilitySettings` said "the gateway
  calls `setup_from_config` at boot" — a statement that was false (BB-73). Misleading
  documentation in the type that developers read first when understanding the config.
- **Root cause:** The docstring was written for an intended behavior that was never
  implemented.
- **Fix:** Updated the docstring to correctly reference `_apply_observability_settings`
  in `gateway.orchestrator` as the actual boot wiring point (`core/settings.py`).
- **Avoid:** writing docstrings that describe intended future behavior as present fact —
  especially on config classes where operators rely on the doc to understand the actual effect.
- **Locked by:** BB-73 tests (the behavior the docstring described is now real).

### BB-75 — Cookbook/security-guide documented CLI commands & flags that never existed

- **Symptom:** Copy-pasting from the user-facing docs errored. `hachi run --once "…"` and
  `echo … | hachi run --once` (cookbook §3, the entire "one-shot task from the CLI" recipe)
  → `No such option: --once`; `hachi run --resume <session-id>` → `Got unexpected extra
  argument(s)`; `hachi doctor --check google|voice` → `No such option: --check`;
  `hachi schedule delete <id>` → `No such command 'delete'`; `hachi secret set <name>`
  (og-security.md) → `No such command 'secret'`.
- **Root cause:** Doc drift. One-shot mode was documented but never implemented (no
  `--once`/one-shot path existed anywhere in `cli/`); `--resume` is a no-argument interactive
  picker, not an id-taking flag; `doctor` never had `--check`; the schedule subcommand is
  `remove`, not `delete`; the credential command is `hachi set` / `hachi secrets --set`,
  not `secret set`.
- **Fix:** Implemented `hachi run --once` (+ bare positional `hachi run "<task>"`, + piped
  stdin) via `_run_once()` in `cli/main.py` — boots an agent, runs one `chat` turn, raw-echoes
  ONLY the reply to stdout (so it pipes byte-clean), then exits. `--resume`/`--continue` now
  reject a stray positional with a guided error. Corrected the four stale doc references in
  `docs/guides/cookbook.md` and `docs/reference/og-security.md`.
- **Avoid:** documenting a CLI command/flag before it is registered — and renaming/removing
  one without grepping the reference docs. `--once` reads stdin only when piped
  (`not sys.stdin.isatty()`) so it never blocks on a TTY.
- **Locked by:** `tests/test_cli_run_once.py` (7 tests — one-shot behavior) and
  `tests/test_docs_cli_reference.py` (introspects the Typer app; asserts every `hachi <cmd>`
  in the reference docs resolves to a real command/subcommand).

### BB-76 — `<button>` with no base `background` rule renders the UA ButtonFace grey

- **Symptom:** The conversation-header session picker and the composer mic button rendered
  as cold `#F0F0F0` grey chips on Hachi's warm bone canvas (`#FBF7EF`) — visibly unthemed,
  as if they belonged to a different app. Reported by the user as "not blending to the theme".
- **Root cause:** Both used the codebase idiom `background: open ? 'var(--hachi-cream)' : undefined`
  in an inline `style`. React **omits** a property whose value is `undefined`, so the rest
  state declared no background at all and fell through to the User-Agent stylesheet, which
  paints `<button>` with `ButtonFace` (`#F0F0F0` on Windows/Chrome). The idiom itself is
  correct and deliberate — an inline background would out-specify the `.class:hover` rule and
  silently kill hover — but it *requires* the class to supply the rest-state background.
  `.hachi-session-title-btn` and `.hachi-composer-voice-btn` defined only `:hover`.
  `.hachi-rating-btn` is the correct precedent: it pairs `:hover` with `background: var(--hachi-canvas)`.
- **Fix:** Added the missing base `background` rules in `frontend/src/styles/interactive.css`.
  While there, gave the session-picker trigger a real state model — bare at rest (it reads as
  the page heading), `--hachi-cream` on hover, and on open it takes the dropdown panel's own
  skin (`--hachi-surface` + `--hachi-line` hairline) so trigger and panel read as one object.
  The open state is keyed off `[aria-expanded='true']` so the visual and a11y states cannot
  drift; it is ordered **after** `:hover` because the two have equal specificity (0,2,0).
- **Avoid:** never let an interactive `<button>` end up with zero `background` declarations.
  If the `.tsx` hands the rest state to CSS via `: undefined`, the class MUST declare a base
  `background` (use `transparent` for ghost buttons). Corollary: do **not** "fix" this by
  putting a literal background in the inline style — inline beats `:hover` and kills it.
- **Third instance:** `.hachi-leash-always-btn` (`routes/approvals.tsx`,
  `components/brand/LeashPrompt.tsx`) had the same defect — reproduced live by injecting a
  pending approval into the store, which rendered a raw grey "Always allow …" button beside
  the outlined Decline and solid-red Allow once. Fixed with the same base rule.
- **Scope boundary:** all three *reproduced* instances are fixed. A wider sweep found ~26
  further classes in `interactive.css` that define a `:hover` background with no base rule;
  most are fine because their `.tsx` sets an inline background — but that is the mirror-image
  hazard (an inline background out-specifies `:hover`, so those hover effects may be silently
  dead). Not audited here.
- **Locked by:** `frontend/tests/interactive-css.test.ts` — asserts the guarded classes
  declare a base background, plus two anti-vacuity guards (the stylesheet actually loaded;
  the parser can still detect the defect). Verified by reverting the CSS fix: the guard
  fails, then passes again once restored.
- **Testing gotcha (cost two gate failures):** that test lives outside `src/` deliberately.
  `frontend/tsconfig.json` scopes `include` to `src` and the project has **no `@types/node`**,
  so importing `node:fs` from a test under `src/` passes Vitest but breaks `tsc --noEmit`
  — failing both the `frontend typecheck` and `frontend build` gate steps. The obvious
  browser-side workaround is a trap: **Vitest stubs CSS imports to `''` even with `?raw`**
  (default `css: false`), so the file reads empty and every assertion passes *vacuously*.
  Node-side tests that read files belong in `frontend/tests/`, and any test that loads a
  fixture should assert the fixture is non-empty.

### BB-77 — Live approvals auto-declined in ~1 second after appearing

- **Symptom:** Any pending approval visible on Home or The leash vanished within one second and was logged as "timed out — Hachi stayed put", even when the gateway sent no expiry.
- **Root cause:** `adaptApproval()` (approvals.ts) correctly sets `expiresAt: 0` as a sentinel for "no server expiry." But `tickApprovals()` (store.ts) tested `a.expiresAt <= now`, and `0 <= Date.now()` is always true — so every live approval expired immediately. The shared 1-second interval in `useCountdown.ts` called `tickApprovals()` whenever any approval card was mounted.
- **Fix:** (1) `tickApprovals` returns early when `dataMode === 'live'` (belt-and-braces). (2) The expiry filter now guards `a.expiresAt > 0 && a.expiresAt <= now`; the keep-filter mirrors it. (3) The `ApprovalCard` in `routes/index.tsx` renders "no auto-decline — Hachi waits until you decide" when `expiresAt <= 0`, matching the existing copy in `routes/approvals.tsx`.
- **Avoid:** never use `expiresAt <= now` without first guarding `expiresAt > 0`; zero is the "no expiry" sentinel throughout the approval domain.
- **Locked by:** `frontend/src/lib/store/store.test.ts` — "tickApprovals — live sentinel and mock expiry (BB-77)".

### BB-78 — Permission removals and operator-tool toggles silently reverted on reload

- **Symptom:** Removing an allowed folder/command in Settings → Permissions, or toggling an operator tool, took effect in the UI but reverted to the previous state on the next hard reload. The Safety section header promised "Narrow it any time."
- **Root cause:** `removeFolder`, `removeCommand`, and `toggleOpTool` in `store.ts` only mutated local Zustand state — no gateway call was made. In contrast, the add paths (`addFolderLive`, `addCommandLive`) already called POST routes. The DELETE routes `DELETE /config/permissions/folders` and `DELETE /config/permissions/commands` did not exist in the backend.
- **Fix:** Added `remove_allowed_folder` / `remove_allowed_command` methods to `HachiSupportService` (cli/main.py), wired them through `GatewayControlPlane` (control_plane.py), and exposed them as `DELETE /config/permissions/folders` and `/commands` in fastapi_app.py. Added `removeFolderLive`, `removeCommandLive`, `toggleOpToolLive` to config.ts (store only mutates on 2xx; shows blocked toast on failure). Rewired PermissionsSection.tsx to use the Live functions. Regenerated OpenAPI schema (BB-4).
- **Avoid:** never wire a destructive UI action to a bare store mutation; always mirror the add-path pattern (Live function → gateway → store-on-2xx).
- **Locked by:** `frontend/src/lib/data/domains/config.test.ts` — "removeFolderLive/removeCommandLive/toggleOpToolLive — persist to gateway (BB-78)"; `tests/test_g1_wave1.py` — "test_delete_allowed_folder/command_*".

### BB-79 — "Browse the kennel → Add" dead-ends; consent dialog never appears

- **Symptom:** Clicking Add on any skill in the kennel browse panel had no effect — the browse panel stayed open and the consent dialog never appeared.
- **Root cause:** `askKennel` in store.ts set `kennelConsent: item` but did not clear `kennelBrowseOpen`. `KennelConsent.tsx` renders the browse panel when `kennelBrowseOpen` is true, so it always rendered the browse panel, never the consent view — even when a pending consent item was in state.
- **Fix:** `askKennel: (item) => set({ kennelConsent: item, kennelBrowseOpen: false })` — consent and browse are mutually exclusive; clearing the browse flag is the correct invariant.
- **Avoid:** consent and browse mode are mutually exclusive — setting one must always clear the other.
- **Locked by:** `frontend/src/components/overlays/KennelConsent.test.tsx` — "askKennel — closes browse panel before showing consent (BB-79)".

### BB-80 — Run terminal scroll-follow was inert; caret had no class (reduced-motion rule never fired)

- **Symptom:** The run output terminal did not auto-scroll to new lines during a live run. Additionally, the `[class*="hachi-caret"]` reduced-motion CSS rule never applied because the caret span had no class.
- **Root cause:** Two layered problems: (1) `run.tsx` wrapped `<Terminal>` in a div with `overflow: auto` and also passed `style={{ display: 'block', minHeight: '100%' }}` — this collapsed Terminal's internal flex layout so the output region never overflowed and the rAF pin was a no-op. (2) The blinking caret span was anonymous (`aria-hidden="true"` only), so `[class*="hachi-caret"]` in the `<style>` block never matched.
- **Fix:** Removed `overflow: auto` from the run wrapper div (it now passes `display: flex` to let Terminal own scrolling). Terminal's style changed to `height: 100%`. Added `className="hachi-caret"` to the caret span. Added `streaming?: boolean` prop (default true): when false, hides the caret and shows "run ended" copy. Added state-based following flag + "↓ Latest" pill. Added `role="log" aria-live="polite"` to the output region.
- **Avoid:** the outer scroll container must never be a wrapper that also sizes its child; Terminal must own its own overflow. And any CSS rule targeting `[class*="x"]` is dead without the class.
- **Locked by:** `frontend/src/components/ui/Terminal.test.tsx` — "Terminal — streaming prop controls caret (BB-80)".

### BB-81 — Authoring "Written to …" badge shown for the wrong target after switching

- **Symptom:** Apply a patch to `brain.og`, then click `settings.toml` — the "Written to ~/.hachi/skills/settings.toml · skill re-indexed" line and the Revert button appeared, claiming a patch was applied to a file that was never touched.
- **Root cause:** `authApplied` in the store was a global `boolean`. Switching `authSel` did not reset it, so any previously-applied target would show the badge on every subsequent target.
- **Fix:** Replaced `authApplied: boolean` with `authAppliedTarget: string | null`. `applyPatch()` sets it to the current `authSel`; `revertPatch()` clears it to `null`. In `authoring.tsx`, `const authApplied = authAppliedTarget === authSel` — a different selected target simply doesn't match, no reset needed.
- **Avoid:** never use a global boolean flag for "this action was performed" when the action is scoped to a selected item; track the item identity instead.
- **Locked by:** `frontend/src/lib/store/store.test.ts` — "applyPatch — per-target applied state (BB-81)".

### BB-82 — Setup wizard let users advance past the key step with no key

- **Symptom:** Clicking "Next" on the API-key step (step 1) advanced the wizard even when no key was entered and none was pre-configured server-side. "Skip" called `closeSetup()` (closing the wizard) rather than advancing to the next step. Re-opening the wizard always reset to step 0, losing any partial progress. The wizard never set a `completed` flag, so `openSetup()` had no way to distinguish "resume in progress" from "start over after finish."
- **Root cause:** `handleNext` called `setupNext()` unconditionally; the primary button had no `disabled` prop; `skipLabel` onClick was `closeSetup`; `openSetup()` always wrote `step: 0`; no `completed` field existed.
- **Fix:** Added `keyOk = setup.keyAlreadySet || keyValidation.status === 'valid'`. Primary button is disabled when `!keyOk` on KEY_STEP. Skip calls `setupNext()`. Added "Set up later" (calls `closeSetup()`) visible only on KEY_STEP. Skip hidden on KEY_STEP unless `keyAlreadySet`. Added `completed: boolean` to setup state; `setupNext()` sets it when finishing step ≥ 4. `openSetup()` preserves step when `step > 0 && !completed`.
- **Avoid:** never gate wizard advancement in the handler alone — the button itself must be disabled so the constraint is visible in the UI and testable without firing click events.
- **Locked by:** `frontend/src/components/overlays/SetupWizard.test.tsx` — "SetupWizard — key step gate (BB-82)".

### BB-83 — Toast queue capped at 1; arm-then-confirm had no cooldown protection

- **Symptom (T8a):** Only one toast could exist at a time; a 4th toast pushed the 1st out silently. `dismissToast()` was a bare `set({ toast: null })` with no id parameter — no way to dismiss a specific toast. The live region was inside the conditional `<Toast>` element, not the always-mounted wrapper, so screen readers missed announcements. Action button support and correct auto-dismiss per tone were absent.
- **Symptom (T8b):** "Always allow" on both approval cards had hand-rolled arm logic with no cooldown — a fast double-click within the same tick could confirm instantly. The arm pattern was duplicated across `approvals.tsx` and `LeashPrompt.tsx`.
- **Root cause (T8a):** Single `toast: Toast | null` state; `ToastHost` role on conditional child. **(T8b):** No shared primitive; `handleAlwaysAllowClick` checked armed state but not elapsed time since arming.
- **Fix:** `types.ts`: added `action?` and `ToastItem extends Toast { id: string }`. Store: `toasts: ToastItem[]` (cap 3, drop oldest); `showToast(msg, tone?, action?)` appends; `dismissToast(id)` by id. `ToastHost`: always-mounted wrapper gets `role="status" aria-live="polite"`; renders stack; timer on oldest toast. New `ConfirmButton` component: arm → cooldown check → confirm; auto-disarm after armWindowMs or blur. Applied to: SessionPicker (session delete), memory (fact delete + undo toast), integrations (Clear/Disconnect), LeashPrompt + approvals (Always allow).
- **Avoid:** never use a single-slot for toasts; never do arm-then-confirm without a cooldown delay; always put the live region on a permanently-mounted element.
- **Locked by:** `frontend/src/lib/store/store.test.ts` — "toast queue — append / cap / dismiss (BB-83)"; `frontend/src/components/ui/ConfirmButton.test.tsx` — "ConfirmButton — arm-then-confirm (BB-83)".

### BB-84 — Tool-protocol injection text rendered verbatim in chat history and Review

- **Symptom:** Conversation history re-loaded from the gateway showed raw injection text beneath the user's message (`[Attached image: hachi logo.png]\n(Use the view_image tool with path: …)`). Review screen rendered `##` headings and `**bold**` as literal characters.
- **Root cause:** `reconstructMessagesFromEvents` (chat.ts) and `loadSessionMessages` set the user message `text` directly from `payload.user_text` / `m.content`, which the gateway stores with the full prompt-injection block. `review.tsx` rendered the Hachi `agentOutput` field with `{ix.agentOutput}` (plain text node) and the user input with `whiteSpace: pre-wrap`.
- **Fix:** New exported pure function `extractInjectedAttachments(text)` strips `\n?[Attached (image|file): name]\n(Use the \w+ tool with path: …)` blocks (multiline, global), returns `{ text, attachments: { name }[] }`. Applied to `role === 'you'` in both adapter paths. Extracted attachments merged into the message's `attachments` array (displayed as chips by `MessageItem`). In `review.tsx`: user cell applies `extractInjectedAttachments`, Hachi cell renders via `<Markdown>` (imported from `../components/ui/Markdown`).
- **Avoid:** never pipe raw `user_text` from the gateway directly to a display layer — the gateway concatenates the prompt-injection preamble into the same field.
- **Locked by:** `frontend/src/lib/data/domains/chat.test.ts` — "extractInjectedAttachments — strip tool-protocol injection (BB-84)".

### BB-85 — Two approval card implementations disagreed: low/medium risk showed filled "Allow once" on approvals screen

- **Symptom:** `routes/index.tsx:ApprovalCard` and `routes/approvals.tsx:ApprovalCard` were independent implementations. The approvals screen made "Allow once" a solid filled brand-red button for low AND medium risk — the visually dominant choice was the one that bypasses the leash, violating Nielsen error-prevention. `LeashPrompt` (the design-correct card) was used in conversation/run but not on the dedicated approval screens.
- **Root cause:** Two separate `ApprovalCard` implementations instead of one shared component. `routes/approvals.tsx` rendered `background: var(--hachi-brand)` on Allow once for non-high-risk approvals.
- **Fix:** Extended `LeashPrompt` props (`riskPill`, `touches`, `countdown: string|null`, `countdownBar`, `headerTestId`, `actionsTestId`). Button weighting now in ONE place: low/medium both outlined, high = Decline solid trust. Deleted `fmtCountdown` from `LeashPrompt` (uses `useCountdown().label` from caller). Both `ApprovalCard` functions replaced with `<LeashPrompt />` composition. `hachi-leash-decline-high-btn` class added to `interactive.css` (resting background in class per BB-76).
- **Avoid:** never duplicate approval-card markup; the design contract for equal-weight decisions lives ONCE in `LeashPrompt`.
- **Locked by:** `frontend/src/components/brand/LeashPrompt.test.tsx` — "LeashPrompt — button weighting (T10 / BB-85)"; `frontend/src/routes/-index.ApprovalCard.test.tsx` — "Home ApprovalCard — action row layout" (structural invariant still holds via LeashPrompt's layout).

### BB-86 — Overflow approval count was non-interactive text with wrong terminology

- **Symptom:** When more than 3 approvals were pending, `routes/index.tsx` showed a `<div>` reading "scroll down in the Leash tab to see all" — `cursor: default`, no keyboard access, terminology "Leash tab" instead of the correct route `/approvals`. Impossible to navigate from keyboard.
- **Root cause:** The overflow count was rendered as a plain div with `cursor: default` instead of a navigable element. The copy referenced a "tab" that doesn't exist in the current navigation model.
- **Fix:** Replaced with a `<button className="hachi-more-approvals-link">` that calls `navigate({ to: '/approvals' })` on click. Label updated to `+ N more waiting on the leash →`. Resting `background: transparent` placed in the CSS class (not inline) per BB-76 so `:hover { text-decoration: underline }` can override it.
- **Avoid:** never render navigation-intent content as a `<div>` with `cursor: default`; never reference navigation locations by informal names.
- **Locked by:** `frontend/tests/interactive-css.test.ts` — "overflow link hover treatment (BB-86)" verifies the `:hover` underline rule exists in `interactive.css`.

### BB-87 — Audit timestamps fabricated at fetch time; history "when" frozen as "just now"

- **Symptom 1:** The operator audit log showed a fabricated timestamp (`new Date().toLocaleTimeString()` called at fetch time) for every historical gateway-sourced audit entry — every page reload re-dated the entire table to the current time.
- **Symptom 2:** Past-decisions history rows always showed "just now" regardless of how long ago the decision was made.
- **Root cause 1:** `frontend/src/lib/data/domains/approvals.ts` adapter called `new Date().toLocaleTimeString()` when adapting `PermissionAuditSnapshot` entries, which carry no timestamp field.
- **Root cause 2:** `store.ts:resolveApproval` and `tickApprovals` wrote the literal string `"just now"` into `HistoryItem.when` with no real timestamp alongside.
- **Fix:**
  - `approvals.ts`: gateway audit entries now get `ts: "—"` (no timestamp from server → render nothing).
  - `types.ts`: added `ts?: number` to `HistoryItem`.
  - `store.ts`: both call sites now write `ts: Date.now()` alongside `when: "just now"`.
  - `approvals.tsx`: history row renders `fmtRelative(item.ts)` when `ts` is present, else falls back to `item.when`.
  - Created `frontend/src/lib/ui/format.ts` with `fmtUSD`, `fmtTokens`, `fmtRelative`, `fmtDate`.
- **Avoid:** never call `new Date()` when adapting server data that has no timestamp field; always store a real `ts: Date.now()` epoch when creating in-memory time-sensitive records.
- **Locked by:** `frontend/src/lib/ui/format.test.ts` — covers all four format functions including the relative-time cases.

### BB-88 — Markdown parser infinite loop on pipe-delimited lines that lack a separator row

- **Symptom:** Vitest worker hung indefinitely (no timeout, no output) when a test rendered a `<Markdown>` component whose source contained a `|…|`-delimited line NOT followed by a `---`-style separator row.
- **Root cause:** `parseBlocks` in `Markdown.tsx` included `!TABLE_ROW_RE.test(rawLines[i])` in the paragraph-accumulation stop condition. A pipe-delimited line that failed the table-header+separator check fell through to the paragraph branch; the inner `while` exited immediately (stop condition matched line 0), produced an empty `lines` array (no block pushed), and `i` was never incremented — infinite spin.
- **Fix:** Removed `!TABLE_ROW_RE.test(rawLines[i])` from the paragraph stop condition. Pipe-delimited lines that don't form a valid table are now absorbed into paragraphs as plain text (the table-detection check at the top of the outer loop handles the valid-table path before the paragraph fallback is ever reached).
- **Avoid:** never add a line pattern to the paragraph stop condition unless that same pattern is also handled by an earlier branch that ALWAYS increments `i`; any stop condition that causes an empty `lines` result without advancing `i` produces an infinite outer loop.
- **Locked by:** `frontend/src/components/ui/Markdown.test.tsx` — "does not produce a table without a separator row" passes the failing input directly to the component.

### BB-89 — The PR security gate was red for every pull request, for ~6 weeks

- **Symptom:** `security-audit --fail-on-high --fail-on-medium`, run on every `pull_request` in CI, exits **2** on any fresh checkout. `main` pushes were green (the strict step was gated on `github.event_name == 'pull_request'`), so the failure was invisible to maintainers and total for contributors. The strict step landed 2026-06-05; **19 merges** went through a gate that had never once passed.
- **Root cause:** `security_audit` mixes two categories of check. **Source/config** checks depend on the resolved config the process can see (`permissions.tier == unrestricted`, terminal `allow_all`, capability `secret_ref`, and a `GOOGLE_CLIENT_SECRET` **exported into the environment**). **Posture** checks depend on how *the runner* is configured (`GOOGLE_CLIENT_ID` set?, `HACHI_REST_ALLOWLIST` populated?, `HACHI_SANDBOX_BACKEND` containerised?). A fresh GitHub runner satisfies none of the posture checks, so it always emitted 2 high + 1 medium. Gating a PR on posture checks means gating it on something the contributor cannot change — every PR is red regardless of its diff.
- **Fix:** Added `--ignore-checks <ids>` to `security-audit` (excluded from both the report and the exit-code gate, echoed back as `ignored_checks`). CI now pins `GOOGLE_CLIENT_ID` / `HACHI_REST_ALLOWLIST` in the job `env:` block and adds `--ignore-checks sandbox.process_backend`. The sandbox check is *ignored* rather than satisfied via `HACHI_SANDBOX_BACKEND=container`, because that would make the gate depend on Docker being present — trading a permanently-red gate for an intermittently-red one. Verified negative case: an unset `HACHI_REST_ALLOWLIST` still exits 2.
- **Fix (part 2, from adversarial review):** the first pass **overclaimed what the gate protects and left the escape hatch unvalidated**. (a) The commit message, the `ci.yml` comment and `docs/reference/og-security.md` all asserted that the gate catches a credential *committed to the tree*. It does not — `security_audit` inspects the process environment and resolved config and never opens a file, so `oauth.google_client_secret_embedded` fires on an **exported env var**. There is no tree secret-scan step in CI at all, and a PR that commits a key passes. All three claims corrected; the gap is tracked as PRODUCT-AUDIT P-30. (b) A requested ignore id that matched nothing was indistinguishable from a successful one — a typo or a renamed check echoed the requested string while the finding survived and the gate still failed. Unmatched ids are now reported separately. (c) `status` was derived from `high_count` alone, so a medium-only run printed `status: pass` with `exit_code: 2`; it is now derived from the exit code. (d) The strict step was still PR-only, leaving `main` unchecked — the very asymmetry that hid the bug; it now runs on both events.
- **Avoid:** never gate a pull request on a check whose input is runner/deployment state rather than the committed tree — pin the environment and `--ignore-checks` the posture-only ids; the gate must be deterministic or contributors learn to ignore it. And before describing what a security gate protects, run it against the attack you are claiming it stops.
- **Locked by:** `tests/test_cli_gateway_command.py` — `test_security_audit_ignore_checks_excludes_findings` (now also asserts the echoed contract and `exit_code == 2`), `test_security_audit_ignore_checks_can_clear_the_gate`, `test_security_audit_ignore_checks_tolerates_whitespace`, `test_security_audit_reports_ignore_ids_that_matched_nothing`.
### BB-90 — Six allowlisted launchers bypassed the blocked-path check entirely

- **Symptom:** In the `guided` tier, `cat ~/.ssh/id_rsa` was denied but `code ~/.ssh/id_rsa` (also `open`, `notepad`, `xdg-open`, `explorer`, `start`) returned `Command 'code' is allowed.` The same secret was readable through any GUI/editor launcher.
- **Root cause:** `check_command` ran its file-argument scan only when the executable was in `_EXFIL_STEMS` (`cat`, `head`, `copy`, `move`, …). Those six launchers are in `_SAFE_COMMANDS` but **not** in `_EXFIL_STEMS`, so they fell through to `return PermissionResult(True, …)` without inspecting a single argument. Separately, `_check_path_args` skipped any token without `/`, `\\`, `~` or `.`, so a bare filename (`cat id_rsa`) was never resolved against the cwd — uncaught whenever cwd sat inside a blocked directory.
- **Fix (part 1):** the argument scan now runs for **every** allowlisted command, not just the exfiltrate set. `_EXFIL_STEMS` is retained only to *widen* the scan (a path-taking command's bare argument is presumed a filename even before it exists). `_check_path_args` also resolves a bare token when it exists on disk, closing the blocked-cwd gap.
- **Fix (part 2 — the class, not the instance):** an adversarial review showed part 1 closed the six named launchers but left three holes of the *same* kind. (a) **`find` takes a nested command**: `find / -name id_rsa -exec cat {} +` has no blocked path among its tokens (`/`, `cat`, `{}`, `+` are all harmless) yet read the file end to end — proven against the real tool, which returned the file contents. (b) **`--flag=value` hid its path behind a leading dash**, so `code --file=~/.ssh/id_rsa` was never inspected. (c) **The gate tokenised with `str.split()` while the executor uses `shlex.split()`**, so `code "<blocked dir>/id_rsa"` fragmented into pieces that resolved nowhere and was allowed. Fixed by denying `find`'s exec primaries (`-exec`/`-execdir`/`-ok`/`-okdir`) in guided/sandbox, inspecting the RHS of `--flag=value`, and tokenising with `shlex.split` (falling back on unbalanced quotes).
- **Avoid:** when a guard enumerates the ways an attack can be spelled, it will miss the next spelling — ask instead what capability the check depends on and whether the *executor* agrees with the *gate*. Two components disagreeing about tokenisation, or one accepting a nested command, defeats any list of patterns.
- **Locked by:** `tests/test_permission_gate_hardening.py` — `test_launcher_commands_cannot_bypass_blocked_paths` (all six), `test_bare_filename_resolving_into_blocked_path_is_denied`, `test_find_exec_is_denied` (`-exec`/`-execdir`/`-ok`/`-okdir`), `test_flag_value_paths_are_inspected`, `test_quoted_path_containing_a_space_is_inspected`, plus `test_allowed_path_still_permitted_after_launcher_fix` and `test_find_without_exec_is_still_allowed` to guard against over-blocking. All 8 hole tests were confirmed to fail against the pre-fix source.
### BB-91 — The SSRF guard let CGNAT and overlay networks straight through

- **Symptom:** `validate_outbound_url("http://100.64.0.1/")` returned `ok=True`. On any machine running Tailscale, the agent could reach every device on the tailnet — provider endpoints, webhook receivers, voice base URLs.
- **Root cause:** the guard was a pure *negative* list — `not (is_private or is_loopback or is_link_local or is_reserved or is_multicast or is_unspecified)`. CPython's `is_private` is a closed literal table (RFC1918, 127/8, 169.254/16, TEST-NETs, 240/4, …) and RFC 6598 shared address space `100.64.0.0/10` is **not in it**. Those addresses also report `is_global=False`, so every disjunct was False and they were treated as public. Present since origin commit `bd9256c` — never a refactor regression. `gateway/_net_guard.py` calls itself a "thin wrapper" but imports nothing from core and duplicates the same negative list, so it carried the identical hole.
- **Fix:** require `is_global` positively *in addition to* keeping the negative list. The list stays because `is_global` alone would regress NAT64 (`64:ff9b::/96`, `is_global=True` but `is_reserved=True`, blocked today). A range denylist of `100.64.0.0/10` was rejected as the fix because `ip_network` membership is False for the IPv4-mapped form `::ffff:100.64.0.1`, which also passed. Both modules patched; the loopback short-circuit stays first so `allow_loopback=True` (local Ollama) still works.
- **Fix (part 2, from adversarial review):** three problems with part 1. (a) **No escape hatch on the gateway path.** `gateway/_net_guard.py` accepted only `allow_loopback`, so tailnet Ollama (`provider_admin.py:381`, the default self-hoster route), voice `base_url` (`voice_endpoints.py:410`) and provider test-connection became unreachable with no override — a security fix that silently breaks a documented deployment mode. It now takes `allow_private`, defaulting to `HACHI_REST_ALLOW_PRIVATE`, matching what the channel senders already honour. (b) **The docstring was a lie that caused the drift.** `_net_guard.py` called itself a "thin wrapper around hachi.core.net_guard" while importing nothing and duplicating the predicate — which is why the duplicate kept the pre-fix behaviour. It now delegates to a shared `ip_is_public`, and only loopback policy stays local. (c) **The rule rested on a private CPython constant.** `is_global` is False for CGNAT only because of `_IPv4Constants._public_network`; an explicit `100.64.0.0/10` membership check (via `ipv4_mapped`, so the mapped form is covered) no longer depends on that, and a test pins the premise.
- **Known remaining lockout (not fixed here):** `jobs/scheduler.py:462` and `cli/commands/schedule.py:230` still call the guard without `allow_private`, so a **tailnet-hosted webhook receiver** stops getting results with only a `logger.warning`. Same for `pack_index.py:174`, `community_packs.py:141`, `search_tools.py:173`. These need the same opt-in threaded through, or an explicit decision to keep them public-only.
- **Avoid:** never define "public" as "matches none of the bad ranges" — the special-purpose registry grows and `ipaddress.is_private` is a closed table, so require `is_global`, pin any range whose `is_global` value you depend on, and keep the negative checks only to catch is_global-but-reserved cases like NAT64. And when a security fix locks out a documented deployment mode, ship the escape hatch *with* it, not as a follow-up.
- **Locked by:** `tests/test_net_guard.py` — `test_cgnat_and_overlay_addresses_are_rejected` (incl. the `::ffff:` form), `test_public_neighbours_of_cgnat_are_allowed` (100.63.255.255 / 100.128.0.0 — a naive `100.` prefix rule breaks these), `test_existing_rejections_survive_the_is_global_change` (incl. NAT64), `test_allow_private_hatch_still_covers_cgnat`, and `test_gateway_guard_agrees_on_cgnat` for the duplicated gateway path.
### BB-92 — A guard placed outside the try/except left the error branch unreachable

- **Symptom:** `hachi models` — a README-documented command — exited 1 with a Rich source-code traceback (`ValueError: ANTHROPIC_API_KEY must be provided…`) whenever no provider key was configured, i.e. on every fresh install.
- **Root cause:** `cli/main.py` built the LLM client *outside* the `try` and only `client.list_models()` inside it. `create_llm_client` → `AnthropicClient.__init__` raises when the credential is absent, so the exception escaped before the `try` was entered. The command already contained the correct degraded path — `elif not discovered: "live discovery unavailable (offline or no API key)"` — but **that branch was unreachable**, because reaching it requires `client` to exist. The same call is wrapped correctly in the TUI/memory list path ~3,000 lines earlier.
- **Fix:** move client construction inside the `try`, default `discovered` to `[]` and `client` to `None`, and swallow the exception with a comment naming the expected cases. Guard the `finally` close with `getattr(client, "close", None)` so it is a no-op when construction failed.
- **Fix (part 2, from adversarial review):** two problems with part 1. (a) **`except Exception: pass` erased the diagnosis.** A typo'd `provider.kind`, a bad `base_url` or a bad `api_key_ref` produced byte-identical output to "no API key yet" — hiding exactly the failures the user must act on. The reason is now captured, shown in the human output, and exposed as an additive `discovery_error` field in `--json` so CI can tell the two apart. (b) **The close was outside the handler.** It sat in a sibling `finally`, so a `close()` failure on a dead HTTP session re-raised the very traceback this change removes; the precedent it claimed to mirror nests the close *inside* the outer `try`. Now nested, matching reality.
- **Also:** `assert "Traceback" not in result.output` was a vacuous test — `CliRunner` catches the exception, so pre-fix output was `""` and the assertion passed trivially. Replaced with `result.exception is None`. Added a close-on-failure test, which was the untested half of (b).
- **Avoid:** when a function has a "graceful degradation" branch, put the *construction* that can fail inside the same try block — a fallback placed after a call that raises is dead code, and any test that stubs the call to succeed will never notice. And never swallow the reason: "degrade silently" and "hide misconfiguration" look identical from the outside.
- **Locked by:** `tests/test_cli_models.py` — `test_models_without_api_key_exits_zero`, `test_models_without_api_key_shows_no_traceback` (both patch `create_llm_client` to **raise**, rather than stubbing it to succeed).
### BB-93 — `curl | bash` installer hung forever and silently skipped the rest of itself

- **Symptom:** Piping `install.sh` into bash could hang indefinitely with no output, and *every line after the clone never executed* — no dependency install, no launcher, no completion message. On Windows, `install.ps1` aborted at `uv sync` with "uv not recognised".
- **Root cause (two independent defects).**
  1. **stdin theft.** `git clone` inherits the script's stdin. Under `curl … | bash` that stdin *is the pipe carrying the remaining script text*, so git consumed the rest of the file. If the clone then needed credentials (private repo, typo'd `HACHI_REPO`) it blocked on a username prompt with no TTY — forever. Reproduced: `printf 'echo START\ngit clone …\necho LINE3\n' | bash` printed `START`, then hung; `LINE3` never appeared.
  2. **PowerShell PATH.** Upstream's uv installer edits the *registry* PATH only, never the current process. `$ErrorActionPreference = "Stop"` then killed `uv sync` even though the install had succeeded. macOS was fine only because `install.sh` had an `export PATH`; the PowerShell equivalent was missing.
- **Fix:** `export GIT_TERMINAL_PROMPT=0` (fail fast instead of prompting), `</dev/null` on every git invocation, explicit exit-code checks with actionable messages, git preconditions moved *before* the uv bootstrap, an explicit `command -v uv` re-check after the PATH export, PowerShell re-reads Machine+User PATH into `$env:Path`, guided setup only runs when a TTY/console is actually present, `HACHI_REF` added for reproducible installs, and the POSIX `hachi` shim now resolves both `.venv/bin` and `.venv/Scripts` and ships executable.
- **Fix (part 2, from adversarial review):** the first pass introduced two regressions of its own. (a) **The guided setup then never ran on the documented path.** Gating on `[ -t 0 ]` is always false under `curl … | bash` because fd0 *is* the pipe — so setup was skipped even for a human at a terminal. It now tests stdout and reattaches the real terminal with `</dev/tty`, falling back to skipping only when there genuinely is no terminal. (b) **`install.ps1` never checked `uv sync`.** A native non-zero exit is not a terminating error under `$ErrorActionPreference = "Stop"`, so a failed dependency install fell through and printed "Hachi is installed" — the same masked-failure class this change removed from the POSIX script. Both scripts now check and report. Also: `$env:Path` is prepended and expanded rather than replaced (replacing discarded conda/scoop session dirs), and `GIT_ASKPASS` is blanked because `GIT_TERMINAL_PROMPT=0` does not stop Git Credential Manager's GUI prompt.
- **Known gap:** the one-liner URLs still fetch the *installer* from `main` (`HACHI_REF` pins only the clone), and an existing checkout ignores `HACHI_REF` on `pull --ff-only`. Both need the script served from a tag.
- **Avoid:** any command in a `curl | bash` script that can read stdin — git, ssh, package managers — must be given `</dev/null` plus a non-interactive flag; and when deciding whether a human is present under a pipe, test **stdout** and reattach `/dev/tty`, never test stdin.
- **Locked by:** `tests/test_install_scripts.py` — structural guards for the stdin redirect, `GIT_TERMINAL_PROMPT`, ordering, POSIX/PowerShell PATH re-checks, TTY-guarded setup, ASCII-only `install.ps1`, and the shim's executable bit and dual venv layout.
### BB-94 — `uv build` silently produced an EMPTY wheel and still reported success

- **Symptom:** `uv build` printed "Successfully built" for both artifacts, but the wheel was **15 KB** (normally ~1.0 MB) and contained only `dist-info` — no `hachi/` package, no `.og` skills, no packs. The sdist was missing `src/` entirely (0 of 279 files). Nothing failed and nothing warned. Installing that wheel would give a `hachi` console script pointing at an import that does not exist.
- **Root cause:** the working tree contained `.anvaya/` — the agent-tooling scratch directory, **95 MB**, holding full copies of this repository plus symlinks to absolute paths. Hatchling builds the wheel *from the sdist*, so once the sdist lost `src/` the wheel was empty by construction. Listing it in `.gitignore` is not sufficient.
- **What did NOT fix it** (each tested, each left the wheel at 15 KB): `[tool.hatch.build] exclude = ["/.anvaya", …]`; removing each nested `pyproject.toml` copy individually; removing both together. Moving the whole `.anvaya/` aside from the *same* tree produced the correct 1.0 MB wheel with 279 source files and 32 skills, every time.
- **Workaround:** build release artifacts from a **clean checkout** (CI, or a separate `git worktree`). Verified: a detached worktree of the same commit builds correctly regardless.
- **Avoid:** never treat "Successfully built" as proof a package is complete — assert on artifact *contents* (wheel size, presence of the package dir and bundled data files), not just the exit code. A 15 KB wheel and a 1 MB wheel both exit 0.
- **Still open:** the precise mechanism inside hatchling's file walk is unidentified. The `[tool.hatch.build] exclude` for `.anvaya` is kept because agent scratch should never ship, but it is documented as *not* a fix for this.
### BB-95 — `hachi serve` served JSON at `/` and 404'd every SPA route

- **Symptom:** `hachi serve` printed `Web UI: http://127.0.0.1:8787`, but a browser at that URL got `{"service":"Hachi Gateway",…}`. Navigating to or refreshing any app route (`/conversation`, `/settings`) returned `404`. The web UI was reachable only by typing `/index.html` explicitly and never using deep links.
- **Root cause (two independent defects).**
  1. **Route shadowing.** `system.get("/")` — the service descriptor — is registered *before* the static mount at `/`. Starlette matches in registration order, so the descriptor won the match for `/` while the mount handled everything else.
  2. **`html=True` gives no history fallback.** The mount's comment claimed "the catch-all `html=True` makes `/anything/deep` return `index.html`". It does not: `html=True` resolves *directory-like* paths to `index.html`. A deep path with no matching file raises 404, so every client-side route broke on refresh or direct link.
- **Fix:** `/` now returns `index.html` when a frontend is mounted (the descriptor moved to a new `/status`, which is stable in both modes), and the mount uses `_SPAStaticFiles`, which falls back to `index.html` for unknown non-API paths while still 404ing genuinely missing API routes.
- **Why no test caught it:** the covering test asserted `assert "Hachi" in resp.text`. The service descriptor *is* `{"service": "Hachi Gateway"}` — so the test passed against the broken behaviour and had never once verified the mount. Replaced with a marker string that cannot appear in an API response.
- **Avoid:** an assertion that a substring is present will happily pass on the wrong response whenever the substring is generic. Assert on something only the *intended* response can contain, and prefer asserting the absence of the wrong one too.
- **Found but not fixed (P-35):** four frontend routes collide with REST paths — `/memory`, `/skills`, `/approvals`, `/integrations`. API routes correctly win, so those pages still break on refresh. The fix is a frontend-side prefix (`/app/*`) or moving REST under `/api/*`. Locked as an explicit assertion in `tests/test_serve_frontend_routing.py::test_known_spa_route_collisions` so it cannot be mistaken for a fallback regression.

<!--
When you fix a bug: add BB-N here with a one-line **Avoid:**, link the locking test,
and (if the constraint is subtle) drop a comment next to the code itself — the agent
gets far better attention on a comment beside the function than on a doc three
directories away.
-->
