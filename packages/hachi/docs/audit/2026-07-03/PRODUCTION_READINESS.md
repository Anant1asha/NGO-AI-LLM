---

# Hachi — Production-Readiness Audit (pre-open-source launch gate)

**Auditor:** independent staff-level review · **Branch:** `frontend-review` · **Method:** full verification gate run locally + nine deep-dive read-throughs of the source, every finding cited to `file:line`. Load-bearing criticals were reproduced first-hand (marked ✅ **reproduced**), not taken on an agent's word.

## 1. Verdict — **Not yet** (ship-blocking gaps, but a strong foundation)

Hachi is **well above the typical "vibe-coded" bar**: the full test suite is genuinely green (**4151 passed / 21 skipped / 0 failed**), the frontend builds clean (119 vitest pass), lint/type/import-linter gates pass, gateway auth is properly hardened (sha256-hashed bearer, constant-time compare, loopback-by-default, `NO_AUTH` refused off-loopback), and the core ReAct loop defends tool-call pairing at three layers. The README is, unusually, more often _under_-promising than over-promising.

**But it cannot ship as "does what it claims" today.** Multiple headline features are confirmed broken or hollow: the advertised **automatic memory extraction is a silent no-op for every user** (a load-bearing import that doesn't exist), the **file-attachment tool group crashes on every call** (wrong permission-gate API), **"Notion/Slack via OAuth" is a facade** whose tokens nothing consumes, **~85% of the documented slash commands don't exist**, and the **flagship "97.6% benchmark" fails its own CI gate on the corpus that actually ships** (and its headline number measures a query that silently errors). Underneath, the persistence layer has real data-durability defects (a connection leak on every background spend record, per-session schedulers that double-fire and clobber each other's file, "delete session" that leaves the transcript behind, a secrets store that can wipe itself on a torn write) and the resilience/routing subsystem is largely decorative (the circuit breaker can never re-open; the router's health filter reads state nothing ever writes).

None of this is a security catastrophe and little of it is deep engineering to fix — it's concentrated, and roughly **1–2 focused weeks** on the Critical/High list plus a README truth-pass moves this to **"Ship with caveats."** But shipping now would mean advertising features that don't work.

---

## 2. Verification gate — what I actually ran

| Gate                                                           | Result                                                                                                                                                        |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pytest -q` (full suite)                                       | ✅ **4151 passed, 21 skipped, 0 failed** (281 s)                                                                                                              |
| frontend `typecheck` / `vitest` / `build`                      | ✅ clean / **119 passed** / builds                                                                                                                            |
| `ruff check`, `mypy` strict-gate, `import-linter`              | ✅ clean / clean (40 files) / 3-of-3 contracts kept                                                                                                           |
| skill-lint, `eval run`                                         | ✅ 0 errors (41 warns) / 14-of-14                                                                                                                             |
| `security-audit --fail-on-high`                                | ⚠️ exit 2 — 2 HIGH, but **both are env-posture** on the auditor's own `.env` (`GOOGLE_CLIENT_SECRET` present, `HACHI_REST_ALLOWLIST` unset), not code defects |
| `skill benchmark --suite fast` **on shipped `default_skills`** | 🔴 **exit 1** (FPR 0.40 > 0.20 gate) — see C4                                                                                                                 |
| `.env` committed to git?                                       | ✅ **No** — untracked, never committed, gitignored. Secrets are safe from the repo.                                                                           |

---

## 3. Promise vs. reality

Representative; the confirmed-broken rows are the ones that matter for launch. "Works" means I or an agent read the implementation and it does what's claimed.

| Claim (README/docs)                                                                                                                                                                                                     | Status                          | Evidence                                                                                                                                                                                                                                   |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ObjectGraph engine, 3-pass, BM25, typed blocks                                                                                                                                                                          | **Works**                       | `og_engine/engine.py`, `parser.py`; BM25 is real (IDF + length-norm)                                                                                                                                                                       |
| **"97.6% token savings, 53 nodes, reproducible"**                                                                                                                                                                       | **Broken/Misleading**           | Frozen `s_real_results_v1.json` (53 nodes) ≠ shipped corpus (60 nodes/31 files). Headline "3-pass" Pass-2/3 are **13-token error strings** from a query that fails to resolve. FPR gate **fails on shipped corpus**. (C3/C4) ✅ reproduced |
| **Automatic long-term memory (background fact extraction)**                                                                                                                                                             | **Broken (silent)**             | `get_memory_vault` doesn't exist → every extraction job returns `skipped:no_vault`. (C1) ✅ reproduced                                                                                                                                     |
| **File/attachment tools** (`attach_file`, `read_attachment`…)                                                                                                                                                           | **Broken (crash)**              | Gate wrapper calls non-existent `gate.check()` + wrong `PermissionRequest` kwargs → TypeError on every call. (C2) ✅ reproduced                                                                                                            |
| **Native integrations "Google, Notion, Slack — all via OAuth"**                                                                                                                                                         | **Partial/False**               | Only Google uses OAuth. Notion/Slack need pasted API keys; the OAuth token layer exists but **nothing ever calls `.load()`** to use it. (H5)                                                                                               |
| **In-chat slash commands** (13 listed)                                                                                                                                                                                  | **Broken**                      | Only `/model` (display-only) + `/help` implemented; other 11 return "Unknown command". `/model [name]` doesn't switch models. (H4)                                                                                                         |
| Permission gating at call time (tiers)                                                                                                                                                                                  | **Works** (names wrong in docs) | Real tiers `sandbox/guided/unrestricted`; README says "lightning/guided/**strict**" — `strict` exists nowhere. (H7)                                                                                                                        |
| Cost caps (per-session + per-turn, mid-turn stop)                                                                                                                                                                       | **Works**                       | `loop.py` enforces between calls → `[BUDGET LIMIT REACHED]`; caveat: stops _after_ the call that crosses (H2)                                                                                                                              |
| Turn serialization, prompt caching, SQLite job queue, SSE + OpenAI `stream:true`, MCP, browser (SSRF-guarded), vision, voice, injection spotlighting, security-audit, OTel tracing, scheduling, REST adapter, edit-undo | **Works**                       | All verified at cited lines; the "hard-to-fake" internals genuinely exist                                                                                                                                                                  |
| Gateway loopback + hashed bearer + session ownership                                                                                                                                                                    | **Works**                       | `fastapi_app.py:588-593,738-780` (facade-session ownership gap noted in H6)                                                                                                                                                                |
| `pipx install hachi-og`                                                                                                                                                                                                 | **Broken**                      | Package is **not on PyPI** (404); `release.yml` ready but no release cut. (H9)                                                                                                                                                             |
| Governed self-learning: "lint + dense-budget **rejection**", "`::assertions` machine-checkable **before execution**"                                                                                                    | **Partial**                     | Only dense-budget rejects; lint is advisory-after-write. Assertions have **no enforcement point** — voluntary tool/CLI only. (M-gov)                                                                                                       |

---

## 4. Findings by severity

Consolidated across all reviewers; duplicates merged. **✅ reproduced** = I verified it first-hand this session.

### 🔴 Critical — broken core functionality / data loss

**C1 — Automatic memory extraction is a silent no-op for every user.** ✅ reproduced
`core/runtime/job_handlers.py:76,78` imports `get_memory_vault` from `core/memory_vault.py` — **the symbol does not exist** (`python -c "from hachi.core.memory_vault import get_memory_vault"` → ImportError). Production registers the handler with no vault factory (`gateway/orchestrator.py:3371`), so every per-turn `extract_fact` job hits the ImportError, is swallowed (`job_handlers.py:79`), sets `ctx.vault=None`, and returns `"skipped:no_vault"` — job marked **COMPLETED**, logging a _misleading_ "ChromaDB not configured?" warning. The advertised "you never need to say 'remember this'" pipeline writes nothing. Untested: `tests/test_durable_fact_extraction.py` always injects `_vault_factory`, so the real path is never exercised. (Explicit memory tools + compaction-flush still work, so it's not total memory loss.) **Fix:** implement `get_memory_vault()` returning `ProcessSharedServices.instance().vault`; change the bare `except` to log with `exc_info`; add a regression test with no injected factory. _(A second, independent bug compounds this: `core/memory.py:222` gates `extract_facts` on `ANTHROPIC_API_KEY` even when a working non-Anthropic client is injected — so auto-memory is doubly dead for Ollama/Groq/OpenRouter users.)_

**C2 — File-attachment tool group crashes on every invocation.** ✅ reproduced
`tools/file_tools.py:311-315` builds `PermissionRequest(tool_name=…, action=…, resource=…)` and calls `gate.check(req)`. Neither exists: `PermissionRequest` fields are `request_id/operation/tool/target/reason/policy_summary` (→ `TypeError`, reproduced), and `PermissionGate` has no `.check()` (only `check_path`/`check_command`/`require_action`; `hasattr` → False). Registered unconditionally (`orchestrator.py:3082`), so `attach_file`/`read_attachment`/`list_attachments`/`search_attachments` all throw when called. No test exercises the gated path. **Fix:** use `gate.check_path(resource, action)` + `PermissionResult.allowed`, like `os_tools`.

**C3 — The headline benchmark number measures a failed query.** ✅ reproduced
The "97.6% / 208 vs 8,726 tokens" figure comes from a representative query `keywords[0]` = `"persona"`, which resolves to the ambiguous node name `identity` (6 nodes) that the resolver refuses to load. Reproduced live: Pass-2 and Pass-3 are **13 tokens each — the length of `"Skill 'identity' not found"` error strings**, not a real skill load. A _correct_ single-skill load produces a larger 3-pass total and a lower savings number. The marquee proof of the moat is, right now, proof that a query silently failed cheaply. `benchmark.md`, the README badge, and the frozen JSON all carry this number. **Fix:** pick a representative query that resolves to exactly one skill; assert `resolve_node(candidates[0])` does not start with `"Error:"`; better, average over the probe set.

**C4 — The benchmark's own CI gate fails on the corpus that ships.** ✅ reproduced
Frozen `benchmarks/og_bench/data/s_real_results_v1.json` claims 53 nodes / FPR 0.0. The repo actually ships **31 files / 60 nodes**. Run against `src/hachi/default_skills`: `skill benchmark --suite fast --json --threshold 0.80` → **exit 1**, because negative-probe **FPR = 0.40** (2 of 5 negatives now match via 2-char prefix over-matching, e.g. `"capacitor"` → `core_finance` on keyword "market **cap**"; `engine.py:439-474`). The README prints "FPR 0.0000 ✅". My earlier "passed" run only passed because my machine's _installed_ skills dir is a stale 53-node copy. CI runs the no-`--dir` form, which bootstraps the 60-node set — so **the benchmark job is red on a clean checkout**, contradicting "reproducible" and "CI gates retrieval quality per-PR". **Fix:** regenerate the frozen JSON from the live corpus in CI (make it an artifact, not a committed constant); fix the prefix-matcher (min length ≥4); add `n001`/`n003` as regression probes.

### 🟠 High — real bugs affecting normal use

**H1 — `_history` is mutated without its lock; background compaction races the turn.** ✅ reproduced
`memory.py:714` (`add_message`) and `:800-809` (`apply_pending_compaction`) mutate/reassign `_history` **without** `_history_lock`, while the background summary job (`:1408`) and async compaction (`:1223`) hold it, and the loop passes the live list by reference to the provider (`loop.py:979`). CPython's GIL prevents a hard crash, but the LLM can be sent a half-compacted history, and a summary can be applied to a message being serialized — including splitting a `tool_use`/`tool_result` pair (→ provider 400). **Fix:** hold the lock on all reads/writes, or snapshot under the lock.

**H2 — Background spend recording leaks a SQLite connection on every call.** ✅ reproduced
`core/cost.py:142,218` imports `from hachi.gateway.orchestrator import _get_session_store` — **another non-existent symbol** (ImportError reproduced). Swallowed → every `record_background_usage`/`record_voice_usage` (fact-extraction, titling, voice) falls through to a fresh `SessionStore()` that runs schema init + migrations and is **never closed** — a leaked WAL connection per background job (holds `sessions.db-wal/-shm` handles on Windows). **Fix:** resolve via `ProcessSharedServices` (as `fastapi_app._resolve_session_store` already does) or `try/finally: store.shutdown()`.

**H3 — Per-session Scheduler over one shared file: double-fires and lost writes.**
`orchestrator.py:2871` builds `Scheduler(ScheduleStore(schedules_file))` and `:3487` a `ScheduleRunner` **per session**; `Scheduler` caches `_schedules` in memory and never re-reads. Three open web sessions → the same cron entry fires 3× (3 LLM runs, 3 webhook POSTs); session B's `set_enabled`/`mark_fired` persists a stale list that **erases** a schedule session A just added. **Fix:** make the Scheduler a `ProcessSharedServices` singleton, or reload-under-lock before each mutate.

**H4 — ~85% of advertised slash commands don't exist.**
`gateway/fastapi_app.py:815-897` implements only `/model` (display-only) and `/help`. `/clear /compact /new /sessions /memory /remember /forget /plan /deep-research /settings /setup /quit` all return "Unknown command" (grep across `src/` finds no handlers). The web composer advertises yet a _third_ vocabulary (`ConversationComposer.tsx:27-37`: `/routine /dry-run /budget /delegate…`), also non-functional. **Fix:** implement the handlers (several map 1:1 to existing endpoints) or trim the README + `_SLASH_HELP_TEXT` to the two that exist.

**H5 — "Notion/Slack via OAuth" is a facade whose tokens are never consumed.**
`integrations/notion/service.py:29,41` and `slack/service.py:42,61` require pasted API/bot tokens. The OAuth connector layer (`connector_registry.py`, `oauth_flow.py`, `/integrations/{id}/oauth/start`) stores tokens but the **only** non-UI caller of `OAuthTokenStore` is `orchestrator.py:318` (`is_connected()` for capability gating) — nothing calls `.load()` to authorize an API request. Connecting Notion/Slack via OAuth in the UI yields tools that still error asking for a key. **Fix:** bridge the OAuth callback to the service vault keys, or reword to "Google via OAuth; Notion/Slack via API tokens".

**H6 — Facade sessions and `/runs/*` skip ownership (multi-client-single-token exposure).**
`/v1/chat/completions` (`fastapi_app.py:1519`) and `/channels/{channel}/inbound` (`:1703`) create sessions via `get_or_create_session`/`complete_chat` that **never call `set_session_owner`** → ownerless sessions are readable by any bearer holder. The channel key is `f"{channel}:{sender}"` with attacker-controlled `sender` → two senders presenting the same id share one agent memory. `/runs`, `/runs/{id}`, `/runs/{id}/wake`, `DELETE /runs/{id}` (`:2358-2470`) have **no owner filter** (unlike `list_sessions`). Consistent with the _documented_ single-tenant model, so severity is bounded — but the moment a second principal shares the install, these leak. **Fix:** stamp ownership on facade-created sessions; apply the `list_sessions` owner filter to `/runs`.

**H7 — Resilience/routing subsystem is largely decorative.**
Two independent core reviews confirmed: the circuit breaker never re-opens from half-open (`resilience.py:175-192` only opens from `closed`), so protection lasts exactly one cooldown; and the router's health filter (`routing/router.py:233`) reads `provider.health()`, which is only updated by `update_health()` — **called nowhere** (grep-verified) — so routing keeps re-selecting a dead provider as primary. Mid-stream failover re-invokes the _primary_ and double-bills/double-prints (`resilience.py:403-424`). Unknown model ids are synthesized as `provider="anthropic"` (`router.py:315`) → guaranteed 404 for a mistyped non-Anthropic model. **Fix:** wire recorded outcomes into `provider.update_health`; add half_open→open on failure; exclude the primary from the stream-recovery chain; infer provider for synthetic descriptors.

**H8 — "Delete session" doesn't delete the transcript; nothing is ever pruned.**
`session_store.py:814-867` deletes only `messages`+`sessions`; the same session's `interaction_log` (verbatim user input + agent output) and `idempotency_keys` (full stored responses) survive and remain readable via `get_interactions()` — a broken privacy promise. Separately, `jobs.db`, `interaction_log`, `idempotency_keys`, `daily_spend`, and edit-undo checkpoint snapshots have **no retention anywhere** (`cleanup_completed` is defined 3× and called by zero production code) — every install grows monotonically. **Fix:** cascade deletes; add a retention sweep to the worker's idle loop.

**H9 — `pipx install hachi-og` is broken; installer is the only working path.**
`https://pypi.org/pypi/hachi-og/json` → 404; no release cut (`version = "0.1.0"`, no tags). The README's most prominent install path fails with "No matching distribution". **Fix:** publish `0.1.0` before launch, or mark it "coming soon" and lead with the `install.sh`/`git clone` paths (which work).

### 🟡 Medium — maintainability, hardening, honesty gaps

- **M1 — Secrets store self-wipes on a torn write.** `secret_store.py:342-353` writes `secrets.enc` via bare `write_text` (no temp+rename); `_read_blob` returns empty on any parse error, so the next `set()` rebuilds the file from an empty read — **destroying every other fallback-stored credential**. Same non-atomic pattern in `onboarding_state.json`, `skill_usage.json`, `secrets_metadata.json` (while `checkpoints` and `ScheduleStore` do it correctly — inconsistent house style). **Fix:** one shared `atomic_write_json()` (temp + `os.replace`); back up unparseable files instead of overwriting.
- **M2 — Governance claims are honor-system.** Lint never rejects a skill write (only dense-budget does; `engine.py:1330`); `::assertions` have no enforcement point in the loop — checkable only via an optional tool/CLI. These are the two headline differentiators vs Hermes. **Fix:** reword, or add an auto-check on skill load.
- **M3 — `move`/`copy`/`ren` bypass the write/delete gate.** `_raw_run_terminal_command` runs `shutil.move`/`copy2` (`os_tools.py:231,246`) without `gate.check_path(dst,"write")`/`(src,"delete")`, so they bypass `allow_delete`/`allow_write` for non-blocked paths. (`blocked_paths` _is_ still enforced — `copy`/`move` are in `_EXFIL_STEMS`; `ren`/`rename` are not.) **Fix:** route native file built-ins through `check_path`.
- **M4 — REST allowlist is off by default; daemon webhook is SSRF-unguarded.** With `HACHI_REST_ALLOWLIST` unset the adapter will call any public host (`rest_adapter.py:132`); and the resident scheduler's `deliver_result` (`scheduler.py:471`) POSTs with **no** `net_guard` check (the CLI path has one) — an LLM-set `webhook_url` can hit internal addresses. **Fix:** fail-closed allowlist; route both webhook paths through `validate_outbound_url`.
- **M5 — `GET /config` returns unmasked config** (`fastapi_app.py:1363`): env-var names, `base_url`s, `secret_ref`s (not raw keys). Inconsistent with the masked `/providers`. **Fix:** mask/redact.
- **M6 — OpenAI-compat endpoint ignores the requested `model`** (`:1529`, echoed only) and its rate limiter is a single global bucket (`:1524`). **Fix:** allowlist + per-principal keying.
- **M7 — Silent tool-arg corruption.** On `max_tokens` mid-tool-call or malformed JSON, both clients fall back to `input={}` with no log (`llm.py:548,683`) and execute the tool with empty args; `stop_reason`/`finish_reason` is never surfaced. Providers that omit streamed tool-call ids yield `ToolCall(id="")` → colliding `tool_use_id`s → pairing 400. **Fix:** synthesize unique ids; propagate finish reason; fail the call on truncation instead of running with `{}`.
- **M8 — MemoryGuard is a 6-regex English blocklist** (`memory_guard.py`): trivially bypassed (non-English, homoglyphs, base64) and false-positives on legitimate first-person facts ("I act as team lead" → blocked). Fine as defense-in-depth, must not be the only line. Also, three read paths (`get_user_snapshot`, `get_agent_snapshot`, `get_recent_facts`) inject stored docs into the system prompt **without redaction** (redaction is search-only).
- **M9 — Declared SDK extras nothing imports.** `slack-sdk`, `notion-client`, `google-auth`, `google-api-python-client` are declared extras but imported **nowhere** (integrations use `httpx`); deptry flags them every run. **Fix:** drop them.
- **M10 — `tokoboros` compat shim reintroduced** (`cli/main.py:151-184`, `gateway/workspace.py:49-90`) — a direct violation of the project's own inviolable rule ("do not reintroduce; tracked code stays tokoboros-free"). Three reviewers flagged it independently. **Fix:** remove, or formally reverse the rule.
- **M11 — ARCHITECTURE.md is staler than the README** (the "map" contributors are told to trust): points permissions at the nonexistent `tools/permissions.py`, documents `POST /sessions/{id}/chat` (real route is `/messages`), labels `/events` as SSE (it's a JSON snapshot). Plus README drift: "TanStack **Start**" (it's `@tanstack/react-router` SPA), `tui/app.py` (now `tui/cockpit/`), "53 default skills" (31 files / 60 nodes).
- **M12 — Missing OSS governance:** no `CODE_OF_CONDUCT.md`, no issue/PR templates, no `CODEOWNERS`. `frontend/package.json` has no `license` field. LICENSE year is 2025 on a 2026 codebase.
- **M13 — `docker compose up --build` fails on a clean clone** — the declared secret file `./.hachi/gateway_api_token.txt` doesn't exist and isn't created by the documented one-liner (`docker-compose.yml:58-60`).
- **M14 — Cost accounting edges:** unknown/local (Ollama) models are billed at fictional `_DEFAULT_PRICING (1.0, 5.0)` (`cost.py:47`) → a daily cap can trip on free local usage; daily-spend keys on local `date.today()` while timestamps are UTC (cap window skews near midnight); a negative per-turn delta after a tracker reset is silently dropped.

### 🟢 Low — polish

Missing icons render blank (`SpendSection.tsx:504` `bar-chart`, `memory.tsx:547` `loader` spinner); dead frontend subsystems (`useRouteLoaders.ts` + `cache.ts` never wired; generated `schema.d.ts` imported nowhere — domains hand-roll types, defeating contract-safety); Home-screen approve/decline + "Run now" + "Retry failed" are **optimistic-only, no gateway call** (`store.ts:757-839`) — the user sees success while the backend is untouched; TUI right-rail renders hardcoded demo plan/approval data (`cockpit/views/chat.py:65-71,548-556`); `_generate_with_retry` and per-session tool thread pool leak (never shut down); p50 off-by-one; `estimate_token_count` re-serializes every block on every `add_message`. Positive: the Markdown renderer is XSS-safe by construction (React nodes + scheme allowlist), no `pickle`/`yaml.load`/`eval`/`shell=True` anywhere, SSRF core guard (`net_guard.py`) is genuinely thorough (DNS-pinning, blocks cloud metadata), and the SQLite cores are well-engineered (WAL, busy_timeout, parameterized throughout — no SQL injection found).

---

## 5. Prioritized action plan (before open-sourcing)

**Ship-blockers (fix first):**

1. **C1** — implement `get_memory_vault()` (+ fix the `ANTHROPIC_API_KEY` gate) so auto-memory actually works; add the missing regression test.
2. **C2** — fix `file_tools` to use the real gate API.
3. **H2** — fix `cost.py`'s `_get_session_store` import (connection leak).
4. **C3 + C4** — fix the benchmark representative query and the FPR prefix-matcher; regenerate the frozen results in CI; correct the README badge/numbers. (The benchmark is the product's central marketing claim — it must be honest and green.)
5. **H4 + H5 + H7-tier-names** — README/docs truth-pass: implement or delete the slash commands; fix "Notion/Slack via OAuth"; fix tier names.
6. **H9** — publish `hachi-og` to PyPI or remove the `pipx` claim.

**High (fix before real users):** 7. **H1** — lock `_history` consistently. 8. **H3** — process-level Scheduler singleton. 9. **H8** — cascade session deletes + a retention sweep. 10. **M1** — one atomic-write helper everywhere. 11. **H6** — stamp ownership on facade sessions + `/runs`. 12. **H7-resilience** — wire provider health / breaker feedback (or delete the dead machinery and stop advertising it).

**Medium (launch hygiene):** 13. Remove the tokoboros shim (M10) or reverse the rule. 14. Rotate the ~20 live secrets in the local `.env`. 15. Drop the dead SDK extras (M9). 16. Fix ARCHITECTURE.md + README drift (M11). 17. Add CoC / issue+PR templates / CODEOWNERS / frontend license (M12). 18. Fix `docker compose` secret bootstrap (M13). 19. SSRF-guard the daemon webhook + fail-closed REST allowlist (M4). 20. Mask `GET /config` (M5).

---

## 6. Open-source readiness checklist

| Item                             | Status                                                                                                                                                            |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LICENSE (MIT)                    | ✅ present (year 2025; frontend subpkg unlicensed)                                                                                                                |
| CONTRIBUTING.md                  | ✅ present, solid                                                                                                                                                 |
| SECURITY.md                      | ✅ present, strong (slightly stale CVE list)                                                                                                                      |
| CODE_OF_CONDUCT.md               | ❌ missing                                                                                                                                                        |
| Issue / PR templates, CODEOWNERS | ❌ missing                                                                                                                                                        |
| CI                               | ✅ strong (3-OS pytest + security + lint + import-linter + eval + frontend-contract + docker-smoke) — **but the `benchmark` job is red on a clean checkout (C4)** |
| Tests                            | ✅ genuinely meaningful; 4151 pass; 0 xfail, 0 unconditional skips, ~0 tautologies                                                                                |
| README install paths             | ⚠️ `install.sh`/`.ps1` work; **`pipx install hachi-og` broken (H9)**; tier names wrong                                                                            |
| Secrets in git                   | ✅ `.env` untracked/never committed — but ~20 live keys on disk to **rotate**                                                                                     |
| Docker                           | ⚠️ images build in CI; **`compose up` fails on clean clone (M13)**                                                                                                |
| Docs accuracy                    | ⚠️ README ~90% honest; ARCHITECTURE.md has 3 wrong load-bearing facts; benchmark doc stale                                                                        |

---

**Bottom line:** the foundation is real and the tests are launch-grade, but the audit found **4 confirmed criticals and 9 highs** — several of them advertised features that silently don't work — plus real data-durability defects. Fix the Critical/High list and do the README truth-pass, and Hachi is a credible open-source release. Ship it today and the first contributor who runs `/remember`, attaches a file, connects Slack via OAuth, or reproduces the benchmark will find it doesn't do what the README says.

The detailed working notes (every finding with `file:line`, failure scenario, suggested fix, plus runtime-reproduction transcripts) are preserved at [`DETAILED_FINDINGS.md`](DETAILED_FINDINGS.md). No code was changed — this is report-only, per the audit rules.

---

## 7. Independent re-verification (second pass, same day)

A second independent pass re-verified this report's load-bearing claims against the working tree (branch `frontend-review`, HEAD `d293c82`) without relying on the original session's evidence. **15 of 15 spot-checked findings confirmed accurate:**

- **C1** — `get_memory_vault` absent from `core/memory_vault.py` (only `MemoryVault` class + module helpers exist); imported at `job_handlers.py:76`.
- **C2** — `PermissionRequest` fields start `request_id` (no `tool_name`); `PermissionGate` exposes only `check_path`/`check_command` (no `.check()`); wrong API used at `file_tools.py:316-321`.
- **H2** — `_get_session_store` defined nowhere in `gateway/`; imported at `cost.py:142,218`.
- **C4 (corpus half)** — frozen JSON says `nodes: 53`; `src/hachi/default_skills` ships 31 `.og` files (60 nodes per live bench run).
- **H9** — `https://pypi.org/pypi/hachi-og/json` → 404, re-checked live this pass.
- **H4** — `_SLASH_HELP_TEXT`/`_handle_slash_command` (`fastapi_app.py:815-897`) implement only `/model` (display-only) + `/help`.
- **H7 (tiers)** — README:151 "lightning / guided / strict" vs real `sandbox`/`guided`/`unrestricted` (`permissions.py:219,237,262`).
- **H7 (resilience)** — `update_health` has exactly 2 definitions and 0 callers repo-wide; `record_failure` requires `_breaker == "closed"` to open (`resilience.py:184`), so half-open never re-opens.
- **H1** — `_history.append` (`memory.py:730`) and `_history` reassignment (`memory.py:801-809`) run without `_history_lock`; lines 1223/1408 do hold it.
- **H3** — per-session `Scheduler(ScheduleStore(...))` at `orchestrator.py:2871`, per-session `ScheduleRunner` at `:3487`.
- **H8** — `delete_session` (`session_store.py:814-833`) deletes only `messages`+`sessions`; `interaction_log` and `idempotency_keys` tables in the same DB survive.
- **M1** — `secret_store.py:342-353` bare `write_text`, no temp+rename.
- **M10** — tokoboros shim at `cli/main.py:151-184` + `gateway/workspace.py:19,50`.
- **Low (frontend demo store)** — `resolveApproval` (`frontend/src/lib/store/store.ts:515-551`) mutates local state only, no gateway call; hardcoded demo result string at `store.ts:573`. Still true after the Wave 0–3 frontend commits (July 1), which predate this audit.
- **arXiv citations in benchmark.md** — closed as NOT fabricated (all three papers web-verified real; see DETAILED_FINDINGS.md).

Full `pytest` suite re-run this pass on the current tree: **4151 passed / 21 skipped / 0 failed** (374 s, exit 0) — identical to the original run.
