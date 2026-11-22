> **Historical document.** Written before the rename to Hachi. References to
> the `hachi` CLI, `HACHI_*` env vars, and `src/hachi/...` paths
> below describe the project **Hachi** (package `hachi`, CLI `hachi`, dist
> `hachi-og`) and are preserved here as migration history.

## Plan: Hachi God-Tier Upgrade

Hachi should evolve from a strong local single-session agent runtime into a local-first, single-operator control plane. Preserve the strongest existing ideas — ObjectGraph, PermissionGate intent, ToolRegistry, runtime events/read models, and sub-agent isolation — and replace the weak points: ad hoc host execution, best-effort background threads, regex-only memory safety, mutable shared session state, and the absence of a real gateway, scheduler, deployment story, or self-improvement pipeline.

**Current review**

- P0 security blockers:
  1. `src/hachi/core/oauth.py` hardcodes a Google client secret fallback and uses it in both token exchange and refresh.
  2. `src/hachi/tools/os_tools.py` executes raw terminal commands with `shell=True`.
  3. `src/hachi/core/mcp_client.py` uses `shell=True` on Windows and inherits the host environment into MCP subprocesses.
  4. `src/hachi/core/rest_adapter.py` issues arbitrary outbound HTTP requests with token interpolation and no SSRF/allowlist policy.
  5. `src/hachi/core/sandbox.py` is process isolation only, not a secure sandbox boundary, and still passes host environment details such as `USERPROFILE`.
  6. `src/hachi/core/memory_guard.py` uses a small regex list that is too weak for persistent-memory prompt injection defense.
- P1 architectural issues:
  1. `src/hachi/gateway/orchestrator.py` no longer mutates `loop.base_system_prompt` per chat, but it still shares `ExecutionLoop`/`MemoryManager` state with no per-session serialization or concurrency control.
  2. `src/hachi/core/memory.py` still has daemon-thread fallback paths and silent exception swallowing outside the queued path, so memory updates can still be dropped invisibly.
  3. `src/hachi/gateway/orchestrator.py` and `src/hachi/tools/delegation_tools.py` now have queue hooks, but background work is still not fully durable end-to-end and lacks a broader retry/health story beyond the in-memory queue.
  4. `src/hachi/og_engine/engine.py` only prints malformed skill parse failures, so skill registry corruption is easy to miss.
  5. `src/hachi/core/session_store.py` is append-only and simple, but not yet a full turn/event store with transactional turn boundaries, FTS, or recovery semantics.
- P1 product/ops gaps:
  1. Gateway foundations exist (`connect`, `chat`, `events`, readiness), but there is still no long-lived daemon with auth, pairing, or remote-safe multi-surface control plane.
  2. No scheduler/cron subsystem; only `core_suspend_workflow` exists.
  3. No Dockerfile, docker-compose, backup/restore tooling, or VPS deployment assets.
  4. CI now runs tests, security audit, lint, and mypy, but lint/type checks are informational and the matrix is still thin.
  5. Tests now cover gateway boot/TUI handshake basics and TurnContext, but still do not cover loop correctness, MCP lifecycle, delegation, concurrency, or end-to-end memory behavior.
- P2 strategic gaps:
  1. No true self-improvement loop. Current code has memory extraction and skill usage analytics, but no candidate-skill synthesis, review pipeline, or automatic skill revision loop.
  2. No per-surface access profiles or pairing model for multi-surface operation.
  3. No structured logs, traces, metrics, or incident bundle yet; `doctor` and `security-audit` exist, but diagnostics/export depth is still below the reference projects.

**Feature gaps**

- Must-have from the reference set:
  1. Local-first gateway daemon with typed WS/HTTP control plane, auth, pairing, idempotency, health, and remote-safe defaults.
  2. Real sandbox boundary with container backend, resource limits, egress policy, workspace mount policy, and per-agent access profiles.
  3. Durable memory stack: active memory, searchable transcripts, semantic memory, provenance, redaction, TTL/review, and compaction.
  4. Scheduled automations/job delivery across supported surfaces.
  5. Multi-surface clients: CLI/TUI first, Web UI second, messaging gateway third.
  6. Observability: structured logs, traces, metrics, security audit, diagnostics export, and operator health views.
  7. Hard secret handling and environment isolation.
  8. Clear packaging/deployment path: local dev, Docker/Compose, VPS install, backup, update, restore.
