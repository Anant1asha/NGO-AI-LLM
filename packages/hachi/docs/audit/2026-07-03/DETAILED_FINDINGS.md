# Orchestrator first-hand findings (verified myself, not via agent)

## Gate results (all run this session)

- pytest FULL: **4151 passed / 21 skipped / 0 failed** (281s). Clean.
- frontend: typecheck clean; **119 vitest pass**; production build ok.
- ruff: clean. mypy strict-gate: clean (40 files). import-linter: 3/3 contracts kept.
- skill-lint: 0 errors, 41 warnings across 31 files.
- eval: 14/14 pass. benchmark fast: passed (r@5=0.9677).
- security-audit --fail-on-high: **exit 2, 2 HIGH** — BOTH env-posture, not code:
  - `oauth.google_client_secret_embedded` (real GOOGLE_CLIENT_SECRET in auditor's local .env)
  - `rest.allowlist_missing` (HACHI_REST_ALLOWLIST unset)
  - => CI `--fail-on-high` would be GREEN in clean CI env (no secret set). BUT the rest.allowlist one may fire in CI. VERIFY the check source. NOTE: security job on main is continue-on-error; PR adds --fail-on-medium.

## .env / secrets in git

- `.env` is NOT tracked, NEVER committed (0 history), IS gitignored (.gitignore:65). GOOD.
- Only tracked env files: frontend/.env.example, qa/fixtures/.env.sample (safe samples).

## BENCHMARK HEADLINE DRIFT (confirmed) — MEDIUM/HIGH credibility

- README badge + README:34/148/511 + benchmark.md:4/90-95 all cite: **97.6% savings, 208 vs 8,726 tok, 53 nodes**.
- Source: FROZEN benchmarks/og_bench/data/s_real_results_v1.json (run_date 2026-06-13, static file).
- LIVE reproduction TODAY (tests/test_og_benchmark.py during pytest): **nodes=60 | baseline=11183 | 3-pass=420 | savings=96.2%**.
- Actual default_skills: **31 files / 60 nodes**, NOT 53.
- test only asserts savings>=0.80 (SAVINGS_THRESHOLD), NOT the specific number => drift invisible to CI.
- README says "reproducible" but reproducing gives DIFFERENT numbers. Fix: regenerate frozen json + docs, or label the number as a point-in-time snapshot.
- Methodology caveats (benchmark.md:166): estimate_tokens = chars/4 (NOT real tokenizer); token savings measured on a SINGLE representative query ("persona"/first index keyword), not an average; baseline = dump-all-::full concat (project's own strawman). All disclosed in methodology but the headline hides them.

## README "53 default skills" (README:659) — WRONG

- "all 53 default skills have ::meta + ::index" — there are 31 skill FILES (all 31 have ::index). 53/60 is a NODE count, conflated with file count.

## arXiv citations in benchmark.md (public-facing) — VERIFY

- benchmark.md:33 cites arXiv 2604.27820 "ObjectGraph..." as FIRST-PARTY (Open Gigantic's own paper, Hachi = reference impl).
- benchmark.md:45 "Graph-of-Skills arXiv 2604.05333"; :46 "SkillReducer arXiv 2603.29919" as "independent third-party research."
- IDs are future-dated (2604=Apr2026, 2603=Mar2026). Need web-verify existence. If fabricated => serious launch credibility problem.

---

# AGENT 1: CORE ENGINE (loop/llm/resilience/cost/routing/sub_agent)

VERIFIED MYSELF: \_history lock inconsistency is REAL. add_message (memory.py:714) + apply_pending_compaction (memory.py:800-809) mutate/reassign \_history WITHOUT \_history_lock; background summary job (memory.py:1408) + async compaction (memory.py:1223) DO hold it; loop reads live list by reference (loop.py:979). GIL => practical failure is stale/half-compacted history to LLM, not crash. Rate HIGH (agent said Critical).

- H1 budget cap overrun: caps checked AFTER the call that crosses them (loop.py:914/1075 vs record at 1061). Post-hoc, can overrun by one full generation. max_tokens=0 => only backstop is \_TOKEN_SAFETY_CEILING=2M (loop.py:363). Docstring overstates ("stops if it WOULD cost"). CONFIRMED.
- H2 sub-agents get NO budget/token/wall caps: sub_agent.py:684-691 builds ExecutionLoop without max_cost_usd/max_tokens/per-turn/max_wall_seconds. Timeout only checked on on_event calls (sub_agent.py:792-799). Runaway delegated loop drains spend invisibly. CONFIRMED.
- H3 record_use/signal_skill_switch fire BEFORE load_skill tool executes (loop.py:1140-1151); if tool fails, usage recorded + compaction triggered for nonexistent skill. SUSPECTED.
- H4 cost recorded even on degraded/empty response; stream_usage=False => TokenUsage() all-zeros => silent 0 cost (spend cap under-counts). CONFIRMED-ish.
- M1 ResilientClient.generate_stream fallback re-invokes PRIMARY + double record_failure (resilience.py:403-424 + chain starts at \_inner 327). 1 outage counts as 2. CONFIRMED.
- M2 \_generate_with_retry is DEAD CODE (loop.py:612-635, no caller). CONFIRMED.
- M3 OpenAI-compat streamed tool calls can produce ToolCall(id="") (llm.py:664-685); non-stream defaults id="tool_call" constant (llm.py:552) => two calls collide => mis-pair/400. SUSPECTED.
- M4 broad except: pass swallow tool-arg JSON parse (llm.py:548/683 -> {}), provider caps (registry.py:67), no log. CONFIRMED.
- M5 \_resolve_turn_client swallows ALL router errors at DEBUG (loop.py:604-610) -> silent fallback to default model. CONFIRMED.
- M6 AgentException never raised by loop on iter-limit (returns "[INCOMPLETE]" string loop.py:1246); sub-agent maps iter-limit->TIMEOUT via except that's unreachable => exhausted sub-agent reported SUCCESS. CONFIRMED.
- M7 RoleResolver builtin path ../default_skills/roles (sub_agent.py:436) — verify dir ships in wheel.
- L1 p50 off-by-one (resilience.py:208). L2 breaker never re-opens from half_open (resilience.py:175-192) CONFIRMED design gap. L3 tool exc loses traceback (loop.py:501). L5 classifier docstring stale.

VERIFICATIONS (agent, useful for promise table):

- BB streaming-return-drop: FIXED (resilience.py:394 yield from + return; loop guards None at 1000).
- sub-agent per-subagent model: FIXED (sub_agent.py:591-602).
- include_usage OpenAI-compat: FIXED default stream_usage=True (llm.py:384/625).
- TurnContext frozen: CONFIRMED (@dataclass frozen slots turn_context.py:24).
- Esc-interrupt/cancel/partial exit: CONFIRMED correct (loop.py:645/680/882/1214).
- multi-provider dispatch real (not stubbed): create_llm_client llm.py:758-867 all kinds.

# arXiv citations: BOTH REAL (web-verified). 2604.27820 (ObjectGraph, first-party Mohit Dubey/Open Gigantic, claims 95.3%), 2604.05333 Graph-of-Skills, 2603.29919 SkillReducer. README uses own 97.6% not the paper's 95.3%. OK — not fabricated.

---

# VERIFIED CRITICALS (proven at runtime by orchestrator)

## CRIT-A (memory): automatic per-turn fact extraction is a SILENT NO-OP. CONFIRMED.

- get_memory_vault does NOT exist -> `uv run python -c "from hachi.core.memory_vault import get_memory_vault"` = ImportError (reproduced).
- Referenced job_handlers.py:76,78 (+docstring 147). Prod registration orchestrator.py:3371 `_job_registry.register("extract_fact", handle_extract_fact)` injects NO \_vault_factory.
- Runtime path: sync_turn enqueues handler_name="extract_fact" (no func) -> handle_extract_fact(\_vault_factory=None) -> build_job_context else-branch (job_handlers.py:74-80) -> ImportError -> caught -> ctx.vault=None -> returns "skipped:no_vault" (job_handlers.py:176-183), job COMPLETED, logs MISLEADING "vault not available (ChromaDB not configured?)".
- Untested: tests/test_durable_fact_extraction.py ALWAYS injects \_vault_factory=lambda:vault, never exercises the None/prod path.
- SCOPE: automatic background extraction DEAD. Explicit memory tools (core\_\* ) + compaction flush (\_flush_facts_to_vault uses self.vault) STILL work. So not total memory loss, but the advertised "auto-remember" pipeline is 100% inert + silently masked. Fix: add get_memory_vault() returning ProcessSharedServices.instance().vault, and change bare except to log WARNING w/ exc_info. + regression test w/ no factory.

## CRIT-B / HIGH (tools): file-attachment tool group crashes on every call. CONFIRMED.

- PROVEN: PermissionRequest(tool_name=...) -> TypeError (fields are request_id/operation/tool/target/reason/policy_summary). PermissionGate.check -> hasattr False.
- file_tools.py:311-315 builds PermissionRequest(tool_name/action/resource) + gate.check(req). Both wrong API.
- "files" ToolSpec registered UNCONDITIONALLY orchestrator.py:3082. attach_file/list_attachments/read_attachment/search_attachments all die at call time (loop catches -> "Tool Execution Error"). Untested (test_file_platform.py never calls register_file_tools/gate).
- Fix: use gate.check_path(resource, action) + PermissionResult.allowed like os_tools.

## CORRECTION to tools-agent H1 (move/copy) -> DOWNGRADE to MEDIUM

- copy AND move ARE in \_EXFIL_STEMS (permissions.py:160-161) => blocked_paths IS enforced for them (agent was WRONG they aren't).
- ren/rename NOT in \_EXFIL_STEMS. Real gap: \_raw_run_terminal_command does shutil.move/copy2 (os_tools.py:231/246) WITHOUT gate.check_path(dst,write)/(src,delete) => bypasses allow_delete/allow_write for NON-blocked paths only. MEDIUM defense-in-depth, not HIGH.

# GATEWAY agent (verify later, single-tenant caveat): H1 fail-open auth when auth_token falsy & bind_host None (but real serve path always passes bind_host+token). H2 OpenAI-compat + channel-inbound sessions never set_session_owner => ownerless => any-token-holder readable; channel key "channel:sender" attacker-controlled => cross-contam. H3 /runs/\* no ownership filter. M1 GET /config unmasked (env var names, base_urls, secret_refs - NOT raw keys). M2 /v1/chat/completions ignores requested model. All gated behind single bearer token; single-tenant is documented design => most are "multi-client-single-token" risks. Bearer check IS constant-time+hashed (verified-good by agent).

# PROMISE agent HIGH: slash cmds /compact//new//remember//forget//memory//plan//deep-research//settings//setup//quit//clear all UNIMPLEMENTED (fastapi_app.py:865-897 only /model+/help); /model doesn't switch. README tiers "lightning/guided/strict" wrong (real: sandbox/guided/unrestricted). tokoboros shim reintroduced cli/main.py:151-184 (scope violation). tui/app.py stale (now tui/cockpit/). Cockpit right-rail = hardcoded demo data (chat.py:65-71,174-179,548-556).