- Nice-to-have:
  1. Voice/TTS/STT.
  2. Paired remote nodes/mobile surfaces.
  3. Model router/failover and workload-aware model selection.
  4. Policy-as-code for skills/tools/MCP servers.
  5. Signed plugin/skill distribution and marketplace.
  6. Eval/trajectory export for learning and benchmarking.
- Roadmap framing:
  1. MVP: secure local single-user assistant with TUI/CLI, durable memory, hardened tool policy, and honest docs.
  2. v1: gateway daemon, web UI, messaging surfaces, scheduler, Docker/VPS deployment, and operator observability.
  3. God-tier: multi-agent routing, self-improving skill loop, paired nodes, evaluations, backups, and polished one-click ops.

**Target architecture**

- Control plane:
  1. A long-lived Gateway daemon owns sessions, auth, routing, jobs, surfaces, and event streaming.
  2. Introduce a typed protocol with `connect` handshake, `req/res/event` envelopes, idempotency for side effects, and capability discovery.
  3. All surfaces become gateway clients: CLI, Textual TUI, Web UI, webhook/messaging bridges, then future mobile/node clients.
- Agent runtime:
  1. Replace shared mutable in-process session state with a Session Supervisor that serializes turns per session.
  2. Turn execution uses an immutable TurnContext instead of mutating shared `base_system_prompt`.
  3. ToolRegistry becomes policy-aware, trace-aware, and surface-aware.
- Memory:
  1. Active memory = current turn history plus structured checkpoint.
  2. Episodic memory = session transcripts, summaries, and searchable history.
  3. Semantic memory = facts, user profile, agent profile, delegation reports, all with provenance and review state.
  4. Learning loop = insight extractor -> candidate skill/rule -> human review -> publish into skill registry.
- Sandbox and security:
  1. Host tools become privileged, not default.
  2. Add sandbox backend interface with `process` backend for development and `container` backend for production.
  3. Enforce egress policy, filesystem roots, secret mounts, and browser/profile isolation.
  4. Add gateway auth + device/surface pairing + per-agent access profiles.
- Skills and tools:
  1. Keep ObjectGraph, but add typed manifests, linting, compilation diagnostics, signed packs, and policy metadata.
  2. Separate skill retrieval, skill execution contract, and skill lifecycle/learning.
  3. Add MCP lifecycle controls: discovery, health, tool filters, retries/circuit breakers.
- Data and observability:
  1. Replace fire-and-forget daemon threads with a durable job queue for prefetch, sync, delegation persistence, and scheduled jobs.
  2. Add structured logs, traces, metrics, audit events, health/readiness, and diagnostics export.
- Deployment:
  1. Support local dev install and Docker/Compose single-user VPS as first-class deployment modes.
  2. Add backup/restore for sessions, skills, configs, secret metadata, and vector stores.

**Suggested folder evolution**

1. Keep the current packages during transition, but grow toward these domains:
   - `gateway/` for daemon, protocol, auth, routing, transports.
   - `runtime/` for session supervisor, turn context, tool execution contract.
   - `memory/` for active, episodic, semantic, learning, redaction, retention.
   - `security/` for audit, policy, pairing, secret references, incident tooling.
   - `sandbox/` for backend interface, process backend, container backend, network policy.
   - `surfaces/` for TUI, CLI client, Web UI, messaging bridges.
   - `jobs/` for scheduler and durable worker queue.
   - `observability/` for logs, metrics, tracing, diagnostics.
   - `skills/` for registry, compiler, linter, publisher.
2. Migrate incrementally rather than rewriting in one pass; keep current imports working via compatibility shims until the daemon/gateway split stabilizes.

**Steps**

1. Phase 0 — Security truthfulness and ship blockers:
   - Remove the committed OAuth secret fallback and fail fast on missing OAuth client configuration.
   - Replace `shell=True` execution paths with argv-based subprocess spawning and explicit command policy checks.
   - Add outbound URL policy and SSRF protection to the REST adapter.
   - Scrub subprocess environments for MCP/sandbox execution and explicitly classify the current process sandbox as development-only.
   - Add a real `security audit` command that detects dangerous settings, open surfaces, secret leakage, and unsafe tool posture.
2. Phase 1 — Runtime correctness and durability. Depends on Phase 0:
   - Refactor `AgentSession.chat()` into a serialized session actor or locked turn runner; stop mutating shared loop prompt state.
   - Introduce TurnContext and typed ToolResult/Error contracts in the execution loop.
   - Replace background daemon threads with a small durable job queue plus retry/backoff and visible failure events.
   - Upgrade SessionStore to persist turns/events transactionally and prepare for FTS transcript search.
3. Phase 2 — Memory system redesign. Depends on Phase 1:
   - Split `MemoryManager` into active history, compaction/checkpointing, fact extraction, and long-term recall services.
   - Keep the dual-collection idea in MemoryVault, but put it behind the existing provider abstraction and add provenance, TTL, review state, and redaction.
   - Add episodic transcript indexing and search.
   - Improve memory safety beyond regex scanning: explicit untrusted-content wrapping, layered sanitization, threat scoring, and quarantine paths.
4. Phase 3 — Gateway daemon and surfaces. Depends on Phase 1; can overlap with Phase 2 once persistence contracts are stable:
   - Introduce a Gateway daemon with typed WS/HTTP API, auth token, pairing, idempotency keys, health, and readiness.
   - Rework CLI/TUI into gateway clients instead of direct boot owners.
   - Add a protected Web UI/dashboard.
   - Add a scheduler/job-delivery subsystem before messaging surfaces.
5. Phase 4 — Skill and tool ecosystem hardening. Parallel with late Phase 3:
   - Add ObjectGraph lint/compile diagnostics and manifest validation.
   - Build signed/managed skill packs and explicit capability metadata.
   - Add tool policy layers (`allow/ask/deny`, sandbox-required, surface restrictions).
   - Add MCP health, retries, per-server tool filtering, and inventory state.
6. Phase 5 — Self-improvement loop. Depends on Phase 2 and Phase 4:
   - Capture repeated successful workflows and failure recoveries.
   - Generate candidate skills or rule updates from trajectories.
   - Require review/approval before activation in MVP/v1; only consider autonomous publish later.
   - Add stale-skill pruning, skill regression tests, and usage-driven refinement.
7. Phase 6 — Ops, deployment, and trust. Depends on Phase 3:
   - Add Dockerfile, Compose, backup/restore, update/migration workflows, and VPS docs.
   - Add production docs: trust model, threat model, incident response, hardening baselines, and operator runbooks.
   - Expand CI to lint/type/security/test matrix and artifact builds.

**Relevant files**

- `d:/OpenGigantic/hachi/src/hachi/gateway/orchestrator.py` — Main refactor anchor. `AgentSession.chat()` currently mutates prompt state, owns persistence hooks, and should become the session-supervisor seam.
- `d:/OpenGigantic/hachi/src/hachi/core/loop.py` — Preserve ReAct orchestration, but replace stringly tool errors with typed results and policy-aware execution.
- `d:/OpenGigantic/hachi/src/hachi/core/memory.py` — Split active memory, compaction, and fact extraction into distinct services.
- `d:/OpenGigantic/hachi/src/hachi/core/memory_vault.py` — Keep the dual-collection concept, add provenance/redaction/TTL/provider abstraction.
- `d:/OpenGigantic/hachi/src/hachi/core/session_store.py` — Upgrade from message log to transactional turn/event store plus transcript search.
- `d:/OpenGigantic/hachi/src/hachi/core/oauth.py` — Remove embedded secret, add safer OAuth configuration/state/PKCE handling.
- `d:/OpenGigantic/hachi/src/hachi/tools/os_tools.py` — Replace shell execution and add auditable command policy.
- `d:/OpenGigantic/hachi/src/hachi/core/mcp_client.py` — Remove shell-mode startup, isolate env, and add lifecycle health/circuit breaking.
- `d:/OpenGigantic/hachi/src/hachi/core/rest_adapter.py` — Add URL allowlists, secret interpolation policy, and SSRF controls.
- `d:/OpenGigantic/hachi/src/hachi/core/sandbox.py` — Recast as development backend beneath a new sandbox interface; container backend becomes the real security path.
- `d:/OpenGigantic/hachi/src/hachi/core/memory_guard.py` — Replace regex-only persistence scanner with layered untrusted-content policy.
- `d:/OpenGigantic/hachi/src/hachi/og_engine/engine.py` — Replace print-based diagnostics with structured validation/linting and compiled skill registry reporting.
- `d:/OpenGigantic/hachi/src/hachi/cli/main.py` — Convert to client/ops entrypoint; `doctor()` should evolve into environment + security + runtime diagnostics.
- `d:/OpenGigantic/hachi/src/hachi/tui/app.py` — Preserve event-driven UI/read-model design, but source data from gateway streams instead of in-process callbacks.
- `d:/OpenGigantic/hachi/.github/workflows/ci.yml` — Expand into lint/type/test/security matrix and build pipeline.
- `d:/OpenGigantic/hachi/README.md` — Align claims with delivered phases and add honest deployment/security guidance.

**Verification**

1. Static gates:
   - `uv run ruff check .`
   - `uv run mypy src`
   - secret scan and SAST (`gitleaks`, `bandit`/`semgrep` or equivalent)
2. Runtime unit tests:
   - permission policy, tool policy, prompt wrapping, memory redaction, gateway auth/pairing, skill compiler/linter
3. Integration tests:
   - boot -> session chat -> tool call -> persistence -> resume
   - MCP lifecycle, sandbox allow/deny paths, REST allowlist/SSRF denial, delegation persistence
4. Reliability tests:
   - concurrent chat attempts, queue retry/recovery, process restart, partial-storage recovery, corrupted skill/memory store handling
5. End-to-end tests:
   - CLI/TUI client against gateway daemon
   - Web UI against gateway daemon
   - Docker/VPS deploy smoke tests
   - scheduled job delivery and recovery
6. Security verification:
   - shell-injection corpus, prompt-injection corpus, SSRF corpus, secret-redaction corpus, untrusted-content wrapping tests

**Decisions**

- Primary trust model: one trusted operator boundary per machine/VPS. Do not claim hostile multi-tenant support in MVP or v1.
- Preserve as first-class assets: ObjectGraph, ToolRegistry, PermissionGate intent, runtime event taxonomy, TUI read models, sub-agent isolation pattern.
- De-emphasize as baseline product surface: raw host shell and unrestricted raw REST. These should become privileged capabilities.
- Surface order:
  1. CLI/TUI
  2. Web dashboard
  3. Messaging bridges (Telegram/Slack/Email/WhatsApp-equivalent)
  4. Remote nodes and voice
- Deployment order:
  1. local developer workflow
  2. Docker/Compose single-user VPS
  3. richer remote node/browser/voice topologies
- Memory order: durability, provenance, and safety before autonomous self-improvement.
- Explicit MVP exclusions: public shared bot, hostile multi-user tenancy, browser control, voice stack, mobile node control, plugin marketplace.

**Prioritized backlog**

1. Remove hardcoded OAuth secret and fail closed. Impact: Critical. Effort: XS.
2. Replace `shell=True` execution in OS tools and MCP startup. Impact: Critical. Effort: M.
3. Add REST allowlist/SSRF policy and environment scrubbing. Impact: Critical. Effort: M.
4. Make session turns serialized and immutable per request. Impact: High. Effort: M.
5. Introduce durable job queue for memory sync/prefetch/delegation persistence. Impact: High. Effort: M.
6. Replace regex-only memory scanner with layered untrusted-content safety model. Impact: High. Effort: M.
7. Add container-backed sandbox with per-agent profiles and egress policy. Impact: Critical. Effort: L.
8. Build gateway daemon/protocol/auth/health foundation. Impact: High. Effort: L.
9. Upgrade SessionStore to transactional turn/event store with search. Impact: High. Effort: M.
10. Convert CLI/TUI into gateway clients. Impact: High. Effort: M.
11. Add scheduler/jobs. Impact: High. Effort: M.
12. Add web dashboard. Impact: Medium-High. Effort: M.
13. Build skill compiler/linter/signed pack pipeline. Impact: Medium-High. Effort: M.
14. Add self-improvement review loop. Impact: Medium-High. Effort: L.
15. Add Docker/Compose, backup/restore, and VPS docs. Impact: High. Effort: M.
16. Expand CI/test/security matrix. Impact: High. Effort: M.
